# agent/followup.py — Scheduler de seguimiento automático a leads
# Generado por AgentKit

import asyncio
import logging
import os
from datetime import datetime, timezone, time as dt_time
from zoneinfo import ZoneInfo
from anthropic import AsyncAnthropic
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger("agentkit")
client = AsyncAnthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

INTERVALO_SEGUIMIENTO  = 1800  # revisar seguimientos cada 30 minutos
INTERVALO_RETOMA       = 600   # revisar retomas cada 10 minutos
INTERVALO_RECORDATORIO = 600   # revisar recordatorios de cita cada 10 minutos

_ZONA_MX = ZoneInfo("America/Mexico_City")


def es_horario_habil() -> bool:
    """
    True si ahora es horario hábil en CDMX:
      Lunes–viernes: 10:00 – 21:00
      Sábados–domingos: 11:00 – 20:00
    """
    ahora = datetime.now(_ZONA_MX)
    hora  = ahora.time().replace(second=0, microsecond=0)
    if ahora.weekday() <= 4:   # lunes a viernes
        return dt_time(10, 0) <= hora <= dt_time(21, 0)
    else:                      # sábado y domingo
        return dt_time(11, 0) <= hora <= dt_time(20, 0)

_FALLBACK = [
    "Hola, ¿pudiste resolver lo de tu equipo? Aquí seguimos para ayudarte cuando gustes. 😊",
    "Buenas, queríamos saber si sigues necesitando apoyo con tu dispositivo. Avísanos.",
    "Hola, ¿pudiste solucionar lo de tu equipo? Si necesitas algo, con gusto te atendemos.",
    "Hola, este es nuestro último mensaje. Cuando necesites apoyo, aquí estaremos. ¡Que estés bien! 😊",
]


def _tiene_presupuesto_en_historial(historial: list[dict]) -> bool:
    """Detecta si ya se envió un presupuesto al cliente (por el comando presupuesto: del grupo)."""
    for msg in historial:
        if msg["role"] == "assistant":
            c = msg["content"].lower()
            if "costo del servicio" in c or ("presupuesto" in c and "$" in c):
                return True
    return False


def _cliente_satisfecho_historial(historial: list[dict]) -> bool:
    """
    Detecta si el cliente expresó satisfacción con el servicio en mensajes recientes.
    Revisa solo los últimos 6 mensajes del cliente para evitar falsos positivos.
    """
    satisfaccion_kw = [
        "ya lo recogí", "ya fui por", "ya lo tengo", "ya pasé", "ya lo llevé",
        "quedó bien", "quedó perfecto", "quedó excelente", "quedó muy bien", "quedó genial",
        "funciona bien", "funciona perfecto", "ya funciona", "ya sirve",
        "excelente servicio", "muy buen servicio", "buen trabajo",
        "los recomiendo", "les recomiendo", "muy recomendados",
    ]
    mensajes_cliente = [m for m in historial if m["role"] == "user"][-6:]
    for msg in mensajes_cliente:
        c = msg["content"].lower()
        if any(kw in c for kw in satisfaccion_kw):
            return True
    return False


def _reseña_ya_solicitada(historial: list[dict]) -> bool:
    """Detecta si ya se solicitó una reseña en esta conversación para no repetirla."""
    for msg in historial:
        if msg["role"] == "assistant":
            c = msg["content"].lower()
            if "maps.app.goo.gl" in c or "reseña en google" in c or "déjanos una reseña" in c:
                return True
    return False


async def generar_mensaje_seguimiento(
    historial: list[dict],
    numero_seguimiento: int,
    asesor: str = "Valeria",
) -> tuple[str, str]:
    """
    Genera un mensaje de seguimiento personalizado.
    Retorna (mensaje, prioridad) donde prioridad es "urgente"|"medio"|"bajo".
    """
    if not historial:
        fallback = _FALLBACK[min(numero_seguimiento, len(_FALLBACK) - 1)]
        return f"{fallback}\n\n{asesor} — Tecnology Support", "medio"

    fragmento = "\n".join(
        f"{'Agente' if m['role'] == 'assistant' else 'Cliente'}: {m['content']}"
        for m in historial[-20:]
    )

    es_ultimo = numero_seguimiento >= 3
    nota_ultimo = "(Es el ÚLTIMO intento — tono de despedida cordial, deja la puerta abierta.)" if es_ultimo else ""

    tiene_presupuesto = _tiene_presupuesto_en_historial(historial)
    ctx_presupuesto = (
        "\nCONTEXTO IMPORTANTE: Ya se envió un presupuesto al cliente. "
        "NO menciones el costo de diagnóstico ($200). "
        "Enfoca el mensaje en dar continuidad a la decisión y ayudar a agendar la visita."
        if tiene_presupuesto else ""
    )

    satisfecho = _cliente_satisfecho_historial(historial)
    reseña_enviada = _reseña_ya_solicitada(historial)
    google_url = os.getenv("GOOGLE_REVIEW_URL", "https://maps.app.goo.gl/XdCSu743LpyY6aAt7")
    ctx_resena = (
        f"\nCONTEXTO IMPORTANTE: El cliente ya expresó satisfacción con el servicio. "
        f"Usa el Escenario F — solicita una reseña en Google. URL: {google_url}"
        if (satisfecho and not reseña_enviada) else
        "\nCONTEXTO: El cliente ya expresó satisfacción y la reseña ya fue solicitada. "
        "Solo agradece con calidez si responde positivamente, no repitas el pedido de reseña."
        if (satisfecho and reseña_enviada) else ""
    )

    prompt = f"""Eres {asesor}, asesor de Tecnology Support, un taller de reparación de electrónicos en CDMX.

Un cliente dejó de responder. Lee el historial y produce la respuesta EN ESTE FORMATO EXACTO:

PRIORIDAD: [urgente|medio|bajo]
MENSAJE:
[el mensaje aquí]

Criterios de prioridad:
- urgente: preguntó precio, dijo que iba a ir, o mostró clara intención de reparación
- medio: conversación activa sobre un dispositivo específico
- bajo: solo preguntas generales sin dispositivo ni precio mencionado
{ctx_presupuesto}{ctx_resena}

HISTORIAL:
{fragmento}

SEGUIMIENTO {numero_seguimiento + 1} DE 4. {nota_ultimo}

Escenarios para el mensaje:
A — Preguntó precio → "Hola [nombre], ¿te quedó alguna duda sobre el precio del [servicio]? 😊"
B — Iba a venir → "Hola [nombre], ¿pudiste venir a dejarnos tu [dispositivo]? Si necesitas reagendar, con gusto."
C — Solo pidió info → "Hola [nombre], vi que preguntaste sobre [servicio/dispositivo]. ¿Aún lo necesitas?"
D — Ya tiene presupuesto → "Hola [nombre], soy {asesor} de Tecnology Support 😊 Quería dar seguimiento a tu [equipo]. ¿Pudiste revisar el presupuesto que te compartimos? ¿Te quedó alguna duda antes de traerlo al módulo?"
E — Sin contexto → "Hola [nombre], hace un rato nos escribiste. ¿Pudimos ayudarte o tienes alguna duda? 😊"
F — Cliente satisfecho (usa solo si el contexto indica satisfacción) → "Hola [nombre], me alegra mucho que quedó bien 😊 Si tienes un momento, nos ayudaría muchísimo una reseña en Google: {google_url} ¡Gracias de antemano!"

Reglas del mensaje:
- Usa nombre real si lo sabes
- Menciona el dispositivo/servicio específico
- Máximo 2-3 oraciones, tono natural de WhatsApp
- Sin asteriscos, sin "estimado cliente"
- Máximo 1 emoji
- Firma: "{asesor} — Tecnology Support" en línea separada"""

    try:
        response = await client.messages.create(
            model="claude-haiku-4-5-20251001",  # Haiku: mensajes cortos de seguimiento, 4× más barato
            max_tokens=200,
            messages=[{"role": "user", "content": prompt}],
        )
        texto = response.content[0].text.strip()

        # Parsear prioridad y mensaje del formato estructurado
        prioridad = "medio"
        mensaje   = texto
        lineas    = texto.splitlines()

        if lineas and lineas[0].upper().startswith("PRIORIDAD:"):
            p = lineas[0].split(":", 1)[1].strip().lower()
            if p in ("urgente", "medio", "bajo"):
                prioridad = p
            # Quitar la línea PRIORIDAD: y la línea MENSAJE: si existe
            resto = "\n".join(lineas[1:]).strip()
            if resto.upper().startswith("MENSAJE:"):
                resto = resto.split(":", 1)[1].strip()
            mensaje = resto

        return mensaje, prioridad

    except Exception as e:
        logger.error(f"Error generando mensaje de seguimiento: {e}")
        fallback = _FALLBACK[min(numero_seguimiento, len(_FALLBACK) - 1)]
        return f"{fallback}\n\n{asesor} — Tecnology Support", "medio"


async def ejecutar_seguimientos():
    from agent.leads import obtener_leads_para_seguimiento, registrar_seguimiento_enviado, MAX_SEGUIMIENTOS
    from agent.memory import obtener_historial, guardar_mensaje
    from agent.providers import obtener_proveedor

    # Nunca enviar seguimientos fuera de horario hábil
    if not es_horario_habil():
        return

    proveedor = obtener_proveedor()
    leads = await obtener_leads_para_seguimiento()

    if not leads:
        return

    logger.info(f"Seguimiento automático: {len(leads)} leads para contactar")

    for lead in leads:
        try:
            # Respetar stop: — nunca enviar seguimientos a números silenciados
            from agent.memory import numero_esta_stopped
            if await numero_esta_stopped(lead.telefono):
                logger.info(f"[SEGUIMIENTO] Omitido — {lead.telefono} está STOPPED")
                continue

            # No interrumpir al cliente si tiene una cita futura confirmada
            from agent.leads import tiene_cita_pendiente
            cita_futura = await tiene_cita_pendiente(lead.telefono)
            if cita_futura:
                logger.info(
                    f"[SEGUIMIENTO] Omitido — {lead.telefono} tiene cita el "
                    f"{cita_futura.strftime('%d/%m %H:%M')} (aún no ha pasado)"
                )
                continue

            historial = await obtener_historial(lead.telefono, limite=30)
            asesor = lead.asesor_asignado or "Valeria"
            mensaje, prioridad = await generar_mensaje_seguimiento(historial, lead.seguimientos_enviados, asesor)
            enviado = await proveedor.enviar_mensaje(lead.telefono, mensaje)
            if enviado:
                await guardar_mensaje(lead.telefono, "assistant", mensaje)
                await registrar_seguimiento_enviado(lead.telefono, prioridad)
                logger.info(
                    f"Seg {lead.seguimientos_enviados + 1}/{MAX_SEGUIMIENTOS} "
                    f"[{asesor}] [{prioridad}] → {lead.telefono}: {mensaje[:60]}"
                )
            else:
                logger.warning(f"No se pudo enviar seguimiento a {lead.telefono}")
        except Exception as e:
            import traceback
            logger.error(f"Error procesando seguimiento para {lead.telefono}: {e}\n{traceback.format_exc()}")


async def ejecutar_retomas():
    """
    Revisa retomas nocturnas pendientes y las envía si el cliente no respondió.
    Se ejecuta cada 10 minutos.
    """
    from agent.leads import obtener_retomas_pendientes, cancelar_retoma
    from agent.memory import obtener_historial, guardar_mensaje
    from agent.providers import obtener_proveedor

    proveedor = obtener_proveedor()
    leads = await obtener_retomas_pendientes()

    if not leads:
        return

    logger.info(f"Retomas pendientes: {len(leads)}")

    for lead in leads:
        try:
            # Respetar stop: — nunca enviar retomas a números silenciados
            from agent.memory import numero_esta_stopped
            if await numero_esta_stopped(lead.telefono):
                logger.info(f"[RETOMA] Omitida — {lead.telefono} está STOPPED")
                continue

            # Si el cliente ya respondió después de que se programó la retoma, cancelar
            retoma_desde = lead.retoma_desde
            ultimo = lead.ultimo_mensaje
            if retoma_desde and ultimo and ultimo > retoma_desde:
                await cancelar_retoma(lead.telefono)
                logger.info(f"Retoma cancelada (cliente ya respondió): {lead.telefono}")
                continue

            asesor = lead.asesor_asignado or "Valeria"

            historial = await obtener_historial(lead.telefono, limite=10)
            from agent.commands import extraer_nombre_cliente
            nombre_cliente = extraer_nombre_cliente(historial)

            saludo = f"¡Hola, {nombre_cliente}!" if nombre_cliente else "¡Hola!"

            mensaje = (
                f"{saludo} \U0001f60a Soy {asesor} de Tecnology Support. "
                f"Vi que nos escribiste anoche, ya estamos en línea y listos para ayudarte. "
                f"¿En qué podemos apoyarte hoy?"
            )

            enviado = await proveedor.enviar_mensaje(lead.telefono, mensaje)
            if enviado:
                await guardar_mensaje(lead.telefono, "assistant", mensaje)
                logger.info(f"Retoma enviada → {lead.telefono}")

            await cancelar_retoma(lead.telefono)

        except Exception as e:
            logger.error(f"Error procesando retoma para {lead.telefono}: {e}")


def segundos_hasta_proximo_domingo_13h() -> float:
    from zoneinfo import ZoneInfo
    from datetime import timedelta
    ZONA = ZoneInfo("America/Mexico_City")
    ahora = datetime.now(ZONA)
    dias_hasta_domingo = (6 - ahora.weekday()) % 7
    if dias_hasta_domingo == 0 and (ahora.hour > 13 or (ahora.hour == 13 and ahora.minute > 0)):
        dias_hasta_domingo = 7
    proximo = ahora.replace(hour=13, minute=0, second=0, microsecond=0)
    proximo += timedelta(days=dias_hasta_domingo)
    segundos = (proximo - ahora).total_seconds()
    logger.info(f"Próximo reporte semanal: {proximo.strftime('%A %d/%m/%Y a las %H:%M')} ({segundos / 3600:.1f}h)")
    return segundos


async def ejecutar_alertas_presupuesto():
    """
    Detecta clientes que no respondieron 24h después de recibir su presupuesto.
    Notifica a Christian para seguimiento manual.
    """
    from agent.leads import obtener_leads_sin_respuesta_presupuesto
    from agent.providers import obtener_proveedor
    from agent.notifications import _enviar_alerta_christian
    from agent.commands import extraer_nombre_cliente
    from agent.memory import obtener_historial

    proveedor = obtener_proveedor()
    leads = await obtener_leads_sin_respuesta_presupuesto(horas=24)

    for lead in leads:
        try:
            historial = await obtener_historial(lead.telefono, limite=10)
            nombre = extraer_nombre_cliente(historial) or lead.telefono
            await _enviar_alerta_christian(
                proveedor,
                tipo="SIN RESPUESTA 24H DESPUÉS DE PRESUPUESTO",
                nombre=nombre,
                equipo="Ver historial",
                resumen=f"El cliente recibió presupuesto el {lead.presupuesto_enviado_en.strftime('%d/%m %H:%M')} y no ha respondido.",
            )
            # Limpiar presupuesto_enviado_en para no re-alertar
            from sqlalchemy import update as sq_update
            from agent.memory import async_session
            from agent.leads import Lead
            async with async_session() as session:
                await session.execute(
                    sq_update(Lead).where(Lead.telefono == lead.telefono).values(presupuesto_enviado_en=None)
                )
                await session.commit()
            logger.info(f"Alerta 24h presupuesto → {lead.telefono}")
        except Exception as e:
            logger.error(f"Error alerta presupuesto {lead.telefono}: {e}")


async def ejecutar_recordatorios_cita():
    """
    Consulta Google Calendar para citas que empiezan en ~1 hora.
    Envía recordatorio al cliente si aún no se envió uno.
    """
    from agent.google_calendar import obtener_eventos_proximos
    from agent.memory import recordatorio_ya_enviado, registrar_recordatorio, guardar_mensaje
    from agent.providers import obtener_proveedor
    from agent.commands import _formatear_numero_destino

    proveedor = obtener_proveedor()
    eventos = await obtener_eventos_proximos(minutos_desde=55, minutos_hasta=70)

    for ev in eventos:
        evento_id = ev["id"]
        if await recordatorio_ya_enviado(evento_id):
            continue

        nombre    = ev["nombre"]
        telefono  = ev["telefono"]
        hora_txt  = ev["hora"]
        dispositivo = ev.get("dispositivo", "")

        phone_fmt, advertencia = _formatear_numero_destino(telefono)
        if advertencia or not phone_fmt:
            logger.warning(f"[RECORDATORIO] Teléfono inválido '{telefono}' — omitido")
            continue

        equipo_txt = f" para tu {dispositivo}" if dispositivo else ""
        mensaje = (
            f"¡Hola {nombre}! 😊 Te recordamos que tienes una cita{equipo_txt} "
            f"en nuestro módulo hoy a las *{hora_txt}*. "
            f"Te esperamos en Plazuela de la Fama 1, Col. La Fama, Tlalpan, CDMX. "
            f"¿Confirmas tu asistencia? ✅"
        )

        # Registrar ANTES de enviar → evita race condition cuando dos
        # instancias del scheduler corren simultáneamente y ambas pasan
        # el check `recordatorio_ya_enviado` antes de que alguna marque el dedup.
        await registrar_recordatorio(evento_id, phone_fmt)
        enviado = await proveedor.enviar_mensaje(phone_fmt, mensaje)
        if enviado:
            await guardar_mensaje(phone_fmt, "assistant", mensaje)
            logger.info(f"[RECORDATORIO] ✅ Enviado a {phone_fmt} ({nombre}) — cita a las {hora_txt}")
        else:
            logger.warning(f"[RECORDATORIO] ❌ No se pudo enviar a {phone_fmt}")


async def ejecutar_recordatorios_24h_cliente():
    """
    Consulta Google Calendar para citas que empiezan en ~24 horas.
    Envía recordatorio "mañana a las X" al cliente si aún no se envió uno.
    Corre cada 10 minutos — el dedup con sufijo "_24h" garantiza envío único.
    """
    from agent.google_calendar import obtener_eventos_proximos
    from agent.memory import recordatorio_ya_enviado, registrar_recordatorio, guardar_mensaje
    from agent.providers import obtener_proveedor
    from agent.commands import _formatear_numero_destino

    proveedor = obtener_proveedor()
    # Ventana: eventos que empiezan entre 22.5h y 25.5h desde ahora
    # Amplia (3h) para no perder la ventana si el scheduler tuvo retraso,
    # angosta para no confundirse con citas de 2 días después.
    eventos = await obtener_eventos_proximos(minutos_desde=22*60+30, minutos_hasta=25*60+30)

    for ev in eventos:
        # Key distinto al de 1h para no mezclar dedup
        evento_id_24h = ev["id"] + "_24h"
        if await recordatorio_ya_enviado(evento_id_24h):
            continue

        nombre     = ev["nombre"]
        telefono   = ev["telefono"]
        hora_txt   = ev["hora"]
        dispositivo = ev.get("dispositivo", "")

        phone_fmt, advertencia = _formatear_numero_destino(telefono)
        if advertencia or not phone_fmt:
            logger.warning(f"[RECORDATORIO-24H] Teléfono inválido '{telefono}' — omitido")
            continue

        equipo_txt = f" para tu {dispositivo}" if dispositivo else ""
        mensaje = (
            f"¡Hola {nombre}! 😊 Te recordamos que *mañana* tienes tu cita{equipo_txt} "
            f"en nuestro módulo a las *{hora_txt}*. "
            f"Te esperamos en Plazuela de la Fama 1, Col. La Fama, Tlalpan, CDMX. "
            f"¿Confirmas tu asistencia? ✅"
        )

        # Registrar ANTES de enviar → evita duplicados por paralelismo
        await registrar_recordatorio(evento_id_24h, phone_fmt)
        enviado = await proveedor.enviar_mensaje(phone_fmt, mensaje)
        if enviado:
            await guardar_mensaje(phone_fmt, "assistant", mensaje)
            logger.info(
                f"[RECORDATORIO-24H] ✅ Enviado a {phone_fmt} ({nombre}) — cita mañana a las {hora_txt}"
            )
        else:
            logger.warning(f"[RECORDATORIO-24H] ❌ No se pudo enviar a {phone_fmt}")


async def ejecutar_alerta_factura():
    """
    Últimos 3 días del mes: alerta al grupo interno sobre órdenes con pago
    electrónico que aún no tienen factura.
    """
    from zoneinfo import ZoneInfo
    import calendar
    ZONA_MX = ZoneInfo("America/Mexico_City")
    hoy = datetime.now(ZONA_MX)
    ultimo_dia = calendar.monthrange(hoy.year, hoy.month)[1]
    if hoy.day < ultimo_dia - 2:
        return  # No es los últimos 3 días del mes

    try:
        from agent.crm import obtener_ordenes_facturables
        from agent.providers import obtener_proveedor
        from agent.commands import GRUPO_INTERNO

        ordenes = await obtener_ordenes_facturables()
        if not ordenes:
            return

        proveedor = obtener_proveedor()

        # Buscar el chat_id del grupo interno
        import httpx, os
        token = os.getenv("WHAPI_TOKEN", "")
        grupo_id = None
        async with httpx.AsyncClient(timeout=10) as http:
            r = await http.get(
                "https://gate.whapi.cloud/chats",
                headers={"Authorization": f"Bearer {token}"},
                params={"count": 50},
            )
            if r.status_code == 200:
                for chat in r.json().get("chats", []):
                    nombre = chat.get("name", "")
                    if GRUPO_INTERNO.lower() in nombre.lower():
                        grupo_id = chat.get("id")
                        break

        if not grupo_id:
            logger.warning("[CRM] No se encontró el grupo interno para alerta de factura")
            return

        lineas = "\n".join(
            f"  #{o['folio']} — {o['cliente']} — ${o['total']} ({o['pago']})"
            for o in ordenes[:20]
        )
        total_monto = sum(float(o["total"] or 0) for o in ordenes)
        msg = (
            f"🧾 *ALERTA — Generar factura al público en general*\n"
            f"Quedan {ultimo_dia - hoy.day} días para fin de mes.\n\n"
            f"Órdenes con pago electrónico sin factura ({len(ordenes)}):\n"
            f"{lineas}\n\n"
            f"💰 Total a facturar: ${total_monto:,.2f} MXN\n"
            f"Usa el comando *consultar: FOLIO* para ver detalles de cada orden."
        )
        await proveedor.enviar_mensaje(grupo_id, msg)
        logger.info(f"[CRM] Alerta de factura enviada — {len(ordenes)} órdenes pendientes")

    except Exception as e:
        logger.error(f"[CRM] Error en alerta de factura: {e}")


async def _loop_alerta_factura():
    """Verifica una vez al día si corresponde enviar alerta de factura."""
    while True:
        await asyncio.sleep(86400)  # 24 horas
        try:
            await ejecutar_alerta_factura()
        except Exception as e:
            logger.error(f"Error en loop alerta factura: {e}")


def _segundos_hasta_proximas_9am() -> float:
    """Segundos hasta las 9:00 AM CDMX del próximo día (o hoy si aún no llega)."""
    from datetime import timedelta as _td
    ahora = datetime.now(_ZONA_MX)
    proximas = ahora.replace(hour=9, minute=0, second=0, microsecond=0)
    if ahora >= proximas:
        proximas += _td(days=1)
    segundos = (proximas - ahora).total_seconds()
    logger.info(f"Próximo resumen diario de citas: {proximas.strftime('%A %d/%m a las %H:%M')} ({segundos/3600:.1f}h)")
    return segundos


async def ejecutar_notificaciones_citas_ulises():
    """
    Detecta citas en Google Calendar no notificadas a Ulises:
    - Recordatorio 1h antes (ventana 55-70 min)
    - Citas nuevas en los próximos 7 días (no registradas con tipo=inmediata)
    """
    from datetime import timedelta as _td
    from agent.google_calendar import obtener_eventos_proximos, obtener_eventos_rango
    from agent.memory import cita_notificada_ya_enviada
    from agent.appointment_notifications import notificar_nueva_cita, notificar_recordatorio_1h

    # 1) Recordatorio 1h para Ulises
    eventos_1h = await obtener_eventos_proximos(minutos_desde=55, minutos_hasta=70)
    for ev in eventos_1h:
        if not await cita_notificada_ya_enviada(ev["id"], "recordatorio_1h"):
            await notificar_recordatorio_1h(
                nombre=ev["nombre"],
                telefono=ev["telefono"],
                dispositivo=ev.get("dispositivo", ""),
                hora_texto=ev["hora"],
                evento_id=ev["id"],
            )

    # 2) Citas nuevas detectadas directamente en Google Calendar (no creadas vía bot)
    desde = datetime.now(_ZONA_MX).date()
    hasta = desde + _td(days=7)
    todos = await obtener_eventos_rango(desde, hasta)
    # Dedup robusto: evita duplicados por ID y por combinación (nombre + fecha)
    notificadas_esta_sesion = set()

    for ev in todos:
        if not ev.get("telefono"):
            continue

        # Clave de dedup: nombre + fecha (para evitar duplicados por cambios de ID)
        dedup_key = f"{ev.get('nombre', '')}_{ev.get('fecha_txt', '')}"

        # Chequea: 1) Ya notificada en BD, 2) Ya notificada en esta sesión
        if not await cita_notificada_ya_enviada(ev["id"], "inmediata") and dedup_key not in notificadas_esta_sesion:
            notificadas_esta_sesion.add(dedup_key)
            await notificar_nueva_cita(
                nombre=ev["nombre"],
                telefono=ev["telefono"],
                dispositivo=ev.get("dispositivo", ""),
                problema=ev.get("problema", ""),
                fecha_texto=ev.get("fecha_txt", ""),
                hora_texto=ev["hora"],
                asesor="Agenda externa",
                evento_id=ev["id"],
            )


async def _loop_notificaciones_citas_ulises():
    """Verifica citas nuevas y recordatorios 1h para Ulises cada 10 minutos."""
    while True:
        await asyncio.sleep(INTERVALO_RECORDATORIO)
        try:
            await ejecutar_notificaciones_citas_ulises()
        except Exception as e:
            logger.error(f"Error en notificaciones citas Ulises: {e}")


async def _loop_resumen_diario_citas():
    """Envía el resumen diario de citas a Ulises a las 9:00 AM CDMX."""
    await asyncio.sleep(_segundos_hasta_proximas_9am())
    while True:
        try:
            from agent.appointment_notifications import enviar_resumen_diario
            await enviar_resumen_diario()
        except Exception as e:
            logger.error(f"Error en resumen diario de citas: {e}")
        await asyncio.sleep(24 * 3600)


async def iniciar_scheduler():
    """
    Scheduler principal que corre en segundo plano:
    - Seguimientos a leads: cada hora
    - Retomas nocturnas: cada 10 minutos
    - Recordatorios de cita (cliente): cada 10 minutos
    - Notificaciones citas Ulises (email+grupo): cada 10 minutos
    - Resumen diario de citas: 9:00 AM CDMX
    - Alertas presupuesto 24h: cada hora
    - Alerta factura fin de mes: diaria
    - Reporte Excel: cada domingo a las 13:00 CDMX
    """
    logger.info("Scheduler activo: seguimientos/hora, retomas/10min, recordatorios/10min, citas-ulises/10min, resumen-citas/9am, factura/diario, reporte/domingo 13h")

    asyncio.create_task(iniciar_scheduler_reporte_semanal())
    asyncio.create_task(_loop_retomas())
    asyncio.create_task(_loop_recordatorios())
    asyncio.create_task(_loop_notificaciones_citas_ulises())
    asyncio.create_task(_loop_resumen_diario_citas())
    asyncio.create_task(_loop_alerta_factura())

    while True:
        await asyncio.sleep(INTERVALO_SEGUIMIENTO)
        try:
            await ejecutar_seguimientos()
        except Exception as e:
            logger.error(f"Error en scheduler de seguimientos: {e}")
        try:
            await ejecutar_alertas_presupuesto()
        except Exception as e:
            logger.error(f"Error en alertas presupuesto: {e}")


async def _loop_retomas():
    while True:
        await asyncio.sleep(INTERVALO_RETOMA)
        try:
            await ejecutar_retomas()
        except Exception as e:
            logger.error(f"Error en scheduler de retomas: {e}")


async def _loop_recordatorios():
    while True:
        await asyncio.sleep(INTERVALO_RECORDATORIO)
        try:
            await ejecutar_recordatorios_cita()          # recordatorio 1h antes al cliente
            await ejecutar_recordatorios_24h_cliente()   # recordatorio 24h antes al cliente
        except Exception as e:
            logger.error(f"Error en scheduler de recordatorios: {e}")


def _enviar_email_smtp_sync(ruta_excel: str, usuario: str, contrasena: str, destino: str):
    """Envía el reporte Excel por Gmail SMTP (síncrono — se llama con to_thread)."""
    import smtplib
    from email.mime.multipart import MIMEMultipart
    from email.mime.base import MIMEBase
    from email.mime.text import MIMEText
    from email import encoders

    fecha = datetime.now(_ZONA_MX).strftime("%d/%m/%Y")

    msg = MIMEMultipart()
    msg["From"]    = usuario
    msg["To"]      = destino
    msg["Subject"] = f"Reporte semanal Tecnology Support — {fecha}"
    msg.attach(MIMEText(
        f"Hola,\n\nAdjunto el reporte semanal de leads y órdenes "
        f"de Tecnology Support generado el {fecha}.\n\n"
        f"Tecnology Support — Sistema de gestión",
        "plain",
    ))
    with open(ruta_excel, "rb") as f:
        part = MIMEBase("application", "octet-stream")
        part.set_payload(f.read())
        encoders.encode_base64(part)
        part.add_header(
            "Content-Disposition",
            f"attachment; filename={os.path.basename(ruta_excel)}",
        )
        msg.attach(part)

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(usuario, contrasena)
        server.send_message(msg)


async def _enviar_reporte_semanal(ruta_excel: str):
    """
    Envía el reporte semanal.
    Prioridad: Resend API (HTTP) → notificación WhatsApp.
    SMTP y Google Drive NO funcionan en Railway (puerto bloqueado / sin quota).
    """
    dest_email = os.getenv("REPORT_EMAIL", "goldbunnyshop@gmail.com")
    fecha_txt  = datetime.now(_ZONA_MX).strftime("%d/%m/%Y")

    # Opción 1: Resend API (HTTP — reemplaza SMTP que Railway bloquea)
    resend_key = os.getenv("RESEND_API_KEY", "")
    if resend_key:
        try:
            import httpx as _httpx
            from_addr = os.getenv("RESEND_FROM", "onboarding@resend.dev")
            async with _httpx.AsyncClient(timeout=20) as client:
                resp = await client.post(
                    "https://api.resend.com/emails",
                    headers={"Authorization": f"Bearer {resend_key}",
                             "Content-Type": "application/json"},
                    json={
                        "from": from_addr,
                        "to": [dest_email],
                        "subject": f"📊 Reporte semanal de leads — {fecha_txt}",
                        "text": (
                            f"El reporte semanal de leads está listo.\n"
                            f"Archivo: {os.path.basename(ruta_excel)}\n"
                            f"Fecha: {fecha_txt}"
                        ),
                    },
                )
            if resp.status_code in (200, 201):
                logger.info(f"[REPORTE] ✅ Enviado via Resend a {dest_email}")
                return
            logger.warning(f"[REPORTE] Resend {resp.status_code}: {resp.text[:150]}")
        except Exception as e:
            logger.warning(f"[REPORTE] Error Resend: {e}")

    # Opción 2: WhatsApp a Christian (Drive falla con service accounts)
    try:
        from agent.providers import obtener_proveedor
        christian = os.getenv("CHRISTIAN_NUMERO", "5541576331")
        _prv = obtener_proveedor()
        await _prv.enviar_mensaje(
            christian,
            f"📊 *Reporte semanal generado — {fecha_txt}*\n"
            f"Archivo: `{os.path.basename(ruta_excel)}`\n"
            f"(Para recibir por email: agrega RESEND_API_KEY en Railway Variables)"
        )
        logger.info("[REPORTE] Notificación WhatsApp enviada a Christian")
    except Exception as e:
        logger.error(f"[REPORTE] Error notificación WhatsApp: {e}")


async def iniciar_scheduler_reporte_semanal():
    from agent.reports import generar_reporte_excel

    await asyncio.sleep(segundos_hasta_proximo_domingo_13h())

    while True:
        try:
            logger.info("Generando reporte semanal (domingo 13h)...")
            ruta = await generar_reporte_excel()
            logger.info(f"Reporte guardado en: {ruta}")
            await _enviar_reporte_semanal(ruta)
        except Exception as e:
            logger.error(f"Error en reporte semanal: {e}")

        await asyncio.sleep(7 * 24 * 3600)
