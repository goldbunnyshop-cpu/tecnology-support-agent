#!/usr/bin/env python3
# scripts/etiquetar_clientes_crm.py — Cruza el CRM con los chats del bot y etiqueta en WhatsApp
"""
Qué hace:
  1. Lee los teléfonos de clientes con orden/nota en el Auto-CRM (tabla transactions).
  2. Lee los teléfonos que el bot atendió (tabla mensajes de la BD del bot).
  3. Cruza por los ÚLTIMOS 10 DÍGITOS => "clientes que se convirtieron después del bot".
  4. Quita los que ya tienen la etiqueta en WhatsApp (vía Whapi).
  5. Etiqueta el resto con "cliente con nota de servicio" (solo con --aplicar).

Por defecto es SIMULACIÓN: no cambia nada en WhatsApp.

Uso:
  python scripts/etiquetar_clientes_crm.py                       # simulación
  python scripts/etiquetar_clientes_crm.py --probar 5512345678   # etiqueta SOLO ese número
  python scripts/etiquetar_clientes_crm.py --aplicar             # etiqueta todos los pendientes
  python scripts/etiquetar_clientes_crm.py --todos-crm           # no exige que el bot los haya atendido

Variables de entorno: WHAPI_TOKEN, DATABASE_URL (BD del bot),
  CRM_API_URL (ej. https://auto-crm-production-8dd5.up.railway.app) y SYNC_API_KEY (del CRM).
Sin CRM_API_URL/SYNC_API_KEY usa un CSV: --csv ruta/transacciones_export.csv
"""

import argparse
import asyncio
import csv
import os
import re
import sys

import httpx
from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
load_dotenv()

from sqlalchemy import select  # noqa: E402

from agent.etiquetas import _norm, nombre_etiqueta, telefonos_con_nota_servicio  # noqa: E402
from agent.memory import Mensaje, async_session, inicializar_db  # noqa: E402

WHAPI = "https://gate.whapi.cloud"


def tel10(valor: str) -> str:
    """Últimos 10 dígitos; '' si no hay un teléfono válido (ej. 's/n')."""
    digitos = re.sub(r"\D", "", str(valor or ""))
    return digitos[-10:] if len(digitos) >= 10 else ""


async def telefonos_crm(csv_ruta: str | None) -> set[str]:
    if csv_ruta:
        with open(csv_ruta, encoding="utf-8-sig") as f:
            return {t for t in (tel10(r.get("Teléfono", "")) for r in csv.DictReader(f)) if t}
    url, clave = os.getenv("CRM_API_URL", "").rstrip("/"), os.getenv("SYNC_API_KEY", "")
    if not url or not clave:
        sys.exit("Falta CRM_API_URL y SYNC_API_KEY (o usa --csv).")
    async with httpx.AsyncClient(timeout=60) as c:
        r = await c.post(f"{url}/api/sync/export", headers={"x-sync-api-key": clave})
        r.raise_for_status()
    tabla = r.json().get("tables", {}).get("transactions", [])
    filas = tabla.get("records") or tabla.get("data") or [] if isinstance(tabla, dict) else tabla
    print(f"CRM: {len(filas)} transacciones recibidas")
    return {t for t in (tel10(f.get("clientephone", "")) for f in filas) if t}


async def telefonos_bot() -> set[str]:
    async with async_session() as s:
        res = await s.execute(select(Mensaje.telefono).distinct())
    return {t for t in (tel10(x) for x in res.scalars().all()) if t}


async def id_etiqueta(c: httpx.AsyncClient, h: dict) -> str:
    r = await c.get(f"{WHAPI}/labels", headers=h)
    r.raise_for_status()
    data = r.json()
    lista = data.get("labels", data) if isinstance(data, dict) else data
    for et in lista:
        if _norm(et.get("name", "")) == nombre_etiqueta():
            return str(et["id"])
    sys.exit(f"No existe la etiqueta '{nombre_etiqueta()}' en WhatsApp Business.")


async def etiquetar(c: httpx.AsyncClient, h: dict, lid: str, tel: str) -> bool:
    # Endpoint de Whapi para asociar etiqueta a un chat (NO verificado en la doc: por eso existe --probar)
    chat = f"52{tel}@s.whatsapp.net"
    r = await c.post(f"{WHAPI}/labels/{lid}/{chat}", headers=h)
    if r.status_code not in (200, 201):
        print(f"  ✗ {tel}: HTTP {r.status_code} {r.text[:150]}")
    return r.status_code in (200, 201)


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv")
    ap.add_argument("--probar", metavar="TEL10")
    ap.add_argument("--aplicar", action="store_true")
    ap.add_argument("--todos-crm", action="store_true")
    a = ap.parse_args()

    await inicializar_db()  # no-op si las tablas ya existen
    crm = await telefonos_crm(a.csv)
    bot = await telefonos_bot()
    convertidos = crm if a.todos_crm else crm & bot
    ya = await telefonos_con_nota_servicio(forzar=True)
    pendientes = sorted(convertidos - ya)

    print(f"Teléfonos únicos en CRM:            {len(crm)}")
    print(f"Teléfonos que el bot atendió:       {len(bot)}")
    print(f"Convertidos (CRM ∩ bot):            {len(crm & bot)}")
    print(f"Ya tienen la etiqueta (Whapi):      {len(convertidos & ya)}")
    print(f"Pendientes de etiquetar:            {len(pendientes)}")

    if not (a.probar or a.aplicar):
        print("\nSimulación: no se cambió nada. Primeros pendientes:", ", ".join(p[:3] + "…" + p[-3:] for p in pendientes[:10]))
        return

    h = {"Authorization": f"Bearer {os.getenv('WHAPI_TOKEN', '')}"}
    async with httpx.AsyncClient(timeout=30) as c:
        lid = await id_etiqueta(c, h)
        destino = [tel10(a.probar)] if a.probar else pendientes
        ok = 0
        for t in destino:
            ok += await etiquetar(c, h, lid, t)
            await asyncio.sleep(1.5)  # sin ráfagas para no alertar a WhatsApp
    print(f"Etiquetados: {ok}/{len(destino)}")


if __name__ == "__main__":
    asyncio.run(main())
