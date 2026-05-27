#!/usr/bin/env python3
"""
Test end-to-end de flujo de precios:
Mensaje → detectar_y_obtener_precios → buscar_productos_en_csv → obtener_cotizacion_display
"""

import asyncio
import sys
sys.path.insert(0, '.')

from agent.brain import detectar_y_obtener_precios
from agent.pricing import buscar_productos_en_csv, obtener_cotizacion_display


async def test_flujo_completo():
    """Prueba el flujo completo para los casos que fallaban."""
    casos = [
        ("Samsung a21", "Samsung", "a21"),
        ("Hisense e60", "Hisense", "e60"),
        ("Moto g85", "Motorola", "g85"),  # Nota: El usuario escribe "Moto" pero buscar_productos_en_csv busca "Motorola"
        ("Moto e21", "Motorola", "e21"),
        ("Google Pixel 8", "Google Pixel", "8"),
        ("iPhone 14", "iPhone", "14"),
    ]

    print("\n" + "="*80)
    print("  TEST END-TO-END: Mensaje → Precios")
    print("="*80 + "\n")

    for mensaje, marca_esperada, modelo_esperado in casos:
        print(f"📱 Mensaje: '{mensaje}'")
        print(f"   Esperado: {marca_esperada} {modelo_esperado}")

        # Paso 1: Detección en brain.py
        contexto = await detectar_y_obtener_precios(mensaje)

        if contexto:
            print(f"   ✓ Detectado y obtenidos precios:")
            for linea in contexto.split("\n")[1:]:
                print(f"      {linea}")
        else:
            print(f"   ✗ NO se obtuvieron precios")

            # Debug: Intentar búsqueda directa
            print(f"      → Debug: buscando {marca_esperada} {modelo_esperado} directamente...")
            productos = buscar_productos_en_csv(marca_esperada, modelo_esperado)
            print(f"      → Productos encontrados: {len(productos)}")
            if productos:
                print(f"      → Primeros 2:")
                for prod in productos[:2]:
                    print(f"         {prod.get('CODIGO')} - {prod.get('DESCRIPCION')} (${prod.get('PRECIO_1')})")

        print()

    print("="*80 + "\n")


if __name__ == "__main__":
    asyncio.run(test_flujo_completo())
