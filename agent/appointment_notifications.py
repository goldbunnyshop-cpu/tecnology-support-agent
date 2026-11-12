# agent/appointment_notifications.py — Notificaciones de citas para Ulises (técnico)
# Mensajes al grupo de WhatsApp "Taller Interno TS" (sin correo: Ulises recibe todo por el grupo)

import re
import asyncio
import json
import logging
import os
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import httpx

logger = logging.getLogger("agentkit")

_ZONA_MX     = ZoneInfo("America/Mexico_City")
GRUPO_NOMBRE  = os.getenv("GRUPO_INTERNO_NOMBRE", "Taller Interno TS")
_UBICACION    = "Plazuela de la Fama 1, Col. La Fama, Tlalpan"

_DIAS_ES  = {0:"lunes",1:"martes",2:"miércoles",3:"jueves",4:"viernes",5:"sábado",6:"domingo"}
_MESES_ES = {1:"enero",2:"febrero",3:"marzo",4:"abril",5:"mayo",6:"junio",
             7:"julio",8:"agosto",9:"septiembre",10:"octubre",11:"noviembre",12:"diciembre"}


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


async def _enviar_grupo(mensaje: str, reintentos: int = 2, mentions: list[str] | None = None) -> bool:
    """Envía mensaje al grupo interno.

    IMPORTANTE — solo reintenta cuando Whapi responde con un error HTTP claro
    (la solicitud NO fue procesada). Si hay timeout o una excepción de red,
    NO se reintenta: el mensaje puede haberse entregado igual aunque no
    recibiéramos la respuesta a tiempo, y reintentar en ese caso era la causa
    de que la misma confirmación de cita llegara duplicada/triplicada al grupo.
    """
    grupo_id = await _obtener_grupo_id()
    if not grupo_id:
        logger.warning("[CITAS GRUPO] ❌ No se encontró el grupo — revisa GRUPO_CHRISTIAN_INTERNO en .env")
        return False

    # Proveedor distinto de Whapi (ej. WAHA): enviar por la capa de providers
    if os.getenv("WHATSAPP_PROVIDER", "whapi").lower() != "whapi":
        from agent.providers import obtener_proveedor
        _prv = obtener_proveedor()
        try:
            return await _prv.enviar_mensaje(grupo_id, mensaje, mentions=mentions)
        except TypeError:
            return await _prv.enviar_mensaje(grupo_id, mensaje)

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

    # Intentar envío — reintentos SOLO ante error HTTP confirmado
    for intento in range(1, reintentos + 1):
        try:
            logger.info(
                f"[CITAS GRUPO] 🔄 Intento {intento}/{reintentos} — "
                f"Enviando a {grupo_id[:20]}... — {mensaje_validado[:60]}..."
            )

            # JSON ASCII-safe: escapa emojis a \uXXXX para evitar mojibake
            _payload = {"to": grupo_id, "body": mensaje_validado}
            if mentions:
                # Whapi: el body debe incluir "@<número>" y la lista "mentions" con los mismos números
                _payload["mentions"] = mentions
            body_bytes = json.dumps(_payload, ensure_ascii=True).encode("ascii")
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

            # Error HTTP claro: Whapi rechazó la solicitud → sí es seguro reintentar
            logger.error(
                f"[CITAS GRUPO] ❌ HTTP {r.status_code} en intento {intento}/{reintentos}"
                f" — {r.text[:150]}"
            )
            if intento < reintentos:
                await asyncio.sleep(1)  # Esperar antes de reintentar

        except (asyncio.TimeoutError, httpx.TimeoutException):
            # Ambiguo: pudo haberse entregado aunque no llegó la respuesta a tiempo.
            # NO reintentar — evita reenviar la misma cita al grupo.
            logger.error(
                f"[CITAS GRUPO] ⏱️ Timeout en intento {intento}/{reintentos} — "
                f"NO se reintenta (el mensaje pudo haberse entregado igual)"
            )
            return False

        except Exception as e:
            # También ambiguo (error de red a media transacción) → no reintentar
            logger.error(f"[CITAS GRUPO] ❌ Excepción en intento {intento}/{reintentos}: {type(e).__name__}: {e}")
            return False

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
    """Notifica inmediatamente al grupo de WhatsApp cuando se agenda una cita."""
    when = f"{fecha_texto.capitalize()}, {hora_texto}"

    # ── Anti-duplicados: reservar el evento ANTES de enviar ──
    # Si esta notificación "inmediata" ya fue registrada (por una llamada
    # anterior, o porque el scheduler de citas-Ulises corrió en paralelo),
    # no la repetimos. Registrar AQUÍ (antes de enviar) — y no al final —
    # evita que el scheduler de 10 min reenvíe la misma cita al grupo mientras
    # este envío sigue en curso.
    from agent.memory import cita_notificada_ya_enviada, registrar_cita_notificada
    _tel10 = "".join(ch for ch in str(telefono or "") if ch.isdigit())[-10:]
    _slot = re.sub(r"[^a-z0-9]", "", f"{fecha_texto}{hora_texto}".lower())
    clave_slot = f"slot:{_tel10}:{_slot}" if _tel10 and _slot else ""
    if clave_slot:
        if await cita_notificada_ya_enviada(clave_slot, "inmediata"):
            logger.warning(f"[CITAS NOTIF] ⚠️ Ya se avisó al grupo de la cita {clave_slot} — se omite (evento duplicado)")
            return
        await registrar_cita_notificada(clave_slot, "inmediata", telefono, False, False)
    if evento_id:
        if await cita_notificada_ya_enviada(evento_id, "inmediata"):
            logger.warning(
                f"[CITAS NOTIF] ⚠️ Notificación 'inmediata' ya registrada para "
                f"evento_id={evento_id} — se omite para no duplicar en el grupo"
            )
            return
        await registrar_cita_notificada(evento_id, "inmediata", telefono, False, False)

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

    msg_grupo = (
        f"🔔 *NUEVA CITA AGENDADA*\n"
        f"👤 {nombre} | 📱 {dispositivo}\n"
        f"⏰ {when} | ⚠️ {problema}\n"
        f"👨‍💼 Asesor: {asesor}"
    )

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

    # Nota: el registro anti-duplicados ya se hizo ANTES de enviar (ver arriba).
    # No se vuelve a registrar aquí para no pisar esa reserva.

    logger.info(
        f"[CITAS NOTIF] ========== NOTIFICACIÓN TERMINADA =========="
        f" | Grupo: {'✅' if enviado_grupo else '❌'}"
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
    msg_grupo = (
        f"⏰ *RECORDATORIO: Cita de {nombre} en 1 hora ({hora_texto})*\n"
        f"📱 {dispositivo}"
    )

    # ── Anti-duplicados: igual que en notificar_nueva_cita, reservar ANTES de enviar ──
    if evento_id:
        from agent.memory import cita_notificada_ya_enviada, registrar_cita_notificada
        if await cita_notificada_ya_enviada(evento_id, "recordatorio_1h"):
            logger.warning(
                f"[CITAS] ⚠️ Recordatorio 1h ya registrado para evento_id={evento_id} — se omite"
            )
            return
        await registrar_cita_notificada(evento_id, "recordatorio_1h", telefono, False, False)

    enviado_grupo = await _enviar_grupo(msg_grupo)

    logger.info(f"[CITAS] Recordatorio 1h — {nombre} {hora_texto} | grupo={enviado_grupo}")


async def enviar_resumen_diario() -> None:
    """Genera y envía el resumen de citas del día al grupo de WhatsApp."""
    from agent.google_calendar import obtener_eventos_del_dia

    ahora = datetime.now(_ZONA_MX)
    fecha_txt = f"{_DIAS_ES.get(ahora.weekday(),'')} {ahora.day} de {_MESES_ES.get(ahora.month,'')}"

    eventos_hoy  = await obtener_eventos_del_dia()

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
