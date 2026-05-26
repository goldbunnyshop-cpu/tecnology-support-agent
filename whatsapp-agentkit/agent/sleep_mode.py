# agent/sleep_mode.py — Gestor de horarios y modo reposo (OPCIÓN 2)
# Verifica si el bot debe estar activo según la hora de operación
# Sleep mode: 00:00 - 5:59 AM (sin mostrar horarios al cliente)

import logging
import random
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

logger = logging.getLogger("agentkit")

ZONA_MEXICO = ZoneInfo("America/Mexico_City")

# ═══════════════════════════════════════════════════════════════════════════════
# HORARIO DE OPERACIÓN DEL BOT (interno) — Bot responde 24/7
# ═══════════════════════════════════════════════════════════════════════════════
HORARIOS_OPERACION_BOT = {
    "lunes": {"inicio": 6, "fin": 24},       # 6 AM - 23:59 PM
    "martes": {"inicio": 6, "fin": 24},
    "miercoles": {"inicio": 6, "fin": 24},
    "jueves": {"inicio": 6, "fin": 24},
    "viernes": {"inicio": 6, "fin": 24},
    "sabado": {"inicio": 6, "fin": 24},      # Bot activo (módulo cerrado)
    "domingo": {"inicio": 6, "fin": 24},     # Bot activo (módulo cerrado)
}

# ═══════════════════════════════════════════════════════════════════════════════
# HORARIO DEL MÓDULO (lo que mostramos al cliente)
# ═══════════════════════════════════════════════════════════════════════════════
HORARIOS_MODULO = {
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

# ═══════════════════════════════════════════════════════════════════════════════
# MENSAJES DE SLEEP MODE (3 variaciones aleatorias - Sin mostrar horas)
# ═══════════════════════════════════════════════════════════════════════════════
_MENSAJES_SLEEP_MODE = [
    "Hola, soy {asesor} de Technology Support 😊\nRecibí tu mensaje y créeme que estoy anotando todo para retomarlo cuando abramos.\nNuestro equipo retoma operaciones cuando iniciemos actividades.\n¡Te atenderé con prioridad en ese momento! Que descanses bien.",

    "Buenas noches, te habla {asesor} de Technology Support.\nHe registrado tu consulta y será atendida con prioridad cuando retomemos actividades.\nQueda todo anotado para darte seguimiento.\n¡Descansa, estamos aquí para ti! 🙏",

    "¡Hola! Soy {asesor}, asesora de Technology Support 😊\nAnotado tu mensaje — no se me olvida. Cuando retomemos operaciones serás de las primeras en ser atendida.\nQue descanses tranquila, ¡vuelvo con la solución!",
]

# ═══════════════════════════════════════════════════════════════════════════════
# MENSAJES DE REACTIVACIÓN (cuando el bot retoma después de 7 horas)
# ═══════════════════════════════════════════════════════════════════════════════
_MENSAJES_REACTIVACION = [
    "Gracias por tu paciencia, estamos dando prioridad a tu consulta. Dime qué problema presenta tu dispositivo 😊",
    "¡Hola de nuevo! Retomamos operaciones. Cuéntame, ¿sigue en pie tu consulta sobre tu dispositivo?",
    "Volvimos, estamos aquí para ayudarte. ¿Cuál era el problema que tenías con tu equipo?",
    "Hola 😊 Acá estamos. Voy a ayudarte con lo que comentaste antes. Adelante.",
]


def esta_en_horario_operacion_bot() -> bool:
    """
    Verifica si el bot está en horario de OPERACIÓN (6 AM - 23:59 PM).

    Returns:
        True si está en horario de operación, False si está en sleep mode (00:00 - 5:59 AM)
    """
    ahora = datetime.now(ZONA_MEXICO)
    dia_semana = ahora.weekday()  # 0=lunes, 6=domingo
    hora_actual = ahora.hour

    dia_nombre = DIAS_ES.get(dia_semana, "desconocido")
    horario = HORARIOS_OPERACION_BOT.get(dia_nombre)

    if not horario:
        logger.warning(f"[SLEEP] Día desconocido: {dia_nombre}")
        return False

    inicio = horario["inicio"]
    fin = horario["fin"]

    # Si hora < 6, estamos en sleep mode (00:00 - 5:59 AM)
    en_operacion = inicio <= hora_actual < fin

    if not en_operacion:
        logger.info(f"[SLEEP] 🌙 MODO REPOSO ACTIVADO — {dia_nombre} {hora_actual:02d}:00 (reactivación en 7 horas)")
    else:
        logger.debug(f"[SLEEP] ✅ Bot operativo — {dia_nombre} {hora_actual:02d}:00")

    return en_operacion


def obtener_mensaje_sleep_mode(asesor: str = "Sofia") -> str:
    """
    Retorna UN mensaje aleatorio de sleep mode (sin mostrar horas).

    Args:
        asesor: Nombre del asesor que atiende

    Returns:
        Mensaje personalizado sin mencionar horarios específicos
    """
    msg = random.choice(_MENSAJES_SLEEP_MODE)
    return msg.format(asesor=asesor)


def calcular_hora_reactivacion(ahora: datetime) -> datetime:
    """
    Calcula la hora de reactivación sumando 7 horas al timestamp actual.

    Args:
        ahora: datetime actual (cuando cliente escribió en sleep mode)

    Returns:
        datetime con +7 horas (hora en que bot reenviará mensaje)

    Ejemplo:
        Cliente escribe a 1:05 AM → retoma a 8:05 AM
        Cliente escribe a 0:20 AM → retoma a 7:20 AM
    """
    return ahora + timedelta(hours=7)


def obtener_mensaje_reactivacion() -> str:
    """
    Retorna UN mensaje aleatorio de reactivación (cuando bot contacta después de 7 horas).
    Se usa para enviar mensaje PROACTIVO después del sleep mode.

    Returns:
        Mensaje amigable sin mencionar horarios
    """
    return random.choice(_MENSAJES_REACTIVACION)


def obtener_horarios_modulo() -> str:
    """
    Retorna los horarios del MÓDULO (para cuando cliente PREGUNTA).
    Se mostra solo si el cliente lo solicita.

    Returns:
        String con horarios del módulo
    """
    return """📅 **Nuestros horarios:**
Lunes a Viernes: 10:00 AM a 9:00 PM
Sábados y Domingos: 11:00 AM a 8:00 PM
¡Abiertos los 7 días!"""


def obtener_horarios_proximos() -> str:
    """Retorna información del próximo horario de atención del módulo"""
    ahora = datetime.now(ZONA_MEXICO)
    dia_semana = ahora.weekday()

    # Si es viernes después de las 9 PM o fin de semana después de las 8 PM
    if dia_semana == 4 and ahora.hour >= 21:  # Viernes noche
        return "El módulo abre el lunes a las 10:00 AM"
    elif dia_semana == 5 and ahora.hour >= 20:  # Sábado noche
        return "El módulo abre el domingo a las 11:00 AM"
    elif dia_semana == 6 and ahora.hour >= 20:  # Domingo noche
        return "El módulo abre el lunes a las 10:00 AM"
    elif ahora.hour < 10 and dia_semana < 5:  # Lunes-viernes antes de 10 AM
        return "El módulo abre hoy a las 10:00 AM"
    elif ahora.hour < 11 and dia_semana >= 5:  # Sábado-domingo antes de 11 AM
        return "El módulo abre hoy a las 11:00 AM"
    else:
        return "El módulo estará disponible en su próximo horario de atención"
