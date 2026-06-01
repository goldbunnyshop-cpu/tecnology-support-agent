# agent/brain.py — Cerebro del agente: conexión con Claude API
# Generado por AgentKit

import os
import re
import yaml
import logging
from anthropic import AsyncAnthropic
from dotenv import load_dotenv
from agent.pricing import obtener_cotizacion_display, buscar_modelo_sin_marca, ALIAS_MARCAS
from agent.pricing_fallback import cotizar_con_fallback

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

# Términos inequívocos de pantalla/display. NO se incluyen "touch"/"táctil" porque
# aparecen en quejas conversacionales de reparación ("el touch muerto") sin intención
# de cotizar — esas las atiende Claude, no el motor de cotización.
_PATRON_DISPLAY = re.compile(
    r"\b(displays?|pantallas?|mica|cristal|gorilla)\b", re.I
)

# Señales de que la consulta NO es de display. El motor de cotización solo cotiza
# PANTALLAS; si el cliente pregunta por mantenimiento de consola, costo de
# diagnóstico, batería, centro de carga, software, o reparación de control, NO debe
# intervenir el motor — lo atiende Claude con las reglas del prompt (precio fijo de
# consola, invitar al módulo, Situación 5, etc.).
_PATRON_NO_DISPLAY = re.compile(
    r"\b("
    r"mantenimiento|limpieza|diagn[oó]stic\w*|"
    r"bater[ií]a|pila|centro\s+de\s+carga|puerto\s+de\s+carga|no\s+carga|"
    r"bocina|altavoz|micr[oó]fono|c[aá]mara|bot[oó]n|botones|"
    r"software|desbloque\w*|liberaci[oó]n|liberar|"
    r"control|mando|joystick|palanca|drift|gatillo|"
    r"consola|playstation|ps[345]|xbox|nintendo|switch"
    r")\b",
    re.I,
)

_PATRON_MODELO_CORTO = re.compile(
    r"^\s*(?:el\s+|del\s+|de\s+)?[a-z]?\d{1,4}(?:\s*(?:\+|plus|ultra|pro|max|fe|lite|neo|mini|se))?\s*\??\s*$",
    re.I,
)

_PATRON_MODELO_EN_TEXTO = re.compile(
    r"\b([a-z]?\d{1,4}(?:\s*(?:\+|plus|ultra|pro|max|fe))?)\b",
    re.I,
)


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
    txt_limpio = _normalizar_consulta_pricing(txt)
    # Primero marcas más largas para evitar colisiones (google pixel antes de pixel)
    for alias in sorted(ALIAS_MARCAS.keys(), key=len, reverse=True):
        if re.search(rf"\b{re.escape(alias)}\b", txt_limpio) or alias in txt_limpio:
            marca = alias
            modelo = re.sub(rf".*?\b{re.escape(alias)}\b", "", txt_limpio, count=1).strip(" :,-")
            if not modelo and alias in txt_limpio:
                modelo = txt_limpio.replace(alias, "").strip(" :,-")
            return marca, (modelo or None)
    # Sin marca explícita, intentar extraer modelo de la frase limpia
    m = _PATRON_MODELO_EN_TEXTO.search(txt_limpio)
    if m:
        return None, m.group(1).strip()
    return None, txt_limpio or None


def _normalizar_consulta_pricing(texto: str) -> str:
    t = (texto or "").lower().strip()
    t = t.replace("¿", " ").replace("?", " ")
    # Corrige typo común detectado en pruebas
    t = t.replace("smsamsung", "samsung")
    # Quita prefijos de intención de precio que contaminan el modelo
    t = re.sub(
        r"^(?:me\s+ayudas?\s+a\s+)?(?:cotizar|cotizacion|cotización|precio|costo|presupuesto)\s+(?:de\s+|del\s+|para\s+)?",
        "",
        t,
    )
    # Limpieza de palabras de relleno frecuentes
    t = re.sub(r"\b(?:tipo|estimado|aprox|aproximado|pantalla|display)\b", " ", t)
    t = re.sub(r"\s+", " ", t).strip(" ,.-")
    return t


def _es_modelo_corto(texto: str) -> bool:
    t = _normalizar_consulta_pricing(texto)
    return bool(_PATRON_MODELO_CORTO.match(t))


def _historial_en_contexto_precio(historial: list[dict]) -> bool:
    if not historial:
        return False
    ultimos = historial[-6:]
    for msg in ultimos:
        if msg.get("role") != "user":
            continue
        c = (msg.get("content") or "").lower()
        if any(re.search(p, c) for p in _PATRONES_PRECIO):
            return True
    return False


def _buscar_ultimo_modelo_historial(historial: list[dict]) -> str | None:
    if not historial:
        return None
    for msg in reversed(historial[-12:]):
        if msg.get("role") != "user":
            continue
        c = _normalizar_consulta_pricing(msg.get("content") or "")
        m = _PATRON_MODELO_EN_TEXTO.search(c)
        if m:
            return m.group(1).strip()
    return None


def _es_respuesta_marca(mensaje: str) -> str | None:
    t = _normalizar_consulta_pricing(mensaje)
    for alias in sorted(ALIAS_MARCAS.keys(), key=len, reverse=True):
        if t == alias:
            return alias
    return None


def _buscar_ultima_marca_historial(historial: list[dict]) -> str | None:
    if not historial:
        return None
    for msg in reversed(historial[-12:]):
        if msg.get("role") != "user":
            continue
        marca = _es_respuesta_marca(msg.get("content") or "")
        if marca:
            return marca
    return None


async def _resolver_pricing_desde_texto(mensaje: str) -> str | None:
    marca, modelo = _extraer_marca_modelo(mensaje)
    # Detectar tipo de pieza para aplicar el multiplicador correcto (tapas ≠ displays)
    refaccion = "tapa" if "tapa" in (mensaje or "").lower() else "display"
    try:
        if marca and modelo:
            r = await cotizar_con_fallback(marca, modelo, refaccion)
            return _limpiar_respuesta_pricing(r)
        if modelo:
            r = await buscar_modelo_sin_marca(modelo)
            return _limpiar_respuesta_pricing(r)
        r = await buscar_modelo_sin_marca(mensaje)
        return _limpiar_respuesta_pricing(r)
    except Exception as e:
        logger.error(f"[PRICING] Error en consulta directa: {e}")
        return None


async def _intentar_respuesta_pricing_contextual(mensaje: str, historial: list[dict]) -> str | None:
    m = (mensaje or "").lower()
    es_consulta_precio = any(re.search(p, m) for p in _PATRONES_PRECIO)
    es_display = bool(_PATRON_DISPLAY.search(m))
    es_no_display = bool(_PATRON_NO_DISPLAY.search(m))
    es_modelo_breve = _es_modelo_corto(mensaje)
    hay_contexto_precio = _historial_en_contexto_precio(historial)
    marca_actual, modelo_actual = _extraer_marca_modelo(mensaje)

    # EXCLUSIÓN: la consulta no es de pantalla → que la maneje Claude, no el motor.
    if es_no_display:
        return None

    # Si este mensaje ya trae modelo y hay intención real de cotizar pantalla
    # (mención de display, palabra de precio, o un modelo corto), resolver con lo
    # ACTUAL. NO se enruta por la sola presencia de una marca: eso desviaba al motor
    # consultas que no eran de pantalla.
    if modelo_actual and (es_display or es_consulta_precio or es_modelo_breve):
        return await _resolver_pricing_desde_texto(mensaje)

    # Pidió pantalla pero sin modelo aún (ej: "cuánto cuesta la pantalla de un iphone").
    if es_display:
        return await _resolver_pricing_desde_texto(mensaje)

    marca_suelta = _es_respuesta_marca(mensaje)
    modelo_prev = _buscar_ultimo_modelo_historial(historial)
    marca_prev = _buscar_ultima_marca_historial(historial)

    if not es_consulta_precio and not (es_modelo_breve and (hay_contexto_precio or marca_prev)) and not (marca_suelta and modelo_prev):
        return None

    # Caso conversacional: cliente responde solo marca después de "costo s21"
    if marca_suelta and modelo_prev:
        try:
            r = await cotizar_con_fallback(marca_suelta, modelo_prev)
            return _limpiar_respuesta_pricing(r)
        except Exception as e:
            logger.error(f"[PRICING] Error resolviendo marca+modelo contextual: {e}")

    # Caso conversacional inverso: cliente responde solo modelo corto tras decir marca
    if es_modelo_breve and marca_prev:
        try:
            r = await cotizar_con_fallback(marca_prev, _normalizar_consulta_pricing(mensaje))
            return _limpiar_respuesta_pricing(r)
        except Exception as e:
            logger.error(f"[PRICING] Error resolviendo modelo con marca contextual: {e}")

    return await _resolver_pricing_desde_texto(mensaje)


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
    respuesta_pricing = await _intentar_respuesta_pricing_contextual(mensaje, historial)
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
