# agent/import_chats.py — Importador de chats existentes de Whapi.cloud
# Generado por AgentKit

import os
import logging
from datetime import datetime, timezone
from anthropic import AsyncAnthropic
import httpx
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger("agentkit")
client = AsyncAnthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

WHAPI_TOKEN = os.getenv("WHAPI_TOKEN")
WHAPI_BASE = "https://gate.whapi.cloud"


def _headers() -> dict:
    return {"Authorization": f"Bearer {WHAPI_TOKEN}", "Content-Type": "application/json"}


async def obtener_todos_los_chats() -> list[dict]:
    """Obtiene todos los chats de contacto (individuales) de Whapi."""
    chats_individuales = []
    offset = 0
    count = 100

    async with httpx.AsyncClient(timeout=30) as http:
        while True:
            r = await http.get(
                f"{WHAPI_BASE}/chats",
                headers=_headers(),
                params={"count": count, "offset": offset}
            )
            if r.status_code != 200:
                logger.error(f"Error obteniendo chats: {r.status_code}")
                break

            data = r.json()
            lote = data.get("chats", [])
            if not lote:
                break

            for chat in lote:
                if chat.get("type") == "contact":
                    chats_individuales.append(chat)

            # Si recibimos menos de `count`, ya terminamos
            if len(lote) < count:
                break
            offset += count

    logger.info(f"Chats individuales encontrados: {len(chats_individuales)}")
    return chats_individuales


async def obtener_mensajes_chat(chat_id: str, cantidad: int = 25) -> list[dict]:
    """Obtiene los últimos N mensajes de texto de un chat."""
    async with httpx.AsyncClient(timeout=30) as http:
        r = await http.get(
            f"{WHAPI_BASE}/messages/list/{chat_id}",
            headers=_headers(),
            params={"count": cantidad}
        )
        if r.status_code != 200:
            return []

    mensajes = []
    for msg in r.json().get("messages", []):
        # Solo mensajes de texto con contenido
        if msg.get("type") == "text":
            texto = msg.get("text", {}).get("body", "").strip()
            if texto:
                mensajes.append({
                    "role": "assistant" if msg.get("from_me") else "user",
                    "content": texto,
                    "timestamp": msg.get("timestamp", 0),
                })

    # Ordenar cronológicamente (Whapi devuelve del más reciente al más antiguo)
    mensajes.sort(key=lambda m: m["timestamp"])
    return mensajes


async def analizar_conversacion(historial: list[dict], nombre_contacto: str) -> dict:
    """
    Usa Claude para analizar la conversación y determinar:
    - Si es un cliente potencial de reparación
    - Nombre, dispositivo, problema
    - Etapa del funnel
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

Determina si es una conversación de un cliente potencial (alguien que preguntó por reparación, precio, o dejó de responder en medio de una consulta).

Si NO es un cliente potencial (conversación personal, spam, grupos, etc.), responde exactamente: NO_CLIENTE

Si SÍ es un cliente potencial, responde SOLO en este formato exacto:
Nombre: [nombre del cliente o el nombre del contacto si no lo dijo]
Dispositivo: [dispositivo mencionado, o "No especificado"]
Problema: [resumen del problema en máximo 8 palabras]
Estado: [activo|en_seguimiento|perdido|convertido]
Notas: [una línea con contexto relevante para dar seguimiento, o vacío]

Criterios de Estado:
- activo: conversación reciente (menos de 3 días), cliente todavía respondiendo
- en_seguimiento: cliente dejó de responder pero mostró interés real
- perdido: cliente claramente no interesado o conversación muy antigua sin seguimiento
- convertido: cliente agendó cita, fue al módulo o confirmó reparación"""

    try:
        response = await client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=150,
            messages=[{"role": "user", "content": prompt}]
        )
        texto = response.content[0].text.strip()

        if texto == "NO_CLIENTE":
            return None

        resultado = {
            "nombre": nombre_contacto,
            "dispositivo": "No especificado",
            "resumen": "Sin detalles",
            "estado": "en_seguimiento",
            "notas": "",
        }
        for linea in texto.splitlines():
            if linea.startswith("Nombre:"):
                resultado["nombre"] = linea.replace("Nombre:", "").strip()
            elif linea.startswith("Dispositivo:"):
                resultado["dispositivo"] = linea.replace("Dispositivo:", "").strip()
            elif linea.startswith("Problema:"):
                resultado["resumen"] = linea.replace("Problema:", "").strip()
            elif linea.startswith("Estado:"):
                estado = linea.replace("Estado:", "").strip().lower()
                if estado in ("activo", "en_seguimiento", "perdido", "convertido"):
                    resultado["estado"] = estado
            elif linea.startswith("Notas:"):
                resultado["notas"] = linea.replace("Notas:", "").strip()
        return resultado

    except Exception as e:
        logger.error(f"Error analizando conversación: {e}")
        return None


async def importar_todos_los_chats(callback_progreso=None) -> dict:
    """
    Importa y clasifica todos los chats existentes de Whapi.
    Retorna un resumen de la importación.

    Args:
        callback_progreso: función opcional(actual, total, info) para mostrar progreso
    """
    from agent.memory import inicializar_db, guardar_mensaje, obtener_historial
    from agent.leads import Lead, async_session, crear_o_actualizar_lead
    from sqlalchemy import select

    await inicializar_db()

    chats = await obtener_todos_los_chats()
    total = len(chats)
    importados = 0
    omitidos = 0
    ya_existentes = 0

    async with async_session() as session:
        leads_existentes = set(
            row[0] for row in (
                await session.execute(select(Lead.telefono))
            ).all()
        )

    for i, chat in enumerate(chats, start=1):
        chat_id = chat.get("id", "")
        # Extraer número limpio: "5219981234567@s.whatsapp.net" → "5219981234567"
        telefono = chat_id.replace("@s.whatsapp.net", "").replace("@c.us", "")
        nombre_contacto = chat.get("name") or chat.get("notify") or telefono

        if callback_progreso:
            callback_progreso(i, total, f"{nombre_contacto} ({telefono})")

        # Saltar si ya está en nuestra base de datos (agente ya lo atiende)
        if telefono in leads_existentes:
            ya_existentes += 1
            continue

        # Obtener mensajes
        historial_whapi = await obtener_mensajes_chat(chat_id)
        if not historial_whapi:
            omitidos += 1
            continue

        # Analizar con Claude
        analisis = await analizar_conversacion(historial_whapi, nombre_contacto)
        if analisis is None:
            omitidos += 1
            continue

        # Guardar en DB
        # Primero crear el lead con su estado correcto
        await crear_o_actualizar_lead(telefono)

        # Guardar historial de mensajes
        for msg in historial_whapi:
            await guardar_mensaje(telefono, msg["role"], msg["content"])

        # Actualizar el estado del lead según el análisis
        async with async_session() as session:
            from sqlalchemy import update
            from agent.leads import Lead
            ts_ultimo = datetime.fromtimestamp(
                historial_whapi[-1]["timestamp"], tz=timezone.utc
            ) if historial_whapi else datetime.utcnow()

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

    resumen = {
        "total_chats": total,
        "importados": importados,
        "omitidos_no_clientes": omitidos,
        "ya_en_sistema": ya_existentes,
    }
    logger.info(f"Importación completada: {resumen}")
    return resumen
