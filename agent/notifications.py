# agent/notifications.py — Comandos del grupo interno y alertas a Christian
# Generado por AgentKit

import os
import re
import logging
from datetime import datetime

logger = logging.getLogger("agentkit")

CHRISTIAN_NUMERO = os.getenv("CHRISTIAN_NUMERO", "5541576331")
ULISES_NUMERO    = os.getenv("ULISES_NUMERO",    "5633500566")
GRUPO_INTERNO    = os.getenv("GRUPO_INTERNO_NOMBRE", "Taller Interno TS")

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

COMANDOS_VALIDOS = ("listo", "demora", "presupuesto", "diagnostico", "password", "llamar", "cita", "reanudar")

TEXTO_MENU = (
    "🛠️ *Comandos — Taller Interno TS*\n\n"
    "*listo:* [número] [equipo] → Cliente listo para recoger\n"
    "*demora:* [número] [tiempo] [equipo] → Necesita más tiempo\n"
    "*diagnostico:* [número] [equipo] [descripción] → Informa diagnóstico\n"
    "*presupuesto:* [número] [equipo] [precio] → Envía presupuesto\n"
    "*password:* [número] → Solicita contraseña al cliente\n"
    "*llamar:* [número] → Pide al cliente que llame\n"
    "*cita:* [número] → Indica que puede pasar sin cita\n"
    "*reanudar:* [número] → Reanuda conversación pausada\n\n"
    "Ejemplo: listo: 5541576331 PS5\n\n"
    "━━━━━━━━━━━━━━━━━━━━━━━━\n"
    "📍 *Ubicación del taller*\n"
    "Plazuela de la Fama 1, Col. La Fama\n"
    "Tlalpan, CDMX, C.P. 14410\n"
    "📞 55 9730 7793\n"
    "🗺️ https://maps.app.goo.gl/XdCSu743LpyY6aAt7"
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
    """password/llamar: PHONE → phone (solo el número)"""
    phone = re.sub(r"\D", "", payload.strip().split()[0]) if payload.strip() else ""
    return phone if phone else None


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

    # ── menu (sin payload) ──
    if texto_cmd.strip().lower() == "menu":
        await proveedor.enviar_mensaje(chat_id_raw, TEXTO_MENU)
        logger.info("[GRUPO CMD] Menú enviado al grupo")
        return True

    resultado = parsear_comando(texto_cmd)
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

    # ── reanudar ──
    elif cmd == "reanudar":
        phone = parsear_phone_simple(payload)
        if not phone:
            await _responder_grupo("⚠️ Formato: reanudar: NÚMERO")
            return True
        from agent.memory import reanudar_conversacion
        phone_fmt, advertencia = _formatear_numero_destino(phone)
        if advertencia:
            await _responder_grupo(advertencia)
            return True
        await reanudar_conversacion(phone_fmt)
        await _responder_grupo(f"✅ Agente reanudado para {phone_fmt}")
        logger.info(f"[PAUSA] Reanudado manualmente por operador: {phone_fmt}")

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
            f"Lunes a Viernes 10:30am–7:00pm · Sábados y Domingos 11:30am–6:30pm. "
            f"¡Te esperamos cuando gustes!"
        )
        ok = await _notificar_cliente(phone, msg_cliente)
        await _responder_grupo(f"{'✅' if ok else '❌'} Invitación sin cita enviada a {phone}")

    return True


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
) -> None:
    """Notifica a Christian y Ulises cuando se agenda una nueva cita."""
    mensaje = (
        f"📅 *NUEVA CITA AGENDADA*\n"
        f"👤 Cliente: {nombre}\n"
        f"📱 Dispositivo: {dispositivo}\n"
        f"🔧 Problema: {problema}\n"
        f"📆 Fecha: {fecha_texto.capitalize()}\n"
        f"🕐 Hora: {hora_texto}\n"
        f"📞 Teléfono: {telefono}"
    )
    for numero in [CHRISTIAN_NUMERO, ULISES_NUMERO]:
        try:
            await proveedor.enviar_mensaje(numero, mensaje)
            logger.info(f"[CALENDAR] Notificación cita → {numero}")
        except Exception as e:
            logger.error(f"[CALENDAR] Error notificando a {numero}: {e}")


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
