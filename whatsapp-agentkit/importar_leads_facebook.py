# importar_leads_facebook.py — Importa leads de Facebook Ads desde el 19 de marzo
# Detecta: conversaciones que inician con imagen (clic en anuncio de Facebook)
# Uso: python importar_leads_facebook.py

import asyncio
import sys
import os
from datetime import datetime, timezone

sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import httpx
from dotenv import load_dotenv
load_dotenv()

WHAPI_TOKEN = os.getenv("WHAPI_TOKEN")
WHAPI_BASE  = "https://gate.whapi.cloud"

# Fecha de inicio de campaña: 19 de marzo de 2026
INICIO_CAMPANA = datetime(2026, 3, 19, 0, 0, 0, tzinfo=timezone.utc)
INICIO_TS = int(INICIO_CAMPANA.timestamp())

TIPOS_IMAGEN = {"image", "sticker", "document", "video"}  # todos los adjuntos típicos de un anuncio


def _headers():
    return {"Authorization": f"Bearer {WHAPI_TOKEN}"}


async def obtener_chats_desde_campana() -> list[dict]:
    """Obtiene chats cuyo último mensaje es posterior al inicio de campaña."""
    chats_validos = []
    offset = 0
    count  = 100

    async with httpx.AsyncClient(timeout=30) as http:
        while True:
            r = await http.get(
                f"{WHAPI_BASE}/chats",
                headers=_headers(),
                params={"count": count, "offset": offset}
            )
            if r.status_code != 200:
                break

            lote = r.json().get("chats", [])
            if not lote:
                break

            for chat in lote:
                if chat.get("type") != "contact":
                    continue
                ts = chat.get("timestamp", 0)
                if ts >= INICIO_TS:
                    chats_validos.append(chat)

            if len(lote) < count:
                break
            offset += count

    return chats_validos


async def primer_mensaje_cliente(chat_id: str) -> dict | None:
    """Retorna el primer mensaje enviado por el cliente (no from_me) en el chat."""
    async with httpx.AsyncClient(timeout=30) as http:
        # Pedir suficientes mensajes para encontrar el primero del cliente
        r = await http.get(
            f"{WHAPI_BASE}/messages/list/{chat_id}",
            headers=_headers(),
            params={"count": 50}
        )
        if r.status_code != 200:
            return None

    mensajes = r.json().get("messages", [])
    # Ordenar del más antiguo al más reciente
    mensajes.sort(key=lambda m: m.get("timestamp", 0))

    for msg in mensajes:
        if not msg.get("from_me", True):  # mensaje del cliente
            return msg
    return None


async def obtener_mensajes_texto(chat_id: str, cantidad: int = 20) -> list[dict]:
    """Obtiene los últimos mensajes de texto del chat para guardar en memoria."""
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
        if msg.get("type") == "text":
            texto = msg.get("text", {}).get("body", "").strip()
            if texto:
                mensajes.append({
                    "role": "assistant" if msg.get("from_me") else "user",
                    "content": texto,
                    "timestamp": msg.get("timestamp", 0),
                })
    mensajes.sort(key=lambda m: m["timestamp"])
    return mensajes


async def main():
    print()
    print("=" * 62)
    print("   Tecnology Support — Importador de Leads de Facebook Ads")
    print("=" * 62)
    print(f"   Campana desde: 19 de marzo de 2026")
    print(f"   Patron: primer mensaje del cliente es imagen (clic en anuncio)")
    print("=" * 62)
    print()

    from agent.leads import Lead, async_session, _migrar_columnas, crear_o_actualizar_lead
    from agent.memory import inicializar_db, guardar_mensaje, obtener_historial
    from agent.reports import generar_reporte_excel
    from sqlalchemy import select, update

    await inicializar_db()
    await _migrar_columnas()

    # Leads ya en sistema
    async with async_session() as session:
        existentes = set(
            row[0] for row in (await session.execute(select(Lead.telefono))).all()
        )

    print("  Buscando chats desde el 19 de marzo...")
    chats = await obtener_chats_desde_campana()
    print(f"  Chats encontrados en ese periodo: {len(chats)}")
    print()

    nuevos_fb   = []
    ya_estaban  = []
    no_imagen   = []

    for i, chat in enumerate(chats, 1):
        chat_id = chat.get("id", "")
        telefono = chat_id.replace("@s.whatsapp.net", "").replace("@c.us", "")
        nombre   = chat.get("name") or chat.get("notify") or telefono

        print(f"  [{i}/{len(chats)}] {nombre[:40]:<40}", end=" ", flush=True)

        primer = await primer_mensaje_cliente(chat_id)

        if primer is None:
            print("sin mensajes")
            no_imagen.append(telefono)
            continue

        tipo_primer = primer.get("type", "")
        es_imagen   = tipo_primer in TIPOS_IMAGEN

        if not es_imagen:
            print(f"texto ({tipo_primer}) — no es ad")
            no_imagen.append(telefono)
            continue

        # Es imagen — lead de Facebook Ad
        print(f"FACEBOOK AD ({tipo_primer})")

        if telefono in existentes:
            # Ya está: solo actualizar fuente si era desconocido
            async with async_session() as session:
                result = await session.execute(select(Lead).where(Lead.telefono == telefono))
                lead = result.scalar_one_or_none()
                if lead and (getattr(lead, "fuente", "desconocido") in ("desconocido", "organico", None, "")):
                    await session.execute(
                        update(Lead)
                        .where(Lead.telefono == telefono)
                        .values(
                            fuente="facebook_ad",
                            fuente_detalle=f"Primer mensaje: imagen ({tipo_primer}), campana desde 19/03/2026"
                        )
                    )
                    await session.commit()
                    nuevos_fb.append({"telefono": telefono, "nombre": nombre, "era_existente": True})
            ya_estaban.append(telefono)
            continue

        # Lead nuevo — importar
        mensajes_texto = await obtener_mensajes_texto(chat_id)

        await crear_o_actualizar_lead(
            telefono,
            fuente="facebook_ad",
            fuente_detalle=f"Primer mensaje: imagen ({tipo_primer}), campana desde 19/03/2026"
        )

        for msg in mensajes_texto:
            await guardar_mensaje(telefono, msg["role"], msg["content"])

        # Marcar timestamp real
        ts_ultimo = chat.get("timestamp", 0)
        if ts_ultimo:
            from datetime import timedelta
            ultimo_dt = datetime.fromtimestamp(ts_ultimo, tz=timezone.utc)
            async with async_session() as session:
                await session.execute(
                    update(Lead)
                    .where(Lead.telefono == telefono)
                    .values(ultimo_mensaje=ultimo_dt)
                )
                await session.commit()

        nuevos_fb.append({"telefono": telefono, "nombre": nombre, "era_existente": False})
        existentes.add(telefono)

    print()
    print("=" * 62)
    print(f"  Facebook Ads detectados : {len(nuevos_fb)}")
    print(f"    - Nuevos importados   : {sum(1 for l in nuevos_fb if not l['era_existente'])}")
    print(f"    - Ya estaban (fuente actualizada): {sum(1 for l in nuevos_fb if l['era_existente'])}")
    print(f"  No eran ads (texto/vacios): {len(no_imagen)}")
    print()

    if nuevos_fb:
        print("  LEADS DE FACEBOOK ADS:")
        for lead in nuevos_fb:
            tag = "(ya estaba)" if lead["era_existente"] else "(nuevo)"
            print(f"    • {lead['nombre']} — {lead['telefono']} {tag}")
        print()

    print("  Generando reporte Excel actualizado...")
    ruta = await generar_reporte_excel()
    print(f"  Reporte guardado: {ruta}")
    print()
    print("=" * 62)
    print()


if __name__ == "__main__":
    asyncio.run(main())
