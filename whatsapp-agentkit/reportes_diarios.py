#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Generador de reportes diarios de citas desde PostgreSQL.
Ejecutar: python reportes_diarios.py
"""

import asyncio
import os
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import select, func
from dotenv import load_dotenv
from collections import defaultdict

load_dotenv()

ZONA_CDMX = ZoneInfo("America/Mexico_City")

# Configuración de base de datos
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./agentkit.db")

# Si es PostgreSQL en producción, ajustar el esquema de URL
if DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)

engine = create_async_engine(DATABASE_URL, echo=False)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

# Importar el modelo de citas
from importar_citas_postgresql import Cita

DIAS_ES = {
    0: "lunes", 1: "martes", 2: "miércoles", 3: "jueves",
    4: "viernes", 5: "sábado", 6: "domingo"
}

MESES_ES = {
    1: "enero", 2: "febrero", 3: "marzo", 4: "abril", 5: "mayo", 6: "junio",
    7: "julio", 8: "agosto", 9: "septiembre", 10: "octubre", 11: "noviembre", 12: "diciembre"
}


def formatear_fecha(dt: datetime) -> str:
    """Formatea una fecha como: 'Lunes 15 de mayo'"""
    if not dt:
        return "N/A"
    dia_nombre = DIAS_ES.get(dt.weekday(), "")
    mes_nombre = MESES_ES.get(dt.month, "")
    return f"{dia_nombre.capitalize()} {dt.day} de {mes_nombre}"


def formatear_hora(dt: datetime) -> str:
    """Formatea una hora como: '14:30'"""
    if not dt:
        return "N/A"
    return dt.strftime("%H:%M")


async def obtener_citas_rango(dias: int = 7) -> list:
    """
    Obtiene todas las citas desde hoy hasta X días en el futuro.

    Args:
        dias: Número de días a incluir (default: 7)

    Returns:
        Lista de citas ordenadas por fecha
    """
    async with async_session() as session:
        ahora = datetime.now(ZONA_CDMX).replace(hour=0, minute=0, second=0, microsecond=0)
        futuro = ahora + timedelta(days=dias)

        query = (
            select(Cita)
            .where(Cita.fecha_hora >= ahora)
            .where(Cita.fecha_hora < futuro)
            .order_by(Cita.fecha_hora.asc())
        )
        result = await session.execute(query)
        return result.scalars().all()


async def obtener_citas_hoy() -> list:
    """Obtiene solo las citas de hoy."""
    async with async_session() as session:
        ahora = datetime.now(ZONA_CDMX).replace(hour=0, minute=0, second=0, microsecond=0)
        manana = ahora + timedelta(days=1)

        query = (
            select(Cita)
            .where(Cita.fecha_hora >= ahora)
            .where(Cita.fecha_hora < manana)
            .order_by(Cita.fecha_hora.asc())
        )
        result = await session.execute(query)
        return result.scalars().all()


def obtener_estadisticas_citas(citas: list) -> dict:
    """Calcula estadísticas de las citas."""
    stats = {
        "total": len(citas),
        "por_asesor": defaultdict(int),
        "por_dispositivo": defaultdict(int),
        "por_fuente": defaultdict(int),
    }

    for cita in citas:
        stats["por_asesor"][cita.asesor] += 1
        stats["por_dispositivo"][cita.dispositivo] += 1
        stats["por_fuente"][cita.fuente] += 1

    return stats


def generar_reporte_texto(citas: list, titulo: str = "REPORTE DE CITAS") -> str:
    """Genera un reporte en formato texto legible."""
    lineas = []
    lineas.append("=" * 70)
    lineas.append(f"  {titulo}")
    lineas.append("=" * 70)
    lineas.append("")

    if not citas:
        lineas.append("❌ No hay citas agendadas.")
        lineas.append("")
        lineas.append("=" * 70)
        return "\n".join(lineas)

    # Agrupar por fecha
    citas_por_fecha = defaultdict(list)
    for cita in citas:
        fecha_key = cita.fecha_hora.date()
        citas_por_fecha[fecha_key].append(cita)

    # Ordenar por fecha
    for fecha in sorted(citas_por_fecha.keys()):
        citas_dia = citas_por_fecha[fecha]
        fecha_obj = datetime.combine(fecha, datetime.min.time(), tzinfo=ZONA_CDMX)

        lineas.append(f"\n📅 {formatear_fecha(fecha_obj)}")
        lineas.append("-" * 70)

        for idx, cita in enumerate(citas_dia, 1):
            lineas.append(
                f"\n  {idx}. ⏰ {formatear_hora(cita.fecha_hora)} — {cita.nombre}"
            )
            lineas.append(f"     📱 {cita.dispositivo}")
            lineas.append(f"     ⚠️  {cita.problema}")
            lineas.append(f"     👨‍💼 {cita.asesor}")
            lineas.append(f"     🔖 [{cita.fuente}]")

    lineas.append("\n" + "=" * 70)

    # Estadísticas
    stats = obtener_estadisticas_citas(citas)
    lineas.append(f"📊 ESTADÍSTICAS")
    lineas.append(f"   Total de citas: {stats['total']}")
    lineas.append(f"   Por asesor: {dict(stats['por_asesor'])}")
    lineas.append(f"   Por dispositivo: {dict(stats['por_dispositivo'])}")
    lineas.append("=" * 70)

    return "\n".join(lineas)


def generar_reporte_html(citas: list, titulo: str = "REPORTE DE CITAS") -> str:
    """Genera un reporte en HTML para abrir en navegador."""
    html = []
    html.append("<!DOCTYPE html>")
    html.append("<html lang='es'>")
    html.append("<head>")
    html.append("<meta charset='UTF-8'>")
    html.append("<meta name='viewport' content='width=device-width, initial-scale=1.0'>")
    html.append(f"<title>{titulo}</title>")
    html.append("<style>")
    html.append("""
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: #333;
            margin: 0;
            padding: 20px;
        }
        .container {
            max-width: 900px;
            margin: 0 auto;
            background: white;
            border-radius: 12px;
            padding: 30px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.2);
        }
        h1 {
            color: #667eea;
            text-align: center;
            margin-bottom: 30px;
            border-bottom: 3px solid #667eea;
            padding-bottom: 15px;
        }
        .fecha-seccion {
            margin-bottom: 30px;
            border-left: 4px solid #667eea;
            padding-left: 20px;
        }
        .fecha-titulo {
            font-size: 1.3em;
            font-weight: bold;
            color: #667eea;
            margin-bottom: 15px;
        }
        .cita-card {
            background: #f8f9fa;
            border-radius: 8px;
            padding: 15px;
            margin-bottom: 12px;
            border-left: 4px solid #764ba2;
        }
        .cita-hora {
            font-weight: bold;
            color: #667eea;
            font-size: 1.1em;
        }
        .cita-cliente {
            margin-top: 8px;
            font-weight: 600;
        }
        .cita-dispositivo {
            color: #666;
            margin-top: 5px;
        }
        .cita-problema {
            color: #e74c3c;
            margin-top: 5px;
            font-size: 0.95em;
        }
        .cita-asesor {
            color: #27ae60;
            margin-top: 5px;
            font-size: 0.95em;
        }
        .cita-fuente {
            color: #999;
            font-size: 0.85em;
            margin-top: 5px;
        }
        .estadisticas {
            background: #ecf0f1;
            border-radius: 8px;
            padding: 20px;
            margin-top: 30px;
        }
        .estadisticas h2 {
            color: #667eea;
            margin-top: 0;
        }
        .stat-item {
            margin: 10px 0;
            padding: 10px;
            background: white;
            border-radius: 5px;
        }
        .vacio {
            text-align: center;
            padding: 40px;
            color: #999;
            font-size: 1.1em;
        }
        .timestamp {
            text-align: right;
            color: #999;
            font-size: 0.9em;
            margin-top: 20px;
            padding-top: 15px;
            border-top: 1px solid #eee;
        }
    """)
    html.append("</style>")
    html.append("</head>")
    html.append("<body>")
    html.append("<div class='container'>")
    html.append(f"<h1>{titulo}</h1>")

    if not citas:
        html.append("<div class='vacio'>❌ No hay citas agendadas</div>")
    else:
        # Agrupar por fecha
        citas_por_fecha = defaultdict(list)
        for cita in citas:
            fecha_key = cita.fecha_hora.date()
            citas_por_fecha[fecha_key].append(cita)

        # Renderizar por fecha
        for fecha in sorted(citas_por_fecha.keys()):
            citas_dia = citas_por_fecha[fecha]
            fecha_obj = datetime.combine(fecha, datetime.min.time(), tzinfo=ZONA_CDMX)

            html.append("<div class='fecha-seccion'>")
            html.append(f"<div class='fecha-titulo'>📅 {formatear_fecha(fecha_obj)}</div>")

            for cita in citas_dia:
                html.append("<div class='cita-card'>")
                html.append(f"<div class='cita-hora'>⏰ {formatear_hora(cita.fecha_hora)}</div>")
                html.append(f"<div class='cita-cliente'>{cita.nombre}</div>")
                html.append(f"<div class='cita-dispositivo'>📱 {cita.dispositivo}</div>")
                html.append(f"<div class='cita-problema'>⚠️ {cita.problema}</div>")
                html.append(f"<div class='cita-asesor'>👨‍💼 {cita.asesor}</div>")
                html.append(f"<div class='cita-fuente'>🔖 [{cita.fuente}]</div>")
                html.append("</div>")

            html.append("</div>")

    # Estadísticas
    if citas:
        stats = obtener_estadisticas_citas(citas)
        html.append("<div class='estadisticas'>")
        html.append("<h2>📊 Estadísticas</h2>")
        html.append(f"<div class='stat-item'><strong>Total de citas:</strong> {stats['total']}</div>")

        if stats["por_asesor"]:
            html.append("<div class='stat-item'><strong>Por asesor:</strong> ")
            for asesor, count in sorted(stats["por_asesor"].items()):
                html.append(f"{asesor} ({count}) ")
            html.append("</div>")

        if stats["por_dispositivo"]:
            html.append("<div class='stat-item'><strong>Por dispositivo:</strong> ")
            for device, count in sorted(stats["por_dispositivo"].items(), key=lambda x: -x[1])[:5]:
                html.append(f"{device} ({count}) ")
            html.append("</div>")

        html.append("</div>")

    html.append(f"<div class='timestamp'>Generado: {datetime.now(ZONA_CDMX).strftime('%d/%m/%Y %H:%M:%S')}</div>")
    html.append("</div>")
    html.append("</body>")
    html.append("</html>")

    return "\n".join(html)


async def generar_y_guardar_reportes():
    """Genera y guarda reportes en archivos."""
    print("\n" + "=" * 70)
    print("  GENERADOR DE REPORTES DIARIOS DE CITAS")
    print("=" * 70 + "\n")

    # Obtener citas
    citas_7dias = await obtener_citas_rango(dias=7)
    citas_hoy = await obtener_citas_hoy()

    # Reporte de hoy
    print("📅 REPORTE DE HOY")
    print(generar_reporte_texto(citas_hoy, "CITAS DE HOY"))

    # Guardar reporte de hoy como HTML
    html_hoy = generar_reporte_html(citas_hoy, "CITAS DE HOY")
    with open("reportes/reporte_hoy.html", "w", encoding="utf-8") as f:
        f.write(html_hoy)
    print("\n✅ Guardado: reportes/reporte_hoy.html")

    # Reporte de próximos 7 días
    print("\n" + "=" * 70)
    print("📅 REPORTE DE PRÓXIMOS 7 DÍAS")
    print(generar_reporte_texto(citas_7dias, "CITAS PRÓXIMOS 7 DÍAS"))

    # Guardar reporte de 7 días como HTML
    html_7dias = generar_reporte_html(citas_7dias, "CITAS PRÓXIMOS 7 DÍAS")
    with open("reportes/reporte_7dias.html", "w", encoding="utf-8") as f:
        f.write(html_7dias)
    print("\n✅ Guardado: reportes/reporte_7dias.html")

    await engine.dispose()


def obtener_reporte_texto_hoy() -> str:
    """Obtiene el reporte de hoy como texto (para enviar por WhatsApp)."""
    citas = asyncio.run(obtener_citas_hoy())
    return generar_reporte_texto(citas, "CITAS DE HOY")


if __name__ == "__main__":
    # Crear carpeta de reportes si no existe
    os.makedirs("reportes", exist_ok=True)

    # Generar reportes
    asyncio.run(generar_y_guardar_reportes())

    print("\n✅ Reportes generados exitosamente")
    print("\nPara abrir los reportes:")
    print("  • Hoy: open reportes/reporte_hoy.html")
    print("  • 7 días: open reportes/reporte_7dias.html")
