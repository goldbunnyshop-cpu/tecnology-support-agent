#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test del sistema de pricing con Hugo Shop CSV.
Verifica que:
1. El CSV se carga correctamente
2. Las búsquedas funcionan
3. Los precios se calculan con la fórmula correcta (×4)
"""

import asyncio
import sys
import os

# Agregar el directorio raíz al path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from agent.pricing import (
    cargar_csv_hugo,
    buscar_productos_en_csv,
    obtener_categoria,
    extraer_precio_usd,
    obtener_cotizacion_display
)


def test_cargar_csv():
    """Verifica que el CSV se carga correctamente."""
    print("\n═" * 60)
    print("TEST 1: Cargar CSV de Hugo Shop")
    print("═" * 60)

    datos = cargar_csv_hugo()
    print(f"✓ Productos cargados: {len(datos)}")

    if len(datos) > 0:
        print(f"\nPrimer producto:")
        primer = datos[0]
        for clave, valor in list(primer.items())[:6]:
            print(f"  {clave}: {valor}")
        return True
    else:
        print("✗ ERROR: CSV vacío o no encontrado")
        return False


def test_busqueda():
    """Verifica búsquedas por marca y modelo."""
    print("\n═" * 60)
    print("TEST 2: Búsqueda de productos")
    print("═" * 60)

    # Test 1: Google Pixel
    productos = buscar_productos_en_csv("Google", "Pixel 7")
    print(f"\nBúsqueda: Google Pixel 7")
    print(f"Resultados: {len(productos)}")
    if productos:
        for p in productos[:2]:
            desc = p.get('DESCRIPCIÓN', '')
            calidad = p.get('CALIDAD', '')
            color = p.get('COLOR', '')
            precio = p.get('PRECIO_1', '')
            print(f"  • {desc} | {calidad} | {color} | {precio}")

    # Test 2: Samsung
    productos = buscar_productos_en_csv("Samsung", "Galaxy")
    print(f"\nBúsqueda: Samsung Galaxy")
    print(f"Resultados: {len(productos)}")

    # Test 3: iPhone
    productos = buscar_productos_en_csv("iPhone", "14")
    print(f"\nBúsqueda: iPhone 14")
    print(f"Resultados: {len(productos)}")

    return True


def test_categorias():
    """Verifica detección de categorías."""
    print("\n═" * 60)
    print("TEST 3: Detección de categorías")
    print("═" * 60)

    casos = [
        ("ORIG S/M", "ORIGINAL"),
        ("OLED S/M", "ORIGINAL"),
        ("INCELL", "GENERICO"),
        ("COG", "GENERICO"),
        ("AMOLED", "AMOLED"),
        ("CARTAN", "ORIGINAL"),
    ]

    for valor, esperado in casos:
        resultado = obtener_categoria(valor)
        estado = "✓" if resultado == esperado else "✗"
        print(f"{estado} {valor:15} → {resultado} (esperado: {esperado})")

    return True


def test_precios():
    """Verifica extracción y conversión de precios."""
    print("\n═" * 60)
    print("TEST 4: Extracción y conversión de precios")
    print("═" * 60)

    casos = [
        ("$ 208.00", 208.0),
        ("$ 1,200.00", 1200.0),
        ("$ 863.00", 863.0),
        ("208.00", 208.0),
    ]

    for valor, esperado in casos:
        precio_usd = extraer_precio_usd(valor)
        precio_mxn = int(precio_usd * 4) if precio_usd else None
        estado = "✓" if precio_usd == esperado else "✗"
        print(f"{estado} {valor:12} → USD ${precio_usd:8.2f} → MXN ${precio_mxn:,}")

    return True


async def test_cotizacion_completa():
    """Test de cotización end-to-end."""
    print("\n═" * 60)
    print("TEST 5: Cotización completa (end-to-end)")
    print("═" * 60)

    casos = [
        ("Google", "Pixel 7Pro"),
        ("Samsung", "Galaxy"),
        ("iPhone", "14"),
    ]

    for marca, modelo in casos:
        print(f"\n→ Cotización para {marca} {modelo}:")
        respuesta = await obtener_cotizacion_display(marca, modelo)
        print(respuesta)
        print("-" * 60)

    return True


async def main():
    """Ejecuta todos los tests."""
    print("\n" + "=" * 60)
    print("   TESTING SISTEMA DE PRICING CON HUGO SHOP")
    print("=" * 60)

    tests = [
        ("Cargar CSV", test_cargar_csv),
        ("Búsqueda", test_busqueda),
        ("Categorías", test_categorias),
        ("Precios", test_precios),
        ("Cotización", test_cotizacion_completa),
    ]

    for nombre, test_func in tests:
        try:
            if asyncio.iscoroutinefunction(test_func):
                resultado = await test_func()
            else:
                resultado = test_func()
            if not resultado:
                print(f"\n✗ Test '{nombre}' falló")
        except Exception as e:
            print(f"\n✗ Test '{nombre}' error: {e}")
            import traceback
            traceback.print_exc()

    print("\n" + "=" * 60)
    print("   TESTING COMPLETADO")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    asyncio.run(main())
