#!/usr/bin/env python3
# scripts/etiquetar_clientes_crm.py — Cruza el CRM con los chats del bot y etiqueta en WhatsApp
"""
Por defecto es SIMULACIÓN (no cambia nada en WhatsApp).

  python scripts/etiquetar_clientes_crm.py                       # simulación
  python scripts/etiquetar_clientes_crm.py --probar 5512345678   # etiqueta SOLO ese número
  python scripts/etiquetar_clientes_crm.py --aplicar             # etiqueta todos los pendientes
  python scripts/etiquetar_clientes_crm.py --todos-crm           # no exige que el bot los haya atendido
  python scripts/etiquetar_clientes_crm.py --csv ruta.csv        # usa un CSV en vez del endpoint del CRM

Variables: WHAPI_TOKEN, DATABASE_URL, CRM_API_URL, SYNC_API_KEY.
"""
import argparse
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dotenv import load_dotenv  # noqa: E402

load_dotenv()
from agent.memory import inicializar_db  # noqa: E402
from agent.sync_clientes_crm import sincronizar  # noqa: E402


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv")
    ap.add_argument("--probar", metavar="TEL10")
    ap.add_argument("--aplicar", action="store_true")
    ap.add_argument("--todos-crm", action="store_true")
    a = ap.parse_args()
    await inicializar_db()
    r = await sincronizar(aplicar=a.aplicar, todos_crm=a.todos_crm, csv_ruta=a.csv, solo=a.probar)
    print(f"Teléfonos únicos en CRM:        {r['crm']}")
    print(f"Teléfonos que el bot atendió:   {r['bot']}")
    print(f"Convertidos (CRM ∩ bot):        {r['convertidos']}")
    print(f"Ya tienen la etiqueta (Whapi):  {r['ya_etiquetados']}")
    print(f"Pendientes de etiquetar:        {r['pendientes']}")
    print(f"Etiquetados ahora:              {r['etiquetados']}")
    if not (a.aplicar or a.probar):
        print("Simulación: no se cambió nada. Ejemplo:", ", ".join(p[:3] + "…" + p[-3:] for p in r["pendientes_lista"][:10]))


if __name__ == "__main__":
    asyncio.run(main())
