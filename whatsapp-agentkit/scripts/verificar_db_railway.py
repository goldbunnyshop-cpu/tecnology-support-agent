"""
Verifica que la BD en Railway está guardando datos correctamente.
Usa la misma DATABASE_URL que en .env (funciona en Railway o local).
"""

import asyncio
import os
from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import text

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./agentkit.db")


async def verificar_base_datos():
    """Conecta a la BD y muestra estado."""

    # Ajustar URL para PostgreSQL si es necesario
    db_url = DATABASE_URL
    if db_url.startswith("postgresql://"):
        db_url = db_url.replace("postgresql://", "postgresql+asyncpg://", 1)

    engine = create_async_engine(db_url, echo=False)
    async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    print("\n" + "="*60)
    print("   VERIFICACIÓN DE BASE DE DATOS")
    print("="*60)
    print(f"\n📊 Database URL: {db_url[:50]}...")

    try:
        async with async_session() as session:
            # 1. Total de mensajes
            try:
                result = await session.execute(text("SELECT COUNT(*) as total FROM mensajes"))
                total_mensajes = result.scalar()
                print(f"\n✅ Tabla 'mensajes': {total_mensajes} registros")
            except Exception as e:
                print(f"\n❌ Tabla 'mensajes': Error - {e}")
                total_mensajes = 0

            # 2. Total de citas
            try:
                result = await session.execute(text("SELECT COUNT(*) as total FROM citas_notificadas"))
                total_citas = result.scalar()
                print(f"✅ Tabla 'citas_notificadas': {total_citas} registros")
            except Exception as e:
                print(f"⚠️  Tabla 'citas_notificadas' no existe o error: {e}")
                total_citas = 0

            # 3. Últimas 5 citas
            if total_citas > 0:
                print("\n📋 Últimas 5 citas agendadas:")
                try:
                    result = await session.execute(
                        text("SELECT id, cliente_telefono, fecha, hora, nombre_cliente FROM citas_notificadas ORDER BY id DESC LIMIT 5")
                    )
                    for idx, row in enumerate(result, 1):
                        print(f"   {idx}. {row[1]} → {row[2]} {row[3]} ({row[4]})")
                except Exception as e:
                    print(f"   Error al leer citas: {e}")

            # 4. Últimos 3 mensajes
            if total_mensajes > 0:
                print("\n💬 Últimos 3 mensajes:")
                try:
                    result = await session.execute(
                        text("SELECT telefono, role, content, timestamp FROM mensajes ORDER BY id DESC LIMIT 3")
                    )
                    for idx, (tel, role, content, ts) in enumerate(result, 1):
                        content_short = content[:50] + "..." if len(content) > 50 else content
                        print(f"   {idx}. [{role.upper()}] {tel}: '{content_short}'")
                except Exception as e:
                    print(f"   Error al leer mensajes: {e}")

        print("\n✅ Conexión exitosa — Base de datos funciona correctamente\n")

    except Exception as e:
        print(f"\n❌ Error al conectar: {e}\n")

    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(verificar_base_datos())
