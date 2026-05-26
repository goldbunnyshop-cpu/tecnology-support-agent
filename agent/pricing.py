# agent/pricing.py — Motor de cotización con Hugo Shop
import os
import csv
import logging
from pathlib import Path
from collections import defaultdict
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()
logger = logging.getLogger("agentkit")

CATEGORIAS_GENERICO = {'INCELL', 'COG', 'COF'}
CATEGORIAS_ORIGINAL = {'ORIG', 'OLED', 'CARTAN'}
CATEGORIAS_AMOLED = {'AMOLED'}
MULTIPLICADOR_USD_A_MXN = 4
RUTA_CSV_HUGO = "knowledge/hugo_shop.csv"

def cargar_csv_hugo():
    datos = []
    if not os.path.exists(RUTA_CSV_HUGO):
        logger.warning(f"[PRICING] CSV no encontrado en {RUTA_CSV_HUGO}")
        return datos
    try:
        lineas_procesadas = []
        with open(RUTA_CSV_HUGO, 'rb') as f:
            for linea_bytes in f:
                linea_limpia = linea_bytes.replace(b'\x00', b'')
                lineas_procesadas.append(linea_limpia.decode('utf-8'))

        from io import StringIO
        csv_contenido = ''.join(lineas_procesadas)
        csv_file = StringIO(csv_contenido)
        reader = csv.DictReader(csv_file)

        if reader.fieldnames is None:
            logger.error("[PRICING] DictReader no pudo leer el encabezado del CSV")
            return datos

        for idx, row in enumerate(reader):
            if not row:
                continue
            valores_no_vacios = [v for v in row.values() if v and str(v).strip()]
            if not valores_no_vacios:
                continue
            codigo = str(row.get('CODIGO', '')).strip()
            descripcion = str(row.get('DESCRIPCION', '')).strip()
            if 'HUGO SHOP' in codigo or 'COTIZACIONES' in codigo:
                continue
            precio_1 = str(row.get('PRECIO_1', '')).strip()
            if not precio_1:
                continue
            datos.append(row)

        logger.info(f"[PRICING] Cargados {len(datos)} productos de Hugo Shop")
        return datos
    except Exception as e:
        logger.error(f"[PRICING] Error cargando CSV: {e}", exc_info=True)
        return datos

def buscar_productos_en_csv(marca, modelo):
    import re
    datos = cargar_csv_hugo()
    resultados = []
    marca_lower = marca.lower().strip()
    modelo_lower = modelo.lower().strip()

    for producto in datos:
        descripcion = str(producto.get('DESCRIPCION', '')).lower()
        codigo = str(producto.get('CODIGO', '')).lower()

        marca_encontrada = False

        if 'iphone' in marca_lower:
            if re.search(r'x\d+', descripcion):
                marca_encontrada = True
        elif 'google pixel' in marca_lower or 'pixel' in marca_lower:
            # Buscar Pixel por nombre O números (7, 7a, 8, 8a, etc.)
            if 'pixel' in descripcion or re.search(r'\d+[a-z]?', descripcion):
                marca_encontrada = True
        elif 'motorola' in marca_lower or 'moto' in marca_lower:
            # Buscar Motorola por nombre O números (E21, E21S, G42, etc.)
            if 'edge' in descripcion or re.search(r'[a-z]\d+', descripcion):
                marca_encontrada = True
        elif 'samsung' in marca_lower:
            # Buscar variantes: A21, A21S, A21A, S21, S22, etc.
            if re.search(r'[a-z]\d+', descripcion):
                marca_encontrada = True
        elif 'hisense' in marca_lower:
            if any(pattern in descripcion for pattern in ['e50', 'e60', 'e30', 'e40', 'v60', 'h50', 'g85', 'c51', 'c53', 'c36', 'c60']):
                marca_encontrada = True
        else:
            primera_palabra = marca_lower.split()[0]
            if primera_palabra in descripcion:
                marca_encontrada = True

        if not marca_encontrada:
            continue

        modelo_encontrado = False

        if 'iphone' in marca_lower:
            numeros_modelo = re.findall(r'\d+', modelo_lower)
            if numeros_modelo:
                numero = numeros_modelo[0]
                if re.search(r'x' + numero, descripcion):
                    usuario_pidio_max = 'max' in modelo_lower
                    descripcion_tiene_max = 'max' in descripcion
                    if usuario_pidio_max == descripcion_tiene_max:
                        modelo_encontrado = True
        elif 'samsung' in marca_lower:
            numeros_modelo = re.findall(r'\d+', modelo_lower)
            if numeros_modelo:
                numero = numeros_modelo[0]
                # Buscar número + variantes: A21, A21S, A217, A21A, etc.
                patron = r'[a-z]?' + numero + r'[a-z\d]*'
                if re.search(patron, descripcion):
                    palabras_modelo = [p for p in modelo_lower.split() if not p.isdigit()]
                    if not palabras_modelo:
                        modelo_encontrado = True
                    elif any(palabra in descripcion for palabra in palabras_modelo):
                        modelo_encontrado = True
        elif 'google pixel' in marca_lower or 'pixel' in marca_lower:
            # Buscar modelo Pixel por número + variantes opcionales (7, 7a, 7 pro, 8, 8a, etc.)
            numeros_modelo = re.findall(r'\d+', modelo_lower)
            if numeros_modelo:
                numero = numeros_modelo[0]
                # Buscar número + variantes opcionales (7, 7a, 7pro, etc.)
                patron = numero + r'[a-z\s]*'
                if re.search(patron, descripcion):
                    palabras_modelo = [p for p in modelo_lower.split() if not p.isdigit()]
                    if not palabras_modelo:
                        modelo_encontrado = True
                    elif any(palabra in descripcion for palabra in palabras_modelo):
                        modelo_encontrado = True
        elif 'hisense' in marca_lower:
            # Buscar modelo Hisense por nombre exacto O número + variantes
            modelo_upper = modelo_lower.upper()
            if modelo_upper in descripcion.upper():
                modelo_encontrado = True
            else:
                numeros = re.findall(r'\d+', modelo_lower)
                if numeros:
                    numero = numeros[0]
                    # Buscar número + variantes opcionales (e60, e60s, etc.)
                    patron = r'[a-z]?' + numero + r'[a-z\d]*'
                    if re.search(patron, descripcion):
                        modelo_encontrado = True
        else:
            if modelo_lower in descripcion:
                modelo_encontrado = True
            elif modelo_lower.replace(' ', '') in descripcion:
                modelo_encontrado = True
            elif modelo_lower.replace(' ', '/') in descripcion:
                modelo_encontrado = True

        if modelo_encontrado:
            resultados.append(producto)

    logger.info(f"[PRICING] Busqueda: {marca} {modelo} -> {len(resultados)} productos encontrados")
    return resultados

def obtener_categoria(calidad_str):
    if not calidad_str:
        return None
    calidad_limpia = str(calidad_str).strip().upper()

    if 'DIAGNOSTICO' in calidad_limpia:
        return 'AMOLED'

    for sufijo in [' S/M', ' C/M', ' SIN MARCO', ' CON MARCO']:
        calidad_limpia = calidad_limpia.replace(sufijo, '')

    if any(cat in calidad_limpia for cat in CATEGORIAS_GENERICO):
        return 'GENERICO'
    elif any(cat in calidad_limpia for cat in CATEGORIAS_ORIGINAL):
        return 'ORIGINAL'
    elif any(cat in calidad_limpia for cat in CATEGORIAS_AMOLED):
        return 'AMOLED'

    logger.debug(f"[PRICING] Calidad no reconocida: {calidad_str}")
    return None

def extraer_precio_usd(precio_str):
    if not precio_str:
        return None
    try:
        limpio = str(precio_str).replace('$', '').replace('USD', '').replace(',', '').strip()
        valor = float(limpio)
        return valor if valor > 0 else None
    except (ValueError, TypeError):
        logger.warning(f"[PRICING] No se pudo parsear precio: {precio_str}")
        return None

def agrupar_por_color(productos):
    agrupados = defaultdict(list)
    for producto in productos:
        color = str(producto.get('COLOR', '')).strip()
        if not color or color.upper() == 'NONE' or color.upper() == '':
            color = 'Sin especificar'
        agrupados[color].append(producto)
    return dict(agrupados)

async def obtener_cotizacion_display(marca, modelo):
    productos = buscar_productos_en_csv(marca, modelo)
    if not productos:
        logger.warning(f"[PRICING] No se encontraron productos para: {marca} {modelo}")
        return (
            f"Disculpa, no tengo en inventario displays para {marca} {modelo}.\n"
            "Podrías verificar el modelo exacto? O puedo conectarte con un tecnico "
            "para asesorarte sobre alternativas compatibles."
        )
    productos_por_categoria = defaultdict(list)
    for producto in productos:
        calidad = producto.get('CALIDAD', '')
        categoria = obtener_categoria(calidad)
        if not categoria:
            logger.debug(f"[PRICING] Calidad desconocida: {calidad}")
            continue
        productos_por_categoria[categoria].append(producto)
    respuesta = f"Para {marca} {modelo} tenemos estas opciones:\n\n"
    categorias_orden = ['GENERICO', 'ORIGINAL', 'AMOLED']
    for categoria in categorias_orden:
        if categoria not in productos_por_categoria:
            continue
        productos_cat = productos_por_categoria[categoria]
        precios_usd = []
        for prod in productos_cat:
            precio_usd = extraer_precio_usd(prod.get('PRECIO_1', ''))
            if precio_usd:
                precios_usd.append(precio_usd)
        if not precios_usd:
            logger.warning(f"[PRICING] Sin precios válidos para {categoria}")
            continue
        precio_usd_promedio = sum(precios_usd) / len(precios_usd)
        precio_mxn = int(precio_usd_promedio * MULTIPLICADOR_USD_A_MXN)
        if categoria == 'GENERICO':
            nombre_categoria = "Calidad Generica"
        elif categoria == 'ORIGINAL':
            nombre_categoria = "Calidad Original"
        elif categoria == 'AMOLED':
            nombre_categoria = "AMOLED"
        else:
            nombre_categoria = categoria
        respuesta += f"* {nombre_categoria}: ${precio_mxn:,} MXN"
        colores_unicos = agrupar_por_color(productos_cat)
        if len(colores_unicos) > 1:
            precios_por_color = {}
            for color, prods in colores_unicos.items():
                precios_color = []
                for prod in prods:
                    precio = extraer_precio_usd(prod.get('PRECIO_1', ''))
                    if precio:
                        precios_color.append(precio)
                if precios_color:
                    precios_por_color[color] = int((sum(precios_color) / len(precios_color)) * MULTIPLICADOR_USD_A_MXN)
            if len(set(precios_por_color.values())) > 1:
                respuesta += " -- Disponible en: "
                colores_lista = ", ".join(sorted(precios_por_color.keys()))
                respuesta += colores_lista
        respuesta += "\n"
    respuesta += (
        "\nCada display incluye: diagnostico, garantia 90 dias y cambio el mismo dia.\n"
        "Cual opcion te interesa? O si tu color no aparece, verifica con nuestro tecnico."
    )
    logger.info(
        f"[PRICING] Cotizacion generada para {marca} {modelo} -- "
        f"Categorias encontradas: {', '.join(productos_por_categoria.keys())}"
    )
    return respuesta

async def inicializar_cotizador():
    try:
        logger.info("[PRICING] Inicializando cotizador de precios...")
        if os.path.exists(RUTA_CSV_HUGO):
            datos = cargar_csv_hugo()
            logger.info(f"[PRICING] Sistema listo con {len(datos)} productos de Hugo Shop")
        else:
            logger.warning(f"[PRICING] CSV no encontrado en {RUTA_CSV_HUGO}")
            logger.warning("[PRICING] Asegurate de que 'hugo_shop.csv' está en la carpeta /knowledge")
    except Exception as e:
        logger.error(f"[PRICING] Error inicializando cotizador: {e}", exc_info=True)
