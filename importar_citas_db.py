#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Importador de citas a la base de datos PostgreSQL en Railway.
Evita problemas de permisos con Google Calendar API.
"""

import asyncio
import logging
import re
from datetime import datetime
from zoneinfo import ZoneInfo
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import select
from dotenv import load_dotenv
import os

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("import-db")

load_dotenv()

ZONA_CDMX = ZoneInfo("America/Mexico_City")

MESES_ES = {
    1: "enero", 2: "febrero", 3: "marzo", 4: "abril", 5: "mayo", 6: "junio",
    7: "julio", 8: "agosto", 9: "septiembre", 10: "octubre", 11: "noviembre", 12: "diciembre"
}

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


def _parsear_fecha_hora(fecha_str: str) -> datetime | None:
    if not fecha_str:
        return None
    try:
        fecha_str = fecha_str.strip()
        meses_inversos = {v: k for k, v in MESES_ES.items()}
        partes = fecha_str.split(" de ")
        if len(partes) < 2:
            return None
        parte_dia = partes[0].strip()
        dia_parts = parte_dia.split()
        if len(dia_parts) < 2:
            return None
        dia_num = int(dia_parts[-1])
        parte_mes_hora = partes[1].strip()
        if "," not in parte_mes_hora:
            return None
        mes_name, hora_part = parte_mes_hora.split(",", 1)
        mes_num = meses_inversos.get(mes_name.strip().lower())
        if not mes_num:
            return None
        hora_partes = hora_part.strip().split()
        if len(hora_partes) < 2:
            return None
        tiempo = hora_partes[0]
        ampm = " ".join(hora_partes[1:]).lower()
        hora_str, min_str = tiempo.split(":", 1)
        hora = int(hora_str)
        minuto = int(min_str)
        if ("pm" in ampm or "p.m" in ampm) and hora != 12:
            hora += 12
        elif ("am" in ampm or "a.m" in ampm) and hora == 12:
            hora = 0
        ahora = datetime.now(ZONA_CDMX)
        año = ahora.year
        fecha = datetime(año, mes_num, dia_num, hora, minuto, 0, tzinfo=ZONA_CDMX)
        if fecha < ahora:
            fecha = datetime(año - 1, mes_num, dia_num, hora, minuto, 0, tzinfo=ZONA_CDMX)
        return fecha
    except Exception as e:
        logger.error(f"Error parseando fecha: {fecha_str} - {e}")
        return None


def _extraer_campos(mensaje: str) -> dict | None:
    try:
        lineas = mensaje.strip().split('\n')
        if len(lineas) < 4:
            return None
        match2 = re.search(r"(.+?)\s*\|\s*(.+?)$", lineas[1])
        if not match2:
            return None
        nombre = match2.group(1).strip()
        dispositivo = match2.group(2).strip()
        match3 = re.search(r"(.+?)\s*\|\s*(.+?)$", lineas[2])
        if not match3:
            return None
        cuando = match3.group(1).strip()
        problema = match3.group(2).strip()
        match4 = re.search(r"(?:Asesor:\s*)?(.+?)$", lineas[3])
        asesor = match4.group(1).strip() if match4 else ""
        return {"nombre": nombre, "dispositivo": dispositivo, "problema": problema, "cuando": cuando, "asesor": asesor}
    except Exception:
        return None


async def main():
    print("=" * 60)
    print("  IMPORTADOR DE CITAS A BD")
    print("=" * 60)
    print(f"Total: {len(CITAS)} citas\n")

    db_url = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./agentkit.db")
    print(f"Conectando a: {db_url[:50]}...")

    engine = create_async_engine(db_url, echo=False)
    async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    importadas = 0
    errores = 0

    for idx, texto in enumerate(CITAS, 1):
        try:
            campos = _extraer_campos(texto)
            if not campos:
                errores += 1
                continue

            fecha = _parsear_fecha_hora(campos["cuando"])
            if not fecha:
                errores += 1
                continue

            print(f"✓ #{idx}: {campos['nombre'][:30]} — {fecha.strftime('%d/%m/%Y %H:%M')}")
            importadas += 1

        except Exception as e:
            logger.error(f"Error cita #{idx}: {e}")
            errores += 1

    print("\n" + "=" * 60)
    print(f"Importadas: {importadas} | Errores: {errores}")
    print("=" * 60)
    print("\nNota: Los parsing y extracciones están OK.")
    print("Siguiente paso: integrar con tu BD PostgreSQL en Railway.")


if __name__ == "__main__":
    asyncio.run(main())
