#!/usr/bin/env python3
"""
Diagnóstico para Hisense E60 y Samsung A21
"""

import asyncio
import sys
sys.path.insert(0, '.')

from agent.pricing import (
    buscar_productos_en_csv,
    obtener_categoria,
    extraer_precio_usd,
    obtener_cotizacion_display,
    cargar_csv_hugo,
)
from collections import defaultdict


async def test_modelo(marca, modelo):
    """Testea un modelo y muestra detalles de la búsqueda."""
    print(f"\n{'='*70}")
    print(f"PROBANDO: {marca.upper()} {modelo.upper()}")
    print(f"{'='*70}\n")

    # 1. Cargar CSV y mostrar todos los productos de esta marca
    todos_datos = cargar_csv_hugo()
    print(f"Total de productos en CSV: {len(todos_datos)}")

    # Filtrar por marca para ver qué existe
    productos_marca = []
    for prod in todos_datos:
        desc = str(prod.get('DESCRIPCION', '')).lower()
        if marca.lower() in desc:
            productos_marca.append(prod)

    print(f"Productos de {marca.upper()} en CSV: {len(productos_marca)}")
    if productos_marca:
        print("\nEjemplos de productos disponibles:")
        for i, prod in enumerate(productos_marca[:5]):
            desc = prod.get('DESCRIPCION', '?')
            precio = prod.get('PRECIO_1', '?')
            calidad = prod.get('CALIDAD', '?')
            print(f"  {i+1}. {desc} | CALIDAD: {calidad} | PRECIO: {precio}")
    print()

    # 2. Buscar el modelo específico
    productos = buscar_productos_en_csv(marca, modelo)
    print(f"Productos encontrados para '{modelo}': {len(productos)}")

    if not productos:
        print(f"❌ NO HAY PRODUCTOS ENCONTRADOS")
        print(f"\nPosibles razones:")
        print(f"  1. El modelo '{modelo}' no existe en el CSV")
        print(f"  2. La lógica de búsqueda no coincide con la descripción")
        print(f"  3. El modelo está escrito diferente en el CSV")
        return

    # 3. Mostrar detalles de cada producto encontrado
    print("\nDetalles de productos encontrados:")
    for i, prod in enumerate(productos):
        print(f"\n  [{i+1}] {prod.get('DESCRIPCION', '?')}")
        print(f"      CALIDAD: {prod.get('CALIDAD', '?')}")
        print(f"      PRECIO: {prod.get('PRECIO_1', '?')}")
        precio_usd = extraer_precio_usd(prod.get('PRECIO_1', ''))
        cat = obtener_categoria(prod.get('CALIDAD', ''))
        print(f"      CATEGORÍA: {cat} | PRECIO_USD: {precio_usd}")

    # 4. Agrupar por categoría
    print(f"\n\nAGRUPADO POR CATEGORÍA:")
    productos_por_categoria = defaultdict(list)
    for prod in productos:
        calidad = prod.get('CALIDAD', '')
        categoria = obtener_categoria(calidad)
        if categoria:
            productos_por_categoria[categoria].append(prod)
        else:
            print(f"  ⚠️ CALIDAD NO RECONOCIDA: {calidad}")

    # 5. Calcular precios
    tiene_precios = False
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
            tiene_precios = True
            promedio = sum(precios_usd) / len(precios_usd)
            precio_mxn = int(promedio * 4)
            print(f"  {categoria}: ${precio_mxn:,} MXN (promedio USD: ${promedio:.2f})")

    if not tiene_precios:
        print("  ❌ SIN PRECIOS VÁLIDOS")
        print(f"\n  Posible razón:")
        print(f"    - Los productos encontrados no tienen CALIDAD reconocida")
        print(f"    - O no tienen PRECIO_1 válido")

    # 6. Respuesta del agente
    print(f"\n\nRESPUESTA DEL AGENTE:")
    print("-" * 70)
    respuesta = await obtener_cotizacion_display(marca, modelo)
    print(respuesta)
    print("-" * 70)


async def main():
    print("\n" + "="*70)
    print("  DIAGNÓSTICO: Hisense E60 y Samsung A21")
    print("="*70)

    await test_modelo('hisense', 'e60')
    await test_modelo('samsung', 'a21')

    print("\n" + "="*70 + "\n")


if __name__ == '__main__':
    asyncio.run(main())
