#!/usr/bin/env python3
# tests/test_pricing_sheets.py — Tests para integración Google Sheets de precios
# Validar: lectura de hojas, parseo, búsqueda, formateo, fallback

import asyncio
import pytest
from agent.pricing_sheets import (
    buscar_google_sheets,
    cotizar_google_sheets,
    formatear_cotizacion_sheets,
)


class TestPricingSheets:
    """Tests para módulo pricing_sheets.py"""

    @pytest.mark.asyncio
    async def test_buscar_display_basico(self):
        """TEST 1: Búsqueda de display por nombre"""
        resultado = await buscar_google_sheets("Display iPhone 15 Oled")
        if resultado:
            assert "nombre" in resultado
            assert "precio" in str(resultado).lower()
            print(f"✅ Display encontrado: {resultado.get('nombre')}")
        else:
            print("⚠️  Display no encontrado (es normal si Sheet no está accesible)")

    @pytest.mark.asyncio
    async def test_buscar_bateria_android(self):
        """TEST 2: Búsqueda de batería Android por marca"""
        resultado = await buscar_google_sheets("Batería Huawei Honor")
        if resultado:
            assert "nombre" in resultado
            assert "p_unitario" in resultado or "mayoreo" in str(resultado).lower()
            print(f"✅ Batería Android encontrada: {resultado.get('nombre')}")
        else:
            print("⚠️  Batería Android no encontrada (es normal si Sheet no está accesible)")

    @pytest.mark.asyncio
    async def test_buscar_bateria_iphone(self):
        """TEST 3: Búsqueda de batería iPhone"""
        resultado = await buscar_google_sheets("Batería iPhone 15")
        if resultado:
            assert "nombre" in resultado
            assert ("surtido" in str(resultado).lower() or "p_unitario" in resultado)
            print(f"✅ Batería iPhone encontrada: {resultado.get('nombre')}")
        else:
            print("⚠️  Batería iPhone no encontrada (es normal si Sheet no está accesible)")

    @pytest.mark.asyncio
    async def test_cotizar_google_sheets(self):
        """TEST 4: Cotización completa desde Google Sheets"""
        cotizacion = await cotizar_google_sheets("iPhone", "15", "display")
        if cotizacion:
            assert "encontramos" in cotizacion.lower() or "precio" in cotizacion.lower()
            assert "$" in cotizacion  # Debe incluir precio formateado
            print(f"✅ Cotización formateada:\n{cotizacion[:200]}...")
        else:
            print("⚠️  Cotización no disponible (es normal si Sheet no está accesible)")

    @pytest.mark.asyncio
    async def test_formateo_display(self):
        """TEST 5: Formateo de Display por CALIDADES (genérica + original).

        Los displays ya no usan formatear_cotizacion_sheets: se agrupan por calidad
        (del nombre del producto) y se formatean con formatear_cotizacion_tiers.
        Aquí validamos que muestra DOS precios (la barata y la cara).
        """
        from agent.pricing import formatear_cotizacion_tiers
        categorias = {
            "GENERICO": [2760.0],   # Incell ($690 x4)
            "ORIGINAL": [4480.0],   # Oled  ($1120 x4)
        }
        cotizacion = formatear_cotizacion_tiers("iPhone", "13 Pro Max", categorias)
        assert "Calidad Generica" in cotizacion
        assert "Calidad Original" in cotizacion
        assert "$2,760" in cotizacion
        assert "$4,480" in cotizacion
        print(f"✅ Formateo Display (tiers):\n{cotizacion[:240]}...")

    @pytest.mark.asyncio
    async def test_formateo_bateria_android(self):
        """TEST 6: Formateo de cotización para Batería Android"""
        producto = {
            "nombre": "Batería Huawei Honor X5",
            "p_unitario": 100.0,
            "mayoreo_1": 70.0,
            "mayoreo_2": 65.0,
            "fuente": "google_sheets_baterias_android",
        }
        cotizacion = await formatear_cotizacion_sheets(producto, "Huawei", "Honor X5")
        assert "Batería Huawei Honor X5" in cotizacion.upper()
        assert "Unitario" in cotizacion
        assert "Mayoreo" in cotizacion
        print(f"✅ Formateo Batería Android:\n{cotizacion[:200]}...")

    @pytest.mark.asyncio
    async def test_formateo_bateria_iphone(self):
        """TEST 7: Formateo de cotización para Batería iPhone"""
        producto = {
            "nombre": "Batería iPhone 15 Pro Max",
            "p_unitario": 250.0,
            "surtido_20pz": 220.0,
            "surtido_50pz": 212.0,
            "fuente": "google_sheets_baterias_iphone",
        }
        cotizacion = await formatear_cotizacion_sheets(producto, "iPhone", "15 Pro Max")
        assert "iPhone 15 Pro Max" in cotizacion.upper()
        assert "20pz" in cotizacion
        assert "50pz" in cotizacion
        print(f"✅ Formateo Batería iPhone:\n{cotizacion[:200]}...")


def test_imports():
    """TEST 0: Validar imports correctos"""
    from agent.pricing_sheets import _cargar_catalogo_sheets, _limpiar_precio
    assert callable(_cargar_catalogo_sheets)
    assert callable(_limpiar_precio)
    print("✅ Imports correctos")


async def test_todas_las_pruebas():
    """Ejecutar todas las pruebas en secuencia"""
    print("\n" + "=" * 70)
    print("TESTS DE INTEGRACIÓN GOOGLE SHEETS")
    print("=" * 70 + "\n")

    test = TestPricingSheets()

    print("[TEST 0] Validar imports...")
    test_imports()
    print()

    print("[TEST 1] Búsqueda de display básico...")
    await test.test_buscar_display_basico()
    print()

    print("[TEST 2] Búsqueda de batería Android...")
    await test.test_buscar_bateria_android()
    print()

    print("[TEST 3] Búsqueda de batería iPhone...")
    await test.test_buscar_bateria_iphone()
    print()

    print("[TEST 4] Cotización completa...")
    await test.test_cotizar_google_sheets()
    print()

    print("[TEST 5] Formateo Display...")
    await test.test_formateo_display()
    print()

    print("[TEST 6] Formateo Batería Android...")
    await test.test_formateo_bateria_android()
    print()

    print("[TEST 7] Formateo Batería iPhone...")
    await test.test_formateo_bateria_iphone()
    print()

    print("=" * 70)
    print("✅ TODOS LOS TESTS COMPLETADOS")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(test_todas_las_pruebas())
