#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Scheduler para generar reportes diarios automáticamente.
Ejecutar: python schedule_reportes.py

O configurar en cron:
  0 6 * * * cd /path/to/agentkit && python schedule_reportes.py
"""

import asyncio
import logging
import schedule
import time
from datetime import datetime
from zoneinfo import ZoneInfo
from reportes_diarios import generar_y_guardar_reportes

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("schedule-reportes")

ZONA_CDMX = ZoneInfo("America/Mexico_City")


def generar_reporte_task():
    """Tarea que se ejecuta según el schedule."""
    logger.info("=" * 70)
    logger.info("  GENERANDO REPORTES DIARIOS")
    logger.info("=" * 70)

    try:
        # Ejecutar el generador de reportes
        asyncio.run(generar_y_guardar_reportes())
        logger.info("✅ Reportes generados exitosamente")
    except Exception as e:
        logger.error(f"❌ Error generando reportes: {e}")


def main():
    """Inicializa el scheduler."""
    logger.info("Scheduler de reportes iniciado")
    logger.info(f"Hora actual (CDMX): {datetime.now(ZONA_CDMX).strftime('%H:%M:%S')}")

    # Programar la tarea para ejecutarse cada día a las 6:00 AM (CDMX)
    schedule.every().day.at("06:00").do(generar_reporte_task)

    logger.info("📅 Reportes programados para: 06:00 AM (CDMX)")
    logger.info("Presiona Ctrl+C para detener")

    # Loop infinito
    while True:
        schedule.run_pending()
        time.sleep(60)  # Verificar cada minuto


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.info("\n⏹ Scheduler detenido")
