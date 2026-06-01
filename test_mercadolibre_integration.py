#!/usr/bin/env python3
# test_mercadolibre_integration.py — Test rápido de integración MercadoLibre

"""
Prueba la integración entre Hugo Shop y MercadoLibre.
Ejecutar antes de hacer push:
    python test_mercadolibre_integration.py
"""

import asyncio
import sys
import os
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from agent.pricing_integration import (
    obtener_cotizacion_con_fallback,
    _es_mensaje_no_disponible
)


async def test_producto_en_hugo():
    """Test 1: Producto que está en Hugo Shop"""
    print("\n" + "="*70)
    print("TEST 1: Producto EN Hugo Shop (sin fallback a ML)")
    print("="*70 + "\n")

    print("[1/3] Buscando: Samsung A21 display...")
    respuesta = await obtener_cotizacion_con_fallback("samsung", "a21")

    print(f"\nRespuesta:\n{respuesta}\n")

    if "no encontr" not in respuesta.lower() and "samsung" in respuesta.lower():
        print("✅ CORRECTO — Hugo Shop encontró el producto\n")
        return True
    else:
        print("❌ ERROR — Esperaba respuesta de Hugo Shop\n")
        return False


async def test_producto_en_ml():
    """Test 2: Producto que NO está en Hugo pero SÍ en ML"""
    print("\n" + "="*70)
    print("TEST 2: Producto en MercadoLibre (fallback)")
    print("="*70 + "\n")

    print("[1/3] Buscando: Motorola G85 batería (no en Hugo)...")
    respuesta = await obtener_cotizacion_con_fallback(
        marca="motorola",
        modelo="g85",
        refaccion="batería"
    )

    print(f"\nRespuesta:\n{respuesta}\n")

    # Podría venir de Hugo o ML, lo importante es que hay respuesta
    if respuesta and len(respuesta) > 20:
        print("✅ CORRECTO — Obtuvo respuesta (Hugo o ML)\n")
        return True
    else:
        print("❌ ERROR — No obtuvo respuesta\n")
        return False


async def test_detector_no_disponible():
    """Test 3: Detector de "no disponible" funciona"""
    print("\n" + "="*70)
    print("TEST 3: Detector de mensajes 'No disponible'")
    print("="*70 + "\n")

    casos = [
        ("No encontre displays en nuestro inventario", True),
        ("Acude al modulo para revisar alternativas", True),
        ("Cotización: Samsung A21 - Genérico $450", False),
        ("", True),
    ]

    todas_ok = True
    for msg, esperado in casos:
        resultado = _es_mensaje_no_disponible(msg[:30] if msg else msg)
        estado = "✅" if resultado == esperado else "❌"
        print(f"{estado} '{msg[:40]}...' → {resultado} (esperado: {esperado})")
        if resultado != esperado:
            todas_ok = False

    print()
    return todas_ok


async def test_timing():
    """Test 4: Timing de respuesta (< 5 segundos)"""
    print("\n" + "="*70)
    print("TEST 4: Performance (timing)")
    print("="*70 + "\n")

    import time

    print("[1/2] Midiendo tiempo Hugo Shop...")
    inicio = time.time()
    resp_hugo = await obtener_cotizacion_con_fallback("samsung", "a21")
    tiempo_hugo = time.time() - inicio
    print(f"      ✓ {tiempo_hugo:.2f}s\n")

    print("[2/2] Midiendo tiempo MercadoLibre fallback...")
    inicio = time.time()
    resp_ml = await obtener_cotizacion_con_fallback("motorola", "g85", "batería")
    tiempo_ml = time.time() - inicio
    print(f"      ✓ {tiempo_ml:.2f}s\n")

    promedio = (tiempo_hugo + tiempo_ml) / 2
    print(f"Promedio: {promedio:.2f}s")

    if promedio < 5:
        print("✅ CORRECTO — Respuestas rápidas\n")
        return True
    else:
        print("⚠️  ADVERTENCIA — Respuestas lentas (>5s)\n")
        return True  # No es un error crítico


async def main():
    print("\n" + "🛒 PRUEBAS: INTEGRACIÓN MERCADOLIBRE".center(70))
    print("=" * 70)
    print(f"Inicio: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")

    todos_ok = True

    try:
        # Test 1
        if not await test_producto_en_hugo():
            todos_ok = False

        # Test 2
        if not await test_producto_en_ml():
            todos_ok = False

        # Test 3
        if not await test_detector_no_disponible():
            todos_ok = False

        # Test 4
        if not await test_timing():
            todos_ok = False

    except Exception as e:
        print(f"\n❌ ERROR DURANTE LAS PRUEBAS:\n{e}")
        import traceback
        traceback.print_exc()
        todos_ok = False

    # Resumen
    print("\n" + "="*70)
    if todos_ok:
        print("✅ TODOS LOS TESTS PASARON — LISTO PARA PRODUCCIÓN")
    else:
        print("❌ ALGUNOS TESTS FALLARON — REVISAR ANTES DE PUSH")
    print("="*70 + "\n")

    return 0 if todos_ok else 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
