#!/usr/bin/env python3
"""
Test que simula exactamente el flujo del webhook en main.py
para diagnosticar dónde se pierden los mensajes.
"""

import asyncio
import sys
import os
from dataclasses import dataclass

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from agent.memory import inicializar_db, esta_pausada, obtener_historial
from agent.commands import esta_bloqueado, procesar_comando_grupo
from agent.tools import (
    fue_ultimo_mensaje_menu_ambiguo,
    detectar_tipo_dispositivo_en_mensaje,
)

# Mensaje fake similar a lo que vendría de Whapi
@dataclass
class MensajeTest:
    telefono: str = "5541576333"
    texto: str = "Hola, ¿cuál es el estatus de mi reparación?"
    mensaje_id: str = "test-001"
    es_propio: bool = False
    nombre_grupo: str = ""
    chat_id_raw: str = "5541576333@s.whatsapp.net"
    tipo: str = "text"
    es_grupo: bool = False


async def test_flujo_webhook():
    """Simula el flujo completo del webhook."""

    print("\n" + "="*70)
    print("TEST: Flujo completo del webhook (simulación)")
    print("="*70 + "\n")

    msg = MensajeTest()
    print(f"[ENTRADA] Mensaje: {msg.texto}")
    print(f"[ENTRADA] Número: {msg.telefono}")
    print(f"[ENTRADA] es_propio: {msg.es_propio}\n")

    # Inicializar DB
    await inicializar_db()
    print("[✓] BD inicializada\n")

    # PASO 1: Verificar si es mensaje propio
    print("[PASO 1] ¿Es mensaje propio?")
    if msg.es_propio:
        print("  ❌ Mensaje propio → DESCARTADO")
        return False
    print("  ✓ No es propio\n")

    # PASO 2: Verificar si texto vacío
    print("[PASO 2] ¿Texto vacío?")
    if not msg.texto or len(msg.texto.strip()) == 0:
        print("  ❌ Texto vacío → DESCARTADO")
        return False
    print(f"  ✓ Texto OK: '{msg.texto[:60]}...'\n")

    # PASO 3: Verificar bloqueo
    print("[PASO 3] ¿Está bloqueado?")
    try:
        bloqueado = esta_bloqueado(msg.telefono)
        print(f"  → Resultado: {bloqueado}")
        if bloqueado:
            print("  ❌ Bloqueado → DESCARTADO")
            return False
        print("  ✓ No está bloqueado\n")
    except Exception as e:
        print(f"  ❌ ERROR: {e}")
        return False

    # PASO 4: Verificar pausa
    print("[PASO 4] ¿Está pausado?")
    try:
        pausado = await esta_pausada(msg.telefono)
        print(f"  → Resultado: {pausado}")
        if pausado:
            print("  ❌ Pausado → DESCARTADO")
            return False
        print("  ✓ No está pausado\n")
    except Exception as e:
        print(f"  ❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False

    # PASO 5: Procesar comandos del grupo (no aplicable a este mensaje)
    print("[PASO 5] ¿Es comando del grupo interno?")
    if not hasattr(msg, "nombre_grupo"):
        print("  → msg sin nombre_grupo, saltando procesamiento de comandos")
        es_cmd = False
    else:
        print(f"  → nombre_grupo: '{msg.nombre_grupo}'")
        es_cmd = False  # Simulamos False porque no es grupo
    if es_cmd:
        print("  ❌ Es comando → DESCARTADO")
        return False
    print("  ✓ No es comando\n")

    # PASO 6: Obtener historial
    print("[PASO 6] Obtener historial")
    try:
        historial = await obtener_historial(msg.telefono)
        print(f"  → Mensajes en historial: {len(historial)}")
        print("  ✓ Historial OK\n")
    except Exception as e:
        print(f"  ❌ ERROR: {e}")
        return False

    # PASO 7: Detectar tipo de dispositivo
    print("[PASO 7] Detectar tipo de dispositivo")
    try:
        tipo_dispositivo = detectar_tipo_dispositivo_en_mensaje(msg.texto, historial)
        print(f"  → Tipo: {tipo_dispositivo}")
        print("  ✓ Tipo OK\n")
    except Exception as e:
        print(f"  ⚠️  ERROR (no crítico): {e}")
        tipo_dispositivo = "desconocido"

    # PASO 8: Verificar si fue último mensaje un menú ambiguo
    print("[PASO 8] ¿Fue último mensaje un menú ambiguo?")
    es_menu_ambiguo = fue_ultimo_mensaje_menu_ambiguo(historial)
    print(f"  → Es ambiguo: {es_menu_ambiguo}")
    print("  ✓ Check OK\n")

    print("="*70)
    print("✅ RESULTADO: El mensaje PASARÍA todos los checkpoints")
    print("   Ahora se generaría respuesta con Claude...")
    print("="*70 + "\n")
    return True


if __name__ == "__main__":
    success = asyncio.run(test_flujo_webhook())
    sys.exit(0 if success else 1)
