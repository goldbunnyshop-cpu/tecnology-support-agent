# agent/brain.py — Cerebro del agente: conexión con Claude API
# Generado por AgentKit

import os
import re
import yaml
import asyncio
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
# NUEVA: También detecta "cambio pantalla" (aun entre paréntesis)
_PATRON_DISPLAY = re.compile(
    r"(?:\b(displays?|pantallas?|mica|cristal|gorilla)\b|cambio\s+(?:de\s+)?(pantalla|display))", re.I
)

# Señales de que la consulta NO es de display. El motor de cotización ahora cotiza
# PANTALLAS + BATERÍAS DE CELULAR (via Google Sheets).
# Si el cliente pregunta por: mantenimiento de consola, diagnóstico, centro de carga,
# software, o reparación de control → Claude atiende (precio fijo, invitar módulo, etc.)
_PATRON_NO_DISPLAY = re.compile(
    r"\b("
    r"mantenimiento|limpieza|diagn[oó]stic\w*|"
    r"pila|centro\s+de\s+carga|puerto\s+de\s+carga|no\s+carga|"
    r"bocina|altavoz|micr[oó]fono|c[aá]mara|bot[oó]n|botones|"
    r"software|desbloque\w*|liberaci[oó]n|liberar|"
    r"control|mando|joystick|palanca|drift|gatillo|"
    r"consola|playstation|ps[345]|xbox|nintendo|switch"
    r")\b",
    re.I,
)

_PATRON_MODELO_CORTO = re.compile(
    r"^\s*(?:el\s+|del\s+|de\s+|es\s+un\s+|tengo\s+un\s+)?"
    r"[a-z]?\d{1,4}"
    r"(?:\s*(?:\+|plus|ultra|pro|max|fe|lite|neo|mini|se)){0,2}"  # hasta 2 variantes: "pro max"
    r"\s*\??\s*$",
    re.I,
)

_PATRON_MODELO_EN_TEXTO = re.compile(
    r"\b([a-z]?\d{1,4}(?:\s*(?:\+|plus|ultra|pro|max|fe|lite|neo|mini|se)){0,2})\b",
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


def _modelo_plausible(modelo: str | None) -> str | None:
    """Un modelo válido tiene al menos un dígito (14, a54, edge 40, p30...).

    Evita que frases de relleno ('hola cuanto cuesta la de un') se cuelen como
    'modelo' y generen cotizaciones corruptas. Si no hay dígito → no es modelo.
    """
    if not modelo:
        return None
    modelo = modelo.strip(" :,-")
    return modelo if re.search(r"\d", modelo) else None


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
            # Solo aceptar el modelo si parece un modelo real (tiene dígito);
            # de lo contrario marca conocida pero sin modelo → se pedirá el modelo.
            return marca, _modelo_plausible(modelo)
    # Sin marca explícita, intentar extraer modelo de la frase limpia
    m = _PATRON_MODELO_EN_TEXTO.search(txt_limpio)
    if m:
        return None, m.group(1).strip()
    return None, _modelo_plausible(txt_limpio)


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
    """Busca el ÚLTIMO modelo mencionado en el historial (últimos 20 mensajes = contexto de sesión)."""
    if not historial:
        return None
    # Buscar en los últimos 20 mensajes para abarcar toda una sesión conversacional
    for msg in reversed(historial[-20:]):
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
    """Busca la ÚLTIMA marca mencionada en el historial (últimos 20 mensajes = contexto de sesión).

    Detecta la marca aunque venga dentro de una frase ("pantalla de un iphone 14"),
    no solo cuando el cliente respondió únicamente la marca. Así el contexto de marca
    persiste durante toda la conversación.
    """
    if not historial:
        return None
    # Buscar en los últimos 20 mensajes
    for msg in reversed(historial[-20:]):
        if msg.get("role") != "user":
            continue
        contenido = msg.get("content") or ""
        # Primero marca-sola; si no, extraer marca de la frase completa.
        marca = _es_respuesta_marca(contenido) or _extraer_marca_modelo(contenido)[0]
        if marca:
            return marca
    return None


def _generar_pregunta_clarificadora(mensaje: str, marca_prev: str | None, modelo_prev: str | None) -> str | None:
    """Genera una pregunta clarificadora inteligente cuando hay contexto pero falta especificidad.

    Ej: Si cliente pregunta "¿precio?" y hace poco preguntó sobre un S21, retorna:
    "¿Del Samsung S21?" en lugar de delegar a Claude.
    """
    m = (mensaje or "").lower()
    es_consulta_precio = any(re.search(p, m) for p in _PATRONES_PRECIO)

    if not es_consulta_precio:
        return None

    # Si pregunta "¿precio?" o similar SIN especificar dispositivo, pero hay contexto anterior
    if marca_prev and modelo_prev:
        dispositivo = f"{marca_prev} {modelo_prev}".strip().title()
        # Detectar si pregunta por refacción específica
        refaccion = "display"
        if re.search(r"\b(bater[ií]a|bateria|pila)\b", m):
            refaccion = "batería"
        elif re.search(r"\b(tapa)\b", m):
            refaccion = "tapa"

        if refaccion == "display":
            return f"¿Del display del {dispositivo}?"
        else:
            return f"¿De la {refaccion} del {dispositivo}?"

    return None


def _detectar_refaccion(mensaje: str) -> str:
    """Tipo de pieza solicitada: bateria > tapa > display (default)."""
    m = (mensaje or "").lower()
    if re.search(r"\b(bater[ií]a|bateria|pila)\b", m):
        return "bateria"
    if "tapa" in m:
        return "tapa"
    return "display"


async def _resolver_pricing_desde_texto(mensaje: str, marca_ctx: str | None = None) -> str | None:
    marca, modelo = _extraer_marca_modelo(mensaje)
    # Si el mensaje no trae marca pero la conversación ya la estableció, usarla.
    if not marca and marca_ctx:
        marca = marca_ctx
    refaccion = _detectar_refaccion(mensaje)
    m = (mensaje or "").lower()
    try:
        logger.info(f"[PRICING] RESOLVER_PRICING: marca='{marca}', modelo='{modelo}', refaccion='{refaccion}'")
        if marca and modelo:
            # SIEMPRE usar cotizar_con_fallback para acceder a Google Sheets
            logger.info(f"[PRICING] Llamando cotizar_con_fallback(marca='{marca}', modelo='{modelo}', refaccion='{refaccion}')")
            r = await cotizar_con_fallback(marca, modelo, refaccion)
            logger.info(f"[PRICING] Respuesta fallback: {r[:100] if r else 'None'}")
            return _limpiar_respuesta_pricing(r)
        if modelo:
            # FIX: Usar cotizar_con_fallback incluso sin marca (Hugo Shop → Google Sheets)
            logger.info(f"[PRICING] Llamando cotizar_con_fallback(marca='', modelo='{modelo}', refaccion='{refaccion}')")
            r = await cotizar_con_fallback("", modelo, refaccion)
            logger.info(f"[PRICING] Respuesta fallback: {r[:100] if r else 'None'}")
            return _limpiar_respuesta_pricing(r)
        # Sin modelo: pedir información
        logger.info(f"[PRICING] Sin modelo específico, usando mensaje completo")
        r = await cotizar_con_fallback("", mensaje, refaccion)
        logger.info(f"[PRICING] Respuesta fallback: {r[:100] if r else 'None'}")
        return _limpiar_respuesta_pricing(r)
    except Exception as e:
        logger.error(f"[PRICING] Error en consulta directa: {e}", exc_info=True)
        return None


async def _intentar_respuesta_pricing_contextual(mensaje: str, historial: list[dict]) -> str | None:
    m = (mensaje or "").lower()
    es_consulta_precio = any(re.search(p, m) for p in _PATRONES_PRECIO)
    es_display = bool(_PATRON_DISPLAY.search(m))
    es_no_display = bool(_PATRON_NO_DISPLAY.search(m))
    es_modelo_breve = _es_modelo_corto(mensaje)
    hay_contexto_precio = _historial_en_contexto_precio(historial)
    marca_actual, modelo_actual = _extraer_marca_modelo(mensaje)

    # LOG DETALLADO: Rastrear decisión del motor de pricing
    logger.info(f"[PRICING-DEBUG] Mensaje: '{mensaje}'")
    logger.info(f"[PRICING-DEBUG] es_consulta_precio={es_consulta_precio}, es_display={es_display}, es_no_display={es_no_display}, es_modelo_breve={es_modelo_breve}")
    logger.info(f"[PRICING-DEBUG] marca_actual='{marca_actual}', modelo_actual='{modelo_actual}'")

    # CRÍTICO: Si menciona display/pantalla/cambio pantalla EXPLÍCITAMENTE,
    # eso tiene prioridad sobre mencionar casualmente "PS5" o "consola".
    # Ej: "iPad (cambio pantalla) controles de PS5" = consulta de display, no de PS5
    if es_display:
        # Es una consulta de display → el motor la maneja, ignora es_no_display
        logger.info(f"[PRICING-DEBUG] Detectado: DISPLAY explícito → motor de pricing")
        pass
    elif es_no_display:
        # NO menciona display y SÍ menciona exclusión → que la maneje Claude
        logger.info(f"[PRICING-DEBUG] Detectado: NO_DISPLAY → delegando a Claude")
        return None

    # Si este mensaje ya trae modelo y hay intención real de cotizar pantalla
    # (mención de display, palabra de precio, o un modelo corto), resolver con lo
    # ACTUAL. NO se enruta por la sola presencia de una marca: eso desviaba al motor
    # consultas que no eran de pantalla.
    if modelo_actual and (es_display or es_consulta_precio or es_modelo_breve):
        # Si el mensaje trae modelo pero no marca, heredar la marca del contexto
        # (ej. cliente respondió "14 pro max" tras hablar del iPhone). Sin esto la
        # búsqueda sin marca matcheaba productos equivocados / precios absurdos.
        marca_ctx = marca_actual or _buscar_ultima_marca_historial(historial)
        return await _resolver_pricing_desde_texto(mensaje, marca_ctx)

    # Pidió pantalla pero sin modelo aún (ej: "cuánto cuesta la pantalla de un iphone").
    if es_display:
        return await _resolver_pricing_desde_texto(mensaje)

    marca_suelta = _es_respuesta_marca(mensaje)
    modelo_prev = _buscar_ultimo_modelo_historial(historial)
    marca_prev = _buscar_ultima_marca_historial(historial)

    # ── NUEVO: Si dice solo "también batería", "también display", "también tapa" ──
    # Reutiliza marca+modelo anterior pero cambia la refacción
    if (marca_prev and modelo_prev) and not marca_actual and not modelo_actual:
        m_lower = m.lower()
        # Detectar si es SOLO cambio de refacción sin nuevo dispositivo
        # FIX: Incluir "bateria" sin acento + "batería" con acento
        if re.search(r"\b(también|tambien|ademas|además|y)\s+(?:la\s+|el\s+|de\s+)?(bater[ií]a|bateria|pila|display|pantalla|tapa)", m_lower):
            # Extraer qué refacción pide
            if re.search(r"\b(bater[ií]a|pila)\b", m_lower):
                refaccion = "bateria"
            elif re.search(r"\b(tapa)\b", m_lower):
                refaccion = "tapa"
            else:
                refaccion = "display"
            try:
                logger.info(f"[PRICING] Reutilizando contexto: {marca_prev} {modelo_prev}, cambiando a refacción='{refaccion}'")
                r = await cotizar_con_fallback(marca_prev, modelo_prev, refaccion)
                return _limpiar_respuesta_pricing(r)
            except Exception as e:
                logger.error(f"[PRICING] Error en cotización contextual con refacción: {e}")

    # ── MEJORA: Caso conversacional: cliente responde solo marca después de "costo s21" ──
    if marca_suelta and modelo_prev:
        try:
            logger.info(f"[PRICING-DEBUG] Caso conversacional: marca='{marca_suelta}' + modelo_prev='{modelo_prev}'")
            r = await cotizar_con_fallback(marca_suelta, modelo_prev)
            logger.info(f"[PRICING-DEBUG] Retornando respuesta contextual")
            return _limpiar_respuesta_pricing(r)
        except Exception as e:
            logger.error(f"[PRICING] Error resolviendo marca+modelo contextual: {e}")

    # ── MEJORA: Caso conversacional inverso: cliente responde solo modelo corto tras decir marca ──
    if es_modelo_breve and marca_prev:
        try:
            logger.info(f"[PRICING-DEBUG] Caso conversacional: modelo_breve + marca_prev='{marca_prev}'")
            r = await cotizar_con_fallback(marca_prev, _normalizar_consulta_pricing(mensaje))
            logger.info(f"[PRICING-DEBUG] Retornando respuesta contextual")
            return _limpiar_respuesta_pricing(r)
        except Exception as e:
            logger.error(f"[PRICING] Error resolviendo modelo con marca contextual: {e}")

    # ── NUEVA MEJORA: Preguntas clarificadoras inteligentes ──
    # Si es una consulta de precio vaga pero hay contexto de dispositivo anterior,
    # no delegar a Claude: hacer pregunta clarificadora ("¿Del Samsung S21?")
    if es_consulta_precio and not modelo_actual and (marca_prev or modelo_prev):
        pregunta = _generar_pregunta_clarificadora(mensaje, marca_prev, modelo_prev)
        if pregunta:
            logger.info(f"[PRICING-DEBUG] Pregunta clarificadora generada: '{pregunta}'")
            return pregunta  # Retorna como respuesta de pricing directa

    # Última evaluación: si NO es claramente una consulta de precio
    if not es_consulta_precio and not (es_modelo_breve and (hay_contexto_precio or marca_prev)) and not (marca_suelta and modelo_prev):
        logger.info(f"[PRICING-DEBUG] NO ES CONSULTA PRECIO → delegando a Claude")
        return None

    logger.info(f"[PRICING-DEBUG] Llamando _resolver_pricing_desde_texto()")
    respuesta = await _resolver_pricing_desde_texto(mensaje)
    if respuesta:
        logger.info(f"[PRICING-DEBUG] ✅ PRICING RETORNÓ RESPUESTA")
        return respuesta
    logger.info(f"[PRICING-DEBUG] ❌ PRICING NO ENCONTRÓ NADA → delegando a Claude")
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
    respuesta_pricing = await _intentar_respuesta_pricing_contextual(mensaje, historial)
    if respuesta_pricing:
        logger.info(f"[{asesor}] Respuesta de pricing directa aplicada")
        return respuesta_pricing

    system_prompt = construir_system_prompt(asesor)
    if contexto_cliente:
        system_prompt = f"{contexto_cliente}\n\n{system_prompt}"

    mensajes = [{"role": m["role"], "content": m["content"]} for m in historial]
    mensajes.append({"role": "user", "content": mensaje})

    # Retry logic: reintentar si error 529 (Overloaded) o timeout
    max_intentos = 3
    espera_inicial = 1  # segundos

    for intento in range(max_intentos):
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
            error_str = str(e).lower()
            # Si es error 529 (Overloaded) o timeout, reintentar con backoff
            if ("529" in str(e) or "overload" in error_str or "timeout" in error_str) and intento < max_intentos - 1:
                espera = espera_inicial * (2 ** intento)  # exponential backoff: 1s, 2s, 4s
                logger.warning(f"[{asesor}] Error transitorio (intento {intento + 1}/{max_intentos}): {e}")
                logger.info(f"[{asesor}] Reintentando en {espera} segundos...")
                await asyncio.sleep(espera)
                continue

            # Si es otro error o último intento fallido, retornar error
            logger.error(f"[{asesor}] Error Claude API (intento {intento + 1}/{max_intentos}): {e}")
            return obtener_mensaje_error()
