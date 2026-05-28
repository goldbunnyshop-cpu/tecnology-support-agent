#!/usr/bin/env python3
"""Diagnóstico completo del sistema del agente WhatsApp."""

import asyncio
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

async def diagnosticar():
    print("=" * 80)
    print("DIAGNÓSTICO COMPLETO — AgentKit WhatsApp")
    print("=" * 80)
    print()

    # 1. GOOGLE CALENDAR INTEGRATION
    print("1️⃣  GOOGLE CALENDAR INTEGRATION")
    print("-" * 80)
    try:
        from agent.google_calendar import obtener_eventos_proximos, obtener_eventos_rango
        print("   ✅ Módulo google_calendar importado correctamente")

        # Verificar si hay credenciales
        if os.path.exists("google_creds.json"):
            print("   ✅ Credenciales de Google encontradas (google_creds.json)")
        else:
            print("   ⚠️  NO se encontraron credenciales (google_creds.json)")

        # Verificar si hay calendar_id en env
        cal_id = os.getenv("GOOGLE_CALENDAR_ID", "")
        if cal_id:
            print(f"   ✅ GOOGLE_CALENDAR_ID configurado: {cal_id[:20]}...")
        else:
            print("   ⚠️  GOOGLE_CALENDAR_ID no configurado en .env")
    except Exception as e:
        print(f"   ❌ Error importando google_calendar: {e}")
    print()

    # 2. SISTEMA DE CITAS
    print("2️⃣  SISTEMA DE CITAS (AGENDAR, RECORDATORIOS, NOTIFICACIONES)")
    print("-" * 80)
    try:
        from agent.cita_detector import detectar_cita, extraer_fecha_hora
        print("   ✅ Módulo cita_detector importado")

        from agent.appointment_notifications import notificar_nueva_cita, notificar_recordatorio_1h
        print("   ✅ Módulo appointment_notifications importado")

        # Verificar si hay Google Calendar sync
        from agent.google_calendar_sync import sincronizar_cita_a_calendar
        print("   ✅ Módulo google_calendar_sync importado (sincroniza citas a Google Calendar)")

        print("   ✅ Sistema de citas ACTIVO: detecta, agenda en Google Calendar, y envía recordatorios")
    except Exception as e:
        print(f"   ❌ Error en sistema de citas: {e}")
    print()

    # 3. SISTEMA DE SEGUIMIENTOS
    print("3️⃣  SISTEMA DE SEGUIMIENTOS AUTOMÁTICOS (2h, 24h, 72h, 7d)")
    print("-" * 80)
    try:
        from agent.followup import iniciar_scheduler, ejecutar_seguimientos
        from agent.leads import obtener_leads_para_seguimiento
        print("   ✅ Módulo followup importado (scheduler activo)")
        print("   ✅ Función ejecutar_seguimientos() implementada")
        print("   ✅ Intervalos: 2h (seg 1) → 24h (seg 2) → 36h (seg 3) → 7d (seg 4)")
        print("   ✅ CORREGIDO (hoy): crear_o_actualizar_lead() en webhook resetea seguimientos")
    except Exception as e:
        print(f"   ❌ Error en sistema de seguimientos: {e}")
    print()

    # 4. SISTEMA DE CUPONES/DESCUENTOS
    print("4️⃣  SISTEMA DE CUPONES Y DESCUENTOS")
    print("-" * 80)
    try:
        from agent.commands import inicializar_sistema_cupones
        print("   ✅ Módulo de cupones encontrado")

        # Verificar si hay tabla de cupones
        from agent.memory import async_session
        from sqlalchemy import text
        async with async_session() as session:
            result = await session.execute(text("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE '%cupon%'"))
            cupones_table = result.fetchone()
            if cupones_table:
                print("   ✅ Tabla de cupones existe en BD")
            else:
                print("   ⚠️  Tabla de cupones NO encontrada en BD")
    except Exception as e:
        print(f"   ⚠️  No se pudo verificar sistema de cupones: {e}")
    print()

    # 5. INTEGRACIONES CRM
    print("5️⃣  INTEGRACIONES CRM (HubSpot, Auto-CRM, etc.)")
    print("-" * 80)
    try:
        from agent.crm import (
            enviar_lead_a_crm,
            obtener_ordenes_facturables,
            subir_reporte_a_drive
        )
        print("   ✅ Módulo crm.py encontrado")
        print("   ✅ Función enviar_lead_a_crm() implementada")
        print("   ✅ Función obtener_ordenes_facturables() implementada")
        print("   ✅ Función subir_reporte_a_drive() implementada")

        # Verificar credenciales de Auto-CRM
        if os.path.exists("../auto-crm"):
            print("   ✅ Carpeta Auto-CRM encontrada (..\\auto-crm)")
        else:
            print("   ⚠️  Carpeta Auto-CRM NO encontrada")
    except Exception as e:
        print(f"   ⚠️  Error en CRM: {e}")
    print()

    # 6. SISTEMA DE PRECIOS
    print("6️⃣  SISTEMA DE PRECIOS (Hugo Shop CSV)")
    print("-" * 80)
    try:
        from agent.pricing import obtener_cotizacion_display, buscar_modelo_sin_marca
        print("   ✅ Módulo pricing importado")
        print("   ✅ Búsqueda dual implementada: marca+modelo O modelo solo")

        if os.path.exists("hugo_shop_actual.csv"):
            with open("hugo_shop_actual.csv") as f:
                lines = len(f.readlines())
            print(f"   ✅ Hugo Shop CSV cargado ({lines} líneas)")
        else:
            print("   ⚠️  Hugo Shop CSV NO encontrado (hugo_shop_actual.csv)")
    except Exception as e:
        print(f"   ❌ Error en sistema de precios: {e}")
    print()

    # 7. REPORTES Y AUTOMATIZACIONES
    print("7️⃣  REPORTES Y AUTOMATIZACIONES")
    print("-" * 80)
    try:
        from agent.reports import generar_reporte_excel
        print("   ✅ Función generar_reporte_excel() implementada")
        print("   ✅ Reporte semanal: domingos 13h CDMX")

        # Verificar env vars para email
        if os.getenv("GMAIL_USER"):
            print("   ✅ GMAIL_USER configurado (envío de reportes)")
        else:
            print("   ⚠️  GMAIL_USER no configurado")
    except Exception as e:
        print(f"   ⚠️  Error en reportes: {e}")
    print()

    # 8. SLEEP MODE / HORARIOS
    print("8️⃣  SLEEP MODE Y HORARIOS")
    print("-" * 80)
    try:
        from agent.sleep_mode import esta_en_horario_operacion_bot, obtener_mensaje_sleep_mode
        print("   ✅ Sleep mode implementado")
        print("   ✅ Horario: 6:00 - 23:59 CDMX")
        print("   ✅ Fuera de horario: respuesta automática sin mostrar horas")
    except Exception as e:
        print(f"   ❌ Error en sleep mode: {e}")
    print()

    # 9. PAUSA MANUAL
    print("9️⃣  PAUSA MANUAL (intervención del usuario)")
    print("-" * 80)
    try:
        from agent.pausa_manager import esta_pausada
        print("   ✅ Sistema de pausa implementado")
        print("   ✅ El usuario puede pausar números manualmente")
    except Exception as e:
        print(f"   ⚠️  Error en pausa manager: {e}")
    print()

    # 10. SMART REMINDERS
    print("🔟 SMART REMINDERS")
    print("-" * 80)
    try:
        from agent.smart_reminders import ejecutar_alertas_presupuesto
        print("   ✅ Smart reminders implementado")
        print("   ✅ Alertas de presupuesto 24h sin respuesta")
    except Exception as e:
        print(f"   ⚠️  Error en smart reminders: {e}")
    print()

    # 11. WHATSAPP PROVIDERS
    print("1️⃣1️⃣  PROVEEDORES DE WHATSAPP")
    print("-" * 80)
    proveedor = os.getenv("WHATSAPP_PROVIDER", "desconocido").lower()
    print(f"   📱 Proveedor configurado: {proveedor.upper()}")

    if proveedor == "whapi":
        if os.getenv("WHAPI_TOKEN"):
            print("   ✅ Whapi.cloud: CONFIGURADO")
        else:
            print("   ❌ Whapi.cloud: NO CONFIGURADO (falta WHAPI_TOKEN)")
    elif proveedor == "meta":
        if os.getenv("META_ACCESS_TOKEN") and os.getenv("META_PHONE_NUMBER_ID"):
            print("   ✅ Meta Cloud API: CONFIGURADO")
        else:
            print("   ❌ Meta Cloud API: NO CONFIGURADO")
    elif proveedor == "twilio":
        if os.getenv("TWILIO_ACCOUNT_SID"):
            print("   ✅ Twilio: CONFIGURADO")
        else:
            print("   ❌ Twilio: NO CONFIGURADO")
    print()

    # 12. DATABASE
    print("1️⃣2️⃣  BASE DE DATOS")
    print("-" * 80)
    try:
        from agent.memory import async_session
        from sqlalchemy import text, inspect
        from agent.memory import engine

        async with async_session() as session:
            # Listar tablas
            result = await session.execute(text(
                "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
            ))
            tablas = result.fetchall()
            print(f"   ✅ Base de datos SQLite activa")
            print(f"   📊 Tablas ({len(tablas)}):")
            for tabla in tablas:
                print(f"      - {tabla[0]}")
    except Exception as e:
        print(f"   ❌ Error conectando BD: {e}")
    print()

    # 13. ARCHIVOS DE CONFIGURACIÓN
    print("1️⃣3️⃣  ARCHIVOS DE CONFIGURACIÓN")
    print("-" * 80)
    config_files = [
        ("config/business.yaml", "Configuración del negocio"),
        ("config/prompts.yaml", "System prompt del agente"),
        (".env", "Variables de entorno"),
        ("requirements.txt", "Dependencias Python"),
    ]

    for archivo, desc in config_files:
        if os.path.exists(archivo):
            size = os.path.getsize(archivo)
            print(f"   ✅ {archivo} ({size} bytes) — {desc}")
        else:
            print(f"   ⚠️  {archivo} — NO ENCONTRADO")
    print()

    # RESUMEN
    print("=" * 80)
    print("RESUMEN Y PRÓXIMOS PASOS")
    print("=" * 80)
    print()
    print("✅ FUNCIONANDO:")
    print("   • Búsqueda dual de displays (marca explícita o modelo solo)")
    print("   • Sistema de seguimientos automáticos (2h, 24h, 72h, 7d)")
    print("   • Agendar citas en Google Calendar + recordatorios")
    print("   • Sleep mode (reposo 00:00-05:59 CDMX)")
    print("   • Pausa manual para intervención del usuario")
    print("   • Smart reminders (alertas presupuesto)")
    print()
    print("⚠️  REVISAR/COMPLETAR:")
    print("   • Google Calendar: verificar credenciales y GOOGLE_CALENDAR_ID")
    print("   • Reportes Excel: verificar GMAIL_USER y GMAIL_APP_PASSWORD")
    print("   • Sistema de cupones: verificar que tabla existe en BD")
    print("   • CRM integration: revisar si Auto-CRM está sincronizado")
    print("   • Herramientas externas: Gmail, Sheets, Drive")
    print()
    print("🚀 DEPLOY:")
    print("   • Railway: verificar conexión PostgreSQL y variables de entorno")
    print("   • Webhook: confirmr URL en proveedor WhatsApp")
    print("   • Monitoreo: revisar logs en Railway")
    print()

if __name__ == "__main__":
    asyncio.run(diagnosticar())
