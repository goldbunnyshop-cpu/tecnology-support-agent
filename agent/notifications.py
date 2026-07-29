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


# (Parsers, comandos y reportes movidos a agent/commands.py)

from agent.commands import extraer_nombre_cliente


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
    imagen_bytes: bytes | None = None,
    imagen_mime: str = "image/jpeg",
) -> None:
    """Notifica a Christian después de un análisis visual.

    Si se pasan imagen_bytes, reenvía la imagen original con el análisis como caption.
    Si no, envía solo el texto (fallback para videos u otros casos).
    """
    nombre = extraer_nombre_cliente(historial) or telefono
    puede  = analisis.get("puede_diagnosticar", True)

    if not puede:
        resumen = f"⚠️ No se pudo analizar ({analisis.get('motivo', 'desconocido')})"
    else:
        marca   = analisis.get("marca", "No identificada")
        modelo  = analisis.get("modelo_probable", "No determinado")
        dano    = analisis.get("dano_visible", "No determinado")
        puerto  = analisis.get("puerto_afectado", "")
        nota    = analisis.get("nota_tecnica", "")

        lineas = [
            f"📱 {marca} — {modelo}",
            f"🔧 Daño: {dano}",
        ]
        if puerto and puerto not in ("ninguno", "No aplica", ""):
            lineas.append(f"🔌 Puerto: {puerto}")
        if nota:
            lineas.append(f"📋 Nota técnica: {nota}")

        resumen = "\n".join(lineas)

    icono  = "📸" if tipo_media == "image" else "🎥"
    caption = (
        f"{icono} VISIÓN — Cliente: {nombre} ({telefono})\n"
        f"{resumen}"
    )

    try:
        # Intento 1: reenviar imagen con caption (A)
        if imagen_bytes and hasattr(proveedor, "enviar_imagen_bytes"):
            ok = await proveedor.enviar_imagen_bytes(
                CHRISTIAN_NUMERO, imagen_bytes, imagen_mime, caption
            )
            if ok:
                logger.info(f"Alerta visión (imagen) enviada a Christian — {telefono}")
                return

        # Fallback: solo texto si no hay imagen o falló el envío
        await proveedor.enviar_mensaje(CHRISTIAN_NUMERO, caption)
        logger.info(f"Alerta visión (texto) enviada a Christian — {telefono}")
    except Exception as e:
        logger.error(f"Error enviando alerta visión a Christian: {e}")
