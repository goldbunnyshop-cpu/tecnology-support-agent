#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script para corregir la función _extraer_campos_cita en agent/main.py
El problema es que los patrones de extracción usan emojis específicos que
tienen problemas de encoding cuando vienen desde JSON.

Solución: Usar patrones flexibles que no dependan de emojis específicos.
"""

import re

def fix_extraer_campos():
    """Reemplaza la función _extraer_campos_cita con una versión corregida."""

    filepath = "agent/main.py"

    with open(filepath, "r", encoding="utf-8") as f:
        contenido = f.read()

    # Encontrar la función actual (delimitada por la siguiente función o EOF)
    patron_inicio = r"def _extraer_campos_cita\(mensaje: str\) -> dict \| None:"
    match_inicio = re.search(patron_inicio, contenido)

    if not match_inicio:
        print("ERROR: No se encontró la función _extraer_campos_cita")
        return False

    inicio = match_inicio.start()
    print(f"✅ Función encontrada en posición {inicio}")

    # Encontrar el inicio de la siguiente función
    resto = contenido[match_inicio.end():]
    match_siguiente = re.search(r"\ndef |^\nasync def ", resto, re.MULTILINE)

    if match_siguiente:
        fin = match_inicio.end() + match_siguiente.start()
    else:
        fin = len(contenido)

    print(f"Función ocupa de {inicio} a {fin}")

    # Nueva función (version corregida)
    nueva_funcion = '''def _extraer_campos_cita(mensaje: str) -> dict | None:
    """
    Extrae campos de un mensaje "NUEVA CITA AGENDADA".
    Retorna dict con: nombre, dispositivo, problema, cuando, asesor
    O None si falla el parseo.

    Formato esperado (patrones flexibles):
    NUEVA CITA AGENDADA
    {nombre} | {dispositivo}
    {cuando} | {problema}
    Asesor: {asesor}
    """
    try:
        # Líneas del mensaje
        lineas = mensaje.strip().split('\\n')
        if len(lineas) < 4:
            logger.warning(f"[IMPORT] Mensaje sin suficientes líneas: {len(lineas)}")
            return None

        # Línea 2: nombre y dispositivo (patrón flexible sin emojis)
        patron_linea2 = r"(.+?)\\s*\\|\\s*(.+?)$"
        match_linea2 = re.search(patron_linea2, lineas[1])
        if not match_linea2:
            logger.warning(f"[IMPORT] No se extrajo nombre/dispositivo de: {lineas[1]}")
            return None
        nombre = match_linea2.group(1).strip()
        dispositivo = match_linea2.group(2).strip()

        # Línea 3: cuando y problema (patrón flexible sin emojis)
        patron_linea3 = r"(.+?)\\s*\\|\\s*(.+?)$"
        match_linea3 = re.search(patron_linea3, lineas[2])
        if not match_linea3:
            logger.warning(f"[IMPORT] No se extrajo cuando/problema de: {lineas[2]}")
            return None
        cuando = match_linea3.group(1).strip()
        problema = match_linea3.group(2).strip()

        # Línea 4: asesor (patrón flexible)
        patron_linea4 = r"(?:Asesor:\\s*)?(.+?)$"
        match_linea4 = re.search(patron_linea4, lineas[3])
        asesor = match_linea4.group(1).strip() if match_linea4 else ""

        return {
            "nombre": nombre,
            "dispositivo": dispositivo,
            "problema": problema,
            "cuando": cuando,
            "asesor": asesor,
        }

    except Exception as e:
        logger.error(f"[IMPORT] Error extrayendo campos de cita: {e}")
        return None

'''

    # Reemplazar
    nuevo_contenido = contenido[:inicio] + nueva_funcion + contenido[fin:]

    # Escribir de vuelta
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(nuevo_contenido)

    print("✅ Función reemplazada exitosamente")
    return True

if __name__ == "__main__":
    if fix_extraer_campos():
        print("\n✅ Corrección completada")
    else:
        print("\n❌ Error al corregir")
        exit(1)
