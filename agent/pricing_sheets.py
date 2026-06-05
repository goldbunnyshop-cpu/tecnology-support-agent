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
import csv
import io
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

def _leer_filas(csv_text: str) -> List[List[str]]:
    """Parsea el CSV con el módulo csv (respeta comas dentro de comillas).

    CRÍTICO: un split(',') ingenuo rompía precios como "$2,000" (coma de miles),
    perdiendo o corrompiendo todos los productos de ≥ $1,000. csv.reader maneja
    correctamente los campos entrecomillados.
    """
    if not csv_text:
        return []
    return list(csv.reader(io.StringIO(csv_text)))


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

    for partes in _leer_filas(csv_text)[3:]:  # Saltar header
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

    for partes in _leer_filas(csv_text)[3:]:  # Saltar header
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

    for partes in _leer_filas(csv_text)[3:]:  # Saltar header
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


# ── Desambiguación reloj / celular y variantes ─────────────────────────────────
# La hoja DISPLAYS mezcla "Display Apple Watch ..." (relojes) con "Display ... iPhone"
# (celulares). El alias 'apple' → iPhone hacía que una consulta sin modelo colara un
# Apple Watch porque su nombre SÍ contiene "apple" y el del iPhone NO. Estos helpers
# separan ambos universos: relojes solo si el cliente dijo "reloj"/"watch".

_PALABRAS_RELOJ = ("reloj", "watch", "iwatch", "smartwatch")

# Variantes que distinguen un iPhone de otro. Orden importa: "pro max" antes que "pro".
_VARIANTES_IPHONE = ("pro max", "pro", "plus", "max", "mini", "se")


def _es_consulta_reloj(*textos: str) -> bool:
    """True si el cliente está preguntando por un reloj (Apple Watch)."""
    t = " ".join(x for x in textos if x).lower()
    return any(w in t for w in _PALABRAS_RELOJ)


def _es_producto_reloj(nombre: str) -> bool:
    """True si el producto del catálogo es un display de Apple Watch."""
    return "watch" in (nombre or "").lower()


def _es_marca_iphone(marca: str) -> bool:
    return (marca or "").lower() in ("apple", "iphone")


def _split_base_variante(modelo: str) -> Tuple[str, Optional[str]]:
    """De 'pro max' / '14 pro max' extrae (base='14', variante='pro max')."""
    m = (modelo or "").lower().strip()
    variante = None
    for v in _VARIANTES_IPHONE:
        if re.search(rf"\b{re.escape(v)}\b", m):
            variante = v
            break
    base = m
    for v in _VARIANTES_IPHONE:
        base = re.sub(rf"\b{re.escape(v)}\b", "", base)
    base = re.sub(r"\s+", " ", base).strip()
    return base, variante


def _variante_en_titulo(nombre: str, base: str) -> Optional[str]:
    """Detecta la variante (pro/pro max/...) que aparece en el nombre tras el base."""
    n = (nombre or "").lower()
    m = re.search(rf"\b{re.escape(base)}\b(.*)", n)
    if not m:
        return None
    resto = m.group(1)
    for v in _VARIANTES_IPHONE:
        if re.search(rf"\b{re.escape(v)}\b", resto):
            return v
    return None


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


def _precio_orden(producto: Dict) -> float:
    """Precio usado para desempatar candidatos del mismo score (el más alto gana)."""
    return producto.get("precio_3") or producto.get("p_unitario") or 0


async def buscar_google_sheets(
    query: str, marca: str = "", modelo: str = "", refaccion: str = "display",
    devolver_todos: bool = False,
):
    """
    Busca un producto en Google Sheets usando query + marca + modelo.

    CRÍTICO: Busca SOLO en la hoja correspondiente según refacción.
    - Si refaccion='display' → busca SOLO en DISPLAYS
    - Si refaccion='bateria' → busca en BATERÍAS ANDROID e iPHONE

    Desambiguación reloj/celular: los displays de Apple Watch SOLO se consideran
    cuando el cliente pidió un reloj ("reloj"/"watch"); de lo contrario se excluyen
    para que 'apple'/'iphone' nunca devuelva un Apple Watch por accidente.

    Retorna:
      - devolver_todos=False (default): el mejor producto (dict) o None
      - devolver_todos=True: lista [(score, producto, hoja)] ordenada de mayor a menor
    """
    vacio = [] if devolver_todos else None
    if not query:
        return vacio

    catalogo = await _cargar_catalogo_sheets()
    if not catalogo:
        logger.warning("[SHEETS] Catálogo vacío")
        return vacio

    # Tokenizar query (solo palabras >= 2 caracteres)
    tokens = [t.lower() for t in re.split(r"\s+", query.lower().strip()) if len(t) >= 2]
    if not tokens:
        logger.warning(f"[SHEETS] Query '{query}' tiene tokens muy cortos, rechazando")
        return vacio

    # ¿El cliente quiere un reloj? Si no, los Apple Watch quedan fuera.
    quiere_reloj = _es_consulta_reloj(query, marca, modelo)

    # Normalizar marca para puntuar: el catálogo usa "iPhone" para celulares; si el
    # cliente dijo "apple" (y NO es consulta de reloj), tratamos como "iphone".
    marca_score = marca
    if _es_marca_iphone(marca) and not quiere_reloj:
        marca_score = "iphone"

    logger.info(f"[SHEETS] Buscando: query='{query}', marca='{marca}'→'{marca_score}', modelo='{modelo}', refaccion='{refaccion}', reloj={quiere_reloj}, tokens={tokens}")

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
            # Filtro reloj/celular: relojes solo si el cliente pidió reloj.
            if _es_producto_reloj(nombre_producto) != quiere_reloj:
                continue
            score = _score_coincidencia(nombre_producto, tokens, marca_score, modelo)

            if score > 0:
                mejores_resultados.append((score, producto, hoja_name))

    if not mejores_resultados:
        logger.info(f"[SHEETS] Sin resultados para '{query}' en {refaccion} (marca='{marca}', modelo='{modelo}')")
        return vacio

    # Ordenar por score y, en empate, por precio más alto (el premium gana).
    mejores_resultados.sort(key=lambda x: (x[0], _precio_orden(x[1])), reverse=True)

    if devolver_todos:
        return mejores_resultados

    # Guard de modelo exacto: si el cliente dio un modelo, el título debe corresponder
    # a ese modelo (mismo base, sin contaminación de otra variante). Evita que
    # 'redmi note 99' (inexistente) cole el precio de un 'redmi note 13' por overlap
    # de tokens. Reutiliza la lógica de Hugo/fallback (soporta títulos multi-modelo).
    if modelo:
        from agent.pricing_fallback import _titulo_coincide_modelo
        filtrados = [
            r for r in mejores_resultados
            if _titulo_coincide_modelo(r[1].get("nombre", ""), marca_score, modelo)
        ]
        if not filtrados:
            logger.info(f"[SHEETS] Ningún título corresponde al modelo '{modelo}' → sin resultado")
            return None
        mejores_resultados = filtrados

    score, producto, hoja = mejores_resultados[0]
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
            precio_mxn = int(precio_max * 3)  # Multiplicador ×3 (margen comercial)
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

async def _cotizar_display_iphone(query: str, marca: str, modelo: str) -> Optional[str]:
    """Cotización de display de iPhone con manejo de variantes.

    Regla de negocio: si el cliente no especifica la versión exacta (14 vs 14 Pro
    vs 14 Pro Max) y existe más de una variante en el catálogo, NO adivinamos:
    preguntamos cuál tiene (igual que Hugo Shop). Solo cotizamos cuando la variante
    es inequívoca o el cliente ya la confirmó.
    """
    # Importación diferida para evitar ciclos de import.
    from agent.pricing import _formatear_pregunta_variantes, _formatear_modelo

    base, variante_pedida = _split_base_variante(modelo)
    if not base:
        # Sin modelo concreto (ej. solo "iphone"): pedir el modelo, no adivinar.
        logger.info("[SHEETS] iPhone sin modelo concreto → no cotizar, pedir modelo")
        return None

    candidatos = await buscar_google_sheets(query, marca, modelo, "display", devolver_todos=True)
    # Quedarnos con displays de iPhone que contengan el número base exacto.
    relevantes = [
        (s, p, h) for (s, p, h) in candidatos
        if "iphone" in p.get("nombre", "").lower()
        and re.search(rf"\b{re.escape(base)}\b", p.get("nombre", "").lower())
    ]
    if not relevantes:
        logger.info(f"[SHEETS] Sin displays iPhone para base '{base}'")
        return None

    # Agrupar por variante presente en el nombre.
    por_variante: Dict[Optional[str], list] = defaultdict(list)
    for s, p, h in relevantes:
        por_variante[_variante_en_titulo(p["nombre"], base)].append(p)

    def _mejor(productos: list) -> Dict:
        return max(productos, key=_precio_orden)

    # El cliente especificó variante (ej "14 pro max").
    if variante_pedida:
        if variante_pedida in por_variante:
            modelo_fmt = _formatear_modelo(base, variante_pedida)
            logger.info(f"[SHEETS] iPhone variante exacta '{modelo_fmt}'")
            return await formatear_cotizacion_sheets(_mejor(por_variante[variante_pedida]), "iPhone", modelo_fmt)
        # Pidió una variante que no tenemos → ofrecer las disponibles.
        logger.info(f"[SHEETS] Variante '{variante_pedida}' no está; ofreciendo disponibles")
        return _formatear_pregunta_variantes(
            "iPhone", base, [v or "__base__" for v in por_variante.keys()]
        )

    # No especificó variante.
    if len(por_variante) > 1:
        logger.info(f"[SHEETS] iPhone {base} con varias variantes → preguntar versión")
        return _formatear_pregunta_variantes(
            "iPhone", base, [v or "__base__" for v in por_variante.keys()]
        )

    # Una sola variante (o solo el base): cotizar directo.
    unica_variante = next(iter(por_variante))
    modelo_fmt = _formatear_modelo(base, unica_variante) if unica_variante else base.upper()
    logger.info(f"[SHEETS] iPhone {modelo_fmt} variante única → cotizar")
    return await formatear_cotizacion_sheets(_mejor(por_variante[unica_variante]), "iPhone", modelo_fmt)


async def cotizar_google_sheets(
    marca: str, modelo: str, refaccion: str = "display"
) -> Optional[str]:
    """
    Busca una pieza en Google Sheets y retorna la cotización formateada.

    CRÍTICO: Pasa refaccion a buscar_google_sheets() para filtrar hojas.

    Retorna:
      - Cotización formateada si encuentra la pieza
      - Pregunta de variante si el modelo es ambiguo (iPhone 14 vs 14 Pro vs Pro Max)
      - None si no encontró
    """
    query = " ".join(p for p in [refaccion, marca, modelo] if p).strip()
    if not query:
        return None

    # Displays de iPhone (celular, no reloj): manejar variantes antes de cotizar.
    if refaccion == "display" and _es_marca_iphone(marca) and not _es_consulta_reloj(query, marca, modelo):
        return await _cotizar_display_iphone(query, marca, modelo)

    # PASAR refaccion para filtrar las hojas correctas
    producto = await buscar_google_sheets(query, marca, modelo, refaccion)
    if not producto:
        return None

    return await formatear_cotizacion_sheets(producto, marca, modelo)
