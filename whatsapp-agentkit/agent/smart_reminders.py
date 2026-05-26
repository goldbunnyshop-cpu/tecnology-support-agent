"""
Smart Reminder Logic para seguimiento de citas
═══════════════════════════════════════════════

Maneja el scheduling inteligente de recordatorios basado en:
- Tiempo entre confirmación y cita
- Hora actual vs hora de recordatorio
- Evita enviar recordatorios cuyo horario ya pasó
"""

from datetime import datetime, timedelta
from typing import Optional
import logging

logger = logging.getLogger("agentkit.smart_reminders")


class ReminderSchedule:
    """Define qué recordatorios enviar basado en timing inteligente."""

    def __init__(self, fecha_cita: str, hora_cita: str, fecha_confirmacion: datetime = None):
        """
        Args:
            fecha_cita: Fecha de la cita (formato "YYYY-MM-DD")
            hora_cita: Hora de la cita (formato "HH:MM")
            fecha_confirmacion: Datetime cuando se confirmó la cita (default: now)
        """
        self.fecha_confirmacion = fecha_confirmacion or datetime.now()
        self.fecha_cita = fecha_cita
        self.hora_cita = hora_cita

        # Parsear fechas y horas
        self.cita_datetime = self._parsear_cita_datetime()
        self.tiempo_hasta_cita = self.cita_datetime - self.fecha_confirmacion

    def _parsear_cita_datetime(self) -> datetime:
        """Convierte fecha_cita + hora_cita a datetime object."""
        try:
            cita_str = f"{self.fecha_cita} {self.hora_cita}"
            return datetime.strptime(cita_str, "%Y-%m-%d %H:%M")
        except ValueError as e:
            logger.error(f"Error parseando cita: {e}")
            # Fallback: asumir fecha hoy
            hora_parts = self.hora_cita.split(":")
            return datetime.now().replace(
                hour=int(hora_parts[0]),
                minute=int(hora_parts[1]),
                second=0,
                microsecond=0
            )

    def debe_enviar_recordatorio_24h(self) -> bool:
        """
        LÓGICA INTELIGENTE: Enviar recordatorio 24 horas antes
        SOLO si la cita está MÁS DE 24 horas en el futuro.

        Ejemplo:
        - Hoy domingo confirma cita para lunes → NO envía (cita en ~24h)
        - Hoy domingo confirma cita para martes → SÍ envía (cita en ~48h)

        Returns:
            True si debe enviarse el recordatorio 24h antes
        """
        # Si la cita es en 24 horas o MENOS, no enviar este recordatorio
        # Usamos > en lugar de >= para permitir exactamente 24h (margen de ~2 minutos)
        if self.tiempo_hasta_cita <= timedelta(hours=24):
            logger.info(f"Cita en {self.tiempo_hasta_cita} — Saltando recordatorio 24h")
            return False

        logger.info(f"Cita en {self.tiempo_hasta_cita} — Enviando recordatorio 24h")
        return True

    def debe_enviar_recordatorio_90min(self) -> bool:
        """
        Recordatorio 90 minutos antes.
        SIEMPRE se envía UNLESS ya pasó la hora.

        Returns:
            True si debe enviarse (y su hora aún no ha pasado)
        """
        ahora = datetime.now()
        hora_recordatorio_90min = self.cita_datetime - timedelta(minutes=90)

        # Si la hora del recordatorio ya pasó, no enviar
        if ahora >= hora_recordatorio_90min:
            logger.info(f"Recordatorio 90min ya pasó ({hora_recordatorio_90min}) — No enviando")
            return False

        logger.info(f"Recordatorio 90min para {hora_recordatorio_90min} — Enviando")
        return True

    def debe_enviar_recordatorio_10min(self) -> bool:
        """
        Recordatorio 10 minutos antes.
        SIEMPRE se envía UNLESS ya pasó la hora.

        Returns:
            True si debe enviarse (y su hora aún no ha pasado)
        """
        ahora = datetime.now()
        hora_recordatorio_10min = self.cita_datetime - timedelta(minutes=10)

        # Si la hora del recordatorio ya pasó, no enviar
        if ahora >= hora_recordatorio_10min:
            logger.info(f"Recordatorio 10min ya pasó ({hora_recordatorio_10min}) — No enviando")
            return False

        logger.info(f"Recordatorio 10min para {hora_recordatorio_10min} — Enviando")
        return True

    def obtener_schedule_reminders(self) -> dict:
        """
        Retorna un dict con los recordatorios a programar.

        Returns:
            {
                "recordatorios": [
                    {"tipo": "24h", "enviar": bool, "datetime": datetime},
                    {"tipo": "90min", "enviar": bool, "datetime": datetime},
                    {"tipo": "10min", "enviar": bool, "datetime": datetime},
                ],
                "proxima_accion": datetime (más cercana),
                "resumen": str (human readable)
            }
        """

        ahora = datetime.now()

        # Calcular datetimes de cada recordatorio
        dt_24h = self.cita_datetime - timedelta(hours=24)
        dt_90min = self.cita_datetime - timedelta(minutes=90)
        dt_10min = self.cita_datetime - timedelta(minutes=10)

        # Evaluar qué enviar
        recordatorios = [
            {
                "tipo": "24h",
                "enviar": self.debe_enviar_recordatorio_24h(),
                "datetime": dt_24h,
                "mensajes": {
                    "titulo": "Recordatorio 24h antes",
                    "body": f"Tienes una cita el {self.fecha_cita} a las {self.hora_cita}"
                }
            },
            {
                "tipo": "90min",
                "enviar": self.debe_enviar_recordatorio_90min(),
                "datetime": dt_90min,
                "mensajes": {
                    "titulo": "Recordatorio 90 minutos",
                    "body": f"Tu cita es en 90 minutos (a las {self.hora_cita})"
                }
            },
            {
                "tipo": "10min",
                "enviar": self.debe_enviar_recordatorio_10min(),
                "datetime": dt_10min,
                "mensajes": {
                    "titulo": "Recordatorio 10 minutos",
                    "body": f"Tu cita es en 10 minutos"
                }
            }
        ]

        # Filtrar solo los que sí deben enviarse
        a_enviar = [r for r in recordatorios if r["enviar"]]

        # Próxima acción = el recordatorio más cercano
        proxima = min([r["datetime"] for r in a_enviar], default=None)

        # Resumen legible
        resumen = self._generar_resumen(recordatorios)

        return {
            "recordatorios": recordatorios,
            "proxima_accion": proxima,
            "resumen": resumen,
            "ahora": ahora,
            "cita_datetime": self.cita_datetime
        }

    def _generar_resumen(self, recordatorios: list) -> str:
        """Genera un resumen legible del plan de recordatorios."""
        lineas = [
            f"📅 Cita: {self.fecha_cita} a las {self.hora_cita}",
            f"⏱️ Tiempo hasta cita: {self.tiempo_hasta_cita}",
            "📢 Recordatorios:",
        ]

        for r in recordatorios:
            estado = "✅ ENVIAR" if r["enviar"] else "⏭️ SALTAR"
            lineas.append(f"  • {r['tipo']}: {estado}")

        return "\n".join(lineas)


# ════════════════════════════════════════════════════════════
# HELPERS para integración con el agente
# ════════════════════════════════════════════════════════════

def planificar_recordatorios_cita(
    telefono: str,
    fecha_cita: str,
    hora_cita: str,
    proveedor_whatsapp = None
) -> dict:
    """
    Planifica los recordatorios inteligentes para una cita confirmada.

    Esta función debería llamarse cuando la cita es CONFIRMADA.

    Args:
        telefono: Número de cliente
        fecha_cita: Fecha formato YYYY-MM-DD
        hora_cita: Hora formato HH:MM
        proveedor_whatsapp: Instancia del proveedor (opcional, para envío inmediato)

    Returns:
        Plan de recordatorios con timing y mensajes
    """

    schedule = ReminderSchedule(fecha_cita, hora_cita)
    plan = schedule.obtener_schedule_reminders()

    logger.info(f"Plan para {telefono}:\n{plan['resumen']}")

    # Aquí iría la lógica de almacenar en base de datos
    # para después usar un scheduler (APScheduler, Celery, etc)

    return plan


# ════════════════════════════════════════════════════════════
# TEST: Verificar lógica con ejemplos
# ════════════════════════════════════════════════════════════

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    print("\n🧪 TEST 1: Cita mañana (confirma hoy)")
    print("─" * 50)
    ahora = datetime.now()
    manana = (ahora + timedelta(days=1)).strftime("%Y-%m-%d")
    s1 = ReminderSchedule(manana, "15:00", ahora)
    plan1 = s1.obtener_schedule_reminders()
    print(plan1["resumen"])
    print(f"Próxima acción: {plan1['proxima_accion']}\n")

    print("🧪 TEST 2: Cita en 2 días (confirma hoy)")
    print("─" * 50)
    en_2_dias = (ahora + timedelta(days=2)).strftime("%Y-%m-%d")
    s2 = ReminderSchedule(en_2_dias, "10:00", ahora)
    plan2 = s2.obtener_schedule_reminders()
    print(plan2["resumen"])
    print(f"Próxima acción: {plan2['proxima_accion']}\n")

    print("🧪 TEST 3: Cita en 5 días (confirma hoy)")
    print("─" * 50)
    en_5_dias = (ahora + timedelta(days=5)).strftime("%Y-%m-%d")
    s3 = ReminderSchedule(en_5_dias, "14:30", ahora)
    plan3 = s3.obtener_schedule_reminders()
    print(plan3["resumen"])
    print(f"Próxima acción: {plan3['proxima_accion']}\n")
