#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script para obtener el ID del grupo de WhatsApp desde Whapi.cloud
"""
import os
import sys
import httpx
import json
from dotenv import load_dotenv

load_dotenv()
token = os.getenv("WHAPI_TOKEN")

if not token:
    print("❌ ERROR: WHAPI_TOKEN no encontrado en .env")
    sys.exit(1)

print("🔍 Conectando a Whapi.cloud...")

try:
    response = httpx.get(
        "https://gate.whapi.cloud/chats",
        headers={"Authorization": f"Bearer {token}"},
        params={"count": 100},
        timeout=15
    )

    if response.status_code != 200:
        print(f"❌ Error de conexión: {response.status_code}")
        print(f"   Response: {response.text}")
        sys.exit(1)

    chats = response.json().get("chats", [])
    grupos = [c for c in chats if c.get("is_group")]

    print(f"\n✅ Conectado. Encontrados {len(grupos)} grupos:\n")

    if not grupos:
        print("⚠️  No hay grupos en esta cuenta de Whapi")
        sys.exit(1)

    # Mostrar todos los grupos
    for idx, g in enumerate(grupos, 1):
        print(f"  {idx}. {g.get('name')}")
        print(f"     ID: {g.get('id')}\n")

    # Buscar automáticamente el grupo de Christian/Taller
    print("\n" + "="*70)
    print("🔎 BÚSQUEDA AUTOMÁTICA:")
    print("="*70 + "\n")

    palabras_clave = ["taller", "interno", "christian", "soporte", "ts", "reparacion"]
    encontrado = False

    for g in grupos:
        nombre = g.get("name", "").lower()
        if any(x in nombre for x in palabras_clave):
            print(f"✅ GRUPO DETECTADO:")
            print(f"   Nombre: {g.get('name')}")
            print(f"   ID: {g.get('id')}")
            print(f"\n📋 Agrégalo a tu .env como:")
            print(f"   GRUPO_CHRISTIAN_INTERNO={g.get('id')}")
            encontrado = True
            break

    if not encontrado:
        print("ℹ️  No se encontró automáticamente.")
        print("   Selecciona el grupo manualmente de la lista arriba.")
        print("   Busca por nombre (Taller Interno, etc.)")
        print("   Copia el ID y agrégalo al .env")

except Exception as e:
    print(f"❌ ERROR: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
