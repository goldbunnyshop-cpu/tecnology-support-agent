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
from agent.memory import (
    inicializar_db, guardar_mensaje, obtener_historial,
    obtener_perfil, guardar_nombre_cliente,
    actualizar_visita_cliente, agregar_dispositivo_cliente,
)
from agent.profile import (
    extraer_nombre_de_mensaje,
    extraer_nombre_de_historial_asistente,
    detectar_dispositivo_en_texto,
    construir_contexto_cliente,
    log_estado_memoria,
)
from agent.providers import obtener_proveedor
from agent.leads import (
    crear_o_actualizar_lead,
    obtener_o_asignar_asesor,
    obtener_resumen_leads,
    programar_retoma,
    cancelar_retoma,
    marcar_presupuesto_enviado,
)
from agent.followup import iniciar_scheduler
from agent.reports import generar_reporte_excel
from agent.import_chats import importar_todos_los_chats
from agent.notifications import (
    procesar_comando_grupo,
    detectar_y_notificar_christian,
    notificar_christian_vision,
    notificar_cita_agendada,
    GRUPO_INTERNO,
)
from agent.google_calendar import (
    detectar_intencion_agendar,
    parsear_fechas_en_texto,
    obtener_slots_disponibles,
    formatear_slots_multiples_para_claude,
    parsear_tag_agendar,
    agendar_cita,
    quitar_tags,
)
from agent.vision import (
    descargar_media,
    descargar_media_por_id,
    analizar_imagen_bytes,
    analizar_thumbnail_b64,
    construir_respuesta_cliente,
)

load_dotenv()

ENVIRONMENT = os.getenv("ENVIRONMENT", "development")
log_level = logging.DEBUG if ENVIRONMENT == "development" else logging.INFO
logging.basicConfig(level=log_level)
logger = logging.getLogger("agentkit")

ZONA_CDMX = ZoneInfo("America/Mexico_City")
proveedor = obtener_proveedor()
PORT = int(os.getenv("PORT", 8080))

_DIAS_ES = {0: "lunes", 1: "martes", 2: "miércoles", 3: "jueves", 4: "viernes", 5: "sábado", 6: "domingo"}
_MESES_ES = {
    1: "enero", 2: "febrero", 3: "marzo", 4: "abril", 5: "mayo", 6: "junio",
    7: "julio", 8: "agosto", 9: "septiembre", 10: "octubre", 11: "noviembre", 12: "diciembre",
}


def _ctx_fecha_cdmx() -> str:
    """Bloque de contexto con fecha y hora actual de CDMX para inyectar en cada respuesta."""
    hoy = datetime.now(ZONA_CDMX)
    man = hoy + timedelta(days=1)
    pas = hoy + timedelta(days=2)
    return (
        f"══ FECHA Y HORA ACTUAL — CDMX ══\n"
        f"Hoy: {_DIAS_ES[hoy.weekday()]} {hoy.day} de {_MESES_ES[hoy.month]} {hoy.year} · {hoy.strftime('%H:%M')}\n"
        f"Mañana: {_DIAS_ES[man.weekday()]} {man.day} de {_MESES_ES[man.month]}\n"
        f"Pasado mañana: {_DIAS_ES[pas.weekday()]} {pas.day} de {_MESES_ES[pas.month]}\n"
        f"NUNCA le preguntes al cliente qué día o fecha es — ya la tienes.\n"
        f"════════════════════════════════════════════════════"
    )

RESPUESTA_IMAGEN_FALLBACK = (
    "Recibí tu imagen \U0001f4f8 En cuanto un especialista la revise te contactamos. "
    "Mientras tanto, ¿puedes describirme qué le pasa a tu equipo?"
)
RESPUESTA_VIDEO_FALLBACK = (
    "Recibí tu video \U0001f3a5 Lo revisaremos con atención. "
    "¿Puedes contarme brevemente qué falla presenta tu equipo mientras lo analizamos?"
)


def cargar_blacklist() -> set[str]:
    try:
        with open("config/blacklist.txt", "r", encoding="utf-8") as f:
            return {l.strip() for l in f if l.strip() and not l.startswith("#")}
    except FileNotFoundError:
        return set()


BLACKLIST: set[str] = cargar_blacklist()


def es_horario_nocturno() -> bool:
    return 0 <= datetime.now(ZONA_CDMX).hour < 6


def calcular_hora_retoma_utc() -> datetime:
    ahora_cdmx = datetime.now(ZONA_CDMX)
    retoma_cdmx = ahora_cdmx + timedelta(hours=8)
    if retoma_cdmx.hour < 9:
        retoma_cdmx = retoma_cdmx.replace(hour=9, minute=0, second=0, microsecond=0)
    return retoma_cdmx.astimezone(timezone.utc).replace(tzinfo=None)


async def manejar_mensaje_nocturno(telefono: str, contenido: str, asesor: str) -> None:
    respuesta = (
        f"Hola, soy {asesor} de Tecnology Support \U0001f60a "
        f"Recibí tu mensaje y con mucho gusto te ayudaré. "
        f"Nuestro equipo retoma atención a partir de las 6:00 AM. "
        f"En cuanto iniciemos operaciones serás atendido con prioridad. "
        f"¡Que descanses!"
    )
    await guardar_mensaje(telefono, "user", contenido)
    await guardar_mensaje(telefono, "assistant", respuesta)
    await proveedor.enviar_mensaje(telefono, respuesta)
    retoma_utc = calcular_hora_retoma_utc()
    await programar_retoma(telefono, retoma_utc, datetime.utcnow())
    logger.info(f"Retoma programada para {telefono} a las {retoma_utc} UTC")


async def _actualizar_perfil_cliente(telefono: str, texto: str, asesor: str):
    """Actualiza visita y detecta dispositivo en background tras cada mensaje."""
    await actualizar_visita_cliente(telefono, asesor)
    dispositivo = detectar_dispositivo_en_texto(texto)
    if dispositivo:
        await agregar_dispositivo_cliente(telefono, dispositivo)


async def _analizar_y_responder_imagen(msg, historial: list, asesor: str) -> str:
    """Descarga la imagen (URL o media_id), la analiza con Vision y responde al cliente."""
    whapi_token = os.getenv("WHAPI_TOKEN", "")
    resultado = None

    logger.info(
        f"[IMG] telefono={msg.telefono} media_url='{(msg.media_url or '')[:60]}' "
        f"media_id='{getattr(msg, 'media_id', '')}' mime='{getattr(msg, 'media_mime_type', '')}'"
    )

    # Intento 1: URL directa del payload
    if msg.media_url and whapi_token:
        resultado = await descargar_media(msg.media_url, whapi_token)

    # Intento 2: fallback por media_id si URL falla o está vacía
    if resultado is None:
        media_id = getattr(msg, "media_id", "")
        mime = getattr(msg, "media_mime_type", "image/jpeg") or "image/jpeg"
        if media_id and whapi_token:
            resultado = await descargar_media_por_id(media_id, whapi_token, mime)
        else:
            logger.warning(f"[IMG] Sin media_url ni media_id para {msg.telefono}")

    if resultado is None:
        return RESPUESTA_IMAGEN_FALLBACK

    imagen_bytes, mime_type = resultado
    analisis = await analizar_imagen_bytes(imagen_bytes, mime_type)

    if not analisis:
        return RESPUESTA_IMAGEN_FALLBACK

    respuesta = construir_respuesta_cliente(analisis, "image", asesor)
    asyncio.create_task(
        notificar_christian_vision(proveedor, msg.telefono, historial, analisis, "image")
    )
    return respuesta


async def _analizar_y_responder_video(msg, historial: list, asesor: str) -> str:
    """Analiza el thumbnail del video con Vision y retorna la respuesta al cliente."""
    analisis = {}

    if msg.media_thumbnail_b64:
        analisis = await analizar_thumbnail_b64(msg.media_thumbnail_b64)
    else:
        logger.info(f"Sin thumbnail para video de {msg.telefono} — usando fallback")

    if not analisis:
        return RESPUESTA_VIDEO_FALLBACK

    respuesta = construir_respuesta_cliente(analisis, "video", asesor)
    asyncio.create_task(
        notificar_christian_vision(proveedor, msg.telefono, historial, analisis, "video")
    )
    return respuesta


@asynccontextmanager
async def lifespan(app: FastAPI):
    from agent.leads import Lead  # noqa: F401
    await inicializar_db()
    logger.info(f"Servidor listo — Puerto: {PORT} | Proveedor: {proveedor.__class__.__name__}")
    scheduler_task = asyncio.create_task(iniciar_scheduler())
    yield
    scheduler_task.cancel()


app = FastAPI(
    title="Tecnology Support — WhatsApp AI Agent",
    version="2.1.0",
    lifespan=lifespan,
)


@app.get("/")
async def health_check():
    return {"status": "ok", "service": "Tecnology Support AgentKit v2.1"}


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
@app.get("/webhook/messages/messages")
async def webhook_verificacion(request: Request):
    resultado = await proveedor.validar_webhook(request)
    if resultado is not None:
        return PlainTextResponse(str(resultado))
    return {"status": "ok"}


@app.post("/webhook")
@app.post("/webhook/messages")
@app.post("/webhook/messages/messages")
async def webhook_handler(request: Request):
    try:
        body = await request.body()
        if not body or body.strip() in (b"", b"null", b"{}"):
            return {"status": "ok"}

        mensajes = await proveedor.parsear_webhook(request)

        for msg in mensajes:
            if msg.es_propio:
                continue

            # ── Grupo interno: procesar comandos de Ulises ──
            if msg.es_grupo:
                nombre_g = getattr(msg, "nombre_grupo", "")
                remitente_g = getattr(msg, "remitente", "")
                logger.info(
                    f"[WEBHOOK] Mensaje de grupo — nombre='{nombre_g}' "
                    f"remitente='{remitente_g}' texto='{(msg.texto or '')[:60]}' "
                    f"es_propio={msg.es_propio}"
                )
                if GRUPO_INTERNO.lower() in nombre_g.lower():
                    logger.info(f"[WEBHOOK] Grupo interno detectado, ejecutando procesar_comando_grupo")
                    await procesar_comando_grupo(
                        msg,
                        proveedor,
                        guardar_mensaje,
                        obtener_historial,
                        marcar_presupuesto_enviado,
                    )
                else:
                    logger.info(
                        f"[WEBHOOK] Grupo ignorado — '{nombre_g}' no coincide con '{GRUPO_INTERNO}'"
                    )
                # Todos los demás grupos se ignoran
                continue

            # ── Blacklist ──
            if msg.telefono in BLACKLIST:
                logger.info(f"Blacklist: {msg.telefono}")
                continue

            # ── Obtener asesor ANTES de actualizar ultimo_mensaje ──
            asesor = await obtener_o_asignar_asesor(msg.telefono)

            # ── Registrar lead ──
            fuente        = getattr(msg, "fuente", "desconocido")
            fuente_detalle = getattr(msg, "fuente_detalle", "")
            await crear_o_actualizar_lead(
                msg.telefono,
                fuente=fuente,
                fuente_detalle=fuente_detalle,
                asesor_asignado=asesor,
            )

            # ── Cancelar retoma si el cliente ya respondió ──
            await cancelar_retoma(msg.telefono)

            # ── Modo nocturno ──
            if es_horario_nocturno():
                contenido = msg.texto or f"[{msg.tipo}]"
                await manejar_mensaje_nocturno(msg.telefono, contenido, asesor)
                continue

            # ── Imagen ──
            if msg.tipo == "image":
                await guardar_mensaje(msg.telefono, "user", "[imagen recibida]")
                await proveedor.enviar_typing(msg.telefono)
                historial_vision = await obtener_historial(msg.telefono)
                respuesta_img = await _analizar_y_responder_imagen(
                    msg, historial_vision, asesor
                )
                await guardar_mensaje(msg.telefono, "assistant", respuesta_img)
                await proveedor.enviar_mensaje(msg.telefono, respuesta_img)
                continue

            # ── Video ──
            if msg.tipo == "video":
                await guardar_mensaje(msg.telefono, "user", "[video recibido]")
                await proveedor.enviar_typing(msg.telefono)
                historial_vision = await obtener_historial(msg.telefono)
                respuesta_vid = await _analizar_y_responder_video(
                    msg, historial_vision, asesor
                )
                await guardar_mensaje(msg.telefono, "assistant", respuesta_vid)
                await proveedor.enviar_mensaje(msg.telefono, respuesta_vid)
                continue

            if not msg.texto:
                continue

            logger.info(f"[{asesor}] {msg.telefono}: {msg.texto[:60]}")

            # ── Cargar perfil del cliente ──
            perfil = await obtener_perfil(msg.telefono)
            log_estado_memoria(msg.telefono, perfil)
            contexto_cliente = construir_contexto_cliente(perfil)

            # ── Detectar nombre si aún no está guardado ──
            if not (perfil and perfil.nombre):
                nombre_detectado = extraer_nombre_de_mensaje(msg.texto)
                if not nombre_detectado:
                    historial_previo = await obtener_historial(msg.telefono)
                    nombre_detectado = extraer_nombre_de_historial_asistente(historial_previo)
                if nombre_detectado:
                    await guardar_nombre_cliente(msg.telefono, nombre_detectado)
                    logger.info(f"Nombre detectado y guardado: {nombre_detectado} ({msg.telefono})")

            # ── Contexto base: fecha CDMX + perfil cliente + teléfono ──
            partes_ctx: list[str] = [_ctx_fecha_cdmx()]
            if contexto_cliente:
                partes_ctx.append(contexto_cliente)
            partes_ctx.append(f"Teléfono del cliente en sistema: {msg.telefono}")

            # ── Disponibilidad real si menciona fecha con intención de visita ──
            if detectar_intencion_agendar(msg.texto):
                fechas_cita = parsear_fechas_en_texto(msg.texto)
                if fechas_cita:
                    dias_slots = []
                    for fc in fechas_cita:
                        slots = await obtener_slots_disponibles(fc)
                        dias_slots.append((fc, slots))
                    partes_ctx.append(formatear_slots_multiples_para_claude(dias_slots))
                    logger.info(f"[CALENDAR] Disponibilidad inyectada para {[str(f) for f in fechas_cita]}")

            contexto_cliente = "\n\n".join(partes_ctx)

            historial = await obtener_historial(msg.telefono)
            await proveedor.enviar_typing(msg.telefono)
            respuesta = await generar_respuesta(
                msg.texto, historial, asesor=asesor, contexto_cliente=contexto_cliente
            )

            # ── Ejecutar cita si Claude incluyó el tag [[AGENDAR:...]] ──
            tag = parsear_tag_agendar(respuesta)
            if tag:
                try:
                    fh = datetime.strptime(
                        f"{tag['fecha_str']} {tag['hora_str']}", "%Y-%m-%d %H:%M"
                    ).replace(tzinfo=ZONA_CDMX)
                    resultado = await agendar_cita(
                        nombre=tag["nombre"],
                        telefono=msg.telefono,
                        dispositivo=tag["dispositivo"],
                        problema=tag["problema"],
                        fecha_hora=fh,
                    )
                    if resultado["ok"]:
                        respuesta = resultado["confirmacion"]
                        asyncio.create_task(
                            notificar_cita_agendada(
                                proveedor=proveedor,
                                nombre=resultado["nombre"],
                                telefono=msg.telefono,
                                dispositivo=resultado["dispositivo"],
                                problema=tag["problema"],
                                fecha_texto=resultado["fecha_texto"],
                                hora_texto=resultado["hora_texto"],
                            )
                        )
                        logger.info(f"[CALENDAR] Cita ejecutada para {msg.telefono} — {resultado['fecha_texto']} {resultado['hora_texto']}")
                    else:
                        respuesta = quitar_tags(respuesta)
                        logger.warning(f"[CALENDAR] Fallo al agendar: {resultado.get('error')}")
                except Exception as e:
                    logger.error(f"[CALENDAR] Error procesando tag AGENDAR: {e}")
                    respuesta = quitar_tags(respuesta)

            await guardar_mensaje(msg.telefono, "user", msg.texto)
            await guardar_mensaje(msg.telefono, "assistant", respuesta)
            await proveedor.enviar_mensaje(msg.telefono, respuesta)

            # ── Actualizar perfil en background ──
            asyncio.create_task(_actualizar_perfil_cliente(msg.telefono, msg.texto, asesor))

            # ── Alertas a Christian (en background, sin bloquear) ──
            asyncio.create_task(
                detectar_y_notificar_christian(
                    msg.texto,
                    historial,
                    msg.telefono,
                    respuesta,
                    proveedor,
                )
            )

            logger.info(f"[{asesor}] → {msg.telefono}: {respuesta[:80]}...")

        return {"status": "ok"}

    except Exception as e:
        logger.error(f"Error en webhook: {e}")
        raise HTTPException(status_code=500, detail=str(e))
