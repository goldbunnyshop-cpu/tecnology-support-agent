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
        return cacheado

    catalogo = {}

    # DISPLAYS
    csv_displays = await _descargar_sheet_csv(GIDS_SHEETS["DISPLAYS"])
    if csv_displays:
        catalogo["DISPLAYS"] = await _parsear_displays(csv_displays)

    # BATERÍAS ANDROID
    csv_android = await _descargar_sheet_csv(GIDS_SHEETS["BATERÍAS ANDROID"])
    if csv_android:
        catalogo["BATERÍAS ANDROID"] = await _parsear_baterias_android(csv_android)

    # BATERÍAS iPHONE
    csv_iphone = await _descargar_sheet_csv(GIDS_SHEETS["BATERÍAS iPHONE"])
    if csv_iphone:
        catalogo["BATERÍAS iPHONE"] = await _parsear_baterias_iphone(csv_iphone)

    total = sum(len(v) for v in catalogo.values())
    logger.info(f"[SHEETS] Catálogo completo cargado: {total} productos de {len(catalogo)} hojas")

    _cache_set(clave, catalogo)
    return catalogo


# ── Búsqueda ───────────────────────────────────────────────────────────────────

def _score_coincidencia(nombre_producto: str, tokens_query: List[str]) -> int:
    """
    Calcula un score de coincidencia entre el query y el nombre del producto.
    Más tokens que coinciden = score más alto.
    """
    nombre_lower = nombre_producto.lower()
    score = sum(1 for tok in tokens_query if tok in nombre_lower)
    return score


async def buscar_google_sheets(
    query: str, marca: str = "", modelo: str = ""
) -> Optional[Dict]:
    """
    Busca un producto en Google Sheets usando query + marca + modelo.

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

    # Tokenizar query
    tokens = [t.lower() for t in re.split(r"\s+", query.lower().strip()) if len(t) >= 2]
    if not tokens:
        return None

    # Búsqueda en todas las hojas
    mejores_resultados = []
    for hoja_name, productos in catalogo.items():
        for producto in productos:
            nombre_producto = producto.get("nombre", "")
            score = _score_coincidencia(nombre_producto, tokens)

            if score > 0:
                mejores_resultados.append((score, producto))

    if not mejores_resultados:
        logger.info(f"[SHEETS] Sin resultados para '{query}'")
        return None

    # Retornar el mejor match
    mejor = max(mejores_resultados, key=lambda x: x[0])
    logger.info(f"[SHEETS] Encontrado: {mejor[1].get('nombre')} (score: {mejor[0]})")

    return mejor[1]


async def formatear_cotizacion_sheets(producto: Dict, marca: str = "", modelo: str = "") -> str:
    """
    Formatea la cotización desde Google Sheets en el mismo estilo que Hugo Shop.
    """
    nombre = producto.get("nombre", "").upper()
    fuente = producto.get("fuente", "")

    lineas = [f"Encontramos en nuestro inventario:\n"]
    lineas.append(f"📦 {nombre}\n")

    # DISPLAYS
    if "displays" in fuente.lower():
        p1 = producto.get("precio_1")
        p2 = producto.get("precio_2")
        p3 = producto.get("precio_3")

        if p1:
            lineas.append(f"* Precio 1: ${int(p1 * 4):,} MXN")  # Multiplicador ×4
        if p2:
            lineas.append(f"* Precio 2: ${int(p2 * 4):,} MXN")
        if p3:
            lineas.append(f"* Precio 3: ${int(p3 * 4):,} MXN")

    # BATERÍAS ANDROID
    elif "android" in fuente.lower():
        p_unit = producto.get("p_unitario")
        may_1 = producto.get("mayoreo_1")
        may_2 = producto.get("mayoreo_2")

        if p_unit:
            lineas.append(f"* Precio Unitario: ${int(p_unit * 4):,} MXN")
        if may_1:
            lineas.append(f"* Mayoreo 1: ${int(may_1 * 4):,} MXN")
        if may_2:
            lineas.append(f"* Mayoreo 2: ${int(may_2 * 4):,} MXN")

    # BATERÍAS iPHONE
    elif "iphone" in fuente.lower():
        p_unit = producto.get("p_unitario")
        sur_20 = producto.get("surtido_20pz")
        sur_50 = producto.get("surtido_50pz")

        if p_unit:
            lineas.append(f"* Precio Unitario: ${int(p_unit * 4):,} MXN")
        if sur_20:
            lineas.append(f"* 20pz Surtido: ${int(sur_20 * 4):,} MXN")
        if sur_50:
            lineas.append(f"* 50pz Surtido: ${int(sur_50 * 4):,} MXN")

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

    Retorna:
      - Cotización formateada si encuentra la pieza
      - None si no encontró
    """
    query = " ".join(p for p in [refaccion, marca, modelo] if p).strip()
    if not query:
        return None

    producto = await buscar_google_sheets(query, marca, modelo)
    if not producto:
        return None

    return await formatear_cotizacion_sheets(producto, marca, modelo)
