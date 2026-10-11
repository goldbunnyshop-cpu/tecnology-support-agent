# agent/filtro_sensible.py — Filtro de consultas sensibles (modificaciones de software/sistema)
#
# Por seguridad legal (equipos robados/extraviados, posibles investigaciones), el bot NO da
# detalles, factibilidad, precios ni métodos sobre: FRP/bypass, cuentas Google/Apple/iCloud,
# PIN/patrón, liberación de compañía, MDM, IMEI y modificaciones de consolas.
# Solo responde un texto fijo: eso se verifica físicamente en el módulo.
#
# Módulo puro (sin red ni IA): se ejecuta ANTES de pricing y de Claude.

import re
import unicodedata

RESPUESTA_SENSIBLE = (
    "Ese tipo de servicio de software no se puede valorar por mensaje. "
    "El técnico lo revisa físicamente en el módulo para saber si es posible. "
    "¿Le comparto la ubicación y el horario? 😊"
)

# Si el cliente insiste después de la primera respuesta fija.
RESPUESTA_SENSIBLE_INSISTENTE = (
    "Para este tipo de servicio no podemos dar información por mensaje: "
    "es necesario que el técnico revise el equipo físicamente en el módulo. "
    "Aquí está la ubicación: https://maps.app.goo.gl/XdCSu743LpyY6aAt7"
)


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFD", (s or "").lower())
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return re.sub(r"\s+", " ", s).strip()


# Cerca = hasta ~40 caracteres entre dos términos (en cualquier orden)
def _cerca(a: str, b: str, n: int = 40) -> str:
    return rf"(?:{a}).{{0,{n}}}(?:{b})|(?:{b}).{{0,{n}}}(?:{a})"


_ACCION_QUITAR = r"quit\w+|elimin\w+|borr\w+|salt\w+|omit\w+|romp\w+|resete\w+|restablec\w+|formate\w+|desactiv\w+|sin\s+(?:cuenta|clave|contrasena|codigo)"
_ACCION_BLOQUEO = r"bloquead\w+|bloqueo|olvid\w+|no\s+recuerd\w+|no\s+me\s+acuerd\w+|no\s+se\s+la|no\s+tengo\s+la|no\s+puedo\s+(?:entrar|acceder|desbloquear)|pid\w+|candado|verific\w+|dueno|anterior|propietario|otra\s+persona"

_PATRONES = [
    # ── Celulares: FRP / bypass / cuentas ──
    r"\bfrp\b", r"\bby\s*-?\s*pass\w*",
    _cerca(r"cuenta\s+(?:de\s+)?(?:google|gmail)|google\s+account|cuenta\s+google|gmail",
           _ACCION_QUITAR + "|" + _ACCION_BLOQUEO),
    _cerca(r"icloud|apple\s*id|id\s+de\s+apple|cuenta\s+(?:de\s+)?apple|buscar\s+mi\s+iphone|find\s+my",
           _ACCION_QUITAR + "|" + _ACCION_BLOQUEO + r"|activacion|desbloq\w+|liber\w+|cuenta"),
    r"bloqueo\s+de\s+activacion", r"activation\s+lock",
    r"cuenta\s+(?:del\s+)?(?:dueno|propietario)\s+anterior", r"(?:dueno|propietario)\s+anterior",
    r"\bmdm\b", r"administracion\s+remota", r"\bknox\b",
    _cerca(r"cuenta\s+(?:de\s+)?(?:samsung|xiaomi|mi|huawei|oppo|vivo|realme|motorola)|mi\s+account|mi\s+cloud|huawei\s+id",
           _ACCION_QUITAR + "|" + _ACCION_BLOQUEO),
    # ── Celulares: PIN / patrón / contraseña de pantalla ──
    _cerca(_ACCION_QUITAR + r"|olvid\w+|no\s+recuerd\w+|no\s+me\s+acuerd\w+",
           r"patron|\bpin\b|contrasena\s+(?:de\s+)?(?:pantalla|bloqueo|celular|telefono|equipo)|codigo\s+de\s+(?:pantalla|desbloqueo|bloqueo)|bloqueo\s+de\s+(?:pantalla|seguridad)", 30),
    r"bloqueo\s+de\s+(?:pantalla|seguridad)",
    r"(?:cel|celular|telefono|equipo|iphone|tablet|ipad|tableta|consola|android)\w*\s+(?:esta\s+)?bloquead\w+",
    r"bloquead\w+\s+(?:por|con|de)\s+(?:compania|operador|google|apple|icloud|cuenta)",
    # ── Desbloqueo / liberación (excepto huella/rostro) ──
    r"desbloque\w+(?!.{0,25}(?:huella|facial|rostro|\bcara\b|face\s*id|touch\s*id|sensor|lector))",
    r"liber\w+\s+(?:el\s+|mi\s+|un\s+|este\s+|de\s+)?(?:cel\w*|telefono|equipo|iphone|samsung|android|compania|operador|telcel|at&?t|movistar|red|sim|linea)",
    r"(?:telcel|at&?t|movistar|compania|operador).{0,25}liber\w+",
    r"liberacion\s+(?:de\s+)?(?:cel\w*|telefono|equipo|iphone|compania|operador|red|telcel|at&?t|movistar)",
    r"network\s+unlock", r"sim\s*lock", r"libre\s+de\s+compania",
    # ── IMEI ──
    _cerca(r"imei", r"repar\w+|cambi\w+|modific\w+|clon\w+|borr\w+|alter\w+|reescrib\w+|reprogram\w+|bloquead\w+|reportad\w+|lista\s+negra|blacklist|invalid\w+|nulo|generico|desbloq\w+|liber\w+|limpi\w+"),
    # ── Root / firmware / bootloader en celulares ──
    r"\broot(?:ear|eo|eado|eada)?\b", r"bootloader", r"custom\s+rom", r"\bmagisk\b", r"jail\s*-?\s*bre?a?k\w*",
    # ── Consolas: modificaciones ──
    r"\bcfw\b", r"\bofw\b", r"custom\s+firmware", r"firmware\s+(?:modificado|custom|personalizado)",
    r"mod\s*-?\s*chip\w*", r"chipe\w+", r"\bhackea\w*", r"\bhackeo\b",
    r"\bmodea\w+", r"\bmodeo\b",
    r"modific\w+\s+(?:de\s+|la\s+|el\s+|mi\s+|una\s+)?(?:software|sistema|firmware|consola|cel\w*|telefono)",
    r"(?:software|sistema|firmware)\s+modific\w+",
    r"desban\w+", r"quitar\s+(?:el\s+)?ban\b", r"\bban(?:ead|eo|ear)\w*", r"ban\s+(?:online|de\s+(?:consola|xbox|playstation|psn|nintendo|live))",
    r"pirat\w+", r"multi\s*-?\s*juegos?",
    r"juegos?\s+(?:gratis|sin\s+pagar|sin\s+comprar|full|descargados|instalados|cargados|clonados)",
    r"(?:instal\w+|cargar|meter|poner|pasar)\s+(?:los\s+|unos\s+|mis\s+|varios\s+)?juegos",
    r"cambi\w+\s+(?:de\s+)?region", r"region\s*-?\s*free",
    r"\bsx\s*os\b", r"\batmosphere\b", r"\bhekate\b", r"\brcm\b", r"\bpayload\b", r"\bexploit\w*",
    r"(?:bajar|degradar|downgrade)\w*\s+(?:de\s+)?(?:version|firmware|sistema)", r"flash\w*\s+(?:la\s+)?(?:consola|lectora|rom)",
]

_RE_SENSIBLE = re.compile("|".join(f"(?:{p})" for p in _PATRONES))

# Seguimientos típicos tras un tema sensible ("¿y cuánto cuesta?", "¿se puede?", "¿cómo se hace?")
_RE_SEGUIMIENTO = re.compile(
    r"cuanto|precio|costo|cuesta|cobr\w+|se\s+puede|pueden|puedes|es\s+posible|posible|como\s+(?:se|lo|le)|"
    r"proceso|metodo|tardan|tiempo|garantia|lo\s+hacen|lo\s+hace|hacen\s+eso|hacen\s+ese|ese\s+servicio|eso\s+si|si\s+se\s+puede"
)


def es_consulta_sensible(texto: str) -> bool:
    """True si el mensaje pide/menciona una modificación de software o sistema sensible."""
    t = _norm(texto)
    return bool(t) and bool(_RE_SENSIBLE.search(t))


def _ultimos_mensajes_usuario(historial: list[dict], n: int = 2) -> list[str]:
    out = []
    for m in reversed(historial or []):
        if m.get("role") == "user":
            out.append(str(m.get("content", "")))
            if len(out) >= n:
                break
    return out


def _ya_se_respondio_sensible(historial: list[dict]) -> bool:
    for m in reversed(historial or []):
        if m.get("role") == "assistant":
            return RESPUESTA_SENSIBLE[:40] in str(m.get("content", "")) or RESPUESTA_SENSIBLE_INSISTENTE[:40] in str(m.get("content", ""))
    return False


def respuesta_sensible(mensaje: str, historial: list[dict] | None = None) -> str | None:
    """
    Devuelve el texto fijo si el mensaje (o su seguimiento inmediato) es una consulta sensible;
    None si no aplica. La 2ª vez seguida, devuelve la versión corta con la ubicación.
    """
    historial = historial or []
    sensible = es_consulta_sensible(mensaje)
    if not sensible:
        # Seguimiento: el tema sensible estaba en los últimos mensajes y esta pregunta es de precio/factibilidad/método
        t = _norm(mensaje)
        if t and _RE_SEGUIMIENTO.search(t) and any(es_consulta_sensible(u) for u in _ultimos_mensajes_usuario(historial, 2)):
            sensible = True
    if not sensible:
        return None
    return RESPUESTA_SENSIBLE_INSISTENTE if _ya_se_respondio_sensible(historial) else RESPUESTA_SENSIBLE
