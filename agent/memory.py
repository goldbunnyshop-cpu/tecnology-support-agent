# agent/memory.py — Memoria de conversaciones con SQLite
# Generado por AgentKit

import json
import logging
import os
from datetime import datetime
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import String, Text, DateTime, select, update, Integer
from dotenv import load_dotenv

logger = logging.getLogger("agentkit")

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./agentkit.db")

# Railway usa "postgres://" o "postgresql://"; asyncpg necesita "postgresql+asyncpg://"
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql+asyncpg://", 1)
elif DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)

_USANDO_SQLITE = DATABASE_URL.startswith("sqlite")

# Pool de conexiones: más amplio en PostgreSQL, mínimo en SQLite
_engine_kwargs: dict = {}
if not _USANDO_SQLITE:
    _engine_kwargs = {"pool_size": 5, "max_overflow": 10, "pool_pre_ping": True}

engine = create_async_engine(DATABASE_URL, echo=False, **_engine_kwargs)
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


class CitaRecordatorio(Base):
    """Registro de recordatorios de citas ya enviados (evita duplicados)."""
    __tablename__ = "citas_recordatorio"

    evento_id: Mapped[str] = mapped_column(String(200), primary_key=True)
    telefono: Mapped[str] = mapped_column(String(50), index=True)
    enviado_en: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


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
    pausada_hasta: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


async def obtener_perfil(telefono: str) -> ClientePerfil | None:
    async with async_session() as session:
        result = await session.execute(
            select(ClientePerfil).where(ClientePerfil.telefono == telefono)
        )
        perfil = result.scalar_one_or_none()
        if perfil is None:
            logger.info(f"[MEMORIA] Perfil no encontrado para {telefono} → cliente nuevo")
        else:
            logger.info(
                f"[MEMORIA] Cargando perfil {telefono} → "
                f"nombre='{perfil.nombre or '?'}' "
                f"asesor='{perfil.asesor_ultimo or '?'}'"
            )
        return perfil


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
    logger.info(f"[MEMORIA] Guardando nombre='{nombre}' para {telefono}")
    async with async_session() as session:
        result = await session.execute(
            select(ClientePerfil).where(ClientePerfil.telefono == telefono)
        )
        perfil = result.scalar_one_or_none()
        if perfil is None:
            session.add(ClientePerfil(telefono=telefono, nombre=nombre))
            await session.commit()
            logger.info(f"[MEMORIA] Perfil creado con nombre='{nombre}' para {telefono}")
        elif not perfil.nombre:
            perfil.nombre = nombre
            await session.commit()
            logger.info(f"[MEMORIA] Nombre actualizado → '{nombre}' para {telefono}")
        else:
            logger.info(f"[MEMORIA] Nombre ya existía ('{perfil.nombre}') — no se sobreescribe")


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


async def _migrar_clientes_perfil():
    """Agrega columnas nuevas a clientes_perfil si no existen."""
    async with engine.begin() as conn:
        for columna, definicion in [
            ("nombre",           "VARCHAR(100)"),
            ("dispositivos_json","TEXT DEFAULT '[]'"),
            ("servicios_json",   "TEXT DEFAULT '[]'"),
            ("ultima_visita",    "DATETIME"),
            ("asesor_ultimo",    "VARCHAR(50) DEFAULT ''"),
            ("notas",            "TEXT DEFAULT ''"),
            ("pausada_hasta",    "DATETIME"),
            ("created_at",       "DATETIME"),
        ]:
            try:
                from sqlalchemy import text
                await conn.execute(text(
                    f"ALTER TABLE clientes_perfil ADD COLUMN {columna} {definicion}"
                ))
            except Exception:
                pass  # columna ya existe


async def inicializar_db():
    """Crea las tablas si no existen y aplica migraciones seguras."""
    if _USANDO_SQLITE:
        logger.warning(
            "[BD] ⚠️  SQLite detectado — los datos se PIERDEN al reiniciar. "
            "Configura DATABASE_URL con PostgreSQL en Railway para persistencia real."
        )
    else:
        db_host = DATABASE_URL.split("@")[-1].split("/")[0] if "@" in DATABASE_URL else "?"
        logger.info(f"[BD] ✅ PostgreSQL: host={db_host}")

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    from agent.leads import _migrar_columnas
    await _migrar_columnas()
    await _migrar_clientes_perfil()
    logger.info("[BD] Tablas listas: mensajes, leads, clientes_perfil, citas_recordatorio")


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


async def pausar_conversacion(telefono: str, horas: int = 2):
    """Pausa el agente para este cliente durante N horas (intervención humana)."""
    hasta = datetime.utcnow() + __import__("datetime").timedelta(hours=horas)
    await _upsert_perfil(telefono, pausada_hasta=hasta)
    logger.info(f"[PAUSA] Conversación {telefono} pausada hasta {hasta.strftime('%H:%M')} UTC")


async def reanudar_conversacion(telefono: str):
    """Reactiva el agente para este cliente."""
    await _upsert_perfil(telefono, pausada_hasta=None)
    logger.info(f"[PAUSA] Conversación {telefono} reanudada")


async def esta_pausada(telefono: str) -> bool:
    """Retorna True si el agente está pausado para este cliente."""
    async with async_session() as session:
        result = await session.execute(
            select(ClientePerfil).where(ClientePerfil.telefono == telefono)
        )
        perfil = result.scalar_one_or_none()
        if not perfil or not perfil.pausada_hasta:
            return False
        if datetime.utcnow() >= perfil.pausada_hasta:
            # Venció la pausa — limpiar automáticamente
            perfil.pausada_hasta = None
            await session.commit()
            return False
        return True


async def recordatorio_ya_enviado(evento_id: str) -> bool:
    """Retorna True si ya se envió el recordatorio para este evento."""
    async with async_session() as session:
        result = await session.execute(
            select(CitaRecordatorio).where(CitaRecordatorio.evento_id == evento_id)
        )
        return result.scalar_one_or_none() is not None


async def registrar_recordatorio(evento_id: str, telefono: str):
    """Marca el recordatorio como enviado para no repetirlo."""
    async with async_session() as session:
        existe = await session.execute(
            select(CitaRecordatorio).where(CitaRecordatorio.evento_id == evento_id)
        )
        if existe.scalar_one_or_none() is None:
            session.add(CitaRecordatorio(evento_id=evento_id, telefono=telefono))
            await session.commit()
