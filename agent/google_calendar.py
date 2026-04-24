# agent/google_calendar.py — Integración con Google Calendar

import asyncio
import base64
import json
import logging
import os
import re
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

logger = logging.getLogger("agentkit")

ZONA = ZoneInfo("America/Mexico_City")
CALENDAR_ID = os.getenv(
    "CALENDAR_ID",
    "a80046be8b375f4a5b1c95f83bd23399a2dce7699d63e861ccc4fb594ae88e3d@group.calendar.google.com",
)
SCOPES = ["https://www.googleapis.com/auth/calendar"]
DURACION_MIN = 30
HORA_INICIO = 10   # 10:00 AM
HORA_FIN = 20      # 8:00 PM (último slot: 19:30)
DIAS_HABILES = {0, 1, 2, 3, 4, 5}  # lunes(0) a sábado(5)

DIAS_ES = {
    0: "lunes", 1: "martes", 2: "miércoles", 3: "jueves",
    4: "viernes", 5: "sábado", 6: "domingo",
}
MESES_ES = {
    1: "enero", 2: "febrero", 3: "marzo", 4: "abril", 5: "mayo", 6: "junio",
    7: "julio", 8: "agosto", 9: "septiembre", 10: "octubre", 11: "noviembre", 12: "diciembre",
}
MESES_NUM = {v: k for k, v in MESES_ES.items()}


# ─── Parseo de fechas y horas en español ─────────────────────────────────────

_DIA_A_NUM = {
    "lunes": 0, "martes": 1, "miercoles": 2, "miércoles": 2,
    "jueves": 3, "viernes": 4, "sabado": 5, "sábado": 5,
}

_RE_DIA = re.compile(r"\b(lunes|martes|mi[eé]rcoles|jueves|viernes|s[aá]bado)\b", re.I)
_RE_DIA_NUM = re.compile(r"\bel\s+(\d{1,2})(?:\s+de\s+(\w+))?\b", re.I)
_RE_HORA_PREP = re.compile(
    r"\ba\s+las?\s+(\d{1,2})(?::(\d{2}))?\s*(?:(am|pm|a\.m\.|p\.m\.))?\b", re.I
)
_RE_HORA_SOLA = re.compile(r"\b(\d{1,2})\s*(am|pm|a\.m\.|p\.m\.)\b", re.I)
_RE_HORA_24 = re.compile(r"\b(\d{1,2}):(\d{2})\b")

_KEYWORDS_VISITA = frozenset({
    "ir", "voy", "venir", "vengo", "paso", "pasar", "llevo", "llevar",
    "agendar", "agenda", "agendo", "cita", "reservar", "apartar",
    "disponible", "disponibilidad", "horario", "cuándo", "cuando",
    "puedo ir", "quisiera ir", "me apunto", "me anotas",
})


def detectar_intencion_agendar(texto: str) -> bool:
    """True si el mensaje contiene fecha/hora + intención de visitar el módulo."""
    t = texto.lower()
    tiene_fecha = bool(
        _RE_DIA.search(t)
        or _RE_DIA_NUM.search(t)
        or re.search(r"\bma[ñn]ana\b|\bhoy\b|\bpasado\s+ma[ñn]ana\b", t)
    )
    if not tiene_fecha:
        return False
    return any(kw in t for kw in _KEYWORDS_VISITA)


def parsear_fecha_en_texto(texto: str) -> date | None:
    """Extrae fecha de un mensaje en español. Retorna None si no detecta ninguna."""
    hoy = datetime.now(ZONA).date()
    t = texto.lower()

    if re.search(r"\bpasado\s+ma[ñn]ana\b", t):
        return hoy + timedelta(days=2)
    if re.search(r"\bma[ñn]ana\b", t):
        return hoy + timedelta(days=1)
    if re.search(r"\bhoy\b", t):
        return hoy

    m = _RE_DIA.search(t)
    if m:
        num = _DIA_A_NUM.get(m.group(1).lower())
        if num is not None:
            dias = (num - hoy.weekday()) % 7 or 7
            return hoy + timedelta(days=dias)

    m = _RE_DIA_NUM.search(t)
    if m:
        dia_num = int(m.group(1))
        mes_str = (m.group(2) or "").lower()
        mes = MESES_NUM.get(mes_str, hoy.month)
        try:
            candidata = date(hoy.year, mes, dia_num)
            if candidata < hoy:
                candidata = date(hoy.year + 1, mes, dia_num)
            return candidata
        except ValueError:
            pass

    return None


def parsear_hora_en_texto(texto: str) -> time | None:
    """Extrae hora de un mensaje en español. Retorna None si no detecta ninguna."""
    t = texto.lower()

    m = _RE_HORA_PREP.search(t)
    if m:
        h, mn = int(m.group(1)), int(m.group(2) or 0)
        suf = (m.group(3) or "").lower().replace(".", "")
        if suf == "pm" and h < 12:
            h += 12
        elif suf == "am" and h == 12:
            h = 0
        try:
            return time(h, mn)
        except ValueError:
            pass

    m = _RE_HORA_SOLA.search(t)
    if m:
        h = int(m.group(1))
        suf = m.group(2).lower().replace(".", "")
        if suf == "pm" and h < 12:
            h += 12
        elif suf == "am" and h == 12:
            h = 0
        try:
            return time(h, 0)
        except ValueError:
            pass

    m = _RE_HORA_24.search(t)
    if m:
        try:
            return time(int(m.group(1)), int(m.group(2)))
        except ValueError:
            pass

    return None


# ─── Google Calendar API (sync interno, async público) ───────────────────────

def _build_service():
    raw = os.getenv("GOOGLE_CREDENTIALS")
    if not raw:
        raise RuntimeError("GOOGLE_CREDENTIALS no configurado en Railway")
    json_str = base64.b64decode(raw.encode()).decode("utf-8")
    info = json.loads(json_str)
    creds = Credentials.from_service_account_info(info, scopes=SCOPES)
    return build("calendar", "v3", credentials=creds)


def _todos_slots(fecha: date) -> list[datetime]:
    slots: list[datetime] = []
    dt = datetime(fecha.year, fecha.month, fecha.day, HORA_INICIO, 0, tzinfo=ZONA)
    fin = datetime(fecha.year, fecha.month, fecha.day, HORA_FIN, 0, tzinfo=ZONA)
    while dt < fin:
        slots.append(dt)
        dt += timedelta(minutes=DURACION_MIN)
    return slots  # 10:00, 10:30 … 19:30


def _slots_sync(fecha: date) -> list[str]:
    if fecha.weekday() not in DIAS_HABILES:
        return []
    slots = _todos_slots(fecha)
    inicio = slots[0]
    fin = slots[-1] + timedelta(minutes=DURACION_MIN)

    try:
        service = _build_service()
        items = service.events().list(
            calendarId=CALENDAR_ID,
            timeMin=inicio.isoformat(),
            timeMax=fin.isoformat(),
            singleEvents=True,
            orderBy="startTime",
        ).execute().get("items", [])
    except RuntimeError as e:
        logger.error(f"[CALENDAR] {e}")
        return []
    except Exception as e:
        logger.error(f"[CALENDAR] Error listando eventos: {e}")
        return []

    ocupados: list[tuple[datetime, datetime]] = []
    for ev in items:
        s = ev.get("start", {}).get("dateTime")
        f = ev.get("end", {}).get("dateTime")
        if s and f:
            try:
                ocupados.append((
                    datetime.fromisoformat(s).astimezone(ZONA),
                    datetime.fromisoformat(f).astimezone(ZONA),
                ))
            except Exception:
                pass

    return [
        slot.strftime("%H:%M")
        for slot in slots
        if all(
            (slot + timedelta(minutes=DURACION_MIN)) <= oi or slot >= of
            for oi, of in ocupados
        )
    ]


def _agendar_sync(
    nombre: str, telefono: str, dispositivo: str, problema: str, fh: datetime
) -> dict:
    fin = fh + timedelta(minutes=DURACION_MIN)
    dia = DIAS_ES.get(fh.weekday(), "")
    mes = MESES_ES.get(fh.month, "")
    fecha_txt = f"{dia} {fh.day} de {mes}"
    hora_txt = fh.strftime("%I:%M %p").lstrip("0").replace("AM", "a.m.").replace("PM", "p.m.")

    body = {
        "summary": f"🔧 {nombre} — {dispositivo}",
        "description": (
            f"Cliente: {nombre}\n"
            f"Teléfono: {telefono}\n"
            f"Dispositivo: {dispositivo}\n"
            f"Problema: {problema}"
        ),
        "start": {"dateTime": fh.isoformat(), "timeZone": "America/Mexico_City"},
        "end": {"dateTime": fin.isoformat(), "timeZone": "America/Mexico_City"},
    }
    try:
        service = _build_service()
        creado = service.events().insert(calendarId=CALENDAR_ID, body=body).execute()
        eid = creado.get("id", "")
        logger.info(f"[CALENDAR] ✅ Cita agendada: {nombre} | {fecha_txt} {hora_txt} | id={eid}")
        return {
            "ok": True,
            "evento_id": eid,
            "nombre": nombre,
            "dispositivo": dispositivo,
            "fecha_texto": fecha_txt,
            "hora_texto": hora_txt,
            "confirmacion": (
                f"✅ *¡Cita confirmada!*\n"
                f"👤 {nombre}\n"
                f"📅 {fecha_txt.capitalize()}\n"
                f"🕐 {hora_txt}\n"
                f"📱 {dispositivo}\n"
                f"📍 Te esperamos en nuestro módulo.\n\n"
                f"_Si necesitas cambiar la fecha, escríbenos con anticipación. ¡Hasta entonces!_ 😊"
            ),
        }
    except RuntimeError as e:
        logger.error(f"[CALENDAR] {e}")
        return {"ok": False, "error": str(e), "confirmacion": ""}
    except Exception as e:
        logger.error(f"[CALENDAR] Error agendando: {e}")
        return {"ok": False, "error": str(e), "confirmacion": ""}


async def obtener_slots_disponibles(fecha: date) -> list[str]:
    """Retorna HH:MM disponibles para el día. Consulta la API en un hilo separado."""
    return await asyncio.to_thread(_slots_sync, fecha)


async def agendar_cita(
    nombre: str, telefono: str, dispositivo: str, problema: str, fecha_hora: datetime
) -> dict:
    """Crea el evento en Google Calendar. Retorna dict con ok, confirmacion, etc."""
    return await asyncio.to_thread(_agendar_sync, nombre, telefono, dispositivo, problema, fecha_hora)


async def cancelar_cita(evento_id: str) -> bool:
    def _cancel():
        try:
            _build_service().events().delete(calendarId=CALENDAR_ID, eventId=evento_id).execute()
            logger.info(f"[CALENDAR] Cancelada cita id={evento_id}")
            return True
        except Exception as e:
            logger.error(f"[CALENDAR] Error cancelando id={evento_id}: {e}")
            return False
    return await asyncio.to_thread(_cancel)


def formatear_slots_para_claude(slots: list[str], fecha: date) -> str:
    """Texto con disponibilidad real para inyectar en el contexto de Claude."""
    dia = DIAS_ES.get(fecha.weekday(), "")
    mes = MESES_ES.get(fecha.month, "")
    fecha_str = f"{dia} {fecha.day} de {mes}"

    if not slots:
        return (
            f"══ DISPONIBILIDAD REAL — {fecha_str.upper()} ══\n"
            f"⚠️ Sin horarios disponibles ese día. Sugiere los 2-3 días hábiles siguientes.\n"
            f"════════════════════════════════════════════════════"
        )

    mañ = [s for s in slots if int(s.split(":")[0]) < 13]
    tar = [s for s in slots if 13 <= int(s.split(":")[0]) < 17]
    noc = [s for s in slots if int(s.split(":")[0]) >= 17]
    bloques = []
    if mañ:
        bloques.append(f"Mañana: {', '.join(mañ)}")
    if tar:
        bloques.append(f"Tarde: {', '.join(tar)}")
    if noc:
        bloques.append(f"Noche: {', '.join(noc)}")

    return (
        f"══ DISPONIBILIDAD REAL — {fecha_str.upper()} ══\n"
        + "\n".join(bloques)
        + "\nOfrece SOLO estos horarios. Cuando el cliente confirme uno, "
        + "incluye el tag [[AGENDAR:...]] al final de tu respuesta.\n"
        + "════════════════════════════════════════════════════"
    )


# ─── Tag [[AGENDAR:...]] embebido en respuesta de Claude ─────────────────────

_RE_TAG = re.compile(
    r"\[\[AGENDAR:"
    r"nombre=([^|]+)\|"
    r"telefono=([^|]+)\|"
    r"dispositivo=([^|]+)\|"
    r"problema=([^|]+)\|"
    r"fecha=(\d{4}-\d{2}-\d{2})\|"
    r"hora=(\d{2}:\d{2})"
    r"\]\]",
    re.I,
)


def parsear_tag_agendar(texto: str) -> dict | None:
    """Extrae los datos del tag [[AGENDAR:...]] si existe. Retorna None si no hay."""
    m = _RE_TAG.search(texto)
    if not m:
        return None
    nombre, telefono, dispositivo, problema, fecha_str, hora_str = m.groups()
    return {
        "nombre": nombre.strip(),
        "telefono": telefono.strip(),
        "dispositivo": dispositivo.strip(),
        "problema": problema.strip(),
        "fecha_str": fecha_str.strip(),
        "hora_str": hora_str.strip(),
    }


def quitar_tags(texto: str) -> str:
    """Elimina el tag [[AGENDAR:...]] antes de enviar el mensaje al cliente."""
    return _RE_TAG.sub("", texto).strip()
