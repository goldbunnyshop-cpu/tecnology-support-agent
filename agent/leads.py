# agent/leads.py — Seguimiento de leads y funnel de conversión
# Generado por AgentKit

from datetime import datetime, timedelta
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import String, DateTime, Integer, select, text
from agent.memory import Base, async_session, engine


class Lead(Base):
    """Registra cada cliente que inicia conversación y su estado en el funnel."""
    __tablename__ = "leads"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    telefono: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    ultimo_mensaje: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    seguimientos_enviados: Mapped[int] = mapped_column(Integer, default=0)
    # activo | en_seguimiento | perdido | convertido
    estado: Mapped[str] = mapped_column(String(30), default="activo")
    # organico | facebook_ad | instagram_ad | referido | desconocido
    fuente: Mapped[str] = mapped_column(String(50), default="desconocido")
    fuente_detalle: Mapped[str] = mapped_column(String(200), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


async def _migrar_columnas():
    """Agrega columnas nuevas si no existen (migración segura sin perder datos)."""
    async with engine.begin() as conn:
        for columna, definicion in [
            ("fuente",         "VARCHAR(50) DEFAULT 'desconocido'"),
            ("fuente_detalle", "VARCHAR(200) DEFAULT ''"),
        ]:
            try:
                await conn.execute(text(f"ALTER TABLE leads ADD COLUMN {columna} {definicion}"))
            except Exception:
                pass  # columna ya existe


async def crear_o_actualizar_lead(telefono: str, fuente: str = "desconocido", fuente_detalle: str = ""):
    """Crea el lead si es nuevo, o actualiza su timestamp si ya existe."""
    async with async_session() as session:
        result = await session.execute(select(Lead).where(Lead.telefono == telefono))
        lead = result.scalar_one_or_none()
        if lead:
            lead.ultimo_mensaje = datetime.utcnow()
            if lead.estado in ("en_seguimiento", "perdido"):
                lead.estado = "activo"
                lead.seguimientos_enviados = 0
            # Actualizar fuente si se detecta una más específica
            if fuente != "desconocido" and lead.fuente == "desconocido":
                lead.fuente = fuente
                lead.fuente_detalle = fuente_detalle
        else:
            lead = Lead(telefono=telefono, fuente=fuente, fuente_detalle=fuente_detalle)
            session.add(lead)
        await session.commit()


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
    """Devuelve todos los leads de una fuente específica (ej: 'facebook_ad')."""
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
    """Marca el lead como convertido (agendó cita o aceptó ir al módulo)."""
    async with async_session() as session:
        result = await session.execute(select(Lead).where(Lead.telefono == telefono))
        lead = result.scalar_one_or_none()
        if lead:
            lead.estado = "convertido"
        await session.commit()


async def obtener_todos_los_leads() -> list[Lead]:
    """Retorna todos los leads ordenados por último mensaje (más reciente primero)."""
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
