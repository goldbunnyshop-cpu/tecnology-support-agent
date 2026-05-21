#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test: Verificar conexión con Google Calendar.
Ejecuta este script DESPUÉS de configurar config/credentials.json
"""

import asyncio
import os
import sys
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

# Agregar la carpeta al path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from agent.google_calendar_sync import (
    test_conexion,
    agregar_cita_a_calendar,
    obtener_proximas_citas
)


async def main():
    print("\n" + "="*70)
    print("   TEST: Google Calendar Integration")
    print("="*70)
    print()

    # Step 1: Verificar conexión
    print("📍 PASO 1: Verificar credenciales y conexión")
    print("-" * 70)
    conexion_ok = await test_conexion()
    print()

    if not conexion_ok:
        print("❌ La conexión con Google Calendar falló.")
        print()
        print("📖 Sigue estas instrucciones:")
        print("   1. Lee: GOOGLE_CALENDAR_SETUP.md")
        print("   2. Crea: config/credentials.json con tus credenciales")
        print("   3. Comparte tu Google Calendar con la Cuenta de Servicio")
        print()
        return

    # Step 2: Agregar cita de prueba
    print("\n📍 PASO 2: Crear una cita de prueba")
    print("-" * 70)

    # Calcular fecha y hora de prueba (mañana a las 10 AM)
    ahora = datetime.now()
    manana = ahora + timedelta(days=1)
    fecha_test = manana.strftime("%Y-%m-%d")
    hora_test = "10:00"

    print(f"📋 Cita de prueba:")
    print(f"   👤 Cliente: Test User AgentKit")
    print(f"   📱 Dispositivo: iPhone 15")
    print(f"   ⚠️  Problema: Pantalla rota")
    print(f"   📅 Fecha: {fecha_test}")
    print(f"   🕐 Hora: {hora_test}")
    print(f"   👨‍💼 Asesor: Sistema de Test")
    print()

    resultado = await agregar_cita_a_calendar(
        nombre_cliente="Test User AgentKit",
        dispositivo="iPhone 15",
        problema="Pantalla rota (test)",
        fecha_str=fecha_test,
        hora_str=hora_test,
        asesor="Sistema"
    )

    if resultado:
        print("✅ Cita de prueba creada exitosamente en Google Calendar")
    else:
        print("❌ Error al crear cita de prueba")
        return

    # Step 3: Obtener citas próximas
    print("\n📍 PASO 3: Listar próximas citas")
    print("-" * 70)

    eventos = await obtener_proximas_citas(dias=7)
    if eventos:
        print(f"📋 Próximos {len(eventos)} eventos en los próximos 7 días:\n")
        for idx, evento in enumerate(eventos[:5], 1):
            titulo = evento.get("summary", "Sin título")
            inicio = evento.get("start", {}).get("dateTime", "").split("T")[0]
            hora = evento.get("start", {}).get("dateTime", "").split("T")[1][:5]
            print(f"   {idx}. {titulo}")
            print(f"      📅 {inicio} {hora}")
    else:
        print("⚠️  No hay citas próximas (o no se pudieron obtener)")

    print("\n" + "="*70)
    print("   ✅ TEST COMPLETADO EXITOSAMENTE")
    print("="*70)
    print()
    print("📝 Próximos pasos:")
    print("   1. Abre tu Google Calendar: https://calendar.google.com/")
    print("   2. Busca la cita 'Test User AgentKit — iPhone 15'")
    print("   3. Si aparece, todo está funcionando ✅")
    print("   4. Puedes continuar con el deploy a Railway")
    print()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\nTest cancelado por el usuario")
    except Exception as e:
        print(f"\n❌ Error inesperado: {e}")
        import traceback
        traceback.print_exc()
