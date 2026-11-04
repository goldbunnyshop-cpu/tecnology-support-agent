#   1. cargar_csv_hugo()  -> Parser robusto que respeta las filas-header de marca
#      del CSV (SAMSUNG,,,,, IPHONE,,,,, etc.) para anclar cada producto a su marca.
#   2. obtener_cotizacion_display(marca, modelo)
#         a) filtra a la marca correcta
#         b) extrae (base, variante) del query y de cada producto
#         c) si el modelo es ambiguo (solo hay variantes, o coexisten base + variantes)
#            -> devuelve pregunta de variantes SIN precios
#         d) si hay match exacto -> cotiza con promedios por categoria
#   3. Las respuestas se devuelven con instrucciones inline para el LLM, para
#      que NO inserte tecnicismos (INCELL, Cartan HG, etc.) ni invente precios
#      cuando estamos pidiendo confirmar la variante.

import os
import re
import csv
import logging
import unicodedata
from io import StringIO
from collections import defaultdict
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger("agentkit")

# Mapeo confirmado de calidad:
#   GENERICO:  INCELL, COG, CARTAN INCELL (compuesto: prioridad sobre CARTAN solo)
#   ORIGINAL:  ORIG, OLED, COF, FHD, DD SOFT, DD SOFT OLED, HG ORIG
#   AMOLED:    AMOLED
MULTIPLICADOR_USD_A_MXN = 4
# Regla comercial (actualizada jul-2026):
# - GENERICO (INCELL, COG, TLED, CARTAN INCELL): x4
# - ORIGINAL (OLED, ORIG, COF, FHD, DD SOFT, HG ORIG):  x4
# - AMOLED:  x3
# Nota: todos los precios en Hugo Shop son en MXN (costo al negocio).
# El multiplicador convierte costo MXN → precio de venta MXN.
# IMOBILE (proveedor premium) usa su propio multiplicador en pricing_sheets.py.
MULTIPLICADOR_POR_CATEGORIA = {
    'GENERICO': 4,
    'ORIGINAL': 4,
    'AMOLED': 3,
}
# Piso mínimo de precio al cliente (jul-2026).
# Si el display más barato (GENÉRICO u ORIGINAL, sin contar C/M) resulta < PISO_GENERICO
# → se activa el piso y se muestran precios fijos en lugar de los calculados.
PISO_GENERICO = 600   # MXN — precio mínimo para calidad genérica
PISO_ORIGINAL = 900   # MXN — precio mínimo para calidad original

RUTA_CSV_HUGO = "knowledge/hugo_shop.csv"

# Marcas que aparecen como filas-header en el CSV (separadoras de seccion)
MARCAS_HEADER = {
    'ALCATEL', 'CUBOT', 'GOOGLE', 'HISENSE', 'HONOR', 'HUAWEI',
    'INFINIX',  # nueva marca en lista jul-2026
    'IPHONE', 'LG', 'NOKIA', 'OPPO', 'SAMSUNG', 'TCL', 'VIVO',
    'XIAOMI', 'ZTE', 'MOTOROLA', 'MOTO', 'POCO', 'REDMI',
    'ONEPLUS', 'ONE PLUS',  # CSV jul-2026 usa "ONE PLUS" con espacio
    'REALME',
}

# Typos y alias de variantes — normaliza lo que escribe el cliente → variante real en CSV
ALIAS_VARIANTES: dict[str, str] = {
    # Motorola Edge (typo frecuente)
    "funcion":    "fusion",
    "funciona":   "fusion",
    "fusión":     "fusion",
    # Sufijos iPhone/Samsung
    "promax":     "pro max",
    "pro maximo": "pro max",
    # Otros typos
    "litee":  "lite",
    "pluss":  "plus",
    "oultra": "ultra",
    "ultre":  "ultra",
    "neon":   "neo",
}


# Alias para mapear lo que escribe el cliente al header del CSV
ALIAS_MARCAS = {
    'iphone': 'IPHONE',
    'apple': 'IPHONE',
    'samsung': 'SAMSUNG',
    'galaxy': 'SAMSUNG',
    'motorola': 'MOTO',
    'moto': 'MOTO',
    'google': 'GOOGLE',
    'google pixel': 'GOOGLE',
    'pixel': 'GOOGLE',
    'huawei': 'HUAWEI',
    'honor': 'HONOR',
    'hisense': 'HISENSE',
    'xiaomi': 'XIAOMI',
    'poco': 'XIAOMI',
    'redmi': 'XIAOMI',
    'oppo': 'OPPO',
    'realme': 'REALME',
    'oneplus': 'ONE PLUS',
    'one plus': 'ONE PLUS',
    'infinix': 'INFINIX',
    'vivo': 'VIVO',
    'tcl': 'TCL',
    'zte': 'ZTE',
    'nokia': 'NOKIA',
    'lg': 'LG',
    'alcatel': 'ALCATEL',
    'cubot': 'CUBOT',
}


# ============================================================
# PARSER CSV ROBUSTO
# ============================================================

def cargar_csv_hugo() -> list[dict]:
    """Carga productos del CSV de Hugo Shop con marca anclada por seccion.

    El CSV usa filas como 'SAMSUNG,,,,,' como separadores de seccion. Las
    aprovecho para etiquetar cada producto con su MARCA correcta sin tener
    que adivinarla por la descripcion.
    """
    datos = []
    if not os.path.exists(RUTA_CSV_HUGO):
        logger.warning(f"[PRICING] CSV no encontrado en {RUTA_CSV_HUGO}")
        return datos

    try:
        # Leer y limpiar nulos del archivo crudo
        with open(RUTA_CSV_HUGO, 'rb') as f:
            crudo = f.read().replace(b'\x00', b'').decode('utf-8', errors='replace')

        reader = csv.reader(StringIO(crudo))
        headers = next(reader, None)
        if not headers:
            logger.error("[PRICING] CSV sin encabezado")
            return datos

        marca_actual = None
        for row in reader:
            if not row or all(not str(c or '').strip() for c in row):
                continue
            # Garantizar 6 columnas (CODIGO, DESCRIPCION, CALIDAD, COLOR, PRECIO_1, PRECIO_2)
            while len(row) < 6:
                row.append('')

            codigo = str(row[0] or '').strip()
            descripcion = str(row[1] or '').strip()
            calidad = str(row[2] or '').strip()
            color = str(row[3] or '').strip()
            precio_1 = str(row[4] or '').strip()

            # Descartar header HUGO SHOP / COTIZACIONES
            cod_upper = codigo.upper()
            if cod_upper.startswith('HUGO SHOP') or cod_upper.startswith('COTIZACIONES'):
                continue

            # Detectar fila-header de marca: CODIGO=marca conocida y resto vacio
            if cod_upper in MARCAS_HEADER and not descripcion and not precio_1:
                marca_actual = cod_upper
                continue
            # Variante: DESCRIPCION trae la marca
            if descripcion.upper() in MARCAS_HEADER and not codigo and not precio_1:
                marca_actual = descripcion.upper()
                continue

            # Producto valido: necesita CODIGO + DESCRIPCION + PRECIO
            if not codigo or not descripcion or not precio_1:
                continue

            # Ignorar baterias (no son displays). En el CSV las baterias tienen
            # la columna CALIDAD desplazada (precio donde deberia ir la calidad).
            if descripcion.lower().startswith('bateria') or descripcion.lower().startswith('bateri'):
                continue

            precio_usd = _extraer_precio_usd(precio_1)
            if not precio_usd:
                continue

            # Detectar basura en la columna CALIDAD (precio, ciudades, etc.)
            if calidad.startswith('$') or calidad.lower().startswith('cuauh') or len(calidad) > 100:
                calidad = ''

            # Lista oct-2026: algunas descripciones repiten la marca como prefijo
            # ("XIAOMI-MI12T", "REALME- C35"). Se quita para que el modelo haga match.
            descripcion = re.sub(r'^(?:XIAOMI|SAMSUNG|HUAWEI|MOTO(?:ROLA)?)\s*-\s*', '', descripcion, flags=re.I).strip()
            # iPhone: "JK X14" (JK = marca del panel) y "2 X14PRO" (dígito suelto) → "X14", "X14PRO"
            if (marca_actual or '') == 'IPHONE':
                descripcion = re.sub(r'^(?:JK\s+|\d\s+)(?=X)', '', descripcion, flags=re.I).strip()
                # "(Diagnóstico)" / "-DIAGNÓSTICO" = calidad premium: se marca en CALIDAD y se
                # quita del nombre para que el modelo haga match (X17(MOVIL IC)-DIAGNÓSTICO → X17(MOVIL IC))
                if 'DIAGNOSTICO' in _quitar_acentos(descripcion).upper():
                    descripcion = re.sub(r'-?\s*\(?\s*diagn[oó]stico\s*\)?', ' ', descripcion, flags=re.I)
                    if 'DIAGN' not in _quitar_acentos(calidad).upper():
                        calidad = f"{calidad} (Diagnóstico)".strip()
                descripcion = re.sub(r'-?\s*120\s*HZ', ' ', descripcion, flags=re.I)   # "X14PRO (MOVIL IC)- 120HZ"
                descripcion = re.sub(r'\b(\d)G\b', r'\1', descripcion)                   # "8G/SE 2020" → "8/SE 2020"
                descripcion = re.sub(r'\s+', ' ', descripcion).strip(' -')

            fila = {
                'MARCA': marca_actual or '',
                'CODIGO': codigo,
                'DESCRIPCION': descripcion,
                'CALIDAD': calidad,
                'COLOR': color or 'Sin especificar',
                'PRECIO_USD': precio_usd,
                'PRECIO_1': precio_1,
            }
            datos.append(fila)

            # Realme viene dentro de la sección OPPO ("REALME- C35", "REALME7 5G/..."):
            # se agrega también como marca REALME para que "realme c35" lo encuentre.
            m_realme = re.match(r'^REALME\s*-?\s*', descripcion, flags=re.I)
            if (marca_actual or '') == 'OPPO' and m_realme:
                datos.append({**fila, 'MARCA': 'REALME', 'DESCRIPCION': descripcion[m_realme.end():].strip()})

        logger.info(f"[PRICING] Cargados {len(datos)} productos de Hugo Shop")
        return datos
    except Exception as e:
        logger.error(f"[PRICING] Error cargando CSV: {e}", exc_info=True)
        return datos


def _quitar_acentos(texto: str) -> str:
    """Elimina acentos para comparación: fusión→fusion, á→a, etc."""
    return ''.join(
        c for c in unicodedata.normalize('NFD', texto)
        if unicodedata.category(c) != 'Mn'
    )


def _extraer_precio_usd(precio_str: str) -> float | None:
    if not precio_str:
        return None
    try:
        limpio = str(precio_str).replace('$', '').replace('USD', '').replace(',', '').strip()
        valor = float(limpio)
        return valor if valor > 0 else None
    except (ValueError, TypeError):
        return None


def _es_con_marco(calidad_str: str) -> bool:
    """Detecta si el producto es variante 'Con Marco' (C/M) en la columna CALIDAD."""
    c = str(calidad_str or '').upper()
    return ' C/M' in c or 'CON MARCO' in c


# ============================================================
# CATEGORIA DE CALIDAD (mapeo confirmado por negocio)
# ============================================================

def obtener_categoria(calidad_str: str) -> str | None:
    """Mapea la calidad cruda del CSV a una de tres categorias del cliente.

    Orden de chequeo importa:
      1. AMOLED (exclusivo)
      2. CARTAN INCELL -> GENERICO (compuesto antes que CARTAN solo)
      3. ORIGINAL (palabras premium)
      4. GENERICO (INCELL/COG)
    """
    if not calidad_str:
        return None
    c = str(calidad_str).strip().upper()
    # Limpiar sufijos de marco que no aportan categoria
    for sufijo in (' S/M', ' C/M', ' SIN MARCO', ' CON MARCO'):
        c = c.replace(sufijo, '')

    if 'AMOLED' in c:
        return 'AMOLED'

    # Compuestos genéricos: TLED y CARTAN TLED son paneles LCD baratos (como INCELL)
    if 'TLED' in c:
        return 'GENERICO'

    # Compuesto: CARTAN INCELL es generico (predomina INCELL)
    if 'CARTAN INCELL' in c:
        return 'GENERICO'

    # Original: ORIG, OLED, COF, FHD, DD SOFT, HG ORIG
    palabras_original = ('HG ORIG', 'DD SOFT', 'OLED', 'ORIG', 'COF', 'FHD', 'CARTAN')
    if any(p in c for p in palabras_original):
        return 'ORIGINAL'

    # Generico: INCELL, COG
    if any(p in c for p in ('INCELL', 'COG')):
        return 'GENERICO'

    logger.debug(f"[PRICING] Calidad no reconocida: {calidad_str}")
    return None


# ============================================================
# NORMALIZADOR DE VARIANTES
# ============================================================

# Variantes "sufijo letra" reconocidas para Samsung (A21S, A21E, A21A)
SUFIJOS_LETRA_SAMSUNG = set('abcdefghijklmnopqrstuvwxyz')


def normalizar_modelo_descripcion(descripcion: str, marca_header: str) -> list[tuple[str | None, str | None]]:
    """De la descripcion del CSV extrae TODAS las parejas (base, variante) que cubre.

    Un mismo display suele ser compatible con varios modelos separados por '/'.
    Cada chunk se parsea por separado segun la marca.

    Ejemplos:
      iPhone:    'X14 PRO'                -> [('14','pro')]
                 'X14/X14 PLUS'           -> [('14',None),('14','plus')]
                 'X12/12PRO'              -> [('12',None),('12','pro')]
      Samsung:   'A21S/A217'              -> [('a21','s'),('a21','7')]
                 'S21 PLUS'               -> [('s21','plus')]
      Hisense:   'V60/E60'                -> [('v60',None),('e60',None)]
                 'H40 LITE/E40/V40'       -> [('h40','lite'),('e40',None),('v40',None)]
      Motorola:  'EDGE 40/EDGE 40 NEO/EDGE 2023' -> [('edge','40'),('edge','40 neo'),('edge','2023')]
      Generico:  'X12/12PRO (MOVIL IC)'   -> parentesis se descarta -> [('12',None),('12','pro')]
    """
    if not descripcion:
        return []

    d = descripcion.lower()
    # Quitar marcadores de marco/proveedor que contienen "/" ANTES de partir por "/":
    # "W/F S20 FE" se partía en "w" + "f s20 fe" y "S/M(BOUTIQUE)" en "s" + "m" → ~120 productos
    # del catálogo (13%) no se encontraban (ej. Samsung S20 FE, Moto E20/E22/E30).
    d = re.sub(r'\b[cs]/m\b', ' ', d)                       # C/M, S/M (con/sin marco)
    d = re.sub(r'^\s*w/f\b', ' ', d)                         # prefijo W/F
    # Quitar parentesis (notas como "(MOVIL IC)", "(BOUTIQUE)", etc.) y restos sin abrir: "BOUTIQUE)"
    d = re.sub(r'\([^)]*\)', ' ', d)
    d = re.sub(r'[^\s/]*\)', ' ', d)
    d = re.sub(r'\bboutique\b', ' ', d)
    chunks = []
    for c in d.split('/'):
        # Prefijos de proveedor/calidad al inicio: WF, WF-B, WF-G…, AA, HG
        c = re.sub(r'^\s*(?:wf(?:-[a-z]+)?|aa|hg)\s+', '', c)
        c = re.sub(r'\s+', ' ', c).strip()
        if c:
            chunks.append(c)

    pares: list[tuple[str | None, str | None]] = []
    vistos: set[tuple[str | None, str | None]] = set()
    for chunk in chunks:
        par = _parsear_chunk_descripcion(chunk, marca_header)
        if par and par not in vistos:
            pares.append(par)
            vistos.add(par)
    return pares


def _parsear_chunk_descripcion(chunk: str, marca_header: str) -> tuple[str | None, str | None] | None:
    """Aplica reglas por marca a un solo chunk (texto entre dos '/' o el unico)."""
    # Limpiar sufijos de calidad/spec que ensucian el nombre del modelo
    chunk = re.sub(r'\s*-\s*\d+hz\b', '', chunk)        # "- 120HZ" / "-120HZ"
    chunk = re.sub(r'\bcartan\b', '', chunk)            # "CARTAN" (es calidad, no modelo)
    chunk = re.sub(r'\bdiagnostico\b', '', chunk)       # "Diagnostico"
    chunk = re.sub(r'-+\s*$', '', chunk).strip()        # trailing "-"
    chunk = re.sub(r'\s+', ' ', chunk).strip()          # colapsar espacios
    tokens = chunk.split()
    if not tokens:
        return None
    primer = tokens[0]
    resto = ' '.join(tokens[1:]).strip() or None
    marca = (marca_header or '').upper()

    # iPhone: prefijo X opcional (en el CSV alternan X14 y 14 cuando hay multi-codigo)
    if marca == 'IPHONE':
        m = re.match(r'^x?(\d+)([a-z]*)$', primer)
        if m and m.group(1):
            base = m.group(1)
            sufijo_letra = m.group(2) or None
            variante = ' '.join(filter(None, [sufijo_letra, resto])).strip() or None
            return base, variante

    # Patron Samsung tipo A21S, S21E (letra + digitos + letra(s) finales)
    m = re.match(r'^([a-z]\d+)([a-z]+)$', primer)
    if m and m.group(2)[0] in SUFIJOS_LETRA_SAMSUNG:
        variante = ' '.join(filter(None, [m.group(2), resto])).strip() or None
        return m.group(1), variante

    # Letra + digitos sin sufijo (S21, A21, V60, E60, H40)
    if re.match(r'^[a-z]\d+$', primer):
        return primer, resto

    # Multi-letras + digitos pegados (EDGE20, EDGE50, NOVA9, NOVA10).
    # El CSV alterna "EDGE 20" y "EDGE20" — normalizamos a base=letras, variante=digitos+resto
    # para que ambas formas matcheen contra el query del cliente ("edge 20 lite").
    m = re.match(r'^([a-z]{2,})(\d+)([a-z]*)$', primer)
    if m:
        base = m.group(1)
        digit_part = m.group(2) + (m.group(3) or '')
        variante = ' '.join(filter(None, [digit_part, resto])).strip() or None
        return base, variante

    # Numero puro (Pixel 7, iPhone 12, Moto G42 cae en patron de arriba)
    m = re.match(r'^(\d+)([a-z]*)$', primer)
    if m:
        base = m.group(1)
        sufijo = m.group(2) or None
        variante = ' '.join(filter(None, [sufijo, resto])).strip() or None
        return base, variante

    # FIX Bug 3 (Poco M5s): Si el primer token es una marca conocida (POCO, REDMI…)
    # dentro de una descripción, stripearla y re-parsear el modelo real.
    # Ej: 'POCO M5S' → strip 'poco' → re-parsear 'm5s' → ('m5', 's')
    # Ej: 'POCO M4'  → strip 'poco' → re-parsear 'm4'  → ('m4', None)
    # Esto ocurre en descripciones XIAOMI como "NOTE10 4G/10S/POCO M5S".
    if primer in ALIAS_MARCAS and len(tokens) > 1:
        sub_chunk = ' '.join(tokens[1:])
        sub_par = _parsear_chunk_descripcion(sub_chunk, marca_header)
        if sub_par and sub_par[0]:
            return sub_par

    # Fallback: primer token como base, resto como variante (ej "EDGE 40")
    return primer, resto


def normalizar_modelo_query(modelo_str: str, marca: str) -> tuple[str | None, str | None]:
    """Del query del cliente extrae (base, variante).

    Ejemplos:
      ('14 pro', 'iphone')        -> ('14', 'pro')
      ('14', 'iphone')            -> ('14', None)
      ('a21', 'samsung')          -> ('a21', None)
      ('a21s', 'samsung')         -> ('a21', 's')
      ('s21', 'samsung')          -> ('s21', None)
      ('s21 plus', 'samsung')     -> ('s21', 'plus')
    """
    if not modelo_str:
        return None, None
    m = modelo_str.lower().strip()
    # Quitar la marca si vino incluida en el modelo
    for marca_lower in ALIAS_MARCAS:
        m = re.sub(rf'\b{re.escape(marca_lower)}\b', '', m).strip()
    if not m:
        return None, None

    # Colapsar "10 +" → "10+" antes de tokenizar (cliente escribe espacio antes de +)
    m = re.sub(r'(\d)\s+\+', r'\1+', m)
    # Colapsar "10 plus" → "10plus" también para variante
    m = re.sub(r'(\d)\s+plus\b', r'\1plus', m)

    # "5g"/"4g"/"lte" son conectividad, no variante de pantalla ("s20 fe 5g" → "s20 fe").
    m = re.sub(r'\b(?:[45]g|lte)\b', ' ', m)
    m = re.sub(r'\s+', ' ', m).strip()
    tokens = m.split()
    if not tokens:
        return None, None
    # Limpiar puntuación residual del primer token (ej: "e32," → "e32")
    primer = re.sub(r'[^a-z0-9\+\-]', '', tokens[0])
    if not primer:
        primer = tokens[0]  # fallback: usar token original
    resto = ' '.join(tokens[1:]).strip() or None

    marca_norm = (ALIAS_MARCAS.get(marca.lower().strip(), '') or '').upper()

    # iPhone: el query es solo el numero (sin prefijo X)
    if marca_norm == 'IPHONE':
        m_num = re.match(r'^(\d+)([a-z]*)$', primer)
        if m_num:
            base = m_num.group(1)
            sufijo = m_num.group(2) or None
            variante = ' '.join(filter(None, [sufijo, resto])).strip() or None
            # Limpiar palabras que significan 'base sin variante'
            PALABRAS_BASE = {'normal', 'base', 'estandar', 'regular'}
            if variante and variante.lower() in PALABRAS_BASE:
                variante = None
            return base, variante

    # Patron A21S
    mm = re.match(r'^([a-z]\d+)([a-z]+)$', primer)
    if mm and mm.group(2)[0] in SUFIJOS_LETRA_SAMSUNG:
        variante = ' '.join(filter(None, [mm.group(2), resto])).strip() or None
        return mm.group(1), variante

    # A21 / S21
    if re.match(r'^[a-z]\d+$', primer):
        return primer, resto

    # EDGE50 / NOVA9 / similares (letras+digitos pegados)
    mm = re.match(r'^([a-z]{2,})(\d+)([a-z]*)$', primer)
    if mm:
        base = mm.group(1)
        digit_part = mm.group(2) + (mm.group(3) or '')
        variante = ' '.join(filter(None, [digit_part, resto])).strip() or None
        return base, variante

    # numero
    mm = re.match(r'^(\d+)([a-z]*)$', primer)
    if mm:
        base = mm.group(1)
        sufijo = mm.group(2) or None
        variante = ' '.join(filter(None, [sufijo, resto])).strip() or None
        return base, variante

    return primer, resto


def _marca_canonica(marca_query: str) -> str | None:
    mq = (marca_query or '').lower().strip()
    if not mq:
        return None
    # Match directo por alias
    if mq in ALIAS_MARCAS:
        return ALIAS_MARCAS[mq]
    # Match por primera palabra
    primera = mq.split()[0]
    if primera in ALIAS_MARCAS:
        return ALIAS_MARCAS[primera]
    # Match por contencion (ej 'pixel 7' -> 'pixel' esta en ALIAS)
    for alias, canonica in ALIAS_MARCAS.items():
        if alias in mq:
            return canonica
    return None


# ============================================================
# FORMATEO DE RESPUESTAS
# ============================================================

# Etiquetas que ve el cliente. SOLO estas tres - sin tecnicismos en parentesis.
ETIQUETAS_CATEGORIA = {
    'GENERICO': 'Calidad Genérica',
    'ORIGINAL': 'Calidad Original',
    'AMOLED': 'Calidad AMOLED Premium',
}


def clasificar_calidad_titulo(titulo: str, es_display: bool) -> str | None:
    """Clasifica la calidad a partir del TITULO del producto (no de una columna CALIDAD).

    A diferencia de obtener_categoria() (pensada para la columna CALIDAD de Hugo),
    aqui INCELL / COPIA / IPS / LCD DOMINAN sobre 'FHD': un "Incell FHD" es un panel
    GENERICO (FHD describe la resolucion, no es premium). Lo usan las fuentes cuya
    calidad viene escrita en el nombre del producto (Google Sheets, fixoem):

      'iPhone 13 Incell FHD'      -> GENERICO
      'iPhone 13 Pro Max Oled'    -> ORIGINAL
      'Hisense E50 Copia Alta'    -> GENERICO
      'Honor 90 Original con Marco' -> ORIGINAL
      'Display ... Amoled'        -> AMOLED
    """
    if not titulo:
        return None
    c = titulo.upper()
    if 'AMOLED' in c:
        return 'AMOLED'
    tiene_generico = any(p in c for p in (
        'INCELL', 'IN-CELL', 'COG', 'IPS', 'LCD', 'COPIA', 'GENERIC', 'GENÉRIC',
    ))
    tiene_original = any(p in c for p in (
        'OLED', 'ORIGINAL', 'ORIG', ' COF', 'DD SOFT', 'HG ORIG',
    ))
    # Caso especial imobile: "Original con Glass Copia Marco" → el panel ES original,
    # solo el marco/vidrio es aftermarket. Si ORIGINAL y COPIA coexisten → ORIGINAL.
    if tiene_generico and tiene_original:
        return 'ORIGINAL'
    # INCELL/COPIA solos (sin ORIGINAL) mandan → genérico.
    if tiene_generico:
        return 'GENERICO'
    if tiene_original:
        return 'ORIGINAL'
    # Sin pista de calidad: un display suele ser un LCD comun (generico);
    # otras piezas (tapa, bateria) no tienen tiers de calidad.
    return 'GENERICO' if es_display else None


def _categorias_finales(productos: list[dict]) -> dict[str, list[float]]:
    """De productos de Hugo Shop arma {CATEGORIA: [precios_finales_mxn]}.

    Los productos Con Marco (C/M en columna CALIDAD) van al bucket 'CON_MARCO'
    para mantenerlos separados del tier ORIGINAL sin marco.
    El resto: GENERICO/ORIGINAL x4, AMOLED x3.
    """
    categorias: dict[str, list[float]] = defaultdict(list)
    for p in productos:
        calidad_raw = p.get('CALIDAD', '')
        cat = obtener_categoria(calidad_raw)  # strips C/M internamente antes de clasificar
        precio = p.get('PRECIO_USD')
        if cat and precio:
            mult = MULTIPLICADOR_POR_CATEGORIA.get(cat, MULTIPLICADOR_USD_A_MXN)
            precio_final = precio * mult
            if _es_con_marco(calidad_raw):
                categorias['CON_MARCO'].append(precio_final)
            else:
                categorias[cat].append(precio_final)
    return categorias


def formatear_cotizacion_tiers(marca: str, modelo: str, categorias: dict[str, list[float]]) -> str:
    """Formatea la cotizacion mostrando una linea por calidad disponible.

    Logica de precios (jul-2026):
    - Piso minimo: si el display mas barato (GENERICO u ORIGINAL, sin C/M) < $600
      → mostrar Generica $600 / Original $900 en lugar de precios calculados.
    - AMOLED: siempre a precio real (no entra en el piso).
    - Con Marco (CON_MARCO): solo aparece si existe en CSV y precio × mult > Original mostrado.
    """
    precios_gen = categorias.get('GENERICO', [])
    precios_orig = categorias.get('ORIGINAL', [])
    precios_amoled = categorias.get('AMOLED', [])
    precios_cm = categorias.get('CON_MARCO', [])

    # Piso: aplica solo sobre GENÉRICO y ORIGINAL sin C/M
    precios_base = precios_gen + precios_orig
    usar_piso = bool(precios_base) and min(precios_base) < PISO_GENERICO

    lineas = [f"Para {marca} {modelo.upper()} tenemos estas opciones:\n"]
    hay_precios = False
    original_mostrado = None  # precio de ORIGINAL que ve el cliente (real o piso)

    if usar_piso:
        lineas.append(f"* {ETIQUETAS_CATEGORIA['GENERICO']}: ${PISO_GENERICO:,} MXN")
        hay_precios = True
        # Solo mostrar "Original" al precio piso si Hugo REALMENTE tiene productos ORIGINAL
        # para este modelo. Si solo hay INCELL/genérico en el catálogo, no fabricar un
        # precio "original" inexistente — eso causa que el cliente llegue al módulo
        # con una expectativa de precio que no existe.
        if precios_orig:
            lineas.append(f"* {ETIQUETAS_CATEGORIA['ORIGINAL']}: ${PISO_ORIGINAL:,} MXN")
            original_mostrado = PISO_ORIGINAL
    else:
        for categoria in ('GENERICO', 'ORIGINAL'):
            precios = categorias.get(categoria, [])
            if not precios:
                continue
            precio_mxn = int(sum(precios) / len(precios))
            lineas.append(f"* {ETIQUETAS_CATEGORIA[categoria]}: ${precio_mxn:,} MXN")
            hay_precios = True
            if categoria == 'ORIGINAL':
                original_mostrado = precio_mxn

    # AMOLED Premium: tier superior — solo si precio > Original mostrado.
    # Si no hay Original en este modelo, se muestra siempre.
    # Regla: proveedor puede ofrecer paneles AMOLED recortados (marco menor al de fábrica)
    # → si su precio no supera al Original, no tiene sentido mostrarlo como premium.
    if precios_amoled:
        precio_amoled = int(sum(precios_amoled) / len(precios_amoled))
        if original_mostrado is None or precio_amoled > original_mostrado:
            lineas.append(f"* {ETIQUETAS_CATEGORIA['AMOLED']}: ${precio_amoled:,} MXN")
            hay_precios = True

    # Con Marco: solo si su precio es mayor al Original mostrado al cliente
    if precios_cm:
        precio_cm = int(sum(precios_cm) / len(precios_cm))
        umbral = original_mostrado if original_mostrado is not None else PISO_ORIGINAL
        if precio_cm > umbral:
            lineas.append(f"* Con Marco: ${precio_cm:,} MXN")
            hay_precios = True

    if not hay_precios:
        return _mensaje_no_disponible(marca, modelo)

    lineas.append("")
    lineas.append("Cada display incluye: diagnostico, garantia 90 dias y cambio el mismo dia.")
    lineas.append("Cual opcion te interesa?")

    cuerpo = "\n".join(lineas)
    return (
        "INFORMACION PARA EL CLIENTE (transmitir tal cual; usar solo las etiquetas "
        "'Calidad Genérica', 'Calidad Original', 'Calidad AMOLED Premium', 'Con Marco' - "
        "sin tecnicismos en parentesis; NUNCA mencionar INCELL, OLED, ORIG, COG ni marcas de proveedor):\n\n"
        f"{cuerpo}"
    )


# ============================================================
# REGLA DE PRECIO DE DISPLAYS — vigente desde sep-2026 (definida por Christian)
# Fuente única: catálogo Hugo Shop (PRECIO_1 = costo). imobile y fixoem ya no se usan.
#   x3 = PRECIO_1 × 3, renglón por renglón del catálogo:
#   - x3 < $600            → piso fijo: Genérica $600 / Original $900
#   - $600 ≤ x3 < $1,000   → Genérica = x3, Original = x3 + $300
#   - $1,000 ≤ x3 ≤ $4,000 → x3 exacto con la calidad tal cual del catálogo
#   - x3 > $4,000          → no se cotiza: lo cotiza un técnico
# Etiquetas: C/M=con marco, S/M=sin marco, ORIG/AA/COF=calidad original,
# INCELL=calidad genérica, OLED (solo iPhone)=calidad premium; se quitan CARTAN y BOUTIQUE.
# ============================================================
MULT_DISPLAY = 3
LIMITE_SUMA_ORIGINAL = 1000
EXTRA_ORIGINAL = 300
LIMITE_TRANSFERIR = 4000

# Etiquetas de proveedor que nunca se muestran al cliente
_RE_TAG_PROVEEDOR = re.compile(r"\(\s*(?:MOVIL\s*IC|BOUTIQUE|B)\s*\)|\bCARTAN\b|\bBOUTIQUE\b|\bMOVIL\s*IC\b", re.I)


def etiqueta_calidad_cliente(calidad: str, es_iphone: bool) -> str:
    """Traduce la columna CALIDAD del catálogo al texto que ve el cliente."""
    t = _RE_TAG_PROVEEDOR.sub(" ", (calidad or "").upper())
    t = t.replace("C/M", " con marco ").replace("S/M", " sin marco ")
    if es_iphone:
        t = re.sub(r"\bOLED\b", " calidad premium ", t)
    t = re.sub(r"\b(?:ORIG|AA|COF)\b", " calidad original ", t)
    t = re.sub(r"\bINCELL\b\+?", " calidad genérica ", t)
    t = re.sub(r"[()]", " ", t)
    # quitar repeticiones ("calidad original calidad original")
    palabras, salida = re.sub(r"\s+", " ", t).strip(), []
    for trozo in re.split(r"(calidad (?:original|genérica|premium))", palabras):
        trozo = trozo.strip()
        if trozo and not (trozo in salida and trozo.startswith("calidad ")):
            salida.append(trozo)
    texto = " ".join(salida).strip()
    if not texto:
        return "Calidad original"
    if not texto.lower().startswith("calidad"):
        texto = "calidad " + texto
    return texto[:1].upper() + texto[1:]


def modelo_para_cliente(marca: str, modelo: str) -> str:
    """iPhone X11–X17 del catálogo son iPhone 11–17: quita la X (no toca X, XR, XS, XS MAX)."""
    m = (modelo or "").strip().upper()
    if _marca_canonica(marca) == "IPHONE":
        m = re.sub(r"^X(1[1-7])", r"\1", m)
    return m


def calidad_iphone(calidad: str, descripcion: str = "") -> str | None:
    """iPhone (3 calidades):
    - renglón "(Diagnóstico)"            → PREMIUM (no muestra "pieza desconocida")
    - INCELL                             → GENERICA
    - OLED (HARD/SOFT) y ORIG/COF/AAA    → ORIGINAL (autoprogramable)
    - sin calidad (solo "S/M")            → GENERICA
    - FHD sin OLED (pantalla LCD)        → GENERICA"""
    texto = _quitar_acentos(f"{descripcion or ''} {calidad or ''}".upper())
    if "DIAGN" in texto:
        return "PREMIUM"
    c = (calidad or "").upper()
    if "INCELL" in c:
        return "GENERICA"
    if "OLED" in c:
        return "ORIGINAL"
    if "FHD" in c:      # FHD sin OLED = pantalla LCD → siempre genérica
        return "GENERICA"
    if re.search(r"\b(?:ORIG|COF|AAA|AA)\b", c):
        return "ORIGINAL"
    return "GENERICA"   # sin calidad en el catálogo (ej. "S/M") → genérica


# Al cliente NUNCA se le dice "autoprogramable" ni "diagnóstico".
_ETIQUETA_IPHONE = {
    "GENERICA": "Calidad genérica",
    "ORIGINAL": "Calidad original",
    "PREMIUM": "Calidad premium (no muestra el mensaje de \"pieza desconocida\" en el menú del iPhone)",
}


def precio_x3_por_calidad(x3: int, categoria: str) -> int:
    """Piso y +$300 aplicados a la calidad: genérica = max(x3, $600);
    original/premium: x3 < $600 → $900, $600–$999 → x3 + $300, $1,000 o más → x3. Sin tope."""
    if categoria == "GENERICA":
        return max(x3, PISO_GENERICO)
    if x3 < PISO_GENERICO:
        return PISO_ORIGINAL
    if x3 < LIMITE_SUMA_ORIGINAL:
        return x3 + EXTRA_ORIGINAL
    return x3


def precios_iphone_base(productos: list[dict]) -> dict[str, int]:
    """Precio por calidad de UN modelo de iPhone, antes de la escalera entre modelos."""
    mas_caro: dict[str, float] = {}
    for p in productos:
        costo = p.get("PRECIO_USD")
        if not costo:
            continue
        cat = calidad_iphone(p.get("CALIDAD", ""), p.get("DESCRIPCION", ""))
        if cat is None:
            continue
        mas_caro[cat] = max(mas_caro.get(cat, 0), costo)
    if not mas_caro:
        return {}

    # Piso como las demás marcas: si la genérica queda en piso (x3 < $600) y el catálogo
    # no trae calidad original, también se ofrece Original $900.
    if "GENERICA" in mas_caro and "ORIGINAL" not in mas_caro \
            and int(round(mas_caro["GENERICA"] * MULT_DISPLAY)) < PISO_GENERICO:
        mas_caro["ORIGINAL"] = 0  # precio_x3_por_calidad(0, ORIGINAL) → $900
    # …y al revés: si solo hay original y queda en piso, también se ofrece Genérica $600.
    if "ORIGINAL" in mas_caro and "GENERICA" not in mas_caro and mas_caro["ORIGINAL"] \
            and int(round(mas_caro["ORIGINAL"] * MULT_DISPLAY)) < PISO_GENERICO:
        mas_caro["GENERICA"] = 0  # precio_x3_por_calidad(0, GENERICA) → $600

    precios = {cat: precio_x3_por_calidad(int(round(c * MULT_DISPLAY)), cat) for cat, c in mas_caro.items()}
    # Interno: la calidad premium siempre es la más cara. Si la original del catálogo
    # cuesta más que la de diagnóstico, se intercambian los precios (el cliente no lo ve).
    if "ORIGINAL" in precios and "PREMIUM" in precios and precios["ORIGINAL"] > precios["PREMIUM"]:
        precios["ORIGINAL"], precios["PREMIUM"] = precios["PREMIUM"], precios["ORIGINAL"]
    return precios


# ── Escalera de precios iPhone (nov-2026) ──────────────────────────────────────
# Un modelo nunca cuesta menos que el anterior en la misma calidad:
#   - misma línea, generación anterior (13 → 14, 13 Pro → 14 Pro, 13 Pro Max → 14 Pro Max)
#   - misma generación: Pro Max ≥ Pro ≥ normal, Plus ≥ normal
# Si sale más barato: nuevo = anterior + (anterior − nuevo). Ej.: 13 $1,173, 14 $975 → 14 = $1,371.
_SUFIJO_RANGO = {"": 0, "PLUS": 1, "PRO": 1, "PROMAX": 2}
_cache_escalera: dict = {"mtime": None, "tabla": {}}


def clave_modelo_iphone(modelo: str) -> str:
    """'X14PRO MAX' / '14 pro max' → '14PROMAX'."""
    m = re.sub(r"\s+", "", (modelo or "").upper())
    return re.sub(r"^X(?=\d)", "", m)


def _ajustar(anterior: int, actual: int) -> int:
    return anterior + (anterior - actual) if actual < anterior else actual


def aplicar_escalera_iphone(tabla: dict[str, dict[str, int]]) -> dict[str, dict[str, int]]:
    """Recibe {clave_modelo: {CALIDAD: precio}} y devuelve la tabla con la escalera aplicada."""
    t = {k: dict(v) for k, v in tabla.items()}
    modelos = []
    for k in t:
        m = re.match(r"^(\d+)(PLUS|PROMAX|PRO|)$", k)
        if m:
            modelos.append((int(m.group(1)), m.group(2), k))
    modelos.sort()
    for _ in range(10):  # repetir hasta que no cambie nada
        cambio = False
        for gen, suf, k in modelos:
            for cat in ("GENERICA", "ORIGINAL", "PREMIUM"):
                if cat not in t[k]:
                    continue
                # misma línea, generación anterior más reciente que tenga esa calidad
                previos = [kk for g, sf, kk in modelos if sf == suf and g < gen and cat in t[kk]]
                # misma generación, variante menor (normal < Plus/Pro < Pro Max)
                menores = [kk for g, sf, kk in modelos
                           if g == gen and _SUFIJO_RANGO[sf] < _SUFIJO_RANGO[suf] and cat in t[kk]
                           and not (suf == "PRO" and sf == "PLUS")]
                refs = ([previos[-1]] if previos else []) + menores
                for ref in refs:
                    nuevo = _ajustar(t[ref][cat], t[k][cat])
                    if nuevo != t[k][cat]:
                        t[k][cat] = nuevo
                        cambio = True
        if not cambio:
            break
    return t


def tabla_iphone() -> dict[str, dict[str, int]]:
    """Precios de todos los iPhone del catálogo con la escalera aplicada (cache por fecha del CSV)."""
    try:
        mtime = os.path.getmtime(RUTA_CSV_HUGO)
    except OSError:
        return {}
    if _cache_escalera["mtime"] == mtime:
        return _cache_escalera["tabla"]
    grupos: dict[str, list[dict]] = defaultdict(list)
    for p in cargar_csv_hugo():
        if p.get("MARCA") != "IPHONE":
            continue
        for base, var in normalizar_modelo_descripcion(p["DESCRIPCION"], "IPHONE"):
            if base:
                grupos[clave_modelo_iphone(_formatear_modelo(base, var))].append(p)
    base_tabla = {k: precios_iphone_base(v) for k, v in grupos.items()}
    tabla = aplicar_escalera_iphone({k: v for k, v in base_tabla.items() if v})
    _cache_escalera.update(mtime=mtime, tabla=tabla)
    return tabla


# ── Precios manuales de iPhone (nov-2026) ──────────────────────────────────────
# knowledge/precios_iphone.csv lo llena Christian a mano (lista editable). Cuando existe,
# son los ÚNICOS precios de iPhone: reemplazan el cálculo x3 sobre Hugo Shop.
# Casilla vacía = esa calidad no se ofrece. Modelo que no está en el archivo → técnico.
RUTA_PRECIOS_IPHONE = "knowledge/precios_iphone.csv"
_cache_manual: dict = {"mtime": None, "tabla": {}}


def precios_iphone_manuales() -> dict[str, dict]:
    """{clave_modelo: {"modelo": "13 Pro", "GENERICA": 1500, ...}} desde el CSV manual."""
    try:
        mtime = os.path.getmtime(RUTA_PRECIOS_IPHONE)
    except OSError:
        return {}
    if _cache_manual["mtime"] == mtime:
        return _cache_manual["tabla"]
    tabla: dict[str, dict] = {}
    try:
        with open(RUTA_PRECIOS_IPHONE, encoding="utf-8") as f:
            for fila in csv.DictReader(f):
                modelo = (fila.get("modelo") or "").strip()
                if not modelo:
                    continue
                d = {"modelo": modelo}
                for col, cat in (("generica", "GENERICA"), ("original", "ORIGINAL"), ("premium", "PREMIUM")):
                    v = re.sub(r"[^\d]", "", fila.get(col) or "")
                    if v and int(v) > 0:
                        d[cat] = int(v)
                tabla[clave_modelo_iphone(modelo)] = d
    except Exception as e:
        logger.error(f"[PRICING] No se pudo leer {RUTA_PRECIOS_IPHONE}: {e}")
        return {}
    _cache_manual.update(mtime=mtime, tabla=tabla)
    logger.info(f"[PRICING] Precios manuales iPhone: {len(tabla)} modelos")
    return tabla


def _sin_acentos(t: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", t or "") if unicodedata.category(c) != "Mn")


def _clave_consulta_iphone(modelo: str) -> str:
    """Texto libre del cliente → clave de la lista manual. Ignora palabras de más.
    '15 pro máx' → 15PROMAX · 'iphone 12 pro cambio' → 12PRO · 'xs max' → XSMAX ·
    'se 2022' / '2022' → SE2022 · 'se' → SE · '16 e' → 16E · '6s plus' → 6SPLUS."""
    t = _sin_acentos((modelo or "").lower())
    t = re.sub(r"\b(?:apple|iphone|i\s*phone|ifone|aifon)\b", " ", t)
    t = re.sub(r"[^a-z0-9+ ]", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    if not t:
        return ""
    t = re.sub(r"(\d)(pro|plus|max|mini|air)", r"\1 \2", t)      # "15pro max" → "15 pro max"
    t = re.sub(r"\b10\b", "x", t) if not re.search(r"\b(1[1-9]|[4-9])\b", t) else t   # "iphone 10" = X
    # SE con año o generación ("se 2022", "se 3ra gen", o solo "2022" cuando el detector quitó "SE")
    if re.search(r"\bse\b", t) or re.fullmatch(r"20(16|20|22)", t):
        if re.search(r"2022|\b3\s*(ra|era|a)?\s*gen", t):
            return "SE2022"
        if re.search(r"2020|\b2\s*(da|nd|a)?\s*gen", t):
            return "SE2020"
        if "2016" in t:
            return "SE2016"
    # X / XR / XS / XS MAX
    if re.search(r"\bx\s*s\s*max\b|\bxsmax\b", t):
        return "XSMAX"
    if re.search(r"\bx\s*s\b", t):
        return "XS"
    if re.search(r"\bx\s*r\b", t):
        return "XR"
    # Número + variante
    m = next((x for x in re.finditer(r"\b(\d{1,2})\s*(s|e)?\b", t) if 4 <= int(x.group(1)) <= 20), None)
    if m:
        num, letra, resto = m.group(1), (m.group(2) or "").upper(), t[m.end():]
        if re.search(r"\bpro\s*max\b|\bpromax\b|\bmax\b", resto):
            suf = "PROMAX"
        elif re.search(r"\bpro\b", resto):
            suf = "PRO"
        elif re.search(r"\bplus\b|\+", resto):
            suf = "PLUS"
        elif re.search(r"\bmini\b", resto):
            suf = "MINI"
        elif re.search(r"\bair\b", resto):
            suf = "AIR"
        else:
            suf = ""
        return f"{num}{letra}{suf}"
    if re.search(r"\bx\b", t):
        return "X"
    m = re.search(r"\bse\b\s*(\w+)?", t)
    if m and (m.group(1) or "") not in _PALABRAS_NO_SE:
        return "SE"
    return ""


_PALABRAS_NO_SE = {"me", "te", "le", "les", "lo", "la", "los", "las", "nos", "rompio", "cayo", "quebro",
                   "estrello", "mojo", "apago", "murio", "dano", "descompuso", "calienta", "traba", "reinicia",
                   "puede", "ve", "ven", "oye", "escucha", "carga", "prende", "apaga", "bloqueo", "hace", "queda"}


def modelo_iphone_de_texto(texto: str) -> str | None:
    """Para brain.py: modelo de iPhone legible ('15 Pro Max', 'XS', 'SE 2022') o None."""
    clave = _clave_consulta_iphone(texto)
    if not clave:
        return None
    d = precios_iphone_manuales().get(clave)
    return d["modelo"] if d else clave


def cotizar_iphone_manual(modelo: str) -> str | None:
    """Cotiza con la lista manual. None si no hay lista (se usa el cálculo automático)."""
    tabla = precios_iphone_manuales()
    if not tabla:
        logger.error(f"[PRICING] Lista manual de iPhone vacía o no encontrada ({RUTA_PRECIOS_IPHONE}) → técnico")
        return _mensaje_no_disponible("iPhone", modelo_para_cliente("iphone", modelo))
    clave = _clave_consulta_iphone(modelo)
    if not clave:
        return None   # no dijo modelo: el flujo normal pregunta cuál es
    if clave in tabla:
        d = tabla[clave]
        precios = {k: v for k, v in d.items() if k in ("GENERICA", "ORIGINAL", "PREMIUM")}
        if not precios:
            return _mensaje_no_disponible("iPhone", d["modelo"])
        return _formatear_iphone(d["modelo"], precios)
    # "SE" → SE 2020 / SE 2022; "13" sin más ya es exacto. Prefijo con varias opciones → preguntar
    opciones = [d["modelo"] for k, d in tabla.items() if k.startswith(clave) and k != clave]
    if clave in ("SE", "X") and opciones:
        lista = ", ".join(f"iPhone {o}" for o in opciones)
        return (
            "INFORMACION PARA EL CLIENTE (transmitir esta pregunta tal cual; "
            "NO ofrecer precios todavia hasta que el cliente confirme la variante exacta):\n\n"
            f"Para cotizarte el precio correcto, ¿cuál de estos modelos tienes: {lista}?"
        )
    return _mensaje_no_disponible("iPhone", modelo_para_cliente("iphone", modelo))


# ── Cotización de display iPhone en 2 mensajes (pedido de Christian, 3 nov 2026) ──
# Mensaje 1: precios con pros y contras de cada calidad (juntos, para comparar).
# Mensaje 2: valor del servicio y lo que incluye. NUNCA mencionar Face ID.
from agent.providers.base import SEPARADOR_MENSAJES

# Modelos cuya pantalla de fábrica es LCD: la genérica casi no pierde brillo ni batería.
_IPHONE_LCD = {"XR", "11", "SE", "SE2020", "SE2022", "8", "8PLUS", "7", "7PLUS", "6", "6S", "6PLUS", "6SPLUS"}

_VALOR_SERVICIO_IPHONE = [
    "Somos especialistas en equipos Apple y tu iPhone lo atiende personal certificado.",
    "La pantalla es la pieza más cara del iPhone después de la tarjeta madre, por eso la instalamos "
    "con herramienta de precisión en estación antiestática y la probamos completa antes de entregártela.",
    "",
    "Tu servicio incluye sin costo extra:",
    "* Limpieza interna profesional del equipo",
    "* Limpieza de bocinas, micrófonos, conectores y puerto de carga",
    "* Garantía de 90 días",
    "* Cambio el mismo día",
    "",
    "¿Cuál opción te interesa?",
]


def _avisa_pieza_desconocida(clave: str) -> bool:
    """El aviso de "pieza desconocida" existe del iPhone 11 en adelante (no en SE, X, XR, XS ni 8)."""
    m = re.match(r"(\d+)", clave or "")
    return bool(m) and int(m.group(1)) >= 11


def _descripcion_calidad_iphone(calidad: str, clave: str) -> str:
    aviso = _avisa_pieza_desconocida(clave)
    if calidad == "GENERICA":
        if clave in _IPHONE_LCD:
            contra = "colores menos vivos que la original"
        else:
            contra = "menos brillo y colores menos vivos que la original, y puede gastar más batería"
        txt = f"Funciona bien para uso diario, pero tiene {contra}."
        return txt + (' Aparece el aviso de "pieza desconocida" en el menú del iPhone.' if aviso else "")
    if calidad == "ORIGINAL":
        txt = "Colores, brillo y respuesta táctil como la de fábrica."
        return txt + (' Aparece el aviso de "pieza desconocida" en el menú del iPhone.' if aviso else "")
    return ('Lo más cercano a la pantalla de fábrica y no muestra el aviso de "pieza desconocida".'
            if aviso else "Lo más cercano a la pantalla de fábrica.")


_ICONO_IPHONE = {"GENERICA": "🔹", "ORIGINAL": "🔸", "PREMIUM": "⭐"}
_NOMBRE_IPHONE = {"GENERICA": "Calidad genérica", "ORIGINAL": "Calidad original", "PREMIUM": "Calidad premium"}


def _formatear_iphone(modelo_txt: str, precios: dict[str, int]) -> str:
    clave = _clave_consulta_iphone(modelo_txt)
    bloques = [f"Para iPhone {modelo_txt} tenemos estas opciones:"]
    for c in ("GENERICA", "ORIGINAL", "PREMIUM"):
        if c in precios:
            bloques.append(
                f"{_ICONO_IPHONE[c]} {_NOMBRE_IPHONE[c]}: ${precios[c]:,} MXN\n"
                f"{_descripcion_calidad_iphone(c, clave)}"
            )
    mensaje1 = "\n\n".join(bloques)
    mensaje2 = "\n".join(_VALOR_SERVICIO_IPHONE)
    return (
        "INFORMACION PARA EL CLIENTE (transmitir tal cual; usar solo las etiquetas "
        "de calidad tal como aparecen, sin agregar otras ni marcas de proveedor):\n\n"
        f"{mensaje1}\n{SEPARADOR_MENSAJES}\n{mensaje2}"
    )


def formatear_cotizacion_iphone(marca: str, modelo: str, productos: list[dict]) -> str:
    """iPhone (nov-2026): una línea por calidad (el producto MÁS CARO de cada una), con
    piso, premium siempre la más cara y escalera entre modelos. Sin transferencia por precio alto."""
    precios = tabla_iphone().get(clave_modelo_iphone(modelo)) or precios_iphone_base(productos)
    if not precios:
        return _mensaje_no_disponible(marca, modelo)
    return _formatear_iphone(modelo_para_cliente(marca, modelo), precios)


def formatear_cotizacion_hugo(marca: str, modelo: str, productos: list[dict]) -> str:
    """Cotización de display con la regla x3 vigente, un renglón por producto del catálogo.
    iPhone usa su propio formato por calidad (ver formatear_cotizacion_iphone)."""
    es_iphone = _marca_canonica(marca) == "IPHONE"
    if es_iphone:
        return formatear_cotizacion_iphone(marca, modelo, productos)
    piso = False
    lineas: list[str] = []
    vistos: set = set()
    hay_transferencia = False

    for p in sorted(productos, key=lambda x: x.get("PRECIO_USD") or 0):
        costo = p.get("PRECIO_USD")
        if not costo:
            continue
        x3 = int(round(costo * MULT_DISPLAY))
        if x3 < PISO_GENERICO:
            piso = True
            continue
        if x3 > LIMITE_TRANSFERIR:
            hay_transferencia = True
            continue
        if x3 < LIMITE_SUMA_ORIGINAL:
            clave = ("par", x3)
            linea = f"* Calidad genérica: ${x3:,} MXN / Calidad original: ${x3 + EXTRA_ORIGINAL:,} MXN"
        else:
            etiqueta = etiqueta_calidad_cliente(p.get("CALIDAD", ""), es_iphone)
            clave = (etiqueta, x3)
            linea = f"* {etiqueta}: ${x3:,} MXN"
        if clave not in vistos:
            vistos.add(clave)
            lineas.append(linea)

    if piso:
        lineas.insert(0, f"* Calidad genérica: ${PISO_GENERICO:,} MXN / Calidad original: ${PISO_ORIGINAL:,} MXN")

    if not lineas:
        # Todo el catálogo de este modelo pasa de $4,000 (o no hay precio): lo cotiza un técnico
        logger.info(f"[PRICING] {marca} {modelo}: x3 > ${LIMITE_TRANSFERIR:,} → técnico")
        return _mensaje_no_disponible(marca, modelo)

    if hay_transferencia:
        lineas.append("* Opción de mayor calidad: se la cotiza un técnico")

    modelo_txt = modelo_para_cliente(marca, modelo)
    cuerpo = "\n".join(
        [f"Para {marca} {modelo_txt} tenemos estas opciones:\n"]
        + lineas
        + ["", "Cada display incluye: diagnostico, garantia 90 dias y cambio el mismo dia.",
           "Cual opcion te interesa?"]
    )
    return (
        "INFORMACION PARA EL CLIENTE (transmitir tal cual; usar solo las etiquetas "
        "de calidad tal como aparecen, sin agregar otras ni marcas de proveedor):\n\n"
        f"{cuerpo}"
    )


def _formatear_cotizacion(marca: str, modelo: str, productos: list[dict]) -> str:
    """Cotizacion de Hugo Shop con la regla x3 vigente (sep-2026)."""
    return formatear_cotizacion_hugo(marca, modelo, productos)


def _formatear_modelo(base: str, variante: str | None) -> str:
    """Combina base + variante respetando convencion de naming.

    - Variante de UNA letra (Samsung A21S, A21E): pegada al base sin espacio.
    - Variante palabra (S21 PLUS, 14 PRO MAX, S21 FE): separada por espacio.
    """
    base_up = base.upper()
    if not variante:
        return base_up
    v = variante.strip()
    # Si la primera "palabra" de la variante es una sola letra -> pegar
    primer = v.split()[0] if v else ''
    if len(primer) == 1 and primer.isalpha():
        resto = ' '.join(v.split()[1:])
        return (base_up + primer.upper() + (' ' + resto.upper() if resto else '')).strip()
    return f"{base_up} {v.upper()}".strip()


def _formatear_pregunta_variantes(marca: str, base: str, variantes: list[str]) -> str:
    """Pide al cliente que confirme la variante exacta antes de cotizar."""
    nombres = []
    for v in variantes:
        if v == '__base__':
            nombres.append(base.upper())
        else:
            nombres.append(_formatear_modelo(base, v))
    lista = ", ".join(nombres)
    cuerpo = (
        f"Para {marca} {base.upper()} manejamos varias versiones: {lista}. "
        f"Para cotizarte el precio correcto, necesito confirmar cual tienes. "
        f"Cual es tu modelo exacto? Si no lo recuerdas o no estas seguro, "
        f"te invitamos a acudir al modulo y con gusto te ayudamos a identificarlo."
    )
    return (
        "INFORMACION PARA EL CLIENTE (transmitir esta pregunta tal cual; "
        "NO ofrecer precios todavia hasta que el cliente confirme la variante exacta):\n\n"
        f"{cuerpo}"
    )


def _mensaje_no_disponible(marca: str, modelo: str) -> str:
    """Mensaje inteligente: pregunta aclaraciones en lugar de rechazar."""
    marca_limpia = marca if marca and marca != "No especificado" else ""
    modelo_limpio = modelo if modelo and modelo != "modelo desconocido" else ""

    # Si falta marca O modelo, pedir ambos (tono cálido + empuje a dar el modelo)
    if not marca_limpia or not modelo_limpio:
        return (
            "¡Con mucho gusto te cotizo tu pantalla! 😊\n"
            "Para darte el precio exacto solo dime de qué equipo es:\n\n"
            "📱 *Marca* (Samsung, iPhone, Motorola, Xiaomi...)\n"
            "🔧 *Modelo* (ej. S22 Ultra, 13 Pro Max, A54, Edge 40)\n\n"
            "Mándame marca y modelo y te paso el precio al instante. "
            "Si no estás seguro del modelo, lo encuentras en *Configuración > Acerca del teléfono*."
        )

    # Si tenemos marca y modelo pero no existe en catálogo
    # → El técnico busca disponibilidad y da precio exacto en max 30 min
    return (
        f"Para el display del *{marca_limpia.upper()} {modelo_limpio}* necesito confirmarte "
        f"el precio exacto con el técnico.\n\n"
        f"En un lapso no mayor a 30 minutos un técnico especialista te atenderá personalmente 😊\n"
        f"¿Prefieres que te contactemos por llamada o seguimos por WhatsApp?"
    )


# ============================================================
# API PUBLICA
# ============================================================

def _resolver_match_hugo(marca: str, modelo: str) -> dict:
    """Nucleo de matching contra Hugo Shop. NO formatea: devuelve un resultado
    estructurado para que lo consuman tanto la cotizacion directa como el merge
    con Google Sheets.

    Retorna uno de:
      {"tipo": "no_disponible"}
      {"tipo": "variante", "respuesta": <pregunta para el cliente>}
      {"tipo": "ok", "modelo": <modelo formateado>, "productos": [<dict de Hugo>...]}
    """
    marca_csv = _marca_canonica(marca)
    if not marca_csv:
        logger.warning(f"[PRICING] Marca no reconocida: {marca}")
        return {"tipo": "no_disponible"}
    if marca_csv == "IPHONE":   # iPhone se cotiza SOLO con la lista manual
        return {"tipo": "no_disponible"}

    productos = cargar_csv_hugo()
    productos_marca = [p for p in productos if p.get('MARCA') == marca_csv]
    if not productos_marca:
        logger.warning(f"[PRICING] Sin productos para marca {marca_csv}")
        return {"tipo": "no_disponible"}

    base_q, var_q = normalizar_modelo_query(modelo, marca)
    if not base_q:
        return {"tipo": "no_disponible"}

    # Mapear cada producto a las variantes que cubre para el base solicitado.
    # Un producto multi-modelo (ej "V60/E60") puede cubrir varias variantes; cada
    # producto aparece UNA vez en `matches` con la lista de variantes aplicables.
    base_q_lower = base_q.lower()
    matches: list[tuple[dict, list[str | None]]] = []
    for p in productos_marca:
        pares = normalizar_modelo_descripcion(p['DESCRIPCION'], marca_csv)
        variantes_aplicables = [v for b, v in pares if b and b.lower() == base_q_lower]
        if variantes_aplicables:
            matches.append((p, variantes_aplicables))

    if not matches:
        logger.warning(f"[PRICING] Sin coincidencias para {marca} {modelo} (base={base_q})")
        return {"tipo": "no_disponible"}

    # Set de variantes unicas en todos los productos coincidentes
    variantes_csv = sorted({(v or '__base__').lower() for _, vs in matches for v in vs})

    if var_q:
        # Cliente especifico una variante: buscar productos que la cubran exactamente
        # Normalizar typos antes de buscar (ej: "funcion" → "fusion")
        # También aplicar alias por palabra (ej: "60 fusión" → "60 fusion" reemplazando
        # palabra a palabra, no solo el string completo que está en el dict de alias).
        var_q_raw = var_q.lower()
        # Primero alias exacto de todo el string
        var_q_lower = ALIAS_VARIANTES.get(var_q_raw, var_q_raw)
        # Luego quitar acentos (fusión→fusion, é→e, etc.)
        var_q_norm = _quitar_acentos(var_q_lower)
        exactos = [
            p for p, vs in matches
            if any(_quitar_acentos((v or '').lower()) == var_q_norm for v in vs)
        ]
        if exactos:
            modelo_completo = _formatear_modelo(base_q, var_q)
            logger.info(f"[PRICING] Hugo match exacto: {marca} {modelo_completo} ({len(exactos)} productos)")
            return {"tipo": "ok", "modelo": modelo_completo, "productos": exactos}
        # Sin exact: si la variante del cliente es prefijo de variantes mas completas
        # (ej "50" prefija "50 fusion", "50 neo", "50 ultra") filtramos a esas.
        variantes_filtradas = sorted({
            v.lower() for _, vs in matches for v in vs
            if v and _quitar_acentos(v.lower()).startswith(var_q_norm)
        })
        if variantes_filtradas:
            logger.info(f"[PRICING] Variante '{var_q}' parcial para {marca} {base_q}. Filtradas: {variantes_filtradas}")
            return {"tipo": "variante", "respuesta": _formatear_pregunta_variantes(marca, base_q, variantes_filtradas)}
        logger.info(f"[PRICING] Variante '{var_q}' no existe para {marca} {base_q}. Variantes: {variantes_csv}")
        return {"tipo": "variante", "respuesta": _formatear_pregunta_variantes(marca, base_q, variantes_csv)}

    # Cliente NO especifico variante.
    # Si solo existe el base puro (sin variantes) -> cotizar directo todos los productos
    if variantes_csv == ['__base__']:
        productos_base = [p for p, vs in matches if any(v is None for v in vs)]
        logger.info(f"[PRICING] Hugo base sin variantes: {marca} {base_q}")
        return {"tipo": "ok", "modelo": base_q, "productos": productos_base}

    # FIX: Si el base existe como producto propio (__base__ está en variantes),
    # cotizarlo directamente sin preguntar. Ej: cliente dice "A50" → quiere A50,
    # no hay ambigüedad real; si quisiera A50S lo diría explícitamente.
    # Antes: pedía variante en loop infinito (primera pregunta → cliente dice "A50" → misma pregunta).
    if '__base__' in variantes_csv:
        productos_base = [p for p, vs in matches if any(v is None for v in vs)]
        if productos_base:
            otras = [v for v in variantes_csv if v != '__base__']
            logger.info(
                f"[PRICING] Base existe entre variantes: {marca} {base_q} → cotizando base. "
                f"Otras variantes disponibles: {otras}"
            )
            return {"tipo": "ok", "modelo": base_q, "productos": productos_base}

    # Hay variantes pero el base NO existe como producto propio: preguntar al cliente.
    logger.info(f"[PRICING] Pidiendo variante a cliente para {marca} {base_q}. Disponibles: {variantes_csv}")
    return {"tipo": "variante", "respuesta": _formatear_pregunta_variantes(marca, base_q, variantes_csv)}


async def obtener_cotizacion_display(marca: str, modelo: str) -> str:
    """Punto de entrada usado por brain.py / tools.py. iPhone: lista manual. Resto: Hugo Shop."""
    if _marca_canonica(marca) == "IPHONE":
        return cotizar_iphone_manual(modelo) or _mensaje_no_disponible("iPhone", modelo)
    res = _resolver_match_hugo(marca, modelo)
    if res["tipo"] == "variante":
        return res["respuesta"]
    if res["tipo"] == "ok":
        return _formatear_cotizacion(marca, res["modelo"], res["productos"])
    return _mensaje_no_disponible(marca, modelo)


async def recolectar_categorias_hugo(marca: str, modelo: str) -> dict:
    """Version estructurada de obtener_cotizacion_display para FUSIONAR con otras
    fuentes. Devuelve las calidades de Hugo Shop ya en MXN, sin formatear.

    Retorna uno de:
      {"tipo": "no_disponible"}
      {"tipo": "variante", "respuesta": <pregunta para el cliente>}
      {"tipo": "ok", "marca": str, "modelo": str, "categorias": {CAT: [precios_mxn]}}
    """
    res = _resolver_match_hugo(marca, modelo)
    if res["tipo"] != "ok":
        return res
    return {
        "tipo": "ok",
        "marca": marca,
        "modelo": res["modelo"],
        "categorias": _categorias_finales(res["productos"]),
    }




async def buscar_modelo_sin_marca(modelo: str) -> str:
    """Busqueda por modelo sin marca explícita."""
    if not modelo or len(modelo.strip()) < 2:
        return _mensaje_no_disponible("No especificado", "modelo desconocido")

    productos = cargar_csv_hugo()
    if not productos:
        logger.warning("[PRICING] CSV vacio en busqueda sin marca")
        return _mensaje_no_disponible("No especificado", modelo)

    modelo_lower = modelo.lower().strip()
    for marca_alias in ALIAS_MARCAS:
        modelo_lower = re.sub(rf'\b{re.escape(marca_alias)}\b', '', modelo_lower).strip()

    if not modelo_lower:
        return _mensaje_no_disponible("No especificado", modelo)

    tokens = modelo_lower.split()
    matches_por_marca = defaultdict(list)

    for p in productos:
        marca = p.get('MARCA', '')
        if not marca or marca == 'IPHONE':   # iPhone: lista manual (abajo)
            continue
        pares = normalizar_modelo_descripcion(p['DESCRIPCION'], marca)
        for base, variante in pares:
            if not base:
                continue
            base_lower = base.lower()
            if tokens and tokens[0] == base_lower:
                matches_por_marca[marca].append((p, [variante]))
                break

    if tokens and _clave_consulta_iphone(" ".join(tokens)) in precios_iphone_manuales():
        matches_por_marca['IPHONE'].append(({}, [None]))

    if not matches_por_marca:
        logger.warning(f"[PRICING] Sin productos para '{modelo}' sin marca")
        return _mensaje_no_disponible("No especificado", modelo)

    if len(matches_por_marca) == 1:
        marca = list(matches_por_marca.keys())[0]
        logger.info(f"[PRICING] Busqueda sin marca: '{modelo}' -> {marca}")
        # Reusar el flujo principal para no mezclar variantes/precios por accidente.
        return await obtener_cotizacion_display(marca, modelo)

    marcas_str = ", ".join(sorted(matches_por_marca.keys()))
    cuerpo = (
        f"Encontre displays para {modelo.upper()} en: {marcas_str}. "
        f"De cual marca es tu dispositivo?"
    )
    return f"INFORMACION PARA EL CLIENTE:\n\n{cuerpo}"


async def inicializar_cotizador():
    try:
        logger.info("[PRICING] Inicializando cotizador de precios...")
        if os.path.exists(RUTA_CSV_HUGO):
            datos = cargar_csv_hugo()
            logger.info(f"[PRICING] Sistema listo con {len(datos)} productos de Hugo Shop")
        else:
            logger.warning(f"[PRICING] CSV no encontrado en {RUTA_CSV_HUGO}")
            logger.warning("[PRICING] Asegurate de que 'hugo_shop.csv' este en la carpeta /knowledge")
    except Exception as e:
        logger.error(f"[PRICING] Error inicializando cotizador: {e}", exc_info=True)
