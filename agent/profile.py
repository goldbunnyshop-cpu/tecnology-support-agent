# agent/profile.py — Extracción de datos del cliente y construcción de contexto persistente

import json
import logging
import re

logger = logging.getLogger("agentkit")

# Patrones para detectar que el cliente menciona su nombre en un mensaje
_PATRONES_NOMBRE = [
    r"\bme llamo\s+([A-ZÁÉÍÓÚÑ][a-záéíóúñ]{2,}(?:\s+[A-ZÁÉÍÓÚÑ][a-záéíóúñ]{2,})?)",
    r"\bmi nombre es\s+([A-ZÁÉÍÓÚÑ][a-záéíóúñ]{2,}(?:\s+[A-ZÁÉÍÓÚÑ][a-záéíóúñ]{2,})?)",
    r"\bme dicen\s+([A-ZÁÉÍÓÚÑ][a-záéíóúñ]{2,})",
    r"\bsoy\s+([A-ZÁÉÍÓÚÑ][a-záéíóúñ]{2,})\b(?!\s+(?:el|la|un|una|tu|su))",
]

# Nombres propios que NO son clientes (asesores, palabras comunes)
_FALSOS_POSITIVOS = {
    "Sofia", "Valentina", "Camila", "Diego", "Andres", "Rodrigo",
    "Tecnology", "Support", "Cliente", "Tecnico",
}

_DISPOSITIVOS = [
    ("PS5",           ["ps5", "playstation 5"]),
    ("PS4",           ["ps4", "playstation 4"]),
    ("PS3",           ["ps3", "playstation 3"]),
    ("Xbox Series S", ["xbox series s"]),
    ("Xbox One",      ["xbox one"]),
    ("Nintendo Switch",["switch", "nintendo switch"]),
    ("iPhone",        ["iphone"]),
    ("Samsung",       ["samsung"]),
    ("Laptop",        ["laptop", "lapto"]),
    ("PC",            ["computadora", "pc gamer", "desktop"]),
    ("Celular",       ["celular", "teléfono", "telefono"]),
]


def extraer_nombre_de_mensaje(texto: str) -> str | None:
    """Detecta si el cliente menciona su nombre en su propio mensaje."""
    if not texto:
        return None
    for patron in _PATRONES_NOMBRE:
        m = re.search(patron, texto, re.IGNORECASE)
        if m:
            nombre = m.group(1).strip().title()
            if nombre not in _FALSOS_POSITIVOS and len(nombre) >= 3:
                return nombre
    return None


def detectar_dispositivo_en_texto(texto: str) -> str | None:
    """Detecta el dispositivo mencionado en el texto del cliente."""
    if not texto:
        return None
    texto_lower = texto.lower()
    for nombre, keywords in _DISPOSITIVOS:
        if any(kw in texto_lower for kw in keywords):
            return nombre
    return None


def construir_contexto_cliente(perfil) -> str:
    """
    Genera el bloque de contexto que se inyecta en el system prompt
    para que el asesor conozca al cliente sin volver a preguntarle sus datos.
    """
    if not perfil:
        return ""

    partes = []

    if perfil.nombre:
        partes.append(f"Nombre: {perfil.nombre}")

    try:
        dispositivos = json.loads(perfil.dispositivos_json or "[]")
        if dispositivos:
            partes.append(f"Dispositivos que ha traído antes: {', '.join(dispositivos[-5:])}")
    except (json.JSONDecodeError, TypeError):
        pass

    try:
        servicios = json.loads(perfil.servicios_json or "[]")
        if servicios:
            partes.append(f"Servicios realizados: {'; '.join(servicios[-5:])}")
    except (json.JSONDecodeError, TypeError):
        pass

    if perfil.ultima_visita:
        partes.append(f"Última visita: {perfil.ultima_visita.strftime('%d/%m/%Y')}")

    if perfil.asesor_ultimo:
        partes.append(f"Asesor que lo atendió antes: {perfil.asesor_ultimo}")

    if perfil.notas:
        partes.append(f"Notas: {perfil.notas}")

    if not partes:
        return ""

    bloque = "\n".join(f"- {p}" for p in partes)
    return (
        "――― PERFIL DEL CLIENTE (información ya conocida) ―――\n"
        f"{bloque}\n"
        "REGLAS: No preguntes datos que ya tienes. Si el cliente dice "
        "'ya te dije mi nombre' o similar, respóndele directamente con su nombre. "
        "Usa su nombre de forma natural al saludar.\n"
        "―――――――――――――――――――――――――――――――――――――"
    )
