# agent/main.py — Servidor FastAPI + Webhook de WhatsApp
# Generado por AgentKit

import os
import asyncio
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import PlainTextResponse
from dotenv import load_dotenv

from agent.brain import generar_respuesta
from agent.memory import inicializar_db, guardar_mensaje, obtener_historial
from agent.providers import obtener_proveedor
from agent.leads import crear_o_actualizar_lead, obtener_resumen_leads
from agent.followup import iniciar_scheduler
from agent.reports import generar_reporte_excel
from agent.import_chats import importar_todos_los_chats

load_dotenv()

ENVIRONMENT = os.getenv("ENVIRONMENT", "development")
log_level = logging.DEBUG if ENVIRONMENT == "development" else logging.INFO
logging.basicConfig(level=log_level)
logger = logging.getLogger("agentkit")

proveedor = obtener_proveedor()
PORT = int(os.getenv("PORT", 8000))


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Inicializa DB y arranca el scheduler de seguimientos al iniciar el servidor."""
    # Importar Lead aquí para que SQLAlchemy registre el modelo antes de crear tablas
    from agent.leads import Lead  # noqa: F401
    await inicializar_db()
    logger.info("Base de datos inicializada")
    logger.info(f"Servidor AgentKit corriendo en puerto {PORT}")
    logger.info(f"Proveedor de WhatsApp: {proveedor.__class__.__name__}")

    # Arrancar scheduler de seguimientos en segundo plano
    scheduler_task = asyncio.create_task(iniciar_scheduler())
    yield
    scheduler_task.cancel()


app = FastAPI(
    title="Tecnology Support — WhatsApp AI Agent",
    version="1.0.0",
    lifespan=lifespan
)


@app.get("/")
async def health_check():
    """Endpoint de salud para Railway/monitoreo."""
    return {"status": "ok", "service": "Tecnology Support AgentKit"}


@app.get("/leads")
async def ver_leads():
    """Resumen del estado del funnel de leads."""
    return await obtener_resumen_leads()


@app.post("/reporte")
async def generar_reporte_manual():
    """Genera el reporte Excel de leads manualmente (sin esperar al domingo)."""
    ruta = await generar_reporte_excel()
    return {"status": "ok", "archivo": ruta}


@app.post("/importar-chats")
async def importar_chats_endpoint():
    """Importa y clasifica los chats existentes de Whapi en segundo plano."""
    asyncio.create_task(_importar_y_reportar())
    return {"status": "ok", "mensaje": "Importación iniciada en segundo plano. Revisa los logs."}


async def _importar_y_reportar():
    resumen = await importar_todos_los_chats()
    if resumen["importados"] > 0:
        await generar_reporte_excel()
        logger.info(f"Importación + reporte completados: {resumen}")


@app.get("/webhook")
@app.get("/webhook/messages")
async def webhook_verificacion(request: Request):
    """Verificación GET del webhook."""
    resultado = await proveedor.validar_webhook(request)
    if resultado is not None:
        return PlainTextResponse(str(resultado))
    return {"status": "ok"}


@app.post("/webhook")
@app.post("/webhook/messages")
async def webhook_handler(request: Request):
    """
    Recibe mensajes de WhatsApp via Whapi.cloud.
    Procesa el mensaje, genera respuesta con Claude y la envía de vuelta.
    Registra al cliente como lead para el sistema de seguimiento.
    """
    try:
        # Whapi envía un POST vacío para validar el webhook — responder 200 de inmediato
        body = await request.body()
        if not body or body.strip() in (b"", b"null", b"{}"):
            return {"status": "ok"}

        mensajes = await proveedor.parsear_webhook(request)

        for msg in mensajes:
            if msg.es_propio or not msg.texto:
                continue

            logger.info(f"Mensaje de {msg.telefono}: {msg.texto}")

            # Registrar/actualizar lead con fuente (Facebook Ad si aplica)
            fuente = getattr(msg, "fuente", "desconocido")
            fuente_detalle = getattr(msg, "fuente_detalle", "")
            await crear_o_actualizar_lead(msg.telefono, fuente=fuente, fuente_detalle=fuente_detalle)
            if fuente == "facebook_ad":
                logger.info(f"Lead de Facebook Ad detectado: {msg.telefono} — {fuente_detalle}")

            # Obtener historial ANTES de guardar el mensaje actual
            historial = await obtener_historial(msg.telefono)

            # Mostrar "escribiendo..." mientras Claude genera la respuesta
            await proveedor.enviar_typing(msg.telefono)
            respuesta = await generar_respuesta(msg.texto, historial)

            await guardar_mensaje(msg.telefono, "user", msg.texto)
            await guardar_mensaje(msg.telefono, "assistant", respuesta)

            await proveedor.enviar_mensaje(msg.telefono, respuesta)

            logger.info(f"Respuesta a {msg.telefono}: {respuesta}")

        return {"status": "ok"}

    except Exception as e:
        logger.error(f"Error en webhook: {e}")
        raise HTTPException(status_code=500, detail=str(e))
