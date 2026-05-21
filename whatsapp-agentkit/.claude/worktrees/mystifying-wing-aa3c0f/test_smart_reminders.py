#!/usr/bin/env python3
"""
Test interactivo de Smart Reminders
════════════════════════════════════

Ejecutar:
    python test_smart_reminders.py

Esto prueba la LÓGICA sin necesidad de proveedor real.
"""

import sys
from datetime import datetime, timedelta
from agent.smart_reminders import ReminderSchedule


def print_header(texto):
    """Print formateado."""
    print(f"\n{'='*70}")
    print(f"  {texto}")
    print(f"{'='*70}\n")


def print_resultado(numero, titulo, fecha_cita, hora_cita, dias_futuro):
    """Ejecuta un test y muestra resultado."""
    print(f"📌 TEST {numero}: {titulo}")
    print(f"   Cita: {fecha_cita} a las {hora_cita} ({dias_futuro} día/s)")
    print("-" * 70)

    ahora = datetime.now()
    schedule = ReminderSchedule(fecha_cita, hora_cita, ahora)
    plan = schedule.obtener_schedule_reminders()

    print(plan["resumen"])

    print(f"\n   📅 Ahora: {ahora.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"   ⏰ Cita: {plan['cita_datetime'].strftime('%Y-%m-%d %H:%M:%S')}")

    print("\n   Detalles de cada recordatorio:")
    for r in plan["recordatorios"]:
        estado = "✅ ENVIAR" if r["enviar"] else "⏭️ SALTAR"
        print(f"      {r['tipo']:<10} → {estado:<15} @ {r['datetime'].strftime('%Y-%m-%d %H:%M:%S')}")

    print()


def main():
    print_header("🧪 Smart Reminders — Test de Lógica")

    ahora = datetime.now()

    # TEST 1: Cita mañana
    manana = (ahora + timedelta(days=1)).strftime("%Y-%m-%d")
    print_resultado(
        1,
        "Cita MAÑANA (confirma hoy)",
        manana,
        "15:00",
        1
    )

    input("Press Enter para siguiente test...")

    # TEST 2: Cita en 2 días
    en_2_dias = (ahora + timedelta(days=2)).strftime("%Y-%m-%d")
    print_resultado(
        2,
        "Cita en 2 DÍAS (confirma hoy)",
        en_2_dias,
        "10:00",
        2
    )

    input("Press Enter para siguiente test...")

    # TEST 3: Cita en 5 días
    en_5_dias = (ahora + timedelta(days=5)).strftime("%Y-%m-%d")
    print_resultado(
        3,
        "Cita en 5 DÍAS (confirma hoy)",
        en_5_dias,
        "14:30",
        5
    )

    input("Press Enter para siguiente test...")

    # TEST 4: Cita en 1 semana
    en_1_semana = (ahora + timedelta(days=7)).strftime("%Y-%m-%d")
    print_resultado(
        4,
        "Cita en 1 SEMANA (confirma hoy)",
        en_1_semana,
        "09:00",
        7
    )

    print_header("✅ Resumen")

    print("""
INTERPRETACIÓN DE LOS RESULTADOS:

✅ ENVIAR     = El recordatorio será programado y enviado
⏭️ SALTAR     = El recordatorio será omitido (no aplica)

REGLAS IMPLEMENTADAS:

1️⃣  24 HORAS ANTES:
    • ✅ ENVIAR si cita está 2+ días en el futuro
    • ⏭️ SALTAR si cita es mañana o más cercana

2️⃣  90 MINUTOS ANTES:
    • ✅ SIEMPRE se envía (excepto si su hora ya pasó)
    • Útil incluso si la cita es en 1-2 días

3️⃣  10 MINUTOS ANTES:
    • ✅ SIEMPRE se envía (excepto si su hora ya pasó)
    • El recordatorio final más cercano

CASOS TÍPICOS:

Hoy domingo → Cita lunes
├─ 24h antes: ⏭️ SALTAR (cita dentro de < 24h)
├─ 90min antes: ✅ ENVIAR
└─ 10min antes: ✅ ENVIAR

Hoy domingo → Cita martes
├─ 24h antes: ✅ ENVIAR (lunes a las misma hora)
├─ 90min antes: ✅ ENVIAR
└─ 10min antes: ✅ ENVIAR

Hoy domingo → Cita sábado próximo (7 días)
├─ 24h antes: ✅ ENVIAR (viernes a las misma hora)
├─ 90min antes: ✅ ENVIAR
└─ 10min antes: ✅ ENVIAR
    """)

    print_header("🚀 Próximos pasos")

    print("""
1. Verificar que la lógica es correcta ✓

2. Instalar APScheduler:
   pip install apscheduler

3. Integrar en tu código:
   - Actualizar agent/main.py (inicializar scheduler)
   - Actualizar agent/cita_detector.py (llamar manejar_cita_confirmada)
   - Ver INTEGRACION_SMART_REMINDERS.md para detalles

4. Deploy a Railway:
   - requirements.txt ya tiene apscheduler
   - Push a GitHub
   - Railway redeploy automático

¿Preguntas? Revisa INTEGRACION_SMART_REMINDERS.md
    """)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n👋 Test finalizado")
        sys.exit(0)
