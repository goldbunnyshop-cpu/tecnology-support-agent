# agent/sleep_mode.py — Gestor de horarios y modo reposo
# Verifica si el bot debe estar activo según la hora de atención

import logging
from datetime import datetime
from zoneinfo import ZoneInfo

logger = logging.getLogger("agentkit")

ZONA_MEXICO = ZoneInfo("America/Mexico_City")

# Horarios de atención configurados
HORARIOS_ATENCION = {
    "lunes": {"inicio": 10, "fin": 21},      # 10 AM a 9 PM
    "martes": {"inicio": 10, "fin": 21},
    "miercoles": {"inicio": 10, "fin": 21},
    "jueves": {"inicio": 10, "fin": 21},
    "viernes": {"inicio": 10, "fin": 21},
    "sabado": {"inicio": 11, "fin": 20},     # 11 AM a 8 PM
    "domingo": {"inicio": 11, "fin": 20},
}

DIAS_ES = {
    0: "lunes",
    1: "martes",
    2: "miercoles",
    3: "jueves",
    4: "viernes",
    5: "sabado",
    6: "domingo",
}


def esta_en_horario_atencion() -> bool:
    """
    Verifica si el bot está en horario de atención.

    Returns:
        True si está en horario, False si está fuera de horario
    """
    ahora = datetime.now(ZONA_MEXICO)
    dia_semana = ahora.weekday()  # 0=lunes, 6=domingo
    hora_actual = ahora.hour

    dia_nombre = DIAS_ES.get(dia_semana, "desconocido")
    horario = HORARIOS_ATENCION.get(dia_nombre)

    if not horario:
        logger.warning(f"[SLEEP] Día desconocido: {dia_nombre}")
        return False

    inicio = horario["inicio"]
    fin = horario["fin"]

    en_horario = inicio <= hora_actual < fin

    if not en_horario:
        logger.info(f"[SLEEP] ❌ FUERA DE HORARIO — {dia_nombre} {hora_actual:02d}:00 (horario: {inicio:02d}:00-{fin:02d}:00)")
    else:
        logger.debug(f"[SLEEP] ✅ En horario — {dia_nombre} {hora_actual:02d}:00")

    return en_horario


def obtener_mensaje_fuera_horario() -> str:
    """Retorna el mensaje cuando está fuera de horario"""
    ahora = datetime.now(ZONA_MEXICO)
    dia_semana = ahora.weekday()
    dia_nombre = DIAS_ES.get(dia_semana, "").capitalize()

    return f"""Hola 👋

Gracias por escribirnos. Ahorita estamos fuera de nuestro horario de atención.

**Nuestros horarios:**
📅 Lunes a Viernes: 10:00 AM a 9:00 PM
📅 Sábados y Domingos: 11:00 AM a 8:00 PM

Te responderemos con gusto cuando abramos. ¡Que tengas un excelente día! 😊"""


def obtener_horarios_proximos() -> str:
    """Retorna información del próximo horario de atención"""
    ahora = datetime.now(ZONA_MEXICO)
    dia_semana = ahora.weekday()

    # Si es viernes después de las 9 PM o fin de semana después de las 8 PM
    if dia_semana == 4 and ahora.hour >= 21:  # Viernes noche
        return "Abrimos el lunes a las 10:00 AM"
    elif dia_semana == 5 and ahora.hour >= 20:  # Sábado noche
        return "Abrimos el domingo a las 11:00 AM"
    elif dia_semana == 6 and ahora.hour >= 20:  # Domingo noche
        return "Abrimos el lunes a las 10:00 AM"
    elif ahora.hour < 10 and dia_semana < 5:  # Lunes-viernes antes de 10 AM
        return "Abrimos hoy a las 10:00 AM"
    elif ahora.hour < 11 and dia_semana >= 5:  # Sábado-domingo antes de 11 AM
        return "Abrimos hoy a las 11:00 AM"
    else:
        return "Estaremos disponibles en nuestro próximo horario de atención"
