#!/usr/bin/env python3
"""
Script de diagnóstico para el sistema de precios.
Ejecuta esto en Railway para verificar qué está pasando con iPhone 14 Pro.
"""

import asyncio
import sys
sys.path.insert(0, '.')

from agent.pricing import (
    buscar_productos_en_csv,
    obtener_categoria,
    extraer_precio_usd,
    obtener_cotizacion_display,
    cargar_csv_hugo
)
from collections import defaultdict


async def diagnosticar():
    print("=" * 70)
    print("DIAGNÓSTICO DEL SISTEMA DE PRECIOS — iPhone 14 Pro")
    print("=" * 70)
    print()

    # 1. Verificar que CSV se carga
    print("1. CARGANDO CSV...")
    datos = cargar_csv_hugo()
    print(f"   Total de productos en CSV: {len(datos)}")
    print()

    # 2. Buscar productos
    print("2. BÚSQUEDA: marca='iphone', modelo='14 pro'")
    productos = buscar_productos_en_csv('iphone', '14 pro')
    print(f"   Productos encontrados: {len(productos)}")
    print()

    # 3. Mapear categorías
    print("3. MAPEO DE CATEGORÍAS")
    productos_por_categoria = defaultdict(list)

    for prod in productos:
        calidad = prod.get('CALIDAD', '')
        categoria = obtener_categoria(calidad)
        if categoria:
            productos_por_categoria[categoria].append(prod)
            print(f"   [{categoria}] {prod.get('DESCRIPCION', '?')[:40]}")
        else:
            print(f"   [NO MAPEADA] CALIDAD: {calidad[:40]}")

    print()

    # 4. Calcular precios por categoría
    print("4. CÁLCULO DE PRECIOS")
    for categoria in ['GENERICO', 'ORIGINAL', 'AMOLED']:
        if categoria not in productos_por_categoria:
            print(f"   {categoria}: No hay productos")
            continue

        productos_cat = productos_por_categoria[categoria]
        precios_usd = []

        print(f"   {categoria}:")
        for prod in productos_cat:
            precio_str = prod.get('PRECIO_1', '')
            precio_usd = extraer_precio_usd(precio_str)
            if precio_usd:
                precios_usd.append(precio_usd)
                print(f"      ${precio_usd} USD - {prod.get('DESCRIPCION', '?')[:35]}")

        if precios_usd:
            promedio = sum(precios_usd) / len(precios_usd)
            precio_mxn = int(promedio * 4)
            print(f"      PROMEDIO: ${promedio:.2f} USD = ${precio_mxn:,} MXN")
        print()

    # 5. Generar respuesta completa
    print("5. RESPUESTA COMPLETA DEL AGENTE:")
    print("-" * 70)
    respuesta = await obtener_cotizacion_display('iphone', '14 pro')
    print(respuesta)
    print("-" * 70)
    print()

    print("=" * 70)
    print("FIN DEL DIAGNÓSTICO")
    print("=" * 70)


if __name__ == '__main__':
    asyncio.run(diagnosticar())
