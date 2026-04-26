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


async def generar_mensaje_seguimiento(
    historial: list[dict],
    numero_seguimiento: int,
    asesor: str = "Sofia",
) -> str:
    """
    Genera un mensaje de seguimiento personalizado según el historial completo
    de la conversación. Analiza el contexto antes de redactar.
    """
    if not historial:
        fallback = _FALLBACK[min(numero_seguimiento, len(_FALLBACK) - 1)]
        return f"{fallback}\n\n{asesor} — Tecnology Support"

    fragmento = "\n".join(
        f"{'Agente' if m['role'] == 'assistant' else 'Cliente'}: {m['content']}"
        for m in historial[-20:]
    )

    es_ultimo = numero_seguimiento >= 3
    nota_ultimo = "(Es el ÚLTIMO intento — tono de despedida cordial, deja la puerta abierta.)" if es_ultimo else ""

    prompt = f"""Eres {asesor}, asesor de Tecnology Support, un taller de reparación de electrónicos en CDMX.

Un cliente dejó de responder. Lee el historial completo y escribe UN mensaje de seguimiento personalizado.

HISTORIAL:
{fragmento}

SEGUIMIENTO {numero_seguimiento + 1} DE 4. {nota_ultimo}

ANTES DE ESCRIBIR, identifica mentalmente:
- Nombre del cliente (si lo mencionó)
- Dispositivo o equipo que mencionó
- En qué punto quedó: ¿preguntó precio?, ¿dijo que iba a ir?, ¿solo pidió info?
- Qué duda o acción quedó pendiente

ELIGE el escenario que aplica y escribe el mensaje:

Escenario A — Preguntó precio y no respondió:
→ "Hola [nombre], quería saber si te quedó alguna duda sobre el precio del [servicio/dispositivo]. ¿Lo pudiste checar? 😊"

Escenario B — Dijo que iba a ir y no vino:
→ "Hola [nombre], ¿pudiste venir a dejarnos tu [dispositivo]? Si necesitas reagendar, con gusto te ayudo."

Escenario C — Pidió información y desapareció:
→ "Hola [nombre], vi que preguntaste sobre [servicio/dispositivo]. ¿Pudiste resolverlo o todavía lo necesitas?"

Escenario D — Sin contexto claro:
→ "Hola [nombre], hace un rato nos escribiste. ¿Pudimos ayudarte o tienes alguna duda pendiente? 😊"

REGLAS:
- Usa el nombre real del cliente si lo sabes; si no, no pongas placeholder
- Menciona el dispositivo/servicio específico de la conversación
- Máximo 2-3 oraciones. Tono natural, como un mensaje de WhatsApp real
- Sin asteriscos, sin frases corporativas, sin "estimado cliente"
- Máximo 1 emoji
- Firma al final en línea separada: "{asesor} — Tecnology Support"

Escribe SOLO el mensaje final."""

    try:
        response = await client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=200,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.content[0].text.strip()
    except Exception as e:
        logger.error(f"Error generando mensaje de seguimiento: {e}")
        fallback = _FALLBACK[min(numero_seguimiento, len(_FALLBACK) - 1)]
        return f"{fallback}\n\n{asesor} — Tecnology Support"


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
            historial = await obtener_historial(lead.telefono, limite=30)
            asesor = lead.asesor_asignado or "Sofia"
            mensaje = await generar_mensaje_seguimiento(historial, lead.seguimientos_enviados, asesor)
            enviado = await proveedor.enviar_mensaje(lead.telefono, mensaje)
            if enviado:
                await guardar_mensaje(lead.telefono, "assistant", mensaje)
                await registrar_seguimiento_enviado(lead.telefono)
                logger.info(
                    f"Seg {lead.seguimientos_enviados + 1}/{MAX_SEGUIMIENTOS} "
                    f"[{asesor}] → {lead.telefono}: {mensaje[:60]}"
                )
            else:
                logger.warning(f"No se pudo enviar seguimiento a {lead.telefono}")
        except Exception as e:
            logger.error(f"Error procesando seguimiento para {lead.telefono}: {e}")


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
            # Si el cliente ya respondió después de que se programó la retoma, cancelar
            retoma_desde = lead.retoma_desde
            ultimo = lead.ultimo_mensaje
            if retoma_desde and ultimo and ultimo > retoma_desde:
                await cancelar_retoma(lead.telefono)
                logger.info(f"Retoma cancelada (cliente ya respondió): {lead.telefono}")
                continue

            asesor = lead.asesor_asignado or "Sofia"

            historial = await obtener_historial(lead.telefono, limite=10)
            from agent.notifications import extraer_nombre_cliente
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
    from agent.notifications import _enviar_alerta_christian, extraer_nombre_cliente
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
    from agent.notifications import _formatear_numero_destino

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

        enviado = await proveedor.enviar_mensaje(phone_fmt, mensaje)
        if enviado:
            await guardar_mensaje(phone_fmt, "assistant", mensaje)
            await registrar_recordatorio(evento_id, phone_fmt)
            logger.info(f"[RECORDATORIO] ✅ Enviado a {phone_fmt} ({nombre}) — cita a las {hora_txt}")
        else:
            logger.warning(f"[RECORDATORIO] ❌ No se pudo enviar a {phone_fmt}")


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
        from agent.notifications import GRUPO_INTERNO

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


async def iniciar_scheduler():
    """
    Scheduler principal que corre en segundo plano:
    - Seguimientos a leads: cada hora
    - Retomas nocturnas: cada 10 minutos
    - Recordatorios de cita: cada 10 minutos
    - Alertas presupuesto 24h: cada hora
    - Alerta factura fin de mes: diaria
    - Reporte Excel: cada domingo a las 13:00 CDMX
    """
    logger.info("Scheduler activo: seguimientos/hora, retomas/10min, recordatorios/10min, factura/diario, reporte/domingo 13h")

    asyncio.create_task(iniciar_scheduler_reporte_semanal())
    asyncio.create_task(_loop_retomas())
    asyncio.create_task(_loop_recordatorios())
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
            await ejecutar_recordatorios_cita()
        except Exception as e:
            logger.error(f"Error en scheduler de recordatorios: {e}")


async def iniciar_scheduler_reporte_semanal():
    from agent.reports import generar_reporte_excel

    await asyncio.sleep(segundos_hasta_proximo_domingo_13h())

    while True:
        try:
            logger.info("Generando reporte semanal de leads (domingo 13h)...")
            ruta = await generar_reporte_excel()
            logger.info(f"Reporte semanal guardado en: {ruta}")
        except Exception as e:
            logger.error(f"Error generando reporte semanal: {e}")

        await asyncio.sleep(7 * 24 * 3600)
