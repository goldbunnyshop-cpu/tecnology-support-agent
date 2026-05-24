# agent/main.py — Servidor FastAPI + Webhook de WhatsApp
# Generado por AgentKit

"""
Servidor principal del agente de WhatsApp.
Funciona con cualquier proveedor (Whapi, Meta, Meta Inbox, Twilio) gracias a la capa de providers.
"""

import os
import logging
import random
from datetime import datetime
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import PlainTextResponse
from dotenv import load_dotenv

from agent.brain import generar_respuesta
from agent.memory import inicializar_db, guardar_mensaje, obtener_historial, esta_pausada
from agent.providers import obtener_proveedor
from agent.sleep_mode import (
    esta_en_horario_operacion_bot,
    obtener_mensaje_sleep_mode,
    calcular_hora_reactivacion,
    ZONA_MEXICO,
)
from agent.profile import extraer_asesor_de_historial
from agent.reminder_scheduler import (
    inicializar_scheduler,
    programar_reactivacion_sleep,
)
from agent.tools import (
    fue_ultimo_mensaje_menu_ambiguo,
    generar_respuesta_post_ambiguo,
    detectar_tipo_dispositivo_en_mensaje,
)
from agent.commands import procesar_comando_grupo, esta_bloqueado, inicializar_sistema_cupones

load_dotenv()

# Configuración de logging según entorno
ENVIRONMENT = os.getenv("ENVIRONMENT", "development")
log_level = logging.DEBUG if ENVIRONMENT == "development" else logging.INFO
logging.basicConfig(level=log_level)
logger = logging.getLogger("agentkit")

# Proveedor de WhatsApp (se configura en .env con WHATSAPP_PROVIDER)
proveedor = obtener_proveedor()
PORT = int(os.getenv("PORT", 8000))


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Inicializa la base de datos, scheduler y sistema de cupones al arrancar el servidor."""
    await inicializar_db()
    logger.info("Base de datos inicializada")

    # Inicializar scheduler para reactivación de sleep mode
    await inicializar_scheduler(app)
    logger.info("Scheduler de reactivación inicializado")

    # Inicializar sistema de cupones (crea hoja ClientePerfil en Google Sheets)
    await inicializar_sistema_cupones()
    logger.info("Sistema de cupones inicializado")

    logger.info(f"Servidor AgentKit corriendo en puerto {PORT}")
    logger.info(f"Proveedor de WhatsApp: {proveedor.__class__.__name__}")
    yield


app = FastAPI(
    title="AgentKit — WhatsApp AI Agent",
    version="1.0.0",
    lifespan=lifespan
)


@app.get("/")
async def health_check():
    """Endpoint de salud para Railway/monitoreo."""
    return {"status": "ok", "service": "agentkit"}


@app.get("/webhook")
async def webhook_verificacion(request: Request):
    """Verificación GET del webhook (requerido por Meta Cloud API, no-op para otros)."""
    resultado = await proveedor.validar_webhook(request)
    if resultado is not None:
        return PlainTextResponse(str(resultado))
    return {"status": "ok"}


@app.post("/webhook")
async def webhook_handler(request: Request):
    """
    Recibe mensajes de WhatsApp via el proveedor configurado.
    Procesa el mensaje, genera respuesta con Claude y la envía de vuelta.

    IMPORTANTE: Cada paso está logeado por separado para diagnosticar fallos.
    """
    try:
        # PASO 1: Parsear webhook
        try:
            logger.debug("🔵 PASO 1: Parseando webhook...")
            mensajes = await proveedor.parsear_webhook(request)
            logger.info(f"✅ Webhook parseado. Mensajes recibidos: {len(mensajes)}")
        except Exception as e:
            logger.error(f"❌ FALLO en parseo de webhook: {e}", exc_info=True)
            raise

        # PASO 2: Procesar cada mensaje
        for idx, msg in enumerate(mensajes, 1):
            logger.debug(f"🔵 PASO 2.{idx}: Procesando mensaje {idx}/{len(mensajes)}")

            # Validar mensaje
            if msg.es_propio:
                logger.debug(f"⏭️  Ignorando mensaje propio: {msg.telefono}")
                continue

            if not msg.texto or len(msg.texto.strip()) == 0:
                logger.debug(f"⏭️  Ignorando mensaje vacío de {msg.telefono}")
                continue

            logger.info(f"📱 Mensaje recibido de {msg.telefono}: '{msg.texto[:50]}...'")

            # VERIFICACIÓN HORARIO: Sleep mode (00:00 - 5:59 AM)
            if not esta_en_horario_operacion_bot():
                logger.info(f"🌙 [SLEEP] Mensaje en horario de reposo — Enviando mensaje sin mostrar horas.")

                # Obtener historial para detectar asesor
                try:
                    historial_temp = await obtener_historial(msg.telefono)
                    asesor = extraer_asesor_de_historial(historial_temp)
                    if not asesor:
                        asesor = random.choice(["Sofia", "Valentina", "Camila", "Daniela", "Andrea", "Rocio"])
                    logger.debug(f"[SLEEP] Asesor seleccionado: {asesor}")
                except Exception as e:
                    logger.warning(f"[SLEEP] No se pudo obtener historial: {e}, usando asesor aleatorio")
                    asesor = random.choice(["Sofia", "Valentina", "Camila", "Daniela", "Andrea", "Rocio"])

                # Enviar mensaje de sleep mode (sin mostrar horas)
                respuesta_sleep = obtener_mensaje_sleep_mode(asesor)
                await guardar_mensaje(msg.telefono, "user", msg.texto)
                await guardar_mensaje(msg.telefono, "assistant", respuesta_sleep)
                await proveedor.enviar_mensaje(msg.telefono, respuesta_sleep)

                # Programar reactivación automática a +7 horas
                ahora = datetime.now(ZONA_MEXICO)
                hora_reactivacion = calcular_hora_reactivacion(ahora)

                resultado_sched = await programar_reactivacion_sleep(
                    telefono=msg.telefono,
                    asesor=asesor,
                    hora_reactivacion=hora_reactivacion,
                    callback_enviar_mensaje=proveedor.enviar_mensaje
                )

                if resultado_sched["exito"]:
                    logger.info(f"[SLEEP] ✅ Reactivación programada: {resultado_sched['detalle']}")
                else:
                    logger.warning(f"[SLEEP] ⚠️ No se pudo programar reactivación: {resultado_sched['detalle']}")

                continue

            try:
                # PASO 2.5: VERIFICAR BLOQUEO (NUEVO)
                if esta_bloqueado(msg.telefono):
                    logger.info(f"🚫 [BLOQUEO] Número {msg.telefono} está bloqueado — ignorando mensaje")
                    continue

                # PASO 2.5b: VERIFICAR PAUSA (intervención manual)
                if await esta_pausada(msg.telefono):
                    logger.info(f"⏸️ [PAUSA] Número {msg.telefono} está pausado — Christian atenderá manualmente")
                    continue

                # PASO 2.6: PROCESAR COMANDOS DEL GRUPO INTERNO (NUEVO)
                # Intentar procesar si es un comando del grupo
                try:
                    # Crear un objeto simple con los atributos necesarios si msg no es un objeto completo
                    if not hasattr(msg, "nombre_grupo"):
                        # Si msg viene de Whapi sin nombre_grupo, saltamos procesamiento de comandos
                        es_comando_procesado = False
                    else:
                        es_comando_procesado = await procesar_comando_grupo(
                            msg,
                            proveedor,
                            guardar_mensaje,
                            obtener_historial,
                        )

                    if es_comando_procesado:
                        logger.info(f"✅ Comando de grupo procesado para {msg.telefono}")
                        continue  # No procesar como mensaje normal
                except Exception as e:
                    logger.debug(f"[CMD] No es comando o error procesando: {e}")
                    # No es error crítico, continuar con flujo normal
                    es_comando_procesado = False

                # PASO 3: Obtener historial
                try:
                    logger.debug(f"🔵 PASO 3: Obteniendo historial de {msg.telefono}...")
                    historial = await obtener_historial(msg.telefono)
                    logger.debug(f"✅ Historial obtenido: {len(historial)} mensajes previos")
                except Exception as e:
                    logger.error(f"❌ FALLO obteniendo historial: {e}", exc_info=True)
                    raise

                # PASO 3.5: Seleccionar asesor (basado en historial o aleatorio)
                try:
                    logger.debug(f"🔵 PASO 3.5: Seleccionando asesor...")
                    asesor = extraer_asesor_de_historial(historial)
                    if not asesor:
                        asesor = random.choice(["Sofia", "Valentina", "Camila", "Daniela", "Andrea", "Rocio"])
                        logger.debug(f"✅ Asesor elegido aleatoriamente: {asesor}")
                    else:
                        logger.debug(f"✅ Asesor recuperado del historial: {asesor}")
                except Exception as e:
                    logger.warning(f"⚠️  Error seleccionando asesor: {e}, usando default")
                    asesor = "Valentina"

                # PASO 4: Detectar tipo de dispositivo
                try:
                    logger.debug(f"🔵 PASO 4: Detectando tipo de dispositivo...")
                    tipo_dispositivo = detectar_tipo_dispositivo_en_mensaje(msg.texto, historial)
                    logger.debug(f"✅ Tipo detectado: {tipo_dispositivo}")
                except Exception as e:
                    logger.error(f"❌ FALLO detectando dispositivo: {e}", exc_info=True)
                    tipo_dispositivo = "desconocido"

                # PASO 5: Generar respuesta
                try:
                    logger.debug(f"🔵 PASO 5: Generando respuesta con asesor: {asesor}...")

                    # Verificar si el último mensaje del asistente fue un menú ambiguo
                    if fue_ultimo_mensaje_menu_ambiguo(historial) and tipo_dispositivo == "ambiguo":
                        logger.debug("ℹ️  Usando respuesta post-ambiguo")
                        respuesta = generar_respuesta_post_ambiguo()
                    else:
                        respuesta = await generar_respuesta(msg.texto, historial, asesor=asesor)

                    logger.info(f"✅ Respuesta generada por {asesor} ({len(respuesta)} caracteres)")
                except Exception as e:
                    logger.error(f"❌ FALLO generando respuesta: {e}", exc_info=True)
                    raise

                # PASO 6: Guardar en memoria
                try:
                    logger.debug(f"🔵 PASO 6: Guardando en memoria...")
                    await guardar_mensaje(msg.telefono, "user", msg.texto)
                    await guardar_mensaje(msg.telefono, "assistant", respuesta)
                    logger.debug(f"✅ Mensajes guardados en BD")
                except Exception as e:
                    logger.error(f"❌ FALLO guardando en BD: {e}", exc_info=True)
                    raise

                # PASO 7: Enviar por WhatsApp
                try:
                    logger.debug(f"🔵 PASO 7: Enviando respuesta por WhatsApp...")
                    exito = await proveedor.enviar_mensaje(msg.telefono, respuesta)

                    if exito:
                        logger.info(f"✅ Respuesta enviada a {msg.telefono}")
                    else:
                        logger.error(f"❌ FALLO enviando a {msg.telefono} (proveedor retornó False)")
                except Exception as e:
                    logger.error(f"❌ FALLO enviando por WhatsApp: {e}", exc_info=True)
                    raise

                logger.info(f"✅ Ciclo completo exitoso para {msg.telefono}")

            except Exception as e:
                logger.error(f"❌ ERROR en procesamiento de mensaje de {msg.telefono}: {e}", exc_info=True)
                # Continuar con el siguiente mensaje en lugar de crashear
                continue

        logger.info(f"✅ Webhook completado. Se procesaron {len(mensajes)} mensajes")
        return {"status": "ok"}

    except Exception as e:
        logger.error(f"❌ ERROR CRÍTICO en webhook: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
