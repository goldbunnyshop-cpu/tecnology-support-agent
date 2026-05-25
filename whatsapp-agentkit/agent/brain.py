# agent/brain.py — Cerebro del agente: conexión con Claude API
# Generado por AgentKit

import os
import yaml
import logging
from anthropic import AsyncAnthropic
from dotenv import load_dotenv
from agent.pricing import obtener_cotizacion_display
import re

load_dotenv()
logger = logging.getLogger("agentkit")

client = AsyncAnthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))


def cargar_config_prompts() -> dict:
    try:
        with open("config/prompts.yaml", "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except FileNotFoundError:
        logger.error("config/prompts.yaml no encontrado")
        return {}


def construir_system_prompt(asesor: str = "Valentina") -> str:
    """Construye el system prompt inyectando el nombre y personalidad del asesor."""
    config = cargar_config_prompts()
    template = config.get("system_prompt_template", "Eres un asistente útil. Responde en español.")
    asesores = config.get("asesores", {})
    info = asesores.get(asesor, {})
    personalidad = info.get("personalidad", "Eres profesional y amable.")
    return (
        template
        .replace("ASESOR_NOMBRE", asesor)
        .replace("ASESOR_PERSONALIDAD", personalidad)
    )


def obtener_mensaje_error() -> str:
    config = cargar_config_prompts()
    return config.get("error_message", "Lo siento, estoy teniendo problemas técnicos. Por favor intente de nuevo.")


def obtener_mensaje_fallback() -> str:
    config = cargar_config_prompts()
    return config.get("fallback_message", "Disculpe, no entendí su mensaje. ¿Podría reformularlo?")




async def detectar_y_obtener_precios(mensaje: str) -> str:
    """
    Detecta si el mensaje pregunta sobre precios de displays.
    Si lo hace, obtiene la cotización y retorna contexto inyectable.
    """
    # Patrones ampliados que indican pregunta sobre displays/pantallas
    # Incluye: cotizar, presupuesto, valor, precio, costo, cuánto, cambio, reparación
    patrones_display = [
        # Palabras clave de precio + display/pantalla
        r'\bcotizar.*(?:display|pantalla|screen)\b',
        r'\b(?:display|pantalla|screen).*cotizar\b',
        r'\bpresupuesto.*(?:display|pantalla|screen)\b',
        r'\b(?:display|pantalla|screen).*presupuesto\b',
        r'\bcuánto.*(?:display|pantalla|screen)\b',
        r'\b(?:display|pantalla|screen).*cuánto\b',
        r'\bprecio.*(?:display|pantalla|screen)\b',
        r'\b(?:display|pantalla|screen).*precio\b',
        r'\bcosto.*(?:display|pantalla|screen)\b',
        r'\b(?:display|pantalla|screen).*costo\b',
        r'\bvalor.*(?:display|pantalla|screen)\b',
        r'\b(?:display|pantalla|screen).*valor\b',

        # Palabras de reparación/cambio
        r'\bcambio\s+(?:de\s+)?(?:pantalla|display|screen)\b',
        r'\breparación\s+(?:de\s+)?(?:pantalla|display|screen)\b',
        r'\breparar\s+(?:pantalla|display|screen)\b',

        # Preguntas genéricas de precio (sin requerir display explícito)
        r'\bcotizar\b',
        r'\bpresupuesto\b',
        r'\bcuánto\s+cuesta\b',
        r'\bcuál\s+es\s+el\s+(?:precio|costo|valor)\b',
        r'\bapróximo\s+(?:precio|costo|valor)\b',
        r'\bcosto\b',                              # Solo "costo"
        r'\bprecio\b',                             # Solo "precio"
        r'\bvalor\b',                              # Solo "valor"
    ]

    mensaje_lower = mensaje.lower()

    # Verificar si pregunta sobre precios
    es_pregunta_precio = any(re.search(p, mensaje_lower) for p in patrones_display)

    # Logs en INFO para que aparezcan en Railway
    if es_pregunta_precio:
        logger.info(f"[BRAIN] 🔍 Pregunta de precio detectada en: '{mensaje_lower[:60]}...'")
    else:
        logger.debug(f"[BRAIN] Mensaje no es pregunta de precio: '{mensaje_lower[:60]}...'")
        return ""

    # Extraer marca y modelo (ej: "iPhone 16", "Samsung S24", "Moto Edge 50 Fusion")
    patron_modelo = r'(iPhone|Samsung|Google Pixel|OnePlus|Xiaomi|Motorola|Huawei|Nokia|LG)\s+(\w+[\s\w]*)'
    match = re.search(patron_modelo, mensaje, re.IGNORECASE)

    if not match:
        logger.debug(f"[BRAIN] Pregunta de precio detectada pero sin modelo identificable")
        return ""

    marca = match.group(1)
    modelo = match.group(2).strip()

    logger.info(f"[BRAIN] ✓ Pregunta sobre precios detectada: {marca} {modelo}")

    # Obtener cotización
    cotizacion = await obtener_cotizacion_display(marca, modelo)

    if cotizacion:
        contexto = f"PRECIO ENCONTRADO PARA {marca.upper()} {modelo.upper()}:\n{cotizacion}"
        logger.info(f"[BRAIN] ✓ Cotización obtenida: {marca} {modelo}")
        return contexto

    logger.debug(f"[BRAIN] Cotización no encontrada para: {marca} {modelo}")
    return ""


async def generar_respuesta(
    mensaje: str,
    historial: list[dict],
    asesor: str = "Valentina",
    contexto_cliente: str = "",
) -> str:
    if not mensaje or len(mensaje.strip()) < 2:
        return obtener_mensaje_fallback()

    # Detectar y obtener precios si pregunta sobre displays
    if not contexto_cliente:
        contexto_precios = await detectar_y_obtener_precios(mensaje)
        if contexto_precios:
            contexto_cliente = contexto_precios

    system_prompt = construir_system_prompt(asesor)
    if contexto_cliente:
        system_prompt = f"{contexto_cliente}\n\n{system_prompt}"

    mensajes = [{"role": m["role"], "content": m["content"]} for m in historial]
    mensajes.append({"role": "user", "content": mensaje})

    try:
        response = await client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1024,
            system=system_prompt,
            messages=mensajes,
        )
        respuesta = response.content[0].text
        logger.info(f"[{asesor}] Respuesta generada ({response.usage.input_tokens} in / {response.usage.output_tokens} out)")
        return respuesta

    except Exception as e:
        logger.error(f"Error Claude API: {e}")
        return obtener_mensaje_error()
