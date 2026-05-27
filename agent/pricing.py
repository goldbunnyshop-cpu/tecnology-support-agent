# agent/pricing.py - Motor de cotizacion con Hugo Shop
#
# Flujo:
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
RUTA_CSV_HUGO = "knowledge/hugo_shop.csv"

# Marcas que aparecen como filas-header en el CSV (separadoras de seccion)
MARCAS_HEADER = {
    'ALCATEL', 'CUBOT', 'GOOGLE', 'HISENSE', 'HONOR', 'HUAWEI',
    'IPHONE', 'LG', 'NOKIA', 'OPPO', 'SAMSUNG', 'TCL', 'VIVO',
    'XIAOMI', 'ZTE', 'MOTOROLA', 'MOTO', 'POCO', 'REDMI',
    'ONEPLUS', 'REALME',
}

# Alias para mapear lo que escribe el cliente al header del CSV
ALIAS_MARCAS = {
    'iphone': 'IPHONE',
    'apple': 'IPHONE',
    'samsung': 'SAMSUNG',
    'galaxy': 'SAMSUNG',
    'motorola': 'MOTOROLA',
    'moto': 'MOTOROLA',
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
    'oneplus': 'ONEPLUS',
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

            datos.append({
                'MARCA': marca_actual or '',
                'CODIGO': codigo,
                'DESCRIPCION': descripcion,
                'CALIDAD': calidad,
                'COLOR': color or 'Sin especificar',
                'PRECIO_USD': precio_usd,
                'PRECIO_1': precio_1,
            })

        logger.info(f"[PRICING] Cargados {len(datos)} productos de Hugo Shop")
        return datos
    except Exception as e:
        logger.error(f"[PRICING] Error cargando CSV: {e}", exc_info=True)
        return datos


def _extraer_precio_usd(precio_str: str) -> float | None:
    if not precio_str:
        return None
    try:
        limpio = str(precio_str).replace('$', '').replace('USD', '').replace(',', '').strip()
        valor = float(limpio)
        return valor if valor > 0 else None
    except (ValueError, TypeError):
        return None


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


def normalizar_modelo_descripcion(descripcion: str, marca_header: str) -> tuple[str | None, str | None]:
    """De la descripcion del CSV extrae (base, variante).

    Ejemplos:
      iPhone:    'X14 PRO'             -> ('14', 'pro')
                 'X14 PRO MAX'         -> ('14', 'pro max')
                 'X14'                 -> ('14', None)
      Samsung:   'A21S'                -> ('a21', 's')
                 'A21S/A217'           -> ('a21', 's')   (multi-codigo: tomo el primero)
                 'S21'                 -> ('s21', None)
                 'S21 FE'              -> ('s21', 'fe')
                 'S21 PLUS'            -> ('s21', 'plus')
      Sufijos en parentesis (ej "(ACTUALIZACION AUTOMATICA)") se descartan.
    """
    if not descripcion:
        return None, None

    # Quitar parentesis y su contenido
    d = re.sub(r'\([^)]*\)', '', descripcion).strip().lower()
    # Multi-codigo: A21S/A217 -> solo el primero
    d = d.split('/')[0].strip()
    tokens = d.split()
    if not tokens:
        return None, None

    primer = tokens[0]
    resto = ' '.join(tokens[1:]).strip() or None
    marca = (marca_header or '').upper()

    # iPhone: prefijo X seguido del numero del modelo
    if marca == 'IPHONE':
        m = re.match(r'^x(\d+)([a-z]*)$', primer)
        if m:
            base = m.group(1)
            sufijo_letra = m.group(2) or None
            variante = ' '.join(filter(None, [sufijo_letra, resto])).strip() or None
            return base, variante

    # Patron Samsung tipo A21S, S21E (letra + digitos + letra(s) finales)
    m = re.match(r'^([a-z]\d+)([a-z]+)$', primer)
    if m and m.group(2)[0] in SUFIJOS_LETRA_SAMSUNG:
        variante = ' '.join(filter(None, [m.group(2), resto])).strip() or None
        return m.group(1), variante

    # Patron letra + digitos sin sufijo (S21, A21)
    if re.match(r'^[a-z]\d+$', primer):
        return primer, resto

    # Patron numero puro (Pixel 7, Moto G42 -> el "g42" cae en el patron de arriba)
    m = re.match(r'^(\d+)([a-z]*)$', primer)
    if m:
        base = m.group(1)
        sufijo = m.group(2) or None
        variante = ' '.join(filter(None, [sufijo, resto])).strip() or None
        return base, variante

    # Fallback: usar primer token como base, el resto como variante
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

    tokens = m.split()
    if not tokens:
        return None, None
    primer = tokens[0]
    resto = ' '.join(tokens[1:]).strip() or None

    marca_norm = (ALIAS_MARCAS.get(marca.lower().strip(), '') or '').upper()

    # iPhone: el query es solo el numero (sin prefijo X)
    if marca_norm == 'IPHONE':
        m_num = re.match(r'^(\d+)([a-z]*)$', primer)
        if m_num:
            base = m_num.group(1)
            sufijo = m_num.group(2) or None
            variante = ' '.join(filter(None, [sufijo, resto])).strip() or None
            return base, variante

    # Patron A21S
    mm = re.match(r'^([a-z]\d+)([a-z]+)$', primer)
    if mm and mm.group(2)[0] in SUFIJOS_LETRA_SAMSUNG:
        variante = ' '.join(filter(None, [mm.group(2), resto])).strip() or None
        return mm.group(1), variante

    # A21 / S21
    if re.match(r'^[a-z]\d+$', primer):
        return primer, resto

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
    'GENERICO': 'Calidad Generica',
    'ORIGINAL': 'Calidad Original',
    'AMOLED': 'AMOLED',
}


def _formatear_cotizacion(marca: str, modelo: str, productos: list[dict]) -> str:
    """Construye la cotizacion final con promedios por categoria.

    Para multiples sub-calidades dentro de la misma categoria (ej INCELL + CARTAN
    INCELL ambos GENERICO), se promedia y se muestra UN solo precio etiquetado
    como 'Calidad Generica'.
    """
    productos_por_categoria = defaultdict(list)
    for p in productos:
        cat = obtener_categoria(p.get('CALIDAD', ''))
        if cat:
            productos_por_categoria[cat].append(p)

    if not productos_por_categoria:
        return _mensaje_no_disponible(marca, modelo)

    lineas = [f"Para {marca} {modelo.upper()} tenemos estas opciones:\n"]
    for categoria in ('GENERICO', 'ORIGINAL', 'AMOLED'):
        productos_cat = productos_por_categoria.get(categoria)
        if not productos_cat:
            continue
        precios = [p['PRECIO_USD'] for p in productos_cat if p.get('PRECIO_USD')]
        if not precios:
            continue
        promedio_usd = sum(precios) / len(precios)
        precio_mxn = int(promedio_usd * MULTIPLICADOR_USD_A_MXN)
        etiqueta = ETIQUETAS_CATEGORIA[categoria]
        linea = f"* {etiqueta}: ${precio_mxn:,} MXN"

        # Listar colores solo si hay precios distintos por color
        precios_por_color = {}
        for p in productos_cat:
            color = p.get('COLOR') or 'Sin especificar'
            precios_por_color.setdefault(color, []).append(p['PRECIO_USD'])
        if len(precios_por_color) > 1:
            colores = sorted(precios_por_color.keys())
            linea += f"  (disponible en: {', '.join(colores)})"
        lineas.append(linea)

    lineas.append("")
    lineas.append("Cada display incluye: diagnostico, garantia 90 dias y cambio el mismo dia.")
    lineas.append("Cual opcion te interesa?")

    cuerpo = "\n".join(lineas)
    return (
        "INFORMACION PARA EL CLIENTE (transmitir tal cual; usar solo las etiquetas "
        "'Calidad Generica', 'Calidad Original', 'AMOLED' - sin tecnicismos en parentesis):\n\n"
        f"{cuerpo}"
    )


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
    return (
        f"Disculpa, no tengo en inventario displays para {marca} {modelo}.\n"
        "Podrias verificar el modelo exacto? O puedo conectarte con un tecnico "
        "para asesorarte sobre alternativas compatibles."
    )


# ============================================================
# API PUBLICA
# ============================================================

async def obtener_cotizacion_display(marca: str, modelo: str) -> str:
    """Punto de entrada usado por brain.py / tools.py."""
    marca_csv = _marca_canonica(marca)
    if not marca_csv:
        logger.warning(f"[PRICING] Marca no reconocida: {marca}")
        return _mensaje_no_disponible(marca, modelo)

    productos = cargar_csv_hugo()
    productos_marca = [p for p in productos if p.get('MARCA') == marca_csv]
    if not productos_marca:
        logger.warning(f"[PRICING] Sin productos para marca {marca_csv}")
        return _mensaje_no_disponible(marca, modelo)

    base_q, var_q = normalizar_modelo_query(modelo, marca)
    if not base_q:
        return _mensaje_no_disponible(marca, modelo)

    # Mapear cada producto a (base, variante) y filtrar por base
    matches = []
    for p in productos_marca:
        base_p, var_p = normalizar_modelo_descripcion(p['DESCRIPCION'], marca_csv)
        if base_p and base_p.lower() == base_q.lower():
            matches.append((p, var_p))

    if not matches:
        logger.warning(f"[PRICING] Sin coincidencias para {marca} {modelo} (base={base_q})")
        return _mensaje_no_disponible(marca, modelo)

    # Variantes unicas presentes en el CSV para este base
    variantes_csv = sorted({(v or '__base__').lower() for _, v in matches})

    if var_q:
        # Cliente especifico una variante: buscar coincidencia exacta
        var_q_lower = var_q.lower()
        exactos = [p for p, v in matches if v and v.lower() == var_q_lower]
        if exactos:
            modelo_completo = _formatear_modelo(base_q, var_q)
            logger.info(f"[PRICING] Cotizando exacto: {marca} {modelo_completo} ({len(exactos)} productos)")
            return _formatear_cotizacion(marca, modelo_completo, exactos)
        # Variante pedida no existe: ofrecer las disponibles
        logger.info(f"[PRICING] Variante '{var_q}' no existe para {marca} {base_q}. Variantes: {variantes_csv}")
        return _formatear_pregunta_variantes(marca, base_q, variantes_csv)

    # Cliente NO especifico variante.
    # Si solo existe el base puro (sin variantes) -> cotizar directo
    if variantes_csv == ['__base__']:
        productos_base = [p for p, v in matches if not v]
        logger.info(f"[PRICING] Cotizando base sin variantes: {marca} {base_q}")
        return _formatear_cotizacion(marca, base_q, productos_base)

    # Hay variantes (con o sin base): preguntar antes de cotizar
    logger.info(f"[PRICING] Pidiendo variante a cliente para {marca} {base_q}. Disponibles: {variantes_csv}")
    return _formatear_pregunta_variantes(marca, base_q, variantes_csv)


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
