# agent/appointment_notifications.py — Notificaciones de citas para Ulises (técnico)
# Email SMTP + mensaje al grupo "Taller Interno TS"

import asyncio
import logging
import os
import smtplib
from datetime import datetime, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from zoneinfo import ZoneInfo

import httpx

logger = logging.getLogger("agentkit")

_ZONA_MX     = ZoneInfo("America/Mexico_City")
EMAIL_ULISES  = os.getenv("EMAIL_ULISES", "10telefonos10@hotmail.com")
SMTP_SERVER   = os.getenv("SMTP_SERVER",  "smtp-mail.outlook.com")
SMTP_PORT     = int(os.getenv("SMTP_PORT", "587"))
GRUPO_NOMBRE  = os.getenv("GRUPO_INTERNO_NOMBRE", "Taller Interno TS")
_UBICACION    = "Plazuela de la Fama 1, Col. La Fama, Tlalpan"

_DIAS_ES  = {0:"lunes",1:"martes",2:"miércoles",3:"jueves",4:"viernes",5:"sábado",6:"domingo"}
_MESES_ES = {1:"enero",2:"febrero",3:"marzo",4:"abril",5:"mayo",6:"junio",
             7:"julio",8:"agosto",9:"septiembre",10:"octubre",11:"noviembre",12:"diciembre"}


# ─── Email SMTP ──────────────────────────────────────────────────────────────

def _enviar_email_sync(asunto: str, body: str) -> bool:
    smtp_user = os.getenv("SMTP_USER", "")
    smtp_pass = os.getenv("SMTP_PASSWORD", "")
    if not smtp_user or not smtp_pass:
        logger.warning("[CITAS EMAIL] SMTP_USER/SMTP_PASSWORD no configurados — omitiendo email")
        return False
    try:
        msg = MIMEMultipart()
        msg["From"]    = smtp_user
        msg["To"]      = EMAIL_ULISES
        msg["Subject"] = asunto
        msg.attach(MIMEText(body, "plain", "utf-8"))
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT, timeout=20) as server:
            server.starttls()
            server.login(smtp_user, smtp_pass)
            server.send_message(msg)
        logger.info(f"[CITAS EMAIL] ✅ Enviado a {EMAIL_ULISES}: {asunto}")
        return True
    except Exception as e:
        logger.error(f"[CITAS EMAIL] Error SMTP: {e}")
        return False


async def _enviar_email(asunto: str, body: str) -> bool:
    return await asyncio.to_thread(_enviar_email_sync, asunto, body)


# ─── Grupo interno Whapi ──────────────────────────────────────────────────────

_grupo_id_cache: str | None = None


async def _obtener_grupo_id() -> str | None:
    global _grupo_id_cache
    if _grupo_id_cache:
        return _grupo_id_cache
    token = os.getenv("WHAPI_TOKEN", "")
    if not token:
        return None
    try:
        async with httpx.AsyncClient(timeout=10) as http:
            r = await http.get(
                "https://gate.whapi.cloud/chats",
                headers={"Authorization": f"Bearer {token}"},
                params={"count": 50},
            )
            if r.status_code == 200:
                for chat in r.json().get("chats", []):
                    if GRUPO_NOMBRE.lower() in chat.get("name", "").lower():
                        _grupo_id_cache = chat.get("id")
                        return _grupo_id_cache
    except Exception as e:
        logger.error(f"[CITAS GRUPO] Error buscando grupo: {e}")
    logger.warning(f"[CITAS GRUPO] No se encontró '{GRUPO_NOMBRE}'")
    return None


async def _enviar_grupo(mensaje: str) -> bool:
    grupo_id = await _obtener_grupo_id()
    if not grupo_id:
        return False
    token = os.getenv("WHAPI_TOKEN", "")
    try:
        async with httpx.AsyncClient(timeout=15) as http:
            r = await http.post(
                "https://gate.whapi.cloud/messages/text",
                headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
                json={"to": grupo_id, "body": mensaje},
            )
            if r.status_code != 200:
                logger.error(f"[CITAS GRUPO] HTTP {r.status_code}: {r.text[:100]}")
                return False
            return True
    except Exception as e:
        logger.error(f"[CITAS GRUPO] Error enviando: {e}")
        return False


# ─── Notificaciones públicas ──────────────────────────────────────────────────

async def notificar_nueva_cita(
    nombre: str,
    telefono: str,
    dispositivo: str,
    problema: str,
    fecha_texto: str,
    hora_texto: str,
    asesor: str,
    evento_id: str = "",
) -> None:
    """Notifica inmediatamente a Ulises por email y grupo cuando se agenda una cita."""
    when = f"{fecha_texto.capitalize()}, {hora_texto}"

    asunto = f"🔔 Nueva cita agendada — {nombre} — {hora_texto}"
    body = (
        f"Nueva cita agendada ✅\n\n"
        f"👤 Cliente: {nombre}\n"
        f"📞 Teléfono: {telefono}\n"
        f"📱 Dispositivo: {dispositivo}\n"
        f"⚠️ Falla/Servicio: {problema}\n"
        f"⏰ Hora: {when}\n"
        f"👨‍💼 Asesor que atendió: {asesor}\n"
        f"📍 Ubicación: {_UBICACION}\n\n"
        f"---\n"
        f"Recordatorio: Esta cita está en tu Google Calendar"
    )
    msg_grupo = (
        f"🔔 *NUEVA CITA AGENDADA*\n"
        f"👤 {nombre} | 📱 {dispositivo}\n"
        f"⏰ {when} | ⚠️ {problema}\n"
        f"👨‍💼 Asesor: {asesor}"
    )

    enviado_email = await _enviar_email(asunto, body)
    enviado_grupo = await _enviar_grupo(msg_grupo)

    if evento_id:
        from agent.memory import registrar_cita_notificada
        await registrar_cita_notificada(evento_id, "inmediata", telefono, enviado_email, enviado_grupo)

    logger.info(f"[CITAS] Notificación inmediata — {nombre} {when} | email={enviado_email} grupo={enviado_grupo}")


async def notificar_recordatorio_1h(
    nombre: str,
    telefono: str,
    dispositivo: str,
    hora_texto: str,
    asesor: str = "",
    evento_id: str = "",
) -> None:
    """Notifica a Ulises 1 hora antes de la cita."""
    asunto = f"⏰ RECORDATORIO — Cita en 1 hora — {nombre}"
    body = (
        f"Recordatorio de cita en 1 hora ⏰\n\n"
        f"👤 Cliente: {nombre}\n"
        f"📞 Teléfono: {telefono}\n"
        f"📱 Dispositivo: {dispositivo}\n"
        f"⏰ Hora: {hora_texto}\n"
        f"👨‍💼 Asesor: {asesor or 'N/A'}\n"
        f"📍 Ubicación: {_UBICACION}\n\n"
        f"---\n"
        f"Esta cita está en tu Google Calendar"
    )
    msg_grupo = (
        f"⏰ *RECORDATORIO: Cita de {nombre} en 1 hora ({hora_texto})*\n"
        f"📱 {dispositivo}"
    )

    enviado_email = await _enviar_email(asunto, body)
    enviado_grupo = await _enviar_grupo(msg_grupo)

    if evento_id:
        from agent.memory import registrar_cita_notificada
        await registrar_cita_notificada(evento_id, "recordatorio_1h", telefono, enviado_email, enviado_grupo)

    logger.info(f"[CITAS] Recordatorio 1h — {nombre} {hora_texto} | email={enviado_email} grupo={enviado_grupo}")


async def enviar_resumen_diario() -> None:
    """Genera y envía el resumen de citas del día a Ulises (email + grupo)."""
    from agent.google_calendar import obtener_eventos_del_dia, obtener_eventos_rango

    ahora = datetime.now(_ZONA_MX)
    fecha_txt = f"{_DIAS_ES.get(ahora.weekday(),'')} {ahora.day} de {_MESES_ES.get(ahora.month,'')}"

    eventos_hoy  = await obtener_eventos_del_dia()
    desde_prox   = ahora.date() + timedelta(days=1)
    hasta_prox   = ahora.date() + timedelta(days=4)
    proximos     = await obtener_eventos_rango(desde_prox, hasta_prox)

    # ── Email ──
    asunto = f"📅 Resumen de citas — {fecha_txt}"
    if not eventos_hoy:
        citas_txt = "No hay citas agendadas para hoy."
    else:
        lineas = [
            f"{i}. {ev['nombre']} — {ev.get('dispositivo','N/A')} — "
            f"{ev['hora']} — {ev.get('problema','N/A')}"
            for i, ev in enumerate(eventos_hoy, 1)
        ]
        citas_txt = "\n".join(lineas)

    proximos_txt = ""
    if proximos:
        proximos_txt = "\n---\nPróximas citas:\n"
        for ev in proximos[:3]:
            proximos_txt += (
                f"• {ev.get('fecha_txt','')} {ev['hora']} — "
                f"{ev['nombre']} ({ev.get('dispositivo','')})\n"
            )

    body = (
        f"Resumen de citas para hoy — {fecha_txt}\n\n"
        f"Total de citas: {len(eventos_hoy)}\n\n"
        f"{citas_txt}"
        f"{proximos_txt}"
    )
    await _enviar_email(asunto, body)

    # ── Grupo ──
    if not eventos_hoy:
        lista_g = "No hay citas agendadas para hoy."
    else:
        lineas_g = [
            f"  {i}. {ev['nombre']} — {ev['hora']} — {ev.get('dispositivo','')}"
            for i, ev in enumerate(eventos_hoy, 1)
        ]
        lista_g = "\n".join(lineas_g)

    msg_grupo = (
        f"📅 *CITAS DE HOY — {fecha_txt}*\n"
        f"Total: {len(eventos_hoy)} citas\n\n"
        f"{lista_g}"
    )
    await _enviar_grupo(msg_grupo)
    logger.info(f"[CITAS] Resumen diario enviado — {len(eventos_hoy)} citas hoy")
