#!/usr/bin/env python3
# test_stop_on.py — Prueba del sistema STOP/ON

"""
Script para probar el sistema de números detenidos (stop/on).
Ejecutar desde la raíz del proyecto:
  python test_stop_on.py
"""

import asyncio
import os
import sys
from datetime import datetime

# Agregar raíz al path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
from agent.memory import inicializar_db, detener_numero, reactivar_numero, numero_esta_stopped, listar_numeros_stopped
from agent.commands_control import procesar_comando_control, validar_numero_activo

load_dotenv()


async def test_basico():
    """Prueba básica: stop/on"""
    print("\n" + "="*70)
    print("TEST 1: Operaciones Básicas (STOP/ON)")
    print("="*70 + "\n")

    numero_test = "5525531098"

    # Init BD
    print("[1/6] Inicializando base de datos...")
    await inicializar_db()
    print("      ✓ BD lista\n")

    # Verificar número activo (debería estar activo)
    print("[2/6] Verificando número ANTES de stop...")
    activo = await validar_numero_activo(numero_test)
    print(f"      Número {numero_test} activo: {activo} (esperado: True)")
    if activo:
        print("      ✓ CORRECTO\n")
    else:
        print("      ✗ ERROR\n")
        return False

    # Detener número
    print("[3/6] Ejecutando STOP...")
    exito, msg = await detener_numero(numero_test, razon="test_stop")
    print(f"      {msg}")
    if exito:
        print("      ✓ CORRECTO\n")
    else:
        print("      ⚠️  Número ya estaba stopped (eso está bien)\n")

    # Verificar número detenido
    print("[4/6] Verificando número DESPUÉS de stop...")
    activo = await validar_numero_activo(numero_test)
    print(f"      Número {numero_test} activo: {activo} (esperado: False)")
    if not activo:
        print("      ✓ CORRECTO (está stopped como se esperaba)\n")
    else:
        print("      ✗ ERROR (no está stopped)\n")
        return False

    # Reactivar número
    print("[5/6] Ejecutando ON...")
    exito, msg = await reactivar_numero(numero_test)
    print(f"      {msg}")
    if exito:
        print("      ✓ CORRECTO\n")
    else:
        print("      ✗ ERROR\n")
        return False

    # Verificar número reactivado
    print("[6/6] Verificando número DESPUÉS de on...")
    activo = await validar_numero_activo(numero_test)
    print(f"      Número {numero_test} activo: {activo} (esperado: True)")
    if activo:
        print("      ✓ CORRECTO (está activo de nuevo)\n")
    else:
        print("      ✗ ERROR (sigue stopped)\n")
        return False

    return True


async def test_comandos():
    """Prueba: procesamiento de comandos"""
    print("\n" + "="*70)
    print("TEST 2: Procesamiento de Comandos")
    print("="*70 + "\n")

    numero_test = "5541234567"
    emisor = "Ulises"

    await inicializar_db()

    # Comando STOP
    print("[1/5] Procesando comando: 'stop: 5541234567'...")
    es_cmd, resp = await procesar_comando_control("stop: 5541234567", emisor)
    print(f"      Es comando: {es_cmd} (esperado: True)")
    print(f"      Respuesta: {resp}\n")
    if es_cmd and resp:
        print("      ✓ CORRECTO\n")
    else:
        print("      ✗ ERROR\n")
        return False

    # Verificar stopped
    print("[2/5] Verificando que número está stopped...")
    activo = await validar_numero_activo(numero_test)
    if not activo:
        print("      ✓ CORRECTO (número stopped)\n")
    else:
        print("      ✗ ERROR\n")
        return False

    # Comando ON
    print("[3/5] Procesando comando: 'on: 5541234567'...")
    es_cmd, resp = await procesar_comando_control("on: 5541234567", emisor)
    print(f"      Es comando: {es_cmd} (esperado: True)")
    print(f"      Respuesta: {resp}\n")
    if es_cmd and resp:
        print("      ✓ CORRECTO\n")
    else:
        print("      ✗ ERROR\n")
        return False

    # Verificar activo
    print("[4/5] Verificando que número está activo...")
    activo = await validar_numero_activo(numero_test)
    if activo:
        print("      ✓ CORRECTO (número activo)\n")
    else:
        print("      ✗ ERROR\n")
        return False

    # Comando stopped-list
    print("[5/5] Procesando comando: 'stopped-list'...")
    es_cmd, resp = await procesar_comando_control("stopped-list", emisor)
    print(f"      Es comando: {es_cmd} (esperado: True)")
    print(f"      Respuesta (primeras 200 chars): {(resp or '')[:200]}\n")
    if es_cmd:
        print("      ✓ CORRECTO\n")
    else:
        print("      ✗ ERROR\n")
        return False

    return True


async def test_variantes():
    """Prueba: aceptación de variantes de número"""
    print("\n" + "="*70)
    print("TEST 3: Tolerancia de Variantes de Número")
    print("="*70 + "\n")

    await inicializar_db()

    # Stop con 10 dígitos
    numero_10d = "5525531098"
    print(f"[1/3] Deteniendo con formato 10 dígitos: {numero_10d}...")
    exito, msg = await detener_numero(numero_10d)
    print(f"      {msg}")
    if exito:
        print("      ✓ CORRECTO\n")
    else:
        print("      ⚠️  Ya estaba stopped\n")

    # Verificar con 13 dígitos
    numero_13d = "5215525531098"
    print(f"[2/3] Verificando con formato 13 dígitos: {numero_13d}...")
    activo = await validar_numero_activo(numero_13d)
    print(f"      Activo: {activo} (esperado: False - debe estar stopped)")
    if not activo:
        print("      ✓ CORRECTO (variante reconocida como stopped)\n")
    else:
        print("      ✗ ERROR (variante no fue detenida)\n")
        return False

    # Reactivar con formato diferente
    numero_12d = "525525531098"
    print(f"[3/3] Reactivando con formato 12 dígitos: {numero_12d}...")
    exito, msg = await reactivar_numero(numero_12d)
    print(f"      {msg}")
    if exito:
        print("      ✓ CORRECTO\n")
    else:
        print("      ✗ ERROR\n")
        return False

    return True


async def main():
    print("\n" + "🛑 PRUEBAS: SISTEMA STOP/ON".center(70))
    print("=" * 70)
    print(f"Inicio: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")

    all_pass = True

    try:
        # Test 1: Operaciones básicas
        if not await test_basico():
            all_pass = False

        # Test 2: Procesamiento de comandos
        if not await test_comandos():
            all_pass = False

        # Test 3: Tolerancia de variantes
        if not await test_variantes():
            all_pass = False

    except Exception as e:
        print(f"\n❌ ERROR DURANTE LAS PRUEBAS:\n{e}")
        import traceback
        traceback.print_exc()
        all_pass = False

    # Resumen
    print("\n" + "="*70)
    if all_pass:
        print("✅ TODAS LAS PRUEBAS PASARON")
    else:
        print("❌ ALGUNAS PRUEBAS FALLARON")
    print("="*70 + "\n")

    return 0 if all_pass else 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
