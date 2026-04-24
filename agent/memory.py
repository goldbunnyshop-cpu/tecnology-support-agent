# agent/memory.py — Memoria de conversaciones con SQLite
# Generado por AgentKit

import json
import os
from datetime import datetime
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import String, Text, DateTime, select, update, Integer
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./agentkit.db")

if DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)

engine = create_async_engine(DATABASE_URL, echo=False)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


class Mensaje(Base):
    """Modelo de mensaje en la base de datos."""
    __tablename__ = "mensajes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    telefono: Mapped[str] = mapped_column(String(50), index=True)
    role: Mapped[str] = mapped_column(String(20))
    content: Mapped[str] = mapped_column(Text)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class ClientePerfil(Base):
    """Perfil persistente del cliente — sobrevive reinicios del servidor."""
    __tablename__ = "clientes_perfil"

    telefono: Mapped[str] = mapped_column(String(50), primary_key=True)
    nombre: Mapped[str] = mapped_column(String(100), nullable=True)
    dispositivos_json: Mapped[str] = mapped_column(Text, default="[]")
    servicios_json: Mapped[str] = mapped_column(Text, default="[]")
    ultima_visita: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    asesor_ultimo: Mapped[str] = mapped_column(String(50), default="")
    notas: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


async def obtener_perfil(telefono: str) -> ClientePerfil | None:
    async with async_session() as session:
        result = await session.execute(
            select(ClientePerfil).where(ClientePerfil.telefono == telefono)
        )
        return result.scalar_one_or_none()


async def _upsert_perfil(telefono: str, **valores):
    """Crea el perfil si no existe, o actualiza los campos indicados."""
    async with async_session() as session:
        result = await session.execute(
            select(ClientePerfil).where(ClientePerfil.telefono == telefono)
        )
        perfil = result.scalar_one_or_none()
        if perfil is None:
            perfil = ClientePerfil(telefono=telefono, **valores)
            session.add(perfil)
        else:
            for k, v in valores.items():
                setattr(perfil, k, v)
        await session.commit()


async def guardar_nombre_cliente(telefono: str, nombre: str):
    """Guarda el nombre la primera vez (no sobreescribe si ya existe)."""
    async with async_session() as session:
        result = await session.execute(
            select(ClientePerfil).where(ClientePerfil.telefono == telefono)
        )
        perfil = result.scalar_one_or_none()
        if perfil is None:
            session.add(ClientePerfil(telefono=telefono, nombre=nombre))
            await session.commit()
        elif not perfil.nombre:
            perfil.nombre = nombre
            await session.commit()


async def actualizar_visita_cliente(telefono: str, asesor: str):
    """Actualiza fecha de última visita y asesor que atendió."""
    await _upsert_perfil(telefono, ultima_visita=datetime.utcnow(), asesor_ultimo=asesor)


async def _agregar_a_lista(telefono: str, campo: str, valor: str, max_items: int = 10):
    """Agrega un valor a una lista JSON en el perfil (sin duplicados, máximo max_items)."""
    async with async_session() as session:
        result = await session.execute(
            select(ClientePerfil).where(ClientePerfil.telefono == telefono)
        )
        perfil = result.scalar_one_or_none()
        if perfil is None:
            kwargs = {campo: json.dumps([valor])}
            session.add(ClientePerfil(telefono=telefono, **kwargs))
        else:
            lista = json.loads(getattr(perfil, campo) or "[]")
            if valor not in lista:
                lista.append(valor)
                if len(lista) > max_items:
                    lista = lista[-max_items:]
                setattr(perfil, campo, json.dumps(lista))
        await session.commit()


async def agregar_dispositivo_cliente(telefono: str, dispositivo: str):
    if dispositivo and dispositivo != "No especificado":
        await _agregar_a_lista(telefono, "dispositivos_json", dispositivo)


async def agregar_servicio_cliente(telefono: str, servicio: str):
    if servicio:
        entrada = f"{servicio} ({datetime.utcnow().strftime('%d/%m/%Y')})"
        await _agregar_a_lista(telefono, "servicios_json", entrada)


async def inicializar_db():
    """Crea las tablas si no existen y aplica migraciones seguras."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    # Migrar columnas nuevas en tablas existentes
    from agent.leads import _migrar_columnas
    await _migrar_columnas()


async def guardar_mensaje(telefono: str, role: str, content: str):
    """Guarda un mensaje en el historial de conversación."""
    async with async_session() as session:
        mensaje = Mensaje(
            telefono=telefono,
            role=role,
            content=content,
            timestamp=datetime.utcnow()
        )
        session.add(mensaje)
        await session.commit()


async def obtener_historial(telefono: str, limite: int = 20) -> list[dict]:
    """
    Recupera los últimos N mensajes de una conversación.

    Args:
        telefono: Número de teléfono del cliente
        limite: Máximo de mensajes a recuperar (default: 20)
    """
    async with async_session() as session:
        query = (
            select(Mensaje)
            .where(Mensaje.telefono == telefono)
            .order_by(Mensaje.timestamp.desc())
            .limit(limite)
        )
        result = await session.execute(query)
        mensajes = result.scalars().all()
        mensajes.reverse()
        return [
            {"role": msg.role, "content": msg.content}
            for msg in mensajes
        ]


async def limpiar_historial(telefono: str):
    """Borra todo el historial de una conversación."""
    async with async_session() as session:
        query = select(Mensaje).where(Mensaje.telefono == telefono)
        result = await session.execute(query)
        mensajes = result.scalars().all()
        for msg in mensajes:
            await session.delete(msg)
        await session.commit()
