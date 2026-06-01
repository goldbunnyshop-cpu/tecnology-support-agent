# agent/commands_control.py — Control de números stopped (stop/on)
# Generado 1 de junio 2026

"""
Procesa comandos de control: stop/on para detener o reactivar números.
Ejecutados SOLO desde el grupo interno (Taller Interno TS).

Comando STOP:
  "stop: 5544554455"     → Agente detendrá de responder a ese número
  "Stop: 5544554455"     → Mismo efecto (case-insensitive)

Comando ON:
  "on: 5544554455"       → Agente reactivará respuestas a ese número
  "On: 5544554455"       → Mismo efecto (case-insensitive)

Resultado:
  - Número stopped: agente NO responde (silencio total)
  - Número on: agente retoma respuestas automáticas
"""

import logging
import re
from datetime import datetime
from agent.memory import (
    detener_numero,
    reactivar_numero,
    listar_numeros_stopped,
    numero_esta_stopped,
)

logger = logging.getLogger("agentkit")

# Patrones para detectar comandos
PATRON_STOP = re.compile(r"^\s*stop\s*:\s*(\d+)\s*$", re.IGNORECASE)
PATRON_ON = re.compile(r"^\s*on\s*:\s*(\d+)\s*$", re.IGNORECASE)
PATRON_STOPPED_LIST = re.compile(r"^\s*(?:stopped|list-stopped|stopped-list)\s*$", re.IGNORECASE)


async def procesar_comando_control(texto: str, emisor_telefono: str) -> tuple[bool, str | None]:
    """
    Procesa comandos stop/on si están presentes en el mensaje.
    Retorna (es_comando, respuesta).

    Si retorna (True, respuesta), el webhook debe responder con la respuesta
    y NO procesar el mensaje como contenido normal.

    Si retorna (False, None), el mensaje NO es un comando, procesar normalmente.
    """
    if not texto:
        return False, None

    # Intentar stop
    match_stop = PATRON_STOP.match(texto.strip())
    if match_stop:
        numero_target = match_stop.group(1)
        logger.info(f"[CMD] Comando STOP detectado: {numero_target} (ejecutado por {emisor_telefono})")
        exito, mensaje = await detener_numero(numero_target, razon="comando_stop", detenido_por=emisor_telefono)
        return True, mensaje

    # Intentar on
    match_on = PATRON_ON.match(texto.strip())
    if match_on:
        numero_target = match_on.group(1)
        logger.info(f"[CMD] Comando ON detectado: {numero_target} (ejecutado por {emisor_telefono})")
        exito, mensaje = await reactivar_numero(numero_target, reactivado_por=emisor_telefono)
        return True, mensaje

    # Intentar listar números stopped
    if PATRON_STOPPED_LIST.match(texto.strip()):
        logger.info(f"[CMD] Comando STOPPED-LIST detectado (ejecutado por {emisor_telefono})")
        stopped_list = await listar_numeros_stopped()
        if not stopped_list:
            respuesta = "📋 No hay números detenidos actualmente."
        else:
            respuesta = "📋 NÚMEROS DETENIDOS:\n\n"
            for i, s in enumerate(stopped_list, 1):
                fecha = datetime.fromisoformat(s["detenido_en"]).strftime("%d/%m %H:%M")
                respuesta += f"{i}. {s['numero']} — desde {fecha}\n   por: {s['detenido_por']}\n\n"
        return True, respuesta

    # No es un comando
    return False, None


async def validar_numero_activo(telefono: str) -> bool:
    """
    Retorna True si el número ESTÁ ACTIVO (puede recibir respuestas).
    Retorna False si el número está STOPPED (debe ser ignorado).

    Esta función DEBE llamarse en main.py ANTES de procesar el mensaje.
    """
    stopped = await numero_esta_stopped(telefono)
    if stopped:
        logger.warning(f"[STOP] Mensaje ignorado — {telefono} está DETENIDO (stopped)")
        return False
    return True
