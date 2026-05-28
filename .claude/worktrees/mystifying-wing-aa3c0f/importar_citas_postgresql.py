#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Importa las 17 citas históricas a PostgreSQL en Railway.
Las citas futuras seguirán el flujo automático desde Google Calendar.
"""

import asyncio
import logging
import re
from datetime import datetime
from zoneinfo import ZoneInfo
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import String, Text, DateTime, Integer
from dotenv import load_dotenv
import os

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("import-pg")

load_dotenv()

ZONA_CDMX = ZoneInfo("America/Mexico_City")

MESES_ES = {
    1: "enero", 2: "febrero", 3: "marzo", 4: "abril", 5: "mayo", 6: "junio",
    7: "julio", 8: "agosto", 9: "septiembre", 10: "octubre", 11: "noviembre", 12: "diciembre"
}

DIAS_ES = {
    0: "lunes", 1: "martes", 2: "miércoles", 3: "jueves",
    4: "viernes", 5: "sábado", 6: "domingo"
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


class Base(DeclarativeBase):
    pass


class Cita(Base):
    __tablename__ = "citas"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    nombre: Mapped[str] = mapped_column(String(255))
    telefono: Mapped[str] = mapped_column(String(20), default="")
    dispositivo: Mapped[str] = mapped_column(String(255))
    problema: Mapped[str] = mapped_column(Text)
    fecha_hora: Mapped[datetime] = mapped_column(DateTime)
    asesor: Mapped[str] = mapped_column(String(255))
    fuente: Mapped[str] = mapped_column(String(50), default="historico")
    creada_en: Mapped[datetime] = mapped_column(DateTime, default=datetime.now(ZONA_CDMX))


def _parsear_fecha(fecha_str: str) -> datetime | None:
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
        dia_num = int(dia_parts[-1])
        parte_mes_hora = partes[1].strip()
        if "," not in parte_mes_hora:
            return None
        mes_name, hora_part = parte_mes_hora.split(",", 1)
        mes_num = meses_inversos.get(mes_name.strip().lower())
        if not mes_num:
            return None
        hora_partes = hora_part.strip().split()
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
    except Exception:
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
    print("=" * 70)
    print("  IMPORTADOR DE CITAS A PostgreSQL (Railway)")
    print("=" * 70)
    print(f"Total: {len(CITAS)} citas históricas\n")

    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        print("❌ ERROR: DATABASE_URL no configurada en .env")
        return

    if db_url.startswith("postgresql://"):
        db_url = db_url.replace("postgresql://", "postgresql+asyncpg://", 1)

    print(f"📌 Conectando a PostgreSQL en Railway...")
    engine = create_async_engine(db_url, echo=False)
    async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    # Crear tabla si no existe
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("✅ Tabla 'citas' lista\n")

    importadas = 0
    errores = 0
    detalles = []

    for idx, texto in enumerate(CITAS, 1):
        try:
            campos = _extraer_campos(texto)
            if not campos:
                print(f"❌ #{idx}: Error extrayendo campos")
                errores += 1
                detalles.append({"numero": idx, "estado": "error", "razon": "Parse error"})
                continue

            fecha = _parsear_fecha(campos["cuando"])
            if not fecha:
                print(f"❌ #{idx}: Error parseando fecha")
                errores += 1
                detalles.append({"numero": idx, "estado": "error", "razon": "Fecha inválida"})
                continue

            cita = Cita(
                nombre=campos["nombre"],
                telefono="",
                dispositivo=campos["dispositivo"],
                problema=campos["problema"],
                fecha_hora=fecha,
                asesor=campos["asesor"],
                fuente="historico"
            )

            async with async_session() as session:
                session.add(cita)
                await session.commit()

            print(f"✓ #{idx}: {campos['nombre'][:35]:35} → {fecha.strftime('%d/%m %H:%M')}")
            importadas += 1
            detalles.append({"numero": idx, "estado": "importada", "nombre": campos["nombre"]})

        except Exception as e:
            print(f"❌ #{idx}: Excepción - {str(e)[:40]}")
            errores += 1
            detalles.append({"numero": idx, "estado": "error", "razon": str(e)[:50]})

    print("\n" + "=" * 70)
    print(f"✅ IMPORTACIÓN COMPLETADA")
    print("=" * 70)
    print(f"📊 Importadas: {importadas}")
    print(f"❌ Errores:    {errores}")
    print(f"📋 Total:      {len(CITAS)}")
    print("=" * 70)

    print("\n🔄 FLUJO FUTURO (automático):")
    print("""
    1. WhatsApp: Cliente agenda cita
    2. Google Calendar: Cita se crea automáticamente
    3. PostgreSQL: Se sincroniza automáticamente desde Google Calendar
    4. Reportes: Aparecen en reportes diarios
    """)

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
