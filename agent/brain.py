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


def _inferir_marca_de_modelo(modelo_str: str) -> str | None:
    """Infiere la marca desde modelos conocidos sin necesidad de marca explícita.

    Ejemplos:
      's23' -> 'Samsung', 's21' -> 'Samsung', 'a21' -> 'Samsung'
      'e60' -> 'Hisense', 'v60' -> 'Hisense'
      '14' -> 'iPhone', '15 pro' -> 'iPhone'
      'edge 20' -> 'Motorola'
    """
    if not modelo_str:
        return None

    m = modelo_str.lower().strip()

    # Patrones Samsung: s[0-9], a[0-9], m[0-9], z[0-9], etc.
    if re.match(r'^[sazm]\d+', m):
        return "Samsung"

    # Patrones Hisense: e[0-9], v[0-9], h[0-9]
    if re.match(r'^[evh]\d+', m):
        return "Hisense"

    # iPhone: numeros puros o con sufijo (14, 15 pro, 15 max)
    if re.match(r'^\d+', m) and 'iphone' not in m and 'samsung' not in m:
        return "iPhone"

    # Motorola/Moto: edge, moto g, moto e
    if 'edge' in m or re.match(r'^g\d+|^e\d+|^gx|^ex', m):
        return "Motorola"

    # Google Pixel: pixel [0-9]
    if 'pixel' in m:
        return "Google"

    return None


async def detectar_y_obtener_precios(mensaje: str) -> str:
    """Detecta precios por keywords O por marca+modelo.

    Flujo DUAL (optimizado):
    1. Intentar detección explícita: marca + modelo en el mensaje
    2. Si NO hay marca explícita pero SÍ hay pregunta de precio: buscar solo por modelo (fallback)
    """
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

    # ====== OPCION 1: Busqueda con marca explícita ======
    patron_modelo = r'(iPhone|Samsung|Google Pixel|Pixel|OnePlus|Xiaomi|Motorola|Huawei|Nokia|LG|Moto|Poco|Redmi|Hisense|Honor|Oppo|Realme|TCL|Vivo|ZTE|Alcatel|Cubot)\s+([\w]+(?:\s+[\w]+){0,3})'
    match = re.search(patron_modelo, mensaje, re.IGNORECASE)

    if match:
        marca = match.group(1)
        modelo = match.group(2).strip()
        logger.info(f"[BRAIN] Marca+modelo detectado explícitamente: {marca} {modelo}")

        msg_confirmacion, fue_ambiguo = _confirmar_variante_amb(modelo)
        if fue_ambiguo:
            return msg_confirmacion

        cotizacion = await obtener_cotizacion_display(marca, modelo)
        if cotizacion:
            contexto = f"PRECIO ENCONTRADO PARA {marca.upper()} {modelo.upper()}:\n{cotizacion}"
            logger.info(f"[BRAIN] Cotizacion obtenida (marca explícita)")
            return contexto
        return ""

    # ====== OPCION 2: Fallback sin marca (si es pregunta de precio) ======
    if es_pregunta_precio:
        logger.info(f"[BRAIN] Pregunta de precio sin marca explícita → intentando fallback")
        # Extraer el modelo del mensaje (sin marca)
        # Patrones: s23, a21, edge 50, pixel 8, etc.
        patron_modelo_solo = r'([a-z]\d+(?:\s+\w+)?|edge\s+\d+|moto\s+[a-z]\d+|pixel\s+\d+|\d+\s+(?:pro|max|ultra|lite|neo|fusion))'
        match_modelo = re.search(patron_modelo_solo, mensaje_lower)

        if match_modelo:
            modelo = match_modelo.group(0).strip()
            logger.info(f"[BRAIN] Modelo sin marca detectado: '{modelo}' → búsqueda dual activada")

            from agent.pricing import buscar_modelo_sin_marca
            cotizacion = await buscar_modelo_sin_marca(modelo)
            if cotizacion:
                contexto = f"BUSQUEDA POR MODELO (sin marca explícita):\n{cotizacion}"
                logger.info(f"[BRAIN] Cotizacion obtenida (búsqueda por modelo)")
                return contexto

    logger.debug(f"[BRAIN] Mensaje sin precio/modelo detectado")
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
