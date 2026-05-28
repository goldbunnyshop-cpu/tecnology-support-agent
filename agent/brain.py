# agent/brain.py — Cerebro del agente: conexión con Claude API
# Generado por AgentKit

import os
import re
import yaml
import logging
from anthropic import AsyncAnthropic
from dotenv import load_dotenv
from agent.pricing import obtener_cotizacion_display, buscar_modelo_sin_marca, ALIAS_MARCAS

load_dotenv()
logger = logging.getLogger("agentkit")

client = AsyncAnthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

_PATRONES_PRECIO = [
    r"\bprecio\b",
    r"\bcosto\b",
    r"\bcotiz",
    r"\bpresupuesto\b",
    r"\bdisplay\b",
    r"\bpantalla\b",
]


def _limpiar_respuesta_pricing(texto: str) -> str:
    """Quita encabezados internos y retorna texto listo para cliente."""
    if not texto:
        return texto
    t = texto.strip()
    prefijos = [
        "INFORMACION PARA EL CLIENTE (transmitir tal cual; usar solo las etiquetas ",
        "INFORMACION PARA EL CLIENTE (transmitir esta pregunta tal cual; ",
        "INFORMACION PARA EL CLIENTE:",
    ]
    for p in prefijos:
        if t.startswith(p):
            # cortar al primer doble salto de linea
            partes = t.split("\n\n", 1)
            if len(partes) == 2:
                return partes[1].strip()
    return t


def _extraer_marca_modelo(mensaje: str) -> tuple[str | None, str | None]:
    """Intenta extraer marca+modelo de un mensaje libre."""
    txt = (mensaje or "").lower()
    # Primero marcas más largas para evitar colisiones (google pixel antes de pixel)
    for alias in sorted(ALIAS_MARCAS.keys(), key=len, reverse=True):
        if re.search(rf"\b{re.escape(alias)}\b", txt):
            marca = alias
            modelo = re.sub(rf".*?\b{re.escape(alias)}\b", "", txt, count=1).strip(" :,-")
            return marca, (modelo or None)
    return None, None


async def _intentar_respuesta_pricing(mensaje: str) -> str | None:
    """Si es consulta de precios, devuelve respuesta directa de pricing."""
    m = (mensaje or "").lower()
    if not any(re.search(p, m) for p in _PATRONES_PRECIO):
        return None

    marca, modelo = _extraer_marca_modelo(mensaje)
    try:
        if marca and modelo:
            r = await obtener_cotizacion_display(marca, modelo)
            return _limpiar_respuesta_pricing(r)
        if modelo:
            r = await buscar_modelo_sin_marca(modelo)
            return _limpiar_respuesta_pricing(r)
        # Si no hubo marca/modelo claros, intentar con el mensaje completo
        r = await buscar_modelo_sin_marca(mensaje)
        return _limpiar_respuesta_pricing(r)
    except Exception as e:
        logger.error(f"[PRICING] Error en consulta directa: {e}")
        return None


def cargar_config_prompts() -> dict:
    try:
        with open("config/prompts.yaml", "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except FileNotFoundError:
        logger.error("config/prompts.yaml no encontrado")
        return {}


def construir_system_prompt(asesor: str = "Sofia") -> str:
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


async def generar_respuesta(
    mensaje: str,
    historial: list[dict],
    asesor: str = "Sofia",
    contexto_cliente: str = "",
) -> str:
    if not mensaje or len(mensaje.strip()) < 2:
        return obtener_mensaje_fallback()

    # Prioridad alta: consultas de precio/cotizacion se resuelven con motor de pricing.
    respuesta_pricing = await _intentar_respuesta_pricing(mensaje)
    if respuesta_pricing:
        logger.info(f"[{asesor}] Respuesta de pricing directa aplicada")
        return respuesta_pricing

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
