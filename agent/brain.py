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
    r"\btouch\b",
    r"\bcristal\b",
    r"\bmica\b",
]

# Términos inequívocos de pantalla/display. NO se incluyen "touch"/"táctil" porque
# aparecen en quejas conversacionales de reparación ("el touch muerto") sin intención
# de cotizar — esas las atiende Claude, no el motor de cotización.
# NUEVA: También detecta "cambio pantalla" (aun entre paréntesis), touch y cristal.
_PATRON_DISPLAY = re.compile(
    r"(?:\b(displays?|pantallas?|mica|gorilla|touch|cristal)\b"
    r"|cambio\s+(?:de\s+)?(pantalla|display|touch|cristal))",
    re.I,
)

# Display inequívoco: display/pantalla/mica/gorilla (no necesitan confirmación).
_PATRON_DISPLAY_DIRECTO = re.compile(
    r"(?:\b(displays?|pantallas?|mica|gorilla)\b"
    r"|cambio\s+(?:de\s+)?(pantalla|display))",
    re.I,
)

# Términos de pantalla que pueden ser ambiguos y requieren confirmación verbal:
# - "cristal" puede ser cristal de cámara o vidrio de pantalla
# - "touch" puede ser queja de falla o cotización de pantalla
_PATRON_DISPLAY_CONFIRMAR = re.compile(
    r"\b(touch|cristal)\b",
    re.I,
)

# Cristal/vidrio de CÁMARA: no es display → siempre técnico
_PATRON_CRISTAL_CAMARA = re.compile(
    r"\b(cristal|vidrio)\s+(?:de\s+)?(?:la\s+)?c[aá]mara\b",
    re.I,
)

# ── Refacciones que SIEMPRE van al técnico (nunca se cotizan por el motor) ──────
# Todo lo que no sea display/pantalla/touch/cristal de celular.
_PATRON_REFACCION_TECNICO = re.compile(
    r"\b("
    r"bater[ií]a|bateria|"
    r"tapa|carcasa|back\s*cover|cubierta|contorno|marco(?!\s+gorilla)|"  # "marco" de display OK si va con gorilla
    r"puerto|conector|centro\s+de\s+carga|cargador|"
    r"bocina|altavoz|aud[ií]fono|auricular|speaker|"
    r"micr[oó]fono|"
    r"c[aá]mara|lente(?!\s+gorilla)|vidrio\s+c[aá]mara|"
    r"bot[oó]n|boton|vibrador|antena|flex|"
    r"SIM|ranura|charger"
    r")\b",
    re.I,
)

# Mensaje estándar cuando la pieza requiere cotización directa del técnico
_MENSAJE_TECNICO_30MIN = (
    "En un lapso no mayor a 30 minutos un técnico especialista te atenderá personalmente 😊\n"
    "¿Prefieres que te contactemos por llamada o seguimos por WhatsApp?"
)

# Señales de que la consulta NO es de display ni refacción cotizable.
# El motor la ignora y Claude atiende (precio fijo de servicio, consola, software, etc.)
_PATRON_NO_DISPLAY = re.compile(
    r"\b("
    r"mantenimiento|limpieza|diagn[oó]stic\w*|"
    r"pila|no\s+carga|"
    r"software|desbloque\w*|liberaci[oó]n|liberar|"
    r"control|mando|joystick|palanca|drift|gatillo|"
    r"consola|playstation|ps[345]|xbox|nintendo|switch"
    r")\b",
    re.I,
)

# Palabras clave de laptop/PC. Si el historial reciente las contiene y el mensaje
# actual no trae una marca de celular explícita, el motor de precios de pantallas
# de celular NO debe dispararse.
_PATRON_LAPTOP_PC = re.compile(
    r"\b(laptop|lapto|notebook|computadora|pc\s*gamer|desktop|macbook|lenovo|dell|asus|acer|msi|gaming\s*\d)\b",
    re.I,
)


def _es_contexto_laptop_pc(historial: list[dict]) -> bool:
    """True si los últimos mensajes sugieren que el dispositivo es una laptop o PC."""
    for msg in (historial or [])[-8:]:
        if _PATRON_LAPTOP_PC.search(msg.get("content") or ""):
            return True
    return False

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
    tokens = txt_limpio.split()
    # Primero marcas más largas para evitar colisiones (google pixel antes de pixel)
    for alias in sorted(ALIAS_MARCAS.keys(), key=len, reverse=True):
        alias_tokens = alias.split()
        n = len(alias_tokens)
        for i in range(len(tokens) - n + 1):
            ventana = tokens[i:i + n]
            coincide = ventana == alias_tokens
            if not coincide and n == 1 and len(alias) >= 4:
                # Typo tolerante: "oppor" ~ "oppo", "iphonee" ~ "iphone"
                tok = tokens[i]
                coincide = tok.startswith(alias) and len(tok) <= len(alias) + 2
            if coincide:
                marca = alias
                resto = tokens[i + n:]
                if not resto:
                    resto = tokens[:i]
                # FIX: Limpiar puntuación y filtrar palabras de conversación.
                # Caso: "tengo un moto E32, ¿cuánto cuesta?" → tokens resto:
                # ["e32,", "cuánto", "cuesta"] → queremos solo ["e32"].
                # La coma pegada a "e32," rompe todos los regex de matching.
                modelo = _extraer_modelo_de_tokens(resto)
                # Solo aceptar el modelo si parece un modelo real (tiene dígito);
                # de lo contrario marca conocida pero sin modelo → se pedirá el modelo.
                return marca, _modelo_plausible(modelo)
    # Sin marca explícita, intentar extraer modelo de la frase limpia
    m = _PATRON_MODELO_EN_TEXTO.search(txt_limpio)
    if m:
        return None, m.group(1).strip()
    return None, _modelo_plausible(txt_limpio)


# Palabras conversacionales que NO son parte del modelo de un dispositivo.
# Al encontrar una de estas después de ya tener tokens de modelo, se para.
_CHATARRA_MODELO = {
    # Palabras de precio/cotización
    'precio', 'precios', 'costo', 'costos', 'cotizar', 'cotizacion', 'cotización',
    'presupuesto', 'cuánto', 'cuanto', 'cuesta', 'cuestan', 'sale', 'salen', 'vale',
    # Artículos y pronombres
    'la', 'el', 'los', 'las', 'lo', 'le', 'les',
    'me', 'te', 'se', 'nos',
    'mi', 'su', 'sus', 'mis', 'tu', 'tus',
    'un', 'una', 'unos', 'unas',
    # Verbos frecuentes
    'tengo', 'tiene', 'tienen', 'tener',
    'es', 'son', 'hay', 'hay',
    'pueden', 'puede', 'puedo',
    # Preposiciones y conjunciones
    'para', 'de', 'del', 'al', 'a', 'en',
    'con', 'sin', 'por', 'que', 'qué',
    'como', 'cómo', 'y', 'o', 'e',
    # Adverbios y otros
    'ya', 'si', 'no', 'favor',
    'porfavor', 'porfa', 'please',
    # Saludos
    'hola', 'buen', 'buenas', 'buenos', 'dias', 'días', 'tardes', 'noches',
    # Pronombres demostrativos
    'esta', 'este', 'esto', 'eso', 'esa', 'ese', 'esos', 'esas',
}


def _extraer_modelo_de_tokens(tokens: list[str]) -> str:
    """Extrae el nombre del modelo de una lista de tokens, descartando palabras
    conversacionales y limpiando puntuación residual.

    Ej: ["e32,", "cuánto", "cuesta", "la"] → "e32"
    Ej: ["edge", "40", "neo", "cuesta"] → "edge 40 neo"
    Ej: ["14", "pro", "max", "tengo"] → "14 pro max"
    """
    modelo_tokens: list[str] = []
    for tok in tokens:
        # Quitar puntuación pegada al token (coma, punto, signos de pregunta, etc.)
        tok_clean = re.sub(r'[,;:!?¡¿\(\)\[\]"\']+', '', tok).strip()
        if not tok_clean:
            continue
        if tok_clean in _CHATARRA_MODELO:
            # Si ya acumulamos tokens de modelo, parar aquí.
            # Si aún no tenemos modelo, ignorar esta palabra y seguir buscando.
            if modelo_tokens:
                break
            continue
        modelo_tokens.append(tok_clean)
    return " ".join(modelo_tokens).strip(" :,-")


def _normalizar_consulta_pricing(texto: str) -> str:
    t = (texto or "").lower().strip()
    t = t.replace("¿", " ").replace("?", " ")
    # Corrige typo común detectado en pruebas
    t = t.replace("smsamsung", "samsung")
    # Quita prefijos de intención de precio que contaminan el modelo
    # (incluye variantes/typos de "quiero": "qiero", "qjiero", etc.)
    t = re.sub(
        r"^(?:me\s+ayudas?\s+a\s+|q[a-z]{0,2}iero\s+|quisiera\s+|necesito\s+|deseo\s+|"
        r"me\s+puedes?\s+|podr[ií]as?\s+)*"
        r"(?:cotizar|cotizacion|cotización|precio|costo|presupuesto)\s+(?:de\s+|del\s+|para\s+|un\s+|una\s+)?",
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


# Patrón para extraer modelo del tag de visión almacenado en historial de asistente.
# Ej: "[imagen: celular Xiaomi Redmi 13 - pantalla rota]" → grupo 1 = "Redmi 13"
_PATRON_VISION_HISTORIAL = re.compile(
    r"\[imagen:\s*\w+\s+\S+\s+([^\-\]]+?)\s*(?:-|\])",
    re.I,
)


def _extraer_modelo_de_tag_vision(contenido: str) -> str | None:
    """Extrae el modelo del texto '[imagen: celular MARCA MODELO - daño]' en mensajes de asistente."""
    m = _PATRON_VISION_HISTORIAL.search(contenido or "")
    if not m:
        return None
    candidato = m.group(1).strip()
    # Filtrar palabras genéricas que no son modelos
    _EXCLUIR = {"serie", "gama", "media", "alta", "baja", "otro", "otra", "no", "determinado"}
    if candidato.lower() in _EXCLUIR:
        return None
    # Validar: debe contener al menos un dígito para ser un modelo específico
    if re.search(r"\d", candidato):
        return candidato
    return None


def _buscar_ultimo_modelo_historial(historial: list[dict]) -> str | None:
    """Busca el ÚLTIMO modelo mencionado en el historial (últimos 20 mensajes).

    Busca en:
    1. Mensajes del USER (el cliente dice su modelo)
    2. Mensajes del ASSISTANT que contienen tags [imagen: ...] con el modelo detectado por visión
    """
    if not historial:
        return None
    for msg in reversed(historial[-20:]):
        contenido = msg.get("content") or ""
        rol = msg.get("role", "")

        # En mensajes de asistente: buscar tag de visión
        if rol == "assistant":
            modelo_vision = _extraer_modelo_de_tag_vision(contenido)
            if modelo_vision:
                # Extraer solo la parte numérica+variante del modelo (ej "Redmi 13" → "13")
                m = _PATRON_MODELO_EN_TEXTO.search(modelo_vision)
                if m:
                    return m.group(1).strip()
            continue

        # En mensajes de usuario: patrón normal
        if rol != "user":
            continue
        c = _normalizar_consulta_pricing(contenido)
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
    """Busca la ÚLTIMA marca mencionada en el historial (últimos 20 mensajes).

    Busca en:
    1. Mensajes del ASSISTANT con tag [imagen: celular MARCA ...] (visión detectó la marca)
    2. Mensajes del USER (cliente escribe la marca)
    """
    if not historial:
        return None
    for msg in reversed(historial[-20:]):
        contenido = msg.get("content") or ""
        rol = msg.get("role", "")

        # En mensajes de asistente: buscar tag de visión — la marca está después de "celular/consola/etc"
        if rol == "assistant" and "[imagen:" in contenido:
            # Ej: "[imagen: celular Xiaomi Redmi 13 - pantalla rota]"
            # Extraer la palabra inmediatamente tras el tipo de dispositivo
            m = re.search(
                r"\[imagen:\s*(?:celular|consola|laptop|tablet|otro)\s+(\S+)",
                contenido, re.I,
            )
            if m:
                candidato = m.group(1).strip().lower()
                # Verificar si es una marca conocida
                marca_norm = ALIAS_MARCAS.get(candidato)
                if marca_norm:
                    return marca_norm
            continue

        # En mensajes de usuario
        if rol != "user":
            continue
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
        refaccion = _detectar_refaccion(m)
        if refaccion in ("display", "display_confirmar"):
            pieza_txt = "display" if refaccion == "display" else "pantalla (touch/cristal)"
            return f"¿Del {pieza_txt} del {dispositivo}?"
        else:
            return None  # Para otras piezas no generar pregunta de precio — el técnico atiende

    return None


def _detectar_refaccion(mensaje: str) -> str:
    """
    Tipo de pieza solicitada.
    Retorna:
      "display"          — pantalla/display/mica/gorilla: se cotiza directamente.
      "display_confirmar" — touch/cristal sin contexto de cámara: cotizar pero
                            el prompts.yaml indica al agente que confirme antes.
      "otro"             — cualquier otra pieza (batería, tapa, puerto, bocina…):
                            siempre se transfiere al técnico, no se cotiza.
    """
    m = (mensaje or "").lower()
    # Cristal de cámara → pieza diferente, no es display
    if _PATRON_CRISTAL_CAMARA.search(m):
        return "otro"
    # Display directo (inequívoco)
    if _PATRON_DISPLAY_DIRECTO.search(m):
        return "display"
    # Touch o cristal a secas → probablemente pantalla, confirmar
    if _PATRON_DISPLAY_CONFIRMAR.search(m):
        return "display_confirmar"
    # Otras refacciones conocidas
    if _PATRON_REFACCION_TECNICO.search(m):
        return "otro"
    return "display"  # default: la mayoría de consultas son de display


def _nombre_pieza_tecnico(mensaje: str) -> str:
    """Extrae el nombre legible de la pieza no-display para el mensaje al cliente."""
    m = (mensaje or "").lower()
    if re.search(r"\b(bater[ií]a|bateria)\b", m): return "batería"
    if re.search(r"\bpila\b", m): return "batería"
    if re.search(r"\b(tapa|carcasa|back\s*cover|cubierta)\b", m): return "tapa trasera"
    if re.search(r"\b(puerto|conector|centro\s+de\s+carga|cargador|charger)\b", m): return "puerto de carga"
    if re.search(r"\b(bocina|altavoz|speaker|aud[ií]fono|auricular)\b", m): return "bocina"
    if re.search(r"\b(micr[oó]fono)\b", m): return "micrófono"
    if re.search(r"\b(c[aá]mara|lente|cristal\s+c[aá]mara|vidrio\s+c[aá]mara)\b", m): return "cámara"
    if re.search(r"\b(bot[oó]n|boton)\b", m): return "botón"
    return "refacción"


async def _resolver_pricing_desde_texto(mensaje: str, marca_ctx: str | None = None) -> str | None:
    marca, modelo = _extraer_marca_modelo(mensaje)
    # Si el mensaje no trae marca pero la conversación ya la estableció, usarla.
    if not marca and marca_ctx:
        marca = marca_ctx
    refaccion = _detectar_refaccion(mensaje)
    m = (mensaje or "").lower()

    # ── Pieza no-display: siempre al técnico, sin consultar precios ──────────────
    # Si pide SOLO refacción no-display (batería, tapa, puerto, bocina, etc.),
    # transferir directamente al técnico. No usar Sheets ni fixoem.
    if refaccion == "otro":
        pieza = _nombre_pieza_tecnico(mensaje)
        logger.info(f"[PRICING] Pieza no-display '{pieza}' → transfiriendo al técnico")
        return (
            f"Para la cotización de *{pieza}* necesito confirmarte el precio exacto con el técnico. "
            f"{_MENSAJE_TECNICO_30MIN}"
        )

    # ── Solicitud COMBINADA: display + otra pieza ─────────────────────────────────
    # Ej: "cuánto la pantalla y la batería del S22?"
    # → cotizar el display y avisar que la otra pieza la cotiza el técnico.
    hay_otra_pieza = bool(_PATRON_REFACCION_TECNICO.search(m)) or bool(_PATRON_CRISTAL_CAMARA.search(m))
    if hay_otra_pieza and refaccion in ("display", "display_confirmar"):
        pieza_extra = _nombre_pieza_tecnico(mensaje)
        logger.info(f"[PRICING] Solicitud combinada: display + '{pieza_extra}' → cotizar display, técnico para el resto")
        # Continúa el flujo normal de display, y al final agrega nota del técnico.
        # Se señala con un flag en el resultado para que _limpiar_respuesta_pricing lo maneje.
        # Aquí usamos un prefijo especial que se procesa abajo.
        pass  # el flujo de display sigue; la nota se agrega al retornar.

    # refaccion "display_confirmar" → tratar igual que "display" en la consulta de precio
    # (la confirmación de voz la maneja el system prompt de Claude)
    refaccion_api = "display"

    try:
        logger.info(f"[PRICING] RESOLVER_PRICING: marca='{marca}', modelo='{modelo}', refaccion='{refaccion_api}'")
        if marca and modelo:
            logger.info(f"[PRICING] Llamando cotizar_con_fallback(marca='{marca}', modelo='{modelo}', refaccion='{refaccion_api}')")
            r = await cotizar_con_fallback(marca, modelo, refaccion_api)
            logger.info(f"[PRICING] Respuesta fallback: {r[:100] if r else 'None'}")
            resultado = _limpiar_respuesta_pricing(r)
            if resultado and hay_otra_pieza:
                pieza_extra = _nombre_pieza_tecnico(mensaje)
                resultado += (
                    f"\n\n🔧 Para la *{pieza_extra}*, un técnico especialista te dará "
                    f"el precio exacto en menos de 30 minutos. "
                    f"¿Prefieres llamada o seguimos por WhatsApp? 😊"
                )
            return resultado
        if modelo:
            logger.info(f"[PRICING] Llamando cotizar_con_fallback(marca='', modelo='{modelo}', refaccion='{refaccion_api}')")
            r = await cotizar_con_fallback("", modelo, refaccion_api)
            logger.info(f"[PRICING] Respuesta fallback: {r[:100] if r else 'None'}")
            resultado = _limpiar_respuesta_pricing(r)
            if resultado and hay_otra_pieza:
                pieza_extra = _nombre_pieza_tecnico(mensaje)
                resultado += (
                    f"\n\n🔧 Para la *{pieza_extra}*, un técnico especialista te dará "
                    f"el precio exacto en menos de 30 minutos. "
                    f"¿Prefieres llamada o seguimos por WhatsApp? 😊"
                )
            return resultado
        # Sin modelo: delegar a Claude
        logger.info(f"[PRICING] Sin modelo en el mensaje → delegando a Claude")
        return None
    except Exception as e:
        logger.error(f"[PRICING] Error en consulta directa: {e}", exc_info=True)
        return None


async def _intentar_respuesta_pricing_contextual(mensaje: str, historial: list[dict]) -> str | None:
    m = (mensaje or "").lower()

    # ── Selector de calidad: cliente elige entre opciones ya mostradas ──────────
    # Caso: agente mostró "Genérica $X / Original $Y" y cliente responde solo "Original"
    # Sin esta detección: _extraer_marca_modelo("Original") → (None,None) → Claude responde
    # conversacionalmente ("¡Perfecto!") en lugar de confirmar el precio.
    _CALIDAD_SELECTORES = {"original", "oled", "oem", "generica", "genérica", "china", "alternativa", "compatible"}
    _m_stripped = m.strip().rstrip(".,!? ")
    if _m_stripped in _CALIDAD_SELECTORES:
        _modelo_hist = _buscar_ultimo_modelo_historial(historial)
        _marca_hist = _buscar_ultima_marca_historial(historial)
        if _modelo_hist:
            logger.info(
                f"[PRICING-DEBUG] Selector de calidad '{_m_stripped}' con dispositivo "
                f"en historial: {_marca_hist} {_modelo_hist} → re-cotizando"
            )
            r = await cotizar_con_fallback(_marca_hist or "", _modelo_hist)
            return _limpiar_respuesta_pricing(r)

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

    # GUARD LAPTOP/PC: Si el contexto de la conversación es de laptop o PC y el mensaje
    # actual no trae una marca de celular explícita, el motor de pantallas de celular
    # no aplica. "ya no prendió la pantalla" sobre una laptop NO es una cotización de
    # display de celular. Sin esta guarda, el motor buscaba "Lenovo 3" en el CSV y
    # devolvía "¡Con mucho gusto te cotizo tu pantalla!" de forma incorrecta.
    if _es_contexto_laptop_pc(historial) and not marca_actual:
        logger.info("[PRICING-DEBUG] Contexto laptop/PC sin marca de celular → delegando a Claude")
        return None

    # ── ANTI-LOOP DE VARIANTE ──────────────────────────────────────────────────────
    # Problema: el agente preguntó "¿cuál variante tienes? (13C / 13 Pro...)" y el
    # cliente respondió "es el Redmi 13". El motor vuelve a llamar cotizar_con_fallback
    # con modelo="13", Hugo devuelve "variante" y el agente pregunta de nuevo.
    #
    # Solución: si el último mensaje del asistente fue una pregunta de variante para
    # la misma marca, y el cliente acaba de responder con un modelo concreto →
    # usar ese modelo tal cual (aunque Hugo no lo tenga exacto) y si no hay precio
    # transferir al técnico sin preguntar de nuevo.
    _ult_asistente_contenido = next(
        (h["content"] for h in reversed(historial) if h["role"] == "assistant"), ""
    ).lower()
    _INDICADORES_PREGUNTA_VARIANTE = (
        "manejamos varias versiones",
        "necesito confirmar cuál tienes",
        "cuál es tu modelo exacto",
        "¿cuál es tu modelo",
        "confirmar cuál versión",
        "confirmar la versión",
        "tienes el",
        "¿es el",
    )
    _fue_pregunta_variante = any(t in _ult_asistente_contenido for t in _INDICADORES_PREGUNTA_VARIANTE)
    if _fue_pregunta_variante and (marca_actual or modelo_actual):
        _marca_resp = marca_actual or _buscar_ultima_marca_historial(historial)
        _modelo_resp = modelo_actual
        if _marca_resp and _modelo_resp:
            logger.info(
                f"[PRICING-DEBUG] Anti-loop variante: cliente confirmó '{_marca_resp} {_modelo_resp}' "
                f"tras pregunta de variante → cotizando con modelo exacto declarado"
            )
            r = await cotizar_con_fallback(_marca_resp, _modelo_resp)
            resultado = _limpiar_respuesta_pricing(r)
            # Si la respuesta es OTRA vez una pregunta de variante, ya no insistir → técnico
            if resultado and any(t in resultado.lower() for t in _INDICADORES_PREGUNTA_VARIANTE):
                logger.info(
                    f"[PRICING-DEBUG] Anti-loop variante: aún no hay precio exacto → técnico"
                )
                return (
                    f"Para el *{_marca_resp.upper()} {_modelo_resp}* necesito "
                    f"confirmarte el precio exacto con el técnico.\n\n"
                    f"{_MENSAJE_TECNICO_30MIN}"
                )
            return resultado

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

    # Pidió pantalla pero sin modelo en el mensaje actual.
    # Antes de buscar con el texto crudo (que no es un modelo), intentar recuperar
    # marca+modelo del historial reciente (ej: cliente dijo "Motorola Stylus 2023"
    # en turno anterior y ahora dice "la pantalla se le cayó").
    if es_display:
        modelo_hist = _buscar_ultimo_modelo_historial(historial)
        marca_hist = _buscar_ultima_marca_historial(historial)
        if modelo_hist:
            logger.info(
                f"[PRICING-DEBUG] Display sin modelo actual → usando historial: "
                f"marca='{marca_hist}' modelo='{modelo_hist}'"
            )
            r = await cotizar_con_fallback(marca_hist or "", modelo_hist)
            return _limpiar_respuesta_pricing(r)
        return await _resolver_pricing_desde_texto(mensaje)

    # ── NUEVO: Cliente responde con marca+modelo tras pregunta de fallback de pricing ──
    # Caso: bot preguntó "¿de qué equipo es?" y cliente responde "Huawei P40"
    # Sin esta detección: modelo_actual='p40', marca_actual='huawei' pero ninguna
    # flag de pricing activa → delegaba a Claude → Claude decía "déjame verificar"
    # sin nunca buscar el precio real.
    if modelo_actual and marca_actual and not es_display and not es_consulta_precio:
        _ult_asistente = next(
            (h["content"] for h in reversed(historial) if h["role"] == "assistant"), ""
        ).lower()
        _FALLBACK_TRIGGERS = (
            "solo dime de qué equipo es",
            "de qué equipo es",
            "¿de qué modelo",
            "dime el modelo",
            "dime de qué",
            "qué equipo tienes",
            "solo dime el modelo",
        )
        if any(t in _ult_asistente for t in _FALLBACK_TRIGGERS):
            logger.info(
                f"[PRICING-DEBUG] Respuesta a fallback de pricing: "
                f"marca='{marca_actual}' modelo='{modelo_actual}'"
            )
            r = await cotizar_con_fallback(marca_actual, modelo_actual)
            return _limpiar_respuesta_pricing(r)

        # FIX Bug 2 (ZTE V41 Smart): Mensaje breve con marca+modelo = consulta implícita.
        # En taller de reparación, quien menciona un equipo sin más contexto pregunta precio.
        # Ej: "ZTE V41 Smart" (3 tokens) → cotizar sin necesitar palabras clave explícitas.
        _msg_norm = _normalizar_consulta_pricing(mensaje)
        if len(_msg_norm.split()) <= 4:
            logger.info(
                f"[PRICING-DEBUG] Mensaje breve ({len(_msg_norm.split())} tokens) con "
                f"marca+modelo → cotizando implícitamente: {marca_actual} {modelo_actual}"
            )
            r = await cotizar_con_fallback(marca_actual, modelo_actual)
            return _limpiar_respuesta_pricing(r)

        # FIX Bug S24FE: Mensaje largo pero con marca+modelo completos Y hay contexto
        # reciente de precio en historial → cotizar aunque el mensaje no lo pida explícitamente.
        # Caso: cliente preguntó precio antes ("¿cuánto pantalla Samsung S24?") y ahora
        # especifica variante: "Buenas tardes sería un Samsung S24 fe"
        if hay_contexto_precio:
            logger.info(
                f"[PRICING-DEBUG] marca+modelo con contexto de precio en historial → "
                f"cotizando implícitamente: {marca_actual} {modelo_actual}"
            )
            r = await cotizar_con_fallback(marca_actual, modelo_actual)
            return _limpiar_respuesta_pricing(r)

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

    # ── Prompt caching ──
    # El system_prompt_template (~5000 tokens, fijo por asesor) se manda IGUAL en
    # cada mensaje. Antes se concatenaba con contexto_cliente (que cambia en cada
    # turno: fecha/hora, perfil, disponibilidad) Y ESE BLOQUE DINÁMICO IBA PRIMERO,
    # lo que rompía cualquier posibilidad de cache (el cache de Anthropic requiere
    # que el PREFIJO sea idéntico).
    #
    # Ahora: el bloque estático va primero con cache_control, y el contexto
    # dinámico va en un bloque separado AL FINAL. Así, dentro de la ventana de
    # cache (5 min), los mensajes 2, 3, 4... de una misma conversación pagan el
    # system prompt grande a ~10% del precio normal en vez de 100%.
    system_prompt_estatico = construir_system_prompt(asesor)

    system_blocks = [
        {
            "type": "text",
            "text": system_prompt_estatico,
            "cache_control": {"type": "ephemeral"},
        }
    ]
    if contexto_cliente:
        system_blocks.append({"type": "text", "text": contexto_cliente})

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
                system=system_blocks,
                messages=mensajes,
            )
            respuesta = response.content[0].text
            uso = response.usage
            cache_leido = getattr(uso, "cache_read_input_tokens", 0) or 0
            cache_creado = getattr(uso, "cache_creation_input_tokens", 0) or 0
            logger.info(
                f"[{asesor}] Respuesta generada ({uso.input_tokens} in / {uso.output_tokens} out"
                f" | cache: {cache_leido} leídos, {cache_creado} creados)"
            )
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


async def generar_mensaje_noshow(
    telefono: str,
    nombre_cliente: str,
    historial: list[dict],
    cupon: str,
    fecha_expira: str,
) -> str:
    """Genera el mensaje de reconexión para un cliente que agendó cita pero NO se
    presentó (no-show). Tono cálido y empático (sin regañar): explora por qué no
    vino y ofrece un cupón de descuento por tiempo limitado para reagendar.

    Usado por el comando 'noshow' del grupo interno. Reutiliza generar_respuesta()
    para mantener la voz del asesor.
    """
    prompt = (
        f"Cliente: {nombre_cliente}\n"
        f"Situacion: agendo una cita en el taller pero NO se presento (no-show).\n"
        f"Cupon: {cupon} (10% de descuento, valido hasta {fecha_expira})\n\n"
        f"Tarea: redacta UN solo mensaje de WhatsApp, calido y empatico (NO regañes), para reconectar:\n"
        f"1. Saluda por su nombre y nota con amabilidad que no pudo asistir a su cita\n"
        f"2. Pregunta si todo esta bien y si le gustaria reagendar\n"
        f"3. Ofrece el cupon {cupon} (10% de descuento) si reagenda antes del {fecha_expira}\n"
        f"4. Indica: 'Muestra este cupon al tecnico al aceptar la reparacion para aplicar el descuento'\n"
        f"5. Cierra invitando a responder con un dia y hora para reagendar\n\n"
        f"Responde SOLO con el mensaje listo para enviar, sin encabezados ni comillas."
    )
    return await generar_respuesta(prompt, historial)
