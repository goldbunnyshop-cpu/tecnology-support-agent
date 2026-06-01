# agent/appointment_notifications.py — Notificaciones de citas para Ulises (técnico)
# Email via Resend API (HTTP) + mensaje al grupo "Taller Interno TS"
# NOTA: Railway bloquea conexiones SMTP salientes — por eso usamos Resend API (HTTP).

import asyncio
import json
import logging
import os
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import httpx

logger = logging.getLogger("agentkit")

_ZONA_MX     = ZoneInfo("America/Mexico_City")
EMAIL_ULISES  = os.getenv("EMAIL_ULISES", "10telefonos10@gmail.com")
GRUPO_NOMBRE  = os.getenv("GRUPO_INTERNO_NOMBRE", "Taller Interno TS")
_UBICACION    = "Plazuela de la Fama 1, Col. La Fama, Tlalpan"

_DIAS_ES  = {0:"lunes",1:"martes",2:"miércoles",3:"jueves",4:"viernes",5:"sábado",6:"domingo"}
_MESES_ES = {1:"enero",2:"febrero",3:"marzo",4:"abril",5:"mayo",6:"junio",
             7:"julio",8:"agosto",9:"septiembre",10:"octubre",11:"noviembre",12:"diciembre"}


# ─── Email via Resend API (HTTP — funciona en Railway) ────────────────────────
# Configurar en Railway Variables:
#   RESEND_API_KEY = re_xxxx...  (obtener en resend.com, plan gratuito = 3000 emails/mes)
#   RESEND_FROM    = onboarding@resend.dev  (o tu dominio verificado)

async def _enviar_email(asunto: str, body: str) -> bool:
    """Envía email usando Resend API (HTTP). Railway NO permite SMTP saliente."""
    api_key = os.getenv("RESEND_API_KEY", "")
    if not api_key:
        logger.warning("[CITAS EMAIL] RESEND_API_KEY no configurado — omitiendo email")
        return False
    from_addr = os.getenv("RESEND_FROM", "onboarding@resend.dev")
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                "https://api.resend.com/emails",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "from": from_addr,
                    "to": [EMAIL_ULISES],
                    "subject": asunto,
                    "text": body,
                },
            )
        if resp.status_code in (200, 201):
            logger.info(f"[CITAS EMAIL] ✅ Enviado via Resend a {EMAIL_ULISES}: {asunto}")
            return True
        else:
            logger.error(f"[CITAS EMAIL] Error Resend {resp.status_code}: {resp.text[:200]}")
            return False
    except Exception as e:
        logger.error(f"[CITAS EMAIL] Excepción Resend: {e}")
        return False


# ─── Grupo interno Whapi ──────────────────────────────────────────────────────

_grupo_id_cache: str | None = None


async def _obtener_grupo_id() -> str | None:
    """
    Resuelve el ID del grupo interno de WhatsApp.

    Orden de prioridad:
      1. GRUPO_CHRISTIAN_INTERNO en .env (ID directo, ej: "120363xxx@g.us") — preferido.
      2. Búsqueda por nombre via Whapi: GRUPO_INTERNO_NOMBRE (default "Taller Interno TS").
    """
    global _grupo_id_cache
    if _grupo_id_cache:
        return _grupo_id_cache

    # Opción 1: ID directo desde .env (no requiere llamar a Whapi)
    grupo_id_directo = os.getenv("GRUPO_CHRISTIAN_INTERNO", "").strip()
    if grupo_id_directo:
        _grupo_id_cache = grupo_id_directo
        logger.info(f"[CITAS GRUPO] Usando GRUPO_CHRISTIAN_INTERNO directo: {grupo_id_directo}")
        return _grupo_id_cache

    # Opción 2: búsqueda por nombre en Whapi
    token = os.getenv("WHAPI_TOKEN", "")
    if not token:
        logger.warning("[CITAS GRUPO] WHAPI_TOKEN no configurado — no puedo buscar grupo")
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
                        logger.info(f"[CITAS GRUPO] Grupo encontrado por nombre '{GRUPO_NOMBRE}' → {_grupo_id_cache}")
                        return _grupo_id_cache
            else:
                logger.error(f"[CITAS GRUPO] Whapi /chats HTTP {r.status_code}: {r.text[:200]}")
    except Exception as e:
        logger.error(f"[CITAS GRUPO] Error buscando grupo: {e}")
    logger.warning(
        f"[CITAS GRUPO] No se encontró el grupo. "
        f"Configura GRUPO_CHRISTIAN_INTERNO=<chat_id>@g.us en .env "
        f"o crea un grupo de WhatsApp llamado '{GRUPO_NOMBRE}'."
    )
    return None


async def _enviar_grupo(mensaje: str, reintentos: int = 2) -> bool:
    """Envía mensaje al grupo interno con reintentos automáticos."""
    grupo_id = await _obtener_grupo_id()
    if not grupo_id:
        logger.warning("[CITAS GRUPO] ❌ No se encontró el grupo — revisa GRUPO_CHRISTIAN_INTERNO en .env")
        return False

    token = os.getenv("WHAPI_TOKEN", "")
    if not token:
        logger.warning("[CITAS GRUPO] ❌ WHAPI_TOKEN no configurado")
        return False

    # Validar mensaje UTF-8
    try:
        mensaje_validado = mensaje.encode('utf-8', errors='replace').decode('utf-8')
    except Exception as e:
        logger.warning(f"[CITAS GRUPO] Validación UTF-8: {e}")
        mensaje_validado = mensaje

    # Intentar envío con reintentos
    for intento in range(1, reintentos + 1):
        try:
            logger.info(
                f"[CITAS GRUPO] 🔄 Intento {intento}/{reintentos} — "
                f"Enviando a {grupo_id[:20]}... — {mensaje_validado[:60]}..."
            )

            # JSON ASCII-safe: escapa emojis a \uXXXX para evitar mojibake
            body_bytes = json.dumps(
                {"to": grupo_id, "body": mensaje_validado},
                ensure_ascii=True,
            ).encode("ascii")
            async with httpx.AsyncClient(timeout=15) as http:
                r = await http.post(
                    "https://gate.whapi.cloud/messages/text",
                    headers={
                        "Authorization": f"Bearer {token}",
                        "Content-Type": "application/json; charset=utf-8",
                    },
                    content=body_bytes,
                )

                if r.status_code == 200:
                    logger.info(f"[CITAS GRUPO] ✅ Mensaje enviado al grupo exitosamente")
                    return True
                else:
                    logger.error(
                        f"[CITAS GRUPO] ❌ HTTP {r.status_code} en intento {intento}/{reintentos}"
                        f" — {r.text[:150]}"
                    )
                    if intento < reintentos:
                        await asyncio.sleep(1)  # Esperar antes de reintentar

        except asyncio.TimeoutError:
            logger.error(f"[CITAS GRUPO] ⏱️ Timeout en intento {intento}/{reintentos}")
            if intento < reintentos:
                await asyncio.sleep(2)

        except Exception as e:
            logger.error(f"[CITAS GRUPO] ❌ Excepción en intento {intento}/{reintentos}: {type(e).__name__}: {e}")
            if intento < reintentos:
                await asyncio.sleep(1)

    logger.error(f"[CITAS GRUPO] ❌ FALLÓ después de {reintentos} intentos")
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

    logger.info(
        f"[CITAS NOTIF] 🚀 ========== INICIANDO NOTIFICACIÓN DE CITA =========="
    )
    logger.info(
        f"[CITAS NOTIF] Cliente: {nombre} | Tel: {telefono}"
    )
    logger.info(
        f"[CITAS NOTIF] Dispositivo: {dispositivo} | Problema: {problema}"
    )
    logger.info(
        f"[CITAS NOTIF] Cuándo: {when} | Asesor: {asesor}"
    )

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

    # Email
    logger.info(f"[CITAS NOTIF] 📧 Enviando email a {EMAIL_ULISES}...")
    try:
        enviado_email = await _enviar_email(asunto, body)
        if enviado_email:
            logger.info(f"[CITAS NOTIF] ✅ Email enviado exitosamente")
        else:
            logger.warning(f"[CITAS NOTIF] ⚠️ Email no se envió (SMTP deshabilitado o error)")
    except Exception as e:
        logger.error(f"[CITAS NOTIF] ❌ Excepción enviando email: {type(e).__name__}: {e}")
        enviado_email = False

    # Grupo
    logger.info(f"[CITAS NOTIF] 📱 Enviando notificación al grupo...")
    try:
        enviado_grupo = await _enviar_grupo(msg_grupo, reintentos=3)
        if enviado_grupo:
            logger.info(f"[CITAS NOTIF] ✅ Notificación al grupo enviada exitosamente")
        else:
            logger.warning(f"[CITAS NOTIF] ⚠️ No se pudo notificar al grupo después de reintentos")
    except Exception as e:
        logger.error(f"[CITAS NOTIF] ❌ Excepción enviando al grupo: {type(e).__name__}: {e}")
        import traceback
        logger.error(f"[CITAS NOTIF] Traceback:\n{traceback.format_exc()}")
        enviado_grupo = False

    # Registrar (OPCIONAL — si falla, continúa de todas formas)
    if evento_id:
        logger.info(f"[CITAS NOTIF] 📋 Intentando registrar en historial (evento_id={evento_id})")
        try:
            from agent.memory import registrar_cita_notificada
            await registrar_cita_notificada(evento_id, "inmediata", telefono, enviado_email, enviado_grupo)
            logger.info(f"[CITAS NOTIF] ✅ Cita registrada en historial de notificaciones")
        except Exception as e:
            logger.warning(
                f"[CITAS NOTIF] ⚠️ No se registró en BD (tabla puede no existir): {type(e).__name__}: {str(e)[:100]}"
            )
            logger.info(f"[CITAS NOTIF] ℹ️ Continuando de todas formas — las notificaciones SÍ se enviaron")

    logger.info(
        f"[CITAS NOTIF] ========== NOTIFICACIÓN TERMINADA =========="
        f" | Email: {'✅' if enviado_email else '❌'} "
        f"| Grupo: {'✅' if enviado_grupo else '❌'}"
    )


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
    logger.info("[CITAS RESUMEN] ✅ Resumen diario enviado")
