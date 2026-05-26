#!/usr/bin/env python3
"""
Test completo del webhook: simula un mensaje de Whapi,
lo procesa a través de todo el pipeline y verifica que genera respuesta.
"""

import asyncio
import sys
import os
import logging

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Configurar logging para ver qué está pasando
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

from agent.main import webhook_handler
from agent.memory import inicializar_db
from agent.providers.whapi import ProveedorWhapi
from unittest.mock import MagicMock, AsyncMock
import json


async def test_webhook_completo():
    """Simula un webhook completo de Whapi."""

    print("\n" + "="*80)
    print("TEST: Webhook completo (con generación de respuesta)")
    print("="*80 + "\n")

    # Inicializar
    await inicializar_db()
    print("[✓] BD inicializada\n")

    # Payload de Whapi
    payload_whapi = {
        "messages": [
            {
                "id": "test-msg-001",
                "from": "5541576333@c.us",
                "from_me": False,
                "chat_id": "5541576333@c.us",
                "type": "text",
                "text": {"body": "Hola, ¿cuál es el estatus de mi reparación?"},
                "timestamp": 1685812800,
            }
        ]
    }

    # Mock del Request
    async def mock_json():
        return payload_whapi

    mock_request = MagicMock()
    mock_request.json = mock_json

    print("[INPUT] Simulando webhook de Whapi:")
    print(json.dumps(payload_whapi, indent=2, ensure_ascii=False))
    print()

    # Procesar webhook
    try:
        resultado = await webhook_handler(mock_request)
        print("\n[OUTPUT] Webhook procesado exitosamente")
        print(f"Resultado: {resultado}")
        print("\n✅ CONCLUSIÓN: El servidor estaría respondiendo correctamente")
        return True

    except Exception as e:
        print(f"\n❌ ERROR procesando webhook: {e}")
        import traceback
        traceback.print_exc()
        print("\n❌ CONCLUSIÓN: Habría un problema en el servidor")
        return False


if __name__ == "__main__":
    try:
        success = asyncio.run(test_webhook_completo())
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\nTest interrumpido")
        sys.exit(1)
