# agent/memory.py — Memoria de conversaciones con SQLite
# Generado por AgentKit

import json
import logging
import os
import re as _re
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import Boolean, String, Text, DateTime, select, update, Integer, or_, UniqueConstraint
from dotenv import load_dotenv

logger = logging.getLogger("agentkit")


def _variantes_telefono(telefono: str) -> list[str]:
    """
    Devuelve todas las variantes posibles de un número mexicano
    (10 dígitos y 13 dígitos con 521) para búsquedas tolerantes a formato.
    """
    d = _re.sub(r"\D", "", telefono or "")
    variantes: list[str] = [d]
    if len(d) == 13 and d.startswith("521"):
        variantes.append(d[3:])          # 5215531351098 → 5531351098
    elif len(d) == 12 and d.startswith("52"):
        variantes.append(d[2:])          # 525531351098  → 5531351098
        variantes.append(f"521{d[2:]}")  # 525531351098  → 5215531351098
    elif len(d) == 10:
        variantes.append(f"521{d}")      # 5531351098    → 5215531351098
    # deduplica manteniendo orden
    seen: set[str] = set()
    return [v for v in variantes if v and not (v in seen or seen.add(v))]  # type: ignore[func-returns-value]


load_dotenv()


def _sqlite_url() -> str:
    """Usa /data/agentkit.db si el volumen está montado, si no ./agentkit.db."""
    data_dir = os.path.abspath("/data")
    exists = os.path.exists(data_dir)
    is_dir = os.path.isdir(data_dir)
    print(f"[BD] _sqlite_url(): /data exists={exists} is_dir={is_dir}", flush=True)
    if exists and is_dir:
        path = f"sqlite+aiosqlite:////{data_dir}/agentkit.db"
        print(f"[BD] _sqlite_url(): usando volumen persistente → {path}", flush=True)
        return path
    path = "sqlite+aiosqlite:///./agentkit.db"
    print(f"[BD] _sqlite_url(): /data no disponible → usando {path}", flush=True)
    return path

_env_db_url = os.getenv("DATABASE_URL", "").strip()
DATABASE_URL = _env_db_url if _env_db_url else _sqlite_url()

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


class MensajeProcesado(Base):
    """Registro de message_ids ya procesados — evita duplicados por reenvíos de Whapi."""
    __tablename__ = "mensajes_procesados"

    mensaje_id: Mapped[str] = mapped_column(String(200), primary_key=True)
    telefono: Mapped[str] = mapped_column(String(50), index=True)
    procesado_en: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class CitaNotificada(Base):
    """Registro de notificaciones de citas enviadas a Ulises (evita duplicados)."""
    __tablename__ = "citas_notificadas"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    evento_id: Mapped[str] = mapped_column(String(200), index=True)
    notificacion_tipo: Mapped[str] = mapped_column(String(30))  # inmediata | recordatorio_1h | resumen_diario
    cliente_tel: Mapped[str] = mapped_column(String(50), default="")
    enviado_email: Mapped[bool] = mapped_column(default=False)
    enviado_grupo: Mapped[bool] = mapped_column(default=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class ConfirmacionCitaEnviada(Base):
    """Evita enviar la confirmación de cita al cliente más de una vez por evento."""
    __tablename__ = "confirmaciones_citas_enviadas"
    __table_args__ = (UniqueConstraint("cliente_telefono", "evento_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    cliente_telefono: Mapped[str] = mapped_column(String(50), index=True)
    evento_id: Mapped[str] = mapped_column(String(200))
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


class Pausa(Base):
    """Pausas activas — agente detenido por intervención manual de Christian."""
    __tablename__ = "pausas"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    cliente_telefono: Mapped[str] = mapped_column(String(50), index=True)
    fecha_pausa: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    duracion_minutos: Mapped[int] = mapped_column(Integer, default=120)
    razon: Mapped[str] = mapped_column(String(100), default="intervencion_manual")
    activa: Mapped[bool] = mapped_column(Boolean, default=True)


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
        ruta_sqlite = DATABASE_URL.replace("sqlite+aiosqlite://", "")
        persistente = "/data/" in ruta_sqlite
        if persistente:
            logger.info(f"[BD] ✅ SQLite PERSISTENTE en volumen Railway: {ruta_sqlite}")
        else:
            logger.warning(
                f"[BD] ⚠️  SQLite TEMPORAL ({ruta_sqlite}) — los datos se PIERDEN al reiniciar. "
                "Monta un volumen en /data en Railway para persistencia."
            )
    else:
        db_host = DATABASE_URL.split("@")[-1].split("/")[0] if "@" in DATABASE_URL else "?"
        logger.info(f"[BD] ✅ PostgreSQL: host={db_host}")

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        # Tabla legacy/operativa para citas detectadas automaticamente
        # (la consume agent/cita_detector.py con SQL directo).
        from sqlalchemy import text
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS citas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nombre TEXT NOT NULL,
                telefono TEXT DEFAULT '',
                dispositivo TEXT NOT NULL,
                problema TEXT NOT NULL,
                fecha_hora DATETIME NOT NULL,
                asesor TEXT DEFAULT '',
                fuente TEXT DEFAULT 'automatica',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """))

    from agent.leads import _migrar_columnas
    await _migrar_columnas()
    await _migrar_clientes_perfil()
    logger.info("[BD] Tablas listas: mensajes, leads, clientes_perfil, citas_recordatorio, mensajes_procesados, citas_notificadas, pausas")


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
    minutos = horas * 60
    async with async_session() as session:
        # Desactivar pausas previas activas para este cliente
        result = await session.execute(
            select(Pausa).where(Pausa.cliente_telefono == telefono, Pausa.activa == True)
        )
        for p in result.scalars().all():
            p.activa = False
        session.add(Pausa(
            cliente_telefono=telefono,
            duracion_minutos=minutos,
            razon="intervencion_manual",
        ))
        await session.commit()
    # Compatibilidad con código existente que lee ClientePerfil.pausada_hasta
    hasta = datetime.utcnow() + timedelta(hours=horas)
    await _upsert_perfil(telefono, pausada_hasta=hasta)
    logger.info(f"[PAUSA] Cliente {telefono} pausado — {minutos} min (intervención manual de Christian)")


async def reanudar_conversacion(telefono: str):
    """Reactiva el agente para este cliente (acepta 10 o 13 dígitos)."""
    variantes = _variantes_telefono(telefono)
    async with async_session() as session:
        result = await session.execute(
            select(Pausa).where(
                Pausa.cliente_telefono.in_(variantes),
                Pausa.activa == True,
            )
        )
        for p in result.scalars().all():
            p.activa = False
        await session.commit()
    for tel in variantes:
        await _upsert_perfil(tel, pausada_hasta=None)
    logger.info(f"[PAUSA] Reanudar manual: {telefono} (comando de Christian)")


async def limpiar_todas_pausas() -> int:
    """Desactiva TODAS las pausas activas en ambas tablas. Retorna cuántas se limpiaron."""
    async with async_session() as session:
        # Limpiar tabla pausas
        result = await session.execute(select(Pausa).where(Pausa.activa == True))
        pausas = result.scalars().all()
        count = len(pausas)
        for p in pausas:
            p.activa = False
        # Limpiar también ClientePerfil.pausada_hasta (fallback legacy)
        result2 = await session.execute(
            select(ClientePerfil).where(ClientePerfil.pausada_hasta != None)
        )
        for perfil in result2.scalars().all():
            perfil.pausada_hasta = None
            count += 1
        await session.commit()
    logger.info(f"[PAUSA] Limpieza total: {count} pausas desactivadas")
    return count


async def esta_pausada(telefono: str) -> bool:
    """Retorna True si el agente está pausado para este cliente.
    Acepta 10 o 13 dígitos — busca todas las variantes del número."""
    variantes = _variantes_telefono(telefono)
    async with async_session() as session:
        # Fuente primaria: tabla pausas (busca todas las variantes del número)
        result = await session.execute(
            select(Pausa)
            .where(
                Pausa.cliente_telefono.in_(variantes),
                Pausa.activa == True,
            )
            .order_by(Pausa.fecha_pausa.desc())
        )
        # Usar .first() para evitar error si hay múltiples filas activas
        pausa = result.scalars().first()
        if pausa:
            expira = pausa.fecha_pausa + timedelta(minutes=pausa.duracion_minutos)
            if datetime.utcnow() < expira:
                return True
            # Pausa vencida — desactivar automáticamente
            pausa.activa = False
            await session.commit()
            return False

        # Fallback: revisar ClientePerfil (pausas de versiones anteriores)
        result2 = await session.execute(
            select(ClientePerfil).where(ClientePerfil.telefono.in_(variantes))
        )
        perfil = result2.scalars().first()
        if not perfil or not perfil.pausada_hasta:
            return False
        if datetime.utcnow() >= perfil.pausada_hasta:
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


async def mensaje_ya_procesado(mensaje_id: str) -> bool:
    """Retorna True si este mensaje_id ya fue procesado (deduplicación contra reenvíos de Whapi)."""
    if not mensaje_id:
        return False
    async with async_session() as session:
        result = await session.execute(
            select(MensajeProcesado).where(MensajeProcesado.mensaje_id == mensaje_id)
        )
        return result.scalar_one_or_none() is not None


async def marcar_mensaje_procesado(mensaje_id: str, telefono: str):
    """Registra el mensaje_id como procesado para evitar procesarlo dos veces."""
    if not mensaje_id:
        return
    async with async_session() as session:
        existe = await session.execute(
            select(MensajeProcesado).where(MensajeProcesado.mensaje_id == mensaje_id)
        )
        if existe.scalar_one_or_none() is None:
            session.add(MensajeProcesado(mensaje_id=mensaje_id, telefono=telefono))
            await session.commit()


async def cita_notificada_ya_enviada(evento_id: str, tipo: str) -> bool:
    """Retorna True si ya se envió esta notificación de cita a Ulises."""
    async with async_session() as session:
        result = await session.execute(
            select(CitaNotificada).where(
                CitaNotificada.evento_id == evento_id,
                CitaNotificada.notificacion_tipo == tipo,
            )
        )
        return result.scalar_one_or_none() is not None


async def registrar_cita_notificada(
    evento_id: str,
    tipo: str,
    cliente_tel: str,
    enviado_email: bool,
    enviado_grupo: bool,
) -> None:
    """Registra que se envió una notificación de cita para no repetirla."""
    async with async_session() as session:
        existe = await session.execute(
            select(CitaNotificada).where(
                CitaNotificada.evento_id == evento_id,
                CitaNotificada.notificacion_tipo == tipo,
            )
        )
        if existe.scalar_one_or_none() is None:
            session.add(CitaNotificada(
                evento_id=evento_id,
                notificacion_tipo=tipo,
                cliente_tel=cliente_tel,
                enviado_email=enviado_email,
                enviado_grupo=enviado_grupo,
            ))
            await session.commit()


async def cita_ya_existe_para_telefono(telefono: str, fecha_hora: datetime, ventana_minutos: int = 45) -> bool:
    """
    Retorna True si ya hay una cita en la BD para este teléfono en ±ventana_minutos
    alrededor de fecha_hora. Evita crear duplicados en Google Calendar.
    """
    if not telefono or not fecha_hora:
        return False
    inicio = fecha_hora - timedelta(minutes=ventana_minutos)
    fin    = fecha_hora + timedelta(minutes=ventana_minutos)
    async with async_session() as session:
        try:
            variantes = _variantes_telefono(telefono)
            placeholders = ", ".join([f":tel{i}" for i in range(len(variantes))])
            params = {f"tel{i}": v for i, v in enumerate(variantes)}
            params.update({"inicio": inicio, "fin": fin})
            result = await session.execute(
                text(
                    f"SELECT COUNT(*) FROM citas "
                    f"WHERE telefono IN ({placeholders}) "
                    f"AND fecha_hora BETWEEN :inicio AND :fin"
                ),
                params,
            )
            count = result.scalar_one_or_none() or 0
            if count > 0:
                logger.info(
                    f"[DEDUP] Cita ya existe para {telefono} en "
                    f"{fecha_hora.strftime('%d/%m %H:%M')} — ignorando duplicado"
                )
            return count > 0
        except Exception as e:
            logger.warning(f"[DEDUP] No se pudo verificar duplicado: {e}")
            return False


async def confirmacion_cita_ya_enviada(cliente_telefono: str, evento_id: str) -> bool:
    """Retorna True si esta confirmación ya fue enviada al cliente — evita duplicados."""
    if not evento_id:
        return False
    async with async_session() as session:
        result = await session.execute(
            select(ConfirmacionCitaEnviada).where(
                ConfirmacionCitaEnviada.cliente_telefono == cliente_telefono,
                ConfirmacionCitaEnviada.evento_id == evento_id,
            )
        )
        return result.scalar_one_or_none() is not None


async def marcar_confirmacion_cita_enviada(cliente_telefono: str, evento_id: str) -> None:
    """Marca la confirmación como enviada para no repetirla."""
    if not evento_id:
        return
    async with async_session() as session:
        try:
            session.add(ConfirmacionCitaEnviada(
                cliente_telefono=cliente_telefono,
                evento_id=evento_id,
            ))
            await session.commit()
        except Exception:
            await session.rollback()  # UNIQUE constraint → ya registrada, ignorar
