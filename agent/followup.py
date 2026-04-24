# agent/followup.py — Scheduler de seguimiento automático a leads
# Generado por AgentKit

import asyncio
import logging
import os
from datetime import datetime, timezone
from anthropic import AsyncAnthropic
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger("agentkit")
client = AsyncAnthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

# Intervalo de revisión: cada hora
INTERVALO_SEGUNDOS = 3600

# Mensajes de respaldo si Claude falla
MENSAJES_FALLBACK = [
    "Hola, ¿pudo resolver lo de su equipo? Aquí seguimos para ayudarle cuando guste.",
    "Buenas, queríamos saber si sigue con la duda sobre su dispositivo. En Tecnology Support estamos listos.",
    "Hola, este es nuestro último mensaje. Cuando necesite apoyo con su equipo, aquí estaremos. ¡Buen día!",
]


async def generar_mensaje_seguimiento(historial: list[dict], numero_seguimiento: int) -> str:
    """
    Genera un mensaje de seguimiento personalizado con Claude,
    basado en el historial real de la conversación.
    """
    if not historial:
        return MENSAJES_FALLBACK[min(numero_seguimiento, 2)]

    # Tomar los últimos 8 mensajes para tener contexto suficiente
    contexto = "\n".join(
        f"{'Cliente' if m['role'] == 'user' else 'Agente'}: {m['content']}"
        for m in historial[-8:]
    )

    prompt = f"""Eres el asistente de Tecnology Support, un taller de reparación de dispositivos electrónicos.

Un cliente inició una conversación pero dejó de responder. Este es el historial:

{contexto}

---
Redacta UN mensaje de seguimiento corto (máximo 2 oraciones) para retomar el contacto.
Reglas:
- Si conoces el nombre del cliente, úsalo
- Menciona el dispositivo o problema que comentó si lo hay
- Tono amable, sin presión, profesional
- Termina con una pregunta abierta o invitación suave a regresar
- Sin emojis
- Es el seguimiento número {numero_seguimiento + 1} de 3
- Si es el seguimiento 3, el tono es de despedida cordial dejando la puerta abierta
Solo escribe el mensaje, sin explicaciones."""

    try:
        response = await client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=120,
            messages=[{"role": "user", "content": prompt}]
        )
        return response.content[0].text.strip()
    except Exception as e:
        logger.error(f"Error generando mensaje de seguimiento: {e}")
        return MENSAJES_FALLBACK[min(numero_seguimiento, 2)]


async def ejecutar_seguimientos():
    """
    Revisa todos los leads sin actividad y envía mensajes de seguimiento.
    Se ejecuta cada hora desde el scheduler.
    """
    from agent.leads import obtener_leads_para_seguimiento, registrar_seguimiento_enviado
    from agent.memory import obtener_historial, guardar_mensaje
    from agent.providers import obtener_proveedor

    proveedor = obtener_proveedor()
    leads = await obtener_leads_para_seguimiento(horas_sin_respuesta=24)

    if not leads:
        return

    logger.info(f"Seguimiento automático: {len(leads)} leads sin actividad")

    for lead in leads:
        try:
            historial = await obtener_historial(lead.telefono)
            mensaje = await generar_mensaje_seguimiento(historial, lead.seguimientos_enviados)

            enviado = await proveedor.enviar_mensaje(lead.telefono, mensaje)

            if enviado:
                # Guardar el seguimiento en el historial de la conversación
                await guardar_mensaje(lead.telefono, "assistant", mensaje)
                await registrar_seguimiento_enviado(lead.telefono)
                logger.info(
                    f"Seguimiento {lead.seguimientos_enviados + 1}/3 → {lead.telefono}"
                )
            else:
                logger.warning(f"No se pudo enviar seguimiento a {lead.telefono}")

        except Exception as e:
            logger.error(f"Error procesando seguimiento para {lead.telefono}: {e}")


def segundos_hasta_proximo_domingo_13h() -> float:
    """Calcula los segundos que faltan para el próximo domingo a las 13:00 hora México."""
    from zoneinfo import ZoneInfo
    from datetime import timedelta
    ZONA = ZoneInfo("America/Mexico_City")
    ahora = datetime.now(ZONA)
    dias_hasta_domingo = (6 - ahora.weekday()) % 7
    # Si hoy es domingo pero ya pasó la 1pm, ir al siguiente domingo
    if dias_hasta_domingo == 0 and (ahora.hour > 13 or (ahora.hour == 13 and ahora.minute > 0)):
        dias_hasta_domingo = 7
    proximo = ahora.replace(hour=13, minute=0, second=0, microsecond=0)
    proximo += timedelta(days=dias_hasta_domingo)
    segundos = (proximo - ahora).total_seconds()
    logger.info(f"Próximo reporte semanal: {proximo.strftime('%A %d/%m/%Y a las %H:%M')} ({segundos / 3600:.1f}h)")
    return segundos


async def iniciar_scheduler():
    """
    Loop de fondo que:
    - Ejecuta seguimientos a clientes cada hora
    - Genera el reporte Excel cada domingo a las 13:00 hora México
    Se arranca desde el lifespan de FastAPI.
    """
    logger.info(f"Scheduler de seguimientos activo — revisión cada {INTERVALO_SEGUNDOS // 60} minutos")

    # Lanzar el scheduler del reporte semanal en paralelo
    asyncio.create_task(iniciar_scheduler_reporte_semanal())

    while True:
        await asyncio.sleep(INTERVALO_SEGUNDOS)
        try:
            await ejecutar_seguimientos()
        except Exception as e:
            logger.error(f"Error en scheduler de seguimientos: {e}")


async def iniciar_scheduler_reporte_semanal():
    """
    Loop independiente que genera el reporte Excel cada domingo a las 13:00 (hora México).
    El primer ciclo duerme hasta el próximo domingo a las 13h,
    luego se repite cada 7 días exactos.
    """
    from agent.reports import generar_reporte_excel

    # Esperar hasta el próximo domingo a las 13:00
    await asyncio.sleep(segundos_hasta_proximo_domingo_13h())

    while True:
        try:
            logger.info("Generando reporte semanal de leads (domingo 13h)...")
            ruta = await generar_reporte_excel()
            logger.info(f"Reporte semanal guardado en: {ruta}")
        except Exception as e:
            logger.error(f"Error generando reporte semanal: {e}")

        # Esperar exactamente 7 días hasta el próximo domingo
        await asyncio.sleep(7 * 24 * 3600)
