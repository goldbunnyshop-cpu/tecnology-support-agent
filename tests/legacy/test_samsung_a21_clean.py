#!/usr/bin/env python3
"""Test limpio de Samsung A21 sin cache"""

import sys
import asyncio
import importlib

# Asegurar que importa fresh
sys.path.insert(0, '.')

# Limpiar cache completamente
for mod in list(sys.modules.keys()):
    if 'agent' in mod:
        del sys.modules[mod]

# Importar fresh
from agent import pricing
importlib.reload(pricing)

from agent.pricing import buscar_productos_en_csv, obtener_cotizacion_display

# Test búsqueda
productos = buscar_productos_en_csv('samsung', 'a21')
print(f"✓ Productos encontrados para 'samsung a21': {len(productos)}")

if productos:
    print("\nProductos encontrados:")
    for p in productos:
        print(f"  - {p.get('DESCRIPCION', '?'):40} | {p.get('CALIDAD', '?'):25} | ${p.get('PRECIO_1', '?')}")

    # Mostrar respuesta del agente
    async def test():
        print("\n" + "="*70)
        print("RESPUESTA DEL AGENTE:")
        print("="*70 + "\n")
        respuesta = await obtener_cotizacion_display('samsung', 'a21')
        print(respuesta)

    asyncio.run(test())
else:
    print("❌ No encontrado")
