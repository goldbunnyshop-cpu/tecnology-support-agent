# agent/pricing.py — Motor de cotización con Hugo Shop
import os
import logging
from anthropic import AsyncAnthropic
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger("agentkit")
client = AsyncAnthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))


# ════════════════════════════════════════════════════════════════════
# MAPEO DE PANTALLAS: Determina qué tipo de pantalla tiene cada modelo
# ════════════════════════════════════════════════════════════════════

def determinar_tipo_pantalla(marca: str, modelo: str) -> str:
    """
    Determina el tipo de pantalla REAL del dispositivo.
    Retorna: 'AMOLED', 'OLED', 'LCD', 'IPS' o 'DESCONOCIDO'

    LÓGICA:
    - AMOLED: Samsung Galaxy S/Z series, flagship Motorola
    - OLED: iPhone Pro, Google Pixel Pro, OnePlus Pro
    - LCD/IPS: Budget/Mid-range, A-series Samsung, Edge Lite, etc.
    """
    marca_lower = marca.lower()
    modelo_lower = modelo.lower()

    # ═══════════════════════════════════════════════════════════════
    # SAMSUNG
    # ═══════════════════════════════════════════════════════════════
    if 'samsung' in marca_lower:
        # Galaxy S/Z Series: AMOLED (premium)
        if any(x in modelo_lower for x in ['s21', 's22', 's23', 's24', 's25', 'z fold', 'z flip']):
            return 'AMOLED'
        # Galaxy A/M/F Series: LCD (presupuesto)
        if any(x in modelo_lower for x in ['galaxy a', 'a12', 'a21', 'a22', 'a32', 'a52', 'a55', 'galaxy m', 'fe']):
            return 'LCD'
        # Por defecto Samsung premium
        return 'AMOLED'

    # ═══════════════════════════════════════════════════════════════
    # IPHONE
    # ═══════════════════════════════════════════════════════════════
    if 'iphone' in marca_lower:
        # iPhone Pro: OLED
        if 'pro' in modelo_lower:
            return 'OLED'
        # iPhone 14+: OLED (incluso base)
        if any(x in modelo_lower for x in ['14', '15', '16']):
            return 'OLED'
        # iPhone SE, 11, 12, 13: LCD (base)
        if any(x in modelo_lower for x in ['se', '11', '12', '13']):
            return 'LCD'
        # Default para otros
        return 'OLED'

    # ═══════════════════════════════════════════════════════════════
    # GOOGLE PIXEL
    # ═══════════════════════════════════════════════════════════════
    if 'pixel' in marca_lower:
        # Pixel Pro/Fold: OLED
        if any(x in modelo_lower for x in ['pro', 'fold', 'a']):
            return 'OLED'
        return 'OLED'

    # ═══════════════════════════════════════════════════════════════
    # MOTOROLA
    # ═══════════════════════════════════════════════════════════════
    if 'motorola' in marca_lower or 'moto' in marca_lower:
        # Edge Premium: AMOLED
        if any(x in modelo_lower for x in ['edge 50', 'edge 40', 'edge 40 pro', 'edge 40 ultra']):
            return 'AMOLED'
        # Edge Mid/Lite: LCD
        if any(x in modelo_lower for x in ['edge 20', 'edge lite', 'edge 30', 'g']):
            return 'LCD'
        # Moto G: LCD
        return 'LCD'

    # ═══════════════════════════════════════════════════════════════
    # ONEPLUS
    # ═══════════════════════════════════════════════════════════════
    if 'oneplus' in marca_lower or 'one plus' in modelo_lower:
        # OnePlus Pro/Ultra: AMOLED
        if any(x in modelo_lower for x in ['pro', 'ultra', 'find']):
            return 'AMOLED'
        # OnePlus regular: AMOLED (mayoría)
        return 'AMOLED'

    # ═══════════════════════════════════════════════════════════════
    # XIAOMI
    # ═════════════�