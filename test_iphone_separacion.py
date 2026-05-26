#!/usr/bin/env python3
"""
Test para verificar que iPhone 14 PRO y iPhone 14 PRO MAX
retornan precios DIFERENTES (como debe ser).
"""

import asyncio
import sys
sys.path.insert(0, '.')

from agent.pricing import (
    buscar_productos_en_csv,
    obtener_categoria,
    extraer_precio_usd,
    obtener_cotizacion_display,
)
from collections import defaultdict


async def test_modelo(marca, modelo):
    """Testea un modelo específico y retorna los precios por categoría."""
    print(f"\n{'='*70}")
    print(f"PROBANDO: {marca.upper()} {modelo.upper()}")
    print(f"{'='*70}\n")

    # Buscar productos
    productos = buscar_productos_en_csv(marca, modelo)
    print(f"Productos encontrados: {len(productos)}\n")

    # Agrupar por categoría
    productos_por_categoria = defaultdict(list)
    for prod in productos:
        calidad = prod.get('CALIDAD', '')
        categoria = obtener_categoria(calidad)
        if categoria:
            productos_por_categoria[categoria].append(prod)

    # Calcular precios
    precios_resultado = {}
    for categoria in ['GENERICO', 'ORIGINAL', 'AMOLED']:
        if categoria not in productos_por_categoria:
            continue

        productos_cat = productos_por_categoria[categoria]
        precios_usd = []

        for prod in productos_cat:
            precio_usd = extraer_precio_usd(prod.get('PRECIO_1', ''))
            if precio_usd:
                precios_usd.append(precio_usd)

        if precios_usd:
            promedio = sum(precios_usd) / len(precios_usd)
            precio_mxn = int(promedio * 4)
            precios_resultado[categoria] = precio_mxn
            print(f"{categoria}: ${precio_mxn:,} MXN (promedio USD: ${promedio:.2f})")

    # Generar respuesta completa
    print(f"\nRESPUESTA DEL AGENTE:")
    print("-" * 70)
    respuesta = await obtener_cotizacion_display(marca, modelo)
    print(respuesta)
    print("-" * 70)

    return precios_resultado


async def main():
    print("\n" + "="*70)
    print("  TEST DE SEPARACIÓN: iPhone 14 PRO vs iPhone 14 PRO MAX")
    print("="*70)

    # Probar ambos modelos
    precios_pro = await test_modelo('iphone', '14 pro')
    precios_max = await test_modelo('iphone', '14 pro max')

    # Comparar resultados
    print("\n" + "="*70)
    print("  VALIDACIÓN")
    print("="*70)

    if precios_pro == precios_max:
        print("\n❌ ERROR: iPhone 14 PRO y iPhone 14 PRO MAX tienen los mismos precios")
        print(f"   PRO: {precios_pro}")
        print(f"   MAX: {precios_max}")
        print("\n   El fix NO funcionó correctamente.")
    else:
        print("\n✅ CORRECTO: iPhone 14 PRO y iPhone 14 PRO MAX tienen precios diferentes")
        print(f"\n   iPhone 14 PRO:")
        for cat, precio in precios_pro.items():
            print(f"     {cat}: ${precio:,} MXN")
        print(f"\n   iPhone 14 PRO MAX:")
        for cat, precio in precios_max.items():
            print(f"     {cat}: ${precio:,} MXN")
        print("\n   ✅ El fix funcionó correctamente")

    print("\n" + "="*70 + "\n")


if __name__ == '__main__':
    asyncio.run(main())
