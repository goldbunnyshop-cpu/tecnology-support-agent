#!/usr/bin/env python3
"""Test de busqueda dual: marca explícita vs fallback por modelo solo."""

import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from agent.brain import detectar_y_obtener_precios


async def test_casos():
    """Prueba casos de uso de la búsqueda dual."""
    casos = [
        # Con marca explícita (debe funcionar como antes)
        "Cuanto cuesta display Samsung S23?",
        "Que precio tiene un iPhone 14 pro?",
        "Presupuesto para Samsung A21",

        # Sin marca (NUEVOS - deben usar fallback)
        "Precio para s23?",
        "Cuanto cuesta a14?",
        "Que valor tiene edge 50?",
        "Display s23 ultra precio?",
        "Cotizar pixel 8?",

        # Casos donde no se detecta nada
        "Hola como estas?",
        "Quiero reparar mi celular",
    ]

    print("=" * 60)
    print("TEST BÚSQUEDA DUAL — Display Pricing")
    print("=" * 60)
    print()

    for i, caso in enumerate(casos, 1):
        print(f"Caso {i}: {caso}")
        resultado = await detectar_y_obtener_precios(caso)
        if resultado:
            print(f"✓ RESPUESTA:\n{resultado}")
        else:
            print("✗ Sin respuesta (ningún precio detectado)")
        print("-" * 60)
        print()


if __name__ == "__main__":
    asyncio.run(test_casos())
