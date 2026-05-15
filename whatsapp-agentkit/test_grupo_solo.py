#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test SOLO del envío al grupo — sin necesidad de recargar módulos
"""

import asyncio
import os
from dotenv import load_dotenv
import httpx
import logging

# Setup logging
logging.basicConfig(level=logging.DEBUG, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

load_dotenv()

async def test_envio_grupo():
    """Test DIRECTO del envío al grupo sin importar el módulo cacheado."""

    print("\n" + "="*80)
    print("🧪 TEST DIRECTO: Envío al grupo")
    print("="*80 + "\n")

    # Configuración
    GRUPO_ID = os.getenv("GRUPO_CHRISTIAN_INTERNO", "").strip()
    WHAPI_TOKEN = os.getenv("WHAPI_TOKEN", "").strip()

    print(f"Grupo ID: {GRUPO_ID if GRUPO_ID else '❌ NO CONFIGURADO'}")
    print(f"Whapi Token: {WHAPI_TOKEN[:15]}..." if WHAPI_TOKEN else "❌ NO CONFIGURADO")

    if not GRUPO_ID or not WHAPI_TOKEN:
        print("\n❌ Configuración incompleta")
        return

    # Mensaje de prueba
    msg_test = (
        "🧪 *TEST DE ENVÍO*\n"
        "Este es un mensaje de prueba directo para verificar que el grupo recibe notificaciones.\n"
        "Si ves esto, ¡el sistema funciona! ✅"
    )

    print(f"\n📝 Mensaje a enviar:")
    print(f"  {msg_test}\n")

    # Validar UTF-8
    try:
        msg_limpio = msg_test.encode('utf-8', errors='replace').decode('utf-8')
        print(f"✅ UTF-8 validado\n")
    except Exception as e:
        print(f"❌ Error UTF-8: {e}\n")
        msg_limpio = msg_test

    # Intentar envío 3 veces
    for intento in range(1, 4):
        print(f"🔄 Intento {intento}/3...")

        try:
            async with httpx.AsyncClient(timeout=15) as http:
                r = await http.post(
                    "https://gate.whapi.cloud/messages/text",
                    headers={
                        "Authorization": f"Bearer {WHAPI_TOKEN}",
                        "Content-Type": "application/json; charset=utf-8"
                    },
                    json={"to": GRUPO_ID, "body": msg_limpio},
                    timeout=15,
                )

                if r.status_code == 200:
                    print(f"✅ ÉXITO en intento {intento}")
                    print(f"   Respuesta: {r.json()}")
                    return True
                else:
                    print(f"❌ HTTP {r.status_code}: {r.text[:100]}")

        except asyncio.TimeoutError:
            print(f"⏱️ Timeout")
        except Exception as e:
            print(f"❌ Error: {type(e).__name__}: {e}")

        if intento < 3:
            print(f"   Esperando 2 segundos...")
            await asyncio.sleep(2)

    print(f"\n❌ FALLÓ después de 3 intentos")
    return False

if __name__ == "__main__":
    resultado = asyncio.run(test_envio_grupo())
    if resultado:
        print("\n" + "="*80)
        print("✅ TEST EXITOSO — El grupo recibió el mensaje")
        print("="*80 + "\n")
    else:
        print("\n" + "="*80)
        print("❌ TEST FALLIDO — Revisa los errores arriba")
        print("="*80 + "\n")
