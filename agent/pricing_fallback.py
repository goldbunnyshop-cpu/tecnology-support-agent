# agent/pricing_fallback.py — Fallback de precios cuando Hugo Shop no tiene la pieza
# Fuentes: fixoem.com (Shopify, primario) + Google Sheet del proveedor (secundario)
#
# Replica la MISMA lógica que agent/pricing.py (Hugo Shop):
#   - Clasifica cada producto en categorías: GENERICO / ORIGINAL / AMOLED
#   - Promedia por categoría y aplica multiplicador (×4 genérico/original, ×3 AMOLED)
#   - Devuelve la respuesta con el mismo formato "INFORMACION PARA EL CLIENTE..."
#
# No usa base de datos (caché en memoria con TTL) para no introducir ciclos circulares.

import os
import re
import csv
import io
import time
import asyncio
import logging
from collections import defaultdict
from typing import Optional

import httpx

from agent.pricing import (
    obtener_categoria,
    ETIQUETAS_CATEGORIA,
    MULTIPLICADOR_POR_CATEGORIA,
    MULTIPLICADOR_USD_A_MXN,
    _mensaje_no_disponible,
)
from agent.pricing_sheets import cotizar_google_sheets

logger = logging.getLogger("agentkit")

# ── Configuración ─────────────────────────────────────────────────────────────
FIXOEM_BASE = os.getenv("FIXOEM_BASE_URL", "https://fixoem.com")
SHEET_ID = os.getenv("PRICING_SHEET_ID", "1sMVr7rUp2dz_4h4NUEwFjH-iVqOjUWjJNYx5ptfgT2U")
# Multiplicador base aplicado al precio de la fuente (displays/general).
# Igual que Hugo Shop: GENERICO/ORIGINAL ×4, AMOLED ×3 (ver MULTIPLICADOR_POR_CATEGORIA).
MULTIPLICADOR_FALLBACK = int(os.getenv("PRICING_FALLBACK_MULTIPLIER", str(MULTIPLICADOR_USD_A_MXN)))

# Multiplicadores especiales para TAPAS (mucha mano de obra para quitar/poner).
MULT_TAPA_IPHONE = int(os.getenv("PRICING_MULT_TAPA_IPHONE", "8"))
MULT_TAPA_OTRAS = int(os.getenv("PRICING_MULT_TAPA_OTRAS", "5"))

# Umbral: si el precio calculado supera este monto, NO se muestra el número; en su
# lugar se invita a consultar el precio directamente con el técnico.
# CRÍTICO: Sin límite de precio. El cliente debe ver TODOS los precios calculados.
# Si necesita restricción especial, usar variable de entorno PRICING_UMBRAL_CONSULTAR
UMBRAL_CONSULTAR = int(os.getenv("PRICING_UMBRAL_CONSULTAR", "999999999"))

CACHE_TTL = int(os.getenv("PRICING_FALLBACK_CACHE_TTL", str(6 * 3600)))  # 6 horas
HTTP_TIMEOUT = 15

# Marcas iPhone (para multiplicador de tapas ×8)
_MARCAS_IPHONE = ("iphone", "apple")


def _es_tapa(refaccion: str, query: str) -> bool:
    t = f"{refaccion} {query}".lower()
    return "tapa" in t


def _multiplicador_para(categoria: Optional[str], refaccion: str, query: str, marca: str) -> int:
    """Multiplicador según tipo de pieza y categoría de calidad."""
    if _es_tapa(refaccion, query):
        if (marca or "").lower() in _MARCAS_IPHONE:
            return MULT_TAPA_IPHONE
        return MULT_TAPA_OTRAS
    if categoria:
        return MULTIPLICADOR_POR_CATEGORIA.get(categoria, MULTIPLICADOR_FALLBACK)
    return MULTIPLICADOR_FALLBACK

# Palabras de stop que NO son refacciones reales (accesorios/herramientas en fixoem)
_TITULOS_IGNORAR = (
    "tablilla", "adaptador", "jcid", "programador", "herramienta",
    "kit ", "pegamento", "adhesivo", "molde",
)


# ── Clasificador de calidad (extiende obtener_categoria de Hugo Shop) ──────────
# Hugo Shop mapea por la columna CALIDAD; aquí lo hacemos sobre el TÍTULO del
# producto. Reusamos obtener_categoria() y añadimos pistas propias de estas fuentes
# (IPS / LCD = genérico; OLED / AMOLED = original/amoled).
_PISTAS_ORIGINAL = ("OLED", "ORIGINAL", "ORIG ", " COF", "FHD", "HG ORIG", "DD SOFT")
_PISTAS_GENERICO = ("INCELL", "IN-CELL", "IPS", "COG", "LCD", "GENERIC", "GENÉRIC")


def _clasificar_calidad(titulo: str, es_display: bool) -> Optional[str]:
    """Devuelve GENERICO / ORIGINAL / AMOLED / None a partir del título.

    Si es un display sin pista clara de calidad, se asume GENERICO (un LCD común);
    para otras piezas (tapa, batería, altavoz) None significa "precio único".
    """
    if not titulo:
        return None
    c = titulo.upper()

    # 1) Intentar la lógica oficial de Hugo Shop sobre el título
    cat = obtener_categoria(titulo)
    if cat:
        return cat

    # 2) Pistas adicionales propias de fixoem / Sheet
    if "AMOLED" in c:
        return "AMOLED"
    if any(p in c for p in _PISTAS_ORIGINAL):
        return "ORIGINAL"
    if any(p in c for p in _PISTAS_GENERICO):
        return "GENERICO"

    # 3) Display sin pista → genérico (LCD común). Otras piezas → precio único.
    if es_display:
        return "GENERICO"
    return None


def _limpiar_precio(valor) -> Optional[float]:
    """Convierte '$1,234.50' o '1234.5' a float."""
    if valor is None:
        return None
    try:
        limpio = str(valor).replace("$", "").replace("MXN", "").replace(",", "").strip()
        precio = float(limpio)
        return precio if precio > 0 else None
    except (ValueError, TypeError):
        return None


def _es_consulta_display(refaccion: str, query: str) -> bool:
    t = f"{refaccion} {query}".lower()
    return any(w in t for w in ("display", "pantalla", "lcd", "oled"))


# Variantes que distinguen un modelo de otro (pro, max, etc.). NO incluye "5g"
# porque no separa modelos (es un sufijo de red). Sirve para evitar que una
# consulta de "iphone 12" devuelva el "12 Pro Max".
_VARIANTES_MODELO = ("pro max", "pro", "max", "mini", "plus", "ultra", "neo", "lite", "fe")


def _titulo_coincide_modelo(titulo: str, marca: str, modelo: str) -> bool:
    """True si el título corresponde al modelo pedido, sin contaminación de variantes.

    Replica el espíritu de Hugo Shop: si el cliente NO pidió una variante (pro, max…),
    no devolvemos productos de esas variantes. Soporta títulos multi-modelo separados
    por '/' (ej "iPhone 12 / 12 Pro" SÍ cubre el "12" base).
    """
    if not titulo or not modelo:
        return False
    t = titulo.lower()
    base_tokens = [tok for tok in modelo.lower().split() if tok not in _VARIANTES_MODELO]
    variantes_query = [v for v in _VARIANTES_MODELO if v in modelo.lower()]

    # Cada chunk separado por '/' es un modelo compatible distinto
    chunks = re.split(r"[/]", t)
    for chunk in chunks:
        # Deben estar todos los tokens base (ej "12", "a54") en el chunk
        if not all(tok in chunk for tok in base_tokens):
            continue
        # Variantes presentes en el chunk que el cliente NO pidió → descartar chunk
        extra = [
            v for v in _VARIANTES_MODELO
            if re.search(rf"\b{re.escape(v)}\b", chunk) and v not in variantes_query
        ]
        if extra:
            continue
        # Si el cliente pidió variante, debe estar en el chunk
        if variantes_query and not all(v in chunk for v in variantes_query):
            continue
        return True
    return False


# ── Caché en memoria con TTL ───────────────────────────────────────────────────
_cache: dict[str, tuple[float, object]] = {}


def _cache_get(clave: str):
    item = _cache.get(clave)
    if not item:
        return None
    ts, valor = item
    if time.monotonic() - ts > CACHE_TTL:
        _cache.pop(clave, None)
        return None
    return valor


def _cache_set(clave: str, valor):
    _cache[clave] = (time.monotonic(), valor)


# ── Fuente 1: fixoem.com (Shopify) ─────────────────────────────────────────────
async def _buscar_fixoem(query: str, _marca_q: str = "", _modelo_q: str = "") -> list[dict]:
    """Busca en fixoem vía el endpoint de sugerencias de Shopify.

    Retorna lista de {titulo, precio, categoria}.
    Los precios de fixoem están en MXN, se multiplican por 3 para margen de venta.
    """
    clave = f"fixoem::{query.lower()}"
    cacheado = _cache_get(clave)
    if cacheado is not None:
        return cacheado

    productos: list[dict] = []
    try:
        async with httpx.AsyncClient(timeout=HTTP_TIMEOUT, follow_redirects=True) as c:
            r = await c.get(
                f"{FIXOEM_BASE}/search/suggest.json",
                params={
                    "q": query,
                    "resources[type]": "product",
                    "resources[limit]": 10,
                },
                headers={"User-Agent": "Mozilla/5.0"},
            )
            if r.status_code != 200:
                logger.warning(f"[FALLBACK] fixoem HTTP {r.status_code} para '{query}'")
                _cache_set(clave, productos)
                return productos
            resultados = (
                r.json().get("resources", {}).get("results", {}).get("products", [])
            )
            es_display = _es_consulta_display("", query)
            for p in resultados:
                titulo = p.get("title", "")
                if any(w in titulo.lower() for w in _TITULOS_IGNORAR):
                    continue
                if not _titulo_coincide_modelo(titulo, _marca_q, _modelo_q):
                    continue
                precio_fixoem_mxn = _limpiar_precio(p.get("price"))
                if not precio_fixoem_mxn:
                    continue
                # Precios de fixoem en MXN se multiplican por 3 para margen comercial
                precio_final = precio_fixoem_mxn * 3
                categoria = _clasificar_calidad(titulo, es_display)
                productos.append(
                    {"titulo": titulo, "precio": precio_final, "categoria": categoria, "fuente": "fixoem"}
                )
                logger.info(f"[FALLBACK] fixoem: {titulo} → MXN${precio_fixoem_mxn:.0f} × 3 = MXN${precio_final:.0f}")
    except Exception as e:
        logger.warning(f"[FALLBACK] Error en fixoem '{query}': {e}")

    _cache_set(clave, productos)
    return productos


# ── Fuente 2: Google Sheet del proveedor ───────────────────────────────────────
async def _obtener_gids_sheet() -> list[str]:
    """Lee las pestañas (gids) del Sheet desde la vista htmlview (cacheado)."""
    clave = "sheet::gids"
    cacheado = _cache_get(clave)
    if cacheado is not None:
        return cacheado

    gids: list[str] = ["0"]
    try:
        async with httpx.AsyncClient(timeout=HTTP_TIMEOUT, follow_redirects=True) as c:
            r = await c.get(f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/htmlview")
            if r.status_code == 200:
                encontrados = re.findall(r"gid=([0-9]+)", r.text)
                if encontrados:
                    gids = sorted(set(encontrados))
    except Exception as e:
        logger.warning(f"[FALLBACK] No se pudieron leer gids del Sheet: {e}")

    _cache_set(clave, gids)
    return gids


async def _cargar_catalogo_sheet() -> list[dict]:
    """Descarga TODAS las pestañas del Sheet y devuelve un catálogo plano (cacheado).

    Cada item: {nombre, precio}. El parseo es tolerante a filas-basura (encabezados,
    direcciones del proveedor, etc.).
    """
    clave = "sheet::catalogo"
    cacheado = _cache_get(clave)
    if cacheado is not None:
        return cacheado

    gids = await _obtener_gids_sheet()

    async def _descargar_tab(gid: str) -> list[dict]:
        items: list[dict] = []
        try:
            async with httpx.AsyncClient(timeout=HTTP_TIMEOUT, follow_redirects=True) as c:
                r = await c.get(
                    f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export",
                    params={"format": "csv", "gid": gid},
                )
                if r.status_code != 200:
                    return items
                r.encoding = "utf-8"
                for row in csv.reader(io.StringIO(r.text)):
                    if len(row) < 2:
                        continue
                    nombre = (row[1] or "").strip()
                    # El precio puede estar en distintas columnas según la pestaña;
                    # tomamos el primer valor con formato de precio en la fila.
                    precio = None
                    for celda in row[2:]:
                        precio = _limpiar_precio(celda)
                        if precio:
                            break
                    if not nombre or not precio:
                        continue
                    # Saltar filas de encabezado/título
                    if nombre.lower() in ("nombre",) or "\n" in nombre:
                        continue
                    items.append({"nombre": nombre, "precio": precio})
        except Exception as e:
            logger.debug(f"[FALLBACK] Error tab {gid}: {e}")
        return items

    catalogo: list[dict] = []
    try:
        resultados = await asyncio.gather(*[_descargar_tab(g) for g in gids])
        for lista in resultados:
            catalogo.extend(lista)
        logger.info(f"[FALLBACK] Catálogo Sheet cargado: {len(catalogo)} productos de {len(gids)} pestañas")
    except Exception as e:
        logger.warning(f"[FALLBACK] Error cargando catálogo Sheet: {e}")

    _cache_set(clave, catalogo)
    return catalogo


async def _buscar_sheet(query: str, refaccion: str, marca: str = "", modelo: str = "") -> list[dict]:
    """Busca en el catálogo del Sheet por coincidencia de todos los tokens del query."""
    catalogo = await _cargar_catalogo_sheet()
    if not catalogo:
        return []

    tokens = [t for t in re.split(r"\s+", query.lower().strip()) if len(t) >= 2]
    if not tokens:
        return []

    es_display = _es_consulta_display(refaccion, query)
    productos: list[dict] = []
    for item in catalogo:
        nombre_lower = item["nombre"].lower()
        if all(tok in nombre_lower for tok in tokens):
            if modelo and not _titulo_coincide_modelo(item["nombre"], marca, modelo):
                continue
            categoria = _clasificar_calidad(item["nombre"], es_display)
            productos.append(
                {
                    "titulo": item["nombre"],
                    "precio": item["precio"],
                    "categoria": categoria,
                    "fuente": "sheet",
                }
            )
    return productos


# ── Formateo (mismo estilo que Hugo Shop) ──────────────────────────────────────
def _linea_precio(etiqueta: str, promedio: float, mult: int) -> str:
    """Construye la línea de precio; si supera el umbral, invita a consultar al técnico."""
    precio_mxn = int(promedio * mult)
    if precio_mxn > UMBRAL_CONSULTAR:
        return f"* {etiqueta}: disponible - consulta el precio directamente con nuestro tecnico"
    return f"* {etiqueta}: ${precio_mxn:,} MXN"


def _formatear_cotizacion_fallback(
    marca: str, modelo: str, refaccion: str, query: str, productos: list[dict]
) -> Optional[str]:
    """Agrupa por categoría, promedia, aplica multiplicador y formatea como Hugo Shop.

    - Multiplicador por tipo de pieza (tapas iPhone ×8, otras tapas ×5, resto ×4/×3).
    - Si el precio de una calidad supera el umbral, se oculta el número y se invita
      a consultar el precio con el técnico (en vez de mostrar una cifra irreal).
    """
    por_categoria: dict[str, list[float]] = defaultdict(list)
    sin_categoria: list[float] = []
    for p in productos:
        cat = p.get("categoria")
        if cat:
            por_categoria[cat].append(p["precio"])
        else:
            sin_categoria.append(p["precio"])

    if not por_categoria and not sin_categoria:
        return None

    titulo = f"{marca} {modelo}".strip().upper()
    lineas = [f"Para {titulo} encontramos estas opciones:\n"]

    for categoria in ("GENERICO", "ORIGINAL", "AMOLED"):
        precios = por_categoria.get(categoria)
        if not precios:
            continue
        promedio = sum(precios) / len(precios)
        mult = _multiplicador_para(categoria, refaccion, query, marca)
        lineas.append(_linea_precio(ETIQUETAS_CATEGORIA[categoria], promedio, mult))

    # Piezas sin tier de calidad (tapa, batería, altavoz, etc.): precio único.
    if sin_categoria and not por_categoria:
        promedio = sum(sin_categoria) / len(sin_categoria)
        mult = _multiplicador_para(None, refaccion, query, marca)
        lineas.append(_linea_precio("Precio", promedio, mult))

    lineas.append("")
    lineas.append("Incluye diagnostico, garantia 90 dias y cambio el mismo dia.")
    lineas.append("Cual opcion te interesa?")

    cuerpo = "\n".join(lineas)
    return (
        "INFORMACION PARA EL CLIENTE (transmitir tal cual; usar solo las etiquetas "
        "'Calidad Generica', 'Calidad Original', 'AMOLED' - sin tecnicismos en parentesis):\n\n"
        f"{cuerpo}"
    )


# ── API pública ────────────────────────────────────────────────────────────────
async def cotizar_fuentes_externas(
    marca: str, modelo: str, refaccion: str = "display"
) -> Optional[str]:
    """Busca la pieza en fixoem (primario) y luego en el Sheet (secundario).

    Retorna la cotización formateada (mismo estilo que Hugo Shop) o None si no
    se encontró en ninguna fuente.
    """
    marca = (marca or "").strip()
    modelo = (modelo or "").strip()
    query = " ".join(p for p in [refaccion, marca, modelo] if p).strip()
    if not query:
        return None

    # 1) fixoem primero
    productos = await _buscar_fixoem(query, marca, modelo)
    if productos:
        logger.info(f"[FALLBACK] fixoem encontró {len(productos)} producto(s) para '{query}'")
        resp = _formatear_cotizacion_fallback(marca, modelo, refaccion, query, productos)
        if resp:
            return resp

    # 2) Sheet del proveedor
    productos = await _buscar_sheet(query, refaccion, marca, modelo)
    if productos:
        logger.info(f"[FALLBACK] Sheet encontró {len(productos)} producto(s) para '{query}'")
        resp = _formatear_cotizacion_fallback(marca, modelo, refaccion, query, productos)
        if resp:
            return resp

    logger.info(f"[FALLBACK] Sin resultados en fixoem ni Sheet para '{query}'")
    return None


# ── Detección de "no disponible" de Hugo Shop ──────────────────────────────────
_INDICADORES_NO_DISPONIBLE = (
    "no encontr",
    "no encontre",
    "modelo diferente",
    "acude al modulo",
    "necesito que me digas",
    "alternativas compatibles",
    # Formato de _mensaje_no_disponible() cuando hay marca+modelo pero no está en
    # Hugo Shop: "❌ Disculpa, no tenemos *X* disponible en este momento". Sin esto
    # la cadena de fallback se detenía y nunca consultaba Google Sheets/fixoem.
    "no tenemos",
    "disponible en este momento",
)


def es_respuesta_no_disponible(respuesta: str) -> bool:
    """True si la respuesta de Hugo Shop indica que NO tiene la pieza."""
    if not respuesta:
        return True
    r = respuesta.lower()
    return any(ind in r for ind in _INDICADORES_NO_DISPONIBLE)


async def cotizar_con_fallback(
    marca: str, modelo: str, refaccion: str = "display"
) -> str:
    """Pipeline de precios con 3+ fuentes:
    1. Hugo Shop (primero) — SOLO para displays
    2. Google Sheets (624 productos: displays, baterías Android/iPhone)
    3. fixoem + Sheet genérico (fallback final)

    CAMBIO: Si refacción != "display", SALTAR Hugo Shop e ir directo a Google Sheets
    (Hugo Shop solo tiene displays, no baterías ni tapas).
    """
    from agent.pricing import obtener_cotizacion_display

    respuesta_hugo = None

    # 1. SOLO intentar Hugo Shop si refacción es display
    if refaccion == "display":
        logger.info(f"[PRICING] Intentando Hugo Shop para DISPLAY: {marca} {modelo}")
        respuesta_hugo = await obtener_cotizacion_display(marca, modelo)

        # Si Hugo Shop tiene la pieza (no es "no disponible"), usarla
        if not es_respuesta_no_disponible(respuesta_hugo):
            logger.info(f"[PRICING] Hugo Shop encontró display: {marca} {modelo}")
            return respuesta_hugo
        logger.info(f"[PRICING] Hugo Shop no tiene display: {marca} {modelo}")
    else:
        logger.info(f"[PRICING] Refacción={refaccion} (no es display), SALTANDO Hugo Shop → Google Sheets")

    # 2. Hugo Shop no tiene o refacción != display → intentar Google Sheets
    logger.info(f"[PRICING] Llamando Google Sheets(marca={marca}, modelo={modelo}, refaccion={refaccion})")
    try:
        respuesta_sheets = await cotizar_google_sheets(marca, modelo, refaccion)
        logger.info(f"[PRICING] Respuesta de Google Sheets: {respuesta_sheets is not None}")
        if respuesta_sheets:
            logger.info(f"[PRICING] Google Sheets encontró '{marca} {modelo}' ({refaccion})")
            return respuesta_sheets
        logger.info(f"[PRICING] Google Sheets NO encontró '{marca} {modelo}' ({refaccion})")
    except Exception as e:
        logger.error(f"[PRICING] EXCEPCIÓN en Google Sheets: {type(e).__name__}: {e}", exc_info=True)

    # 3. Google Sheets no tiene → intentar fixoem + Sheet genérico
    logger.info(f"[PRICING] Intentando fixoem + Sheet genérico para '{marca} {modelo}' ({refaccion})...")
    externa = await cotizar_fuentes_externas(marca, modelo, refaccion)
    if externa:
        logger.info(f"[PRICING] fixoem/Sheet genérico encontraron '{marca} {modelo}'")
        return externa

    # Nadie tiene → si tenemos respuesta de Hugo Shop, devolverla; si no, devolver genérica
    if respuesta_hugo:
        logger.info(f"[PRICING] Ninguna fuente tiene '{marca} {modelo}' ({refaccion}), devolviendo Hugo Shop")
        return respuesta_hugo

    logger.info(f"[PRICING] Ninguna fuente tiene '{marca} {modelo}' ({refaccion})")
    return _mensaje_no_disponible(marca, modelo)
