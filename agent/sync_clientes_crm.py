# agent/sync_clientes_crm.py — Cruza clientes del CRM con los chats del bot y los etiqueta en WhatsApp
"""
Lógica compartida por el script manual (scripts/etiquetar_clientes_crm.py)
y la tarea semanal del bot (miércoles 03:00 CDMX, silenciosa: solo logs).

Cruce por los ÚLTIMOS 10 DÍGITOS del teléfono.
Modos (variable CRM_ETIQUETAS_AUTO): "apagado" | "simular" (default) | "aplicar".
"""

import asyncio
import csv
import logging
import os
import re

import httpx
from sqlalchemy import select

from agent.etiquetas import _norm, nombre_etiqueta, telefonos_con_nota_servicio
from agent.memory import Mensaje, async_session

logger = logging.getLogger("agentkit")
WHAPI = "https://gate.whapi.cloud"


def tel10(valor) -> str:
    """Últimos 10 dígitos; '' si no es un teléfono válido (ej. 's/n')."""
    digitos = re.sub(r"\D", "", str(valor or ""))
    return digitos[-10:] if len(digitos) >= 10 else ""


async def telefonos_crm(csv_ruta: str | None = None) -> set[str]:
    """Teléfonos de la tabla transactions del Auto-CRM (endpoint de sync o CSV)."""
    if csv_ruta:
        with open(csv_ruta, encoding="utf-8-sig") as f:
            return {t for t in (tel10(r.get("Teléfono", "")) for r in csv.DictReader(f)) if t}
    url = os.getenv("CRM_API_URL", "").strip().rstrip("/")
    clave = os.getenv("SYNC_API_KEY", "").strip()  # Railway puede guardar saltos de línea al pegar
    if not url or not clave:
        raise RuntimeError("Falta CRM_API_URL y/o SYNC_API_KEY")
    async with httpx.AsyncClient(timeout=60) as c:
        # El CRM limita /api/sync/export a 1 petición cada 10 s (y la laptop sincroniza cada 5 min):
        # si responde 429, esperar y reintentar.
        for intento in range(4):
            r = await c.post(f"{url}/api/sync/export", headers={"x-sync-api-key": clave})
            if r.status_code != 429:
                break
            logger.info(f"[CRM-ETIQUETAS] CRM respondió 429; reintento {intento + 1}/3 en 12 s")
            await asyncio.sleep(12)
        r.raise_for_status()
    tabla = r.json().get("tables", {}).get("transactions", [])
    filas = (tabla.get("records") or tabla.get("data") or []) if isinstance(tabla, dict) else tabla
    logger.info(f"[CRM-ETIQUETAS] CRM devolvió {len(filas)} transacciones")
    return {t for t in (tel10(f.get("clientephone", "")) for f in filas) if t}


async def telefonos_bot() -> set[str]:
    async with async_session() as s:
        res = await s.execute(select(Mensaje.telefono).distinct())
    return {t for t in (tel10(x) for x in res.scalars().all()) if t}


async def chat_ids_bot() -> dict[str, str]:
    """tel10 -> chat_id exacto que Whapi le dio al bot (ej. '5215512345678@s.whatsapp.net')."""
    async with async_session() as s:
        res = await s.execute(select(Mensaje.telefono).distinct())
    ids: dict[str, str] = {}
    for raw in res.scalars().all():
        t = tel10(raw)
        if t:
            ids[t] = raw if "@" in raw else f"{raw}@s.whatsapp.net"
    return ids


async def _id_etiqueta(c: httpx.AsyncClient, h: dict) -> str:
    r = await c.get(f"{WHAPI}/labels", headers=h)
    r.raise_for_status()
    data = r.json()
    lista = data.get("labels", data) if isinstance(data, dict) else data
    for et in lista:
        if _norm(et.get("name", "")) == nombre_etiqueta():
            return str(et["id"])
    raise RuntimeError(f"No existe la etiqueta '{nombre_etiqueta()}' en WhatsApp Business")


async def etiquetar_chat(c: httpx.AsyncClient, h: dict, lid: str, tel: str, chat_id: str | None = None) -> bool:
    # Endpoint de Whapi para asociar etiqueta a un chat. Se usa el chat_id real del bot si existe;
    # si no, se adivina 52+10 dígitos (puede dar 404 si ese chat no existe en esta línea).
    chat = chat_id or f"52{tel}@s.whatsapp.net"
    r = await c.post(f"{WHAPI}/labels/{lid}/{chat}", headers=h)
    if r.status_code not in (200, 201):
        logger.warning(f"[CRM-ETIQUETAS] {tel[:3]}…{tel[-3:]}: HTTP {r.status_code} {r.text[:120]}")
    return r.status_code in (200, 201)


async def sincronizar(aplicar: bool = False, todos_crm: bool = False,
                      csv_ruta: str | None = None, solo: str | None = None) -> dict:
    """Calcula (y opcionalmente aplica) las etiquetas pendientes. Devuelve el resumen."""
    crm = await telefonos_crm(csv_ruta)
    bot = await telefonos_bot()
    convertidos = crm if todos_crm else crm & bot
    ya = await telefonos_con_nota_servicio(forzar=True)
    pendientes = sorted(convertidos - ya)
    resumen = {"crm": len(crm), "bot": len(bot), "convertidos": len(crm & bot),
               "ya_etiquetados": len(convertidos & ya), "pendientes": len(pendientes), "etiquetados": 0}
    destino = [tel10(solo)] if solo else (pendientes if aplicar else [])
    if destino:
        h = {"Authorization": f"Bearer {os.getenv('WHAPI_TOKEN', '').strip()}"}
        ids = await chat_ids_bot()
        async with httpx.AsyncClient(timeout=30) as c:
            lid = await _id_etiqueta(c, h)
            for t in destino:
                if t not in ids:
                    logger.warning(f"[CRM-ETIQUETAS] {t[:3]}…{t[-3:]}: el bot no tiene ese chat; se intenta 52+10 dígitos")
                resumen["etiquetados"] += await etiquetar_chat(c, h, lid, t, ids.get(t))
                await asyncio.sleep(1.5)  # sin ráfagas
    resumen["pendientes_lista"] = pendientes
    return resumen
