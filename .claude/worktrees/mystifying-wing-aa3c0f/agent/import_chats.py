# agent/import_chats.py — Importador de chats existentes de Whapi.cloud

import os
import logging
from datetime import datetime, timezone, date
from typing import Callable
from anthropic import AsyncAnthropic
import httpx
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger("agentkit")
client = AsyncAnthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

WHAPI_TOKEN = os.getenv("WHAPI_TOKEN")
WHAPI_BASE  = "https://gate.whapi.cloud"


def _headers() -> dict:
    return {"Authorization": f"Bearer {WHAPI_TOKEN}", "Content-Type": "application/json"}


async def obtener_todos_los_chats() -> list[dict]:
    """Obtiene todos los chats individuales de Whapi (paginado de 100 en 100)."""
    chats = []
    offset = 0
    async with httpx.AsyncClient(timeout=30) as http:
        while True:
            r = await http.get(
                f"{WHAPI_BASE}/chats",
                headers=_headers(),
                params={"count": 100, "offset": offset},
            )
            if r.status_code != 200:
                logger.error(f"Error obteniendo chats: {r.status_code} — {r.text[:200]}")
                break
            lote = r.json().get("chats", [])
            if not lote:
                break
            chats.extend(c for c in lote if c.get("type") == "contact")
            if len(lote) < 100:
                break
            offset += 100
    logger.info(f"Chats individuales encontrados: {len(chats)}")
    return chats


async def obtener_mensajes_chat(chat_id: str, cantidad: int = 200) -> list[dict]:
    """Obtiene los últimos N mensajes de texto de un chat (orden cronológico)."""
    async with httpx.AsyncClient(timeout=30) as http:
        r = await http.get(
            f"{WHAPI_BASE}/messages/list/{chat_id}",
            headers=_headers(),
            params={"count": cantidad},
        )
        if r.status_code != 200:
            return []

    mensajes = []
    for msg in r.json().get("messages", []):
        if msg.get("type") == "text":
            texto = msg.get("text", {}).get("body", "").strip()
            if texto:
                mensajes.append({
                    "role":      "assistant" if msg.get("from_me") else "user",
                    "content":   texto,
                    "timestamp": msg.get("timestamp", 0),
                })

    mensajes.sort(key=lambda m: m["timestamp"])
    return mensajes


async def analizar_conversacion(historial: list[dict], nombre_contacto: str) -> dict | None:
    """
    Usa Claude para clasificar la conversación:
    cliente potencial → nombre, dispositivo, problema, estado.
    Retorna None si no es un cliente de reparación.
    """
    if not historial:
        return None

    fragmento = "\n".join(
        f"{'Negocio' if m['role'] == 'assistant' else 'Contacto'}: {m['content']}"
        for m in historial[-15:]
    )

    prompt = f"""Analiza esta conversación de WhatsApp de un taller de reparación de dispositivos electrónicos.
Nombre del contacto en WhatsApp: "{nombre_contacto}"

Conversación:
{fragmento}

Si NO es un cliente potencial (conversación personal, spam, proveedor, etc.), responde exactamente: NO_CLIENTE

Si SÍ es un cliente potencial (preguntó por reparación, precio, o quedó sin respuesta), responde SOLO:
Nombre: [nombre del cliente o nombre del contacto]
Dispositivo: [dispositivo mencionado, o "No especificado"]
Problema: [resumen en máximo 8 palabras]
Estado: [activo|en_seguimiento|perdido|convertido]
Notas: [una línea de contexto para dar seguimiento, o vacío]

Criterios de Estado:
- activo: conversación reciente (menos de 3 días), cliente todavía respondiendo
- en_seguimiento: cliente dejó de responder pero mostró interés real
- perdido: cliente claramente no interesado o conversación muy antigua sin seguimiento
- convertido: cliente agendó cita, fue al módulo o confirmó reparación"""

    try:
        response = await client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=150,
            messages=[{"role": "user", "content": prompt}],
        )
        texto = response.content[0].text.strip()
        if texto == "NO_CLIENTE":
            return None

        resultado = {
            "nombre":     nombre_contacto,
            "dispositivo": "No especificado",
            "resumen":    "Sin detalles",
            "estado":     "en_seguimiento",
            "notas":      "",
        }
        for linea in texto.splitlines():
            if linea.startswith("Nombre:"):
                resultado["nombre"]     = linea.split(":", 1)[1].strip()
            elif linea.startswith("Dispositivo:"):
                resultado["dispositivo"] = linea.split(":", 1)[1].strip()
            elif linea.startswith("Problema:"):
                resultado["resumen"]    = linea.split(":", 1)[1].strip()
            elif linea.startswith("Estado:"):
                estado = linea.split(":", 1)[1].strip().lower()
                if estado in ("activo", "en_seguimiento", "perdido", "convertido"):
                    resultado["estado"] = estado
            elif linea.startswith("Notas:"):
                resultado["notas"]      = linea.split(":", 1)[1].strip()
        return resultado

    except Exception as e:
        logger.error(f"Error analizando conversación: {e}")
        return None


async def importar_todos_los_chats(
    desde: date | None = None,
    mensajes_por_chat: int = 200,
    reimportar: bool = False,
    callback_progreso: Callable | None = None,
) -> dict:
    """
    Importa y clasifica chats de Whapi con filtros opcionales.

    Args:
        desde:              Solo incluir mensajes con fecha >= esta fecha. None = sin filtro.
        mensajes_por_chat:  Cuántos mensajes traer por chat (default 200).
        reimportar:         Si True, procesa también chats ya existentes en DB.
        callback_progreso:  Función opcional(actual, total, info) para progreso.

    Returns:
        Diccionario con resumen detallado de la importación.
    """
    from agent.memory import inicializar_db, guardar_mensaje, obtener_historial
    from agent.leads import Lead, async_session, crear_o_actualizar_lead
    from sqlalchemy import select, update

    await inicializar_db()

    # Convertir la fecha de corte a timestamp Unix (inicio del día UTC)
    ts_desde: int | None = None
    if desde:
        ts_desde = int(datetime(desde.year, desde.month, desde.day, tzinfo=timezone.utc).timestamp())
        logger.info(f"[IMPORT] Filtro de fecha: desde {desde} (ts={ts_desde})")

    chats = await obtener_todos_los_chats()
    total = len(chats)

    # Leads ya en DB (para saber si saltar o no)
    async with async_session() as session:
        leads_existentes = set(
            row[0] for row in (await session.execute(select(Lead.telefono))).all()
        )

    importados       = 0
    omitidos         = 0
    ya_existentes    = 0
    sin_mensajes     = 0
    fechas_vistas: list[datetime] = []

    for i, chat in enumerate(chats, start=1):
        chat_id        = chat.get("id", "")
        telefono       = chat_id.replace("@s.whatsapp.net", "").replace("@c.us", "")
        nombre_contacto = chat.get("name") or chat.get("notify") or telefono

        if callback_progreso:
            callback_progreso(i, total, f"{nombre_contacto} ({telefono})")

        # Saltar si ya existe y no se pidió reimportar
        if telefono in leads_existentes and not reimportar:
            ya_existentes += 1
            continue

        # Obtener mensajes con la cantidad configurada
        historial_whapi = await obtener_mensajes_chat(chat_id, cantidad=mensajes_por_chat)
        if not historial_whapi:
            sin_mensajes += 1
            continue

        # Filtrar por fecha si se indicó
        if ts_desde is not None:
            historial_whapi = [m for m in historial_whapi if m["timestamp"] >= ts_desde]

        if not historial_whapi:
            omitidos += 1
            continue

        # Registrar rango de fechas para el resumen
        for m in historial_whapi:
            if m["timestamp"]:
                fechas_vistas.append(
                    datetime.fromtimestamp(m["timestamp"], tz=timezone.utc)
                )

        # Analizar con Claude
        analisis = await analizar_conversacion(historial_whapi, nombre_contacto)
        if analisis is None:
            omitidos += 1
            continue

        # Crear o actualizar lead
        await crear_o_actualizar_lead(telefono)

        # Guardar historial (solo mensajes nuevos si es reimport)
        if reimportar and telefono in leads_existentes:
            historial_db = await obtener_historial(telefono, limite=500)
            ts_ya_guardados = {m.get("content", "") for m in historial_db}
            historial_whapi = [
                m for m in historial_whapi if m["content"] not in ts_ya_guardados
            ]

        for msg in historial_whapi:
            await guardar_mensaje(telefono, msg["role"], msg["content"])

        # Actualizar estado del lead
        ts_ultimo = datetime.fromtimestamp(
            max(m["timestamp"] for m in historial_whapi), tz=timezone.utc
        ) if historial_whapi else datetime.utcnow()

        async with async_session() as session:
            await session.execute(
                update(Lead)
                .where(Lead.telefono == telefono)
                .values(estado=analisis["estado"], ultimo_mensaje=ts_ultimo)
            )
            await session.commit()

        importados += 1
        logger.info(
            f"[{i}/{total}] {analisis['nombre']} — {analisis['dispositivo']} "
            f"— {analisis['estado']} — {analisis['resumen']}"
        )

    # Calcular rango real de fechas procesadas
    fecha_mas_antigua = None
    fecha_mas_reciente = None
    if fechas_vistas:
        fecha_mas_antigua  = min(fechas_vistas).strftime("%Y-%m-%d")
        fecha_mas_reciente = max(fechas_vistas).strftime("%Y-%m-%d")

    resumen = {
        "total_chats_en_whapi":     total,
        "chats_procesados":         importados + omitidos,
        "clientes_nuevos_encontrados": importados,
        "omitidos_no_clientes":     omitidos,
        "sin_mensajes_en_rango":    sin_mensajes,
        "ya_en_sistema_saltados":   ya_existentes,
        "filtro_desde":             str(desde) if desde else "sin filtro",
        "mensajes_por_chat":        mensajes_por_chat,
        "reimportar":               reimportar,
        "fecha_mensaje_mas_antiguo": fecha_mas_antigua,
        "fecha_mensaje_mas_reciente": fecha_mas_reciente,
    }
    logger.info(f"[IMPORT] Completado: {resumen}")
    return resumen
