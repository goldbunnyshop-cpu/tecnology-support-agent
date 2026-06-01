#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Endpoints de API para reportes de citas.
Integrar en agent/main.py con:
    from agent.reportes_api import setup_reportes_routes
    setup_reportes_routes(app)
"""

import os
import asyncio
from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse
from datetime import datetime
from zoneinfo import ZoneInfo

from reportes_diarios import obtener_reporte_texto_hoy, generar_y_guardar_reportes

ZONA_CDMX = ZoneInfo("America/Mexico_City")


def setup_reportes_routes(app: FastAPI):
    """Registra los endpoints de reportes en la aplicación FastAPI."""

    @app.get("/api/reportes/hoy/texto")
    async def reporte_hoy_texto():
        """Retorna el reporte de hoy en formato texto."""
        try:
            reporte = obtener_reporte_texto_hoy()
            return {
                "status": "ok",
                "fecha": datetime.now(ZONA_CDMX).isoformat(),
                "reporte": reporte
            }
        except Exception as e:
            return {
                "status": "error",
                "mensaje": str(e)
            }

    @app.get("/api/reportes/hoy/html")
    async def reporte_hoy_html():
        """Retorna el reporte de hoy como HTML (descargable)."""
        ruta = "reportes/reporte_hoy.html"
        if os.path.exists(ruta):
            return FileResponse(ruta, media_type="text/html", filename="reporte_hoy.html")
        return JSONResponse(
            {"status": "error", "mensaje": "Reporte no encontrado. Ejecuta: python reportes_diarios.py"},
            status_code=404
        )

    @app.get("/api/reportes/7dias/html")
    async def reporte_7dias_html():
        """Retorna el reporte de 7 días como HTML (descargable)."""
        ruta = "reportes/reporte_7dias.html"
        if os.path.exists(ruta):
            return FileResponse(ruta, media_type="text/html", filename="reporte_7dias.html")
        return JSONResponse(
            {"status": "error", "mensaje": "Reporte no encontrado. Ejecuta: python reportes_diarios.py"},
            status_code=404
        )

    @app.get("/api/reportes/generar")
    async def generar_reportes():
        """Genera los reportes de forma manual (sin bloquear)."""
        try:
            # Ejecutar de forma asíncrona
            await asyncio.to_thread(
                lambda: asyncio.run(generar_y_guardar_reportes())
            )
            return {
                "status": "ok",
                "mensaje": "Reportes generados exitosamente",
                "fecha": datetime.now(ZONA_CDMX).isoformat()
            }
        except Exception as e:
            return {
                "status": "error",
                "mensaje": str(e)
            }

    @app.get("/api/salud")
    async def health_check():
        """Verificación de salud del sistema."""
        return {
            "status": "ok",
            "servicio": "agentkit",
            "timestamp": datetime.now(ZONA_CDMX).isoformat()
        }
