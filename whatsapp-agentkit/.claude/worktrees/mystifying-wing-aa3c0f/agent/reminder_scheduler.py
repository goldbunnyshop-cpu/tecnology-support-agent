"""
Scheduler de Recordatorios Inteligentes
═══════════════════════════════════════════════════════════

Maneja la programación en tiempo real de los recordatorios de citas.
Usa APScheduler para ejecutar tareas en momentos precisos.
"""

import os
import logging
from datetime import datetime, timedelta
from typing import Optional, Callable
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.date import DateTrigger

from agent.smart_reminders import ReminderSchedule

logger = logging.getLogger("agentkit.reminder_scheduler")

# Instancia global del scheduler (se inicializa en main.py)
scheduler: Optional[AsyncIOScheduler] = None


async def inicializar_scheduler(app=None) -> AsyncIOScheduler:
    """Inicializa el scheduler de APScheduler."""
    global scheduler

    if scheduler is not None:
        return scheduler

    scheduler = AsyncIOScheduler()
    scheduler.start()
    logger.info("Reminder Scheduler inicializado")

    return scheduler


async def programar_recordatorios_cita(
    telefono: str,
    fecha_cita: str,
    hora_cita: str,
    nombre_cliente: str,
    callback_enviar_mensaje: Callable,
    fecha_confirmacion: Optional[datetime] = None
) -> dict:
    """
    Programa los recordatorios inteligentes para una cita confirmada.

    Args:
        telefono: Número de teléfono del cliente
        fecha_cita: Fecha formato YYYY-MM-DD
        hora_cita: Hora formato HH:MM
        nombre_cliente: Nombre del cliente (para logs)
        callback_enviar_mensaje: Función async para enviar mensaje
            Signature: async def enviar_mensaje(telefono: str, mensaje: str) -> bool
        fecha_confirmacion: Cuándo se confirmó (default: ahora)

    Returns:
        {
            "exito": bool,
            "recordatorios_programados": list,
            "proxima_accion": datetime,
            "detalle": str
        }
    """

    if scheduler is None:
        logger.error("Scheduler no inicializado")
        return {
            "exito": False,
            "recordatorios_programados": [],
            "detalle": "Scheduler no inicializado"
        }

    # Generar plan inteligente
    schedule = ReminderSchedule(fecha_cita, hora_cita, fecha_confirmacion)
    plan = schedule.obtener_schedule_reminders()

    recordatorios_programados = []

    # Programar cada recordatorio
    for recordatorio in plan["recordatorios"]:
        if not recordatorio["enviar"]:
            logger.info(f"[{nombre_cliente}] Saltando recordatorio {recordatorio['tipo']}")
            continue

        dt_recordatorio = recordatorio["datetime"]
        tipo = recordatorio["tipo"]
        mensaje = recordatorio["mensajes"]["body"]

        try:
            # Crear job ID único
            job_id = f"reminder_{telefono}_{tipo}_{int(dt_recordatorio.timestamp())}"

            # Función wrapper que captura los parámetros
            async def enviar_recordatorio(tel=telefono, msg=mensaje, t=tipo):
                logger.info(f"Enviando recordatorio {t} a {tel}")
                await callback_enviar_mensaje(tel, msg)

            # Programar en APScheduler
            job = scheduler.add_job(
                enviar_recordatorio,
                trigger=DateTrigger(run_date=dt_recordatorio),
                id=job_id,
                replace_existing=True,
                timezone="America/Mexico_City"  # O la zona del usuario
            )

            recordatorios_programados.append({
                "tipo": tipo,
                "datetime": dt_recordatorio,
                "job_id": job_id,
                "mensaje": mensaje
            })

            logger.info(
                f"[{nombre_cliente}] Recordatorio {tipo} programado para "
                f"{dt_recordatorio.strftime('%Y-%m-%d %H:%M:%S')}"
            )

        except Exception as e:
            logger.error(f"Error programando recordatorio {tipo}: {e}")

    detalle = (
        f"Programados {len(recordatorios_programados)} recordatorios para "
        f"{nombre_cliente} (cita {fecha_cita} {hora_cita})"
    )

    return {
        "exito": len(recordatorios_programados) > 0,
        "recordatorios_programados": recordatorios_programados,
        "proxima_accion": plan["proxima_accion"],
        "detalle": detalle
    }


async def cancelar_recordatorios_cita(telefono: str, fecha_cita: str) -> dict:
    """
    Cancela todos los recordatorios programados para una cita.
    Útil si el cliente cancela o reprograma la cita.

    Args:
        telefono: Número del cliente
        fecha_cita: Fecha de la cita original

    Returns:
        {"exito": bool, "cancelados": int}
    """

    if scheduler is None:
        return {"exito": False, "cancelados": 0}

    cancelados = 0
    job_ids_a_cancelar = [
        job.id for job in scheduler.get_jobs()
        if telefono in job.id and fecha_cita in job.id
    ]

    for job_id in job_ids_a_cancelar:
        try:
            scheduler.remove_job(job_id)
            cancelados += 1
            logger.info(f"Recordatorio cancelado: {job_id}")
        except Exception as e:
            logger.error(f"Error cancelando {job_id}: {e}")

    return {"exito": cancelados > 0, "cancelados": cancelados}


def obtener_recordatorios_pendientes(telefono: Optional[str] = None) -> list:
    """
    Retorna los recordatorios pendientes (programados pero no ejecutados).

    Args:
        telefono: Si se proporciona, filtra solo para este cliente

    Returns:
        Lista de recordatorios pendientes con timing
    """

    if scheduler is None:
        return []

    recordatorios = []

    for job in scheduler.get_jobs():
        # Filtrar por teléfono si se proporciona
        if telefono and telefono not in job.id:
            continue

        # Si es un job de reminder
        if "reminder_" in job.id:
            recordatorios.append({
                "job_id": job.id,
                "proximamente": str(job.next_run_time),
                "segundos_hasta": (job.next_run_time - datetime.now()).total_seconds()
            })

    return sorted(recordatorios, key=lambda x: x["segundos_hasta"])


# ════════════════════════════════════════════════════════════
# Funciones helper para integración con cita_detector
# ════════════════════════════════════════════════════════════

async def manejar_cita_confirmada(
    telefono: str,
    fecha_cita: str,
    hora_cita: str,
    nombre_cliente: str,
    proveedor_whatsapp = None
) -> None:
    """
    Se llama cuando una cita es CONFIRMADA.

    Encadena:
    1. Agregar a Google Calendar (ya existe)
    2. Programar recordatorios inteligentes
    3. Enviar confirmación al cliente

    Args:
        telefono: Número cliente
        fecha_cita: Formato YYYY-MM-DD
        hora_cita: Formato HH:MM
        nombre_cliente: Nombre para logs
        proveedor_whatsapp: Instancia del proveedor para enviar mensajes
    """

    logger.info(f"Manejando cita confirmada: {nombre_cliente} ({telefono})")

    # Callback para enviar mensajes
    async def enviar_recordatorio_callback(tel: str, msg: str):
        if proveedor_whatsapp:
            await proveedor_whatsapp.enviar_mensaje(tel, msg)
        else:
            logger.warning(f"No hay proveedor — mensaje no enviado: {msg}")

    # Programar recordatorios
    resultado = await programar_recordatorios_cita(
        telefono=telefono,
        fecha_cita=fecha_cita,
        hora_cita=hora_cita,
        nombre_cliente=nombre_cliente,
        callback_enviar_mensaje=enviar_recordatorio_callback,
        fecha_confirmacion=datetime.now()
    )

    if resultado["exito"]:
        logger.info(f"✅ {resultado['detalle']}")
        # Enviar confirmación al cliente
        if proveedor_whatsapp:
            msg_confirmacion = (
                f"✅ Cita confirmada para el {fecha_cita} a las {hora_cita}\n\n"
                f"Te enviaremos recordatorios antes de tu cita."
            )
            await proveedor_whatsapp.enviar_mensaje(telefono, msg_confirmacion)
    else:
        logger.error(f"❌ Error programando recordatorios: {resultado['detalle']}")
