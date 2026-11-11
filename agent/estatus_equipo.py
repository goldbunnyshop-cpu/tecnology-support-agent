# agent/estatus_equipo.py — El cliente pregunta si su equipo ya está listo
#
# Caso real (nov 2026, 5639659669): el técnico le dijo al cliente que apenas lo iba a hacer y,
# cuando el cliente preguntó, el bot le confirmó que ya podía pasar por su equipo (aún sin reparar).
# Otro caso (5510032479): a "¿ya está lista mi tableta?" el bot ofreció servicio a domicilio.
#
# El bot NO tiene acceso al estatus real de las reparaciones. Estas preguntas nunca van a Claude:
# se contesta un mensaje fijo y se avisa al grupo interno para que el técnico responda.

import re
import unicodedata

_EQUIPO = r"(equipo|celular|cel|telefono|movil|iphone|ipad|tableta|tablet|laptop|compu\w*|consola|ps\d|xbox|switch|control|reloj|bocina)"

_PATRONES = [
    # "¿ya está listo?", "¿mi tableta ya quedó?", "¿ya quedó reparado?"
    r"\b(ya\s+)?(esta|quedo|queda)\s+(list[oa]s?|reparad[oa]s?|arreglad[oa]s?|terminad[oa]s?)\b",
    r"\bya\s+(quedo|quedaron|termin\w*|acab\w*)\b",
    r"\bya\s+(lo|la|los|las|me\s+lo|me\s+la)\s+(repararon|arreglaron|terminaron|cambiaron|tienen)\b",
    # "¿ya puedo pasar por mi equipo?", "¿cuándo paso a recogerlo?"
    r"\b(pasar|paso|ir|voy|vengo|venir)\s+(a\s+)?(por|recoger)\s+(mi|el|la|lo|los|las|su)\b",
    r"\b(pasar|paso|ir|voy)\s+a\s+recoger\w*\b",
    r"\brecoger\w*\s+(mi|el|la)\s+" + _EQUIPO,
    # "¿cómo va mi celular?", "¿hay avance?", "estatus de mi reparación"
    r"\bcomo\s+va\s+(mi|el|la|lo)\b",
    r"\b(avance|estatus|status)\b.*\b(" + _EQUIPO[1:-1] + r"|reparacion)\b",
    r"\b(" + _EQUIPO[1:-1] + r"|reparacion)\b.*\b(avance|estatus|status)\b",
    r"\bcuando\s+(esta|queda)\s+(list|mi|el|la)\w*",
]

# Preguntas ANTES de dejar el equipo ("¿en cuánto tiempo queda?", "si lo llevo hoy, ¿queda listo?")
_PREVENTA = re.compile(
    r"\b(si\s+(lo|la|se\s+lo|se\s+la)\s+(llevo|dejo|traigo)|cuanto\s+tard\w*|en\s+cuanto\s+tiempo|"
    r"el\s+mismo\s+dia|mismo\s+dia|cuanto\s+(tiempo|se\s+tarda))\b"
)


def _norm(t: str) -> str:
    t = unicodedata.normalize("NFD", (t or "").lower())
    return "".join(c for c in t if unicodedata.category(c) != "Mn")


def es_pregunta_estatus(texto: str) -> bool:
    """True si el cliente pregunta por el avance/entrega de un equipo que ya dejó."""
    t = _norm(texto)
    if not t or _PREVENTA.search(t):
        return False
    return any(re.search(p, t) for p in _PATRONES)


RESPUESTA_CLIENTE = (
    "Déjeme confirmar con el técnico el avance de su equipo 🔧 "
    "En breve le aviso por aquí 😊"
)


def respuesta_estatus(ahora=None) -> str:
    """Fuera de horario dice cuándo le confirma el técnico (ej. 'hoy a partir de las 10:30')."""
    try:
        from agent.horario import fuera_de_horario, texto_retoma
        if fuera_de_horario(ahora):
            return (f"Déjeme confirmar con el técnico el avance de su equipo 🔧 "
                    f"Le aviso por aquí {texto_retoma(ahora)} 😊")
    except Exception:
        pass
    return RESPUESTA_CLIENTE


def mensaje_grupo_estatus(telefono: str, texto: str) -> str:
    tel = "".join(ch for ch in str(telefono) if ch.isdigit())
    return "\n".join([
        "🔔 *CLIENTE PREGUNTA POR SU EQUIPO*",
        f"📞 {tel} — wa.me/{tel}",
        f"💬 \"{(texto or '').strip()[:200]}\"",
        "➡️ Revisar el estatus real y contestarle. El bot NO le confirmó nada.",
    ])


# El cliente ya dejó su equipo ("ya la dejé", "quedaron en avisarme", "me dijeron que en 2 días").
# Casos reales (nov 2026): a esos clientes les llegaban seguimientos de venta ("¿pudiste venir?",
# "quería dar seguimiento…") y el bot llegó a confirmar días de entrega.
_EN_TALLER = re.compile(
    r"\b(ya\s+(lo|la|los|las)\s+(deje|dejamos|lleve|llevamos|entregue)|"
    r"(deje|dejamos|lleve|entregue)\s+(mi|una|un|el|la|los|las)\s+\w+(\s+\w+)?\s+(a\s+reparar|para\s+reparar|en\s+reparacion|con\s+ustedes|ahi|alla)|"
    r"(deje|dejamos)\s+(mi|una|un|el|la)\s+\w+(\s+\w+)?\s+(ayer|hoy|el\s+\w+)|"
    r"quedaron\s+(en\s+)?(de\s+)?avisar\w*|me\s+(van\s+a\s+)?avisa\w*\s+cuando|"
    r"me\s+dijeron\s+que\s+(en|dentro\s+de|vaya|regrese|pase|venga)|"
    r"ya\s+fui\b|espero\s+(la|el)\s+(reparacion|equipo|diagnostico)|"
    r"(esta|sigue)\s+en\s+reparacion|cuando\s+este\s+list[oa])"
)


def equipo_en_taller(texto: str) -> bool:
    """True si el cliente dice que su equipo ya está con nosotros (no es venta: es entrega pendiente)."""
    return bool(_EN_TALLER.search(_norm(texto)))
