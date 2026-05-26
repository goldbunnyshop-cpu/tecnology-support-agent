#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test directo para debugging del regex de fechas
"""

import re

# Ejemplos reales de las citas que necesitas parsear
FECHAS_TEST = [
    "Sábado 9 de mayo, 11:30 a.m.",
    "Sábado 16 de mayo, 11:00 a.m.",
    "Sábado 9 de mayo, 12:00 p.m.",
    "Jueves 14 de mayo, 7:30 p.m.",
    "Miércoles 13 de mayo, 10:30 a.m.",
    "Viernes 15 de mayo, 5:00 p.m.",
    "Domingo 17 de mayo, 12:00 p.m.",
]

# Los patrones que se han probado
PATRONES = {
    "original": r"(\w+)\s+(\d{1,2})\s+de\s+(\w+),\s+(\d{1,2}):(\d{2})\s*(am|pm|AM|PM)",
    "intento_1": r"([a-záéíóúñ]+)\s+(\d{1,2})\s+de\s+([a-záéíóúñ]+),\s+(\d{1,2}):(\d{2})\s*(am|pm|AM|PM)",
    "intento_2": r"([a-záéíóúñ]+)\s+(\d{1,2})\s+de\s+([a-záéíóúñ]+),\s+(\d{1,2}):(\d{2})\s*(a\.m\.|p\.m\.|am|pm|AM|PM)",
    "intento_3": r"([^\d]+?)\s+(\d{1,2})\s+de\s+([^\d,]+?),\s+(\d{1,2}):(\d{2})\s*(a\.m\.|p\.m\.|am|pm|AM|PM)",
    "nuevo_1": r"(\D+?)\s+(\d{1,2})\s+de\s+(\D+?),\s+(\d{1,2}):(\d{2})\s*(a\.m\.|p\.m\.|am|pm|a\.m|p\.m|AM|PM|a|p)",
    "nuevo_2": r"^(\w+)\s+(\d{1,2})\s+de\s+(\w+),\s+(\d{1,2}):(\d{2})\s+(a\.m\.|p\.m\.|am|pm)$",
}

print("=" * 70)
print("TEST DE REGEX PARA PARSING DE FECHAS")
print("=" * 70)
print()

for nombre_patron, patron in PATRONES.items():
    print(f"\n📋 Patrón: {nombre_patron}")
    print(f"   {patron}")
    print("   " + "-" * 65)

    matches_totales = 0
    for fecha in FECHAS_TEST:
        try:
            match = re.search(patron, fecha)
            if match:
                matches_totales += 1
                grupos = match.groups()
                print(f"   ✅ '{fecha}'")
                print(f"      → Grupos: {grupos}")
            else:
                print(f"   ❌ '{fecha}' — NO COINCIDE")
        except Exception as e:
            print(f"   ⚠️  '{fecha}' — ERROR: {e}")

    print(f"\n   📊 Resultado: {matches_totales}/{len(FECHAS_TEST)} coinciden")
    print()

# Test adicional: probar con la cadena exacta extraída de un mensaje
print("\n" + "=" * 70)
print("TEST CON FORMATO EXACTO DE MENSAJE COMPLETO")
print("=" * 70)

MENSAJE_COMPLETO = "🔔 *NUEVA CITA AGENDADA*\n👤 Jose Luis Gil Miranda | 📱 PS5\n⏰ Sábado 9 de mayo, 11:30 a.m. | ⚠️ Sobrecalentamiento, se apaga sola\n👨‍💼 Asesor: Sofia"

# Extraer solo la parte de la fecha del mensaje
patron_extraer_fecha = r"⏰\s+([^|]+)\s*\|"
match_fecha = re.search(patron_extraer_fecha, MENSAJE_COMPLETO)

if match_fecha:
    fecha_extraida = match_fecha.group(1).strip()
    print(f"\n✅ Fecha extraída del mensaje: '{fecha_extraida}'")
    print()

    # Probar los patrones sobre la fecha extraída
    for nombre, patron in PATRONES.items():
        match = re.search(patron, fecha_extraida)
        if match:
            print(f"✅ {nombre}: {match.groups()}")
        else:
            print(f"❌ {nombre}: NO COINCIDE")
else:
    print("❌ No se pudo extraer la fecha del mensaje")

print("\n" + "=" * 70)
