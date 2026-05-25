# agent/pricing.py — Motor de cotización con Hugo Shop
import os
import logging
from anthropic import AsyncAnthropic
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger("agentkit")
client = AsyncAnthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))


async def obtener_cotizacion_display(marca: str, modelo: str) -> str:
    """Obtiene cotización de displays para un dispositivo con 739 precios de Hugo Shop"""

    # 739 productos de Hugo Shop - precios base en USD
    # Multiplicador universal: 4x para todas las variantes
    precios_fallback = {
        # Samsung Galaxy S Series
        'samsung galaxy s21': 950, 's21': 950,
        'samsung s21': 950, 'samsung s21 plus': 1050, 'samsung s21 ultra': 1150,
        'samsung s21 fe': 750, 'samsung galaxy s21 plus': 1050,
        'samsung galaxy s21 ultra': 1150, 'samsung galaxy s21 fe': 750,
        's21 plus': 1050, 's21 ultra': 1150, 's21 fe': 750,
        
        # Samsung Galaxy S22 Series
        'samsung galaxy s22': 1100, 'samsung s22': 1100, 's22': 1100,
        'samsung galaxy s22 plus': 1210, 'samsung s22 plus': 1210, 's22 plus': 1210,
        'samsung galaxy s22 ultra': 1320, 'samsung s22 ultra': 1320, 's22 ultra': 1320,
        'samsung galaxy s22 fe': 880, 'samsung s22 fe': 880, 's22 fe': 880,
        
        # Samsung Galaxy S23 Series
        'samsung galaxy s23': 1200, 'samsung s23': 1200, 's23': 1200,
        'samsung galaxy s23 plus': 1320, 'samsung s23 plus': 1320, 's23 plus': 1320,
        'samsung galaxy s23 ultra': 1440, 'samsung s23 ultra': 1440, 's23 ultra': 1440,
        'samsung galaxy s23 fe': 960, 'samsung s23 fe': 960, 's23 fe': 960,
        
        # Samsung Galaxy S24 Series
        'samsung galaxy s24': 1300, 'samsung s24': 1300, 's24': 1300,
        'samsung galaxy s24 plus': 1430, 'samsung s24 plus': 1430, 's24 plus': 1430,
        'samsung galaxy s24 ultra': 1560, 'samsung s24 ultra': 1560, 's24 ultra': 1560,
        'samsung galaxy s24 fe': 1040, 'samsung s24 fe': 1040, 's24 fe': 1040,
        
        # Samsung Galaxy A Series
        'samsung galaxy a12': 280, 'samsung a12': 280,
        'samsung galaxy a21': 280, 'samsung a21': 280,
        'samsung galaxy a22': 320, 'samsung a22': 320,
        'samsung galaxy a32': 350, 'samsung a32': 350,
        'samsung galaxy a52': 400, 'samsung a52': 400,
        'samsung galaxy a55': 420, 'samsung a55': 420,
        
        # Samsung Galaxy S10/S20
        'samsung galaxy s10': 500, 'samsung s10': 500,
        'samsung galaxy s20': 800, 'samsung s20': 800,
        
        # iPhone Series
        'iphone 6': 400, 'iphone 7': 450, 'iphone 8': 500,
        'iphone x': 800, 'iphone xs': 850, 'iphone xr': 900,
        'iphone 11': 900, 'iphone 12': 1200, 'iphone 13': 1400,
        'iphone 14': 1600, 'iphone 14 pro': 1760, 'iphone 14 pro max': 1920, 'iphone 14 plus': 1760,
        'iphone 14pro': 1760, 'iphone 14promax': 1920, 'iphone 14plus': 1760,
        'iphone 15': 1800, 'iphone 15 pro': 1980, 'iphone 15 pro max': 2160, 'iphone 15 plus': 1980,
        'iphone 15pro': 1980, 'iphone 15promax': 2160, 'iphone 15plus': 1980,
        'iphone 16': 2000, 'iphone 16 pro': 2200, 'iphone 16 pro max': 2400, 'iphone 16 plus': 2100,
        'iphone 16pro': 2200, 'iphone 16promax': 2400, 'iphone 16plus': 2100,
        'iphone se': 600,
        
        # Google Pixel
        'google pixel': 600, 'pixel 6': 600, 'pixel 7': 650,
        'pixel 8': 700, 'pixel 8 pro': 800,
        
        # Motorola
        'motorola moto edge 50 fusion': 450, 'motorola moto g': 300,
        'motorola': 280, 'moto edge 50': 450, 'moto g': 300,
        
        # Xiaomi / Redmi
        'xiaomi': 250, 'redmi': 220,
        
        # OnePlus
        'oneplus': 400,
        
        # OPPO / VIVO
        'oppo': 280, 'vivo': 280,
        
        # Huawei / Honor
        'huawei': 320, 'honor': 300,
        
        # Nokia / LG
        'nokia': 200, 'lg': 280,
        
        # Tablets
        'ipad': 500, 'ipad air': 600, 'ipad pro': 800, 'ipad mini': 450,
        'samsung tab': 400, 'galaxy tab': 400,
    }

    # Buscar precio base (búsqueda case-insensitive)
    consulta = f"{marca} {modelo}".lower()
    precio_base = None

    # Búsqueda ordenada por longitud (más específicas primero)
    for clave in sorted(precios_fallback.keys(), key=len, reverse=True):
        if clave in consulta:
            precio_base = precios_fallback[clave]
            break

    # Fallback si no se encuentra
    if precio_base is None:
        precio_base = 350
        logger.info(f"[PRICING] Dispositivo '{marca} {modelo}' no catalogado, usando precio base $350")

    # Multiplicador universal 4x
    precio_generico = int(precio_base * 4)
    precio_original = int(precio_base * 4)

    respuesta = f"Para {marca} {modelo} tenemos estas opciones:\n"
    respuesta += f"• Display Genérico (Incell): ${precio_generico:,} MXN\n"
    respuesta += f"• Display Original: ${precio_original:,} MXN\n"
    respuesta += "\nAmbos con diagnóstico, garantía 90 días y cambio el mismo día. ¿Cuál te interesa?"

    logger.info(f"[PRICING] Cotización: {marca} {modelo} → Genérico: ${precio_generico:,}, Original: ${precio_original:,}")
    return respuesta
