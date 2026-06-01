#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test completo del proceso de importación de citas
Verifica que:
1. Los mensajes se parsean correctamente
2. Los campos se extraen correctamente
3. Las fechas se parsean correctamente
"""

import re
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

# Configuración de zona horaria
ZONA_CDMX = ZoneInfo("America/Mexico_City")

# Meses en español
MESES_ES = {
    1: "enero", 2: "febrero", 3: "marzo", 4: "abril",
    5: "mayo", 6: "junio", 7: "julio", 8: "agosto",
    9: "septiembre", 10: "octubre", 11: "noviembre", 12: "diciembre"
}

def parsear_fecha_hora(fecha_str: str) -> datetime | None:
    """Parsea una fecha como 'Sábado 9 de mayo, 11:30 a.m.'"""
    if not fecha_str:
        return None

    try:
        fecha_str = fecha_str.strip()
        meses_inversos = {v: k for k, v in MESES_ES.items()}

        # NUEVO PATRÓN FLEXIBLE (sin emojis específicos)
        patron = r"(\w+)\s+(\d{1,2})\s+de\s+(\w+),\s+(\d{1,2}):(\d{2})\s+(a\.m\.|p\.m\.|am|pm)"
        match = re.search(patron, fecha_str)

        if not match:
            print(f"  ❌ No se pudo parsear: {fecha_str}")
            return None

        dia_nombre, dia_num, mes_nombre, hora_str, min_str, ampm = match.groups()

        mes_num = meses_inversos.get(mes_nombre.lower())
        if not mes_num:
            print(f"  ❌ Mes no reconocido: {mes_nombre}")
            return None

        hora = int(hora_str)
        minuto = int(min_str)
        if ampm.lower() in ("pm", "p.m.") and hora != 12:
            hora += 12
        elif ampm.lower() in ("am", "a.m.") and hora == 12:
            hora = 0

        ahora = datetime.now(ZONA_CDMX)
        año = ahora.year

        try:
            fecha = datetime(año, mes_num, int(dia_num), hora, minuto, 0, tzinfo=ZONA_CDMX)
            if fecha < ahora:
                fecha = datetime(año - 1, mes_num, int(dia_num), hora, minuto, 0, tzinfo=ZONA_CDMX)
            return fecha
        except ValueError as e:
            print(f"  ❌ Error creando datetime: {e}")
            return None

    except Exception as e:
        print(f"  ❌ Error: {e}")
        return None


def extraer_campos_cita(mensaje: str) -> dict | None:
    """Extrae campos de un mensaje usando PATRONES FLEXIBLES (sin emojis)"""
    try:
        lineas = mensaje.strip().split('\n')
        if len(lineas) < 4:
            print(f"  ❌ Mensaje sin suficientes líneas")
            return None

        # Línea 2: nombre y dispositivo
        match_linea2 = re.search(r"(.+?)\s*\|\s*(.+?)$", lineas[1])
        if not match_linea2:
            print(f"  ❌ No se extrajo nombre/dispositivo")
            return None
        nombre = match_linea2.group(1).strip()
        dispositivo = match_linea2.group(2).strip()

        # Línea 3: cuando y problema
        match_linea3 = re.search(r"(.+?)\s*\|\s*(.+?)$", lineas[2])
        if not match_linea3:
            print(f"  ❌ No se extrajo cuando/problema")
            return None
        cuando = match_linea3.group(1).strip()
        problema = match_linea3.group(2).strip()

        # Línea 4: asesor
        match_linea4 = re.search(r"(?:Asesor:\s*)?(.+?)$", lineas[3])
        asesor = match_linea4.group(1).strip() if match_linea4 else ""

        return {
            "nombre": nombre,
            "dispositivo": dispositivo,
            "problema": problema,
            "cuando": cuando,
            "asesor": asesor,
        }

    except Exception as e:
        print(f"  ❌ Error: {e}")
        return None


# Datos de prueba (sin emojis, solo texto limpio)
MENSAJES_PRUEBA = [
    """NUEVA CITA AGENDADA
Jose Luis Gil Miranda | PS5
Sábado 9 de mayo, 11:30 a.m. | Sobrecalentamiento, se apaga sola
Asesor: Sofia""",

    """NUEVA CITA AGENDADA
Andrés | PS5
Sábado 16 de mayo, 11:00 a.m. | Consola se apaga después de 30 minutos
Asesor: Valentina""",

    """NUEVA CITA AGENDADA
Emmanuel | PS5
Sábado 9 de mayo, 12:00 p.m. | Puerto HDMI con falso contacto
Asesor: Camila""",

    """NUEVA CITA AGENDADA
Francisco González | PS3
Jueves 14 de mayo, 7:30 p.m. | Charola no jala los discos
Asesor: Sofia""",
]

print("=" * 70)
print("TEST DE IMPORTACIÓN DE CITAS")
print("=" * 70)
print()

exitosas = 0
fallidas = 0

for i, mensaje in enumerate(MENSAJES_PRUEBA, 1):
    print(f"📋 Mensaje {i}:")

    # Extraer campos
    campos = extraer_campos_cita(mensaje)
    if not campos:
        print(f"  ❌ FALLO EN EXTRACCIÓN\n")
        fallidas += 1
        continue

    print(f"  ✅ Campos extraídos:")
    print(f"     Nombre: {campos['nombre']}")
    print(f"     Dispositivo: {campos['dispositivo']}")
    print(f"     Cuando: {campos['cuando']}")
    print(f"     Problema: {campos['problema']}")
    print(f"     Asesor: {campos['asesor']}")

    # Parsear fecha
    fecha = parsear_fecha_hora(campos['cuando'])
    if fecha:
        print(f"  ✅ Fecha parseada: {fecha.isoformat()}")
        exitosas += 1
    else:
        print(f"  ❌ FALLO EN PARSEO DE FECHA")
        fallidas += 1

    print()

print("=" * 70)
print(f"RESULTADO: {exitosas} exitosas, {fallidas} fallidas")
print("=" * 70)

if fallidas == 0:
    print("\n✅ ¡TODOS LOS TESTS PASARON!")
    print("La solución está lista para usar en Railway.")
else:
    print(f"\n❌ {fallidas} test(s) fallaron")
