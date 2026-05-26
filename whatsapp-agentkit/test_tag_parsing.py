#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test script para verificar que el parsing de tags funciona correctamente.
"""

import re
from datetime import datetime
from zoneinfo import ZoneInfo

ZONA_CDMX = ZoneInfo("America/Mexico_City")


def parsear_tag_agendar(texto: str):
    """
    Extrae el tag [[AGENDAR:...]] de la respuesta de Claude.
    """
    patron = r"\[\[AGENDAR:([^\]]+)\]\]"
    match = re.search(patron, texto)

    if not match:
        return None

    contenido = match.group(1)
    datos = {}

    for campo in contenido.split("|"):
        if "=" in campo:
            clave, valor = campo.split("=", 1)
            datos[clave.strip()] = valor.strip()

    # Validar que tenga los campos mínimos
    if not all(k in datos for k in ["nombre", "dispositivo", "problema", "fecha", "hora"]):
        print(f"❌ Faltan campos. Tengo: {list(datos.keys())}")
        return None

    return datos


def quitar_tags(texto: str) -> str:
    """Remueve los tags [[AGENDAR:...]] de la respuesta."""
    return re.sub(r"\[\[AGENDAR:[^\]]+\]\]", "", texto).strip()


# Test 1: Parsing del tag
print("=" * 70)
print("TEST 1: Parsing del tag [[AGENDAR:...]]")
print("=" * 70)

respuesta_con_tag = """¡Listo, Mario! Para hoy tengo disponible las *6:00 PM* 😊

¿Confirmamos esa hora para el mantenimiento de tu PS4?

[[AGENDAR:nombre=Mario|telefono=5215533135109|dispositivo=PS4|problema=Mantenimiento|fecha=2026-05-15|hora=18:00]]"""

print(f"\nRespuesta con tag:\n{respuesta_con_tag}\n")

tag = parsear_tag_agendar(respuesta_con_tag)

if tag:
    print("✅ Tag parseado exitosamente:")
    for clave, valor in tag.items():
        print(f"   {clave}: {valor}")

    # Test 2: Limpiar tags de la respuesta
    print("\n" + "=" * 70)
    print("TEST 2: Limpiar tags de la respuesta")
    print("=" * 70)

    respuesta_limpia = quitar_tags(respuesta_con_tag)
    print(f"\nRespuesta limpia:\n{respuesta_limpia}\n")

    # Test 3: Parsear fecha y hora
    print("=" * 70)
    print("TEST 3: Parsear fecha y hora")
    print("=" * 70)

    try:
        fh = datetime.strptime(
            f"{tag['fecha']} {tag['hora']}", "%Y-%m-%d %H:%M"
        ).replace(tzinfo=ZONA_CDMX)

        print(f"✅ Fecha y hora parseadas:")
        print(f"   fecha_hora: {fh}")
        print(f"   strftime: {fh.strftime('%A %d de %B, %H:%M')}")

    except Exception as e:
        print(f"❌ Error parseando fecha: {e}")

else:
    print("❌ No se pudo parsear el tag")


# Test 4: Validación de campos faltantes
print("\n" + "=" * 70)
print("TEST 4: Validación de campos faltantes")
print("=" * 70)

respuesta_incompleta = """Entendido, voy a agendar tu cita.

[[AGENDAR:nombre=Mario|dispositivo=PS4]]"""

print(f"\nRespuesta incompleta:\n{respuesta_incompleta}\n")

tag2 = parsear_tag_agendar(respuesta_incompleta)

if tag2:
    print("✅ Tag parseado (esto no debería suceder)")
else:
    print("✅ Validación correcta: tag rechazado por campos incompletos")

print("\n" + "=" * 70)
print("✅ Todos los tests completados")
print("=" * 70)
