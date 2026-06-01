#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script para importar citas de forma DIRECTA (sin HTTP).
Usa las mismas funciones de parsing que agent/main.py
y guarda directamente en Google Calendar.
"""

import asyncio
import logging
import re
from datetime import datetime
from zoneinfo import ZoneInfo
from dotenv import load_dotenv

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("import-local")

load_dotenv()

# Importar funciones del agente
from agent.google_calendar import (
    agendar_cita,
    DIAS_ES,
    MESES_ES,
)

ZONA_CDMX = ZoneInfo("America/Mexico_City")

CITAS = [
    "🔔 *NUEVA CITA AGENDADA*\n👤 Jose Luis Gil Miranda | 📱 PS5\n⏰ Sábado 9 de mayo, 11:30 a.m. | ⚠️ Sobrecalentamiento, se apaga sola\n👨‍💼 Asesor: Sofia",
    "🔔 *NUEVA CITA AGENDADA*\n👤 Andrés | 📱 PS5\n⏰ Sábado 16 de mayo, 11:00 a.m. | ⚠️ Consola se apaga después de 30 minutos\n👨‍💼 Asesor: Valentina",
    "🔔 *NUEVA CITA AGENDADA*\n👤 Emmanuel | 📱 PS5\n⏰ Sábado 9 de mayo, 12:00 p.m. | ⚠️ Puerto HDMI con falso contacto\n👨‍💼 Asesor: Camila",
    "🔔 *NUEVA CITA AGENDADA*\n👤 Francisco González | 📱 PS3\n⏰ Jueves 14 de mayo, 7:30 p.m. | ⚠️ Charola no jala los discos\n👨‍💼 Asesor: Sofia",
    "🔔 *NUEVA CITA AGENDADA*\n👤 Gonz | 📱 Xbox Series S\n⏰ Sábado 9 de mayo, 12:30 p.m. | ⚠️ Mantenimiento por sobrecalentamiento\n👨‍💼 Asesor: Sofia",
    "🔔 *NUEVA CITA AGENDADA*\n👤 Augusto | 📱 PS4\n⏰ Sábado 9 de mayo, 5:30 p.m. | ⚠️ Mantenimiento\n👨‍💼 Asesor: Valentina",
    "🔔 *NUEVA CITA AGENDADA*\n👤 Raul Del Prado Flores | 📱 Xbox Series X\n⏰ Sábado 16 de mayo, 11:30 a.m. | ⚠️ Mantenimiento\n👨‍💼 Asesor: Valentina",
    "🔔 *NUEVA CITA AGENDADA*\n👤 José Antonio | 📱 PS5 con lector de discos\n⏰ Sábado 16 de mayo, 1:30 p.m. | ⚠️ Bandeja de discos dañada\n👨‍💼 Asesor: Valentina",
    "🔔 *NUEVA CITA AGENDADA*\n👤 Pablo | 📱 PS5\n⏰ Sábado 16 de mayo, 11:30 a.m. | ⚠️ Se calienta y se apaga\n👨‍💼 Asesor: Sofia",
    "🔔 *NUEVA CITA AGENDADA*\n👤 Eric Soto Rodríguez | 📱 Xbox 360 (x2) + Moto Z\n⏰ Jueves 14 de mayo, 11:00 a.m. | ⚠️ Xbox 360 con falla, Moto Z cambio de pantalla\n👨‍💼 Asesor: Sofia",
    "🔔 *NUEVA CITA AGENDADA*\n👤 Israel | 📱 Nintendo Switch\n⏰ Sábado 16 de mayo, 11:30 a.m. | ⚠️ Drift en palancas\n👨‍💼 Asesor: Sofia",
    "🔔 *NUEVA CITA AGENDADA*\n👤 José Juan Campos Medina | 📱 PS4 Fat, PS3 Fat, Xbox 360\n⏰ Domingo 17 de mayo, 12:00 p.m. | ⚠️ Mantenimiento profundo\n👨‍💼 Asesor: Camila",
    "🔔 *NUEVA CITA AGENDADA*\n👤 Carlos Tengo | 📱 iPhone 14\n⏰ Sábado 16 de mayo, 2:00 p.m. | ⚠️ Centro de carga dañado\n👨‍💼 Asesor: Sofia",
    "🔔 *NUEVA CITA AGENDADA*\n👤 Jaime Escamilla | 📱 Xbox Series X Digital\n⏰ Miércoles 13 de mayo, 10:30 a.m. | ⚠️ Puerto Ethernet fallo\n👨‍💼 Asesor: Camila",
    "🔔 *NUEVA CITA AGENDADA*\n👤 Irving Sanchez | 📱 Xbox One\n⏰ Viernes 15 de mayo, 5:00 p.m. | ⚠️ No enciende\n👨‍💼 Asesor: Sofia",
    "🔔 *NUEVA CITA AGENDADA*\n👤 David | 📱 PS5\n⏰ Sábado 16 de mayo, 2:45 p.m. | ⚠️ Se calienta mucho\n👨‍💼 Asesor: Valentina",
    "🔔 *NUEVA CITA AGENDADA*\n👤 Diego Gutierrez | 📱 Sony PS Vita PCH-1000\n⏰ Sábado 16 de mayo, 12:00 p.m. | ⚠️ Fallo en joystick\n👨‍💼 Asesor: Daniela",
]


def _parsear_fecha_hora_del_mensaje(fecha_str: str) -> datetime | None:
    """
    Parsea una cadena como "Jueves 15 de mayo, 3:30 PM" a datetime.
    VERSIÓN ULTRA-ROBUSTA: Sin regex complicado, solo string splitting.
    """
    logger.info(f"[IMPORT] Parseando fecha: '{fecha_str}'")
    if not fecha_str:
        return None

    try:
        fecha_str = fecha_str.strip()
        meses_inversos = {v: k for k, v in MESES_ES.items()}

        # Dividir por "de" para extraer día y mes
        partes = fecha_str.split(" de ")
        if len(partes) < 2:
            logger.warning(f"[IMPORT] Formato inválido (sin 'de'): {fecha_str}")
            return None

        # Parte 1: "DIA_NOMBRE DIA_NUM" (ej: "Sábado 9")
        parte_dia = partes[0].strip()
        dia_parts = parte_dia.split()
        if len(dia_parts) < 2:
            logger.warning(f"[IMPORT] No se pudo extraer día: {parte_dia}")
            return None
        dia_num_str = dia_parts[-1]
        try:
            dia_num = int(dia_num_str)
        except ValueError:
            logger.warning(f"[IMPORT] Día no es número: {dia_num_str}")
            return None

        # Parte 2: "MES_NOMBRE, HH:MM AMPM" (ej: "mayo, 11:30 a.m.")
        parte_mes_hora = partes[1].strip()
        # Dividir por coma
        if "," not in parte_mes_hora:
            logger.warning(f"[IMPORT] No hay coma: {parte_mes_hora}")
            return None
        mes_name, hora_part = parte_mes_hora.split(",", 1)
        mes_name = mes_name.strip()
        hora_part = hora_part.strip()

        # Buscar el mes
        mes_num = meses_inversos.get(mes_name.lower())
        if not mes_num:
            logger.warning(f"[IMPORT] Mes no encontrado: {mes_name}")
            return None

        # Extraer hora y ampm del formato "HH:MM AM/PM" o "HH:MM a.m."
        hora_partes = hora_part.split()
        if len(hora_partes) < 2:
            logger.warning(f"[IMPORT] Formato hora inválido: {hora_part}")
            return None

        tiempo = hora_partes[0]  # "11:30"
        ampm = " ".join(hora_partes[1:]).lower()  # "a.m." o "am"

        # Extraer hora y minuto
        if ":" not in tiempo:
            logger.warning(f"[IMPORT] No hay ':' en tiempo: {tiempo}")
            return None
        hora_str, min_str = tiempo.split(":", 1)
        try:
            hora = int(hora_str)
            minuto = int(min_str)
        except ValueError:
            logger.warning(f"[IMPORT] Hora/minuto no válidos: {hora_str}:{min_str}")
            return None

        # Convertir a 24h
        if ("pm" in ampm or "p.m" in ampm) and hora != 12:
            hora += 12
        elif ("am" in ampm or "a.m" in ampm) and hora == 12:
            hora = 0

        # Crear datetime
        ahora = datetime.now(ZONA_CDMX)
        año = ahora.year

        try:
            fecha = datetime(año, mes_num, dia_num, hora, minuto, 0, tzinfo=ZONA_CDMX)
            if fecha < ahora:
                # Si la fecha es anterior a ahora, intentar con el año anterior
                fecha = datetime(año - 1, mes_num, dia_num, hora, minuto, 0, tzinfo=ZONA_CDMX)
            return fecha
        except ValueError as e:
            logger.warning(f"[IMPORT] Error datetime: {e}")
            return None

    except Exception as e:
        logger.error(f"[IMPORT] Error parseando: {fecha_str} - {e}")
        return None


def _extraer_campos_cita(mensaje: str) -> dict | None:
    """
    Extrae campos de un mensaje "NUEVA CITA AGENDADA".
    Retorna dict con: nombre, dispositivo, problema, cuando, asesor
    O None si falla el parseo.

    Formato esperado:
    🔔 *NUEVA CITA AGENDADA*
    👤 {nombre} | 📱 {dispositivo}
    ⏰ {cuando} | ⚠️ {problema}
    👨‍💼 Asesor: {asesor}
    """
    try:
        # Líneas del mensaje
        lineas = mensaje.strip().split('\n')
        if len(lineas) < 4:
            logger.warning(f"[IMPORT] Mensaje con menos de 4 líneas: {len(lineas)}")
            return None

        # Línea 2: nombre y dispositivo
        # Patrón: "👤 {nombre} | 📱 {dispositivo}"
        match_linea2 = re.search(r"(.+?)\s*\|\s*(.+?)$", lineas[1])
        if not match_linea2:
            logger.warning(f"[IMPORT] No se extrajo nombre/dispositivo de: {lineas[1]}")
            return None
        nombre = match_linea2.group(1).strip()
        dispositivo = match_linea2.group(2).strip()

        # Línea 3: cuando y problema
        # Patrón: "⏰ {cuando} | ⚠️ {problema}"
        match_linea3 = re.search(r"(.+?)\s*\|\s*(.+?)$", lineas[2])
        if not match_linea3:
            logger.warning(f"[IMPORT] No se extrajo cuando/problema de: {lineas[2]}")
            return None
        cuando = match_linea3.group(1).strip()
        problema = match_linea3.group(2).strip()

        # Línea 4: asesor
        # Patrón: "👨‍💼 Asesor: {asesor}"
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
        logger.error(f"[IMPORT] Error extrayendo campos de cita: {e}")
        return None


async def main():
    print("=" * 60)
    print("  IMPORTADOR DE CITAS (LOCAL)")
    print("=" * 60)
    print(f"Total de citas a importar: {len(CITAS)}\n")

    total_encontradas = len(CITAS)
    importadas = 0
    ya_existentes = 0
    errores = 0
    detalles = []

    # Procesar cada cita
    for idx, texto_msg in enumerate(CITAS, 1):
        try:
            logger.info(f"[IMPORT] ▄▄▄ Procesando cita #{idx} ▄▄▄")

            # Extraer campos de la cita
            campos = _extraer_campos_cita(texto_msg)
            if not campos:
                logger.warning(f"[IMPORT] No se extrajeron campos de la cita #{idx}")
                errores += 1
                detalles.append({
                    "numero": idx,
                    "estado": "error",
                    "razon": "No se extrajeron los campos correctamente",
                })
                continue

            logger.info(f"[IMPORT] Campos extraídos: {campos}")

            # Parsear la fecha y hora
            fecha_hora = _parsear_fecha_hora_del_mensaje(campos["cuando"])
            if not fecha_hora:
                logger.warning(f"[IMPORT] No se pudo parsear fecha: {campos['cuando']}")
                errores += 1
                detalles.append({
                    "numero": idx,
                    "nombre": campos.get("nombre", "?"),
                    "estado": "error",
                    "razon": f"No se pudo parsear la fecha/hora: {campos['cuando']}",
                })
                continue

            logger.info(f"[IMPORT] Fecha parseada: {fecha_hora}")

            # Agendar cita
            resultado = await agendar_cita(
                nombre=campos["nombre"],
                telefono="",  # Sin teléfono para citas importadas
                dispositivo=campos["dispositivo"],
                problema=campos["problema"],
                fecha_hora=fecha_hora,
                asesor=campos["asesor"],
            )

            logger.info(f"[IMPORT] agendar_cita() retornó: {resultado}")

            # Procesar resultado
            if isinstance(resultado, dict) and resultado.get("ok"):
                importadas += 1
                detalles.append({
                    "numero": idx,
                    "nombre": campos["nombre"],
                    "dispositivo": campos["dispositivo"],
                    "problema": campos["problema"],
                    "fecha_hora": fecha_hora.isoformat(),
                    "asesor": campos["asesor"],
                    "estado": "importada",
                })
                logger.info(f"[IMPORT] ✅ Importada: {campos['nombre']}")
            else:
                error_msg = resultado.get("error", "") if isinstance(resultado, dict) else str(resultado)
                if "ya existe" in error_msg.lower() or "duplicate" in error_msg.lower():
                    ya_existentes += 1
                    detalles.append({
                        "numero": idx,
                        "nombre": campos["nombre"],
                        "estado": "ya_existente",
                        "razon": error_msg,
                    })
                    logger.info(f"[IMPORT] ℹ️ Ya existe: {campos['nombre']}")
                else:
                    errores += 1
                    detalles.append({
                        "numero": idx,
                        "nombre": campos["nombre"],
                        "estado": "error",
                        "razon": error_msg,
                    })
                    logger.warning(f"[IMPORT] ❌ Error: {error_msg}")

        except Exception as e:
            errores += 1
            logger.error(f"[IMPORT] ❌ Excepción en cita #{idx}: {e}")
            import traceback
            logger.error(f"[IMPORT] Traceback:\n{traceback.format_exc()}")
            detalles.append({
                "numero": idx,
                "estado": "error",
                "razon": str(e),
            })

    # Resumen
    print("\n" + "=" * 60)
    print("✅ RESULTADO:")
    print("=" * 60)
    print(f"✓ Importadas:      {importadas}")
    print(f"⏭️  Ya existentes:   {ya_existentes}")
    print(f"❌ Errores:         {errores}")
    print(f"📊 Total procesadas: {total_encontradas}")
    print("=" * 60)

    if errores > 0:
        print("\n🔴 Detalles de errores:")
        for detalle in detalles:
            if detalle.get("estado") == "error":
                print(f"  ❌ #{detalle.get('numero')}: {detalle.get('razon', 'Error desconocido')}")

    if importadas > 0:
        print("\n✅ Citas importadas exitosamente:")
        for detalle in detalles:
            if detalle.get("estado") == "importada":
                print(f"  ✓ #{detalle.get('numero')}: {detalle.get('nombre', '?')} ({detalle.get('dispositivo')})")

    print("\n" + "=" * 60)
    print("Proceso completado.")


if __name__ == "__main__":
    asyncio.run(main())
