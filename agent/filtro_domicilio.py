# agent/filtro_domicilio.py — Servicio a domicilio con cobertura de 8 km (regla del dueño)
#
# Reglas:
#   - SÍ hay servicio a domicilio. Por chat NUNCA se comparten precios: costo y cita se
#     concretan de forma manual con un responsable.
#   - Cobertura: 8 km en línea recta desde La Comer Tlalpan (tabla config/cobertura_domicilio.csv).
#   - El bot pide código postal o colonia (+ alcaldía) y clasifica:
#       dentro → "sí llegamos a su zona" + se transfiere a un responsable.
#       borde  → "lo validamos con el técnico", pide ubicación/dirección + se transfiere.
#       fuera / no se reconoce → se transfiere a un responsable. NUNCA se niega el servicio.
#   - Al transferir, main.py avisa al grupo interno y pausa el bot en ese chat.
#
# Módulo puro (sin red ni IA): se ejecuta ANTES de pricing y de Claude.

import csv
import os
import re
import unicodedata
from dataclasses import dataclass, field

# ── Textos al cliente ─────────────────────────────────────────────────────────

CARGO_DOMICILIO = 400        # cargo fijo por servicio a domicilio, sobre cualquier precio
DIAGNOSTICO = 200            # diagnóstico normal (bonificable); a domicilio = 200 + 400

NOTA_CARGO = (
    f"El servicio a domicilio tiene un cargo de ${CARGO_DOMICILIO} adicional al precio de la reparación "
    f"(si se requiere diagnóstico: ${DIAGNOSTICO} + ${CARGO_DOMICILIO} = ${DIAGNOSTICO + CARGO_DOMICILIO})."
)

RESPUESTA_DOMICILIO = (
    "¡Sí contamos con servicio a domicilio! 🏠 "
    "Para revisar la cobertura en su zona, ¿me comparte su código postal? "
    "Si no lo tiene a la mano, su colonia y alcaldía. "
    "Y de paso, ¿qué equipo es (marca y modelo) y qué falla tiene?"
)

RESPUESTA_PEDIR_CP = (
    "Para confirmarle la cobertura, ¿me comparte su código postal? "
    "Si no lo tiene a la mano, su colonia y alcaldía 😊"
)

RESPUESTA_AMBIGUA = (
    "Hay varias colonias con ese nombre en la ciudad. "
    "¿Me confirma su código postal o su alcaldía? 😊"
)

TXT_DENTRO = (
    "¡Perfecto, sí llegamos a {zona}! 🙌 "
    "Le transfiero con un responsable que concreta la cita a domicilio. "
    "En breve le escribe por este mismo chat."
)

TXT_BORDE = (
    "{zona_cap} queda en el límite de nuestra zona de servicio, así que lo validamos con el técnico. "
    "¿Nos comparte su ubicación por WhatsApp 📍 o su dirección? "
    "Le regresamos el mensaje con la información en breve."
)

TXT_FUERA = (
    "Le transfiero con un responsable para revisar su zona y cómo podemos atender su solicitud. "
    "En breve le escribe por este mismo chat 🙌"
)

# Marcas para reconocer en el historial lo que ya respondió el bot
_MARCA_INICIO = (RESPUESTA_DOMICILIO[:40], RESPUESTA_PEDIR_CP[:40], RESPUESTA_AMBIGUA[:40])
_MARCA_TRANSFERIDO = ("Le transfiero con un responsable", "lo validamos con el técnico")

_VENTANA_MODO = 12   # mensajes recientes del historial que se revisan

# ── Utilidades ────────────────────────────────────────────────────────────────


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFD", (s or "").lower())
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    s = re.sub(r"[^a-z0-9ñ ]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


# ── Detección de la consulta ──────────────────────────────────────────────────

# Solo cuenta si el que va/recoge es el NEGOCIO ("¿vienen a mi casa?", "¿pueden recogerlo?").
# Frases del cliente sobre sí mismo ("paso a recoger mi equipo", "tengo que ir a mi casa") NO activan.
_LUGAR = r"(?:mi |la |su )?(?:casa|domicilio|oficina|trabajo|negocio)"
_PUEDEN = r"\b(?:pued\w+|podri\w+|pudier\w+|se puede)\b (?:\w+ ){0,2}"
_PATRONES = [
    r"\ba domicilio\b",
    r"\bservicio (?:a|en) (?:domicilio|casa|mi casa|la casa|oficina|mi oficina)\b",
    rf"\b(?:van|vienen|vas|vienes|pasan|pasas|acuden|llegan|llegas) (?:a|hasta) {_LUGAR}\b",
    rf"{_PUEDEN}(?:venir|ir|pasar|acudir|llegar) (?:a|hasta) {_LUGAR}\b",
    r"\b(?:recogen|recoges|pasan por|pasas por|van por|vienen por) (?:el |mi |la |los |las )?(?:equipo|cel\w*|telefono|laptop|compu\w*|consola|tablet\w*|ipad|iphone|control)\w*",
    rf"{_PUEDEN}(?:recoger\w*|pasar por|ir por|venir por)\b",
    r"\b(?:atienden|reparan|arreglan|trabajan|hacen (?:el )?servicio) (?:a|en) (?:domicilio|casa)\b",
    rf"\btecnico\b.{{0,25}}\b(?:viene|va|puede ir|puede venir|pasa) (?:a|hasta) {_LUGAR}\b",
    r"\bhome service\b",
]
# El cliente dice que él va al módulo / no quiere domicilio → no se activa y se sale del modo domicilio
_RE_DECLINA = re.compile(
    r"\b(?:yo paso|yo voy|yo la llevo|yo lo llevo|la llevo|lo llevo|paso (?:a|al|por|mas tarde|en la)|"
    r"voy (?:al|a la|para alla|para el)|no hay (?:alguien|nadie)|prefiero (?:ir|pasar|llevar)|"
    r"no (?:quiero|necesito) (?:el servicio )?a domicilio|mejor (?:voy|paso|la llevo|lo llevo))\b"
)
_RE_DOMICILIO = re.compile("|".join(f"(?:{p})" for p in _PATRONES))

_RE_PRECIO = re.compile(
    r"cuanto|precio|costo|cuesta|cobr\w+|cotiz\w+|presupuesto|aproximad\w+|mas o menos|rango|tarifa"
)


def es_consulta_domicilio(texto: str) -> bool:
    """True si el mensaje pregunta/pide servicio a domicilio."""
    t = _norm(texto)
    return bool(t) and bool(_RE_DOMICILIO.search(t)) and not _RE_DECLINA.search(t)


# ── Tabla de cobertura ────────────────────────────────────────────────────────

_RUTA_CSV = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                         "config", "cobertura_domicilio.csv")

ALCALDIAS = {
    "alvaro obregon": "Álvaro Obregón", "azcapotzalco": "Azcapotzalco", "benito juarez": "Benito Juárez",
    "coyoacan": "Coyoacán", "cuajimalpa": "Cuajimalpa de Morelos", "cuauhtemoc": "Cuauhtémoc",
    "gustavo a madero": "Gustavo A. Madero", "gam": "Gustavo A. Madero", "iztacalco": "Iztacalco",
    "iztapalapa": "Iztapalapa", "magdalena contreras": "La Magdalena Contreras", "contreras": "La Magdalena Contreras",
    "miguel hidalgo": "Miguel Hidalgo", "milpa alta": "Milpa Alta", "tlahuac": "Tláhuac",
    "tlalpan": "Tlalpan", "venustiano carranza": "Venustiano Carranza", "xochimilco": "Xochimilco",
}
# Fuera de CDMX → siempre se transfiere
_RE_FUERA_CDMX = re.compile(
    r"\b(?:estado de mexico|edomex|edo mex|naucalpan|ecatepec|nezahualcoyotl|neza|tlalnepantla|"
    r"huixquilucan|chalco|ixtapaluca|chimalhuacan|tecamac|cuautitlan|coacalco|atizapan|"
    r"la paz|texcoco|toluca|metepec|morelos|cuernavaca|tepoztlan|puebla|queretaro|hidalgo|pachuca)\b"
)

# Nombres de colonia demasiado genéricos para reconocerlos solos en un texto libre
_COLONIAS_GENERICAS = {
    "centro", "ejido", "la joya", "las aguilas", "el mirador", "la presa", "los reyes", "la palma",
    "la cruz", "el rosario", "san juan", "san jose", "san miguel", "san pedro", "san pablo",
    "san antonio", "san francisco", "santa cruz", "santa maria", "el carmen",
    "la loma", "la era", "el arenal", "la cantera", "las flores", "jardines", "guadalupe",
    "fuentes", "loma bonita", "lomas", "los olivos", "la estrella", "el ocote", "la otra banda",
    "ampliacion", "barrio", "pueblo", "unidad", "infonavit", "residencial", "granjas",
}


@dataclass
class _ZonaCP:
    cp: str
    alcaldia: str
    cobertura: str  # dentro | borde | fuera
    colonias: list = field(default_factory=list)


_CPS: dict[str, _ZonaCP] = {}
_COLONIAS: dict[str, list[tuple[str, str]]] = {}   # nombre normalizado → [(cp, nombre original)]


def _cargar():
    if _CPS:
        return
    with open(_RUTA_CSV, encoding="utf-8") as fh:
        lineas = [l for l in fh if not l.startswith("#")]
    for r in csv.DictReader(lineas):
        cols = [c for c in (r["colonias"] or "").split("|") if c]
        _CPS[r["cp"]] = _ZonaCP(r["cp"], r["alcaldia"], r["cobertura"], cols)
        for c in cols:
            n = _norm(c)
            # Fuera: nombres muy cortos o genéricos, y colonias que se llaman igual que una alcaldía
            # ("Tlalpan", "Cuauhtémoc"...) porque el cliente casi siempre se refiere a la alcaldía.
            if (len(n) >= 4 and not n.isdigit() and n not in _COLONIAS_GENERICAS
                    and n not in ALCALDIAS and n not in {_norm(v) for v in ALCALDIAS.values()}):
                _COLONIAS.setdefault(n, []).append((r["cp"], c))


@dataclass
class Ubicacion:
    cobertura: str          # dentro | borde | fuera | ambigua
    zona: str = ""          # texto para el cliente, ej. "la colonia Toriello Guerra (Tlalpan)"
    cp: str = ""
    alcaldia: str = ""
    colonia: str = ""


def _zona_texto(colonia: str, cp: str, alcaldia: str) -> str:
    if colonia:
        return f"la colonia {colonia} ({alcaldia})" if alcaldia else f"la colonia {colonia}"
    return f"el C.P. {cp} ({alcaldia})" if alcaldia else f"el C.P. {cp}"


def resolver_ubicacion(texto: str) -> Ubicacion | None:
    """Busca CP, colonia o alcaldía en el texto. None si no reconoce ninguna ubicación."""
    _cargar()
    t = _norm(texto)
    if not t:
        return None

    # 1) Código postal (5 dígitos)
    for cp in re.findall(r"(?<!\d)(\d{5})(?!\d)", t):
        z = _CPS.get(cp)
        if z:
            col = z.colonias[0] if len(z.colonias) == 1 else ""
            return Ubicacion(z.cobertura, _zona_texto(col, cp, z.alcaldia), cp, z.alcaldia, col)
        return Ubicacion("fuera", f"el C.P. {cp}", cp)   # CP fuera de la tabla (otro estado o nuevo) → transferir

    # 2) Alcaldía mencionada (sirve para filtrar colonias)
    alcaldia = ""
    for clave in sorted(ALCALDIAS, key=len, reverse=True):
        if re.search(rf"\b{clave}\b", t):
            alcaldia = ALCALDIAS[clave]
            break

    # 3) Colonia (coincidencia de nombre completo, la más larga gana)
    encontrados = [n for n in _COLONIAS if re.search(rf"\b{re.escape(n)}\b", t)]
    encontrados = [n for n in encontrados if not any(n != m and n in m for m in encontrados)]
    if encontrados:
        # Incluir colonias cuyo nombre CONTIENE el encontrado ("Ajusco" → también "Santo Tomás Ajusco",
        # "San Miguel Ajusco"): si quedan con distinta cobertura, se pide CP en vez de adivinar.
        extendidos = {m for n in encontrados for m in _COLONIAS if re.search(rf"\b{re.escape(n)}\b", m)}
        candidatos = [(cp, nom) for n in extendidos for cp, nom in _COLONIAS[n]]
        if alcaldia:
            filtrados = [(cp, nom) for cp, nom in candidatos if _CPS[cp].alcaldia == alcaldia]
            candidatos = filtrados or candidatos
        coberturas = {_CPS[cp].cobertura for cp, _ in candidatos}
        alcaldias = {_CPS[cp].alcaldia for cp, _ in candidatos}
        if len(coberturas) == 1:
            # Para el texto al cliente, preferir la colonia que escribió tal cual
            exactos = [(cp, nom) for cp, nom in candidatos if _norm(nom) in encontrados]
            cp, nom = (exactos or candidatos)[0]
            alc = alcaldias.pop() if len(alcaldias) == 1 else ""
            cp_unico = cp if len({c for c, _ in candidatos}) == 1 else ""
            return Ubicacion(coberturas.pop(), _zona_texto(nom, cp_unico, alc), cp_unico, alc, nom)
        nom = next((n for _, n in candidatos if _norm(n) in encontrados), candidatos[0][1])
        return Ubicacion("ambigua", _zona_texto(nom, "", ""), colonia=nom)

    # 4) Fuera de CDMX mencionado explícitamente
    if _RE_FUERA_CDMX.search(t):
        return Ubicacion("fuera", "su zona")

    # 5) Solo alcaldía: no alcanza (ej. Tlalpan llega hasta el Ajusco) → hay que pedir CP/colonia
    if alcaldia:
        return Ubicacion("ambigua", alcaldia, alcaldia=alcaldia)
    return None


# ── Cargo por servicio a domicilio ($400 sobre cualquier precio) ──────────────

_RE_MONTO = re.compile(r"\$\s?(\d{1,3}(?:,\d{3})+|\d+)(?:\.\d{2})?(?:\s?MXN)?")
_MARCA_DESGLOSE = "servicio a domicilio $"


def _precios_en_texto(texto: str) -> list[tuple[str, int]]:
    """[(etiqueta, monto)] por cada precio del texto. Etiqueta = lo que va antes del precio en su línea."""
    out = []
    for linea in (texto or "").splitlines():
        for mt in _RE_MONTO.finditer(linea):
            monto = int(mt.group(1).replace(",", ""))
            if monto < 50 or monto == CARGO_DOMICILIO and "domicilio" in linea.lower():
                continue
            etiqueta = re.sub(r"^[\s*•\-✅📱🔧]+", "", linea[:mt.start()]).strip(" :=-—")
            out.append((etiqueta[:60], monto))
    return out


def texto_desglose(texto: str) -> str:
    """Desglose 'precio + $400 = total' para cada precio del texto ('' si no hay precios)."""
    items = _precios_en_texto(texto)[:8]
    if not items:
        return ""
    if len(items) == 1:
        et, m = items[0]
        return f"${m:,} + {_MARCA_DESGLOSE}{CARGO_DOMICILIO} = *${m + CARGO_DOMICILIO:,} MXN*"
    lineas = [f"🏠 A domicilio (+{_MARCA_DESGLOSE}{CARGO_DOMICILIO}):"]
    for et, m in items:
        lineas.append(f"* {et + ': ' if et else ''}${m:,} + ${CARGO_DOMICILIO} = *${m + CARGO_DOMICILIO:,} MXN*")
    return "\n".join(lineas)


def agregar_cargo_domicilio(respuesta: str) -> str:
    """Agrega al final de una cotización el desglose con el cargo a domicilio (si tiene precios)."""
    if not respuesta or _MARCA_DESGLOSE in respuesta:
        return respuesta
    d = texto_desglose(respuesta)
    if not d:
        return respuesta
    if "\n" not in d:
        d = f"🏠 A domicilio: {d}"
    return f"{respuesta.rstrip()}\n\n{d}"


def _ultima_cotizacion(historial: list[dict] | None) -> str:
    """Último mensaje del bot con precios (que no sea un texto de domicilio)."""
    for m in reversed(list(historial or [])[-_VENTANA_MODO:]):
        c = str(m.get("content", ""))
        if m.get("role") == "assistant" and _RE_MONTO.search(c) and _MARCA_DESGLOSE not in c:
            return c
    return ""


INSTRUCCION_CLAUDE = (
    "⚠️ NOTA SISTEMA — SERVICIO A DOMICILIO: este cliente pidió servicio a domicilio. "
    f"A CUALQUIER precio que menciones súmale ${CARGO_DOMICILIO} y muéstralo con desglose, ej.: "
    f"\"Mantenimiento PS5 $1,400 + servicio a domicilio ${CARGO_DOMICILIO} = $1,800 MXN\". "
    f"Diagnóstico a domicilio: ${DIAGNOSTICO} + ${CARGO_DOMICILIO} = ${DIAGNOSTICO + CARGO_DOMICILIO} MXN. "
    "No confirmes fecha ni hora de la visita: eso lo concreta un responsable."
)


# ── Estado de la conversación ─────────────────────────────────────────────────


def _asistente_reciente(historial: list[dict] | None) -> list[str]:
    return [str(m.get("content", "")) for m in list(historial or [])[-_VENTANA_MODO:] if m.get("role") == "assistant"]


def en_modo_domicilio(historial: list[dict] | None) -> bool:
    """True si la conversación reciente es de servicio a domicilio y el cliente no lo declinó después."""
    recientes = list(historial or [])[-_VENTANA_MODO:]
    ult = -1
    for i, m in enumerate(recientes):
        if m.get("role") == "assistant" and any(mk in str(m.get("content", "")) for mk in _MARCA_INICIO + _MARCA_TRANSFERIDO):
            ult = i
    if ult < 0:
        return False
    return not any(m.get("role") == "user" and _RE_DECLINA.search(_norm(str(m.get("content", ""))))
                   for m in recientes[ult + 1:])


def ya_transferido(historial: list[dict] | None) -> bool:
    return any(any(mk in c for mk in _MARCA_TRANSFERIDO) for c in _asistente_reciente(historial))


def _veces_pedido_ubicacion(historial: list[dict] | None) -> int:
    marcas = _MARCA_INICIO
    return sum(1 for c in _asistente_reciente(historial) if any(mk in c for mk in marcas))


@dataclass
class DecisionDomicilio:
    texto: str
    transferir: bool = False
    ubicacion: Ubicacion | None = None


def _decision_por_ubicacion(u: Ubicacion) -> DecisionDomicilio:
    if u.cobertura == "dentro":
        return DecisionDomicilio(TXT_DENTRO.format(zona=u.zona).replace(" a el ", " al "), True, u)
    if u.cobertura == "borde":
        zona_cap = u.zona[:1].upper() + u.zona[1:]
        return DecisionDomicilio(TXT_BORDE.format(zona_cap=zona_cap), True, u)
    return DecisionDomicilio(TXT_FUERA, True, u)


def _bloque_cargo(historial: list[dict] | None) -> str:
    """Desglose de la última cotización + $400, o la nota general del cargo si no hay cotización."""
    desglose = texto_desglose(_ultima_cotizacion(historial))
    if desglose:
        if "\n" not in desglose:
            return f"Con lo que le cotizamos, a domicilio quedaría: {desglose}"
        return desglose
    return NOTA_CARGO


def evaluar_domicilio(mensaje: str, historial: list[dict] | None = None) -> DecisionDomicilio | None:
    """
    Decide la respuesta de servicio a domicilio. None si no aplica (sigue el flujo normal).
    Si .transferir es True, main.py debe avisar al grupo interno y pausar el chat.
    """
    historial = historial or []
    if ya_transferido(historial):
        return None   # ya lo atiende un responsable; si el bot se reanudó, sigue normal (sin precios)

    if _RE_DECLINA.search(_norm(mensaje)):
        return None   # "yo paso", "la llevo al módulo"... → flujo normal
    modo = en_modo_domicilio(historial)
    if not modo and not es_consulta_domicilio(mensaje):
        return None

    u = resolver_ubicacion(mensaje)
    if u and u.cobertura in ("dentro", "borde", "fuera"):
        d = _decision_por_ubicacion(u)
        if not modo and u.cobertura != "fuera":
            # Pidió domicilio y dio su zona en el mismo mensaje: incluir el cargo en el mensaje
            d.texto = f"{d.texto}\n\n{_bloque_cargo(historial)}"
        return d

    if not modo:
        # Primera vez: confirmar servicio, informar el cargo (con desglose si ya se cotizó) y pedir CP
        return DecisionDomicilio(f"{RESPUESTA_DOMICILIO}\n\n{_bloque_cargo(historial)}")

    # Ya en modo domicilio y no se pudo ubicar
    if _veces_pedido_ubicacion(historial) >= 2:
        return DecisionDomicilio(TXT_FUERA, True, u)   # no se queda atorado: lo ve un responsable
    if _RE_PRECIO.search(_norm(mensaje)):
        return None   # pregunta de precio: la contesta el flujo normal y brain.py suma el cargo
    if u and u.cobertura == "ambigua":
        return DecisionDomicilio(RESPUESTA_AMBIGUA if u.colonia else RESPUESTA_PEDIR_CP)
    return DecisionDomicilio(RESPUESTA_PEDIR_CP)


def respuesta_domicilio(mensaje: str, historial: list[dict] | None = None) -> str | None:
    """Compatibilidad (brain.py / Messenger): solo el texto de la decisión."""
    d = evaluar_domicilio(mensaje, historial)
    return d.texto if d else None


def mensaje_grupo_domicilio(telefono: str, d: DecisionDomicilio, historial: list[dict], mensaje: str) -> str:
    """Aviso para el grupo interno cuando se transfiere un cliente de domicilio."""
    num = re.sub(r"\D", "", telefono or "")
    u = d.ubicacion
    etiqueta = {"dentro": "✅ DENTRO de 8 km", "borde": "⚠️ BORDE (validar con técnico)",
                "fuera": "🔁 FUERA / sin ubicar (revisar si se cubre)"}.get(u.cobertura if u else "fuera",
                                                                         "🔁 FUERA / sin ubicar (revisar si se cubre)")
    zona = []
    if u:
        if u.colonia: zona.append(f"Col. {u.colonia}")
        if u.cp: zona.append(f"C.P. {u.cp}")
        if u.alcaldia: zona.append(u.alcaldia)
    msgs_cliente = [str(m.get("content", "")) for m in historial if m.get("role") == "user"][-4:] + [mensaje]
    resumen = "\n".join(f"  • {m[:150]}" for m in msgs_cliente if m.strip())
    return (
        f"🏠 *SERVICIO A DOMICILIO — atender manualmente*\n"
        f"📱 {num}\n"
        f"📍 {', '.join(zona) or 'sin ubicación clara'}\n"
        f"📏 {etiqueta}\n"
        f"💬 Lo que escribió el cliente:\n{resumen}\n\n"
        f"💲 Se le informó el cargo a domicilio de ${CARGO_DOMICILIO} sobre el precio de la reparación.\n"
        f"⏸️ Bot pausado en este chat 24 h.\n"
        f"Para reactivar el bot: *reanudar: {num}*"
    )
