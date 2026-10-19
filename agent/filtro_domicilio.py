# agent/filtro_domicilio.py — Servicio a domicilio (regla del dueño)
#
# Sí hay servicio a domicilio, pero por chat NO se comparten precios: la cotización y la
# cita a domicilio se concretan de forma manual con el equipo.
#   1) Si el cliente pregunta por servicio a domicilio → texto fijo (sin IA, sin precio).
#   2) Mientras la conversación esté en "modo domicilio" (el bot ya dio ese texto en los
#      últimos mensajes), el motor de precios NO se ejecuta y, si el cliente pide precio,
#      se responde un texto fijo sin cifras.
#
# Módulo puro (sin red ni IA): se ejecuta ANTES de pricing y de Claude.

import re
import unicodedata

RESPUESTA_DOMICILIO = (
    "¡Sí contamos con servicio a domicilio! 🏠 "
    "Para el servicio a domicilio la cotización y la cita se concretan de forma personalizada con nuestro equipo. "
    "¿Me comparte su nombre, el equipo (marca y modelo), la falla y su colonia o alcaldía?"
)

# Si en modo domicilio el cliente pide precio / aproximado.
RESPUESTA_DOMICILIO_PRECIO = (
    "Para el servicio a domicilio el costo se lo confirma directamente nuestro equipo al concretar la cita, "
    "porque depende del equipo, la falla y la zona. "
    "¿Me comparte su nombre, el equipo (marca y modelo), la falla y su colonia o alcaldía para avanzar?"
)

# Cuántos mensajes recientes del historial se revisan para saber si estamos en modo domicilio.
_VENTANA_MODO = 12


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFD", (s or "").lower())
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return re.sub(r"\s+", " ", s).strip()


_PATRONES = [
    r"\ba\s+domicilio\b",
    r"\bservicio\s+(?:a|en)\s+(?:domicilio|casa|mi\s+casa|la\s+casa|oficina|mi\s+oficina)\b",
    r"\b(?:van|vienen|vas|vienes|venir|ir|pasan|pasas|pasar|acuden|acudir)\s+(?:a|hasta)\s+(?:mi\s+|la\s+|su\s+)?(?:casa|domicilio|oficina|trabajo|negocio)\b",
    r"\b(?:recogen|recoges|recoger|pasan\s+por|pasas\s+por|pasar\s+por|van\s+por|vienen\s+por)\s+(?:el\s+|mi\s+|la\s+|los\s+|las\s+)?(?:equipo|cel\w*|telefono|laptop|compu\w*|consola|tablet\w*|ipad|iphone|control)\w*",
    r"\b(?:atienden|reparan|arreglan|trabajan|hacen\s+(?:el\s+)?servicio)\s+(?:a|en)\s+(?:domicilio|casa)\b",
    r"\ba\s+(?:mi\s+)?casa\b.{0,25}\b(?:servicio|reparar|repara\w*|arregl\w*|tecnico)\b",
    r"\btecnico\b.{0,25}\b(?:a|hasta)\s+(?:mi\s+)?(?:casa|domicilio|oficina)\b",
    r"\bhome\s+service\b",
]

_RE_DOMICILIO = re.compile("|".join(f"(?:{p})" for p in _PATRONES))

_RE_PRECIO = re.compile(
    r"cuanto|precio|costo|cuesta|cobr\w+|cotiz\w+|presupuesto|aproximad\w+|mas\s+o\s+menos|rango|tarifa|\$\s*\d"
)


def es_consulta_domicilio(texto: str) -> bool:
    """True si el mensaje pregunta/pide servicio a domicilio."""
    t = _norm(texto)
    return bool(t) and bool(_RE_DOMICILIO.search(t))


def en_modo_domicilio(historial: list[dict] | None) -> bool:
    """True si el bot ya respondió el texto de domicilio en los mensajes recientes."""
    for m in list(historial or [])[-_VENTANA_MODO:]:
        if m.get("role") == "assistant":
            c = str(m.get("content", ""))
            if RESPUESTA_DOMICILIO[:40] in c or RESPUESTA_DOMICILIO_PRECIO[:40] in c:
                return True
    return False


def respuesta_domicilio(mensaje: str, historial: list[dict] | None = None) -> str | None:
    """
    Texto fijo si aplica; None si no.
    - Primera vez que pregunta por domicilio → RESPUESTA_DOMICILIO.
    - Ya en modo domicilio y pide precio → RESPUESTA_DOMICILIO_PRECIO.
    - Ya en modo domicilio sin pedir precio → None (Claude continúa, con pricing bloqueado).
    """
    historial = historial or []
    modo = en_modo_domicilio(historial)
    if modo:
        return RESPUESTA_DOMICILIO_PRECIO if _RE_PRECIO.search(_norm(mensaje)) else None
    if es_consulta_domicilio(mensaje):
        return RESPUESTA_DOMICILIO
    return None
