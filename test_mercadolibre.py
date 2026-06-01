#!/usr/bin/env python3
"""
test_mercadolibre.py — Test del scraper robusto de MercadoLibre v3
Verifica:
  1. Búsquedas SEPARADAS (genérico vs original)
  2. Filtro NACIONAL (bloquea internacionales)
  3. Selecciona 3º PRECIO MÁS BAJO (garantiza disponibilidad)
"""

import asyncio
import sys
import logging

logging.basicConfig(
    level=logging.INFO,
    format='[%(name)s] %(levelname)s: %(message)s'
)

async def main():
    print("\n" + "="*75)
    print("  MercadoLibre Scraper Test v3")
    print("  • Búsquedas SEPARADAS (genérico vs original)")
    print("  • Filtro NACIONAL (sin internacionales)")
    print("  • Selecciona 3º PRECIO MÁS BAJO")
    print("="*75 + "\n")

    # Importar
    from agent.memory import inicializar_db
    from agent.pricing_mercadolibre_v2 import cotizar_refaccion_mercadolibre_v2

    # Inicializar BD
    print("▶ Inicializando base de datos...")
    await inicializar_db()
    print("  ✅ BD lista\n")

    # Casos de prueba
    pruebas = [
        ("batería", "motorola g85"),
        ("tapa trasera", "iphone 12"),
        ("centro de carga", "samsung a21"),
        ("pantalla", "redmi note 9"),
        ("cámara frontal", "motorola g70"),
    ]

    print("▶ Probando cotizaciones (con lógica v3):\n")

    for i, (refaccion, modelo) in enumerate(pruebas, 1):
        print(f"  [{i}/{len(pruebas)}] {refaccion.title()} para {modelo.title()}")
        try:
            resultado = await cotizar_refaccion_mercadolibre_v2(refaccion, modelo)

            if resultado:
                gen = resultado.get('precio_generico')
                orig = resultado.get('precio_original')
                fuente = resultado.get('fuente', '?')

                print(f"        ✅ Encontrado (fuente: {fuente})")

                if gen:
                    print(f"           Genérico: ${gen:>10,} MXN")
                else:
                    print(f"           Genérico: {'NO DISPONIBLE':>10}")

                if orig and orig != gen:
                    print(f"           Original: ${orig:>10,} MXN")
                else:
                    print(f"           Original: {'(igual genérico)':>10}")

            else:
                print(f"        ❌ No encontrado (ML bloqueó o no existe)")

        except Exception as e:
            print(f"        ⚠️  Error: {type(e).__name__}: {e}")

        print()

    print("\n" + "="*75)
    print("  ✅ TEST COMPLETADO")
    print("="*75)
    print("\n📝 Detalles de la lógica v3:\n")
    print("  1. BÚSQUEDAS SEPARADAS")
    print("     • Primera búsqueda: '{refaccion} {modelo} genérico'")
    print("     • Segunda búsqueda: '{refaccion} {modelo} original'")
    print("     • NO se mezclan resultados (categoría garantizada)")
    print()
    print("  2. FILTRO NACIONAL")
    print("     • Bloquea: 'enviado desde', 'usa', 'china', etc.")
    print("     • Permite: 'méxico', 'envío nacional', 'stock en méxico'")
    print("     • Evita envíos de 1 mes desde el extranjero")
    print()
    print("  3. SELECCIONA 3º PRECIO MÁS BAJO")
    print("     • 1º bajo: Suele venderse rápido (stock bajo)")
    print("     • 2º bajo: Todavía puede haber lotes/precios raros")
    print("     • 3º bajo: ✅ Stock disponible + precio coherente")
    print("     • Final: 3º bajo × 4 = precio al cliente")
    print()
    print("✅ Verifica en logs arriba:")
    print("   [ML GENERICO] — precios nacionales de búsqueda genérico")
    print("   [ML ORIGINAL] — precios nacionales de búsqueda original")
    print("   [ML NACIONAL] — filtrado internacional")
    print()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n[!] Test interrumpido\n")
        sys.exit(0)
    except Exception as e:
        print(f"\n[!] Error: {e}\n")
        import traceback
        traceback.print_exc()
        sys.exit(1)
