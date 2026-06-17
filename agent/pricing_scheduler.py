# agent/pricing_scheduler.py — Tareas programadas para actualización de precios
# Updates diarios: 2 PM y 8 PM | Consultas diarias: 3 veces

import os
import logging
import asyncio
from typing import List, Optional
from datetime import datetime, time
from pytz import timezone as tz_from_pytz
from zoneinfo import ZoneInfo
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

# Importar cotizador cuando esté disponible
# from agent.pricing import obtener_cotizador

logger = logging.getLogger("agentkit")

ZONA_MEXICO = ZoneInfo("America/Mexico_City")
ZONA_PYTZ = tz_from_pytz("America/Mexico_City")


class PricingScheduler:
    """Orquestador de tareas programadas para actualización de precios"""

    def __init__(self):
        self.scheduler = AsyncIOScheduler(timezone=ZONA_PYTZ)
        self.cotizador = None
        self.ultima_actualizacion_hugo = None
        self.consultas_dia_actual = 0
        self.fecha_consultas = None

    async def inicializar(self):
        """Inicializa el scheduler con todas las tareas"""
        logger.info("Inicializando PricingScheduler...")

        try:
            # Importar aquí para evitar circular imports
            # from agent.pricing import obtener_cotizador
            # self.cotizador = await obtener_cotizador()

            # ── TAREA 1: Actualización Hugo Shop - 2 PM ──
            self.scheduler.add_job(
                self.actualizar_hugo_2pm,
                CronTrigger(hour=14, minute=0, timezone=ZONA_PYTZ),
                id="hugo_shop_2pm",
                name="Actualizar Hugo Shop (2 PM)",
                replace_existing=True,
                misfire_grace_time=300,  # 5 minutos de gracia
            )
            logger.info("✓ Tarea registrada: Actualizar Hugo Shop a las 2 PM")

            # ── TAREA 2: Actualización Hugo Shop - 8 PM ──
            self.scheduler.add_job(
                self.actualizar_hugo_8pm,
                CronTrigger(hour=20, minute=0, timezone=ZONA_PYTZ),
                id="hugo_shop_8pm",
                name="Actualizar Hugo Shop (8 PM)",
                replace_existing=True,
                misfire_grace_time=300,
            )
            logger.info("✓ Tarea registrada: Actualizar Hugo Shop a las 8 PM")

            # ── TAREA 3: Consultas diarias - 11 AM ──
            self.scheduler.add_job(
                self.consulta_diaria_11am,
                CronTrigger(hour=11, minute=0, timezone=ZONA_PYTZ),
                id="consulta_11am",
                name="Consulta diaria (11 AM)",
                replace_existing=True,
                misfire_grace_time=300,
            )
            logger.info("✓ Tarea registrada: Consulta diaria a las 11 AM")

            # ── TAREA 4: Consultas diarias - 2 PM (secundaria) ──
            self.scheduler.add_job(
                self.consulta_diaria_2pm,
                CronTrigger(hour=14, minute=30, timezone=ZONA_PYTZ),  # 2:30 PM para evitar overlap
                id="consulta_2pm",
                name="Consulta diaria (2 PM)",
                replace_existing=True,
                misfire_grace_time=300,
            )
            logger.info("✓ Tarea registrada: Consulta diaria a las 2:30 PM")

            # ── TAREA 5: Consultas diarias - 8 PM (tercera) ──
            self.scheduler.add_job(
                self.consulta_diaria_8pm,
                CronTrigger(hour=20, minute=30, timezone=ZONA_PYTZ),  # 8:30 PM para evitar overlap
                id="consulta_8pm",
                name="Consulta diaria (8 PM)",
                replace_existing=True,
                misfire_grace_time=300,
            )
            logger.info("✓ Tarea registrada: Consulta diaria a las 8:30 PM")

            # ── TAREA 6: Reset de contador diario @ medianoche ──
            self.scheduler.add_job(
                self.resetear_contador_diario,
                CronTrigger(hour=0, minute=0, timezone=ZONA_PYTZ),
                id="reset_daily",
                name="Reset contador diario",
                replace_existing=True,
            )
            logger.info("✓ Tarea registrada: Reset contador a medianoche")

            # ── TAREA 7: Refrescar catálogo de precios desde Google Sheets (3 AM) ──
            # Descarga las 3 hojas (DISPLAYS, BATERÍAS ANDROID, BATERÍAS iPHONE) y
            # persiste en SQLite. Así el catálogo siempre tiene precios del día
            # sin depender de que la laptop del operador esté encendida.
            self.scheduler.add_job(
                self.refrescar_catalogo_sheets,
                CronTrigger(hour=3, minute=0, timezone=ZONA_PYTZ),
                id="catalogo_sheets_3am",
                name="Refrescar catálogo Google Sheets (3 AM)",
                replace_existing=True,
                misfire_grace_time=600,  # 10 min de gracia
            )
            logger.info("✓ Tarea registrada: Refrescar catálogo Sheets a las 3 AM")

            if not self.scheduler.running:
                self.scheduler.start()
                logger.info("✓ AsyncIOScheduler iniciado")

        except Exception as e:
            logger.error(f"Error inicializando PricingScheduler: {e}")

    async def detener(self):
        """Detiene el scheduler"""
        if self.scheduler.running:
            self.scheduler.shutdown()
            logger.info("PricingScheduler detenido")

    # ====================================================================
    # TAREAS: ACTUALIZACIÓN DE PRECIOS
    # ====================================================================

    async def refrescar_catalogo_sheets(self):
        """Tarea diaria (3 AM): descarga las 3 hojas de Sheets y persiste en SQLite."""
        hora = datetime.now(ZONA_MEXICO).strftime("%H:%M:%S")
        logger.info(f"[SCHEDULER] Refrescando catálogo Google Sheets @ {hora}")
        try:
            from agent.pricing_sheets import recargar_catalogo_forzado
            catalogo = await recargar_catalogo_forzado()
            total = sum(len(v) for v in catalogo.values())
            logger.info(f"[SCHEDULER] ✅ Catálogo actualizado — {total} productos")
        except Exception as e:
            logger.error(f"[SCHEDULER] ❌ Error refrescando catálogo: {e}")

    async def actualizar_hugo_2pm(self):
        """Tarea programada: Actualizar Hugo Shop a las 2 PM"""
        hora_actual = datetime.now(ZONA_MEXICO).strftime("%H:%M:%S")
        logger.info(f"[SCHEDULER] Iniciando actualización Hugo Shop (2 PM) @ {hora_actual}")

        try:
            # if self.cotizador:
            #     exito = await self.cotizador.actualizar_hugo_shop()
            #     if exito:
            #         self.ultima_actualizacion_hugo = datetime.now(ZONA_MEXICO)
            #         logger.info("[SCHEDULER] ✓ Hugo Shop actualizado exitosamente")
            #         await self._notificar_actualizacion("2 PM")
            #     else:
            #         logger.error("[SCHEDULER] ✗ Error actualizando Hugo Shop")
            # else:
            logger.warning("[SCHEDULER] Cotizador no inicializado")

        except Exception as e:
            logger.error(f"[SCHEDULER] Error en actualización 2 PM: {e}")

    async def actualizar_hugo_8pm(self):
        """Tarea programada: Actualizar Hugo Shop a las 8 PM"""
        hora_actual = datetime.now(ZONA_MEXICO).strftime("%H:%M:%S")
        logger.info(f"[SCHEDULER] Iniciando actualización Hugo Shop (8 PM) @ {hora_actual}")

        try:
            # if self.cotizador:
            #     exito = await self.cotizador.actualizar_hugo_shop()
            #     if exito:
            #         self.ultima_actualizacion_hugo = datetime.now(ZONA_MEXICO)
            #         logger.info("[SCHEDULER] ✓ Hugo Shop actualizado exitosamente")
            #         await self._notificar_actualizacion("8 PM")
            #     else:
            #         logger.error("[SCHEDULER] ✗ Error actualizando Hugo Shop")
            # else:
            logger.warning("[SCHEDULER] Cotizador no inicializado")

        except Exception as e:
            logger.error(f"[SCHEDULER] Error en actualización 8 PM: {e}")

    # ====================================================================
    # TAREAS: CONSULTAS DIARIAS (3 veces)
    # ====================================================================

    async def consulta_diaria_11am(self):
        """Tarea programada: Consulta diaria #1 a las 11 AM"""
        hora_actual = datetime.now(ZONA_MEXICO).strftime("%H:%M:%S")
        logger.info(f"[SCHEDULER] Consulta diaria #1 (11 AM) @ {hora_actual}")

        self.consultas_dia_actual += 1
        self.fecha_consultas = datetime.now(ZONA_MEXICO).date()

        try:
            await self._procesar_consulta_diaria(1)
        except Exception as e:
            logger.error(f"[SCHEDULER] Error en consulta 11 AM: {e}")

    async def consulta_diaria_2pm(self):
        """Tarea programada: Consulta diaria #2 a las 2:30 PM"""
        hora_actual = datetime.now(ZONA_MEXICO).strftime("%H:%M:%S")
        logger.info(f"[SCHEDULER] Consulta diaria #2 (2:30 PM) @ {hora_actual}")

        self.consultas_dia_actual += 1

        try:
            await self._procesar_consulta_diaria(2)
        except Exception as e:
            logger.error(f"[SCHEDULER] Error en consulta 2 PM: {e}")

    async def consulta_diaria_8pm(self):
        """Tarea programada: Consulta diaria #3 a las 8:30 PM"""
        hora_actual = datetime.now(ZONA_MEXICO).strftime("%H:%M:%S")
        logger.info(f"[SCHEDULER] Consulta diaria #3 (8:30 PM) @ {hora_actual}")

        self.consultas_dia_actual += 1

        try:
            await self._procesar_consulta_diaria(3)
        except Exception as e:
            logger.error(f"[SCHEDULER] Error en consulta 8 PM: {e}")

    async def _procesar_consulta_diaria(self, numero_consulta: int):
        """Lógica común para procesar consultas diarias"""
        logger.info(f"[SCHEDULER] Procesando consulta #{numero_consulta} del día")

        # Aquí iría la lógica de consulta real:
        # - Verificar inventario
        # - Actualizar precios si es necesario
        # - Notificar si hay cambios significativos
        # - Validar consistencia de datos

        await asyncio.sleep(1)  # Placeholder
        logger.info(f"[SCHEDULER] ✓ Consulta #{numero_consulta} completada")

    async def resetear_contador_diario(self):
        """Tarea programada: Reset de contador a medianoche"""
        logger.info("[SCHEDULER] Reset de contador de consultas diarias")
        self.consultas_dia_actual = 0
        self.fecha_consultas = None

    # ====================================================================
    # HELPERS Y NOTIFICACIONES
    # ====================================================================

    async def _notificar_actualizacion(self, hora: str):
        """Notifica al grupo interno sobre actualización de precios"""
        try:
            # Aquí se integraría con agent.notifications
            # from agent.notifications import enviar_notificacion_grupo
            # await enviar_notificacion_grupo(f"✓ Precios actualizados a las {hora}")
            logger.info(f"[SCHEDULER] Notificación: Precios actualizados a las {hora}")
        except Exception as e:
            logger.error(f"Error notificando actualización: {e}")

    def obtener_estado(self) -> dict:
        """Retorna estado actual del scheduler"""
        return {
            "running": self.scheduler.running,
            "ultima_actualizacion_hugo": self.ultima_actualizacion_hugo.isoformat() if self.ultima_actualizacion_hugo else None,
            "consultas_hoy": self.consultas_dia_actual,
            "fecha": self.fecha_consultas.isoformat() if self.fecha_consultas else None,
            "tareas_activas": len(self.scheduler.get_jobs()),
        }

    def listar_tareas(self) -> List[dict]:
        """Lista todas las tareas programadas"""
        tareas = []
        for job in self.scheduler.get_jobs():
            tareas.append({
                "id": job.id,
                "name": job.name,
                "next_run_time": job.next_run_time.isoformat() if job.next_run_time else None,
                "trigger": str(job.trigger),
            })
        return tareas


# ====================================================================
# INSTANCIA GLOBAL Y FUNCIONES DE MÓDULO
# ====================================================================

_scheduler_instance: Optional[PricingScheduler] = None


async def inicializar_pricing_scheduler() -> PricingScheduler:
    """Factory para inicializar el scheduler global"""
    global _scheduler_instance
    if _scheduler_instance is None:
        _scheduler_instance = PricingScheduler()
        await _scheduler_instance.inicializar()
    return _scheduler_instance


async def obtener_pricing_scheduler() -> PricingScheduler:
    """Obtiene la instancia global del scheduler"""
    global _scheduler_instance
    if _scheduler_instance is None:
        await inicializar_pricing_scheduler()
    return _scheduler_instance


# Para importar en main.py:
# from agent.pricing_scheduler import inicializar_pricing_scheduler, obtener_pricing_scheduler
