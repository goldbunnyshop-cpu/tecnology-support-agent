#!/usr/bin/env python3
"""Test de detectar_y_obtener_precios sin dependencias de Anthropic."""

import re
import sys

def _confirmar_variante_amb(modelo: str) -> tuple:
    modelo_lower = modelo.lower()
    if '+' in modelo_lower:
        modelo_limpio = modelo_lower.replace(' +', '').replace('+', '')
        return f"Detecte {modelo_limpio.title()} Plus. Confirma?", True
    return "", False

def detectar_marca_modelo(mensaje: str) -> str:
    """Extrae solo la lógica de detección de marca+modelo sin llamadas async."""
    patrones_display = [
        r'\bcotizar.*(?:display|pantalla|screen)\b',
        r'\bprecio\b', r'\bcosto\b', r'\bvalor\b',
    ]

    mensaje_lower = mensaje.lower()
    es_pregunta_precio = any(re.search(p, mensaje_lower) for p in patrones_display)

    patron_modelo = r'(iPhone|Samsung|Google Pixel|Pixel|OnePlus|Xiaomi|Motorola|Huawei|Nokia|LG|Moto|Poco|Redmi|Hisense|Honor|Oppo|Realme|TCL|Vivo|ZTE|Alcatel|Cubot)\s+([\w]+(?:\s+[\w]+){0,3})'
    match = re.search(patron_modelo, mensaje, re.IGNORECASE)

    # LÓGICA CLAVE: Retorna información si TIENE keywords OR marca+modelo
    if es_pregunta_precio:
        print(f"   [Log] Precio keywords detectados")
    elif match:
        print(f"   [Log] Marca+modelo detectado SIN keywords")
    else:
        print(f"   [Log] Sin precio ni marca+modelo -> retorna vacio")
        return ""

    if not match:
        print(f"   [Log] Precio detectado pero sin modelo")
        return ""

    marca = match.group(1)
    modelo = match.group(2).strip()
    return f"{marca}|{modelo}"

print("\n" + "="*80)
print("  TEST: Logica de deteccion SIN keywords de precio")
print("="*80 + "\n")

test_cases = [
    ("Samsung a21", True, "Samsung a21"),
    ("Hisense e60", True, "Hisense e60"),
    ("Moto g85", True, "Moto g85"),
    ("Google Pixel 8", True, "Google Pixel 8"),
    ("iPhone 14", True, "iPhone 14"),
    ("hola como estas", False, ""),
]

passed = 0
failed = 0

for mensaje, debe_encontrar, esperado in test_cases:
    print(f"Mensaje: '{mensaje}'")
    resultado = detectar_marca_modelo(mensaje)
    
    if debe_encontrar:
        if resultado and resultado.replace("|", " ") == esperado:
            print(f"   ✓ Encontrado: {esperado}\n")
            passed += 1
        else:
            print(f"   ✗ Esperado: {esperado}, obtuve: {resultado}\n")
            failed += 1
    else:
        if not resultado:
            print(f"   ✓ Correctamente no encontrado\n")
            passed += 1
        else:
            print(f"   ✗ No deberia encontrar pero obtuve: {resultado}\n")
            failed += 1

print("="*80)
print(f"Resultados: {passed} pasaron, {failed} fallaron")
print("="*80)

sys.exit(0 if failed == 0 else 1)
