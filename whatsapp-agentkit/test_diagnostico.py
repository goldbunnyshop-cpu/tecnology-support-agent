#!/usr/bin/env python3
"""
Script de diagnóstico para verificar si los checkpoints están funcionando.
Simula el flujo de main.py sin necesidad de WhatsApp.
"""

import asyncio
import sys
import os
from datetime import datetime

# Agregar ruta
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from agent.memory import inicializar_db, esta_pausada, obtener_historial
from agent.commands import esta_bloqueado

NUMERO_TEST = "5541576333"


async def test_checkpoints():
    """Simula los checkpoints del webhook."""

    print("\n" + "="*60)
    print("DIAGNÓSTICO: Verificando checkpoints de main.py")
    print("="*60 + "\n")

    # Inicializar DB
    await inicializar_db()
    print("[✓] BD inicializada")

    # TEST 1: Bloqueo
    print(f"\n[TEST 1] Checkpoint BLOQUEO")
    print(f"  → Número: {NUMERO_TEST}")
    resultado = esta_bloqueado(NUMERO_TEST)
    print(f"  → ¿Está bloqueado? {resultado}")
    if resultado:
        print("  ❌ ERROR: El número está bloqueado (debería NO estarlo)")
        return False
    print("  ✓ OK: Número no bloqueado")

    # TEST 2: Pausa
    print(f"\n[TEST 2] Checkpoint PAUSA")
    print(f"  → Número: {NUMERO_TEST}")
    try:
        resultado = await esta_pausada(NUMERO_TEST)
        print(f"  → ¿Está pausado? {resultado}")
        if resultado:
            print("  ❌ ERROR: El número está pausado (debería NO estarlo)")
            return False
        print("  ✓ OK: Número no pausado")
    except Exception as e:
        print(f"  ❌ ERROR CRÍTICO en esta_pausada(): {e}")
        import traceback
        traceback.print_exc()
        return False

    # TEST 3: Historial
    print(f"\n[TEST 3] Obtener historial")
    print(f"  → Número: {NUMERO_TEST}")
    try:
        historial = await obtener_historial(NUMERO_TEST)
        print(f"  → Mensajes en historial: {len(historial)}")
        print(f"  → Historial: {historial[:2] if historial else 'VACÍO'}")
        print("  ✓ OK: Historial recuperado sin errores")
    except Exception as e:
        print(f"  ❌ ERROR en obtener_historial(): {e}")
        import traceback
        traceback.print_exc()
        return False

    print("\n" + "="*60)
    print("DIAGNÓSTICO: Todos los checkpoints pasaron")
    print("="*60 + "\n")
    return True


if __name__ == "__main__":
    success = asyncio.run(test_checkpoints())
    sys.exit(0 if success else 1)
