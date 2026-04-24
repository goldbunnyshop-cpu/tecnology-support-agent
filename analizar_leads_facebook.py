# analizar_leads_facebook.py — Detecta leads de Facebook Ads en conversaciones existentes
# Uso: python analizar_leads_facebook.py

import asyncio
import sys
import os

sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from anthropic import AsyncAnthropic
from dotenv import load_dotenv

load_dotenv()
client = AsyncAnthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))


async def detectar_fuente_facebook(historial: list[dict], nombre_contacto: str) -> tuple[bool, str]:
    """
    Usa Claude para analizar si la conversación se originó desde un anuncio de Facebook/Instagram.
    Retorna (es_facebook_ad, razon).
    """
    if not historial:
        return False, ""

    primer_mensaje = next((m["content"] for m in historial if m["role"] == "user"), "")
    fragmento = "\n".join(
        f"{'Cliente' if m['role'] == 'user' else 'Negocio'}: {m['content']}"
        for m in historial[:8]
    )

    prompt = f"""Analiza si esta conversación de WhatsApp se originó desde un anuncio de Facebook o Instagram.

Nombre del contacto guardado: "{nombre_contacto}"
Primer mensaje del cliente: "{primer_mensaje}"

Conversación completa (inicio):
{fragmento}

Señales de que viene de un anuncio:
- El contacto NO está guardado con nombre personal (solo número o guardado como "iPhone X roto", "Laptop cliente", etc.)
- El primer mensaje es directo pidiendo precio o reparación sin contexto previo
- Menciona haber visto una publicidad, anuncio, Facebook, Instagram, o "vi tu post"
- El nombre guardado tiene el dispositivo incluido (ej: "Cristian Display iPhone", "S20+ Falta Pagar")
- El cliente no tiene ninguna relación previa aparente (conversación muy transaccional desde el inicio)
- El cliente llegó sin que hubiera conversación previa de ningún tipo

Responde SOLO en este formato:
ES_AD: si/no
RAZON: [una línea explicando por qué]"""

    try:
        response = await client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=80,
            messages=[{"role": "user", "content": prompt}]
        )
        texto = response.content[0].text.strip()
        es_ad = False
        razon = ""
        for linea in texto.splitlines():
            if linea.startswith("ES_AD:"):
                es_ad = "si" in linea.lower()
            elif linea.startswith("RAZON:"):
                razon = linea.replace("RAZON:", "").strip()
        return es_ad, razon
    except Exception:
        return False, ""


async def main():
    print()
    print("=" * 62)
    print("   Tecnology Support — Detector de Leads de Facebook Ads")
    print("=" * 62)
    print()

    from agent.leads import Lead, async_session, _migrar_columnas, obtener_todos_los_leads
    from agent.memory import inicializar_db, obtener_historial
    from agent.import_chats import obtener_todos_los_chats
    from agent.reports import generar_reporte_excel
    from sqlalchemy import select, update

    await inicializar_db()
    await _migrar_columnas()

    # Obtener nombres de contacto desde Whapi para tenerlos disponibles
    print("  Obteniendo nombres de contactos desde Whapi...")
    chats = await obtener_todos_los_chats()
    nombres_por_tel = {}
    for chat in chats:
        tel = chat["id"].replace("@s.whatsapp.net", "").replace("@c.us", "")
        nombres_por_tel[tel] = chat.get("name") or chat.get("notify") or tel

    leads = await obtener_todos_los_leads()
    # Solo analizar leads sin fuente definida
    pendientes = [l for l in leads if getattr(l, "fuente", "desconocido") in ("desconocido", None, "")]
    total = len(pendientes)

    print(f"  Analizando {total} leads sin fuente clasificada...")
    print()

    facebook_ads = []
    organicos = []

    for i, lead in enumerate(pendientes, 1):
        nombre = nombres_por_tel.get(lead.telefono, lead.telefono)
        print(f"  [{i}/{total}] {nombre}...", end=" ", flush=True)

        historial = await obtener_historial(lead.telefono, limite=8)
        es_ad, razon = await detectar_fuente_facebook(historial, nombre)

        fuente = "facebook_ad" if es_ad else "organico"

        async with async_session() as session:
            await session.execute(
                update(Lead)
                .where(Lead.telefono == lead.telefono)
                .values(fuente=fuente, fuente_detalle=razon)
            )
            await session.commit()

        if es_ad:
            facebook_ads.append({"telefono": lead.telefono, "nombre": nombre, "razon": razon, "estado": lead.estado})
            print(f"Facebook Ad")
        else:
            organicos.append(lead.telefono)
            print(f"Organico")

    print()
    print(f"  Clasificados: {len(facebook_ads)} Facebook Ads / {len(organicos)} organicos")
    print()

    if facebook_ads:
        print("  LEADS DE FACEBOOK ADS DETECTADOS:")
        print()
        for lead in facebook_ads:
            estado_label = {"activo": "Activo", "en_seguimiento": "En seguimiento",
                           "perdido": "Perdido", "convertido": "Convertido"}.get(lead["estado"], lead["estado"])
            print(f"    • {lead['nombre']} ({lead['telefono']})")
            print(f"      Estado: {estado_label}")
            print(f"      Razon: {lead['razon']}")
            print()

    print("  Regenerando reporte Excel con fuentes clasificadas...")
    ruta = await generar_reporte_excel()
    print(f"  Reporte guardado en: {ruta}")
    print()
    print("=" * 62)
    print()


if __name__ == "__main__":
    asyncio.run(main())
