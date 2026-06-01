#!/usr/bin/env python3
"""Test directo de pricing.py — búsqueda dual sin dependencias de Claude API."""

import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from agent.pricing import (
    obtener_cotizacion_display,
    buscar_modelo_sin_marca,
    cargar_csv_hugo,
    normalizar_modelo_query,
)


async def main():
    print("=" * 70)
    print("TEST PRICING — Búsqueda Dual (Marca Explícita vs Modelo Solo)")
    print("=" * 70)
    print()

    # Cargar datos una sola vez
    print("[INIT] Cargando datos de Hugo Shop...")
    productos = cargar_csv_hugo()
    print(f"[INIT] ✓ {len(productos)} productos cargados\n")

    # ======== CASOS CON MARCA EXPLÍCITA ========
    print("─" * 70)
    print("OPCION 1: CON MARCA EXPLÍCITA (prueba que el sistema anterior sigue funcionando)")
    print("─" * 70)
    print()

    casos_marca = [
        ("Samsung", "S23"),
        ("Samsung", "A21"),
        ("Samsung", "A14"),
        ("iPhone", "14 Pro"),
        ("iPhone", "15"),
    ]

    for marca, modelo in casos_marca:
        print(f"Buscando: {marca} {modelo}")
        resultado = await obtener_cotizacion_display(marca, modelo)
        if "PRECIO ENCONTRADO" in resultado or "Para" in resultado:
            print(f"✓ ÉXITO")
            # Mostrar primeras 2 líneas de respuesta
            lineas = resultado.split('\n')[:3]
            for linea in lineas:
                if linea.strip():
                    print(f"  {linea}")
        else:
            print(f"⚠ SIN COINCIDENCIAS: {resultado[:80]}")
        print()

    # ======== CASOS SIN MARCA (NUEVOS) ========
    print("─" * 70)
    print("OPCION 2: SIN MARCA (búsqueda por modelo solo — NUEVO)")
    print("─" * 70)
    print()

    casos_sin_marca = [
        "S23",
        "s23",
        "A14",
        "a14",
        "14 pro",
        "edge 50",
        "pixel 8",
    ]

    for modelo in casos_sin_marca:
        print(f"Buscando (sin marca): {modelo}")
        resultado = await buscar_modelo_sin_marca(modelo)
        if "Para" in resultado or "Encontre" in resultado:
            print(f"✓ ÉXITO")
            lineas = resultado.split('\n')[:3]
            for linea in lineas:
                if linea.strip():
                    print(f"  {linea}")
        else:
            print(f"⚠ {resultado[:80]}")
        print()

    print("=" * 70)
    print("TEST COMPLETADO")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
