# agent/main.py — Servidor FastAPI + Webhook de WhatsApp
# Generado por AgentKit

import os
import asyncio
import logging
import pytz
import re
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone, date
from zoneinfo import ZoneInfo

from typing import Optional, List

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import PlainTextResponse, JSONResponse
from pydantic import BaseModel
from sqlalchemy import select
from dotenv import load_dotenv

from agent.brain import generar_respuesta
from agent.memory import (
    inicializar_db, guardar_mensaje, obtener_historial,
    obtener_perfil, guardar_nombre_cliente,
    actualizar_visita_cliente, agregar_dispositivo_cliente,
    pausar_conversacion, esta_pausada,
    mensaje_ya_procesado, marcar_mensaje_procesado,
    confirmacion_cita_ya_enviada, marcar_confirmacion_cita_enviada,
    Mensaje, async_session,
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
    obtener_todos_los_leads_detalle,
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
    agendar_cita,
    obtener_citas_hoy_formateadas,
    UBICACION_MODULO,
    DIAS_ES,
    MESES_ES,
)

import httpx
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

# Números internos — la pausa NO debe activarse si el destinatario es uno de estos
_NUMERO_NEGOCIO   = os.getenv("NUMERO_NEGOCIO",   "5659866275")
_NUMERO_CHRISTIAN = os.getenv("NUMERO_CHRISTIAN",  "5541576331")
_NUMEROS_INTERNOS = {_NUMERO_NEGOCIO, _NUMERO_CHRISTIAN}

# PAUSA_ACTIVA = False: el bot se pausaba a sí mismo al enviar respuestas.
# La pausa manual se activa con el comando "pausa: NÚMERO" desde el grupo.
PAUSA_ACTIVA = False

# Locks por número de teléfono — evita procesar dos mensajes del mismo cliente en paralelo
_locks: dict[str, asyncio.Lock] = {}


def _obtener_lock(telefono: str) -> asyncio.Lock:
    if telefono not in _locks:
        _locks[telefono] = asyncio.Lock()
    return _locks[telefono]


def _es_numero_interno(telefono: str) -> bool:
    """True si el teléfono pertenece a la empresa/equipo, no a un cliente."""
    return any(telefono.endswith(n) or n.endswith(telefono) for n in _NUMEROS_INTERNOS)

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
    # Importar y crear tablas
    from agent.leads import Lead, _migrar_columnas  # noqa: F401

    # 1. Inicializar BD general (conversaciones, perfiles)
    await inicializar_db()
    logger.info("[INIT] Base de datos de conversaciones lista")

    # 2. Crear tabla `leads` si no existe + agregar columnas
    try:
        await _migrar_columnas()
        logger.info("[INIT] Tabla 'leads' creada/actualizada en PostgreSQL")
    except Exception as e:
        logger.warning(f"[INIT] Error en migración de leads: {e}")

    # 3. Inicializar CRM (Google Sheets) — DESACTIVADO TEMPORALMENTE
    # TODO: Configurar credenciales de Google Sheets antes de activar
    # from agent.crm import inicializar_crm
    # await inicializar_crm()
    # logger.info("[INIT] CRM (Google Sheets) listo")

    # 4. Mensaje de inicio
    logger.info(f"[INIT] Servidor listo — Puerto: {PORT} | Proveedor: {proveedor.__class__.__name__}")

    # 5. Iniciar scheduler de seguimientos
    scheduler_task = asyncio.create_task(iniciar_scheduler())

    # 6. Iniciar scheduler de citas diarias (9:00 AM)
    scheduler_citas_task = asyncio.create_task(scheduler_citas_diarias())
    logger.info("[INIT] Scheduler de citas diarias (9:00 AM) iniciado ✓")

    yield

    # Cleanup
    scheduler_task.cancel()
    scheduler_citas_task.cancel()
    logger.info("[SHUTDOWN] Servidor detenido")


app = FastAPI(
    title="Tecnology Support — WhatsApp AI Agent",
    version="2.1.0",
    lifespan=lifespan,
)


@app.get("/")
async def health_check():
    return {"status": "ok", "service": "Tecnology Support AgentKit v2.1"}


@app.get("/leads")
async def ver_leads(detalle: bool = False, estados: str = "todos"):
    """
    GET /leads              — resumen de conteos por estado y fuente
    GET /leads?detalle=true — lista completa con nombre, dispositivo, estado y último mensaje
    """
    import json as _json
    if not detalle:
        return await obtener_resumen_leads()

    leads = await obtener_todos_los_leads_detalle()
    if estados != "todos":
        filtrar = [e.strip() for e in estados.split(",")]
        leads = [l for l in leads if l.estado in filtrar]
    resultado = []
    for lead in leads:
        perfil = await obtener_perfil(lead.telefono)
        historial = await obtener_historial(lead.telefono, limite=4)
        nombre = (perfil.nombre or "") if perfil else ""
        dispositivos: list[str] = []
        if perfil:
            try:
                dispositivos = _json.loads(perfil.dispositivos_json or "[]")
            except Exception:
                dispositivos = []
        ultimo_contenido = ""
        if historial:
            ultimo_contenido = historial[-1]["content"][:200]
        resultado.append({
            "telefono":              lead.telefono,
            "nombre":                nombre,
            "asesor":                lead.asesor_asignado or "",
            "estado":                lead.estado,
            "prioridad":             lead.prioridad,
            "dispositivos":          dispositivos[-3:] if dispositivos else [],
            "fuente":                lead.fuente,
            "seguimientos_enviados": lead.seguimientos_enviados,
            "seguimiento_realizado": lead.seguimiento_realizado,
            "ultimo_mensaje":        lead.ultimo_mensaje.isoformat() if lead.ultimo_mensaje else None,
            "ultimo_contenido":      ultimo_contenido,
            "conversacion_reciente": [
                {"rol": m["role"], "texto": m["content"][:150]}
                for m in historial
            ],
            "creado":                lead.created_at.isoformat() if lead.created_at else None,
        })
    return {"total": len(resultado), "leads": resultado}


@app.post("/reporte")
async def generar_reporte_manual():
    ruta = await generar_reporte_excel()
    return {"status": "ok", "archivo": ruta}


@app.post("/importar-chats")
async def importar_chats_endpoint(
    desde: str | None = None,
    mensajes: int = 200,
    reimportar: bool = False,
):
    """
    Importa y clasifica chats de Whapi.

    Params:
        desde      — Fecha de corte ISO (YYYY-MM-DD). Solo procesa mensajes >= esa fecha.
        mensajes   — Mensajes a traer por chat (default 200, max recomendado 500).
        reimportar — Si True, fuerza reimportación de chats ya en DB.

    Ejemplo: POST /importar-chats?desde=2026-03-19&mensajes=200&reimportar=true
    """
    from datetime import date as date_type
    fecha_desde: date_type | None = None
    if desde:
        try:
            fecha_desde = date_type.fromisoformat(desde)
        except ValueError:
            return {"status": "error", "detalle": f"Fecha inválida: '{desde}'. Usa formato YYYY-MM-DD."}

    asyncio.create_task(_importar_y_reportar(fecha_desde, mensajes, reimportar))
    return {
        "status": "ok",
        "mensaje": "Importación iniciada en segundo plano.",
        "parametros": {
            "desde":      str(fecha_desde) if fecha_desde else "sin filtro",
            "mensajes":   mensajes,
            "reimportar": reimportar,
        },
    }


async def _importar_y_reportar(
    desde=None,
    mensajes_por_chat: int = 200,
    reimportar: bool = False,
):
    resumen = await importar_todos_los_chats(
        desde=desde,
        mensajes_por_chat=mensajes_por_chat,
        reimportar=reimportar,
    )
    if resumen["clientes_nuevos_encontrados"] > 0:
        await generar_reporte_excel()
    logger.info(f"[IMPORT] Resumen final: {resumen}")


@app.get("/webhook")
@app.get("/webhook/messages")
@app.get("/webhook/messages/messages")
async def webhook_verificacion(request: Request):
    resultado = await proveedor.validar_webhook(request)
    if resultado is not None:
        return PlainTextResponse(str(resultado))
    return {"status": "ok"}


# ── Messenger ────────────────────────────────────────────────────────────────

@app.get("/messenger")
async def messenger_verificacion(request: Request):
    """Meta verifica el webhook con un GET antes de activarlo."""
    from agent.providers.messenger import ProveedorMessenger
    messenger = ProveedorMessenger()
    resultado = await messenger.validar_webhook(request)
    if resultado is not None:
        return PlainTextResponse(str(resultado))
    return {"status": "ok"}


@app.post("/messenger")
async def messenger_handler(request: Request):
    """Recibe mensajes de Messenger y los procesa igual que WhatsApp."""
    from agent.providers.messenger import ProveedorMessenger
    messenger = ProveedorMessenger()
    try:
        mensajes = await messenger.parsear_webhook(request)
        for msg in mensajes:
            if not msg.texto:
                continue
            historial = await obtener_historial(msg.telefono, limite=20)
            asesor = await obtener_o_asignar_asesor(msg.telefono)
            await crear_o_actualizar_lead(msg.telefono, fuente="messenger", asesor_asignado=asesor)
            await actualizar_visita_cliente(msg.telefono, asesor)

            perfil = await obtener_perfil(msg.telefono)
            contexto_cliente = construir_contexto_cliente(perfil, asesor) if perfil else ""

            partes_ctx = [_ctx_fecha_cdmx()]
            if contexto_cliente:
                partes_ctx.append(contexto_cliente)
            partes_ctx.append(f"Canal: Facebook Messenger")
            contexto_extra = "\n\n".join(partes_ctx)

            respuesta = await generar_respuesta(msg.texto, historial, asesor, contexto_extra)
            await guardar_mensaje(msg.telefono, "user", msg.texto)
            await guardar_mensaje(msg.telefono, "assistant", respuesta)
            await messenger.enviar_mensaje(msg.telefono, respuesta)

            logger.info(f"[MESSENGER] {msg.telefono} → {respuesta[:60]}")
        return {"status": "ok"}
    except Exception as e:
        logger.error(f"[MESSENGER] Error: {e}")
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
            # ── Deduplicación rápida: Whapi puede reenviar el mismo webhook varias veces ──
            if msg.mensaje_id and await mensaje_ya_procesado(msg.mensaje_id):
                logger.info(f"[DEDUP] {msg.mensaje_id} ({msg.telefono}) ya procesado — ignorando")
                continue

            # ── Mensaje propio: el número de negocio envió a un cliente → pausar ──
            if msg.es_propio and not msg.es_grupo:
                if PAUSA_ACTIVA and not _es_numero_interno(msg.telefono):
                    await pausar_conversacion(msg.telefono, horas=2)
                continue

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

            # ── Modo pausa (intervención humana activa) ──
            # Siempre revisa la pausa manual (independiente de PAUSA_ACTIVA)
            if await esta_pausada(msg.telefono):
                logger.info(f"[PAUSA ACTIVA] {msg.telefono} — mensaje ignorado, Christian está atendiendo")
                continue

            async with _obtener_lock(msg.telefono):
                # ── Double-check dedup dentro del lock (maneja carrera entre requests) ──
                if msg.mensaje_id and await mensaje_ya_procesado(msg.mensaje_id):
                    logger.info(f"[DEDUP] {msg.mensaje_id} ({msg.telefono}) — skip (lock)")
                    continue
                if msg.mensaje_id:
                    await marcar_mensaje_procesado(msg.mensaje_id, msg.telefono)

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

                # ── Sincronizar perfil (SÍNCRONO) — crea clientes_perfil si no existe ──
                # Esto garantiza que obtener_perfil() más abajo siempre encuentre el registro.
                await actualizar_visita_cliente(msg.telefono, asesor)

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

                # Si la última respuesta del agente fue una confirmación de cita,
                # indicarle a Claude que ya está agendada y responda preguntas normalmente
                if historial and historial[-1]["role"] == "assistant" and "CITA CONFIRMADA" in historial[-1]["content"].upper():
                    contexto_cliente += (
                        "\n\n⚠️ NOTA SISTEMA: Esta conversación ya tiene una cita confirmada. "
                        "Responde NORMALMENTE a cualquier pregunta adicional del cliente "
                        "(ubicación, cambios, precios, etc.). "
                        "NO repitas la confirmación. NO incluyas [[AGENDAR:...]] de nuevo."
                    )

                await proveedor.enviar_typing(msg.telefono)
                respuesta = await generar_respuesta(
                    msg.texto, historial, asesor=asesor, contexto_cliente=contexto_cliente
                )

                # ── Ejecutar cita si Claude incluyó el tag [[AGENDAR:...]] ──
                # TODO: Implementar parsear_tag_agendar basado en _RE_TAG de google_calendar.py
                tag = None  # parsear_tag_agendar(respuesta) — función no implementada aún
                if tag and False:  # Desactivado hasta implementar parsear_tag_agendar
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
                            asesor=asesor,
                        )
                        if resultado["ok"]:
                            evento_id = resultado.get("evento_id", "")
                            # Dedup: ignorar si ya se envió esta confirmación al cliente
                            if evento_id and await confirmacion_cita_ya_enviada(msg.telefono, evento_id):
                                logger.warning(f"[CALENDAR] Confirmación duplicada ignorada — {msg.telefono} / {evento_id}")
                                # respuesta = quitar_tags(respuesta)  # TODO: Implementar quitar_tags
                            else:
                                respuesta = resultado["confirmacion"]
                                if evento_id:
                                    await marcar_confirmacion_cita_enviada(msg.telefono, evento_id)
                                asyncio.create_task(
                                    notificar_cita_agendada(
                                        proveedor=proveedor,
                                        nombre=resultado["nombre"],
                                        telefono=msg.telefono,
                                        dispositivo=resultado["dispositivo"],
                                        problema=tag["problema"],
                                        fecha_texto=resultado["fecha_texto"],
                                        hora_texto=resultado["hora_texto"],
                                        asesor=asesor,
                                        evento_id=evento_id,
                                    )
                                )
                                logger.info(f"[CALENDAR] Cita ejecutada para {msg.telefono} — {resultado['fecha_texto']} {resultado['hora_texto']}")
                        else:
                            # Calendar falló → igual confirmar al cliente con datos del tag
                            logger.warning(f"[CALENDAR] Fallo al agendar: {resultado.get('error')} — enviando confirmación manual")
                            dia  = DIAS_ES.get(fh.weekday(), "")
                            mes  = MESES_ES.get(fh.month, "")
                            fecha_txt = f"{dia} {fh.day} de {mes}"
                            hora_txt  = fh.strftime("%I:%M %p").lstrip("0").replace("AM", "a.m.").replace("PM", "p.m.")
                            evento_id = f"manual_{msg.telefono}_{int(datetime.now(ZONA_CDMX).timestamp())}"
                            if await confirmacion_cita_ya_enviada(msg.telefono, evento_id):
                                logger.warning(f"[CALENDAR] Confirmación duplicada ignorada — {msg.telefono} / {evento_id}")
                                # respuesta = quitar_tags(respuesta)  # TODO: Implementar quitar_tags
                            else:
                                linea_asesor = f"👨‍💼 Asesor: {asesor}\n" if asesor else ""
                                respuesta = (
                                    f"✅ *¡CITA CONFIRMADA!*\n\n"
                                    f"📋 *Resumen:*\n"
                                    f"👤 {tag['nombre']}\n"
                                    f"📱 {tag['dispositivo']}\n"
                                    f"⏰ {fecha_txt.capitalize()} · {hora_txt}\n"
                                    f"{linea_asesor}"
                                    f"\n{UBICACION_MODULO}\n\n"
                                    f"📞 Si necesitas cambiar la cita, escríbenos 😊"
                                )
                                await marcar_confirmacion_cita_enviada(msg.telefono, evento_id)
                                asyncio.create_task(
                                    notificar_cita_agendada(
                                        proveedor=proveedor,
                                        nombre=tag["nombre"],
                                        telefono=msg.telefono,
                                        dispositivo=tag["dispositivo"],
                                        problema=tag["problema"],
                                        fecha_texto=fecha_txt,
                                        hora_texto=hora_txt,
                                        asesor=asesor,
                                        evento_id=evento_id,
                                    )
                                )
                    except Exception as e:
                        logger.error(f"[CALENDAR] Error procesando tag AGENDAR: {e}")
                        respuesta = quitar_tags(respuesta)

                await guardar_mensaje(msg.telefono, "user", msg.texto)
                await guardar_mensaje(msg.telefono, "assistant", respuesta)
                await proveedor.enviar_mensaje(msg.telefono, respuesta)

                # ── Detectar dispositivo en background (no bloquea) ──
                dispositivo_detectado = detectar_dispositivo_en_texto(msg.texto)
                if dispositivo_detectado:
                    asyncio.create_task(agregar_dispositivo_cliente(msg.telefono, dispositivo_detectado))

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


# ==================================================================================
# API REST DE LEADS — /api/leads (sincronización con auto-crm)
# ==================================================================================


class LeadResponse(BaseModel):
    """Modelo de respuesta para un lead."""
    id: int
    telefono: str
    ultimo_mensaje: Optional[str] = None
    estado: str
    fuente: str
    asesor_asignado: str
    prioridad: str
    seguimientos_enviados: int
    created_at: Optional[str] = None

    class Config:
        from_attributes = True


class LeadsListResponse(BaseModel):
    """Modelo de respuesta para lista de leads."""
    total: int
    leads: List[LeadResponse]


class UpdateLeadRequest(BaseModel):
    """Modelo para actualizar un lead."""
    estado: Optional[str] = None
    prioridad: Optional[str] = None
    asesor_asignado: Optional[str] = None


@app.get("/api/leads", response_model=LeadsListResponse)
async def get_leads(
    estado: Optional[str] = None,
    fuente: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
):
    """
    Obtiene todos los leads, opcionalmente filtrados por estado o fuente.

    Query params:
    - estado: "activo", "en_seguimiento", "convertido", "perdido"
    - fuente: "facebook_ad", "organico", "whatsapp", etc.
    - skip: offset (default 0)
    - limit: cantidad máxima (default 100)
    """
    try:
        from agent.leads import (
            obtener_todos_los_leads_detalle,
            obtener_leads_por_fuente,
        )

        if fuente:
            leads = await obtener_leads_por_fuente(fuente)
        else:
            leads = await obtener_todos_los_leads_detalle()

        if estado:
            leads = [l for l in leads if l.estado == estado]

        leads_paginados = leads[skip:skip + limit]

        leads_response = [
            LeadResponse(
                id=l.id,
                telefono=l.telefono,
                ultimo_mensaje=l.ultimo_mensaje.isoformat() if l.ultimo_mensaje else None,
                estado=l.estado,
                fuente=getattr(l, "fuente", "desconocido") or "desconocido",
                asesor_asignado=getattr(l, "asesor_asignado", "") or "",
                prioridad=getattr(l, "prioridad", "medio") or "medio",
                seguimientos_enviados=getattr(l, "seguimientos_enviados", 0) or 0,
                created_at=l.created_at.isoformat() if l.created_at else None,
            )
            for l in leads_paginados
        ]

        return LeadsListResponse(total=len(leads), leads=leads_response)

    except Exception as e:
        logger.error(f"[API] Error en GET /api/leads: {e}")
        return JSONResponse(
            status_code=500,
            content={"error": str(e), "total": 0, "leads": []},
        )


@app.get("/api/leads/stats/resumen")
async def get_leads_stats():
    """
    Estadísticas de leads: conteo por estado y fuente.
    """
    try:
        from agent.leads import obtener_resumen_leads
        return await obtener_resumen_leads()
    except Exception as e:
        logger.error(f"[API] Error en GET /api/leads/stats/resumen: {e}")
        return JSONResponse(status_code=500, content={"error": str(e)})


@app.get("/api/leads/{telefono}")
async def get_lead(telefono: str):
    """Obtiene un lead específico por teléfono."""
    try:
        from agent.leads import obtener_todos_los_leads_detalle

        leads = await obtener_todos_los_leads_detalle()
        lead = next((l for l in leads if l.telefono == telefono), None)

        if not lead:
            return JSONResponse(
                status_code=404,
                content={"error": f"Lead {telefono} no encontrado"},
            )

        return LeadResponse(
            id=lead.id,
            telefono=lead.telefono,
            ultimo_mensaje=lead.ultimo_mensaje.isoformat() if lead.ultimo_mensaje else None,
            estado=lead.estado,
            fuente=getattr(lead, "fuente", "desconocido") or "desconocido",
            asesor_asignado=getattr(lead, "asesor_asignado", "") or "",
            prioridad=getattr(lead, "prioridad", "medio") or "medio",
            seguimientos_enviados=getattr(lead, "seguimientos_enviados", 0) or 0,
            created_at=lead.created_at.isoformat() if lead.created_at else None,
        )

    except Exception as e:
        logger.error(f"[API] Error en GET /api/leads/{telefono}: {e}")
        return JSONResponse(status_code=500, content={"error": str(e)})


@app.put("/api/leads/{telefono}")
async def update_lead(telefono: str, data: UpdateLeadRequest):
    """
    Actualiza estado / prioridad / asesor de un lead.

    Body (JSON):
        {"estado": "convertido", "prioridad": "urgente", "asesor_asignado": "Sofia"}
    """
    try:
        from agent.leads import Lead
        from agent.memory import async_session

        async with async_session() as session:
            result = await session.execute(
                select(Lead).where(Lead.telefono == telefono)
            )
            lead_obj = result.scalar_one_or_none()

            if not lead_obj:
                return JSONResponse(
                    status_code=404,
                    content={"error": f"Lead {telefono} no encontrado"},
                )

            if data.estado:
                lead_obj.estado = data.estado
            if data.prioridad:
                lead_obj.prioridad = data.prioridad
            if data.asesor_asignado:
                lead_obj.asesor_asignado = data.asesor_asignado

            await session.commit()

            logger.info(f"[API] Lead {telefono} actualizado: {data}")
            return {
                "ok": True,
                "telefono": telefono,
                "cambios": data.dict(exclude_none=True),
            }

    except Exception as e:
        logger.error(f"[API] Error en PUT /api/leads/{telefono}: {e}")
        return JSONResponse(status_code=500, content={"error": str(e)})


# ==================================================================================
# ENDPOINTS PARA GOOGLE CALENDAR - REPORTE DIARIO (FASE 1)
# ==================================================================================

@app.get("/api/calendar/today")
async def get_calendar_today():
    """
    Retorna el reporte formateado de citas de hoy.
    Usado por: Auto-CRM UI + Scheduler de WhatsApp
    """
    try:
        reporte = await obtener_citas_hoy_formateadas()

        return {
            "ok": True,
            "fecha": datetime.now(ZONA_CDMX).strftime('%Y-%m-%d'),
            "reporte": reporte
        }
    except Exception as e:
        logger.error(f"[API] Error en GET /api/calendar/today: {e}")
        return JSONResponse(
            status_code=500,
            content={"ok": False, "error": str(e), "reporte": ""}
        )


@app.post("/api/calendar/enviar-reporte")
async def enviar_reporte_citas():
    """
    Endpoint para dispara el envío de citas a WhatsApp.
    POST /api/calendar/enviar-reporte
    """
    try:
        reporte = await obtener_citas_hoy_formateadas()

        logger.info(f"[CALENDAR] Reporte listo para enviar al grupo WhatsApp")

        return {
            "ok": True,
            "reporte": reporte,
            "timestamp": datetime.now(ZONA_CDMX).isoformat()
        }
    except Exception as e:
        logger.error(f"[API] Error en POST /api/calendar/enviar-reporte: {e}")
        return JSONResponse(status_code=500, content={"ok": False, "error": str(e)})


# ==================================================================================
# IMPORTAR CITAS HISTÓRICAS DEL GRUPO WHATSAPP
# ==================================================================================

def _parsear_fecha_hora_del_mensaje(fecha_str: str) -> datetime | None:
    """
    Parsea una cadena como "Jueves 15 de mayo, 3:30 PM" a datetime.
    Retorna None si falla el parseo.
    """
    if not fecha_str:
        return None

    try:
        # Limpiar la cadena
        fecha_str = fecha_str.strip()

        # Invertir MESES_ES para buscar por nombre
        meses_inversos = {v: k for k, v in MESES_ES.items()}

        # Regex para extraer: "DIA DD de MES, HH:MM AM/PM"
        # Ej: "Jueves 15 de mayo, 3:30 PM"
        patron = r"(\w+)\s+(\d{1,2})\s+de\s+(\w+),\s+(\d{1,2}):(\d{2})\s*(am|pm|AM|PM)"
        match = re.search(patron, fecha_str)

        if not match:
            logger.warning(f"[IMPORT] No se pudo parsear fecha: {fecha_str}")
            return None

        dia_nombre, dia_num, mes_nombre, hora_str, min_str, ampm = match.groups()

        # Obtener el número de mes
        mes_num = meses_inversos.get(mes_nombre.lower())
        if not mes_num:
            logger.warning(f"[IMPORT] Mes no reconocido: {mes_nombre}")
            return None

        # Convertir hora a formato 24h
        hora = int(hora_str)
        minuto = int(min_str)
        if ampm.lower() == "pm" and hora != 12:
            hora += 12
        elif ampm.lower() == "am" and hora == 12:
            hora = 0

        # Obtener el año (usar año actual, o año siguiente si la fecha es en el pasado)
        ahora = datetime.now(ZONA_CDMX)
        año = ahora.year

        try:
            fecha = datetime(año, mes_num, int(dia_num), hora, minuto, 0, tzinfo=ZONA_CDMX)

            # Si la fecha es en el pasado, asumir que es del año anterior
            if fecha < ahora:
                fecha = datetime(año - 1, mes_num, int(dia_num), hora, minuto, 0, tzinfo=ZONA_CDMX)

            return fecha
        except ValueError as e:
            logger.warning(f"[IMPORT] Error creando datetime: {e} (año={año}, mes={mes_num}, día={dia_num})")
            return None

    except Exception as e:
        logger.error(f"[IMPORT] Error parseando fecha '{fecha_str}': {e}")
        return None


def _extraer_campos_cita(mensaje: str) -> dict | None:
    """
    Extrae campos de un mensaje "NUEVA CITA AGENDADA".
    Retorna dict con: nombre, dispositivo, problema, cuando, asesor
    O None si falla el parseo.

    Formato esperado:
    🔔 *NUEVA CITA AGENDADA*
    👤 {nombre} | 📱 {dispositivo}
    ⏰ {cuando} | ⚠️ {problema}
    👨‍💼 Asesor: {asesor}
    """
    try:
        # Líneas del mensaje
        lineas = mensaje.strip().split('\n')
        if len(lineas) < 4:
            return None

        # Línea 2: nombre y dispositivo
        # Patrón: "👤 {nombre} | 📱 {dispositivo}"
        patron_linea2 = r"👤\s+(.+?)\s*\|\s*📱\s+(.+?)(?:\s|$)"
        match_linea2 = re.search(patron_linea2, lineas[1])
        if not match_linea2:
            logger.warning(f"[IMPORT] No se extrajo nombre/dispositivo de: {lineas[1]}")
            return None
        nombre = match_linea2.group(1).strip()
        dispositivo = match_linea2.group(2).strip()

        # Línea 3: cuando y problema
        # Patrón: "⏰ {cuando} | ⚠️ {problema}"
        patron_linea3 = r"⏰\s+(.+?)\s*\|\s*⚠️\s+(.+?)(?:\s|$)"
        match_linea3 = re.search(patron_linea3, lineas[2])
        if not match_linea3:
            logger.warning(f"[IMPORT] No se extrajo cuando/problema de: {lineas[2]}")
            return None
        cuando = match_linea3.group(1).strip()
        problema = match_linea3.group(2).strip()

        # Línea 4: asesor
        # Patrón: "👨‍💼 Asesor: {asesor}"
        patron_linea4 = r"👨‍💼\s+Asesor:\s*(.+?)(?:\s|$)"
        match_linea4 = re.search(patron_linea4, lineas[3])
        asesor = match_linea4.group(1).strip() if match_linea4 else ""

        return {
            "nombre": nombre,
            "dispositivo": dispositivo,
            "problema": problema,
            "cuando": cuando,
            "asesor": asesor,
        }

    except Exception as e:
        logger.error(f"[IMPORT] Error extrayendo campos de cita: {e}")
        return None


async def _obtener_grupo_id_whapi() -> str | None:
    """Obtiene el ID del grupo 'Taller Interno TS' desde Whapi.cloud."""
    token = os.getenv("WHAPI_TOKEN", "")
    if not token:
        logger.warning("[IMPORT] WHAPI_TOKEN no configurado")
        return None

    try:
        async with httpx.AsyncClient(timeout=15) as http:
            # Obtener lista de chats
            response = await http.get(
                "https://gate.whapi.cloud/chats",
                headers={"Authorization": f"Bearer {token}"},
                params={"count": 100},
            )
            if response.status_code != 200:
                logger.error(f"[IMPORT] Error obteniendo chats: {response.status_code}")
                return None

            chats = response.json().get("chats", [])
            for chat in chats:
                chat_name = chat.get("name", "").lower()
                if "taller" in chat_name and "interno" in chat_name:
                    grupo_id = chat.get("id")
                    logger.info(f"[IMPORT] ✅ Encontrado grupo: {chat.get('name')} (ID: {grupo_id})")
                    return grupo_id

            logger.warning("[IMPORT] No se encontró el grupo 'Taller Interno TS'")
            return None

    except Exception as e:
        logger.error(f"[IMPORT] Error buscando grupo en Whapi: {e}")
        return None


async def _obtener_mensajes_grupo_whapi(grupo_id: str, limite: int = 100) -> list[dict]:
    """Obtiene mensajes del grupo desde Whapi.cloud."""
    token = os.getenv("WHAPI_TOKEN", "")
    if not token or not grupo_id:
        return []

    try:
        async with httpx.AsyncClient(timeout=15) as http:
            response = await http.get(
                f"https://gate.whapi.cloud/messages",
                headers={"Authorization": f"Bearer {token}"},
                params={"chat_id": grupo_id, "count": limite},
            )
            if response.status_code != 200:
                logger.error(f"[IMPORT] Error obteniendo mensajes: {response.status_code}")
                return []

            data = response.json()
            mensajes = data.get("messages", [])
            logger.info(f"[IMPORT] Obtenidos {len(mensajes)} mensajes del grupo")
            return mensajes

    except Exception as e:
        logger.error(f"[IMPORT] Error obteniendo mensajes del grupo: {e}")
        return []


@app.post("/api/calendar/importar-de-texto")
async def importar_citas_de_texto(request: Request):
    """
    Importa citas pegando el texto del grupo de WhatsApp.
    Acepta POST con JSON:
    {
        "mensajes": [
            "🔔 *NUEVA CITA AGENDADA*\n👤 Juan | 📱 iPhone\n⏰ Jueves 15 de mayo, 3:30 PM | ⚠️ Pantalla rota\n👨‍💼 Asesor: Sofia"
        ]
    }

    POST /api/calendar/importar-de-texto
    """
    try:
        body = await request.json()

        # LOGGING EXHAUSTIVO para diagnosticar
        logger.info(f"[IMPORT] RAW body type: {type(body)}")
        logger.info(f"[IMPORT] RAW body repr: {repr(body)[:500]}")

        # Manejar tanto {mensajes: [...]} como [...]
        if isinstance(body, list):
            logger.info(f"[IMPORT] Body es lista directa, {len(body)} elementos")
            mensajes_texto = body
        elif isinstance(body, dict):
            logger.info(f"[IMPORT] Body es dict, claves: {list(body.keys())}")
            mensajes_texto = body.get("mensajes", [])
            logger.info(f"[IMPORT] Extrajeron {len(mensajes_texto)} mensajes de .get('mensajes')")
        else:
            logger.warning(f"[IMPORT] Body tipo inesperado: {type(body)}")
            mensajes_texto = []

        if not mensajes_texto:
            return JSONResponse(
                status_code=400,
                content={"ok": False, "error": "Se requiere 'mensajes' (lista de strings)"}
            )

        logger.info(f"[IMPORT] Procesando {len(mensajes_texto)} mensajes de texto")

        total_encontradas = len(mensajes_texto)
        importadas = 0
        ya_existentes = 0
        errores = 0
        detalles = []

        # Procesar cada mensaje de texto
        for idx, texto_msg in enumerate(mensajes_texto, 1):
            try:
                logger.info(f"[IMPORT] ═══ Procesando mensaje #{idx} ═══")
                logger.info(f"[IMPORT] Tipo de texto_msg: {type(texto_msg)}")
                logger.info(f"[IMPORT] Contenido (primeros 200 chars): {repr(str(texto_msg)[:200])}")

                # Asegurar que texto_msg es un string (PowerShell puede crear estructuras anidadas)
                if isinstance(texto_msg, dict):
                    logger.info(f"[IMPORT] Convirtiendo dict a string")
                    texto_msg = str(texto_msg)
                elif isinstance(texto_msg, list):
                    logger.info(f"[IMPORT] Convirtiendo lista a string (len={len(texto_msg)})")
                    texto_msg = " ".join(str(x) for x in texto_msg)
                else:
                    logger.info(f"[IMPORT] Ya es string, converso por si acaso")
                    texto_msg = str(texto_msg)

                logger.info(f"[IMPORT] Después conversión: {type(texto_msg)}, len={len(texto_msg)}")

                # Extraer campos de la cita
                logger.info(f"[IMPORT] Llamando _extraer_campos_cita()...")
                campos = _extraer_campos_cita(texto_msg)
                logger.info(f"[IMPORT] _extraer_campos_cita() retornó: {type(campos)}")
                if not campos:
                    logger.warning(f"[IMPORT] No se extrajeron campos del mensaje #{idx}")
                    errores += 1
                    detalles.append({
                        "numero": idx,
                        "estado": "error",
                        "razon": "No se extrajeron los campos correctamente",
                    })
                    continue

                # Parsear la fecha y hora
                fecha_hora = _parsear_fecha_hora_del_mensaje(campos["cuando"])
                if not fecha_hora:
                    logger.warning(f"[IMPORT] No se pudo parsear: {campos['cuando']}")
                    errores += 1
                    detalles.append({
                        "numero": idx,
                        "nombre": campos.get("nombre", "?"),
                        "estado": "error",
                        "razon": f"No se pudo parsear fecha: {campos['cuando']}",
                    })
                    continue

                # Agendar la cita en Google Calendar
                resultado = await agendar_cita(
                    nombre=campos["nombre"],
                    telefono="",
                    dispositivo=campos["dispositivo"],
                    problema=campos["problema"],
                    fecha_hora=fecha_hora,
                    asesor=campos["asesor"],
                )

                if resultado.get("ok"):
                    importadas += 1
                    detalles.append({
                        "numero": idx,
                        "nombre": campos["nombre"],
                        "dispositivo": campos["dispositivo"],
                        "problema": campos["problema"],
                        "fecha_hora": fecha_hora.isoformat(),
                        "asesor": campos["asesor"],
                        "estado": "importada",
                        "confirmacion": resultado.get("confirmacion", ""),
                    })
                    logger.info(f"[IMPORT] ✅ Importada: {campos['nombre']}")
                else:
                    error_msg = resultado.get("error", "").lower()
                    if "ya existe" in error_msg or "duplicate" in error_msg:
                        ya_existentes += 1
                        detalles.append({
                            "numero": idx,
                            "nombre": campos["nombre"],
                            "estado": "ya_existente",
                            "razon": resultado.get("error", "Ya existe"),
                        })
                        logger.info(f"[IMPORT] ℹ️ Ya existe: {campos['nombre']}")
                    else:
                        errores += 1
                        detalles.append({
                            "numero": idx,
                            "nombre": campos["nombre"],
                            "estado": "error",
                            "razon": resultado.get("error", "Error desconocido"),
                        })
                        logger.warning(f"[IMPORT] ❌ Error: {resultado.get('error')}")

            except Exception as e:
                errores += 1
                import traceback
                logger.error(f"[IMPORT] ❌ Excepción en mensaje #{idx}: {e}")
                logger.error(f"[IMPORT] Traceback:\n{traceback.format_exc()}")
                detalles.append({
                    "numero": idx,
                    "estado": "error",
                    "razon": str(e),
                    "tipo_error": type(e).__name__,
                })

        logger.info(
            f"[IMPORT] ✅ Resumen: {importadas} importadas, {ya_existentes} existentes, {errores} errores"
        )

        return {
            "ok": True,
            "total_encontradas": total_encontradas,
            "importadas": importadas,
            "ya_existentes": ya_existentes,
            "errores": errores,
            "timestamp": datetime.now(ZONA_CDMX).isoformat(),
            "detalles": detalles,
        }

    except Exception as e:
        logger.error(f"[API] Error en POST /api/calendar/importar-de-texto: {e}")
        return JSONResponse(
            status_code=500,
            content={"ok": False, "error": str(e)}
        )


@app.post("/api/calendar/importar-historico")
async def importar_citas_historicas():
    """
    Importa citas del grupo WhatsApp a Google Calendar.
    Lee mensajes del grupo "Taller Interno TS" desde Whapi.cloud.

    POST /api/calendar/importar-historico

    Retorna:
    {
        "ok": bool,
        "total_encontradas": int,
        "importadas": int,
        "ya_existentes": int,
        "errores": int,
        "detalles": [...]
    }
    """
    try:
        ahora = datetime.now(ZONA_CDMX)
        hace_12_dias = ahora - timedelta(days=12)

        logger.info(f"[IMPORT] Buscando citas desde {hace_12_dias.date()} hasta {ahora.date()}")

        # 1. Obtener el ID del grupo
        grupo_id = await _obtener_grupo_id_whapi()
        if not grupo_id:
            return JSONResponse(
                status_code=400,
                content={"ok": False, "error": "No se encontró el grupo 'Taller Interno TS'"}
            )

        # 2. Obtener mensajes del grupo desde Whapi
        mensajes_whapi = await _obtener_mensajes_grupo_whapi(grupo_id, limite=200)

        # 3. Filtrar solo los que contienen "NUEVA CITA AGENDADA" y son de los últimos 12 días
        mensajes_validos = []
        for msg in mensajes_whapi:
            # Whapi retorna timestamp en segundos o milisegundos
            timestamp_ms = msg.get("timestamp", 0)
            if timestamp_ms > 1e10:  # milisegundos
                msg_time = datetime.fromtimestamp(timestamp_ms / 1000, tz=ZONA_CDMX)
            else:  # segundos
                msg_time = datetime.fromtimestamp(timestamp_ms, tz=ZONA_CDMX)

            # Filtrar por fecha
            if msg_time < hace_12_dias:
                continue

            # Filtrar por contenido
            texto = msg.get("text", {}).get("body", "").strip()
            if "NUEVA CITA AGENDADA" not in texto:
                continue

            mensajes_validos.append({
                "timestamp": msg_time,
                "content": texto,
                "message_id": msg.get("id", ""),
            })

        logger.info(f"[IMPORT] Encontrados {len(mensajes_validos)} mensajes con citas")

        total_encontradas = len(mensajes_validos)
        importadas = 0
        ya_existentes = 0
        errores = 0
        detalles = []

        # 4. Procesar cada mensaje
        for msg in mensajes_validos:
            try:
                # Extraer campos de la cita
                campos = _extraer_campos_cita(msg["content"])
                if not campos:
                    logger.warning(f"[IMPORT] No se extrajeron campos de cita del mensaje ID {msg['message_id']}")
                    errores += 1
                    detalles.append({
                        "timestamp": msg["timestamp"].isoformat(),
                        "estado": "error",
                        "razon": "No se extrajeron los campos correctamente",
                    })
                    continue

                # Parsear la fecha y hora
                fecha_hora = _parsear_fecha_hora_del_mensaje(campos["cuando"])
                if not fecha_hora:
                    logger.warning(f"[IMPORT] No se pudo parsear fecha/hora: {campos['cuando']}")
                    errores += 1
                    detalles.append({
                        "timestamp": msg["timestamp"].isoformat(),
                        "nombre": campos.get("nombre", "?"),
                        "estado": "error",
                        "razon": f"No se pudo parsear fecha: {campos['cuando']}",
                    })
                    continue

                # Agendar la cita en Google Calendar
                resultado = await agendar_cita(
                    nombre=campos["nombre"],
                    telefono="",  # No tenemos el teléfono del grupo
                    dispositivo=campos["dispositivo"],
                    problema=campos["problema"],
                    fecha_hora=fecha_hora,
                    asesor=campos["asesor"],
                )

                if resultado.get("ok"):
                    importadas += 1
                    detalles.append({
                        "timestamp": msg["timestamp"].isoformat(),
                        "nombre": campos["nombre"],
                        "dispositivo": campos["dispositivo"],
                        "problema": campos["problema"],
                        "fecha_hora": fecha_hora.isoformat(),
                        "asesor": campos["asesor"],
                        "estado": "importada",
                        "confirmacion": resultado.get("confirmacion", ""),
                    })
                    logger.info(f"[IMPORT] ✅ Importada cita: {campos['nombre']} - {fecha_hora}")
                else:
                    # Revisar si es porque ya existe
                    error_msg = resultado.get("error", "").lower()
                    if "ya existe" in error_msg or "duplicate" in error_msg:
                        ya_existentes += 1
                        detalles.append({
                            "timestamp": msg["timestamp"].isoformat(),
                            "nombre": campos["nombre"],
                            "estado": "ya_existente",
                            "razon": resultado.get("error", "Ya existe en calendario"),
                        })
                        logger.info(f"[IMPORT] ℹ️ Ya existe: {campos['nombre']}")
                    else:
                        errores += 1
                        detalles.append({
                            "timestamp": msg["timestamp"].isoformat(),
                            "nombre": campos["nombre"],
                            "estado": "error",
                            "razon": resultado.get("error", "Error desconocido"),
                        })
                        logger.warning(f"[IMPORT] ❌ Error agendando {campos['nombre']}: {resultado.get('error')}")

            except Exception as e:
                errores += 1
                logger.error(f"[IMPORT] Excepción procesando cita: {e}")
                detalles.append({
                    "timestamp": msg["timestamp"].isoformat(),
                    "estado": "error",
                    "razon": str(e),
                })

        logger.info(
            f"[IMPORT] ✅ Resumen: {importadas} importadas, {ya_existentes} ya existentes, {errores} errores"
        )

        return {
            "ok": True,
            "total_encontradas": total_encontradas,
            "importadas": importadas,
            "ya_existentes": ya_existentes,
            "errores": errores,
            "timestamp": ahora.isoformat(),
            "detalles": detalles,
        }

    except Exception as e:
        logger.error(f"[API] Error en POST /api/calendar/importar-historico: {e}")
        return JSONResponse(
            status_code=500,
            content={"ok": False, "error": str(e)}
        )


# ==================================================================================
# SCHEDULER PARA CITAS - ENVÍO DIARIO A LAS 9:00 AM
# ==================================================================================

async def scheduler_citas_diarias():
    """
    Scheduler que envía reporte de citas a las 9:00 AM México (CDMX).
    Se ejecuta cada 30 segundos para revisar si es hora de enviar.
    """
    tz_mexico = pytz.timezone('America/Mexico_City')

    while True:
        try:
            ahora = datetime.now(tz_mexico)

            # Si es 9:00 AM (entre 9:00:00 y 9:00:59)
            if ahora.hour == 9 and ahora.minute == 0:
                logger.info("[SCHEDULER-CITAS] ⏰ Es las 9:00 AM - Enviando reporte de citas...")

                try:
                    reporte = await obtener_citas_hoy_formateadas()

                    # Aquí iría el código para enviar a WhatsApp
                    # Uso el proveedor existente: proveedor.enviar_mensaje()
                    try:
                        await proveedor.enviar_mensaje(
                            numero=_NUMERO_NEGOCIO,  # Enviar al número del negocio
                            texto=reporte,
                            grupo_id=GRUPO_INTERNO  # Enviar al grupo interno
                        )
                        logger.info("[SCHEDULER-CITAS] ✅ Reporte de citas enviado al grupo")
                    except Exception as e:
                        logger.warning(f"[SCHEDULER-CITAS] No se pudo enviar a WhatsApp: {e}")

                    # Esperar 2 minutos para no dispararse múltiples veces
                    await asyncio.sleep(120)

                except Exception as e:
                    logger.error(f"[SCHEDULER-CITAS] Error obteniendo reporte: {e}")

        except Exception as e:
            logger.error(f"[SCHEDULER-CITAS] Error general en scheduler: {e}")

        # Revisar cada 30 segundos
        await asyncio.sleep(30)
