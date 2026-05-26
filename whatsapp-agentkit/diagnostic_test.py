#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script de diagnóstico — Prueba las 3 áreas críticas del agente de citas
1. Caracteres mojibake en respuestas
2. Notificaciones al grupo interno
3. Guardado de citas en PostgreSQL
"""

import asyncio
import sys
import os
import json
from datetime import datetime
from zoneinfo import ZoneInfo

# Agregar directorio raíz al path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv()

ZONA_CDMX = ZoneInfo("America/Mexico_City")

# ════════════════════════════════════════════════════════════════════════════════
# TEST 1: Caracteres Mojibake (UTF-8 encoding)
# ════════════════════════════════════════════════════════════════════════════════

def test_encoding():
    """Verifica si los caracteres especiales se codifican correctamente."""
    print("\n" + "="*80)
    print("TEST 1: ENCODING DE CARACTERES (Mojibake)")
    print("="*80 + "\n")

    textos_test = [
        "✅ CITA CONFIRMADA",
        "¡Hola! Este es un test",
        "Gracias por tu preferencia. ¡Te esperamos!",
        "⏰ Lunes 18 de mayo, 10:00 a.m.",
        "📱 iPhone 14 Pro | ⚠️ Pantalla rota",
    ]

    print("Textos a verificar:")
    for i, texto in enumerate(textos_test, 1):
        print(f"  {i}. {texto}")

        # Verificar si se puede codificar a UTF-8
        try:
            encoded = texto.encode("utf-8")
            decoded = encoded.decode("utf-8")
            match = texto == decoded
            status = "✅ OK" if match else "❌ MISMATCH"
            print(f"     {status} — Tamaño: {len(encoded)} bytes")
        except Exception as e:
            print(f"     ❌ ERROR: {e}")

    # Test de emojis
    print("\n📊 Test de emojis:")
    emojis = ["✅", "❌", "⏰", "📱", "👤", "📞", "👨‍💼", "🔔"]
    for emoji in emojis:
        try:
            bytes_emoji = emoji.encode("utf-8")
            print(f"  {emoji} → {bytes_emoji.hex()} → {'OK' if emoji == bytes_emoji.decode('utf-8') else 'CORRUPTED'}")
        except Exception as e:
            print(f"  {emoji} → ERROR: {e}")

    print("\n✓ Test 1 completado")


# ════════════════════════════════════════════════════════════════════════════════
# TEST 2: Notificaciones al grupo
# ════════════════════════════════════════════════════════════════════════════════

async def test_group_notifications():
    """Prueba el envío de notificaciones al grupo interno."""
    print("\n" + "="*80)
    print("TEST 2: NOTIFICACIONES AL GRUPO INTERNO")
    print("="*80 + "\n")

    # Verificar configuración
    grupo_id = os.getenv("GRUPO_CHRISTIAN_INTERNO", "").strip()
    whapi_token = os.getenv("WHAPI_TOKEN", "").strip()

    print("📋 Configuración:")
    print(f"  GRUPO_CHRISTIAN_INTERNO: {grupo_id if grupo_id else '❌ NO CONFIGURADO'}")
    print(f"  WHAPI_TOKEN: {whapi_token[:10]}..." if whapi_token else "  WHAPI_TOKEN: ❌ NO CONFIGURADO")

    if not grupo_id or not whapi_token:
        print("\n❌ Configuración incompleta — no puedo testear notificaciones")
        return

    # Test de envío
    print("\n🔄 Intentando enviar mensaje de prueba al grupo...")
    try:
        import httpx

        mensaje_test = (
            "🧪 *TEST DE NOTIFICACIONES*\n"
            "Este es un mensaje de prueba para verificar que el sistema de notificaciones funciona correctamente.\n"
            "⏰ Hora: " + datetime.now(ZONA_CDMX).strftime("%d/%m/%Y %H:%M:%S")
        )

        async with httpx.AsyncClient(timeout=15) as http:
            r = await http.post(
                "https://gate.whapi.cloud/messages/text",
                headers={"Authorization": f"Bearer {whapi_token}", "Content-Type": "application/json"},
                json={"to": grupo_id, "body": mensaje_test},
            )

            print(f"\n  HTTP Status: {r.status_code}")
            if r.status_code == 200:
                print("  ✅ Mensaje enviado correctamente al grupo")
                print(f"  Respuesta: {r.json()}")
            else:
                print(f"  ❌ Error HTTP {r.status_code}")
                print(f"  Respuesta: {r.text[:200]}")

    except Exception as e:
        print(f"  ❌ Excepción: {e}")
        import traceback
        traceback.print_exc()

    print("\n✓ Test 2 completado")


# ════════════════════════════════════════════════════════════════════════════════
# TEST 3: Guardado de citas en PostgreSQL
# ════════════════════════════════════════════════════════════════════════════════

async def test_database_saving():
    """Prueba guardar y recuperar una cita de prueba en la BD."""
    print("\n" + "="*80)
    print("TEST 3: GUARDADO DE CITAS EN POSTGRESQL")
    print("="*80 + "\n")

    # Verificar configuración de BD
    db_url = os.getenv("DATABASE_URL", "").strip()
    print("📋 Configuración:")
    print(f"  DATABASE_URL: {db_url[:50]}..." if db_url else "  DATABASE_URL: ❌ NO CONFIGURADO")

    if not db_url:
        print("\n❌ Base de datos no configurada")
        return

    try:
        from agent.memory import inicializar_db, async_session, guardar_mensaje

        print("\n🔄 Inicializando base de datos...")
        await inicializar_db()
        print("  ✅ Base de datos inicializada")

        # Test de inserción
        print("\n🔄 Intentando guardar un mensaje de prueba...")
        numero_test = "+525541234567"

        await guardar_mensaje(numero_test, "user", "Hola, tengo un iPhone roto")
        print(f"  ✅ Mensaje de usuario guardado")

        await guardar_mensaje(numero_test, "assistant", "✅ *CITA CONFIRMADA* — Lunes 20 de mayo, 10:00 a.m.")
        print(f"  ✅ Mensaje del agente guardado")

        # Test de recuperación
        print("\n🔄 Recuperando historial...")
        from agent.memory import obtener_historial

        historial = await obtener_historial(numero_test, limite=10)
        print(f"  ✅ Historial recuperado: {len(historial)} mensajes")
        for msg in historial:
            print(f"    • {msg['role']}: {msg['content'][:60]}...")

        # Test de cita específica
        print("\n🔄 Insertando cita de prueba directamente...")
        from agent.cita_detector import guardar_cita_automatica

        fecha_test = datetime(2026, 5, 20, 10, 0, tzinfo=ZONA_CDMX)
        exito = await guardar_cita_automatica(
            nombre="Test Cliente",
            dispositivo="iPhone 14",
            problema="Pantalla rota",
            fecha_hora=fecha_test,
            asesor="Agente Test",
            telefono=numero_test,
        )

        if exito:
            print("  ✅ Cita de prueba guardada exitosamente")
        else:
            print("  ❌ No se pudo guardar la cita")

    except Exception as e:
        print(f"  ❌ Excepción: {e}")
        import traceback
        traceback.print_exc()

    print("\n✓ Test 3 completado")


# ════════════════════════════════════════════════════════════════════════════════
# MAIN
# ════════════════════════════════════════════════════════════════════════════════

async def main():
    print("\n")
    print("╔" + "="*78 + "╗")
    print("║" + " "*20 + "DIAGNOSTIC TEST — Sistema de Citas" + " "*24 + "║")
    print("╚" + "="*78 + "╝")

    # Test 1: Encoding
    test_encoding()

    # Test 2: Notificaciones
    await test_group_notifications()

    # Test 3: Base de datos
    await test_database_saving()

    print("\n" + "="*80)
    print("✅ DIAGNÓSTICO COMPLETADO")
    print("="*80)
    print("\nSiguientes pasos:")
    print("1. Si Test 1 mostró caracteres corruptos → Problema de encoding UTF-8")
    print("2. Si Test 2 falló → Problema de Whapi o configuración de grupo")
    print("3. Si Test 3 falló → Problema de conexión a PostgreSQL o SQLAlchemy")
    print("\n")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n⛔ Diagnóstico cancelado por usuario")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Error crítico: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
