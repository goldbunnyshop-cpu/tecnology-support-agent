# agent/espera_cliente.py — Entender cuándo el cliente dijo que va a responder
#
# Caso real (nov 2026): el miércoles el cliente escribe "el viernes les confirmo" y el bot,
# por su calendario fijo (2 h, 24 h, 72 h, 7 días), le volvía a escribir 2 horas después.
# Aquí se detecta el plazo que propone el cliente y se devuelve la fecha a partir de la cual
# es prudente volver a escribirle. leads.py pausa los seguimientos hasta esa fecha.

import re
import unicodedata
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

ZONA = ZoneInfo("America/Mexico_City")

_DIAS = {"lunes": 0, "martes": 1, "miercoles": 2, "jueves": 3, "viernes": 4, "sabado": 5, "domingo": 6}
_MESES = {"enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6, "julio": 7,
          "agosto": 8, "septiembre": 9, "setiembre": 9, "octubre": 10, "noviembre": 11, "diciembre": 12}
_NUM = {"un": 1, "una": 1, "uno": 1, "dos": 2, "tres": 3, "cuatro": 4, "cinco": 5, "seis": 6,
        "siete": 7, "ocho": 8, "diez": 10, "quince": 15, "par": 2, "un par de": 2}

# El cliente pospone: "les confirmo", "te aviso", "paso", "lo llevo", "me comunico", "cuando me paguen"...
_POSPONE = re.compile(
    r"\b(confirm\w*|avis\w*|escrib\w*|digo|dire|decimos|marc\w*|llam\w*|paso|pasare|pasamos|voy|ire|vamos|"
    r"llev\w*|regres\w*|comunic\w*|contact\w*|ve(o|re|mos)|chec\w*|revis\w*|decid\w*|pens\w*|"
    r"cobr\w*|pag\w*|deposit\w*|quincena|tenga|tengo|junte|reun\w*|respond\w*|contest\w*|"
    r"platic\w*|consult\w*|pregunt\w*|aparto|agend\w*|hablamos|hablo)\b"
)

HORA_RETOMA = 12          # a qué hora retomar cuando el cliente dio un día (mediodía, prudente)
HORA_TARDE = 17
MAX_DIAS = 62             # nunca pausar más de ~2 meses


def _norm(t: str) -> str:
    t = unicodedata.normalize("NFD", (t or "").lower())
    return "".join(c for c in t if unicodedata.category(c) != "Mn")


def _dia(base: datetime, dias: int, hora: int = HORA_RETOMA) -> datetime:
    d = base + timedelta(days=dias)
    return d.replace(hour=hora, minute=0, second=0, microsecond=0)


def _cantidad(txt: str) -> int | None:
    txt = txt.strip()
    if txt.isdigit():
        return int(txt)
    return _NUM.get(txt)


def detectar_espera(texto: str, ahora: datetime | None = None) -> datetime | None:
    """Fecha/hora (CDMX, aware) hasta la que conviene NO escribirle al cliente, o None.

    Solo actúa si el cliente pospone algo ("les confirmo", "paso", "te aviso"...) y da un plazo.
    """
    t = _norm(texto)
    if not t or not _POSPONE.search(t):
        return None
    ahora = (ahora or datetime.now(ZONA)).astimezone(ZONA)
    tarde = bool(re.search(r"\b(en la|por la|a la) (tarde|noche)\b", t))
    hora = HORA_TARDE if tarde else HORA_RETOMA

    # "en 2 horas", "en un rato", "al rato"
    m = re.search(r"\ben (\d+|un|una|dos|tres|cuatro|cinco|un par de) horas?\b", t)
    if m and (n := _cantidad(m.group(1))):
        return ahora + timedelta(hours=n, minutes=15)
    if re.search(r"\b(al rato|en un rato|mas tarde|en la tarde|en la noche|hoy)\b", t) and not re.search(
        r"\b(manana|semana|mes|lunes|martes|miercoles|jueves|viernes|sabado|domingo)\b", t
    ):
        return ahora + timedelta(hours=4)

    # "en 3 días", "en dos semanas", "en un mes"
    m = re.search(r"\ben (\d+|un|una|dos|tres|cuatro|cinco|seis|siete|ocho|diez|quince|un par de) "
                  r"(dias?|semanas?|mes(es)?)\b", t)
    if m and (n := _cantidad(m.group(1))):
        unidad = m.group(2)
        dias = n if unidad.startswith("dia") else n * 7 if unidad.startswith("semana") else n * 30
        return _dia(ahora, min(dias, MAX_DIAS), hora)

    # mañana / pasado mañana
    if re.search(r"\bpasado manana\b", t):
        return _dia(ahora, 2, hora)
    if re.search(r"\bmanana\b", t) and not re.search(r"\b(en la|por la|esta|de la) manana\b", t):
        return _dia(ahora, 1, hora)

    # próximo mes / mes que entra / fin de mes / quincena
    if re.search(r"\b(proximo mes|siguiente mes|mes que entra|otro mes|el mes que viene)\b", t):
        primero = (ahora.replace(day=1) + timedelta(days=32)).replace(day=1)
        return primero.replace(hour=hora, minute=0, second=0, microsecond=0) + timedelta(days=1)
    if re.search(r"\b(fin de mes|finales de mes|fines de mes)\b", t):
        sig = (ahora.replace(day=1) + timedelta(days=32)).replace(day=1)
        fin = sig - timedelta(days=1)
        destino = fin if fin.date() > ahora.date() else sig
        return destino.replace(hour=hora, minute=0, second=0, microsecond=0)
    if re.search(r"\bquincena\b", t):
        if ahora.day < 15:
            destino = ahora.replace(day=15)
        else:
            sig = (ahora.replace(day=1) + timedelta(days=32)).replace(day=1)
            fin = sig - timedelta(days=1)
            destino = fin if ahora.date() < fin.date() else sig.replace(day=15)
        return destino.replace(hour=hora, minute=0, second=0, microsecond=0) + timedelta(days=1)

    # próxima semana / semana que entra → lunes siguiente
    if re.search(r"\b(proxima semana|siguiente semana|semana que entra|la otra semana|semana que viene)\b", t):
        dias = 7 - ahora.weekday()
        return _dia(ahora, dias, hora)
    # fin de semana → sábado
    if re.search(r"\b(fin de semana|fin de)\b", t):
        dias = (5 - ahora.weekday()) % 7 or 7
        return _dia(ahora, dias, hora)

    # "el 15", "el 20 de noviembre"
    m = re.search(r"\b(?:el|para el|hasta el|dia) (\d{1,2})(?: de (" + "|".join(_MESES) + r"))?\b", t)
    if m:
        dia = int(m.group(1))
        mes = _MESES.get(m.group(2) or "", ahora.month)
        anio = ahora.year
        try:
            destino = ahora.replace(year=anio, month=mes, day=dia, hour=hora, minute=0, second=0, microsecond=0)
            if destino <= ahora:
                destino = destino.replace(year=anio + 1) if m.group(2) else (
                    (ahora.replace(day=1) + timedelta(days=32)).replace(day=dia, hour=hora, minute=0, second=0, microsecond=0))
            if (destino - ahora).days <= MAX_DIAS:
                return destino
        except ValueError:
            pass

    # día de la semana: "el viernes", "el próximo lunes"
    for nombre, wd in _DIAS.items():
        if re.search(rf"\b{nombre}\b", t):
            dias = (wd - ahora.weekday()) % 7
            if dias == 0 or re.search(rf"\b(proximo|siguiente|otro) {nombre}\b", t):
                dias = dias or 7
            return _dia(ahora, dias, hora)

    # Pospone sin fecha ("lo platico con mi esposa y les aviso", "déjame pensarlo"):
    # no insistir a las 2 h; darle 2 días.
    if re.search(r"\b(les? aviso|te aviso|le aviso|les? confirmo|te confirmo|lo pienso|pensarlo|lo platico|"
                 r"lo checo|lo consulto|lo reviso|lo veo|te digo|les digo|le digo|te escribo|les escribo)\b", t):
        return _dia(ahora, 2, HORA_RETOMA)

    return None


def describir_espera(hasta: datetime) -> str:
    """'el viernes 6 de noviembre' — para el contexto del mensaje de seguimiento."""
    d = hasta.astimezone(ZONA)
    dias = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
    meses = ["", "enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
             "septiembre", "octubre", "noviembre", "diciembre"]
    return f"{dias[d.weekday()]} {d.day} de {meses[d.month]}"
