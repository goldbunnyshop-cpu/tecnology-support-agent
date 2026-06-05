# agent/commands.py — Sistema unificado de comandos del grupo interno
# Consolidación de notifications.py + pausa_manager.py + nuevos comandos

import os
import re
import logging
import random
import string
from datetime import datetime, timedelta
from collections import defaultdict

logger = logging.getLogger("agentkit")

# ════════════════════════════════════════════════════════════════════════════
# CONFIGURACIÓN Y CONSTANTES
# ════════════════════════════════════════════════════════════════════════════

CHRISTIAN_NUMERO  = os.getenv("CHRISTIAN_NUMERO", "5541576331")
ULISES_NUMERO     = os.getenv("ULISES_NUMERO",    "5633500566")
GRUPO_INTERNO     = os.getenv("GRUPO_INTERNO_NOMBRE", "Taller Interno TS")
GRUPO_INTERNO_ID  = os.getenv("GRUPO_INTERNO_ID", "")

# Comandos válidos (existentes + nuevos)
COMANDOS_VALIDOS = (
    # Notificaciones
    "listo", "demora", "presupuesto", "diagnostico", "password", "llamar",
    "cita", "pausa", "reanudar", "clabe", "pago", "nota", "orden",
    "estatus", "consultar",
    # Reportes
    "reporte", "pendientes", "menu",
    # NUEVOS: Sistema de bloqueo + seguimiento con cupones
    "stop", "2nd", "unblock", "noshow",
)

TEXTO_MENU = (
    "🛠️ *Comandos — Taller Interno TS*\n\n"
    "*── Notificaciones al cliente ──*\n"
    "*listo:* [número] [equipo] → Cliente listo para recoger\n"
    "*demora:* [número] [tiempo] [equipo] → Necesita más tiempo\n"
    "*diagnostico:* [número] [equipo] [descripción] → Informa diagnóstico\n"
    "*presupuesto:* [número] [equipo] [precio] → Envía presupuesto\n"
    "*clabe:* [número] → Envía CLABE de pago\n"
    "*pago:* [número] [monto] → Instrucciones de pago\n"
    "*password:* [número] → Solicita contraseña\n"
    "*llamar:* [número] → Pide que llame\n"
    "*cita:* [número] → Puede pasar sin cita\n"
    "*pausa:* [número] → Pausa agente 2h (tú atiendes)\n"
    "*reanudar:* [número] → Reanuda agente\n\n"
    "*── CRM / Órdenes ──*\n"
    "*nota:* [folio_físico] [número] [equipo] [modelo] [falla] [total] [pago] [refaccion:costo]\n"
    "   _Ej: nota: 13054 5541576333 iPhone 13 pantalla 1200 tarjeta refaccion:500_\n"
    "*orden:* [número] [equipo] [total] [pago] [refacción?] — folio auto-asignado\n"
    "   _Ej: orden: 5541576331 PS5 2500 tarjeta 350_\n"
    "*estatus:* [folio] [recibido|proceso|listo|entregado]\n"
    "   _Ej: estatus: 00001 listo_\n"
    "*consultar:* [folio] → Datos completos de una orden\n\n"
    "*── Sistema de Seguimiento + Cupones (NUEVO) ──*\n"
    "*stop:* [número] — Bloquea cliente (agente no responde)\n"
    "*2nd:* [número] — Segundo seguimiento + cupón 15% desc (válido 8 días)\n"
    "*unblock:* [número] — Desbloquea para seguimiento normal (sin cupón)\n"
    "*noshow:* [número] — Cliente agendó pero no vino + cupón 10% desc (válido 8 días)\n\n"
    "*── Reportes ──*\n"
    "*reporte* → Resumen del día (leads + CRM + pendientes)\n"
    "*pendientes* → Pendientes de seguimiento"
)

# ════════════════════════════════════════════════════════════════════════════
# SISTEMA DE BLOQUEO EN-MEMORIA (NO PERSISTENTE)
# ════════════════════════════════════════════════════════════════════════════

# Diccionario: telefono_normalizado → razón del bloqueo
# ⚠️ OBSOLETO: el webhook entrante (main.py) NO lee este dict. El bloqueo real de
# clientes vive en la tabla StoppedNumber (BD) vía agent.memory.detener_numero /
# numero_esta_stopped. Estas funciones en memoria quedan solo por compatibilidad.
_NUMEROS_BLOQUEADOS = {}


def bloquear_numero(telefono: str, razon: str = "Bloqueado por usuario"):
    """Bloquea un número en memoria (sin persistencia)."""
    tel_norm = _normalizar_numero(telefono)
    _NUMEROS_BLOQUEADOS[tel_norm] = {
        "razon": razon,
        "bloqueado_en": datetime.now(),
    }
    logger.info(f"[BLOQUEO] Número {tel_norm} bloqueado: {razon}")


def desbloquear_numero(telefono: str):
    """Desbloquea un número."""
    tel_norm = _normalizar_numero(telefono)
    if tel_norm in _NUMEROS_BLOQUEADOS:
        del _NUMEROS_BLOQUEADOS[tel_norm]
        logger.info(f"[BLOQUEO] Número {tel_norm} desbloqueado")


def esta_bloqueado(telefono: str) -> bool:
    """Verifica si un número está bloqueado."""
    tel_norm = _normalizar_numero(telefono)
    return tel_norm in _NUMEROS_BLOQUEADOS


def obtener_razon_bloqueo(telefono: str) -> str | None:
    """Retorna la razón del bloqueo o None."""
    tel_norm = _normalizar_numero(telefono)
    if tel_norm in _NUMEROS_BLOQUEADOS:
        return _NUMEROS_BLOQUEADOS[tel_norm]["razon"]
    return None


# ════════════════════════════════════════════════════════════════════════════
# SISTEMA DE CUPONES
# ════════════════════════════════════════════════════════════════════════════

def generar_cupon(porcentaje: int) -> str:
    """
    Genera un cupón aleatorio.
    - `porcentaje=15` → "15OFF" + sufijo aleatorio (ej: 15OFFK7X2)
    - `porcentaje=10` → "10OFF" + sufijo aleatorio (ej: 10OFFCB492)
    """
    prefijo = f"{porcentaje}OFF"
    sufijo = "".join(random.choices(string.ascii_uppercase + string.digits, k=4))
    return f"{prefijo}{sufijo}"


def calcular_fecha_expiracion(dias: int = 8) -> datetime:
    """Calcula la fecha de expiración del cupón (hoy + X días)."""
    return datetime.now() + timedelta(days=dias)


# ════════════════════════════════════════════════════════════════════════════
# PARSERS DE NÚMEROS Y UTILIDADES
# ════════════════════════════════════════════════════════════════════════════

def _normalizar_numero(numero: str) -> str:
    """
    Elimina el prefijo de país. Convierte a 10 dígitos locales.
    52  + 10 dígitos = 12 dígitos  → elimina '52'
    521 + 10 dígitos = 13 dígitos  → elimina '521'
    152 + 10 dígitos = 13 dígitos  → elimina '152'
    """
    n = re.sub(r"\D", "", numero or "")
    if len(n) == 13 and n.startswith("521"):
        return n[3:]
    if len(n) == 13 and n.startswith("152"):
        return n[3:]
    if len(n) == 12 and n.startswith("52"):
        return n[2:]
    return n


def _formatear_numero_destino(phone: str) -> tuple[str, str | None]:
    """
    Formatea número al formato de Whapi: 521XXXXXXXXXX (13 dígitos).
    Retorna (numero_formateado, advertencia_o_None).
    """
    n = re.sub(r"\D", "", phone or "")

    if len(n) == 10:
        return f"521{n}", None
    if len(n) == 12 and n.startswith("52"):
        return f"521{n[2:]}", None
    if len(n) == 13 and n.startswith("521"):
        return n, None
    if len(n) == 11 and n.startswith("1"):
        return n, None
    if len(n) >= 11:
        return n, None

    advertencia = (
        "⚠️ Número inválido. Incluye código de país.\n"
        "Ejemplo: 5541576331 (México) o 12125551234 (USA)"
    )
    return "", advertencia


def _extraer_phone_y_resto(payload: str) -> tuple[str, str]:
    """Extrae teléfono (primer token de dígitos) y resto del payload."""
    partes = payload.strip().split(None, 1)
    if not partes:
        return "", ""
    phone = re.sub(r"\D", "", partes[0])
    resto = partes[1].strip() if len(partes) > 1 else ""
    return phone, resto


# ════════════════════════════════════════════════════════════════════════════
# PARSERS DE COMANDOS (Todos los existentes)
# ════════════════════════════════════════════════════════════════════════════

def parsear_comando(texto: str) -> tuple[str, str] | None:
    """Detecta si el texto es un comando válido. Retorna (comando, payload) o None."""
    if not texto:
        return None
    texto = texto.strip()
    for cmd in COMANDOS_VALIDOS:
        patron = re.compile(rf"^{cmd}\s*:", re.IGNORECASE)
        if patron.match(texto):
            payload = texto[texto.index(":")+1:].strip()
            return cmd.lower(), payload
    return None


def parsear_listo(payload: str) -> tuple[str, str] | None:
    """listo: PHONE EQUIPO"""
    phone, equipo = _extraer_phone_y_resto(payload)
    return (phone, equipo) if phone and equipo else None


def parsear_demora(payload: str) -> tuple[str, str, str] | None:
    """demora: PHONE TIEMPO EQUIPO"""
    phone, resto = _extraer_phone_y_resto(payload)
    if not phone or not resto:
        return None
    time_match = re.match(
        r"^(\d+\s*(?:hora|horas|minuto|minutos|d[íi]a|d[íi]as|dias|semana|semanas)\b\s*)",
        resto, re.IGNORECASE,
    )
    if time_match:
        tiempo = time_match.group(1).strip()
        equipo = resto[time_match.end():].strip()
    else:
        partes = resto.split(None, 1)
        tiempo = partes[0]
        equipo = partes[1] if len(partes) > 1 else ""
    return (phone, tiempo, equipo) if equipo else None


def parsear_presupuesto(payload: str) -> tuple[str, str, str] | None:
    """presupuesto: PHONE EQUIPO PRECIO"""
    phone, resto = _extraer_phone_y_resto(payload)
    if not phone or not resto:
        return None
    partes = resto.split()
    if len(partes) < 2:
        return None
    precio_raw = partes[-1].lstrip("$").replace(",", "")
    equipo = " ".join(partes[:-1])
    return (phone, equipo, precio_raw)


def parsear_diagnostico(payload: str) -> tuple[str, str, str] | None:
    """diagnostico: PHONE EQUIPO DESCRIPCIÓN"""
    phone, resto = _extraer_phone_y_resto(payload)
    if not phone or not resto:
        return None
    partes = resto.split(None, 1)
    equipo = partes[0]
    descripcion = partes[1].strip() if len(partes) > 1 else ""
    return (phone, equipo, descripcion) if descripcion else None


def parsear_phone_simple(payload: str) -> str | None:
    """password/llamar/clabe: PHONE"""
    phone = re.sub(r"\D", "", payload.strip().split()[0]) if payload.strip() else ""
    return phone if phone else None


def parsear_pago(payload: str) -> tuple[str, str] | None:
    """pago: PHONE MONTO"""
    phone, monto = _extraer_phone_y_resto(payload)
    if not phone or not monto:
        return None
    monto = re.sub(r"[$,\s]", "", monto).strip()
    return (phone, monto) if monto else None


_FORMAS_PAGO = ("efectivo", "tarjeta", "transferencia", "trans")


def parsear_nota(payload: str) -> dict | None:
    """nota: FOLIO_FISICO TELÉFONO EQUIPO [MODELO] FALLA TOTAL FORMA_PAGO [refaccion:COSTO]"""
    refaccion = 0.0
    ref_match = re.search(r"\brefaccion:(\d+(?:\.\d+)?)\b", payload, re.IGNORECASE)
    if ref_match:
        refaccion = float(ref_match.group(1))
        payload = payload[: ref_match.start()] + payload[ref_match.end():]

    partes = payload.strip().split()
    if len(partes) < 6:
        return None

    folio_fisico = partes[0]
    phone = re.sub(r"\D", "", partes[1])
    if not phone:
        return None

    resto = partes[2:]
    if not resto or resto[-1].lower() not in _FORMAS_PAGO:
        return None
    forma_pago = resto[-1].lower()
    resto = resto[:-1]

    if not resto or not re.match(r"^\d+(\.\d+)?$", resto[-1]):
        return None
    total = float(resto[-1])
    resto = resto[:-1]

    if not resto:
        return None
    if len(resto) == 1:
        equipo, modelo, falla = resto[0], "", ""
    elif len(resto) == 2:
        equipo, modelo, falla = resto[0], "", resto[1]
    else:
        equipo = resto[0]
        falla  = resto[-1]
        modelo = " ".join(resto[1:-1])

    return {
        "folio_fisico": folio_fisico,
        "phone":        phone,
        "equipo":       equipo,
        "modelo":       modelo,
        "falla":        falla,
        "total":        total,
        "forma_pago":   forma_pago,
        "refaccion":    refaccion,
    }


def parsear_orden_crm(payload: str) -> dict | None:
    """orden: TELÉFONO EQUIPO... TOTAL PAGO [REFACCION]"""
    partes = payload.strip().split()
    if len(partes) < 4:
        return None

    phone = re.sub(r"\D", "", partes[0])
    if not phone:
        return None

    resto = partes[1:]
    refaccion = 0.0
    if len(resto) >= 2 and re.match(r"^\d+(\.\d+)?$", resto[-1]) and resto[-2].lower() in _FORMAS_PAGO:
        refaccion = float(resto[-1])
        resto = resto[:-1]

    if not resto or resto[-1].lower() not in _FORMAS_PAGO:
        return None
    forma_pago = resto[-1].lower()
    resto = resto[:-1]

    if not resto or not re.match(r"^\d+(\.\d+)?$", resto[-1]):
        return None
    total = float(resto[-1])
    resto = resto[:-1]

    equipo = " ".join(resto)
    if not equipo:
        return None

    return {
        "phone":      phone,
        "equipo":     equipo,
        "total":      total,
        "forma_pago": forma_pago,
        "refaccion":  refaccion,
    }


_MAPA_ESTATUS = {
    "recibido":   "Recibido",
    "proceso":    "En proceso",
    "en proceso": "En proceso",
    "listo":      "Listo",
    "entregado":  "Entregado",
}


def parsear_estatus_crm(payload: str) -> tuple[str, str] | None:
    """estatus: FOLIO NUEVO_ESTATUS"""
    partes = payload.strip().split(None, 1)
    if len(partes) < 2:
        return None
    folio      = partes[0]
    estatus_raw = partes[1].strip().lower()
    estatus    = _MAPA_ESTATUS.get(estatus_raw)
    return (folio, estatus) if estatus else None


# ════════════════════════════════════════════════════════════════════════════
# EXTRACCIÓN DE NOMBRE DEL CLIENTE
# ════════════════════════════════════════════════════════════════════════════

PALABRAS_COMUNES = {
    "Hola", "Buenos", "Buenas", "Gracias", "Claro", "Tecnology",
    "Support", "Entiendo", "Perfecto", "Excelente", "Muchas", "Disculpe",
    "Sofia", "Valentina", "Camila", "Diego", "Andres", "Rodrigo",
}


def extraer_nombre_cliente(historial: list[dict]) -> str:
    """Intenta extraer nombre del cliente del historial."""
    for msg in historial:
        if msg["role"] == "assistant":
            matches = re.findall(r"\bHola,?\s+([A-ZÁÉÍÓÚÑ][a-záéíóúñ]{2,})", msg["content"])
            for m in matches:
                if m not in PALABRAS_COMUNES:
                    return m
    return ""


# ════════════════════════════════════════════════════════════════════════════
# PROCESADOR PRINCIPAL DE COMANDOS
# ════════════════════════════════════════════════════════════════════════════

async def procesar_comando_grupo(
    msg,
    proveedor,
    guardar_mensaje_fn,
    obtener_historial_fn,
) -> bool:
    """
    Procesa un mensaje del grupo 'Taller Interno TS'.
    CAMBIO: Ahora acepta a CUALQUIERA en el grupo (sin restricción de remitente).
    Retorna True si era un comando válido, False si no.
    """
    nombre_grupo = getattr(msg, "nombre_grupo", "")
    chat_id_raw = getattr(msg, "chat_id_raw", msg.telefono)
    texto_cmd = msg.texto or ""

    # Verificar que es el grupo correcto
    if GRUPO_INTERNO.lower() not in nombre_grupo.lower():
        logger.debug(f"[CMD] Grupo '{nombre_grupo}' no contiene '{GRUPO_INTERNO}'")
        return False

    # CAMBIO: Aceptar a CUALQUIERA en el grupo (sin verificación de remitente)
    logger.info(f"[CMD] Mensaje del grupo '{nombre_grupo}': '{texto_cmd[:80]}'")

    texto_lower = texto_cmd.strip().lower()

    # ── menu ──
    if texto_lower == "menu" or texto_lower == "menu:":
        await proveedor.enviar_mensaje(chat_id_raw, TEXTO_MENU)
        logger.info("[CMD] Menú enviado")
        return True

    # ── reporte ──
    if texto_lower == "reporte" or texto_lower == "reporte:":
        await _cmd_reporte_dia(chat_id_raw, proveedor, obtener_historial_fn)
        return True

    # ── reanudar todo ──
    if texto_lower == "reanudar todo":
        from agent.memory import limpiar_todas_pausas
        count = await limpiar_todas_pausas()
        await proveedor.enviar_mensaje(chat_id_raw,
            f"✅ Todas las pausas limpiadas ({count})\n"
            f"El agente responde a todos."
        )
        return True

    # Normalizar espacios invisibles de WhatsApp
    texto_normalizado = (
        texto_cmd.strip()
        .replace('​', '')   # Zero-width space
        .replace(' ', ' ')  # Non-breaking space
    )
    resultado = parsear_comando(texto_normalizado)
    if not resultado:
        logger.debug(f"[CMD] No es comando válido: '{texto_cmd[:60]}'")
        return False

    cmd, payload = resultado
    logger.info(f"[CMD] Comando detectado: {cmd} — {payload[:80]}")

    async def _responder(texto: str):
        await proveedor.enviar_mensaje(chat_id_raw, texto)

    async def _notificar_cliente(phone_raw: str, mensaje: str) -> bool:
        phone_fmt, advertencia = _formatear_numero_destino(phone_raw)
        if advertencia:
            await _responder(advertencia)
            return False
        from agent.memory import numero_esta_stopped
        if await numero_esta_stopped(phone_fmt):
            await _responder(
                f"⛔ Número {phone_fmt} está DETENIDO (stop). "
                f"Reactívalo con 'unblock: {phone_fmt}' u 'on: {phone_fmt}' para enviarle mensajes."
            )
            return False
        enviado = await proveedor.enviar_mensaje(phone_fmt, mensaje)
        if enviado:
            await guardar_mensaje_fn(phone_fmt, "assistant", mensaje)
        return enviado

    # ════════════════════════════════════════════════════════════════════════════
    # COMANDOS EXISTENTES (notificaciones al cliente)
    # ════════════════════════════════════════════════════════════════════════════

    if cmd == "listo":
        parsed = parsear_listo(payload)
        if not parsed:
            await _responder("⚠️ Formato: listo: NÚMERO EQUIPO\nEj: listo: 5541576331 iPhone 13")
            return True
        phone, equipo = parsed
        msg_txt = f"¡Listo! Tu {equipo} está listo para recoger.\n¿Cuándo lo pasas por el módulo? 😊"
        await _notificar_cliente(phone, msg_txt)
        await _responder(f"✅ '{equipo}' notificado a {phone}")
        return True

    if cmd == "demora":
        parsed = parsear_demora(payload)
        if not parsed:
            await _responder("⚠️ Formato: demora: NÚMERO TIEMPO EQUIPO\nEj: demora: 5541576331 2 horas iPhone 13")
            return True
        phone, tiempo, equipo = parsed
        msg_txt = f"Actualizamos: tu {equipo} necesita *{tiempo} más*. Ya casi está.\nTe avisamos cuando esté listo 🔔"
        await _notificar_cliente(phone, msg_txt)
        await _responder(f"✅ Demora de {tiempo} notificada a {phone}")
        return True

    if cmd == "presupuesto":
        parsed = parsear_presupuesto(payload)
        if not parsed:
            await _responder("⚠️ Formato: presupuesto: NÚMERO EQUIPO PRECIO\nEj: presupuesto: 5541576331 iPhone 13 500")
            return True
        phone, equipo, precio = parsed
        msg_txt = f"Presupuesto de tu {equipo}:\n\n💰 *${precio} MXN*\n\n¿Quieres que procedamos con la reparación?"
        await _notificar_cliente(phone, msg_txt)
        await _responder(f"✅ Presupuesto de ${precio} enviado a {phone}")
        return True

    if cmd == "diagnostico":
        parsed = parsear_diagnostico(payload)
        if not parsed:
            await _responder("⚠️ Formato: diagnostico: NÚMERO EQUIPO DESCRIPCIÓN\nEj: diagnostico: 5541576331 iPhone 13 pantalla rota")
            return True
        phone, equipo, desc = parsed
        msg_txt = f"Diagnóstico de tu {equipo}:\n\n🔧 {desc}\n\nTe mandamos presupuesto en breve."
        await _notificar_cliente(phone, msg_txt)
        await _responder(f"✅ Diagnóstico enviado a {phone}")
        return True

    if cmd == "password":
        phone = parsear_phone_simple(payload)
        if not phone:
            await _responder("⚠️ Formato: password: NÚMERO\nEj: password: 5541576331")
            return True
        msg_txt = "Para poder hacer el diagnóstico, necesitamos la contraseña de tu dispositivo. ¿Nos la compartes? 🔐"
        await _notificar_cliente(phone, msg_txt)
        await _responder(f"✅ Solicitud de contraseña enviada a {phone}")
        return True

    if cmd == "llamar":
        phone = parsear_phone_simple(payload)
        if not phone:
            await _responder("⚠️ Formato: llamar: NÚMERO")
            return True
        msg_txt = "Hola, necesitamos aclarar algunos detalles. ¿Podrías darnos una llamada? 📞"
        await _notificar_cliente(phone, msg_txt)
        await _responder(f"✅ Solicitud de llamada enviada a {phone}")
        return True

    if cmd == "cita":
        phone = parsear_phone_simple(payload)
        if not phone:
            await _responder("⚠️ Formato: cita: NÚMERO")
            return True
        msg_txt = "Puedes pasar cuando gustes, sin necesidad de agendar cita. Estamos en:\n\n📍 Plazuela de la Fama 1, Col. La Fama, CDMX\n⏰ Lun-Sab: 10:00-19:00"
        await _notificar_cliente(phone, msg_txt)
        await _responder(f"✅ Info de cita enviada a {phone}")
        return True

    if cmd == "pausa":
        phone = parsear_phone_simple(payload)
        if not phone:
            await _responder("⚠️ Formato: pausa: NÚMERO")
            return True
        phone_fmt, _ = _formatear_numero_destino(phone)
        try:
            from agent.pausa_manager import obtener_pausa_manager
            pausa_mgr = await obtener_pausa_manager()
            exito, mensaje = await pausa_mgr.procesar_pausa(
                phone_fmt,
                razon="Pausa manual del operador",
                duracion_horas=2
            )
            if exito:
                await _responder(f"⏸️  {mensaje}")
            else:
                await _responder(f"❌ {mensaje}")
        except Exception as e:
            logger.error(f"[PAUSA] Error: {e}")
            await _responder(f"❌ Error: {e}")
        return True

    if cmd == "reanudar":
        phone = parsear_phone_simple(payload)
        if not phone:
            await _responder("⚠️ Formato: reanudar: NÚMERO")
            return True
        phone_fmt, _ = _formatear_numero_destino(phone)
        try:
            from agent.pausa_manager import obtener_pausa_manager
            pausa_mgr = await obtener_pausa_manager()
            exito, mensaje = await pausa_mgr.reanudar_pausa(phone_fmt)
            if exito:
                await _responder(f"▶️  {mensaje}")
            else:
                await _responder(f"❌ {mensaje}")
        except Exception as e:
            logger.error(f"[REANUDAR] Error: {e}")
            await _responder(f"❌ Error: {e}")
        return True

    if cmd == "clabe":
        phone = parsear_phone_simple(payload)
        if not phone:
            await _responder("⚠️ Formato: clabe: NÚMERO")
            return True
        clabe = os.getenv("CLABE_CUENTA", "")
        if not clabe:
            await _responder("❌ CLABE no configurada en .env")
            return True
        msg_txt = f"Cuenta para transferencia (CLABE):\n\n💳 {clabe}"
        await _notificar_cliente(phone, msg_txt)
        await _responder(f"✅ CLABE enviada a {phone}")
        return True

    if cmd == "pago":
        parsed = parsear_pago(payload)
        if not parsed:
            await _responder("⚠️ Formato: pago: NÚMERO MONTO\nEj: pago: 5541576331 1200")
            return True
        phone, monto = parsed
        msg_txt = f"Perfecto, el total es *${monto} MXN*.\n\nTienes estas opciones:\n• Efectivo en el módulo\n• Transferencia (puedo darte CLABE)\n• Tarjeta 💳"
        await _notificar_cliente(phone, msg_txt)
        await _responder(f"✅ Opción de pago de ${monto} enviada a {phone}")
        return True

    # ════════════════════════════════════════════════════════════════════════════
    # COMANDOS CRM (nota, orden, estatus, consultar)
    # ════════════════════════════════════════════════════════════════════════════

    if cmd == "nota":
        parsed = parsear_nota(payload)
        if not parsed:
            await _responder("⚠️ Formato: nota: FOLIO_FISICO NÚMERO EQUIPO [MODELO] FALLA TOTAL PAGO [refaccion:COSTO]")
            return True
        try:
            from agent.crm import registrar_orden
            phone_fmt, _ = _formatear_numero_destino(parsed["phone"])
            historial = await obtener_historial_fn(phone_fmt)
            nombre = extraer_nombre_cliente(historial) or phone_fmt
            resultado = await registrar_orden(
                telefono=phone_fmt, cliente=nombre, equipo=parsed["equipo"],
                modelo=parsed["modelo"], falla=parsed["falla"],
                total=parsed["total"], forma_pago=parsed["forma_pago"],
                refaccion=parsed["refaccion"],
            )
            com_txt = f"${resultado['comision']:.2f}" if resultado["comision"] else "$0.00"
            drive_txt = f"\n📁 Drive: {resultado['link_drive']}" if resultado["link_drive"] else ""
            await _responder(
                f"✅ Nota #{parsed['folio_fisico']} registrada\n"
                f"👤 {nombre}\n"
                f"💰 ${parsed['total']:,.0f}\n"
                f"💳 Comisión: {com_txt}\n"
                f"📊 Ganancia: ${resultado['ganancia']:,.2f}{drive_txt}"
            )
        except Exception as e:
            await _responder(f"❌ Error registrando nota: {e}")
        return True

    if cmd == "orden":
        parsed = parsear_orden_crm(payload)
        if not parsed:
            await _responder("⚠️ Formato: orden: NÚMERO EQUIPO TOTAL PAGO [REFACCIÓN]")
            return True
        try:
            from agent.crm import registrar_orden
            phone_fmt, _ = _formatear_numero_destino(parsed["phone"])
            historial = await obtener_historial_fn(phone_fmt)
            nombre = extraer_nombre_cliente(historial) or phone_fmt
            resultado = await registrar_orden(
                telefono=phone_fmt, cliente=nombre, equipo=parsed["equipo"],
                modelo="", falla="", total=parsed["total"],
                forma_pago=parsed["forma_pago"], refaccion=parsed["refaccion"],
            )
            await _responder(
                f"✅ Orden #{resultado['folio_crm']} registrada\n"
                f"👤 {nombre}\n"
                f"💰 ${resultado['total']}\n"
                f"📊 Ganancia: ${resultado['ganancia']}"
            )
        except Exception as e:
            await _responder(f"❌ Error: {e}")
        return True

    if cmd == "estatus":
        parsed = parsear_estatus_crm(payload)
        if not parsed:
            await _responder("⚠️ Formato: estatus: FOLIO ESTATUS\nEstatus válidos: recibido | proceso | listo | entregado")
            return True
        folio, estatus = parsed
        try:
            from agent.crm import actualizar_estatus_orden
            ok = await actualizar_estatus_orden(folio, estatus)
            if ok:
                await _responder(f"✅ Folio #{folio.zfill(4)} → *{estatus}*")
            else:
                await _responder(f"❌ Folio #{folio.zfill(4)} no encontrado")
        except Exception as e:
            await _responder(f"❌ Error: {e}")
        return True

    if cmd == "consultar":
        folio = payload.strip().split()[0] if payload.strip() else ""
        if not folio:
            await _responder("⚠️ Formato: consultar: FOLIO")
            return True
        try:
            from agent.crm import consultar_orden
            orden = await consultar_orden(folio)
            if not orden:
                await _responder(f"❌ Folio #{folio.zfill(4)} no encontrado")
            else:
                await _responder(
                    f"📋 *Orden #{orden['folio']}*\n"
                    f"👤 {orden['cliente']}\n"
                    f"🔧 {orden['equipo']} {orden['modelo']}\n"
                    f"📊 Estatus: *{orden['estatus']}*\n"
                    f"💰 ${orden['total']}"
                )
        except Exception as e:
            await _responder(f"❌ Error: {e}")
        return True

    # ════════════════════════════════════════════════════════════════════════════
    # NUEVOS COMANDOS: SISTEMA DE BLOQUEO
    # ════════════════════════════════════════════════════════════════════════════

    if cmd == "stop":
        """Detiene al cliente en el store PERSISTENTE (tabla StoppedNumber en BD).

        Antes escribía en un dict en memoria que NADIE leía en el webhook entrante
        → el agente seguía respondiendo. Ahora usa detener_numero(), el MISMO store
        que revisa main.py antes de procesar cada mensaje del cliente.
        """
        phone = re.sub(r"\D", "", payload)  # tolera números con espacios/guiones
        if not phone:
            await _responder("⚠️ Formato: stop: NÚMERO\nEj: stop: 5541576331")
            return True
        phone_fmt, advertencia = _formatear_numero_destino(phone)
        if advertencia:
            await _responder(advertencia)
            return True
        from agent.memory import detener_numero
        _, mensaje = await detener_numero(phone_fmt, razon="comando_stop", detenido_por="grupo")
        await _responder(mensaje)
        return True

    if cmd == "2nd":
        """
        Segundo seguimiento: Genera mensaje persuasivo con cupón 15% descuento.
        Lee últimos 10 mensajes como contexto, llama a Claude con prompt específico.
        Cupón aplica cuando cliente acepta presupuesto y reparación.
        Registra cupón en ClientePerfil (Google Sheets).
        """
        phone = parsear_phone_simple(payload)
        if not phone:
            await _responder("⚠️ Formato: 2nd: NÚMERO\nEj: 2nd: 5541576331")
            return True
        phone_fmt, advertencia = _formatear_numero_destino(phone)
        if advertencia:
            await _responder(advertencia)
            return True

        # Obtener últimos 10 mensajes para contexto
        try:
            historial = await obtener_historial_fn(phone_fmt, limite=10)
            nombre = extraer_nombre_cliente(historial) or phone_fmt

            # Generar cupón 15% (válido 8 días)
            cupon = generar_cupon(15)
            fecha_expira = calcular_fecha_expiracion(8)
            fecha_expira_fmt = fecha_expira.strftime("%d/%m/%Y")

            # Registrar cupón en CRM (ClientePerfil)
            from agent import crm
            await crm.registrar_cupon(phone_fmt, cupon, porcentaje=15, dias_validez=8)

            # Generar mensaje persuasivo usando Claude
            from agent.brain import generar_respuesta

            prompt_contexto = (
                f"Cliente: {nombre}\n"
                f"Última actividad: {len(historial)} mensajes en historial\n"
                f"Cupón: {cupon} (15% descuento, válido hasta {fecha_expira_fmt})\n"
                f"Tarea: Genera un mensaje persuasivo de segundo seguimiento para intentar "
                f"agendar una visita al taller. Incluye:\n"
                f"1. Empatía — hace tiempo no hablamos\n"
                f"2. Oferta: 15% descuento si agenda dentro de 8 días\n"
                f"3. Cupón: {cupon}\n"
                f"4. Instrucción: 'Al aceptar la reparación, muestra este cupón al técnico para aplicar descuento'\n"
                f"5. Disponibilidad y horarios del taller"
            )

            mensaje_seguimiento = await generar_respuesta(prompt_contexto, historial)

            # Enviar mensaje al cliente
            exito = await proveedor.enviar_mensaje(phone_fmt, mensaje_seguimiento)

            if exito:
                # Reactivar el número (si estaba detenido) para que el seguimiento fluya
                from agent.memory import reactivar_numero
                await reactivar_numero(phone_fmt, reactivado_por="comando_2nd")
                logger.info(f"[2ND] Mensaje de seguimiento enviado a {phone_fmt} — Cupón: {cupon}")

                # Confirmar en grupo
                await _responder(
                    f"✅ Segundo seguimiento enviado a {nombre} ({phone_fmt})\n\n"
                    f"🎟️ Cupón: {cupon}\n"
                    f"⏰ Válido hasta: {fecha_expira_fmt}\n"
                    f"📝 Mensaje:\n{mensaje_seguimiento}"
                )
            else:
                await _responder(f"❌ Error enviando mensaje a {phone_fmt}")
        except Exception as e:
            logger.error(f"[2ND] Error: {e}")
            await _responder(f"❌ Error en seguimiento: {e}")
        return True

    if cmd == "unblock":
        """Reactiva un número detenido (mismo store persistente que 'stop')."""
        phone = re.sub(r"\D", "", payload)
        if not phone:
            await _responder("⚠️ Formato: unblock: NÚMERO\nEj: unblock: 5541576331")
            return True
        phone_fmt, advertencia = _formatear_numero_destino(phone)
        if advertencia:
            await _responder(advertencia)
            return True

        from agent.memory import reactivar_numero
        _, mensaje = await reactivar_numero(phone_fmt, reactivado_por="grupo")
        await _responder(mensaje)
        return True

    if cmd == "noshow":
        """
        No-show: Cliente agendó cita pero no se presentó.
        Genera mensaje empático explorando por qué, luego ofrece cupón 10% descuento.
        Registra cupón en ClientePerfil (Google Sheets).
        """
        phone = parsear_phone_simple(payload)
        if not phone:
            await _responder("⚠️ Formato: noshow: NÚMERO\nEj: noshow: 5541576331")
            return True
        phone_fmt, advertencia = _formatear_numero_destino(phone)
        if advertencia:
            await _responder(advertencia)
            return True

        # Obtener últimos 10 mensajes para contexto
        try:
            historial = await obtener_historial_fn(phone_fmt, limite=10)
            nombre = extraer_nombre_cliente(historial) or phone_fmt

            # Generar cupón 10% (válido 8 días)
            cupon = generar_cupon(10)
            fecha_expira = calcular_fecha_expiracion(8)
            fecha_expira_fmt = fecha_expira.strftime("%d/%m/%Y")

            # Registrar cupón en CRM (ClientePerfil)
            from agent import crm
            await crm.registrar_cupon(phone_fmt, cupon, porcentaje=10, dias_validez=8)

            # Generar mensaje usando Claude: Mensaje empático de reconexión con cupón
            from agent.brain import generar_mensaje_noshow

            mensaje_noshow = await generar_mensaje_noshow(
                telefono=phone_fmt,
                nombre_cliente=nombre,
                historial=historial,
                cupon=cupon,
                fecha_expira=fecha_expira_fmt
            )

            # Enviar mensaje al cliente
            exito = await proveedor.enviar_mensaje(phone_fmt, mensaje_noshow)

            if exito:
                logger.info(f"[NOSHOW] Mensaje de reconexión enviado a {phone_fmt} — Cupón: {cupon}")

                # Confirmar en grupo
                await _responder(
                    f"✅ Follow-up de no-show enviado a {nombre} ({phone_fmt})\n\n"
                    f"🎟️ Cupón: {cupon}\n"
                    f"⏰ Válido hasta: {fecha_expira_fmt}\n"
                    f"📝 Mensaje:\n{mensaje_noshow}"
                )
            else:
                await _responder(f"❌ Error enviando mensaje a {phone_fmt}")
        except Exception as e:
            logger.error(f"[NOSHOW] Error: {e}")
            await _responder(f"❌ Error en no-show: {e}")
        return True

    # ════════════════════════════════════════════════════════════════════════════
    # COMANDOS DE REPORTE
    # ════════════════════════════════════════════════════════════════════════════

    if cmd == "pendientes":
        await _cmd_pendientes_seguimiento(chat_id_raw, proveedor, obtener_historial_fn)
        return True

    logger.warning(f"[CMD] Comando no implementado: {cmd}")
    return False


# ════════════════════════════════════════════════════════════════════════════
# FUNCIONES DE REPORTE (auxiliares)
# ════════════════════════════════════════════════════════════════════════════

async def _cmd_reporte_dia(chat_id: str, proveedor, obtener_historial_fn):
    """Resumen del día."""
    try:
        from agent.leads import obtener_resumen_leads
        from agent.crm import obtener_ordenes_del_dia, obtener_ordenes_por_estatus
        from zoneinfo import ZoneInfo

        resumen = await obtener_resumen_leads()
        hoy_ord = await obtener_ordenes_del_dia()
        pendientes = await obtener_ordenes_por_estatus("Listo")

        ingresos = sum(float(o.get("total", 0) or 0) for o in hoy_ord)
        hoy_fmt = datetime.now(ZoneInfo("America/Mexico_City")).strftime("%d/%m/%Y")

        msg = (
            f"📊 *Resumen — {hoy_fmt}*\n\n"
            f"*Leads:* {resumen.get('convertido', 0)} convertidos | "
            f"{resumen.get('en_seguimiento', 0)} en seguimiento\n"
            f"*CRM:* {len(hoy_ord)} órdenes | ${ingresos:,.2f}\n"
            f"*Listos:* {len(pendientes)}"
        )
        await proveedor.enviar_mensaje(chat_id, msg)
    except Exception as e:
        logger.error(f"[CMD] Error reporte: {e}")
        await proveedor.enviar_mensaje(chat_id, f"❌ Error: {e}")


async def _cmd_pendientes_seguimiento(chat_id: str, proveedor, obtener_historial_fn):
    """Lista pendientes de seguimiento."""
    try:
        from agent.leads import obtener_pendientes_seguimiento
        import re as _re

        pendientes = await obtener_pendientes_seguimiento()
        if not pendientes:
            await proveedor.enviar_mensaje(chat_id, "✅ No hay pendientes.")
            return

        lineas = [f"⏳ *Pendientes de seguimiento* — {len(pendientes)}\n"]
        for lead in pendientes[:20]:
            seg_n = lead.seguimientos_enviados
            lineas.append(
                f"• {lead.telefono} | {lead.prioridad.upper()} | "
                f"seg {seg_n}/4"
            )

        msg = "\n".join(lineas)
        if len(pendientes) > 20:
            msg += f"\n... y {len(pendientes)-20} más"

        await proveedor.enviar_mensaje(chat_id, msg)
    except Exception as e:
        logger.error(f"[CMD] Error pendientes: {e}")
        await proveedor.enviar_mensaje(chat_id, f"❌ Error: {e}")


# ════════════════════════════════════════════════════════════════════════════
# INICIALIZACIÓN DE SISTEMA DE CUPONES
# ════════════════════════════════════════════════════════════════════════════

async def inicializar_sistema_cupones():
    """
    Inicializa el sistema de cupones: crea la hoja ClientePerfil en Google Sheets.
    Debe llamarse una sola vez en el startup de main.py.
    """
    try:
        from agent import crm
        exito = await crm.crear_hoja_cupones()
        if exito:
            logger.info("[CUPONES] Sistema de cupones inicializado correctamente")
        else:
            logger.warning("[CUPONES] No se pudo crear/verificar hoja ClientePerfil (CRM desactivado?)")
    except Exception as e:
        logger.warning(f"[CUPONES] Error inicializando sistema: {e}")
