# agent/venta_upgrade.py — Ventas de mejoras (ampliar memoria/almacenamiento, SSD, RAM…)
#
# Caso real (nov 2026): un cliente que cotizaba mantenimiento de PS5 pidió ampliar la memoria
# y el bot le sugirió comprar en Mercado Libre / Amazon. Tecnology Support SÍ vende e instala
# la pieza (es ganancia por reventa). Aquí se detecta la solicitud y se arma el aviso al grupo
# interno para que el técnico cotice; el bot NO se pausa y sigue con el servicio original.

import re
import unicodedata

_DISPOSITIVOS = [
    ("PS5", r"\bps\s*5\b|playstation\s*5"), ("PS4", r"\bps\s*4\b|playstation\s*4"),
    ("Xbox Series X", r"series\s*x"), ("Xbox Series S", r"series\s*s"), ("Xbox", r"\bxbox\b"),
    ("Nintendo Switch", r"\bswitch\b"), ("Laptop", r"\blaptop\b|\bnotebook\b|\bmacbook\b"),
    ("PC", r"\bpc\b|computadora|\bcpu\b"), ("Steam Deck", r"steam\s*deck"),
]
_SERVICIOS = [
    ("Mantenimiento", r"manten\w*|limpieza|pasta termica|se calienta|ruido"),
    ("Cambio de display", r"pantalla|display"), ("Batería", r"bateria"),
    ("Centro de carga", r"centro de carga|puerto de carga|no carga"),
    ("HDMI", r"\bhdmi\b"), ("Diagnóstico", r"diagnostico|no prende|no enciende"),
]

_PIEZA = r"(memoria|almacenamiento|espacio|ssd|nvme|m\.?\s*2|disco( duro| solido)?|\bram\b|gigas|\bgb\b|\btb\b|tera(byte)?s?)"
_ACCION = r"(ampli\w*|aument\w*|expand\w*|agreg\w*|anad\w*|pon(er|erle|gan)|instal\w*|cambi\w*|mejor\w*|actualiz\w*|subir|mas)"


def _norm(t: str) -> str:
    t = unicodedata.normalize("NFD", (t or "").lower())
    return "".join(c for c in t if unicodedata.category(c) != "Mn")


def es_solicitud_upgrade(texto: str) -> bool:
    """True si el cliente pide ampliar/instalar memoria, almacenamiento, SSD o RAM."""
    t = _norm(texto)
    if not t:
        return False
    if re.search(r"\b(ssd|nvme|m\.?\s*2)\b", t) and not re.search(r"\b(precio|cuanto)\b.*\bpantalla\b", t):
        return True
    if re.search(rf"{_ACCION}\W+(?:\w+\W+){{0,4}}{_PIEZA}", t):
        return True
    if re.search(rf"{_PIEZA}\W+(?:\w+\W+){{0,3}}(mas grande|de mas|extra|adicional)", t):
        return True
    return bool(re.search(r"\b(se (me )?lleno|sin espacio|no tengo espacio|ya no cabe|poco espacio)\b", t))


def _buscar(patrones, texto: str) -> str:
    t = _norm(texto)
    for nombre, patron in patrones:
        if re.search(patron, t):
            return nombre
    return ""


def mensaje_grupo_upgrade(telefono: str, texto: str, historial: list[dict] | None, asesor: str = "") -> str:
    """Aviso al grupo interno: oportunidad de venta + instalación."""
    contexto = " ".join(str(m.get("content", "")) for m in (historial or [])[-12:]) + " " + (texto or "")
    dispositivo = _buscar(_DISPOSITIVOS, texto) or _buscar(_DISPOSITIVOS, contexto) or "no especificado"
    servicio = _buscar(_SERVICIOS, contexto)
    tel = "".join(ch for ch in str(telefono) if ch.isdigit())
    lineas = [
        "🛒 *VENTA: AMPLIACIÓN / MEJORA*",
        f"📞 {tel} — wa.me/{tel}",
        f"📱 Equipo: {dispositivo}",
        f"💬 Pidió: \"{(texto or '').strip()[:200]}\"",
    ]
    if servicio:
        lineas.append(f"🔧 También cotiza: {servicio} (no perder este servicio)")
    if asesor:
        lineas.append(f"👨‍💼 Asesor: {asesor}")
    lineas.append("➡️ Cotizar pieza + instalación (al tipo de cambio de hoy) y mandarle el precio YA: el bot le dijo que en instantes se lo damos y está cerrando la cita.")
    return "\n".join(lineas)
