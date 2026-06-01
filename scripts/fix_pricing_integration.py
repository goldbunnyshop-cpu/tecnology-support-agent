#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script de integración: Conecta pricing.py con brain.py
Permite que el agente busque precios cuando el cliente pregunta sobre displays
Ejecución: python fix_pricing_integration.py
"""

import os
import sys

def modificar_pricing():
    """Agrega función de cotización en pricing.py"""
    pricing_path = "agent/pricing.py"

    if not os.path.exists(pricing_path):
        print("❌ Error: agent/pricing.py no encontrado")
        return False

    # Leer archivo actual
    with open(pricing_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Función a agregar (antes del final del archivo)
    nueva_funcion = '''

# ============================================================================
# FUNCIÓN PÚBLICA: OBTENER COTIZACIÓN DISPLAY
# ============================================================================

async def obtener_cotizacion_display(marca: str, modelo: str) -> str:
    """
    Obtiene cotización de display para un modelo específico.
    Busca en Hugo Shop cache y retorna texto formateado para el cliente.

    Args:
        marca: Marca del dispositivo (ej: "iPhone", "Samsung")
        modelo: Modelo específico (ej: "16", "S24")

    Returns:
        String con opciones de precio formateado o mensaje de fallback
    """
    logger.info(f"[PRICING] Buscando cotización: {marca} {modelo}")

    try:
        # Cargar cache de Hugo Shop
        cache_manager = CacheManager()
        productos = cache_manager.cargar_hugo_shop()

        if not productos:
            logger.warning("[PRICING] Cache Hugo Shop vacío")
            return "Para ese modelo te doy el precio exacto en el diagnóstico (2 horas). Tenemos opciones genérica y original según tu presupuesto, ambas con garantía 90 días."

        # Buscar productos que coincidan
        consulta = f"{marca} {modelo}".lower()
        coincidencias = [p for p in productos if consulta in p.get("DESCRIPCIÓN", "").lower()]

        if not coincidencias:
            logger.warning(f"[PRICING] Sin coincidencias para: {consulta}")
            return "Para ese modelo te doy el precio exacto en el diagnóstico (2 horas). Tenemos opciones genérica y original según tu presupuesto."

        # Procesar cotizaciones (máximo 2 opciones: genérico y original)
        cotizaciones = []
        for producto in coincidencias[:2]:
            try:
                precio_base = float(producto.get("PRECIO_1", 0))
                if precio_base <= 0:
                    continue

                descripcion = producto.get("DESCRIPCIÓN", "")
                calidad = DetectorDispositivo.detectar_calidad(descripcion)
                multiplicador = MotorMultiplicadores.obtener_multiplicador(
                    FuentePrecio.HUGO_SHOP,
                    calidad
                )
                precio_final = int(precio_base * multiplicador)

                # Determinar etiqueta (Genérico o Original)
                if "original" in descripcion.lower() or calidad in [CalidadDispositivo.OLED, CalidadDispositivo.AMOLED]:
                    etiqueta = "Original"
                else:
                    etiqueta = "Genérico (Incell)"

                cotizaciones.append({
                    "etiqueta": etiqueta,
                    "precio": precio_final,
                    "calidad": calidad.value
                })
            except (ValueError, KeyError):
                continue

        if not cotizaciones:
            return "Para ese modelo te doy el precio exacto en el diagnóstico (2 horas)."

        # Formatear respuesta para el cliente
        respuesta = f"Para {marca} {modelo} tenemos:\\n"
        for cot in cotizaciones[:2]:
            respuesta += f"• Display {cot['etiqueta']}: ${cot['precio']:,} MXN\\n"

        respuesta += "\\nAmbos incluyen diagnóstico, garantía 90 días y cambio el mismo día. ¿Cuál te interesa?"

        logger.info(f"[PRICING] ✅ Cotización generada para {marca} {modelo}")
        return respuesta

    except Exception as e:
        logger.error(f"[PRICING] Error obteniendo cotización: {e}")
        return "Para ese modelo te doy el precio exacto en el diagnóstico (2 horas). Tenemos opciones genérica y original según tu presupuesto."
'''

    # Agregar función al final
    if "async def obtener_cotizacion_display" not in content:
        content += nueva_funcion
        with open(pricing_path, 'w', encoding='utf-8') as f:
            f.write(content)
        print("✅ Función obtener_cotizacion_display() agregada a pricing.py")
        return True
    else:
        print("⚠️  Función ya existe en pricing.py")
        return True


def modificar_brain():
    """Integra búsqueda de precios en brain.py"""
    brain_path = "agent/brain.py"

    if not os.path.exists(brain_path):
        print("❌ Error: agent/brain.py no encontrado")
        return False

    with open(brain_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # 1. Agregar import de pricing
    if "from agent.pricing import" not in content:
        content = content.replace(
            "from dotenv import load_dotenv",
            "from dotenv import load_dotenv\nfrom agent.pricing import obtener_cotizacion_display\nimport re"
        )
        print("✅ Imports agregados a brain.py")

    # 2. Agregar función de detección de preguntas sobre displays
    nueva_funcion_deteccion = '''

async def detectar_y_obtener_precios(mensaje: str) -> str:
    """
    Detecta si el mensaje pregunta sobre precios de displays.
    Si lo hace, obtiene la cotización y retorna contexto inyectable.
    """
    # Patrones que indican pregunta sobre displays
    patrones_display = [
        r'\\bcuánto.*display\\b',
        r'\\bcuánto.*pantalla\\b',
        r'\\bcuánto.*screen\\b',
        r'\\bprecio.*display\\b',
        r'\\bprecio.*pantalla\\b',
        r'\\bcosto.*display\\b',
        r'\\bcambio de pantalla\\b',
        r'\\bcambio de display\\b',
    ]

    mensaje_lower = mensaje.lower()

    # Verificar si pregunta sobre precios
    es_pregunta_precio = any(re.search(p, mensaje_lower) for p in patrones_display)

    if not es_pregunta_precio:
        return ""

    # Extraer marca y modelo (ej: "iPhone 16", "Samsung S24")
    patron_modelo = r'(iPhone|Samsung|Google Pixel|OnePlus|Xiaomi|Motorola|Huawei|Nokia|LG)\\s+(\\w+\\s*\\w*)'
    match = re.search(patron_modelo, mensaje, re.IGNORECASE)

    if not match:
        return ""

    marca = match.group(1)
    modelo = match.group(2).strip()

    logger.info(f"[BRAIN] Pregunta sobre precios detectada: {marca} {modelo}")

    # Obtener cotización
    cotizacion = await obtener_cotizacion_display(marca, modelo)

    if cotizacion:
        contexto = f"PRECIO ENCONTRADO PARA {marca.upper()} {modelo.upper()}:\\n{cotizacion}"
        return contexto

    return ""
'''

    # Agregar función si no existe
    if "async def detectar_y_obtener_precios" not in content:
        # Insertar antes de generar_respuesta
        idx = content.find("async def generar_respuesta")
        if idx > 0:
            content = content[:idx] + nueva_funcion_deteccion + "\n\n" + content[idx:]
        print("✅ Función detectar_y_obtener_precios() agregada a brain.py")

    # 3. Modificar generar_respuesta para usar detección de precios
    old_gen = '''async def generar_respuesta(
    mensaje: str,
    historial: list[dict],
    asesor: str = "Valentina",
    contexto_cliente: str = "",
) -> str:
    if not mensaje or len(mensaje.strip()) < 2:
        return obtener_mensaje_fallback()

    system_prompt = construir_system_prompt(asesor)
    if contexto_cliente:
        system_prompt = f"{contexto_cliente}\\n\\n{system_prompt}"'''

    new_gen = '''async def generar_respuesta(
    mensaje: str,
    historial: list[dict],
    asesor: str = "Valentina",
    contexto_cliente: str = "",
) -> str:
    if not mensaje or len(mensaje.strip()) < 2:
        return obtener_mensaje_fallback()

    # Detectar y obtener precios si pregunta sobre displays
    if not contexto_cliente:
        contexto_precios = await detectar_y_obtener_precios(mensaje)
        if contexto_precios:
            contexto_cliente = contexto_precios

    system_prompt = construir_system_prompt(asesor)
    if contexto_cliente:
        system_prompt = f"{contexto_cliente}\\n\\n{system_prompt}"'''

    if old_gen in content:
        content = content.replace(old_gen, new_gen)
        print("✅ generar_respuesta() modificada para usar precios")

    with open(brain_path, 'w', encoding='utf-8') as f:
        f.write(content)

    return True


def main():
    """Ejecuta las modificaciones"""
    print("=" * 60)
    print("🔧 Integración de Precios — pricing.py + brain.py")
    print("=" * 60)
    print()

    # Cambiar a directorio del proyecto si es necesario
    if os.path.exists("config/prompts.yaml"):
        print("✅ Directorio correcto detectado\n")
    else:
        print("❌ No estás en el directorio del proyecto")
        print("   Ejecuta este script desde: C:\\Users\\Elitebook\\whatsapp-agentkit\\")
        return False

    # Ejecutar modificaciones
    print("📝 Modificando agent/pricing.py...")
    if not modificar_pricing():
        return False
    print()

    print("📝 Modificando agent/brain.py...")
    if not modificar_brain():
        return False
    print()

    print("=" * 60)
    print("✅ ¡Integración completada!")
    print("=" * 60)
    print()
    print("Lo que se hizo:")
    print("1. ✅ Agregó función obtener_cotizacion_display() en pricing.py")
    print("2. ✅ Agregó función detectar_y_obtener_precios() en brain.py")
    print("3. ✅ Modificó generar_respuesta() para usar detección de precios")
    print()
    print("Ahora cuando un cliente pregunta por precios de displays:")
    print("• El agente detectará la pregunta")
    print("• Buscará el precio en Hugo Shop cache")
    print("• Mostrará dos opciones (genérico + original)")
    print()
    print("📚 Próximo paso:")
    print("1. git add agent/pricing.py agent/brain.py")
    print("2. git commit -m 'feat: integración de precios en consultas de display'")
    print("3. git push origin main")
    print("4. Railway redesplegará automáticamente")
    print()
    return True


if __name__ == "__main__":
    try:
        success = main()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)
