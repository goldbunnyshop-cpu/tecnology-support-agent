#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test local de Hugo Shop — Verifica que los precios se consulten correctamente
Ejecutar: python test_hugo_shop.py
"""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
from agent.tools import obtener_precio_display, formatear_respuesta_precio

load_dotenv()

print()
print("=" * 80)
print("   TEST HUGO SHOP — Consulta de precios de displays")
print("=" * 80)
print()

# Casos de prueba
casos = [
    ("iPhone", "16"),
    ("iPhone", "15"),
    ("Samsung", "S24"),
    ("Samsung", "S24 Ultra"),
    ("Xiaomi", "14"),
]

print("📱 TESTANDO CONSULTAS A HUGO SHOP:\n")

for marca, modelo in casos:
    print(f"  Consultando: {marca} {modelo}")
    precio = obtener_precio_display(marca, modelo)

    if precio["encontrado"]:
        print(f"    ✅ Encontrado")
        print(f"       Genérico (x4):  ${precio['precio_generico']:,} MXN")
        print(f"       Original (x3):  ${precio['precio_original']:,} MXN")
    else:
        print(f"    ⚠️  {precio['razon']}")
    print()

print("=" * 80)
print("   EJEMPLO DE RESPUESTA AL CLIENTE")
print("=" * 80)
print()

respuesta = formatear_respuesta_precio("iPhone", "16")
print(respuesta)

print()
print("=" * 80)
print("   TEST COMPLETADO")
print("=" * 80)
print()
print("Si ves valores con $ significa que Hugo Shop está conectado y funciona.")
print("Si ves '⚠️ no está en nuestro catálogo', revisa que la hoja tenga ese modelo.")
print()
