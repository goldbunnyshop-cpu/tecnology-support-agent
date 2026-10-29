# agent/horario.py — Horario de los HUMANOS (técnicos / responsables)
#
# El bot contesta 24 h (cotiza e informa), pero fuera de horario NO promete atención
# humana inmediata ("en breve", "en menos de 30 minutos"): dice cuándo se retoma.
#
# Horario del módulo (decidido por el dueño):
#   Lun–Vie 10:00–21:00 · Sáb–Dom 11:00–20:00
# Los humanos retoman la atención a partir del horario de citas:
#   Lun–Vie 10:30 · Sáb–Dom 11:30
# "Fuera de horario" = desde que cierra el módulo hasta las 10:30 / 11:30 del día siguiente.

import re
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

ZONA_CDMX = ZoneInfo("America/Mexico_City")

APERTURA_HUMANOS = {0: time(10, 30), 1: time(10, 30), 2: time(10, 30), 3: time(10, 30), 4: time(10, 30),
                    5: time(11, 30), 6: time(11, 30)}
CIERRE_MODULO = {0: time(21, 0), 1: time(21, 0), 2: time(21, 0), 3: time(21, 0), 4: time(21, 0),
                 5: time(20, 0), 6: time(20, 0)}
_DIAS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]


def _ahora(ahora: datetime | None = None) -> datetime:
    return (ahora or datetime.now(ZONA_CDMX)).astimezone(ZONA_CDMX)


def fuera_de_horario(ahora: datetime | None = None) -> bool:
    a = _ahora(ahora)
    d = a.weekday()
    return a.time() < APERTURA_HUMANOS[d] or a.time() >= CIERRE_MODULO[d]


def proxima_apertura(ahora: datetime | None = None) -> datetime:
    a = _ahora(ahora)
    hoy = a.replace(hour=APERTURA_HUMANOS[a.weekday()].hour, minute=APERTURA_HUMANOS[a.weekday()].minute,
                    second=0, microsecond=0)
    if a < hoy:
        return hoy
    m = a + timedelta(days=1)
    t = APERTURA_HUMANOS[m.weekday()]
    return m.replace(hour=t.hour, minute=t.minute, second=0, microsecond=0)


def minutos_hasta_apertura(ahora: datetime | None = None) -> int:
    return max(1, int((proxima_apertura(ahora) - _ahora(ahora)).total_seconds() // 60))


def texto_retoma(ahora: datetime | None = None) -> str:
    """'hoy a partir de las 10:30', 'mañana a partir de las 11:30'."""
    a = _ahora(ahora)
    ap = proxima_apertura(a)
    hora = ap.strftime("%H:%M").lstrip("0")
    if ap.date() == a.date():
        cuando = "hoy"
    elif ap.date() == (a + timedelta(days=1)).date():
        cuando = "mañana"
    else:
        cuando = f"el {_DIAS[ap.weekday()]}"
    return f"{cuando} a partir de las {hora}"


# Promesas de atención inmediata → se reemplazan fuera de horario
_FUERA = "Nuestro equipo está fuera de horario"


def ajustar_promesas(texto: str, ahora: datetime | None = None) -> str:
    """Fuera de horario, cambia 'en breve' / 'en 30 minutos' por cuándo se retoma la atención."""
    if not texto or not fuera_de_horario(ahora) or _FUERA in texto:
        return texto
    r = texto_retoma(ahora)
    reglas = [
        (r"En un lapso no mayor a 30 minutos un técnico especialista te atenderá personalmente",
         f"{_FUERA}: un técnico especialista te atenderá {r}"),
        (r"en menos de 30 minutos", r),
        (r"En breve le escribe por este mismo chat\.?",
         f"{_FUERA}; le escribe {r} por este mismo chat."),
        (r"y en breve le confirmamos\.?", f"y le confirmamos {r} ({_FUERA.lower()})."),
        (r"Le regresamos el mensaje con la información en breve\.?",
         f"{_FUERA}; le regresamos el mensaje con la información {r}."),
    ]
    out = texto
    for patron, nuevo in reglas:
        out = re.sub(patron, nuevo, out)
    return out


def nota_claude(ahora: datetime | None = None) -> str:
    """Contexto para la IA cuando el equipo humano está fuera de horario ('' si está en horario)."""
    if not fuera_de_horario(ahora):
        return ""
    return (
        f"⚠️ NOTA SISTEMA — FUERA DE HORARIO: el equipo humano está fuera de horario y retoma la atención "
        f"{texto_retoma(ahora)}. Puedes cotizar, dar información y agendar citas dentro del horario de citas. "
        f"NO prometas que un técnico o responsable responderá 'en breve', 'en unos minutos' o 'ahorita': "
        f"di que retomamos {texto_retoma(ahora)}."
    )
