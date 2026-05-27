#!/usr/bin/env python3
"""
Test integral de variantes de modelos — Todas las marcas
Verifica que el fix general funcione para iPhone, Samsung, Motorola, Pixel, Hisense
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


async def test_marca_modelo(marca, modelos_a_probar):
    """Testea una marca con múltiples variantes de modelo."""
    print(f"\n{'='*70}")
    print(f"MARCA: {marca.upper()}")
    print(f"{'='*70}\n")

    for modelo in modelos_a_probar:
        productos = buscar_productos_en_csv(marca, modelo)

        # Agrupar por categoría
        productos_por_categoria = defaultdict(list)
        for prod in productos:
            calidad = prod.get('CALIDAD', '')
            categoria = obtener_categoria(calidad)
            if categoria:
                productos_por_categoria[categoria].append(prod)

        # Calcular precios
        precios_encontrados = {}
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
                precios_encontrados[categoria] = precio_mxn

        # Resultado
        if precios_encontrados:
            print(f"  ✓ {marca} {modelo:20} → ", end="")
            for cat, precio in precios_encontrados.items():
                print(f"{cat}: ${precio:,} MXN  ", end="")
            print()
        else:
            print(f"  ✗ {marca} {modelo:20} → NO ENCONTRADO")


async def main():
    print("\n" + "="*70)
    print("  TEST INTEGRAL: Variantes de modelos — Todas las marcas")
    print("="*70)

    # Marcas y sus variantes a probar
    pruebas = {
        'iphone': ['14', '14 pro', '14 pro max', '15', '15 pro', '15 pro max'],
        'samsung': ['a21', 'a21s', 'a217', 's21', 's21+', 'a12', 'a12s'],
        'motorola': ['e21', 'e21s', 'e22', 'e30', 'e32', 'g42'],
        'google pixel': ['7', '7a', '8', '8a'],
        'pixel': ['7', '7a', '8', '8a'],  # Alternativa
        'hisense': ['e60', 'e30', 'e40', 'v60'],
    }

    for marca, modelos in pruebas.items():
        await test_marca_modelo(marca, modelos)

    print("\n" + "="*70 + "\n")


if __name__ == '__main__':
    asyncio.run(main())
