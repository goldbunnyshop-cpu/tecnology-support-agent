# agent/leads.py — Seguimiento de leads y funnel de conversión
# Generado por AgentKit

import random
from datetime import datetime, timedelta
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import String, DateTime, Integer, select, update, text
from agent.memory import Base, async_session, engine


ASESORES = ["Sofia", "Valentina", "Camila", "Diego", "Andres", "Rodrigo"]


class Lead(Base):
    """Registra cada cliente que inicia conversación y su estado en el funnel."""
    __tablename__ = "leads"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    telefono: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    ultimo_mensaje: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    seguimientos_enviados: Mapped[int] = mapped_column(Integer, default=0)
    estado: Mapped[str] = mapped_column(String(30), default="activo")
    fuente: Mapped[str] = mapped_column(String(50), default="desconocido")
    fuente_detalle: Mapped[str] = mapped_column(String(200), default="")
    asesor_asignado: Mapped[str] = mapped_column(String(50), default="")
    retoma_en: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    retoma_desde: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


async def _migrar_columnas():
    """Agrega columnas nuevas si no existen (migración segura sin perder datos)."""
    async with engine.begin() as conn:
        for columna, definicion in [
            ("fuente",           "VARCHAR(50) DEFAULT 'desconocido'"),
            ("fuente_detalle",   "VARCHAR(200) DEFAULT ''"),
            ("asesor_asignado",  "VARCHAR(50) DEFAULT ''"),
            ("retoma_en",        "DATETIME"),
            ("retoma_desde",     "DATETIME"),
        ]:
            try:
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
            return random.choice(ASESORES)

        asesor_actual = lead.asesor_asignado or ""
        ultimo = lead.ultimo_mensaje or datetime.utcnow()
        inactivo_72h = (datetime.utcnow() - ultimo) >= timedelta(hours=72)

        if asesor_actual and not inactivo_72h:
            return asesor_actual

        opciones = [a for a in ASESORES if a != asesor_actual] or ASESORES
        nuevo = random.choice(opciones)
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
            if lead.estado in ("en_seguimiento", "perdido"):
                lead.estado = "activo"
                lead.seguimientos_enviados = 0
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


async def obtener_leads_para_seguimiento(horas_sin_respuesta: int = 24) -> list[Lead]:
    """Devuelve leads sin actividad que aún no han recibido los 3 seguimientos."""
    limite = datetime.utcnow() - timedelta(hours=horas_sin_respuesta)
    async with async_session() as session:
        result = await session.execute(
            select(Lead).where(
                Lead.ultimo_mensaje < limite,
                Lead.seguimientos_enviados < 3,
                Lead.estado != "perdido",
                Lead.estado != "convertido",
            )
        )
        return list(result.scalars().all())


async def obtener_leads_por_fuente(fuente: str) -> list[Lead]:
    """Devuelve todos los leads de una fuente específica."""
    async with async_session() as session:
        result = await session.execute(
            select(Lead).where(Lead.fuente == fuente).order_by(Lead.ultimo_mensaje.desc())
        )
        return list(result.scalars().all())


async def registrar_seguimiento_enviado(telefono: str):
    """Incrementa el contador de seguimientos. Marca como perdido al llegar a 3."""
    async with async_session() as session:
        result = await session.execute(select(Lead).where(Lead.telefono == telefono))
        lead = result.scalar_one_or_none()
        if lead:
            lead.seguimientos_enviados += 1
            lead.estado = "perdido" if lead.seguimientos_enviados >= 3 else "en_seguimiento"
        await session.commit()


async def marcar_como_convertido(telefono: str):
    """Marca el lead como convertido."""
    async with async_session() as session:
        result = await session.execute(select(Lead).where(Lead.telefono == telefono))
        lead = result.scalar_one_or_none()
        if lead:
            lead.estado = "convertido"
        await session.commit()


async def obtener_todos_los_leads() -> list[Lead]:
    """Retorna todos los leads ordenados por último mensaje."""
    from sqlalchemy import desc
    async with async_session() as session:
        result = await session.execute(select(Lead).order_by(desc(Lead.ultimo_mensaje)))
        return list(result.scalars().all())


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
