#!/usr/bin/env python3
"""
Test de detección de marca + modelo en brain.py
Verifica que la lógica de regex funciona para los casos que fallaban
"""

import re

def test_patron_marca_modelo():
    """Prueba el patrón regex de detección de marca + modelo."""
    patron_modelo = r'(iPhone|Samsung|Google Pixel|Pixel|OnePlus|Xiaomi|Motorola|Huawei|Nokia|LG|Moto|Poco|Redmi|Hisense|Honor|Oppo|Realme|TCL|Vivo|ZTE|Alcatel|Cubot)\s+([\w]+(?:\s+[\w]+){0,3})'

    test_cases = [
        ("Samsung a21", True, "Samsung", "a21"),
        ("Hisense e60", True, "Hisense", "e60"),
        ("Moto g85", True, "Moto", "g85"),
        ("Samsung a21s", True, "Samsung", "a21s"),
        ("Google Pixel 8", True, "Google Pixel", "8"),
        ("Pixel 8a", True, "Pixel", "8a"),
        ("iPhone 14 pro max", True, "iPhone", "14 pro max"),
        ("Motorola edge 60", True, "Motorola", "edge 60"),
        ("hello world", False, None, None),  # Sin marca
        ("precio samsung", False, None, None),  # Palabra antes de marca
    ]

    print("\n" + "="*70)
    print("  TEST: Detección de marca + modelo")
    print("="*70 + "\n")

    passed = 0
    failed = 0

    for texto, debe_coincidir, marca_esperada, modelo_esperado in test_cases:
        match = re.search(patron_modelo, texto, re.IGNORECASE)

        if debe_coincidir:
            if match:
                marca = match.group(1).strip()
                modelo = match.group(2).strip()
                if marca == marca_esperada and modelo == modelo_esperado:
                    print(f"✓ '{texto}' → {marca} {modelo}")
                    passed += 1
                else:
                    print(f"✗ '{texto}' → Coincidir: SÍ, pero valores incorrectos")
                    print(f"    Esperado: {marca_esperada} {modelo_esperado}")
                    print(f"    Obtenido: {marca} {modelo}")
                    failed += 1
            else:
                print(f"✗ '{texto}' → NO coincidió (pero debería)")
                failed += 1
        else:
            if match:
                print(f"✗ '{texto}' → Coincidió (pero no debería)")
                failed += 1
            else:
                print(f"✓ '{texto}' → Correctamente no coincidió")
                passed += 1

    print(f"\n{'='*70}")
    print(f"Resultados: {passed} pasaron, {failed} fallaron")
    print(f"{'='*70}\n")

    return failed == 0


if __name__ == "__main__":
    exito = test_patron_marca_modelo()
    exit(0 if exito else 1)
