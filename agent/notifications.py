# agent/notifications.py — Comandos del grupo interno y alertas a Christian
# Generado por AgentKit

import os
import re
import logging
from datetime import datetime

logger = logging.getLogger("agentkit")

CHRISTIAN_NUMERO  = os.getenv("CHRISTIAN_NUMERO", "5541576331")
ULISES_NUMERO     = os.getenv("ULISES_NUMERO",    "5633500566")
GRUPO_INTERNO     = os.getenv("GRUPO_INTERNO_NOMBRE", "Taller Interno TS")
GRUPO_INTERNO_ID  = os.getenv("GRUPO_INTERNO_ID", "")  # chat_id del grupo @g.us para notificaciones

# Palabras clave que activan alerta a Christian en mensajes del cliente
KEYWORDS_ALERTA = [
    "garantía", "garantia", "queja", "molesto", "molesta",
    "enojado", "enojada", "no funciona", "no sirve", "urgente",
    "urgentemente", "mal servicio", "muy mal",
]

KEYWORDS_PRESUPUESTO_REFACCION = [
    "refacción", "refaccion", "pantalla", "display", "batería", "bateria",
    "centro de carga", "puerto usb", "bocina", "altavoz", "micrófono", "microfono",
    "cuánto cuesta", "cuanto cuesta", "precio de", "cuánto sale", "cuanto sale",
    "cotización", "cotizacion", "presupuesto de",
]

KEYWORDS_CITA = [
    "agendo", "voy a ir", "paso mañana", "paso hoy", "iré", "me apunto",
    "me anotas", "apártame", "apartame", "reserva", "aparto un espacio",
    "confirmo", "confirmado",
]


# ──────────────────────────────────────────────
# Parsers de comandos
# ──────────────────────────────────────────────

COMANDOS_VALIDOS = ("listo", "demora", "presupuesto", "diagnostico", "password", "llamar", "cita", "pausa", "reanudar", "clabe", "pago", "nota", "orden", "estatus", "consultar", "marcar seguimiento")

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
    "*consultar:* [folio] → Datos completos de una orden\n"
    "   _Ej: consultar: 00001_\n\n"
    "*── Reportes ──*\n"
    "*reporte* → Resumen del día (leads + CRM + pendientes)\n"
    "*reporte seguimiento* → Lista completa de clientes\n"
    "*pendientes seguimiento* → Solo los pendientes de contactar\n"
    "*marcar seguimiento:* [número] → Marca como atendido\n"
    "   _Ej: marcar seguimiento: 5541576331_"
)


def _normalizar_numero(numero: str) -> str:
    """Elimina el prefijo de país que agrega Whapi en mensajes de grupo.
    Convierte cualquier formato mexicano a 10 dígitos locales para comparar.
      52  + 10 dígitos = 12 dígitos  (ej: 525633500566  → 5633500566)
      521 + 10 dígitos = 13 dígitos  (ej: 5215541576331 → 5541576331)
      152 + 10 dígitos = 13 dígitos  (ej: 1525541576331 → 5541576331)
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
    Formatea el número de destino al formato que espera Whapi para envío.
    México siempre debe enviarse como 521XXXXXXXXXX (13 dígitos).
    Retorna (numero_formateado, advertencia_o_None).

    Reglas:
      10 dígitos                    → México local   → 521XXXXXXXXXX
      12 dígitos empezando con 52   → México sin 1   → 521XXXXXXXXXX
      13 dígitos empezando con 521  → México completo → sin cambio
      11 dígitos empezando con 1    → USA/Canadá      → sin cambio
      >= 11 dígitos (otros)         → tiene código de país → sin cambio
      < 10 dígitos o ambiguo        → advertencia en el grupo
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
        "⚠️ Número internacional detectado. Por favor incluye el código de país.\n"
        "Ejemplo:\n"
        "57XXXXXXXXXX para Colombia\n"
        "1XXXXXXXXXX para USA/California"
    )
    return "", advertencia


def parsear_comando(texto: str) -> tuple[str, str] | None:
    """Detecta si el texto es un comando válido. Retorna (comando, payload) o None."""
    if not texto:
        return None
    texto = texto.strip()
    for cmd in COMANDOS_VALIDOS:
        patron = re.compile(rf"^{cmd}\s*:", re.IGNORECASE)
        if patron.match(texto):
            payload = texto[texto.index(":")+1:].strip()
            return cmd, payload
    return None


def _extraer_phone_y_resto(payload: str) -> tuple[str, str]:
    """Extrae el teléfono (primer token de dígitos) y el resto del payload."""
    partes = payload.strip().split(None, 1)
    if not partes:
        return "", ""
    phone = re.sub(r"\D", "", partes[0])  # solo dígitos
    resto = partes[1].strip() if len(partes) > 1 else ""
    return phone, resto


def parsear_listo(payload: str) -> tuple[str, str] | None:
    """listo: PHONE EQUIPO → (phone, equipo)"""
    phone, equipo = _extraer_phone_y_resto(payload)
    if not phone or not equipo:
        return None
    return phone, equipo


def parsear_demora(payload: str) -> tuple[str, str, str] | None:
    """demora: PHONE TIEMPO EQUIPO → (phone, tiempo, equipo)"""
    phone, resto = _extraer_phone_y_resto(payload)
    if not phone or not resto:
        return None
    # Buscar patrón de tiempo: número + unidad
    time_match = re.match(
        r"^(\d+\s*(?:hora|horas|minuto|minutos|d[íi]a|d[íi]as|dias|semana|semanas)\b\s*)",
        resto,
        re.IGNORECASE,
    )
    if time_match:
        tiempo = time_match.group(1).strip()
        equipo = resto[time_match.end():].strip()
    else:
        partes = resto.split(None, 1)
        tiempo = partes[0]
        equipo = partes[1] if len(partes) > 1 else ""
    return phone, tiempo, equipo


def parsear_presupuesto(payload: str) -> tuple[str, str, str] | None:
    """presupuesto: PHONE EQUIPO PRECIO → (phone, equipo, precio)"""
    phone, resto = _extraer_phone_y_resto(payload)
    if not phone or not resto:
        return None
    partes = resto.split()
    if len(partes) < 2:
        return None
    precio_raw = partes[-1].lstrip("$").replace(",", "")
    equipo = " ".join(partes[:-1])
    return phone, equipo, precio_raw


def parsear_diagnostico(payload: str) -> tuple[str, str, str] | None:
    """diagnostico: PHONE EQUIPO DESCRIPCIÓN → (phone, equipo, descripcion)"""
    phone, resto = _extraer_phone_y_resto(payload)
    if not phone or not resto:
        return None
    # El equipo es el primer token del resto, la descripción es todo lo demás
    partes = resto.split(None, 1)
    equipo = partes[0]
    descripcion = partes[1].strip() if len(partes) > 1 else ""
    if not descripcion:
        return None
    return phone, equipo, descripcion


def parsear_phone_simple(payload: str) -> str | None:
    """password/llamar/clabe: PHONE → phone (solo el número)"""
    phone = re.sub(r"\D", "", payload.strip().split()[0]) if payload.strip() else ""
    return phone if phone else None


def parsear_pago(payload: str) -> tuple[str, str] | None:
    """pago: PHONE MONTO → (phone, monto)"""
    phone, monto = _extraer_phone_y_resto(payload)
    if not phone or not monto:
        return None
    monto = re.sub(r"[$,\s]", "", monto).strip()
    return (phone, monto) if monto else None


def parsear_nota(payload: str) -> dict | None:
    """
    nota: FOLIO_FISICO TELÉFONO EQUIPO [MODELO] FALLA TOTAL FORMA_PAGO [refaccion:COSTO]
    Ejemplo: 13054 5541576333 iPhone 13 pantalla 1200 tarjeta refaccion:500
      EQUIPO = primera palabra (ej: "iPhone")
      MODELO = palabras intermedias (ej: "13", "Pro Max") — puede estar vacío
      FALLA  = última palabra antes del total (una sola palabra: "pantalla")
    """
    # Extraer refaccion:X (puede estar en cualquier posición)
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

    # Forma de pago (último token)
    if not resto or resto[-1].lower() not in _FORMAS_PAGO:
        return None
    forma_pago = resto[-1].lower()
    resto = resto[:-1]

    # Total (segundo desde la derecha)
    if not resto or not re.match(r"^\d+(\.\d+)?$", resto[-1]):
        return None
    total = float(resto[-1])
    resto = resto[:-1]

    # EQUIPO [MODELO] FALLA
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


def _formatear_clabe(clabe_raw: str) -> str:
    """Formatea una CLABE en grupos de 4 dígitos separados por espacios."""
    digitos = re.sub(r"\D", "", clabe_raw)
    return " ".join(digitos[i:i+4] for i in range(0, len(digitos), 4))


_FORMAS_PAGO = ("efectivo", "tarjeta", "transferencia", "trans")
_MAPA_ESTATUS = {
    "recibido":   "Recibido",
    "proceso":    "En proceso",
    "en proceso": "En proceso",
    "listo":      "Listo",
    "entregado":  "Entregado",
}


def parsear_orden_crm(payload: str) -> dict | None:
    """
    orden: TELÉFONO EQUIPO... TOTAL PAGO [REFACCION]
    Ejemplo: 5541576331 PS5 2500 tarjeta 350
    El folio ya no se pasa — se auto-asigna en el CRM (consecutivo global).
    """
    partes = payload.strip().split()
    if len(partes) < 4:
        return None

    phone = re.sub(r"\D", "", partes[0])
    if not phone:
        return None

    resto = partes[1:]

    # Refacción opcional: número después de la forma de pago
    refaccion = 0.0
    if len(resto) >= 2 and re.match(r"^\d+(\.\d+)?$", resto[-1]) and resto[-2].lower() in _FORMAS_PAGO:
        refaccion = float(resto[-1])
        resto = resto[:-1]

    # Forma de pago
    if not resto or resto[-1].lower() not in _FORMAS_PAGO:
        return None
    forma_pago = resto[-1].lower()
    resto = resto[:-1]

    # Total
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


def parsear_estatus_crm(payload: str) -> tuple[str, str] | None:
    """
    estatus: FOLIO NUEVO_ESTATUS
    Ejemplo: 45 listo
    """
    partes = payload.strip().split(None, 1)
    if len(partes) < 2:
        return None
    folio      = partes[0]
    estatus_raw = partes[1].strip().lower()
    estatus    = _MAPA_ESTATUS.get(estatus_raw)
    if not estatus:
        return None
    return folio, estatus


# ──────────────────────────────────────────────
# Extracción del nombre del cliente del historial
# ──────────────────────────────────────────────

PALABRAS_COMUNES = {
    "Hola", "Buenos", "Buenas", "Gracias", "Claro", "Tecnology",
    "Support", "Entiendo", "Perfecto", "Excelente", "Muchas", "Disculpe",
    "Sofia", "Valentina", "Camila", "Diego", "Andres", "Rodrigo",
}

def extraer_nombre_cliente(historial: list[dict]) -> str:
    """Intenta extraer el nombre del cliente del historial de conversación."""
    for msg in historial:
        if msg["role"] == "assistant":
            # Busca patrones como "Hola, Juan" o "Juan,"
            matches = re.findall(r"\bHola,?\s+([A-ZÁÉÍÓÚÑ][a-záéíóúñ]{2,})", msg["content"])
            for m in matches:
                if m not in PALABRAS_COMUNES:
                    return m
    return ""


# ──────────────────────────────────────────────
# Procesador de comandos del grupo interno
# ──────────────────────────────────────────────

async def procesar_comando_grupo(
    msg,
    proveedor,
    guardar_mensaje_fn,
    obtener_historial_fn,
    marcar_presupuesto_fn,
) -> bool:
    """
    Procesa un mensaje del grupo 'Taller Interno TS' enviado por Ulises.
    Retorna True si era un comando válido, False si no.
    """
    remitente = getattr(msg, "remitente", "")
    nombre_grupo = getattr(msg, "nombre_grupo", "")
    chat_id_raw = getattr(msg, "chat_id_raw", msg.telefono)
    texto_cmd = msg.texto or ""

    logger.info(
        f"[GRUPO CMD] nombre_grupo='{nombre_grupo}' | remitente='{remitente}' "
        f"| GRUPO='{GRUPO_INTERNO}' | texto='{texto_cmd[:60]}'"
    )

    # Verificar grupo correcto
    if GRUPO_INTERNO.lower() not in nombre_grupo.lower():
        logger.warning(
            f"[GRUPO CMD] Rechazado — grupo '{nombre_grupo}' no contiene '{GRUPO_INTERNO}'"
        )
        return False

    # Verificar remitente: aceptar Ulises y Christian
    remitente_norm  = _normalizar_numero(remitente)
    autorizados     = {
        _normalizar_numero(ULISES_NUMERO),
        _normalizar_numero(CHRISTIAN_NUMERO),
    }
    if remitente_norm not in autorizados:
        logger.warning(
            f"[GRUPO CMD] Rechazado — remitente '{remitente}' (norm: '{remitente_norm}') "
            f"no está en autorizados {autorizados}"
        )
        return False

    logger.info(f"[GRUPO CMD] Remitente verificado como Ulises. Texto: '{texto_cmd[:80]}'")

    texto_lower = texto_cmd.strip().lower()

    # ── menu ──
    if texto_lower == "menu":
        await proveedor.enviar_mensaje(chat_id_raw, TEXTO_MENU)
        logger.info("[GRUPO CMD] Menú enviado al grupo")
        return True

    # ── reporte (resumen del día) ──
    if texto_lower == "reporte":
        await _cmd_reporte_dia(chat_id_raw, proveedor)
        return True

    # ── reporte seguimiento ──
    if texto_lower == "reporte seguimiento":
        await _cmd_reporte_seguimiento(chat_id_raw, proveedor)
        return True

    # ── pendientes seguimiento ──
    if texto_lower == "pendientes seguimiento":
        await _cmd_pendientes_seguimiento(chat_id_raw, proveedor)
        return True

    # Normalizar: eliminar caracteres invisibles que WhatsApp puede insertar
    texto_normalizado = (
        texto_cmd.strip()
        .replace('​', '')   # Zero-width space
        .replace(' ', ' ')  # Non-breaking space
    )
    resultado = parsear_comando(texto_normalizado)
    if not resultado:
        logger.info(f"[GRUPO CMD] Texto no es un comando válido: '{texto_cmd[:60]}'")
        return False

    cmd, payload = resultado
    logger.info(f"Comando de Ulises: {cmd} — {payload}")

    async def _responder_grupo(texto: str):
        await proveedor.enviar_mensaje(chat_id_raw, texto)

    async def _notificar_cliente(phone_raw: str, mensaje: str) -> bool:
        phone_fmt, advertencia = _formatear_numero_destino(phone_raw)
        if advertencia:
            await _responder_grupo(advertencia)
            return False
        logger.info(f"[CMD] Destino: '{phone_raw}' → '{phone_fmt}'")
        enviado = await proveedor.enviar_mensaje(phone_fmt, mensaje)
        if enviado:
            await guardar_mensaje_fn(phone_fmt, "assistant", mensaje)
        return enviado

    # ── listo ──
    if cmd == "listo":
        parsed = parsear_listo(payload)
        if not parsed:
            await _responder_grupo("⚠️ Formato: listo: NÚMERO EQUIPO")
            return True
        phone, equipo = parsed
        historial = await obtener_historial_fn(phone)
        nombre = extraer_nombre_cliente(historial) or "cliente"
        msg_cliente = (
            f"Hola {nombre} \U0001f60a "
            f"Te informamos que tu {equipo} ya está listo para recoger. "
            f"Puedes pasar en nuestro horario de atención: "
            f"Lunes a Viernes 10am–9pm, Sábados y Domingos 11am–8pm. "
            f"¡Gracias por tu preferencia!"
        )
        ok = await _notificar_cliente(phone, msg_cliente)
        if ok:
            from agent.memory import agregar_servicio_cliente, agregar_dispositivo_cliente
            await agregar_dispositivo_cliente(phone, equipo)
            await agregar_servicio_cliente(phone, f"Reparación completada: {equipo}")
        await _responder_grupo(f"{'✅' if ok else '❌'} Notificación enviada a {phone}")

    # ── demora ──
    elif cmd == "demora":
        parsed = parsear_demora(payload)
        if not parsed:
            await _responder_grupo("⚠️ Formato: demora: NÚMERO TIEMPO EQUIPO")
            return True
        phone, tiempo, equipo = parsed
        historial = await obtener_historial_fn(phone)
        nombre = extraer_nombre_cliente(historial) or "cliente"
        msg_cliente = (
            f"Hola {nombre} \U0001f60a "
            f"Queremos informarte que tu {equipo} requiere un poco más de tiempo "
            f"para garantizar un trabajo de calidad. "
            f"Estará listo en aproximadamente {tiempo}. "
            f"Disculpa el inconveniente, ¡gracias por tu paciencia!"
        )
        ok = await _notificar_cliente(phone, msg_cliente)
        await _responder_grupo(f"{'✅' if ok else '❌'} Notificación enviada a {phone}")

    # ── presupuesto ──
    elif cmd == "presupuesto":
        parsed = parsear_presupuesto(payload)
        if not parsed:
            await _responder_grupo("⚠️ Formato: presupuesto: NÚMERO EQUIPO PRECIO")
            return True
        phone, equipo, precio = parsed
        historial = await obtener_historial_fn(phone)
        nombre = extraer_nombre_cliente(historial) or "cliente"
        msg_cliente = (
            f"Hola {nombre} \U0001f60a "
            f"Nuestro técnico ya revisó tu {equipo} y el costo del servicio es de "
            f"*${precio} MXN*, precio final con IVA incluido. "
            f"Aceptamos todas las tarjetas sin comisión. "
            f"¿Autorizas que procedamos con la reparación?"
        )
        ok = await _notificar_cliente(phone, msg_cliente)
        if ok:
            await marcar_presupuesto_fn(phone)
        await _responder_grupo(
            f"{'✅' if ok else '❌'} Presupuesto enviado a {phone} (${precio} por {equipo})"
        )

    # ── diagnostico ──
    elif cmd == "diagnostico":
        parsed = parsear_diagnostico(payload)
        if not parsed:
            await _responder_grupo("⚠️ Formato: diagnostico: NÚMERO EQUIPO DESCRIPCIÓN")
            return True
        phone, equipo, descripcion = parsed
        historial = await obtener_historial_fn(phone)
        nombre = extraer_nombre_cliente(historial) or "cliente"
        msg_cliente = (
            f"Hola {nombre} \U0001f60a "
            f"Nuestro técnico revisó tu {equipo} y encontró lo siguiente: "
            f"{descripcion}. "
            f"En breve te compartimos el presupuesto de reparación. "
            f"¿Tienes alguna duda?"
        )
        ok = await _notificar_cliente(phone, msg_cliente)
        await _responder_grupo(f"{'✅' if ok else '❌'} Diagnóstico enviado a {phone}")

    # ── password ──
    elif cmd == "password":
        phone = parsear_phone_simple(payload)
        if not phone:
            await _responder_grupo("⚠️ Formato: password: NÚMERO")
            return True
        historial = await obtener_historial_fn(phone)
        nombre = extraer_nombre_cliente(historial) or "cliente"
        msg_cliente = (
            f"Hola {nombre} \U0001f60a "
            f"Para continuar con la revisión de tu equipo, nuestro técnico necesita "
            f"acceder al dispositivo. ¿Podrías compartir tu contraseña o patrón de desbloqueo? "
            f"Tu información es completamente confidencial y será eliminada "
            f"una vez concluido el servicio."
        )
        ok = await _notificar_cliente(phone, msg_cliente)
        await _responder_grupo(f"{'✅' if ok else '❌'} Solicitud de contraseña enviada a {phone}")

    # ── llamar ──
    elif cmd == "llamar":
        phone = parsear_phone_simple(payload)
        if not phone:
            await _responder_grupo("⚠️ Formato: llamar: NÚMERO")
            return True
        historial = await obtener_historial_fn(phone)
        nombre = extraer_nombre_cliente(historial) or "cliente"
        msg_cliente = (
            f"Hola {nombre} \U0001f60a "
            f"Para atender mejor tu caso, te pedimos que nos contactes al teléfono de sucursal: "
            f"*55 9730 7793* (solo llamadas). "
            f"Nuestro equipo técnico te atenderá directamente."
        )
        ok = await _notificar_cliente(phone, msg_cliente)
        await _responder_grupo(f"{'✅' if ok else '❌'} Solicitud de llamada enviada a {phone}")

    # ── pausa (manual: Christian toma el caso) ──
    elif cmd == "pausa":
        phone = parsear_phone_simple(payload)
        if not phone:
            await _responder_grupo("⚠️ Formato: pausa: NÚMERO\nEj: pausa: 5215614693930")
            return True
        phone_fmt, advertencia = _formatear_numero_destino(phone)
        if advertencia:
            await _responder_grupo(advertencia)
            return True
        from agent.memory import pausar_conversacion
        await pausar_conversacion(phone_fmt, horas=2)
        await _responder_grupo(
            f"✅ Pausa activada: {phone_fmt} (120 min)\n"
            f"El agente no responderá mientras Christian interviene."
        )
        logger.info(f"[PAUSA] Cliente {phone_fmt} pausado por Christian")

    # ── reanudar ──
    elif cmd == "reanudar":
        phone = parsear_phone_simple(payload)
        if not phone:
            await _responder_grupo("⚠️ Formato: reanudar: NÚMERO\nEj: reanudar: 5215614693930")
            return True
        phone_fmt, advertencia = _formatear_numero_destino(phone)
        if advertencia:
            await _responder_grupo(advertencia)
            return True
        from agent.memory import reanudar_conversacion
        await reanudar_conversacion(phone_fmt)
        await _responder_grupo(
            f"✅ Conversación reanudada: {phone_fmt}\n"
            f"Agente puede responder de nuevo."
        )
        logger.info(f"[REANUDAR] Cliente {phone_fmt} reanudado")

    # ── cita ──
    elif cmd == "cita":
        phone = parsear_phone_simple(payload)
        if not phone:
            await _responder_grupo("⚠️ Formato: cita: NÚMERO")
            return True
        historial = await obtener_historial_fn(phone)
        nombre = extraer_nombre_cliente(historial) or "cliente"
        msg_cliente = (
            f"Hola {nombre} \U0001f60a "
            f"Queremos informarte que puedes pasar a nuestro módulo sin necesidad de cita previa. "
            f"Te atendemos en nuestro horario habitual: "
            f"Lunes a Viernes 10:00am–9:00pm · Sábados y Domingos 11:00am–8:00pm. "
            f"¡Te esperamos cuando gustes!"
        )
        ok = await _notificar_cliente(phone, msg_cliente)
        await _responder_grupo(f"{'✅' if ok else '❌'} Invitación sin cita enviada a {phone}")

    # ── clabe ──
    elif cmd == "clabe":
        phone = parsear_phone_simple(payload)
        if not phone:
            await _responder_grupo("⚠️ Formato: clabe: NÚMERO")
            return True
        phone_fmt, advertencia = _formatear_numero_destino(phone)
        if advertencia:
            await _responder_grupo(advertencia)
            return True
        clabe_numero = os.getenv("CLABE_PAGO", "16758000005753814")
        msg1 = (
            "Para realizar tu pago por transferencia:\n"
            "🏦 Banco: Hey Banco\n"
            "👤 Razón Social: Gold Bunny TS"
        )
        msg2 = _formatear_clabe(clabe_numero)
        ok1 = await proveedor.enviar_mensaje(phone_fmt, msg1)
        if ok1:
            await guardar_mensaje_fn(phone_fmt, "assistant", msg1)
        ok2 = await proveedor.enviar_mensaje(phone_fmt, msg2)
        if ok2:
            await guardar_mensaje_fn(phone_fmt, "assistant", msg2)
        ok = ok1 and ok2
        await _responder_grupo(f"{'✅' if ok else '❌'} CLABE enviada a {phone_fmt}")

    # ── pago ──
    elif cmd == "pago":
        parsed = parsear_pago(payload)
        if not parsed:
            await _responder_grupo("⚠️ Formato: pago: NÚMERO MONTO")
            return True
        phone, monto = parsed
        phone_fmt, advertencia = _formatear_numero_destino(phone)
        if advertencia:
            await _responder_grupo(advertencia)
            return True
        historial = await obtener_historial_fn(phone_fmt)
        nombre = extraer_nombre_cliente(historial) or "cliente"
        msg_cliente = (
            f"Hola {nombre} \U0001f60a "
            f"Para completar tu pago de *${monto} MXN* puedes realizarlo "
            f"por transferencia a nuestra CLABE o en efectivo en el módulo. "
            f"¿Cuál prefieres?"
        )
        ok = await _notificar_cliente(phone, msg_cliente)
        await _responder_grupo(f"{'✅' if ok else '❌'} Instrucciones de pago enviadas a {phone_fmt} (${monto})")

    # ── nota (CRM — folio físico + auto-folio CRM) ──
    elif cmd == "nota":
        parsed = parsear_nota(payload)
        if not parsed:
            await _responder_grupo(
                "⚠️ Formato: nota: FOLIO_FÍSICO NÚMERO EQUIPO [MODELO] FALLA TOTAL PAGO [refaccion:COSTO]\n"
                "Ej: nota: 13054 5541576333 iPhone 13 pantalla 1200 tarjeta refaccion:500"
            )
            return True

        phone_fmt, advertencia = _formatear_numero_destino(parsed["phone"])
        if advertencia:
            await _responder_grupo(advertencia)
            return True

        historial = await obtener_historial_fn(phone_fmt)
        nombre = extraer_nombre_cliente(historial) or phone_fmt

        try:
            from agent.crm import registrar_orden
            resultado = await registrar_orden(
                telefono  = phone_fmt,
                cliente   = nombre,
                equipo    = parsed["equipo"],
                modelo    = parsed["modelo"],
                falla     = parsed["falla"],
                total     = parsed["total"],
                forma_pago= parsed["forma_pago"],
                refaccion = parsed["refaccion"],
            )
            try:
                from agent.leads import marcar_como_convertido
                await marcar_como_convertido(phone_fmt)
            except Exception as ex:
                logger.warning(f"[CRM] No se pudo marcar convertido: {ex}")

            com_txt   = f"${resultado['comision']:.2f}" if resultado["comision"] else "$0.00"
            drive_txt = f"\n📁 Drive: {resultado['link_drive']}" if resultado["link_drive"] else ""
            equipo_txt = f"{parsed['equipo']} {parsed['modelo']}".strip()
            await _responder_grupo(
                f"✅ Nota #{parsed['folio_fisico']} registrada\n"
                f"👤 Cliente: {nombre}\n"
                f"📞 Tel: {parsed['phone']}\n"
                f"🔧 Equipo: {equipo_txt} | Falla: {parsed['falla']}\n"
                f"💰 Total: ${parsed['total']:,.0f} | Pago: {parsed['forma_pago'].title()}\n"
                f"💳 Comisión: {com_txt} | Refacción: ${parsed['refaccion']:,.2f}\n"
                f"📊 Ganancia Real: ${resultado['ganancia']:,.2f}\n"
                f"📋 Folio CRM: {resultado['folio_crm']} | {resultado['bloque']}"
                f"{drive_txt}"
            )
        except Exception as e:
            logger.error(f"[CRM] Error registrando nota: {e}")
            await _responder_grupo(f"❌ Error registrando nota: {e}")

    # ── orden (CRM) ──
    elif cmd == "orden":
        parsed = parsear_orden_crm(payload)
        if not parsed:
            await _responder_grupo(
                "⚠️ Formato: orden: NÚMERO EQUIPO TOTAL PAGO [REFACCIÓN]\n"
                "Ej: orden: 5541576331 PS5 2500 tarjeta 350\n"
                "(El folio se asigna automáticamente)"
            )
            return True

        phone_fmt, advertencia = _formatear_numero_destino(parsed["phone"])
        if advertencia:
            await _responder_grupo(advertencia)
            return True

        historial = await obtener_historial_fn(phone_fmt)
        nombre = extraer_nombre_cliente(historial) or phone_fmt

        try:
            from agent.crm import registrar_orden
            resultado = await registrar_orden(
                telefono  = phone_fmt,
                cliente   = nombre,
                equipo    = parsed["equipo"],
                modelo    = "",
                falla     = "",
                total     = parsed["total"],
                forma_pago= parsed["forma_pago"],
                refaccion = parsed["refaccion"],
            )
            com_txt   = f"  💳 Comisión: ${resultado['comision']}" if resultado["comision"] else ""
            drive_txt = f"\n  📁 Drive: {resultado['link_drive']}" if resultado["link_drive"] else ""
            await _responder_grupo(
                f"✅ Orden #{resultado['folio_crm']} registrada | {resultado['bloque']}\n"
                f"  👤 {nombre} ({phone_fmt})\n"
                f"  🔧 {resultado['equipo']}\n"
                f"  💰 ${resultado['total']} ({parsed['forma_pago']}){com_txt}\n"
                f"  📊 Ganancia: ${resultado['ganancia']}"
                f"{drive_txt}"
            )
        except Exception as e:
            logger.error(f"[CRM] Error registrando orden: {e}")
            await _responder_grupo(f"❌ Error registrando orden: {e}")

    # ── estatus (CRM) ──
    elif cmd == "estatus":
        parsed_e = parsear_estatus_crm(payload)
        if not parsed_e:
            await _responder_grupo(
                "⚠️ Formato: estatus: FOLIO ESTATUS\n"
                "Estatus válidos: recibido | proceso | listo | entregado\n"
                "Ej: estatus: 45 listo"
            )
            return True
        folio_e, nuevo_e = parsed_e
        try:
            from agent.crm import actualizar_estatus_orden
            ok = await actualizar_estatus_orden(folio_e, nuevo_e)
            if ok:
                await _responder_grupo(f"✅ Folio #{folio_e.zfill(4)} → *{nuevo_e}*")
            else:
                await _responder_grupo(f"❌ Folio #{folio_e.zfill(4)} no encontrado en ORDENES")
        except Exception as e:
            logger.error(f"[CRM] Error actualizando estatus: {e}")
            await _responder_grupo(f"❌ Error: {e}")

    # ── marcar seguimiento ──
    elif cmd == "marcar seguimiento":
        identificador = payload.strip()
        if not identificador:
            await _responder_grupo("⚠️ Formato: marcar seguimiento: NÚMERO  — Ej: marcar seguimiento: 5541576331")
            return True
        try:
            from agent.leads import marcar_seguimiento_manual
            tel = await marcar_seguimiento_manual(identificador)
            if tel:
                await _responder_grupo(f"✅ Seguimiento marcado como atendido: {tel}")
            else:
                await _responder_grupo(f"❌ No se encontró cliente con '{identificador}'")
        except Exception as e:
            await _responder_grupo(f"❌ Error: {e}")

    # ── consultar (CRM) ──
    elif cmd == "consultar":
        folio_c = payload.strip().split()[0] if payload.strip() else ""
        if not folio_c:
            await _responder_grupo("⚠️ Formato: consultar: FOLIO  — Ej: consultar: 45")
            return True
        try:
            from agent.crm import consultar_orden
            orden = await consultar_orden(folio_c)
            if not orden:
                await _responder_grupo(f"❌ Folio #{folio_c.zfill(4)} no encontrado")
            else:
                drive_txt = f"\n📁 {orden['link_drive']}" if orden["link_drive"] else ""
                factura_txt = f"\n🧾 Factura: {orden['factura']}" if orden["factura"] else ""
                await _responder_grupo(
                    f"📋 *Orden #{orden['folio']}*\n"
                    f"👤 {orden['cliente']} · {orden['telefono']}\n"
                    f"🔧 {orden['equipo']} {orden['modelo']}\n"
                    f"🗒️ {orden['falla'] or 'Sin descripción'}\n"
                    f"📅 Ingreso: {orden['fecha']}\n"
                    f"📊 Estatus: *{orden['estatus']}*\n"
                    f"💰 ${orden['total']} ({orden['forma_pago']})\n"
                    f"   Comisión: ${orden['comision']} | Refacción: ${orden['refaccion']}\n"
                    f"   Ganancia: ${orden['ganancia']}"
                    f"{drive_txt}{factura_txt}"
                )
        except Exception as e:
            logger.error(f"[CRM] Error consultando orden: {e}")
            await _responder_grupo(f"❌ Error: {e}")

    return True


# ──────────────────────────────────────────────
# Reportes de seguimiento (comandos internos)
# ──────────────────────────────────────────────

def _icono_prioridad(p: str) -> str:
    return {"urgente": "🔴", "medio": "🟡", "bajo": "🟢"}.get(p, "⚪")


def _fmt_fecha(dt) -> str:
    if not dt:
        return "—"
    try:
        from zoneinfo import ZoneInfo
        from datetime import timezone
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        cdmx = dt.astimezone(ZoneInfo("America/Mexico_City"))
        return cdmx.strftime("%d/%m %H:%M")
    except Exception:
        return str(dt)[:10]


async def _cmd_reporte_seguimiento(chat_id: str, proveedor):
    """Genera reporte completo de todos los clientes con su estado de seguimiento."""
    try:
        from agent.leads import obtener_todos_los_leads_detalle
        from agent.crm import obtener_mapa_ordenes_por_telefono
        import re as _re

        leads = await obtener_todos_los_leads_detalle()
        if not leads:
            await proveedor.enviar_mensaje(chat_id, "No hay clientes registrados aún.")
            return

        # Cargar órdenes de Sheets en un solo request
        try:
            mapa_ordenes = await obtener_mapa_ordenes_por_telefono()
        except Exception:
            mapa_ordenes = {}

        bloques = {"urgente": [], "medio": [], "bajo": []}
        for lead in leads:
            tel_norm = _re.sub(r"\D", "", lead.telefono)
            ordenes  = mapa_ordenes.get(tel_norm, [])
            tiene_orden = bool(ordenes)
            orden_txt = f"Orden #{ordenes[0]['folio']} ({ordenes[0]['estatus']})" if tiene_orden else "Sin orden"
            seg_txt = "✅ Contactado" if lead.seguimiento_realizado else "⏳ Pendiente"
            ico = _icono_prioridad(lead.prioridad)
            linea = (
                f"{ico} {lead.telefono} · {lead.estado} · {orden_txt} · "
                f"últ: {_fmt_fecha(lead.ultimo_mensaje)} · {seg_txt}"
            )
            bloques.setdefault(lead.prioridad, []).append(linea)

        total = len(leads)
        pendientes = sum(1 for l in leads if not l.seguimiento_realizado and l.estado not in ("perdido", "convertido"))

        partes = [f"📊 *Reporte Seguimiento* — {total} clientes · {pendientes} pendientes\n"]
        for prioridad, items in [("urgente", bloques["urgente"]), ("medio", bloques["medio"]), ("bajo", bloques["bajo"])]:
            if items:
                partes.append(f"\n{_icono_prioridad(prioridad)} *{prioridad.upper()}* ({len(items)})")
                partes.extend(items[:15])  # max 15 por bloque para no saturar
                if len(items) > 15:
                    partes.append(f"  ... y {len(items)-15} más")

        msg = "\n".join(partes)
        # WhatsApp tiene límite de ~4096 chars; truncar si es necesario
        if len(msg) > 3800:
            msg = msg[:3750] + "\n\n_(lista truncada — hay más clientes)_"

        await proveedor.enviar_mensaje(chat_id, msg)
        logger.info(f"[GRUPO CMD] Reporte seguimiento enviado — {total} clientes")

    except Exception as e:
        logger.error(f"[GRUPO CMD] Error en reporte seguimiento: {e}")
        await proveedor.enviar_mensaje(chat_id, f"❌ Error generando reporte: {e}")


async def _cmd_pendientes_seguimiento(chat_id: str, proveedor):
    """Lista solo los clientes que aún necesitan seguimiento."""
    try:
        from agent.leads import obtener_pendientes_seguimiento
        from agent.crm import obtener_mapa_ordenes_por_telefono
        import re as _re

        pendientes = await obtener_pendientes_seguimiento()
        if not pendientes:
            await proveedor.enviar_mensaje(chat_id, "✅ No hay clientes pendientes de seguimiento.")
            return

        try:
            mapa_ordenes = await obtener_mapa_ordenes_por_telefono()
        except Exception:
            mapa_ordenes = {}

        lineas = [f"⏳ *Pendientes de seguimiento* — {len(pendientes)} clientes\n"]
        for lead in pendientes:
            tel_norm = _re.sub(r"\D", "", lead.telefono)
            ordenes  = mapa_ordenes.get(tel_norm, [])
            orden_txt = f"#{ordenes[0]['folio']}" if ordenes else "sin orden"
            ico = _icono_prioridad(lead.prioridad)
            seg_n = lead.seguimientos_enviados
            lineas.append(
                f"{ico} {lead.telefono} · {orden_txt} · "
                f"seg {seg_n}/4 · últ: {_fmt_fecha(lead.ultimo_mensaje)}"
            )

        msg = "\n".join(lineas[:50])  # máx 50 resultados
        if len(pendientes) > 50:
            msg += f"\n... y {len(pendientes)-50} más"

        await proveedor.enviar_mensaje(chat_id, msg)

    except Exception as e:
        logger.error(f"[GRUPO CMD] Error en pendientes seguimiento: {e}")
        await proveedor.enviar_mensaje(chat_id, f"❌ Error: {e}")


async def _cmd_reporte_dia(chat_id: str, proveedor):
    """Resumen del día: leads por estado + ingresos CRM + pendientes de recoger."""
    from zoneinfo import ZoneInfo as _ZI
    try:
        from agent.leads import obtener_resumen_leads
        from agent.crm import obtener_ordenes_del_dia, obtener_ordenes_por_estatus

        resumen   = await obtener_resumen_leads()
        hoy_ord   = await obtener_ordenes_del_dia()
        pendientes = await obtener_ordenes_por_estatus("Listo")

        ingresos = sum(float(o.get("total", 0) or 0) for o in hoy_ord)
        ganancia = sum(float(o.get("ganancia", 0) or 0) for o in hoy_ord)

        hoy_fmt = datetime.now(_ZI("America/Mexico_City")).strftime("%d/%m/%Y")

        msg = (
            f"📊 *Resumen del día — {hoy_fmt}*\n\n"
            f"*── Leads ──*\n"
            f"✅ Convertidos: {resumen.get('convertido', 0)}\n"
            f"📞 En seguimiento: {resumen.get('en_seguimiento', 0)}\n"
            f"🟢 Activos: {resumen.get('activo', 0)}\n"
            f"❌ Perdidos: {resumen.get('perdido', 0)}\n"
            f"📊 Total clientes: {resumen.get('total', 0)}\n\n"
            f"*── CRM del día ──*\n"
            f"📋 Órdenes registradas hoy: {len(hoy_ord)}\n"
            f"💰 Ingresos: ${ingresos:,.2f} MXN\n"
            f"💵 Ganancia estimada: ${ganancia:,.2f} MXN\n\n"
            f"*── Pendientes de recoger ──*\n"
            f"🔔 Listos para recoger: {len(pendientes)}"
        )
        if pendientes:
            lineas = "\n".join(
                f"  • #{o['folio']} {o['equipo']} — {o['cliente']}"
                for o in pendientes[:10]
            )
            msg += f"\n{lineas}"
            if len(pendientes) > 10:
                msg += f"\n  ... y {len(pendientes)-10} más"

        await proveedor.enviar_mensaje(chat_id, msg)
        logger.info("[GRUPO CMD] Reporte del día enviado")

    except Exception as e:
        logger.error(f"[GRUPO CMD] Error en reporte del día: {e}")
        await proveedor.enviar_mensaje(chat_id, f"❌ Error generando reporte: {e}")


# ──────────────────────────────────────────────
# Detección de alertas para Christian
# ──────────────────────────────────────────────

async def detectar_y_notificar_christian(
    mensaje: str,
    historial: list[dict],
    telefono: str,
    respuesta_agente: str,
    proveedor,
) -> None:
    """
    Analiza el mensaje del cliente y la respuesta del agente.
    Envía una alerta a Christian si se detectan condiciones relevantes.
    """
    msg_lower = mensaje.lower()
    nombre = extraer_nombre_cliente(historial) or telefono

    # Detectar equipo mencionado (simple heurística)
    equipo = _detectar_equipo(mensaje + " " + " ".join(
        m["content"] for m in historial[-4:] if m["role"] == "user"
    ))

    # ── Alerta: palabras de urgencia/queja ──
    alerta_kw = next((kw for kw in KEYWORDS_ALERTA if kw in msg_lower), None)
    if alerta_kw:
        await _enviar_alerta_christian(
            proveedor,
            tipo=f"URGENCIA / QUEJA — \"{alerta_kw}\"",
            nombre=nombre,
            equipo=equipo,
            resumen=mensaje[:120],
        )
        return  # Solo una alerta por mensaje

    # ── Alerta: pide presupuesto de refacción ──
    kw_presup = next((kw for kw in KEYWORDS_PRESUPUESTO_REFACCION if kw in msg_lower), None)
    if kw_presup:
        await _enviar_alerta_christian(
            proveedor,
            tipo="SOLICITUD DE PRESUPUESTO DE REFACCIÓN",
            nombre=nombre,
            equipo=equipo,
            resumen=mensaje[:120],
        )
        return

    # ── Alerta: cliente agenda cita ──
    kw_cita = next((kw for kw in KEYWORDS_CITA if kw in msg_lower), None)
    if kw_cita:
        await _enviar_alerta_christian(
            proveedor,
            tipo="CITA AGENDADA",
            nombre=nombre,
            equipo=equipo,
            resumen=mensaje[:120],
        )


def _detectar_equipo(texto: str) -> str:
    """Heurística simple para detectar el dispositivo mencionado."""
    texto_lower = texto.lower()
    dispositivos = [
        ("PS5", ["ps5", "playstation 5"]),
        ("PS4", ["ps4", "playstation 4"]),
        ("PS3", ["ps3", "playstation 3"]),
        ("Xbox Series S", ["xbox series s"]),
        ("Xbox One", ["xbox one"]),
        ("Nintendo Switch", ["switch", "nintendo"]),
        ("iPhone", ["iphone"]),
        ("Samsung", ["samsung"]),
        ("laptop", ["laptop", "lapto"]),
        ("PC", ["computadora", "pc gamer", "desktop"]),
        ("celular", ["celular", "teléfono", "telefono"]),
    ]
    for nombre, keywords in dispositivos:
        if any(kw in texto_lower for kw in keywords):
            return nombre
    return "No especificado"


async def _enviar_alerta_christian(
    proveedor,
    tipo: str,
    nombre: str,
    equipo: str,
    resumen: str,
) -> None:
    """Envía la notificación formateada al número de Christian."""
    mensaje = (
        f"\U0001f514 {tipo}\n"
        f"Cliente: {nombre}\n"
        f"Equipo: {equipo}\n"
        f"Mensaje: {resumen}"
    )
    try:
        await proveedor.enviar_mensaje(CHRISTIAN_NUMERO, mensaje)
        logger.info(f"Alerta enviada a Christian: {tipo} — {nombre}")
    except Exception as e:
        logger.error(f"Error enviando alerta a Christian: {e}")


async def notificar_cita_agendada(
    proveedor,
    nombre: str,
    telefono: str,
    dispositivo: str,
    problema: str,
    fecha_texto: str,
    hora_texto: str,
    asesor: str = "",
    evento_id: str = "",
) -> None:
    """Notifica a Christian, Ulises y al grupo interno cuando se agenda una cita."""
    linea_asesor = f"👨‍💼 Asesor: {asesor}\n" if asesor else ""
    mensaje_individual = (
        f"📅 *NUEVA CITA AGENDADA*\n"
        f"👤 Cliente: {nombre}\n"
        f"📱 Dispositivo: {dispositivo}\n"
        f"🔧 Problema: {problema}\n"
        f"📆 Fecha: {fecha_texto.capitalize()}\n"
        f"🕐 Hora: {hora_texto}\n"
        f"📞 Teléfono: {telefono}\n"
        f"{linea_asesor}"
    )
    for numero in [CHRISTIAN_NUMERO, ULISES_NUMERO]:
        try:
            await proveedor.enviar_mensaje(numero, mensaje_individual)
            logger.info(f"[CALENDAR] Notificación cita → {numero}")
        except Exception as e:
            logger.error(f"[CALENDAR] Error notificando a {numero}: {e}")

    # Email + grupo via appointment_notifications (maneja dedup, email SMTP y búsqueda de grupo)
    try:
        from agent.appointment_notifications import notificar_nueva_cita
        await notificar_nueva_cita(
            nombre=nombre,
            telefono=telefono,
            dispositivo=dispositivo,
            problema=problema,
            fecha_texto=fecha_texto,
            hora_texto=hora_texto,
            asesor=asesor or "Agente",
            evento_id=evento_id,
        )
    except Exception as e:
        logger.error(f"[CALENDAR] Error en notificación email/grupo: {e}")


async def notificar_christian_vision(
    proveedor,
    telefono: str,
    historial: list[dict],
    analisis: dict,
    tipo_media: str,
) -> None:
    """Notifica a Christian después de un análisis visual automático."""
    nombre = extraer_nombre_cliente(historial) or telefono
    dispositivo = analisis.get("dispositivo", "No identificado")
    dano = analisis.get("dano_visible", "No determinado")
    precio = analisis.get("rango_precio", "Por cotizar")
    puede = analisis.get("puede_diagnosticar", False)

    if not puede:
        resumen = f"No se pudo analizar el {tipo_media} (motivo: {analisis.get('motivo', 'desconocido')})"
    else:
        resumen = (
            f"Dispositivo: {dispositivo}\n"
            f"Daño detectado: {dano}\n"
            f"Precio estimado dado: {precio}"
        )

    icono = "\U0001f4f8" if tipo_media == "image" else "\U0001f3a5"
    mensaje = (
        f"{icono} ANÁLISIS VISUAL AUTOMÁTICO\n"
        f"Cliente: {nombre}\n"
        f"{resumen}"
    )
    try:
        await proveedor.enviar_mensaje(CHRISTIAN_NUMERO, mensaje)
        logger.info(f"Alerta visión enviada a Christian — {telefono}")
    except Exception as e:
        logger.error(f"Error enviando alerta visión a Christian: {e}")
