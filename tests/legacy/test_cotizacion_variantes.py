#!/usr/bin/env python3
"""
Test de cotización con variantes — Muestra respuesta al cliente
Verifica que la respuesta sea correcta para modelos con variantes
"""

import asyncio
import sys
sys.path.insert(0, '.')

from agent.pricing import obtener_cotizacion_display


async def test_cotizacion(marca, modelo):
    """Testea la cotización para un modelo específico."""
    print(f"\n{'─'*70}")
    print(f"Consulta: {marca.upper()} {modelo.upper()}")
    print(f"{'─'*70}\n")

    respuesta = await obtener_cotizacion_display(marca, modelo)
    print(respuesta)


async def main():
    print("\n" + "="*70)
    print("  TEST DE COTIZACIÓN: Variantes de modelos")
    print("  (Muestra respuesta completa al cliente)")
    print("="*70)

    # Casos de prueba clave con variantes
    casos = [
        ('iphone', '14 pro'),      # iPhone with Pro variant
        ('iphone', '14 pro max'),  # iPhone with Max variant
        ('samsung', 'a21'),        # Samsung base model
        ('samsung', 'a21s'),       # Samsung with S variant
        ('motorola', 'e30'),       # Motorola with variants
        ('google pixel', '8'),     # Google Pixel
        ('google pixel', '8a'),    # Google Pixel with a variant
        ('hisense', 'e60'),        # Hisense
    ]

    for marca, modelo in casos:
        await test_cotizacion(marca, modelo)

    print("\n" + "="*70 + "\n")


if __name__ == '__main__':
    asyncio.run(main())
