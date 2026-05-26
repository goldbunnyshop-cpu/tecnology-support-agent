# agent/brain.py - Cerebro del agente
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
    config = cargar_config_prompts()
    template = config.get("system_prompt_template", "Eres un asistente util. Responde en espanol.")
    asesores = config.get("asesores", {})
    info = asesores.get(asesor, {})
    personalidad = info.get("personalidad", "Eres profesional y amable.")
    return template.replace("ASESOR_NOMBRE", asesor).replace("ASESOR_PERSONALIDAD", personalidad)

def obtener_mensaje_error() -> str:
    config = cargar_config_prompts()
    return config.get("error_message", "Lo siento, estoy teniendo problemas tecnicos.")

def obtener_mensaje_fallback() -> str:
    config = cargar_config_prompts()
    return config.get("fallback_message", "Disculpe, no entendi su mensaje.")

def _confirmar_variante_amb(modelo: str) -> tuple:
    modelo_lower = modelo.lower()
    if '+' in modelo_lower:
        modelo_limpio = modelo_lower.replace(' +', '').replace('+', '')
        respuesta = f"Detecte que preguntaste por {modelo_limpio.title()} Plus. Confirma: 'Plus' o 'normal'?"
        return respuesta, True
    return "", False

async def detectar_y_obtener_precios(mensaje: str) -> str:
    """Detecta precios por keywords O por marca+modelo sin importar keywords."""
    patrones_display = [
        r'\bcotizar.*(?:display|pantalla|screen)\b',
        r'\b(?:display|pantalla|screen).*cotizar\b',
        r'\bpresupuesto.*(?:display|pantalla|screen)\b',
        r'\b(?:display|pantalla|screen).*presupuesto\b',
        r'\bcuanto.*(?:display|pantalla|screen)\b',
        r'\b(?:display|pantalla|screen).*cuanto\b',
        r'\bprecio.*(?:display|pantalla|screen)\b',
        r'\b(?:display|pantalla|screen).*precio\b',
        r'\bcosto.*(?:display|pantalla|screen)\b',
        r'\b(?:display|pantalla|screen).*costo\b',
        r'\bvalor.*(?:display|pantalla|screen)\b',
        r'\b(?:display|pantalla|screen).*valor\b',
        r'\bcambio\s+(?:de\s+)?(?:pantalla|display|screen)\b',
        r'\breparacion\s+(?:de\s+)?(?:pantalla|display|screen)\b',
        r'\breparar\s+(?:pantalla|display|screen)\b',
        r'\bcotizar\b', r'\bpresupuesto\b', r'\bcuanto\s+cuesta\b',
        r'\bcual\s+es\s+el\s+(?:precio|costo|valor)\b',
        r'\bprecio\b', r'\bcosto\b', r'\bvalor\b',
    ]

    mensaje_lower = mensaje.lower()
    es_pregunta_precio = any(re.search(p, mensaje_lower) for p in patrones_display)

    patron_modelo = r'(iPhone|Samsung|Google Pixel|Pixel|OnePlus|Xiaomi|Motorola|Huawei|Nokia|LG|Moto|Poco|Redmi|Hisense|Honor|Oppo|Realme|TCL|Vivo|ZTE|Alcatel|Cubot)\s+([\w]+(?:\s+[\w]+){0,3})'
    match = re.search(patron_modelo, mensaje, re.IGNORECASE)

    if es_pregunta_precio:
        logger.info(f"[BRAIN] Pregunta de precio detectada (keywords)")
    elif match:
        logger.info(f"[BRAIN] Marca+modelo detectado sin keywords")
    else:
        logger.debug(f"[BRAIN] Mensaje sin precio ni marca+modelo")
        return ""

    if not match:
        logger.debug(f"[BRAIN] Precio detectado pero sin modelo")
        return ""

    marca = match.group(1)
    modelo = match.group(2).strip()
    logger.info(f"[BRAIN] Buscando: {marca} {modelo}")

    msg_confirmacion, fue_ambiguo = _confirmar_variante_amb(modelo)
    if fue_ambiguo:
        return msg_confirmacion

    cotizacion = await obtener_cotizacion_display(marca, modelo)
    if cotizacion:
        contexto = f"PRECIO ENCONTRADO PARA {marca.upper()} {modelo.upper()}:\n{cotizacion}"
        logger.info(f"[BRAIN] Cotizacion obtenida")
        return contexto

    return ""

async def generar_respuesta(mensaje: str, historial: list, asesor: str = "Valentina", telefono: str = "", nombre_cliente: str = "") -> str:
    if not mensaje or len(mensaje.strip()) < 2:
        return obtener_mensaje_fallback()

    system_prompt = construir_system_prompt(asesor=asesor)

    from datetime import datetime
    from zoneinfo import ZoneInfo
    ZONA_CDMX = ZoneInfo("America/Mexico_City")
    ahora = datetime.now(ZONA_CDMX)

    contexto_cliente = f"Cliente: {nombre_cliente if nombre_cliente else 'NO CAPTURADO'}\nTelefono: {telefono if telefono else 'NO DISPONIBLE'}\nHora: {ahora.strftime('%H:%M')}\n"
    system_prompt += "\n" + contexto_cliente

    contexto_precios = await detectar_y_obtener_precios(mensaje)
    if contexto_precios:
        system_prompt += f"\nINFORMACION DE PRECIOS:\n{contexto_precios}"
        logger.info(f"[BRAIN] Precio inyectado")

    mensajes = [{"role": msg.get("role"), "content": msg.get("content")} for msg in historial]
    mensajes.append({"role": "user", "content": mensaje})

    try:
        response = await client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1024,
            system=system_prompt,
            messages=mensajes
        )
        respuesta = response.content[0].text
        logger.info(f"[BRAIN] Respuesta generada")
        return respuesta
    except Exception as e:
        logger.error(f"[BRAIN] Error: {e}")
        return obtener_mensaje_error()

async def generar_mensaje_noshow(telefono: str, nombre_cliente: str, historial: list, cupon: str, fecha_expira: str) -> str:
    system_prompt = construir_system_prompt(asesor="Valentina")
    contexto = f"Cliente no asistio: {nombre_cliente}\nCupon: {cupon} (valido hasta {fecha_expira})\nSe empático pero ofrece segunda oportunidad con descuento."
    system_prompt += "\n" + contexto

    mensajes = [{"role": msg.get("role"), "content": msg.get("content")} for msg in historial]
    mensajes.append({"role": "user", "content": "Cliente no asistio. Envia mensaje de reconexion empatico."})

    try:
        response = await client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1024,
            system=system_prompt,
            messages=mensajes
        )
        respuesta = response.content[0].text
        logger.info(f"[BRAIN] Mensaje noshow generado para {nombre_cliente}")
        return respuesta
    except Exception as e:
        logger.error(f"[BRAIN] Error noshow: {e}")
        return f"Hola {nombre_cliente}, notamos que no asististe a tu cita. Queremos ofrecerte una segunda oportunidad con 10% descuento. Cupon: {cupon}"
