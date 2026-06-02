# agent/pricing_sheets.py — Integración específica de Google Sheets para precios
# Fuentes de precios consolidadas: Displays (18 items), Baterías Android (212 items), Baterías iPhone (99 items)
#
# Estructura:
#   1. DISPLAYS (rows 431-448): Nombre | Categoría fija | Precio1 | Precio2 | Precio3
#   2. BATERÍAS ANDROID (rows 5-216): Nombre | P. Unitario | Mayoreo1 | Mayoreo2
#   3. BATERÍAS iPHONE (rows 5-103): Nombre | P. Unitario | 20pz Surtido | 50pz Surtido
#
# Implementa caché con TTL de 1 hora. Usa credenciales de Google Sheets API.

import os
import re
import time
import asyncio
import logging
from collections import defaultdict
from typing import Optional, Dict, List, Tuple

import httpx

logger = logging.getLogger("agentkit")

# ── Configuración ─────────────────────────────────────────────────────────────
SHEET_ID = os.getenv("GOOGLE_SHEETS_ID", "1sMVr7rUp2dz_4h4NUEwFjH-iVqOjUWjJNYx5ptfgT2U")
CACHE_TTL = int(os.getenv("PRICING_SHEETS_CACHE_TTL", str(1 * 3600)))  # 1 hora
HTTP_TIMEOUT = 15

# GIDs de las hojas específicas (obtenidas del mapeo)
GIDS_SHEETS = {
    "DISPLAYS": "1452574805",           # 18 items (rows 431-448)
    "BATERÍAS ANDROID": "122108320",    # 212 items (rows 5-216)
    "BATERÍAS iPHONE": "1428974357",    # 99 items (rows 5-103)
}

# ── Caché en memoria con TTL ───────────────────────────────────────────────────
_cache: Dict[str, Tuple[float, object]] = {}


def _cache_get(clave: str):
    """Obtiene valor del caché si no ha expirado."""
    item = _cache.get(clave)
    if not item:
        return None
    ts, valor = item
    if time.monotonic() - ts > CACHE_TTL:
        _cache.pop(clave, None)
        return None
    return valor


def _cache_set(clave: str, valor):
    """Guarda valor en caché con timestamp."""
    _cache[clave] = (time.monotonic(), valor)


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


# ── Parseo específico por hoja ─────────────────────────────────────────────────

async def _parsear_displays(csv_text: str) -> List[Dict]:
    """
    Parsea hoja DISPLAYS:
      Columna B: Nombre
      Columna C: Categoría (fija: "Display / Display de Diagnóstico")
      Columna D: Precio 1
      Columna E: Precio 2
      Columna F: Precio 3

    Retorna lista de {nombre, categoria, precio_1, precio_2, precio_3}
    """
    productos = []
    lineas = csv_text.split("\n")

    for linea in lineas[3:]:  # Saltar header
        if not linea.strip():
            continue

        partes = linea.split(",")
        if len(partes) < 6:
            continue

        nombre = partes[1].strip() if len(partes) > 1 else ""
        categoria = partes[2].strip() if len(partes) > 2 else ""
        precio_1 = _limpiar_precio(partes[3].strip() if len(partes) > 3 else None)
        precio_2 = _limpiar_precio(partes[4].strip() if len(partes) > 4 else None)
        precio_3 = _limpiar_precio(partes[5].strip() if len(partes) > 5 else None)

        if not nombre or not any([precio_1, precio_2, precio_3]):
            continue

        # Ignorar header row
        if nombre.lower() in ("nombre",):
            continue

        productos.append({
            "nombre": nombre,
            "categoria": categoria if categoria else "Display / Display de Diagnóstico",
            "precio_1": precio_1,
            "precio_2": precio_2,
            "precio_3": precio_3,
            "fuente": "google_sheets_displays",
        })

    logger.info(f"[SHEETS] DISPLAYS: {len(productos)} productos parseados")
    return productos


async def _parsear_baterias_android(csv_text: str) -> List[Dict]:
    """
    Parsea hoja BATERÍAS ANDROID:
      Columna B: Nombre
      Columna C: P. Unitario
      Columna D: Mayoreo 1
      Columna E: Mayoreo 2

    Retorna lista de {nombre, p_unitario, mayoreo_1, mayoreo_2}
    """
    productos = []
    lineas = csv_text.split("\n")

    for linea in lineas[3:]:  # Saltar header
        if not linea.strip():
            continue

        partes = linea.split(",")
        if len(partes) < 5:
            continue

        nombre = partes[1].strip() if len(partes) > 1 else ""
        p_unitario = _limpiar_precio(partes[2].strip() if len(partes) > 2 else None)
        mayoreo_1 = _limpiar_precio(partes[3].strip() if len(partes) > 3 else None)
        mayoreo_2 = _limpiar_precio(partes[4].strip() if len(partes) > 4 else None)

        if not nombre or not any([p_unitario, mayoreo_1, mayoreo_2]):
            continue

        # Ignorar header / categoría rows
        if nombre.lower() in ("nombre", "precio unitario"):
            continue
        if "=" in nombre:  # Línea de separación
            continue

        productos.append({
            "nombre": nombre,
            "p_unitario": p_unitario,
            "mayoreo_1": mayoreo_1,
            "mayoreo_2": mayoreo_2,
            "fuente": "google_sheets_baterias_android",
        })

    logger.info(f"[SHEETS] BATERÍAS ANDROID: {len(productos)} productos parseados")
    return productos


async def _parsear_baterias_iphone(csv_text: str) -> List[Dict]:
    """
    Parsea hoja BATERÍAS iPHONE:
      Columna B: Nombre
      Columna C: P. Unitario
      Columna D: 20pz Surtido
      Columna E: 50pz Surtido

    Retorna lista de {nombre, p_unitario, surtido_20pz, surtido_50pz}
    """
    productos = []
    lineas = csv_text.split("\n")

    for linea in lineas[3:]:  # Saltar header
        if not linea.strip():
            continue

        partes = linea.split(",")
        if len(partes) < 5:
            continue

        nombre = partes[1].strip() if len(partes) > 1 else ""
        p_unitario = _limpiar_precio(partes[2].strip() if len(partes) > 2 else None)
        surtido_20pz = _limpiar_precio(partes[3].strip() if len(partes) > 3 else None)
        surtido_50pz = _limpiar_precio(partes[4].strip() if len(partes) > 4 else None)

        if not nombre or not any([p_unitario, surtido_20pz, surtido_50pz]):
            continue

        # Ignorar header
        if nombre.lower() in ("nombre", "p. unitario"):
            continue

        productos.append({
            "nombre": nombre,
            "p_unitario": p_unitario,
            "surtido_20pz": surtido_20pz,
            "surtido_50pz": surtido_50pz,
            "fuente": "google_sheets_baterias_iphone",
        })

    logger.info(f"[SHEETS] BATERÍAS iPHONE: {len(productos)} productos parseados")
    return productos


# ── Descarga de sheets ─────────────────────────────────────────────────────────

async def _descargar_sheet_csv(gid: str) -> str:
    """Descarga una hoja específica en formato CSV."""
    try:
        async with httpx.AsyncClient(timeout=HTTP_TIMEOUT, follow_redirects=True) as c:
            r = await c.get(
                f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export",
                params={"format": "csv", "gid": gid},
            )
            if r.status_code == 200:
                return r.text
            logger.warning(f"[SHEETS] HTTP {r.status_code} descargando gid={gid}")
    except Exception as e:
        logger.warning(f"[SHEETS] Error descargando gid={gid}: {e}")

    return ""


async def _cargar_catalogo_sheets() -> Dict[str, List[Dict]]:
    """
    Descarga y parsea todas las 3 hojas.
    Retorna {hoja_name: [productos]}
    """
    clave = "sheets::catalogo_completo"
    cacheado = _cache_get(clave)
    if cacheado is not None:
        logger.info(f"[SHEETS] Catálogo desde caché ({sum(len(v) for v in cacheado.values())} productos)")
        return cacheado

    logger.info(f"[SHEETS] Descargando catálogo desde Google Sheets (SHEET_ID={SHEET_ID[:20]}...)")
    catalogo = {}

    # DISPLAYS
    logger.info("[SHEETS] Descargando DISPLAYS...")
    csv_displays = await _descargar_sheet_csv(GIDS_SHEETS["DISPLAYS"])
    if csv_displays:
        catalogo["DISPLAYS"] = await _parsear_displays(csv_displays)
        logger.info(f"[SHEETS] DISPLAYS: {len(catalogo['DISPLAYS'])} items")
    else:
        logger.warning("[SHEETS] DISPLAYS: no se pudo descargar (csv vacío)")

    # BATERÍAS ANDROID
    logger.info("[SHEETS] Descargando BATERÍAS ANDROID...")
    csv_android = await _descargar_sheet_csv(GIDS_SHEETS["BATERÍAS ANDROID"])
    if csv_android:
        catalogo["BATERÍAS ANDROID"] = await _parsear_baterias_android(csv_android)
        logger.info(f"[SHEETS] BATERÍAS ANDROID: {len(catalogo['BATERÍAS ANDROID'])} items")
    else:
        logger.warning("[SHEETS] BATERÍAS ANDROID: no se pudo descargar (csv vacío)")

    # BATERÍAS iPHONE
    logger.info("[SHEETS] Descargando BATERÍAS iPHONE...")
    csv_iphone = await _descargar_sheet_csv(GIDS_SHEETS["BATERÍAS iPHONE"])
    if csv_iphone:
        catalogo["BATERÍAS iPHONE"] = await _parsear_baterias_iphone(csv_iphone)
        logger.info(f"[SHEETS] BATERÍAS iPHONE: {len(catalogo['BATERÍAS iPHONE'])} items")
    else:
        logger.warning("[SHEETS] BATERÍAS iPHONE: no se pudo descargar (csv vacío)")

    total = sum(len(v) for v in catalogo.values())
    logger.info(f"[SHEETS] Catálogo completo cargado: {total} productos de {len(catalogo)} hojas")

    _cache_set(clave, catalogo)
    return catalogo


# ── Búsqueda ───────────────────────────────────────────────────────────────────

def _score_coincidencia(nombre_producto: str, tokens_query: List[str], marca: str = "", modelo: str = "") -> int:
    """
    Calcula score de coincidencia con umbral mínimo.

    Puntuación:
    - Si encuentra MARCA + MODELO juntos en el nombre → score = 100 (match perfecto)
    - Si encuentra MARCA en el nombre → score = 50 + tokens adicionales
    - Si encuentra varios tokens → score = tokens encontrados (mínimo 2)
    - Si encuentra 0-1 tokens → score = 0 (rechaza)
    """
    nombre_lower = nombre_producto.lower()
    marca_lower = marca.lower() if marca else ""
    modelo_lower = modelo.lower() if modelo else ""

    # Match perfecto: marca + modelo juntos
    if marca_lower and modelo_lower:
        if marca_lower in nombre_lower and modelo_lower in nombre_lower:
            return 100
        if marca_lower in nombre_lower:
            return 50  # Marca encontrada pero no modelo

    # Token matching: contar coincidencias
    coincidencias = sum(1 for tok in tokens_query if tok in nombre_lower)

    # UMBRAL MÍNIMO: al menos 2 tokens deben coincidir (no aceptar matches débiles)
    return coincidencias if coincidencias >= 2 else 0


async def buscar_google_sheets(
    query: str, marca: str = "", modelo: str = "", refaccion: str = "display"
) -> Optional[Dict]:
    """
    Busca un producto en Google Sheets usando query + marca + modelo.

    CRÍTICO: Busca SOLO en la hoja correspondiente según refacción.
    - Si refaccion='display' → busca SOLO en DISPLAYS
    - Si refaccion='bateria' → busca en BATERÍAS ANDROID e iPHONE

    Retorna:
      - Para DISPLAYS: {nombre, categoria, precio_1, precio_2, precio_3, fuente}
      - Para BATERÍAS ANDROID: {nombre, p_unitario, mayoreo_1, mayoreo_2, fuente}
      - Para BATERÍAS iPHONE: {nombre, p_unitario, surtido_20pz, surtido_50pz, fuente}
      - None si no encontró nada
    """
    if not query:
        return None

    catalogo = await _cargar_catalogo_sheets()
    if not catalogo:
        logger.warning("[SHEETS] Catálogo vacío")
        return None

    # Tokenizar query (solo palabras >= 2 caracteres)
    tokens = [t.lower() for t in re.split(r"\s+", query.lower().strip()) if len(t) >= 2]
    if not tokens:
        logger.warning(f"[SHEETS] Query '{query}' tiene tokens muy cortos, rechazando")
        return None

    logger.info(f"[SHEETS] Buscando en catálogo: query='{query}', marca='{marca}', modelo='{modelo}', refaccion='{refaccion}', tokens={tokens}")

    # FILTRAR HOJAS SEGÚN REFACCIÓN (CRÍTICO)
    hojas_a_buscar = {}
    if refaccion == "display":
        # Solo displays
        hojas_a_buscar = {k: v for k, v in catalogo.items() if "DISPLAYS" in k.upper()}
        logger.info(f"[SHEETS] Refaccion=display → buscando SOLO en DISPLAYS")
    elif refaccion == "bateria":
        # Solo baterías
        hojas_a_buscar = {k: v for k, v in catalogo.items() if "BATERÍAS" in k.upper() or "BATERIA" in k.upper()}
        logger.info(f"[SHEETS] Refaccion=bateria → buscando SOLO en BATERÍAS")
    else:
        # Fallback: buscar en todas
        hojas_a_buscar = catalogo
        logger.info(f"[SHEETS] Refaccion={refaccion} desconocida → buscando en todas las hojas")

    # Búsqueda en hojas filtradas
    mejores_resultados = []
    for hoja_name, productos in hojas_a_buscar.items():
        for producto in productos:
            nombre_producto = producto.get("nombre", "")
            score = _score_coincidencia(nombre_producto, tokens, marca, modelo)

            if score > 0:
                mejores_resultados.append((score, producto, hoja_name))

    if not mejores_resultados:
        logger.info(f"[SHEETS] Sin resultados para '{query}' en {refaccion} (marca='{marca}', modelo='{modelo}')")
        return None

    # Retornar el mejor match
    mejor = max(mejores_resultados, key=lambda x: x[0])
    score, producto, hoja = mejor[0], mejor[1], mejor[2]
    logger.info(f"[SHEETS] Encontrado en {hoja}: '{producto.get('nombre')}' (score: {score})")

    return producto


async def formatear_cotizacion_sheets(producto: Dict, marca: str = "", modelo: str = "") -> str:
    """
    Formatea la cotización desde Google Sheets en el mismo estilo que Hugo Shop.

    CAMBIO IMPORTANTE:
    - Para DISPLAYS: Mostrar SOLO el precio MÁS ALTO (precio_3) etiquetado como "Calidad"
    - Para BATERÍAS: Mostrar SOLO el precio Unitario (sin mayoreo ni surtidos)
    """
    nombre = producto.get("nombre", "").upper()
    fuente = producto.get("fuente", "")
    titulo = f"{marca} {modelo}".strip().upper() if marca and modelo else nombre

    lineas = [f"Para {titulo} encontramos estas opciones:\n"]

    # DISPLAYS - Mostrar SOLO el precio MÁS ALTO
    if "displays" in fuente.lower():
        p1 = producto.get("precio_1")
        p2 = producto.get("precio_2")
        p3 = producto.get("precio_3")

        # Seleccionar el precio más alto (precio_3 es el premium)
        precios = [p for p in [p1, p2, p3] if p]
        if precios:
            precio_max = max(precios)  # El precio más alto
            precio_mxn = int(precio_max * 4)  # Multiplicador ×4
            lineas.append(f"* Calidad Original: ${precio_mxn:,} MXN")
            logger.info(f"[SHEETS] DISPLAYS formateado: {titulo} → precio ${precio_mxn:,} MXN")
        else:
            logger.warning(f"[SHEETS] DISPLAYS sin precios válidos para {titulo}")

    # BATERÍAS ANDROID - Mostrar SOLO el precio Unitario
    elif "android" in fuente.lower():
        p_unit = producto.get("p_unitario")

        if p_unit:
            precio_mxn = int(p_unit * 4)  # Multiplicador ×4
            lineas.append(f"* Precio Unitario: ${precio_mxn:,} MXN")
            logger.info(f"[SHEETS] BATERÍAS ANDROID formateado: {titulo} → precio ${precio_mxn:,} MXN")
        else:
            logger.warning(f"[SHEETS] BATERÍAS ANDROID sin precio unitario para {titulo}")

    # BATERÍAS iPHONE - Mostrar SOLO el precio Unitario
    elif "iphone" in fuente.lower():
        p_unit = producto.get("p_unitario")

        if p_unit:
            precio_mxn = int(p_unit * 4)  # Multiplicador ×4
            lineas.append(f"* Precio Unitario: ${precio_mxn:,} MXN")
            logger.info(f"[SHEETS] BATERÍAS iPHONE formateado: {titulo} → precio ${precio_mxn:,} MXN")
        else:
            logger.warning(f"[SHEETS] BATERÍAS iPHONE sin precio unitario para {titulo}")

    lineas.append("")
    lineas.append("✅ Incluye diagnóstico, garantía 90 días y cambio el mismo día.")
    lineas.append("¿Cuál opción te interesa?")

    return "\n".join(lineas)


# ── API pública ────────────────────────────────────────────────────────────────

async def cotizar_google_sheets(
    marca: str, modelo: str, refaccion: str = "display"
) -> Optional[str]:
    """
    Busca una pieza en Google Sheets y retorna la cotización formateada.

    CRÍTICO: Pasa refaccion a buscar_google_sheets() para filtrar hojas.

    Retorna:
      - Cotización formateada si encuentra la pieza
      - None si no encontró
    """
    query = " ".join(p for p in [refaccion, marca, modelo] if p).strip()
    if not query:
        return None

    # PASAR refaccion para filtrar las hojas correctas
    producto = await buscar_google_sheets(query, marca, modelo, refaccion)
    if not producto:
        return None

    return await formatear_cotizacion_sheets(producto, marca, modelo)
