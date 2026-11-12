#!/usr/bin/env python3
# scripts/diagnostico_pendientes.py — SOLO LECTURA: ¿por qué los pendientes (CRM ∩ bot) no se pueden etiquetar?
"""
Uso:  python scripts/diagnostico_pendientes.py 2>&1 | cut -c1-150
Por cada cliente pendiente imprime una línea: formato del ID guardado por el bot, nº de mensajes,
primer/último mensaje, fecha de su última nota en el CRM y el HTTP de Whapi (/chats/{id}) para
cada variante de ID (guardado, 52+10, 521+10). Al final, resumen de formatos y fechas. No modifica nada.
"""
import asyncio
import os
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import httpx  # noqa: E402
from dotenv import load_dotenv  # noqa: E402

load_dotenv()
from sqlalchemy import func, select  # noqa: E402

from agent.etiquetas import telefonos_con_nota_servicio  # noqa: E402
from agent.memory import Mensaje, async_session, inicializar_db  # noqa: E402
from agent.sync_clientes_crm import WHAPI, telefonos_bot, telefonos_crm, tel10  # noqa: E402


async def fechas_crm() -> dict:
    """tel10 -> fecha (YYYY-MM-DD) de su última nota en el CRM."""
    url, clave = os.getenv("CRM_API_URL", "").strip().rstrip("/"), os.getenv("SYNC_API_KEY", "").strip()
    async with httpx.AsyncClient(timeout=60) as c:
        for _ in range(4):
            r = await c.post(f"{url}/api/sync/export", headers={"x-sync-api-key": clave})
            if r.status_code != 429:
                break
            await asyncio.sleep(12)
        r.raise_for_status()
    t = r.json().get("tables", {}).get("transactions", [])
    filas = (t.get("records") or t.get("data") or []) if isinstance(t, dict) else t
    out = {}
    for f in filas:
        k = tel10(f.get("clientephone", ""))
        ts = f.get("fecha")
        try:
            from datetime import datetime, timezone
            d = datetime.fromtimestamp(int(ts), timezone.utc).strftime("%Y-%m-%d")
        except Exception:
            d = str(ts)[:10]
        if k and d > out.get(k, ""):
            out[k] = d
    return out


async def main():
    await inicializar_db()
    crm, bot = await telefonos_crm(), await telefonos_bot()
    await asyncio.sleep(11)  # el CRM limita 1 petición / 10 s
    fcrm = await fechas_crm()
    ya = await telefonos_con_nota_servicio(forzar=True)
    pend = sorted((crm & bot) - ya)
    print(f"Pendientes: {len(pend)}")

    async with async_session() as s:
        filas = (await s.execute(
            select(Mensaje.telefono, func.count(), func.min(Mensaje.timestamp), func.max(Mensaje.timestamp))
            .group_by(Mensaje.telefono))).all()
    por_tel = {}
    for raw, n, a, b in filas:
        t = tel10(raw)
        if t:
            por_tel.setdefault(t, []).append((raw, n, a, b))

    h = {"Authorization": f"Bearer {os.getenv('WHAPI_TOKEN', '').strip()}"}
    formatos, resultados = Counter(), Counter()
    async with httpx.AsyncClient(timeout=30) as c:
        for t in pend:
            ids = por_tel.get(t, [])
            for raw, n, a, b in ids:
                suf = raw[raw.find("@"):] if "@" in raw else f"dígitos{len(raw)}"
                formatos[suf] += 1
                cand = list(dict.fromkeys([raw if "@" in raw else f"{raw}@s.whatsapp.net",
                                           f"52{t}@s.whatsapp.net", f"521{t}@s.whatsapp.net"]))
                codigos = []
                for cid in cand:
                    try:
                        r = await c.get(f"{WHAPI}/chats/{cid}", headers=h)
                        codigos.append(f"{len(cid)}:{r.status_code}")
                    except Exception:
                        codigos.append(f"{len(cid)}:red")
                    await asyncio.sleep(0.4)
                resultados["200" if any(x.endswith(":200") for x in codigos) else "sin chat"] += 1
                print(f"{t[:3]}…{t[-3:]} {suf:>14} msgs={n:<3} bot={str(a)[:10]}→{str(b)[:10]} "
                      f"crm={fcrm.get(t, '?')} whapi[{' '.join(codigos)}]")
    print("\nFormatos de ID:", dict(formatos))
    print("Whapi conoce el chat:", dict(resultados))


if __name__ == "__main__":
    asyncio.run(main())
