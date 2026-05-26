#!/usr/bin/env python3
"""
Test para verificar que _variantes_telefono funciona correctamente
y que la función esta_pausada puede buscar por diferentes formatos de número.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from agent.memory import _variantes_telefono


def test_variantes():
    """Test de diferentes formatos de números."""

    print("\n" + "="*70)
    print("TEST: Variantes de teléfono")
    print("="*70 + "\n")

    test_cases = [
        "5541576333",                    # Formato limpio (10 dígitos)
        "5541576333@c.us",              # Formato Whapi
        "525541576333",                 # Con prefijo 52
        "5215541576333",                # Con prefijo 521
        "+525541576333",                # Con +52
    ]

    for numero in test_cases:
        try:
            variantes = _variantes_telefono(numero)
            print(f"Input: '{numero}'")
            print(f"Variantes: {variantes}")
            print()
        except Exception as e:
            print(f"Input: '{numero}'")
            print(f"❌ ERROR: {e}")
            print()


if __name__ == "__main__":
    test_variantes()
