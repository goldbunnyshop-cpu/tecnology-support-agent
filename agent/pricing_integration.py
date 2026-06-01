# agent/pricing_integration.py — Integración Hugo Shop + MercadoLibre
# Creado: 1 de junio 2026
# Purpose: Si Hugo Shop no tiene el producto, buscar en MercadoLibre como fallback

import logging
from typing import Optional, Dict
from agent.pricing import obtener_cotizacion_display
# from agent.pricing_mercadolibre import cotizar_refaccion_mercadolibre  # DESACTIVADO: causaba crash Railway

logger = logging.getLogger("agentkit")


async def obtener_cotizacion_con_fallback(marca: str, modelo: str, refaccion: str = "display") -> str:
    """
    Intenta obtener cotización siguiendo este flujo:

    1. Busca en Hugo Shop
    2. Si NO encuentra (devuelve mensaje "no disponible"), intenta MercadoLibre
    3. Combina ambos resultados de forma elegante

    Args:
        marca: Marca del dispositivo (Samsung, iPhone, etc.)
        modelo: Modelo del dispositivo (A21, 14, G85, etc.)
        refaccion: Tipo de refacción (default: "display")

    Returns:
        Respuesta formateada con precios de Hugo Shop y/o MercadoLibre
    """

    # Paso 1: Intentar Hugo Shop
    logger.info(f"[PRICING] Buscando {refaccion} {marca} {modelo} en Hugo Shop...")
    respuesta_hugo = await obtener_cotizacion_display(marca, modelo)

    # Detectar si Hugo Shop encontró algo o devolvió "no disponible"
    es_no_disponible = _es_mensaje_no_disponible(respuesta_hugo)

    if not es_no_disponible:
        # Hugo Shop tiene el producto → retornar
        logger.info(f"[PRICING] Encontrado en Hugo Shop: {marca} {modelo}")
        return respuesta_hugo

    # Paso 2: Hugo Shop no tiene → intentar MercadoLibre
    # DESACTIVADO TEMPORALMENTE POR CRASH EN RAILWAY (bs4 y web scraping inestable)
    # TODO: Reactivar después de implementar API estable (ej: Amazon, API de precios)
    logger.warning(f"[PRICING] MercadoLibre desactivado temporalmente. Devolviendo respuesta de Hugo Shop.")
    return respuesta_hugo

    # --- CÓDIGO ANTIGUO (comentado) ---
    # logger.info(f"[PRICING] No en Hugo Shop. Buscando en MercadoLibre: {refaccion} {marca} {modelo}...")
    # resultado_ml = await cotizar_refaccion_mercadolibre(refaccion, modelo)
    #
    # if not resultado_ml:
    #     logger.warning(f"[PRICING] No encontrado en Hugo Shop ni MercadoLibre: {marca} {modelo}")
    #     return respuesta_hugo
    #
    # respuesta_combinada = _formatear_respuesta_combinada(
    #     marca=marca,
    #     modelo=modelo,
    #     resultado_hugo=None,
    #     resultado_ml=resultado_ml
    # )
    #
    # logger.info(f"[PRICING] Cotización MercadoLibre encontrada: {marca} {modelo}")
    # return respuesta_combinada


def _es_mensaje_no_disponible(respuesta: str) -> bool:
    """Detecta si la respuesta indica que Hugo Shop no tiene el producto."""
    if not respuesta:
        return True

    indicadores = [
        "no encontr",
        "sin producto",
        "sin coincidencia",
        "no disponible",
        "modelo diferente",
        "inventario",
        "acude al modulo",
    ]

    respuesta_lower = respuesta.lower()
    return any(ind in respuesta_lower for ind in indicadores)


def _formatear_respuesta_combinada(
    marca: str,
    modelo: str,
    resultado_hugo: Optional[Dict] = None,
    resultado_ml: Optional[Dict] = None
) -> str:
    """Formatea una respuesta combinada de Hugo Shop + MercadoLibre."""

    lineas = [f"💻 **{marca.upper()} {modelo}**\n"]

    if resultado_hugo:
        lineas.append("✅ **Hugo Shop** (Tu Tienda Local)")
        lineas.append(f"  Genérico: ${resultado_hugo['precio_generico']:,.0f} MXN")
        if resultado_hugo.get('precio_original'):
            lineas.append(f"  Original: ${resultado_hugo['precio_original']:,.0f} MXN")
        lineas.append("")

    if resultado_ml:
        lineas.append("🛒 **MercadoLibre** (Alternativas Nacionales)")
        if resultado_ml['precio_generico']:
            lineas.append(f"  Genérico: ${resultado_ml['precio_generico']:,.0f} MXN")
        if resultado_ml['precio_original']:
            lineas.append(f"  Original: ${resultado_ml['precio_original']:,.0f} MXN")
        lineas.append("")

    # Si solo hay MercadoLibre
    if not resultado_hugo and resultado_ml:
        lineas.append("📌 Este producto no está en nuestro inventario, pero encontramos ")
        lineas.append("opciones en MercadoLibre a nivel nacional.")
        lineas.append("")
        lineas.append("¿Te interesa alguna de estas opciones o prefieres que agendemos ")
        lineas.append("una cita para revisar alternativas compatibles?")

    return "\n".join(lineas).strip()


async def obtener_cotizacion_display_mejorada(marca: str, modelo: str) -> str:
    """
    Versión mejorada de obtener_cotizacion_display() que integra MercadoLibre.

    NOTA: Esta función REEMPLAZA la llamada en brain.py:

    EN brain.py, cambiar:
        respuesta_pricing = await _intentar_respuesta_pricing_contextual(mensaje, historial)

    POR:
        respuesta_pricing = await _intentar_respuesta_pricing_contextual_mejorada(mensaje, historial)

    Y cambiar la función _intentar_respuesta_pricing_contextual para que use:
        from agent.pricing_integration import obtener_cotizacion_display_mejorada

    Y dentro de esa función, cambiar:
        r = await obtener_cotizacion_display(marca, modelo)

    POR:
        r = await obtener_cotizacion_display_mejorada(marca, modelo)
    """
    return await obtener_cotizacion_con_fallback(marca, modelo, "display")
