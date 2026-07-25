# agent/profile.py — Extracción de datos del cliente y construcción de contexto persistente

import json
import logging
import re

logger = logging.getLogger("agentkit")

_PATRONES_NOMBRE = [
    r"\bme llamo\s+([A-ZÁÉÍÓÚÑ][a-záéíóúñ]{2,}(?:\s+[A-ZÁÉÍÓÚÑ][a-záéíóúñ]{2,})?)",
    r"\bmi nombre es\s+([A-ZÁÉÍÓÚÑ][a-záéíóúñ]{2,}(?:\s+[A-ZÁÉÍÓÚÑ][a-záéíóúñ]{2,})?)",
    r"\bme dicen\s+([A-ZÁÉÍÓÚÑ][a-záéíóúñ]{2,})",
    r"\bsoy\s+([A-ZÁÉÍÓÚÑ][a-záéíóúñ]{2,})\b(?!\s+(?:el|la|un|una|tu|su))",
]

_FALSOS_POSITIVOS = {
    "Sofia", "Valentina", "Camila", "Diego", "Andres", "Rodrigo",
    "Tecnology", "Support", "Cliente", "Tecnico", "Hola", "Buenas",
}

_DISPOSITIVOS = [
    ("PS5",            ["ps5", "playstation 5"]),
    ("PS4",            ["ps4", "playstation 4"]),
    ("PS3",            ["ps3", "playstation 3"]),
    ("Xbox Series S",  ["xbox series s"]),
    ("Xbox One",       ["xbox one"]),
    ("Nintendo Switch",["switch", "nintendo switch"]),
    ("iPhone",         ["iphone"]),
    ("Samsung",        ["samsung"]),
    ("Laptop",         ["laptop", "lapto"]),
    ("PC",             ["computadora", "pc gamer", "desktop"]),
    ("Celular",        ["celular"]),  # "teléfono" eliminado — demasiado genérico (número de tel., etc.)
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


def extraer_nombre_de_historial_asistente(historial: list[dict]) -> str | None:
    """Busca en mensajes del asistente el nombre con el que ya saludó al cliente.
    Si el asesor ya dijo 'Hola, Juan' o '¡Hola Juan!' en algún turno, lo recupera.
    """
    for msg in historial:
        if msg.get("role") != "assistant":
            continue
        content = msg.get("content", "")
        matches = re.findall(
            r"(?:Hola|Hola,|¡Hola)\s*,?\s+([A-ZÁÉÍÓÚÑ][a-záéíóúñ]{2,})",
            content,
        )
        for m in matches:
            if m not in _FALSOS_POSITIVOS:
                return m
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
    Genera el bloque de contexto que va AL INICIO del system prompt (antes de las
    instrucciones del asesor) para que Claude lo lea primero y lo priorice.

    Para clientes con historial: instrucciones explícitas y fuertes de NO pedir nombre.
    Para clientes nuevos: retorna cadena vacía (asesor presenta normalmente).
    """
    # Sin perfil = cliente completamente nuevo
    if not perfil:
        return (
            "══ CLIENTE NUEVO ══\n"
            "No tienes información previa de este cliente. "
            "Preséntate con tu nombre y saluda normalmente.\n"
            "══════════════════"
        )

    # Recopilar datos disponibles
    nombre = perfil.nombre or ""

    dispositivos: list[str] = []
    try:
        dispositivos = json.loads(perfil.dispositivos_json or "[]")
    except (json.JSONDecodeError, TypeError):
        pass

    servicios: list[str] = []
    try:
        servicios = json.loads(perfil.servicios_json or "[]")
    except (json.JSONDecodeError, TypeError):
        pass

    ultima_visita = (
        perfil.ultima_visita.strftime("%d/%m/%Y") if perfil.ultima_visita else ""
    )
    asesor_anterior = perfil.asesor_ultimo or ""
    notas = perfil.notas or ""

    # Sin ningún dato útil (perfil vacío recién creado)
    tiene_datos = any([nombre, dispositivos, servicios, ultima_visita])
    if not tiene_datos:
        return (
            "══ CLIENTE NUEVO ══\n"
            "No tienes información previa de este cliente. "
            "Preséntate con tu nombre y saluda normalmente.\n"
            "══════════════════"
        )

    # ── Cliente con historial ─────────────────────────────────────────
    lineas = ["══ PERFIL DEL CLIENTE (PRIORIDAD MÁXIMA — LEE ANTES DE RESPONDER) ══"]

    if nombre:
        lineas.append(f"NOMBRE DEL CLIENTE: {nombre}")
        lineas.append(
            f"⛔ PROHIBIDO preguntar el nombre — ya lo tienes: {nombre}.\n"
            f"✅ Salúdalo directamente: '¡Hola {nombre}!' al inicio del mensaje."
        )
    else:
        lineas.append(
            "El cliente ya ha conversado antes pero aún no conoces su nombre. "
            "Si lo menciona en este mensaje, úsalo de inmediato."
        )

    if dispositivos:
        ultimo_disp = dispositivos[-1]
        lineas.append(f"Dispositivos que ha traído antes: {', '.join(dispositivos[-5:])}")
        lineas.append(
            f"⛔ PROHIBIDO preguntar qué equipo trajo si ya lo mencionó antes. "
            f"Su último dispositivo fue: {ultimo_disp}."
        )

    if servicios:
        lineas.append(f"Servicios realizados: {'; '.join(servicios[-3:])}")

    if ultima_visita:
        lineas.append(f"Última visita: {ultima_visita}")

    if asesor_anterior:
        lineas.append(f"Asesor que lo atendió antes: {asesor_anterior}")

    if notas:
        lineas.append(f"Notas importantes: {notas}")

    lineas.append(
        "\nCOMPORTAMIENTO OBLIGATORIO:\n"
        "• Si es la primera respuesta de esta sesión: saluda por nombre ('¡Hola [nombre]! "
        "Qué gusto verte de nuevo 😊 ¿En qué puedo ayudarte?')\n"
        "• NUNCA te presentes como si fuera la primera vez que hablan\n"
        "• NUNCA pidas datos que ya tienes (nombre, dispositivo, servicio anterior)\n"
        "• Si el cliente dice 'ya te dije mi nombre', responde con su nombre directamente"
    )

    lineas.append("══════════════════════════════════════════════════════════")

    return "\n".join(lineas)


def log_estado_memoria(telefono: str, perfil) -> None:
    """Emite el log de estado de memoria al inicio de cada conversación."""
    if not perfil or not any([
        perfil.nombre, perfil.ultima_visita,
        perfil.dispositivos_json and perfil.dispositivos_json != "[]",
    ]):
        logger.info(f"[MEMORIA] Cliente nuevo — {telefono} — sin historial previo")
        return

    dispositivos: list[str] = []
    try:
        dispositivos = json.loads(perfil.dispositivos_json or "[]")
    except (json.JSONDecodeError, TypeError):
        pass

    ultimo_disp = dispositivos[-1] if dispositivos else "—"
    ultima = perfil.ultima_visita.strftime("%d/%m/%Y") if perfil.ultima_visita else "—"

    logger.info(
        f"[MEMORIA] Cliente {telefono} — "
        f"nombre='{perfil.nombre or '?'}' "
        f"último_dispositivo='{ultimo_disp}' "
        f"última_visita={ultima} "
        f"asesor='{perfil.asesor_ultimo or '?'}'"
    )
