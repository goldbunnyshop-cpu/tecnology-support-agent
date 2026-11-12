# agent/etiquetas.py — Etiquetas de WhatsApp Business ("Cliente con nota de servicio")
#
# Christian marca en WhatsApp Business a los clientes que ya visitaron el taller con la
# etiqueta "Cliente con nota de servicio". Esos clientes NO reciben seguimientos de venta
# ni retomas: su equipo ya está con nosotros (o ya se entregó).
#
# Lee las etiquetas con la API de Whapi. Si la API falla, NO se bloquea nada (comportamiento
# de siempre) y queda un error en logs.
#
# Variable opcional: ETIQUETA_NOTA_SERVICIO (default "cliente con nota de servicio").

import os
import re
import time
import logging
import unicodedata

import httpx

logger = logging.getLogger("agentkit")

_CACHE_SEG = 600          # 10 minutos
_cache = {"ts": 0.0, "telefonos": set(), "ok": False}


def _norm(t: str) -> str:
    t = unicodedata.normalize("NFD", (t or "").lower())
    return re.sub(r"\s+", " ", "".join(c for c in t if unicodedata.category(c) != "Mn")).strip()


def nombre_etiqueta() -> str:
    return _norm(os.getenv("ETIQUETA_NOTA_SERVICIO", "cliente con nota de servicio"))


def _tel10(x: str) -> str:
    d = "".join(ch for ch in str(x or "") if ch.isdigit())
    return d[-10:] if len(d) >= 10 else ""


def _ids_de_chats(data) -> list[str]:
    """Saca los chat_id de cualquier forma de respuesta (cambia según motor/proveedor)."""
    ids: list[str] = []

    def visitar(x):
        if isinstance(x, str):
            if re.fullmatch(r"\d{6,}@(c\.us|s\.whatsapp\.net|lid)", x):
                ids.append(x)
        elif isinstance(x, dict):
            for k in ("id", "chatId", "chat_id", "_serialized", "jid"):
                if k in x:
                    visitar(x[k])
            for k in ("chats", "items", "objects", "data"):
                if k in x:
                    visitar(x[k])
        elif isinstance(x, list):
            for i in x:
                visitar(i)

    visitar(data)
    return ids


async def _labels_whapi(c: httpx.AsyncClient) -> list[str]:
    h = {"Authorization": f"Bearer {os.getenv('WHAPI_TOKEN', '')}"}
    r = await c.get("https://gate.whapi.cloud/labels", headers=h)
    r.raise_for_status()
    data = r.json()
    lista = data.get("labels", data) if isinstance(data, dict) else data
    objetivo = nombre_etiqueta()
    ids = [str(l.get("id")) for l in lista if _norm(l.get("name", "")) == objetivo]
    if not ids:
        logger.warning(f"[ETIQUETAS] No existe la etiqueta '{objetivo}' en WhatsApp Business")
        return []
    chats: list[str] = []
    for lid in ids:
        r = await c.get(f"https://gate.whapi.cloud/labels/{lid}", headers=h)
        r.raise_for_status()
        crudo = r.json()
        nuevos = _ids_de_chats(crudo)
        # Diagnóstico (sin datos personales): forma de la respuesta y cuántos chats trae
        logger.info(
            f"[ETIQUETAS] Whapi etiqueta {lid}: claves={sorted(crudo) if isinstance(crudo, dict) else type(crudo).__name__} "
            f"chats={len(nuevos)}"
        )
        chats += nuevos
    return chats


async def telefonos_con_nota_servicio(forzar: bool = False) -> set[str]:
    """Últimos 10 dígitos de los clientes con la etiqueta. Cache de 10 min."""
    if not forzar and time.time() - _cache["ts"] < _CACHE_SEG:
        return _cache["telefonos"]
    proveedor = os.getenv("WHATSAPP_PROVIDER", "whapi").lower()
    try:
        async with httpx.AsyncClient(timeout=15) as c:
            chats = await _labels_whapi(c) if proveedor == "whapi" else []
        tels = {t for t in (_tel10(x) for x in chats) if t}
        _cache.update(ts=time.time(), telefonos=tels, ok=True)
        logger.info(f"[ETIQUETAS] '{nombre_etiqueta()}': {len(tels)} clientes")
    except Exception as e:
        # Si falla, se reintenta en 10 min y NO se bloquea a nadie
        _cache.update(ts=time.time(), ok=False)
        logger.error(f"[ETIQUETAS] No se pudieron leer las etiquetas ({proveedor}): {e}")
    return _cache["telefonos"]


async def tiene_nota_servicio(telefono: str) -> bool:
    t = _tel10(telefono)
    return bool(t) and t in await telefonos_con_nota_servicio()
