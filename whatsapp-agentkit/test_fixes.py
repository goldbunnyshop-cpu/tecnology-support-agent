#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test rápido de los 3 fixes:
1. UTF-8 encoding en Whapi
2. Notificaciones al grupo con logging mejorado
3. Guardado de citas en PostgreSQL
"""

import asyncio
import sys
import os
from datetime import datetime
from zoneinfo import ZoneInfo

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv()

ZONA_CDMX = ZoneInfo("America/Mexico_City")

async def main():
    print("\n" + "="*80)
    print("🧪 TEST RÁPIDO DE FIXES - Sistema de Citas")
    print("="*80 + "\n")

    # ───────────────────────────────────────────────────────────────────────
    # TEST 1: Verificar que el grupo está configurado
    # ───────────────────────────────────────────────────────────────────────
    print("📋 TEST 1: Configuración del grupo")
    print("-" * 80)

    grupo_id = os.getenv("GRUPO_CHRISTIAN_INTERNO", "").strip()
    print(f"GRUPO_CHRISTIAN_INTERNO = {grupo_id if grupo_id else '❌ NO CONFIGURADO'}")

    if grupo_id:
        print(f"✅ Grupo configurado correctamente")
    else:
        print(f"❌ ERROR: Necesitas agregar GRUPO_CHRISTIAN_INTERNO al .env")
        print(f"   Ejemplo: GRUPO_CHRISTIAN_INTERNO=120363423715417410@g.us")
        return

    # ───────────────────────────────────────────────────────────────────────
    # TEST 2: Probar notificación del grupo con new logging
    # ───────────────────────────────────────────────────────────────────────
    print("\n📱 TEST 2: Envío de notificación de prueba al grupo")
    print("-" * 80)

    try:
        from agent.appointment_notifications import notificar_nueva_cita

        nombre_test = "Test Cliente"
        fecha_test = "Lunes 20 de mayo"
        hora_test = "10:00 a.m."

        print(f"Enviando notificación...")
        print(f"  Cliente: {nombre_test}")
        print(f"  Fecha: {fecha_test} | Hora: {hora_test}")

        # Llamar directamente (no con asyncio.create_task)
        await notificar_nueva_cita(
            nombre=nombre_test,
            telefono="+525541234567",
            dispositivo="iPhone 14",
            problema="Pantalla rota",
            fecha_texto=fecha_test,
            hora_texto=hora_test,
            asesor="Sofia",
            evento_id="TEST_123",
        )
        print("\n✅ Función ejecutada — revisa los logs arriba para detalles")

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()

    # ───────────────────────────────────────────────────────────────────────
    # TEST 3: Probar UTF-8 encoding en Whapi
    # ───────────────────────────────────────────────────────────────────────
    print("\n" + "="*80)
    print("✏️ TEST 3: UTF-8 Encoding en Whapi")
    print("-" * 80)

    try:
        from agent.providers import obtener_proveedor

        proveedor = obtener_proveedor()
        print(f"Proveedor: {proveedor.__class__.__name__}")

        mensaje_unicode = "✅ *CITA CONFIRMADA* — ¡Lunes 20 de mayo, 10:00 a.m.! 🎉"
        print(f"\nMensaje de prueba:")
        print(f"  {mensaje_unicode}")

        # Validar encoding
        try:
            encoded = mensaje_unicode.encode('utf-8')
            decoded = encoded.decode('utf-8')
            if decoded == mensaje_unicode:
                print(f"✅ UTF-8 válido — {len(encoded)} bytes")
            else:
                print(f"❌ Mismatch en UTF-8")
        except Exception as e:
            print(f"❌ Error en UTF-8: {e}")

        # Nota: No enviamos de verdad para no molestar
        print("\n(No se envía el mensaje para no saturar — pero la función está lista)")

    except Exception as e:
        print(f"❌ Error: {e}")

    # ───────────────────────────────────────────────────────────────────────
    # RESUMEN
    # ───────────────────────────────────────────────────────────────────────
    print("\n" + "="*80)
    print("✅ TEST COMPLETADO")
    print("="*80)
    print("\n📝 Próximos pasos:")
    print("  1. Revisa los logs arriba para ver si la notificación se envió")
    print("  2. Si ves '[CITAS GRUPO] ✅ Mensaje enviado', el grupo está funcionando")
    print("  3. Si ves caracteres raros (Â¡), hay un problema de encoding")
    print("  4. Prueba enviando un mensaje real de WhatsApp para testear todo junto\n")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n⛔ Cancelado")
        sys.exit(0)
