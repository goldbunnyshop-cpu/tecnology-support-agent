# agent/leads.py — Seguimiento de leads y funnel de conversión
# Generado por AgentKit

import logging
import random
import re
from datetime import datetime, timedelta
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import String, DateTime, Integer, select, update, text
from agent.memory import Base, async_session, engine

logger = logging.getLogger("agentkit")


ASESORES = ["Sofia", "Valentina", "Camila", "Isabella", "Daniela", "Valeria"]


class Lead(Base):
    """Registra cada cliente que inicia conversación y su estado en el funnel."""
    __tablename__ = "leads"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    telefono: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    ultimo_mensaje: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    seguimientos_enviados: Mapped[int] = mapped_column(Integer, default=0)
    seguimiento_enviado_en: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    seguimiento_realizado: Mapped[bool] = mapped_column(default=False)
    prioridad: Mapped[str] = mapped_column(String(20), default="medio")
    estado: Mapped[str] = mapped_column(String(30), default="activo")
    fuente: Mapped[str] = mapped_column(String(50), default="desconocido")
    fuente_detalle: Mapped[str] = mapped_column(String(200), default="")
    asesor_asignado: Mapped[str] = mapped_column(String(50), default="")
    retoma_en: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    retoma_desde: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    presupuesto_enviado_en: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


async def _migrar_columnas():
    """Agrega columnas nuevas si no existen (migración segura sin perder datos)."""
    from agent.memory import _USANDO_SQLITE
    tipo_fecha = "DATETIME" if _USANDO_SQLITE else "TIMESTAMP"
    bool_false = "BOOLEAN DEFAULT 0" if _USANDO_SQLITE else "BOOLEAN DEFAULT false"
    for columna, definicion in [
        ("fuente",                  "VARCHAR(50) DEFAULT 'desconocido'"),
        ("fuente_detalle",          "VARCHAR(200) DEFAULT ''"),
        ("asesor_asignado",         "VARCHAR(50) DEFAULT ''"),
        ("retoma_en",               tipo_fecha),
        ("retoma_desde",            tipo_fecha),
        ("presupuesto_enviado_en",  tipo_fecha),
        ("seguimiento_enviado_en",   tipo_fecha),
        ("seguimiento_realizado",    bool_false),
        ("prioridad",               "VARCHAR(20) DEFAULT 'medio'"),
    ]:
        # Una transacción POR columna: en Postgres un ALTER que falla (columna ya
        # existe) aborta toda la transacción; aislándolos, los demás siguen.
        try:
            async with engine.begin() as conn:
                await conn.execute(text(f"ALTER TABLE leads ADD COLUMN {columna} {definicion}"))
        except Exception:
            pass  # columna ya existe


async def obtener_o_asignar_asesor(telefono: str) -> str:
    """
    Retorna el asesor asignado al cliente.
    - Cliente nuevo o sin asesor: asigna uno aleatorio.
    - Cliente con asesor y actividad < 72h: devuelve el mismo.
    - Cliente inactivo >= 72h: asigna uno diferente al anterior.
    IMPORTANTE: llamar ANTES de crear_o_actualizar_lead para usar el ultimo_mensaje previo.
    """
    async with async_session() as session:
        result = await session.execute(select(Lead).where(Lead.telefono == telefono))
        lead = result.scalar_one_or_none()

        if lead is None:
            asesor = random.choice(ASESORES)
            logger.info(f"[ASESOR] Cliente nuevo {telefono} → asignado: {asesor}")
            return asesor

        asesor_actual = lead.asesor_asignado or ""
        ultimo = lead.ultimo_mensaje or datetime.utcnow()
        inactivo_72h = (datetime.utcnow() - ultimo) >= timedelta(hours=72)

        if asesor_actual and not inactivo_72h:
            logger.info(f"[ASESOR] {telefono} → mantiene asesor: {asesor_actual}")
            return asesor_actual

        opciones = [a for a in ASESORES if a != asesor_actual] or ASESORES
        nuevo = random.choice(opciones)
        logger.info(f"[ASESOR] {telefono} → inactivo 72h, cambio: {asesor_actual or '(sin asignar)'} → {nuevo}")
        await session.execute(
            update(Lead).where(Lead.telefono == telefono).values(asesor_asignado=nuevo)
        )
        await session.commit()
        return nuevo


async def crear_o_actualizar_lead(
    telefono: str,
    fuente: str = "desconocido",
    fuente_detalle: str = "",
    asesor_asignado: str = "",
):
    """Crea el lead si es nuevo, o actualiza su timestamp si ya existe."""
    async with async_session() as session:
        result = await session.execute(select(Lead).where(Lead.telefono == telefono))
        lead = result.scalar_one_or_none()
        if lead:
            lead.ultimo_mensaje = datetime.utcnow()
            if lead.estado in ("en_seguimiento", "perdido", "noshow"):
                # Cliente volvió a escribir → reactivar secuencia de seguimiento
                lead.estado = "activo"
                lead.seguimientos_enviados = 0
                lead.seguimiento_enviado_en = None
                lead.seguimiento_realizado = False  # el cliente respondió, puede recibir seguimiento nuevo
            if fuente != "desconocido" and lead.fuente == "desconocido":
                lead.fuente = fuente
                lead.fuente_detalle = fuente_detalle
            if asesor_asignado and not lead.asesor_asignado:
                lead.asesor_asignado = asesor_asignado
        else:
            lead = Lead(
                telefono=telefono,
                fuente=fuente,
                fuente_detalle=fuente_detalle,
                asesor_asignado=asesor_asignado,
            )
            session.add(lead)
        await session.commit()


async def programar_retoma(telefono: str, retoma_en_utc: datetime, desde_utc: datetime):
    """Registra una retoma nocturna programada para este lead."""
    async with async_session() as session:
        await session.execute(
            update(Lead).where(Lead.telefono == telefono).values(
                retoma_en=retoma_en_utc,
                retoma_desde=desde_utc,
            )
        )
        await session.commit()


async def cancelar_retoma(telefono: str):
    """Cancela la retoma programada (cliente ya respondió)."""
    async with async_session() as session:
        await session.execute(
            update(Lead).where(Lead.telefono == telefono).values(
                retoma_en=None,
                retoma_desde=None,
            )
        )
        await session.commit()


async def obtener_retomas_pendientes() -> list[Lead]:
    """Devuelve leads cuya retoma programada ya venció."""
    ahora = datetime.utcnow()
    async with async_session() as session:
        result = await session.execute(
            select(Lead).where(
                Lead.retoma_en.isnot(None),
                Lead.retoma_en <= ahora,
            )
        )
        return list(result.scalars().all())


# Intervalos de seguimiento por número de seguimientos ya enviados
# (0 = primer seguimiento pendiente, 1 = segundo, etc.)
_INTERVALOS_SEGUIMIENTO = {
    0: timedelta(hours=2),    # Seg 1: 2h desde el último mensaje del cliente
    1: timedelta(hours=24),   # Seg 2: 24h desde que se envió el seguimiento 1
    2: timedelta(hours=72),   # Seg 3: 72h (3 días) desde que se envió el seguimiento 2
    3: timedelta(days=7),     # Seg 4: 7 días desde que se envió el seguimiento 3
}
MAX_SEGUIMIENTOS = 4


async def obtener_leads_para_seguimiento() -> list[Lead]:
    """
    Retorna TODOS los leads que necesitan seguimiento ahora.

    Criterios por número de seguimientos enviados:
      0 enviados → esperar 2h  desde Lead.ultimo_mensaje
      1 enviado  → esperar 24h desde Lead.seguimiento_enviado_en
      2 enviados → esperar 36h desde Lead.seguimiento_enviado_en
      3 enviados → esperar 7d  desde Lead.seguimiento_enviado_en
    """
    ahora = datetime.utcnow()
    async with async_session() as session:
        result = await session.execute(
            select(Lead).where(
                Lead.seguimientos_enviados < MAX_SEGUIMIENTOS,
                Lead.seguimiento_realizado == False,   # noqa: E712 — SQLAlchemy requiere ==
                Lead.estado != "perdido",
                Lead.estado != "convertido",
                Lead.estado != "noshow",   # noshow: tuvo cita pero no vino — excluir del auto-scheduler
            )
        )
        todos = result.scalars().all()

    candidatos = []
    for lead in todos:
        n = lead.seguimientos_enviados
        intervalo = _INTERVALOS_SEGUIMIENTO.get(n)
        if intervalo is None:
            continue

        if n == 0:
            # Primer seguimiento: contar desde el último mensaje del cliente
            ref = lead.ultimo_mensaje or lead.created_at
        else:
            # Siguientes: contar desde que se envió el seguimiento anterior
            ref = lead.seguimiento_enviado_en

        if ref is None:
            continue

        if ahora - ref >= intervalo:
            candidatos.append(lead)

    return candidatos


async def tiene_cita_pendiente(telefono: str) -> datetime | None:
    """
    Retorna la fecha_hora de la próxima cita FUTURA del cliente, o None si no hay.

    Se usa en ejecutar_seguimientos() para evitar enviar mensajes de seguimiento
    mientras el cliente tiene una cita confirmada que aún no ha pasado.
    """
    # Margen: ignorar citas de las últimas 4 horas (tiempo razonable post-visita)
    desde = datetime.utcnow() - timedelta(hours=4)
    try:
        async with async_session() as session:
            result = await session.execute(text("""
                SELECT fecha_hora FROM citas
                WHERE telefono = :tel
                AND fecha_hora > :desde
                ORDER BY fecha_hora ASC
                LIMIT 1
            """), {"tel": telefono, "desde": desde})
            row = result.first()
            if row and row[0]:
                return row[0]
    except Exception as e:
        logger.warning(f"[LEADS] Error consultando cita pendiente para {telefono}: {e}")
    return None


async def obtener_leads_por_fuente(fuente: str) -> list[Lead]:
    """Devuelve todos los leads de una fuente específica."""
    async with async_session() as session:
        result = await session.execute(
            select(Lead).where(Lead.fuente == fuente).order_by(Lead.ultimo_mensaje.desc())
        )
        return list(result.scalars().all())


async def registrar_seguimiento_enviado(telefono: str, prioridad: str = "medio"):
    """Incrementa el contador, registra timestamp y marca como contactado."""
    async with async_session() as session:
        result = await session.execute(select(Lead).where(Lead.telefono == telefono))
        lead = result.scalar_one_or_none()
        if lead:
            lead.seguimientos_enviados += 1
            lead.seguimiento_enviado_en = datetime.utcnow()
            lead.prioridad              = prioridad
            if lead.seguimientos_enviados >= MAX_SEGUIMIENTOS:
                # Secuencia completa: marcar como terminado
                lead.seguimiento_realizado = True
                lead.estado = "perdido"
            else:
                # Quedan más seguimientos pendientes: resetear a False para que
                # el scheduler lo recoja de nuevo cuando venza el siguiente intervalo.
                # BUG FIX: sin este reset, seguimientos 2/3/4 nunca se enviaban.
                lead.seguimiento_realizado = False
                lead.estado = "en_seguimiento"
        await session.commit()


async def marcar_seguimiento_manual(identificador: str):
    """
    Marca como atendido por folio (si contiene letras) o por teléfono.
    Usado desde el grupo interno con 'marcar seguimiento: X'.
    """
    async with async_session() as session:
        # Intentar por teléfono primero
        norm = re.sub(r"\D", "", identificador)
        result = await session.execute(select(Lead).where(Lead.telefono.contains(norm)))
        lead = result.scalar_one_or_none()
        if lead:
            lead.seguimiento_realizado = True
            await session.commit()
            return lead.telefono
        return None


async def marcar_como_convertido(telefono: str):
    """Marca el lead como convertido (agendó cita y se presentó)."""
    async with async_session() as session:
        result = await session.execute(select(Lead).where(Lead.telefono == telefono))
        lead = result.scalar_one_or_none()
        if lead:
            lead.estado = "convertido"
        await session.commit()


async def marcar_lead_noshow(telefono: str):
    """
    Marca el lead como 'noshow': agendó cita pero no se presentó.
    El estado 'noshow' lo excluye del seguimiento masivo automático (comando masivo)
    y del scheduler normal. Solo se reactiva si el cliente vuelve a escribir.
    """
    async with async_session() as session:
        result = await session.execute(select(Lead).where(Lead.telefono == telefono))
        lead = result.scalar_one_or_none()
        if lead:
            lead.estado = "noshow"
            lead.seguimiento_realizado = True  # pausar secuencia automática
        await session.commit()
        logger.info(f"[LEAD] {telefono} marcado como noshow")


async def obtener_todos_los_leads() -> list[Lead]:
    """Retorna todos los leads ordenados por último mensaje."""
    from sqlalchemy import desc
    async with async_session() as session:
        result = await session.execute(select(Lead).order_by(desc(Lead.ultimo_mensaje)))
        return list(result.scalars().all())


async def marcar_presupuesto_enviado(telefono: str):
    """Registra el momento en que se envió un presupuesto al cliente."""
    async with async_session() as session:
        await session.execute(
            update(Lead).where(Lead.telefono == telefono).values(
                presupuesto_enviado_en=datetime.utcnow()
            )
        )
        await session.commit()


async def obtener_leads_sin_respuesta_presupuesto(horas: int = 24) -> list[Lead]:
    """Leads que recibieron presupuesto y no han respondido en N horas."""
    limite = datetime.utcnow() - timedelta(hours=horas)
    async with async_session() as session:
        result = await session.execute(
            select(Lead).where(
                Lead.presupuesto_enviado_en.isnot(None),
                Lead.presupuesto_enviado_en <= limite,
                Lead.ultimo_mensaje <= limite,  # no han respondido
            )
        )
        return list(result.scalars().all())


async def obtener_leads_sin_cita(min_inactividad_horas: int = 2) -> list[Lead]:
    """
    Leads elegibles para seguimiento masivo: sin cita confirmada y sin actividad reciente.

    INCLUYE:
      - estado 'activo' o 'en_seguimiento' (no convertido, no perdido, no noshow)
      - ultimo_mensaje hace más de min_inactividad_horas (no interrumpe conversaciones activas)
      - seguimientos_enviados < MAX_SEGUIMIENTOS

    EXCLUYE automáticamente:
      - convertido   → tiene cita confirmada (viene + pagó)
      - perdido      → ya agotó los 4 seguimientos
      - noshow       → tuvo cita pero no se presentó (se maneja con comando noshow:)
      - seguimiento_enviado_en < 12h → el scheduler ya envió uno reciente, no pisar
      - Números en stopped_numbers  → se filtran en el loop del comando masivo
    """
    corte_actividad = datetime.utcnow() - timedelta(hours=min_inactividad_horas)
    corte_seguimiento = datetime.utcnow() - timedelta(hours=12)  # no pisar al scheduler

    from sqlalchemy import or_

    async with async_session() as session:
        result = await session.execute(
            select(Lead).where(
                Lead.estado.in_(["activo", "en_seguimiento"]),
                Lead.seguimientos_enviados < MAX_SEGUIMIENTOS,
                Lead.ultimo_mensaje <= corte_actividad,
                # No enviar si el scheduler ya mandó uno hace menos de 12h
                or_(
                    Lead.seguimiento_enviado_en.is_(None),
                    Lead.seguimiento_enviado_en <= corte_seguimiento,
                ),
            ).order_by(Lead.ultimo_mensaje.asc())
        )
        return list(result.scalars().all())


async def obtener_pendientes_seguimiento() -> list[Lead]:
    """Leads que AÚN necesitan seguimiento (seguimiento_realizado=False, no perdido/convertido)."""
    async with async_session() as session:
        result = await session.execute(
            select(Lead).where(
                Lead.seguimiento_realizado == False,   # noqa: E712
                Lead.estado != "perdido",
                Lead.estado != "convertido",
            ).order_by(Lead.ultimo_mensaje.desc())
        )
        return list(result.scalars().all())


async def obtener_todos_los_leads_detalle() -> list[Lead]:
    """Todos los leads ordenados por prioridad y último mensaje."""
    from sqlalchemy import case, desc
    orden_prioridad = case(
        {"urgente": 1, "medio": 2, "bajo": 3},
        value=Lead.prioridad,
        else_=2,
    )
    async with async_session() as session:
        result = await session.execute(
            select(Lead).order_by(orden_prioridad, desc(Lead.ultimo_mensaje))
        )
        return list(result.scalars().all())


async def detener_seguimiento(telefono: str):
    """Detiene todos los seguimientos futuros para este lead."""
    async with async_session() as session:
        await session.execute(
            update(Lead).where(Lead.telefono == telefono).values(
                estado="perdido",
                seguimientos_enviados=MAX_SEGUIMIENTOS,
                seguimiento_realizado=True,
            )
        )
        await session.commit()
        return True


async def obtener_resumen_leads() -> dict:
    """Retorna un conteo de leads por estado y fuente."""
    async with async_session() as session:
        result = await session.execute(select(Lead))
        leads = result.scalars().all()
        resumen = {
            "activo": 0, "en_seguimiento": 0, "perdido": 0, "convertido": 0, "total": 0,
            "por_fuente": {}
        }
        for lead in leads:
            resumen[lead.estado] = resumen.get(lead.estado, 0) + 1
            resumen["total"] += 1
            fuente = getattr(lead, "fuente", "desconocido") or "desconocido"
            resumen["por_fuente"][fuente] = resumen["por_fuente"].get(fuente, 0) + 1
        return resumen
