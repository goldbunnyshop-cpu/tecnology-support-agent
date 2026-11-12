#!/usr/bin/env python3
# scripts/diagnostico_numero.py — SOLO LECTURA: ¿dónde existe este número? (BD del bot, CRM, Whapi)
"""
Uso:  python scripts/diagnostico_numero.py 5579940312
Muestra: filas del bot (formato de ID, cantidad, primer/último mensaje), notas del CRM (sin nombres)
y el código HTTP de Whapi para cada variante posible del ID del chat. No modifica nada.
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import httpx  # noqa: E402
from dotenv import load_dotenv  # noqa: E402

load_dotenv()
from sqlalchemy import func, select  # noqa: E402

from agent.memory import Mensaje, async_session, inicializar_db  # noqa: E402
from agent.sync_clientes_crm import WHAPI, tel10  # noqa: E402


async def main(tel: str):
    tel = tel10(tel)
    await inicializar_db()
    print(f"== Número {tel[:3]}…{tel[-3:]} ==")

    # 1) BD del bot
    async with async_session() as s:
        q = (select(Mensaje.telefono, func.count(), func.min(Mensaje.timestamp), func.max(Mensaje.timestamp))
             .where(Mensaje.telefono.like(f"%{tel}%")).group_by(Mensaje.telefono))
        filas = (await s.execute(q)).all()
    print(f"[BOT] ids distintos con ese número: {len(filas)}")
    ids = []
    for raw, n, primero, ultimo in filas:
        sufijo = raw[raw.find("@"):] if "@" in raw else "(sin @)"
        print(f"  formato=…{sufijo} largo={len(raw)} mensajes={n} primero={str(primero)[:16]} ultimo={str(ultimo)[:16]}")
        ids.append(raw if "@" in raw else f"{raw}@s.whatsapp.net")

    # 2) CRM (sin nombres)
    url, clave = os.getenv("CRM_API_URL", "").strip().rstrip("/"), os.getenv("SYNC_API_KEY", "").strip()
    try:
        async with httpx.AsyncClient(timeout=60) as c:
            for _ in range(4):
                r = await c.post(f"{url}/api/sync/export", headers={"x-sync-api-key": clave})
                if r.status_code != 429:
                    break
                await asyncio.sleep(12)
            r.raise_for_status()
        tabla = r.json().get("tables", {}).get("transactions", [])
        filas_crm = (tabla.get("records") or tabla.get("data") or []) if isinstance(tabla, dict) else tabla
        mias = [f for f in filas_crm if tel10(f.get("clientephone", "")) == tel]
        print(f"[CRM] notas con ese teléfono: {len(mias)}")
        for f in mias[:5]:
            print(f"  folio={f.get('folio')} fecha={str(f.get('fecha'))[:10]} total={f.get('total')} pago={f.get('formapago')}")
    except Exception as e:
        print(f"[CRM] error: {str(e)[:100]}")

    # 3) Whapi: ¿conoce el chat?
    h = {"Authorization": f"Bearer {os.getenv('WHAPI_TOKEN', '').strip()}"}
    candidatos = list(dict.fromkeys(ids + [f"52{tel}@s.whatsapp.net", f"521{tel}@s.whatsapp.net"]))
    async with httpx.AsyncClient(timeout=30) as c:
        for cid in candidatos:
            r = await c.get(f"{WHAPI}/chats/{cid}", headers=h)
            extra = ""
            if r.status_code == 200:
                d = r.json()
                extra = f" claves={sorted(d)[:8]} etiquetas={d.get('labels')}"
            print(f"[WHAPI] GET /chats/…{cid[cid.find('@'):]} (len {len(cid)}) -> HTTP {r.status_code}{extra}")


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1]))
