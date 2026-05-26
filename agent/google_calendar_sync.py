# agent/google_calendar_sync.py - Sincronizacion con Google Calendar
# Generado por AgentKit

"""
Integracion con Google Calendar.

Notas importantes:
- Si se usa una Service Account, GOOGLE_CALENDAR_ID NO debe ser "primary".
  "primary" apunta al calendario de la propia Service Account (invisible
  desde calendar.google.com). Hay que poner el email del calendario al que
  se quiere escribir, p.ej. tu_email@gmail.com, y compartir ese calendario
  con el client_email de la Service Account dandole permiso "Hacer cambios
  en eventos".
"""

import os
import json
import logging
from datetime import datetime, timedelta
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

logger = logging.getLogger("agentkit")

SCOPES = ["https://www.googleapis.com/auth/calendar"]
CREDENTIALS_PATH = os.getenv("GOOGLE_CREDENTIALS_PATH", "config/credentials.json")
CALENDAR_ID = os.getenv("GOOGLE_CALENDAR_ID", "primary")


def _get_credentials_info() -> dict | None:
    """Lee el dict de credenciales desde JSON inline o archivo."""
    # Primero intenta la variable con el JSON completo (para Railway sin volumen)
    json_inline = os.getenv("GOOGLE_CREDENTIALS_JSON")
    if json_inline:
        try:
            return json.loads(json_inline)
        except Exception as e:
            logger.error(f"[CALENDAR] GOOGLE_CREDENTIALS_JSON mal formado: {e}")
            return None
    # Luego intenta el archivo
    try:
        with open(CREDENTIALS_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def _client_email_de_credenciales():
    """Devuelve el client_email de las credenciales (para logs/diagnostico)."""
    info = _get_credentials_info()
    return info.get("client_email") if info else None


def cargar_credenciales():
    """Carga las credenciales de Google desde GOOGLE_CREDENTIALS_JSON o archivo."""
    info = _get_credentials_info()

    if not info:
        logger.error(
            "[CALENDAR] Sin credenciales. Define GOOGLE_CREDENTIALS_JSON (Railway) "
            f"o coloca el archivo en: {CREDENTIALS_PATH}"
        )
        return None

    try:
        creds = Credentials.from_service_account_info(info, scopes=SCOPES)
        logger.info("[CALENDAR] Credenciales cargadas")
        logger.info(f"[CALENDAR]   client_email (SA): {info.get('client_email')}")
        logger.info(f"[CALENDAR]   calendar_id usado: {CALENDAR_ID!r}")
        if CALENDAR_ID == "primary":
            logger.warning(
                "[CALENDAR] GOOGLE_CALENDAR_ID=primary con Service Account -> "
                "los eventos NO apareceran en tu Google Calendar personal. "
                "Cambialo a tu email y comparte el calendario con la SA."
            )
        return creds
    except Exception as e:
        logger.error(f"[CALENDAR] Error al cargar credenciales: {e}")
        return None


def obtener_servicio_calendar():
    """Obtiene el servicio de Google Calendar."""
    creds = cargar_credenciales()
    if not creds:
        return None
    try:
        return build("calendar", "v3", credentials=creds)
    except Exception as e:
        logger.error(f"[CALENDAR] Error al conectar con la API: {e}")
        return None


async def agregar_cita_a_calendar(nombre_cliente, dispositivo, problema, fecha_str, hora_str, asesor="Sin asignar"):
    """Agrega una cita a Google Calendar. Retorna True si fue exitoso."""

    service = obtener_servicio_calendar()
    if not service:
        logger.warning("[CALENDAR] No disponible - cita no sincronizada")
        return False

    try:
        fecha_hora = datetime.strptime(f"{fecha_str} {hora_str}", "%Y-%m-%d %H:%M")
        fecha_hora_fin = fecha_hora + timedelta(hours=1)

        evento = {
            "summary": f"{nombre_cliente} - {dispositivo}",
            "description": (
                f"Dispositivo: {dispositivo}\n"
                f"Problema: {problema}\n"
                f"Asesor: {asesor}"
            ),
            "start": {"dateTime": fecha_hora.isoformat(), "timeZone": "America/Mexico_City"},
            "end":   {"dateTime": fecha_hora_fin.isoformat(), "timeZone": "America/Mexico_City"},
            "reminders": {
                "useDefault": False,
                "overrides": [
                    {"method": "email", "minutes": 30},
                    {"method": "popup", "minutes": 10},
                ],
            },
            "colorId": "4",
        }

        logger.info(f"[CALENDAR] Insertando evento en calendarId={CALENDAR_ID!r}")
        resultado = service.events().insert(calendarId=CALENDAR_ID, body=evento).execute()

        event_id = resultado.get("id")
        event_link = resultado.get("htmlLink")
        organizer_email = (resultado.get("organizer") or {}).get("email")
        creator_email = (resultado.get("creator") or {}).get("email")

        logger.info(f"[CALENDAR] OK - {nombre_cliente} -> {fecha_str} {hora_str}")
        logger.info(f"[CALENDAR]   event_id:  {event_id}")
        logger.info(f"[CALENDAR]   htmlLink:  {event_link}")
        logger.info(f"[CALENDAR]   creator:   {creator_email}")
        logger.info(f"[CALENDAR]   organizer: {organizer_email}  <-- calendario real")

        sa_email = _client_email_de_credenciales()
        if organizer_email and sa_email and organizer_email == sa_email:
            logger.warning(
                "[CALENDAR] El evento se creo en el calendario de la Service "
                "Account, no en uno personal. Configura GOOGLE_CALENDAR_ID con "
                "el email del calendario destino y comparte ese calendario con "
                f"{sa_email} con permiso de Hacer cambios en eventos."
            )

        return True

    except HttpError as e:
        logger.error(f"[CALENDAR] Error HTTP {e.resp.status}: {e}")
        if e.resp.status == 404:
            logger.error(
                f"[CALENDAR] 404 -> calendarId={CALENDAR_ID!r} no existe para la "
                "Service Account, o no esta compartido con ella."
            )
        elif e.resp.status == 403:
            logger.error("[CALENDAR] 403 -> sin permiso de escritura en ese calendario.")
        return False
    except Exception as e:
        logger.error(f"[CALENDAR] Error inesperado: {e}")
        return False


async def obtener_proximas_citas(dias=7):
    """Obtiene las proximas N citas del calendario."""
    service = obtener_servicio_calendar()
    if not service:
        return []
    try:
        ahora = datetime.utcnow().isoformat() + "Z"
        fecha_fin = (datetime.utcnow() + timedelta(days=dias)).isoformat() + "Z"
        resultado = service.events().list(
            calendarId=CALENDAR_ID,
            timeMin=ahora,
            timeMax=fecha_fin,
            maxResults=10,
            singleEvents=True,
            orderBy="startTime",
        ).execute()
        eventos = resultado.get("items", [])
        logger.info(f"[CALENDAR] {len(eventos)} citas proximas en {CALENDAR_ID!r}")
        return eventos
    except Exception as e:
        logger.error(f"[CALENDAR] Error al obtener citas: {e}")
        return []


async def test_conexion():
    """Verifica que la conexion con Google Calendar funciona y lista calendarios."""
    logger.info("============================================================")
    logger.info("   TEST: Google Calendar Connection")
    logger.info("============================================================")

    creds = cargar_credenciales()
    if not creds:
        return False

    service = obtener_servicio_calendar()
    if not service:
        return False

    try:
        calendar_list = service.calendarList().list().execute()
        items = calendar_list.get("items", [])
        logger.info(f"Conexion OK - {len(items)} calendarios accesibles por la SA:")
        for cal in items:
            logger.info(f"  - {cal.get('summary')}  id={cal.get('id')}  role={cal.get('accessRole')}")
        if not items:
            logger.warning(
                "La Service Account no ve NINGUN calendario. Tienes que compartir "
                "tu calendario personal con su client_email."
            )
        return True
    except Exception as e:
        logger.error(f"Error: {e}")
        return False


if __name__ == "__main__":
    import asyncio
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    asyncio.run(test_conexion())
