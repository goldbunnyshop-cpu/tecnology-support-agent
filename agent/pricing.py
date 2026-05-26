# agent/pricing.py — Motor de cotización con Hugo Shop (CSV + categorización por CALIDAD)
import os
import csv
import logging
from pathlib import Path
from collections import defaultdict
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()
logger = logging.getLogger("agentkit")

# ════════════════════════════════════════════════════════════════════
# CONSTANTES: Categorización por CALIDAD (columna C del CSV)
# ════════════════════════════════════════════════════════════════════

# CATEGORÍA 1: Genérico (económico, compatible)
CATEGORIAS_GENERICO = {'INCELL', 'COG', 'COF'}

# CATEGORÍA 2: Calidad Original (piezas originales estándar)
CATEGORIAS_ORIGINAL = {'ORIG', 'OLED', 'CARTAN'}

# CATEGORÍA 3: AMOLED (piezas premium originales)
CATEGORIAS_AMOLED = {'AMOLED'}

# Multiplicador universal para TODAS las categorías
MULTIPLICADOR_USD_A_MXN = 4

# Ruta del CSV de Hugo Shop
RUTA_CSV_HUGO = "knowledge/hugo_shop.csv"


# ════════════════════════════════════════════════════════════════════
# FUNCIÓN: Cargar CSV de Hugo Shop
# ════════════════════════════════════════════════════════════════════

def cargar_csv_hugo() -> list[dict]:
    """
    Lee el CSV de Hugo Shop y retorna lista de diccionarios.
    Estructura esperada:
    - Columna A: CÓDIGO
    - Columna B: DESCRIPCIÓN (búsqueda: marca + modelo)
    - Columna C: CALIDAD (INCELL, COG, COF, ORIG, OLED, CARTAN, AMOLED, etc.)
    - Columna D: COLOR
    - Columna E: PRECIO_1 (precio en USD - USAR ESTE)
    - Columna F: PRECIO_2
    """
    datos = []

    if not os.path.exists(RUTA_CSV_HUGO):
        logger.warning(f"[PRICING] CSV no encontrado en {RUTA_CSV_HUGO}")
        return datos

    try:
        with open(RUTA_CSV_HUGO, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)

            for idx, row in enumerate(reader):
                # Ignorar filas vacías o que no tengan datos
                if not row or not any(row.values()):
                    continue

                # Ignorar filas que parecen ser encabezados o metadata
                descripcion = str(row.get('DESCRIPCIÓN', '') or row.get('descripcion', '')).strip()
                if not descripcion or 'HUGO SHOP' in descripcion or 'COTIZACIONES' in descripcion:
                    continue

                datos.append(row)

        logger.info(f"[PRICING] Cargados {len(datos)} productos de Hugo Shop")
        return datos

    except Exception as e:
        logger.error(f"[PRICING] Error cargando CSV: {e}")
        return datos


# ════════════════════════════════════════════════════════════════════
# FUNCIÓN: Buscar marca+modelo en el CSV
# ════════════════════════════════════════════════════════════════════

def buscar_productos_en_csv(marca: str, modelo: str) -> list[dict]:
    """
    Busca todos los productos que coincidan con marca y modelo.
    La búsqueda se hace en la columna DESCRIPCIÓN.

    Ejemplo: buscar("Samsung", "S24") → busca "Samsung S24" en DESCRIPCIÓN
    """
    datos = cargar_csv_hugo()
    resultados = []

    marca_lower = marca.lower().strip()
    modelo_lower = modelo.lower().strip()

    for producto in datos:
        # La descripción está en la columna "DESCRIPCIÓN" (con mayúscula en el CSV)
        descripcion = str(producto.get('DESCRIPCIÓN', '') or producto.get('descripcion', '')).lower()

        # Búsqueda flexible: coincide si ambos términos están en la descripción
        if marca_lower in descripcion and modelo_lower in descripcion:
            resultados.append(producto)

    # Si no hay match exacto, buscar solo por marca (menos restrictivo)
    if not resultados:
        for producto in datos:
            descripcion = str(producto.get('DESCRIPCIÓN', '') or producto.get('descripcion', '')).lower()
            if marca_lower in descripcion:
                resultados.append(producto)

    logger.info(f"[PRICING] Búsqueda: {marca} {modelo} → {len(resultados)} productos encontrados")
    return resultados


# ════════════════════════════════════════════════════════════════════
# FUNCIÓN: Categorizar por CALIDAD
# ════════════════════════════════════════════════════════════════════

def obtener_categoria(calidad_str: str) -> str | None:
    """
    Determina la categoría basándose en el valor de CALIDAD (columna C).
    Retorna: 'GENERICO', 'ORIGINAL', 'AMOLED' o None si no coincide.

    El CSV puede tener valores como:
    - "ORIG S/M" (sin marco), "ORIG C/M" (con marco)
    - "OLED S/M"
    - "INCELL", "COG", "COF", etc.

    Nota: El " S/M" o " C/M" se ignora, solo importa la categoría base.
    """
    if not calidad_str:
        return None

    # Limpiar: quitar espacios extras y variantes (S/M, C/M, etc.)
    calidad_limpia = str(calidad_str).strip().upper()

    # Remover sufijos como " S/M", " C/M", etc.
    for sufijo in [' S/M', ' C/M', ' SIN MARCO', ' CON MARCO']:
        calidad_limpia = calidad_limpia.replace(sufijo, '')

    # Buscar coincidencia
    if any(cat in calidad_limpia for cat in CATEGORIAS_GENERICO):
        return 'GENERICO'
    elif any(cat in calidad_limpia for cat in CATEGORIAS_ORIGINAL):
        return 'ORIGINAL'
    elif any(cat in calidad_limpia for cat in CATEGORIAS_AMOLED):
        return 'AMOLED'

    logger.debug(f"[PRICING] Calidad no reconocida: {calidad_str}")
    return None


# ════════════════════════════════════════════════════════════════════
# FUNCIÓN: Extraer precio en USD y convertir a MXN
# ════════════════════════════════════════════════════════════════════

def extraer_precio_usd(precio_str: str) -> float | None:
    """
    Extrae valor numérico del precio (columna E - PRECIO_1).
    Maneja formatos como:
    - "100", "100.50"
    - "$100", "$100.50"
    - "$ 100.00"
    - "$ 1,200.00" (con coma para miles)
    """
    if not precio_str:
        return None

    try:
        # Limpiar: remover símbolos de moneda, espacios, comas, texto
        limpio = str(precio_str).replace('$', '').replace('USD', '').replace(',', '').strip()
        valor = float(limpio)
        return valor if valor > 0 else None
    except (ValueError, TypeError):
        logger.warning(f"[PRICING] No se pudo parsear precio: {precio_str}")
        return None


# ════════════════════════════════════════════════════════════════════
# FUNCIÓN: Agrupar productos por color y detectar variantes
# ════════════════════════════════════════════════════════════════════

def agrupar_por_color(productos: list[dict]) -> dict[str, list[dict]]:
    """
    Agrupa los productos por color (columna D).
    Retorna: {color: [lista de productos con ese color]}

    Ejemplo: Si hay Negro, Blanco, Azul → retorna 3 claves
    """
    agrupados = defaultdict(list)

    for producto in productos:
        # Puede venir como "COLOR" (mayúsculas) o "color" (minúsculas) en el CSV
        color = str(producto.get('COLOR', '') or producto.get('color', '')).strip()
        if not color or color.upper() == 'NONE' or color.upper() == '':
            color = 'Sin especificar'
        agrupados[color].append(producto)

    return dict(agrupados)


# ════════════════════════════════════════════════════════════════════
# FUNCIÓN: Construir respuesta de cotización
# ════════════════════════════════════════════════════════════════════

async def obtener_cotizacion_display(marca: str, modelo: str) -> str:
    """
    Obtiene cotización de displays basándose en Hugo Shop CSV.

    LÓGICA:
    1. Busca marca+modelo en CSV
    2. Agrupa por CALIDAD (columna C) → 3 categorías
    3. Agrupa por COLOR (columna D) → solo mostrar si hay variantes de precio
    4. Multiplica PRECIO_1 × 4 para todas las categorías
    5. Retorna respuesta formateada con opciones disponibles
    """

    # Paso 1: Buscar productos
    productos = buscar_productos_en_csv(marca, modelo)

    if not productos:
        logger.warning(f"[PRICING] No se encontraron productos para: {marca} {modelo}")
        return (
            f"Disculpa, no tengo en inventario displays para {marca} {modelo}.\n"
            "¿Podrías verificar el modelo exacto? O puedo conectarte con un técnico "
            "para asesorarte sobre alternativas compatibles."
        )

    # Paso 2: Agrupar por CALIDAD (categoría) y COLOR
    productos_por_categoria = defaultdict(list)

    for producto in productos:
        categoria = obtener_categoria(producto.get('CALIDAD', ''))
        if not categoria:
            logger.debug(f"[PRICING] Calidad desconocida: {producto.get('CALIDAD')}")
            continue
        productos_por_categoria[categoria].append(producto)

    # Paso 3: Construir respuesta
    respuesta = f"Para {marca} {modelo} tenemos estas opciones:\n\n"

    # Orden de presentación: Genérico → Original → AMOLED
    categorias_orden = ['GENERICO', 'ORIGINAL', 'AMOLED']

    for categoria in categorias_orden:
        if categoria not in productos_por_categoria:
            continue

        productos_cat = productos_por_categoria[categoria]

        # Calcular precio promedio para esta categoría (pueden haber variantes de color)
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

        # Nombrar categoría según tipo
        if categoria == 'GENERICO':
            nombre_categoria = "Display Genérico (Incell/COG)"
        elif categoria == 'ORIGINAL':
            nombre_categoria = "Display Calidad original"
        elif categoria == 'AMOLED':
            nombre_categoria = "Display AMOLED original"
        else:
            nombre_categoria = f"Display {categoria}"

        respuesta += f"• {nombre_categoria}: ${precio_mxn:,} MXN"

        # Paso 4: Mostrar variantes de COLOR solo si hay diferencia de precio
        colores_unicos = agrupar_por_color(productos_cat)

        if len(colores_unicos) > 1:
            # Detectar si hay variación de precio entre colores
            precios_por_color = {}
            for color, prods in colores_unicos.items():
                precios_color = []
                for prod in prods:
                    precio = extraer_precio_usd(prod.get('PRECIO_1', ''))
                    if precio:
                        precios_color.append(precio)
                if precios_color:
                    precios_por_color[color] = int((sum(precios_color) / len(precios_color)) * MULTIPLICADOR_USD_A_MXN)

            # Si hay variación de precio, listar colores disponibles
            if len(set(precios_por_color.values())) > 1:
                respuesta += " — Disponible en: "
                colores_lista = ", ".join(sorted(precios_por_color.keys()))
                respuesta += colores_lista

        respuesta += "\n"

    respuesta += (
        "\nCada display incluye: diagnóstico, garantía 90 días y cambio el mismo día.\n"
        "¿Cuál opción te interesa? O si tu color no aparece, verifica con nuestro técnico."
    )

    logger.info(
        f"[PRICING] Cotización generada para {marca} {modelo} — "
        f"Categorías encontradas: {', '.join(productos_por_categoria.keys())}"
    )

    return respuesta


async def inicializar_cotizador():
    """
    Inicializa el sistema de cotización.
    Verifica que el CSV está disponible.
    """
    try:
        logger.info("[PRICING] Inicializando cotizador de precios...")

        if os.path.exists(RUTA_CSV_HUGO):
            datos = cargar_csv_hugo()
            logger.info(f"[PRICING] ✅ Sistema listo con {len(datos)} productos de Hugo Shop")
        else:
            logger.warning(f"[PRICING] ⚠️  CSV no encontrado en {RUTA_CSV_HUGO}")
            logger.warning("[PRICING] Asegúrate de que 'hugo_shop.csv' está en la carpeta /knowledge")

    except Exception as e:
        logger.error(f"[PRICING] Error inicializando cotizador: {e}", exc_info=True)
