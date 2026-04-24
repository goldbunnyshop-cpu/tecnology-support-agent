# agent/main.py — Servidor FastAPI + Webhook de WhatsApp
# Generado por AgentKit

import os
import asyncio
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import PlainTextResponse
from dotenv import load_dotenv

from agent.brain import generar_respuesta
from agent.memory import inicializar_db, guardar_mensaje, obtener_historial
from agent.providers import obtener_proveedor
from agent.leads import (
    crear_o_actualizar_lead,
    obtener_o_asignar_asesor,
    obtener_resumen_leads,
    programar_retoma,
    cancelar_retoma,
)
from agent.followup import iniciar_scheduler
from agent.reports import generar_reporte_excel
from agent.import_chats import importar_todos_los_chats

load_dotenv()

ENVIRONMENT = os.getenv("ENVIRONMENT", "development")
log_level = logging.DEBUG if ENVIRONMENT == "development" else logging.INFO
logging.basicConfig(level=log_level)
logger = logging.getLogger("agentkit")

ZONA_CDMX = ZoneInfo("America/Mexico_City")
proveedor = obtener_proveedor()
PORT = int(os.getenv("PORT", 8080))

# Respuestas fijas para media
RESPUESTA_IMAGEN = (
    "Recibí tu imagen \U0001f4f8 En cuanto un especialista la revise te contactamos. "
    "Mientras tanto, ¿puedes describirme qué le pasa a tu equipo?"
)
RESPUESTA_VIDEO = (
    "Recibí tu video \U0001f3a5 Lo revisaremos con atención. "
    "¿Puedes contarme brevemente qué falla presenta tu equipo mientras lo analizamos?"
)


def cargar_blacklist() -> set[str]:
    try:
        with open("config/blacklist.txt", "r", encoding="utf-8") as f:
            return {
                line.strip()
                for line in f
                if line.strip() and not line.startswith("#")
            }
    except FileNotFoundError:
        return set()


BLACKLIST: set[str] = cargar_blacklist()


def es_horario_nocturno() -> bool:
    """Retorna True si la hora actual en CDMX está entre 00:00 y 06:00."""
    return 0 <= datetime.now(ZONA_CDMX).hour < 6


def calcular_hora_retoma_utc() -> datetime:
    """
    Calcula en UTC la hora en que debe enviarse la retoma:
    ahora + 8h en CDMX, pero nunca antes de las 9:00 AM CDMX.
    """
    ahora_cdmx = datetime.now(ZONA_CDMX)
    retoma_cdmx = ahora_cdmx + timedelta(hours=8)
    if retoma_cdmx.hour < 9:
        retoma_cdmx = retoma_cdmx.replace(hour=9, minute=0, second=0, microsecond=0)
    return retoma_cdmx.astimezone(timezone.utc).replace(tzinfo=None)


async def manejar_mensaje_nocturno(telefono: str, texto_o_tipo: str, asesor: str) -> None:
    """Envía la respuesta de fuera de horario y programa la retoma."""
    respuesta = (
        f"Hola, soy {asesor} de Tecnology Support \U0001f60a "
        f"Recibí tu mensaje y con mucho gusto te ayudaré. "
        f"Nuestro equipo retoma atención a partir de las 6:00 AM. "
        f"En cuanto iniciemos operaciones serás atendido con prioridad. "
        f"¡Que descanses!"
    )
    await guardar_mensaje(telefono, "user", texto_o_tipo)
    await guardar_mensaje(telefono, "assistant", respuesta)
    await proveedor.enviar_mensaje(telefono, respuesta)

    ahora_utc = datetime.utcnow()
    retoma_utc = calcular_hora_retoma_utc()
    await programar_retoma(telefono, retoma_utc, ahora_utc)
    logger.info(f"Retoma programada para {telefono} a las {retoma_utc} UTC")


@asynccontextmanager
async def lifespan(app: FastAPI):
    from agent.leads import Lead  # noqa: F401
    await inicializar_db()
    logger.info("Base de datos inicializada")
    logger.info(f"Puerto: {PORT} | Proveedor: {proveedor.__class__.__name__}")
    scheduler_task = asyncio.create_task(iniciar_scheduler())
    yield
    scheduler_task.cancel()


app = FastAPI(
    title="Tecnology Support — WhatsApp AI Agent",
    version="2.0.0",
    lifespan=lifespan,
)


@app.get("/")
async def health_check():
    return {"status": "ok", "service": "Tecnology Support AgentKit"}


@app.get("/leads")
async def ver_leads():
    return await obtener_resumen_leads()


@app.post("/reporte")
async def generar_reporte_manual():
    ruta = await generar_reporte_excel()
    return {"status": "ok", "archivo": ruta}


@app.post("/importar-chats")
async def importar_chats_endpoint():
    asyncio.create_task(_importar_y_reportar())
    return {"status": "ok", "mensaje": "Importacion iniciada en segundo plano."}


async def _importar_y_reportar():
    resumen = await importar_todos_los_chats()
    if resumen["importados"] > 0:
        await generar_reporte_excel()
        logger.info(f"Importacion + reporte completados: {resumen}")


@app.get("/webhook")
@app.get("/webhook/messages")
async def webhook_verificacion(request: Request):
    resultado = await proveedor.validar_webhook(request)
    if resultado is not None:
        return PlainTextResponse(str(resultado))
    return {"status": "ok"}


@app.post("/webhook")
@app.post("/webhook/messages")
async def webhook_handler(request: Request):
    try:
        body = await request.body()
        if not body or body.strip() in (b"", b"null", b"{}"):
            return {"status": "ok"}

        mensajes = await proveedor.parsear_webhook(request)

        for msg in mensajes:
            # Ignorar mensajes propios
            if msg.es_propio:
                continue

            # Ignorar grupos
            if msg.es_grupo:
                logger.debug(f"Mensaje de grupo ignorado: {msg.telefono}")
                continue

            # Ignorar números en blacklist
            if msg.telefono in BLACKLIST:
                logger.info(f"Número en blacklist ignorado: {msg.telefono}")
                continue

            # Obtener asesor ANTES de actualizar ultimo_mensaje (para detectar 72h correctamente)
            asesor = await obtener_o_asignar_asesor(msg.telefono)

            # Registrar/actualizar lead
            fuente = getattr(msg, "fuente", "desconocido")
            fuente_detalle = getattr(msg, "fuente_detalle", "")
            await crear_o_actualizar_lead(
                msg.telefono,
                fuente=fuente,
                fuente_detalle=fuente_detalle,
                asesor_asignado=asesor,
            )

            # Si el cliente responde, cancelar cualquier retoma pendiente
            await cancelar_retoma(msg.telefono)

            # Modo nocturno: 00:00 – 06:00 CDMX
            if es_horario_nocturno():
                contenido = msg.texto or f"[{msg.tipo}]"
                await manejar_mensaje_nocturno(msg.telefono, contenido, asesor)
                continue

            # Manejar imágenes
            if msg.tipo == "image":
                await guardar_mensaje(msg.telefono, "user", "[imagen recibida]")
                await guardar_mensaje(msg.telefono, "assistant", RESPUESTA_IMAGEN)
                await proveedor.enviar_mensaje(msg.telefono, RESPUESTA_IMAGEN)
                logger.info(f"Imagen recibida de {msg.telefono}")
                continue

            # Manejar videos
            if msg.tipo == "video":
                await guardar_mensaje(msg.telefono, "user", "[video recibido]")
                await guardar_mensaje(msg.telefono, "assistant", RESPUESTA_VIDEO)
                await proveedor.enviar_mensaje(msg.telefono, RESPUESTA_VIDEO)
                logger.info(f"Video recibido de {msg.telefono}")
                continue

            # Solo procesar texto
            if not msg.texto:
                continue

            logger.info(f"[{asesor}] Mensaje de {msg.telefono}: {msg.texto}")

            historial = await obtener_historial(msg.telefono)
            await proveedor.enviar_typing(msg.telefono)
            respuesta = await generar_respuesta(msg.texto, historial, asesor=asesor)

            await guardar_mensaje(msg.telefono, "user", msg.texto)
            await guardar_mensaje(msg.telefono, "assistant", respuesta)
            await proveedor.enviar_mensaje(msg.telefono, respuesta)

            logger.info(f"[{asesor}] Respuesta a {msg.telefono}: {respuesta[:80]}...")

        return {"status": "ok"}

    except Exception as e:
        logger.error(f"Error en webhook: {e}")
        raise HTTPException(status_code=500, detail=str(e))
