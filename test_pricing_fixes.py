#!/usr/bin/env python3
"""
Test de las correcciones en pricing.py para los 3 errores reportados:
1. iPhone 11 normal (base sin variante)
2. Cotización sin marca específica
3. Consolas vs displays (no debe confundir)
"""

import asyncio
import sys
sys.path.insert(0, '.')

from agent.pricing import (
    normalizar_modelo_query,
    obtener_cotizacion_display,
    buscar_modelo_sin_marca,
)

async def test_iphone_11_normal():
    """Test 1: Cliente dice 'iPhone 11 normal' debería reconocer que es el modelo base sin variante."""
    print("\n" + "="*70)
    print("TEST 1: iPhone 11 NORMAL (modelo base sin variante)")
    print("="*70)

    base_q, var_q = normalizar_modelo_query("11 normal", "iphone")
    print(f"Input: modelo='11 normal', marca='iphone'")
    print(f"Parsed: base={base_q}, variante={var_q}")
    print(f"✓ CORRECTO: variante debe ser None (no 'normal')")
    assert var_q is None, f"Error: variante debería ser None, pero es {var_q}"

    # Ahora cotizar
    cotizacion = await obtener_cotizacion_display("iphone", "11 normal")
    print(f"\nCotización generada:")
    print(cotizacion[:200] + "..." if len(cotizacion) > 200 else cotizacion)

    # Verificar que NO dice "no tengo en inventario"
    assert "no tengo en inventario" not in cotizacion.lower(), "Error: no debería decir que no hay en inventario"
    print("✓ CORRECTO: Se cotizó el modelo base correctamente")


async def test_cotizacion_sin_marca():
    """Test 2: Cliente pregunta por display sin especificar marca — debería pedir clarificación."""
    print("\n" + "="*70)
    print("TEST 2: Cotización SIN MARCA específica")
    print("="*70)

    resultado = await buscar_modelo_sin_marca("cambio de pantalla")
    print(f"Input: 'cambio de pantalla' (sin marca, sin modelo claro)")
    print(f"Resultado:")
    print(resultado)

    # Verificar que PREGUNTA clarificaciones en lugar de decir "no tengo"
    assert "marca" in resultado.lower() or "cual" in resultado.lower(), \
        "Error: debería preguntar qué marca/modelo, no rechazar"
    print("✓ CORRECTO: Pide clarificación en lugar de rechazar")


async def test_consolas_vs_displays():
    """Test 3: Cotización de consola vs display — no debe confundir."""
    print("\n" + "="*70)
    print("TEST 3: Nintendo 2DS (consola) vs display de consola")
    print("="*70)

    # Intentar cotizar "display de Nintendo 2DS" — no debería confundir con celular
    resultado = await obtener_cotizacion_display("Nintendo", "2DS display")
    print(f"Input: marca='Nintendo', modelo='2DS display'")
    print(f"Resultado:")
    print(resultado)

    # Nintendo no está en ALIAS_MARCAS de phones, así que debería manejar gracefully
    assert "no tengo en inventario" in resultado.lower() or \
           "marca" in resultado.lower() or \
           "modelo" in resultado.lower(), \
        "Error: debería reconocer que Nintendo no es marca de displays"
    print("✓ CORRECTO: No confunde consola con celular")


async def main():
    print("\n🔧 VALIDANDO CORRECCIONES DE PRICING\n")
    print("Estos tests verifican que los 3 errores reportados estén SOLUCIONADOS:\n")
    print("1. iPhone 11 normal (cliente dice 'normal' 3 veces → debe cotizar el base)")
    print("2. Cotización sin marca (cliente no especifica → pide clarificación)")
    print("3. Consola vs display (Nintendo no confunde con celular)\n")

    try:
        await test_iphone_11_normal()
        await test_cotizacion_sin_marca()
        await test_consolas_vs_displays()

        print("\n" + "="*70)
        print("✅ TODOS LOS TESTS PASARON")
        print("="*70)
        print("\nLas correcciones están funcionando correctamente.")
        print("El agente debería ahora:")
        print("  • Reconocer 'normal' como 'modelo base sin variante'")
        print("  • Pedir clarificación en lugar de rechazar cotizaciones vagas")
        print("  • No confundir marcas de consolas con marcas de celulares")

    except AssertionError as e:
        print(f"\n❌ TEST FALLIDO: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
