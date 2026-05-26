#!/usr/bin/env python3
"""
Test del parseo de Whapi para verificar que los mensajes se están normalizando correctamente.
"""

import asyncio
import sys
import os
import json
from unittest.mock import MagicMock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from agent.providers.whapi import ProveedorWhapi


async def test_whapi_parseo():
    """Simula el parseo de un webhook de Whapi."""

    print("\n" + "="*70)
    print("TEST: Parseo de Whapi")
    print("="*70 + "\n")

    proveedor = ProveedorWhapi()

    # Payload típico de Whapi para un mensaje de texto
    payload_whapi = {
        "messages": [
            {
                "id": "wamid.HVwYdKqIdAz5V4VsDiQXZ6F8d73QwQ==",
                "from": "5541576333@c.us",  # número del cliente
                "from_me": False,  # NO es del agente
                "chat_id": "5541576333@c.us",  # chat individual
                "type": "text",
                "text": {
                    "body": "Hola, ¿cuál es el estatus de mi reparación?"
                },
                "timestamp": 1685812800,
            }
        ]
    }

    # Mock del Request
    async def mock_json():
        return payload_whapi

    mock_request = MagicMock()
    mock_request.json = mock_json

    print("[INPUT] Payload de Whapi:")
    print(json.dumps(payload_whapi, indent=2, ensure_ascii=False))
    print()

    # Parsear
    try:
        mensajes = await proveedor.parsear_webhook(mock_request)
        print(f"[OUTPUT] Mensajes parseados: {len(mensajes)}\n")

        for i, msg in enumerate(mensajes, 1):
            print(f"Mensaje {i}:")
            print(f"  telefono: {msg.telefono}")
            print(f"  texto: '{msg.texto}'")
            print(f"  es_propio: {msg.es_propio}")
            print(f"  mensaje_id: {msg.mensaje_id}")
            print(f"  tipo: {msg.tipo}")
            print()

            # Validaciones
            print("Validaciones:")
            print(f"  ✓ Tiene telefono: {bool(msg.telefono)}")
            print(f"  ✓ Tiene texto: {bool(msg.texto)}")
            print(f"  ✓ NO es propio: {not msg.es_propio}")
            print(f"  ✓ Texto no vacío: {len(msg.texto.strip()) > 0}")

            if msg.telefono and msg.texto and not msg.es_propio:
                print("\n✅ RESULTADO: El mensaje pasaría las validaciones iniciales")
            else:
                print("\n❌ RESULTADO: El mensaje sería descartado")

    except Exception as e:
        print(f"❌ ERROR al parsear: {e}")
        import traceback
        traceback.print_exc()
        return False

    print("\n" + "="*70)
    return True


if __name__ == "__main__":
    success = asyncio.run(test_whapi_parseo())
    sys.exit(0 if success else 1)
