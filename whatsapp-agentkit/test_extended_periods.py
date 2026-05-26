#!/usr/bin/env python3
"""
Test Extended — Validar que la lógica aplica para TODOS los períodos
═══════════════════════════════════════════════════════════════════════

Prueba: 4 días, 1 semana, 1 mes, etc.
"""

from datetime import datetime, timedelta
from agent.smart_reminders import ReminderSchedule


def test_periodo(dias, nombre):
    """Test un período específico."""
    print(f"\n{'='*70}")
    print(f"  TEST: Cita en {dias} DÍA(S) — {nombre}")
    print(f"{'='*70}\n")

    ahora = datetime.now()
    fecha_cita = (ahora + timedelta(days=dias)).strftime("%Y-%m-%d")

    schedule = ReminderSchedule(fecha_cita, "15:00", ahora)
    plan = schedule.obtener_schedule_reminders()

    # Mostrar resumen
    print(plan["resumen"])

    # Detalles
    print("\n  Detalles:")
    for r in plan["recordatorios"]:
        estado = "✅ ENVIAR" if r["enviar"] else "⏭️ SALTAR"
        print(f"    {r['tipo']:<10} → {estado:<15} @ {r['datetime'].strftime('%Y-%m-%d %H:%M')}")

    # Validar lógica
    print("\n  Validación:")
    tiene_24h = [r for r in plan["recordatorios"] if r["tipo"] == "24h" and r["enviar"]]
    tiene_90min = [r for r in plan["recordatorios"] if r["tipo"] == "90min" and r["enviar"]]
    tiene_10min = [r for r in plan["recordatorios"] if r["tipo"] == "10min" and r["enviar"]]

    # Regla: si > 24h debe enviar 24h (más de un día)
    # Nota: Exactamente 1 día puede ser < 24h si la hora es anterior a la actual
    if dias > 1:  # Más de 1 día = más de 24 horas
        assert len(tiene_24h) > 0, f"❌ FALLA: Cita en {dias} días debería enviar 24h"
        print(f"    ✅ 24h before: Enviado (correcto para {dias}+ días)")
    else:
        # 0.5 o 1 día pueden ser < 24h dependiendo de la hora actual
        estado_24h = "⏭️ Saltado" if len(tiene_24h) == 0 else "✅ Enviado"
        print(f"    {estado_24h} 24h before (< 24h desde ahora, {dias} día/s)")

    # Siempre debe enviar 90min y 10min (si no pasó)
    assert len(tiene_90min) > 0, f"❌ FALLA: 90min no se envió para {dias} días"
    assert len(tiene_10min) > 0, f"❌ FALLA: 10min no se envió para {dias} días"
    print(f"    ✅ 90min before: Enviado ✓")
    print(f"    ✅ 10min before: Enviado ✓")

    return True


def main():
    print("\n" + "="*70)
    print("  TEST EXTENDIDO — Múltiples períodos")
    print("="*70)

    casos = [
        (0.5, "HOY (en 12 horas)"),
        (1, "MAÑANA (1 día)"),
        (2, "Pasado mañana (2 días)"),
        (3, "En 3 días"),
        (4, "En 4 días"),
        (7, "En 1 SEMANA"),
        (14, "En 2 SEMANAS"),
        (30, "En 1 MES"),
        (60, "En 2 MESES"),
        (90, "En 3 MESES"),
    ]

    resultados = []

    for dias, nombre in casos:
        try:
            test_periodo(dias, nombre)
            resultados.append((nombre, "✅ PASS"))
        except AssertionError as e:
            print(f"\n  ❌ FALLO: {e}")
            resultados.append((nombre, "❌ FAIL"))

    # Resumen final
    print(f"\n{'='*70}")
    print("  RESUMEN FINAL")
    print(f"{'='*70}\n")

    for nombre, estado in resultados:
        print(f"  {estado}  {nombre}")

    total_pass = sum(1 for _, estado in resultados if "✅" in estado)
    total = len(resultados)

    print(f"\n  Total: {total_pass}/{total} tests pasados\n")

    if total_pass == total:
        print("  ✅ CONCLUSIÓN: La lógica aplica para TODOS los períodos")
        print("  La estructura es genérica basada en timedelta()")
        print("  Funciona igual para: 1 día, 4 días, 1 semana, 1 mes, etc.")
        return True
    else:
        print("  ❌ Algunos tests fallaron")
        return False


if __name__ == "__main__":
    import sys
    success = main()
    sys.exit(0 if success else 1)
