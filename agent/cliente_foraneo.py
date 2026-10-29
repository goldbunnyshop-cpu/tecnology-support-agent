# agent/cliente_foraneo.py — Clientes que NO están en CDMX y vendrán en una fecha futura
#
# Caso real (5215617849563, Nubia Z60 Ultra): "yo estaré en la Ciudad de México como por el
# 7 de noviembre". El bot solo dijo "queda anotado" y agendó, sin aclarar nada.
# Regla: si el cliente indica que viene de fuera / estará en CDMX en una fecha, se inyecta
# una nota para que el bot (1) confirme que entendió que viene de fuera y la fecha,
# (2) comparta la ubicación completa, (3) avise que la refacción se confirma/aparta antes
# de su viaje y (4) le pida avisar si cambia su fecha de llegada.

import re
import unicodedata


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFD", (s or "").lower())
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return re.sub(r"\s+", " ", s).strip()


_CIUDAD = r"(?:la |el )?(?:ciudad de mexico|cdmx|df|d f|ciudad|mexico|tlalpan)"

_PATRONES = [
    rf"\b(?:estare|estaria|voy a estar|llego|llegare|llegaria|vengo|vendre|viajo|voy|ire|bajo|bajare|paso por) (?:a |al |en |por |de vuelta a )?{_CIUDAD}\b",
    rf"\b(?:cuando|en cuanto) (?:este|llegue|vaya|baje|venga) (?:a |en |por )?{_CIUDAD}\b",
    r"\bno (?:vivo|radico|estoy|soy) (?:en|de) (?:la )?(?:ciudad|cdmx|df|mexico)\b",
    r"\b(?:soy|vivo|radico|estoy) (?:de|en) (?:fuera|provincia|el estado de|otro estado|toluca|puebla|queretaro|"
    r"cuernavaca|pachuca|guadalajara|monterrey|veracruz|oaxaca|acapulco|leon|morelia|hidalgo|morelos|guerrero)\b",
    r"\bestoy fuera de (?:la )?(?:ciudad|cdmx)\b",
    r"\bvengo de (?:fuera|provincia|otro estado)\b",
]
_RE = re.compile("|".join(f"(?:{p})" for p in _PATRONES))


def es_cliente_foraneo(texto: str) -> bool:
    t = _norm(texto)
    return bool(t) and bool(_RE.search(t))


def cliente_foraneo_en_historial(historial: list[dict] | None, mensaje: str = "") -> bool:
    if es_cliente_foraneo(mensaje):
        return True
    return any(m.get("role") == "user" and es_cliente_foraneo(str(m.get("content", "")))
               for m in (historial or [])[-12:])


NOTA_FORANEO = (
    "⚠️ NOTA SISTEMA — CLIENTE QUE VIENE DE FUERA DE CDMX: el cliente indicó que no está en la ciudad "
    "y vendrá en una fecha específica. En tu respuesta:\n"
    "1) Confirma con tus palabras que entendiste que viene de fuera y la fecha que dio "
    "(si dijo 'como por el…', pregunta si esa fecha ya es segura).\n"
    "2) Comparte la ubicación completa: Plazuela de la Fama 1, Col. La Fama, Tlalpan — interior de La Comer Tlalpan, "
    "zona de Fuentes Brotantes, a 3 calles del Metrobús Ayuntamiento — Maps: https://maps.app.goo.gl/XdCSu743LpyY6aAt7 "
    "y el horario de ese día. Aclara que estamos en el SUR de la ciudad (Tlalpan) para que planee su traslado.\n"
    "3) Dile que confirmamos la disponibilidad de la refacción ANTES de su viaje para que no venga en vano, "
    "y que le escribimos unos días antes para confirmar.\n"
    "4) Pídele que nos avise si cambia su fecha de llegada.\n"
    "Si ya diste esta información antes en la conversación, NO la repitas completa: solo lo que falte."
)
