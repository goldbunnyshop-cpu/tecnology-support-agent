#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script DIRECTO para importar citas usando credenciales desde archivo JSON.
Bypasea la carga de .env para evitar problemas con variables largas.
"""

import asyncio
import logging
import re
import json
import base64
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("import-directo")

# Constantes de Google Calendar
SCOPES = ["https://www.googleapis.com/auth/calendar"]
CALENDAR_ID = "tecnotogysupportmx@gmail.com"
ZONA = ZoneInfo("America/Mexico_City")
DURACION_MIN = 30

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


def cargar_credenciales():
    try:
        with open("config/credentials.json", "r") as f:
            creds_dict = json.load(f)
        logger.info("[SETUP] Credenciales cargadas")
        return creds_dict
    except Exception as e:
        logger.error(f"[SETUP] Error cargando credenciales: {e}")
        return None


def crear_servicio(creds_dict):
    try:
        creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
        service = build("calendar", "v3", credentials=creds)
        logger.info("[SETUP] Servicio Google Calendar creado")
        return service
    except Exception as e:
        logger.error(f"[SETUP] Error creando servicio: {e}")
        return None


def _parsear_fecha_hora_del_mensaje(fecha_str: str) -> datetime | None:
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
        dia_num_str = dia_parts[-1]
        try:
            dia_num = int(dia_num_str)
        except ValueError:
            return None
        parte_mes_hora = partes[1].strip()
        if "," not in parte_mes_hora:
            return None
        mes_name, hora_part = parte_mes_hora.split(",", 1)
        mes_name = mes_name.strip()
        hora_part = hora_part.strip()
        mes_num = meses_inversos.get(mes_name.lower())
        if not mes_num:
            return None
        hora_partes = hora_part.split()
        if len(hora_partes) < 2:
            return None
        tiempo = hora_partes[0]
        ampm = " ".join(hora_partes[1:]).lower()
        if ":" not in tiempo:
            return None
        hora_str, min_str = tiempo.split(":", 1)
        try:
            hora = int(hora_str)
            minuto = int(min_str)
        except ValueError:
            return None
        if ("pm" in ampm or "p.m" in ampm) and hora != 12:
            hora += 12
        elif ("am" in ampm or "a.m" in ampm) and hora == 12:
            hora = 0
        ahora = datetime.now(ZONA)
        año = ahora.year
        try:
            fecha = datetime(año, mes_num, dia_num, hora, minuto, 0, tzinfo=ZONA)
            if fecha < ahora:
                fecha = datetime(año - 1, mes_num, dia_num, hora, minuto, 0, tzinfo=ZONA)
            return fecha
        except ValueError:
            return None
    except Exception:
        return None


def _extraer_campos_cita(mensaje: str) -> dict | None:
    try:
        lineas = mensaje.strip().split('\n')
        if len(lineas) < 4:
            return None
        match_linea2 = re.search(r"(.+?)\s*\|\s*(.+?)$", lineas[1])
        if not match_linea2:
            return None
        nombre = match_linea2.group(1).strip()
        dispositivo = match_linea2.group(2).strip()
        match_linea3 = re.search(r"(.+?)\s*\|\s*(.+?)$", lineas[2])
        if not match_linea3:
            return None
        cuando = match_linea3.group(1).strip()
        problema = match_linea3.group(2).strip()
        match_linea4 = re.search(r"(?:Asesor:\s*)?(.+?)$", lineas[3])
        asesor = match_linea4.group(1).strip() if match_linea4 else ""
        return {
            "nombre": nombre,
            "dispositivo": dispositivo,
            "problema": problema,
            "cuando": cuando,
            "asesor": asesor,
        }
    except Exception:
        return None


def agendar_cita(service, nombre: str, dispositivo: str, problema: str, fecha_hora: datetime, asesor: str = ""):
    try:
        fin = fecha_hora + timedelta(minutes=DURACION_MIN)
        dia = DIAS_ES.get(fecha_hora.weekday(), "")
        mes = MESES_ES.get(fecha_hora.month, "")
        fecha_txt = f"{dia} {fecha_hora.day} de {mes}"
        hora_txt = fecha_hora.strftime("%I:%M %p").lstrip("0").replace("AM", "a.m.").replace("PM", "p.m.")

        body = {
            "summary": f"🔧 {nombre} — {dispositivo}",
            "description": (
                f"Cliente: {nombre}\nDispositivo: {dispositivo}\nProblema: {problema}\nAsesor: {asesor}"
            ),
            "start": {"dateTime": fecha_hora.isoformat(), "timeZone": "America/Mexico_City"},
            "end": {"dateTime": fin.isoformat(), "timeZone": "America/Mexico_City"},
        }

        creado = service.events().insert(calendarId=CALENDAR_ID, body=body).execute()
        eid = creado.get("id", "")
        logger.info(f"[CALENDAR] Cita agendada: {nombre}")
        return {
            "ok": True,
            "evento_id": eid,
            "nombre": nombre,
            "dispositivo": dispositivo,
            "fecha_texto": fecha_txt,
            "hora_texto": hora_txt,
        }
    except Exception as e:
        logger.error(f"[CALENDAR] Error: {e}")
        error_msg = str(e).lower()
        if "conflict" in error_msg or "ya existe" in error_msg:
            return {"ok": False, "error": "Ya existe", "es_duplicado": True}
        return {"ok": False, "error": str(e), "es_duplicado": False}


async def main():
    print("=" * 60)
    print("  IMPORTADOR DE CITAS (DIRECTO)")
    print("=" * 60)
    print(f"Total de citas a importar: {len(CITAS)}\n")

    creds_dict = cargar_credenciales()
    if not creds_dict:
        print("Error cargando credenciales. Abortando.")
        return

    service = crear_servicio(creds_dict)
    if not service:
        print("Error creando servicio. Abortando.")
        return

    print()

    total_encontradas = len(CITAS)
    importadas = 0
    ya_existentes = 0
    errores = 0
    detalles = []

    for idx, texto_msg in enumerate(CITAS, 1):
        try:
            campos = _extraer_campos_cita(texto_msg)
            if not campos:
                errores += 1
                detalles.append({"numero": idx, "estado": "error", "razon": "No se extrajeron campos"})
                continue

            fecha_hora = _parsear_fecha_hora_del_mensaje(campos["cuando"])
            if not fecha_hora:
                errores += 1
                detalles.append({"numero": idx, "nombre": campos.get("nombre", "?"), "estado": "error", "razon": "Error parsing fecha"})
                continue

            resultado = agendar_cita(service, nombre=campos["nombre"], dispositivo=campos["dispositivo"], problema=campos["problema"], fecha_hora=fecha_hora, asesor=campos["asesor"])

            if resultado.get("ok"):
                importadas += 1
                detalles.append({"numero": idx, "nombre": campos["nombre"], "dispositivo": campos["dispositivo"], "estado": "importada"})
            elif resultado.get("es_duplicado"):
                ya_existentes += 1
                detalles.append({"numero": idx, "nombre": campos["nombre"], "estado": "ya_existente", "razon": "Ya existe"})
            else:
                errores += 1
                detalles.append({"numero": idx, "nombre": campos["nombre"], "estado": "error", "razon": resultado.get("error", "Desconocido")})

        except Exception as e:
            errores += 1
            detalles.append({"numero": idx, "estado": "error", "razon": str(e)})

    print("\n" + "=" * 60)
    print("RESULTADO:")
    print("=" * 60)
    print(f"Importadas:      {importadas}")
    print(f"Ya existentes:   {ya_existentes}")
    print(f"Errores:         {errores}")
    print(f"Total procesadas: {total_encontradas}")
    print("=" * 60)

    if errores > 0:
        print("\nDetalles de errores:")
        for detalle in detalles:
            if detalle.get("estado") == "error":
                print(f"  #{detalle.get('numero')}: {detalle.get('razon')}")

    if importadas > 0:
        print("\nCitas importadas:")
        for detalle in detalles:
            if detalle.get("estado") == "importada":
                print(f"  #{detalle.get('numero')}: {detalle.get('nombre')}")

    if ya_existentes > 0:
        print("\nYa existentes:")
        for detalle in detalles:
            if detalle.get("estado") == "ya_existente":
                print(f"  #{detalle.get('numero')}: {detalle.get('nombre')}")

    print("\n" + "=" * 60)
    print("Proceso completado.")


if __name__ == "__main__":
    asyncio.run(main())
