# test_pricing_nuevo.py - Tests del flujo de cotizacion con variantes.
# Corre desde la raiz: python test_pricing_nuevo.py
import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from agent.pricing import (
    cargar_csv_hugo,
    obtener_categoria,
    normalizar_modelo_descripcion,
    normalizar_modelo_query,
    obtener_cotizacion_display,
)


def chk(cond, msg):
    print(f"  {'ok  ' if cond else 'FAIL'}: {msg}")
    return cond


def t_parser():
    print("\n[1] Parser CSV - asigna MARCA por seccion")
    datos = cargar_csv_hugo()
    r = True
    r &= chk(len(datos) > 0, f"carga productos (n={len(datos)})")
    marcas = {p['MARCA'] for p in datos}
    r &= chk('SAMSUNG' in marcas, "detecta SAMSUNG")
    r &= chk('IPHONE' in marcas, "detecta IPHONE")
    r &= chk(all(p['MARCA'] for p in datos), "todos los productos con MARCA")
    r &= chk(not any(p['DESCRIPCION'].lower().startswith('bater') for p in datos), "sin baterias")
    return r


def t_categorias():
    print("\n[2] Categorias")
    casos = [
        ('INCELL+ S/M(MOVIL IC)', 'GENERICO'),
        ('COG', 'GENERICO'),
        ('CARTAN INCELL+', 'GENERICO'),
        ('ORIG C/M', 'ORIGINAL'),
        ('HG SOFT OLED C/M(BOUTIQUE)', 'ORIGINAL'),
        ('HG FHD+ COF 120HZ', 'ORIGINAL'),
        ('AMOLED C/M', 'AMOLED'),
        ('CARTAN (AMERICANO)-ORIG', 'ORIGINAL'),
    ]
    r = True
    for cal, esp in casos:
        got = obtener_categoria(cal)
        r &= chk(got == esp, f"'{cal}' -> {got} (esperado {esp})")
    return r


def t_norm_desc():
    print("\n[3] normalizar_modelo_descripcion")
    casos = [
        ('X14 PRO', 'IPHONE', ('14', 'pro')),
        ('X14 PRO MAX', 'IPHONE', ('14', 'pro max')),
        ('X14', 'IPHONE', ('14', None)),
        ('A21S', 'SAMSUNG', ('a21', 's')),
        ('A21S/A217', 'SAMSUNG', ('a21', 's')),
        ('S21', 'SAMSUNG', ('s21', None)),
        ('S21 FE', 'SAMSUNG', ('s21', 'fe')),
        ('S21 PLUS', 'SAMSUNG', ('s21', 'plus')),
        ('S21 ULTRA(ACTUALIZACION AUTOMATICA)', 'SAMSUNG', ('s21', 'ultra')),
    ]
    r = True
    for desc, marca, esp in casos:
        got = normalizar_modelo_descripcion(desc, marca)
        r &= chk(got == esp, f"'{desc}' [{marca}] -> {got}")
    return r


def t_norm_query():
    print("\n[4] normalizar_modelo_query")
    casos = [
        ('14 pro', 'iphone', ('14', 'pro')),
        ('14 pro max', 'iphone', ('14', 'pro max')),
        ('14', 'iphone', ('14', None)),
        ('a21', 'samsung', ('a21', None)),
        ('a21s', 'samsung', ('a21', 's')),
        ('s21', 'samsung', ('s21', None)),
        ('s21 plus', 'samsung', ('s21', 'plus')),
    ]
    r = True
    for mod, marca, esp in casos:
        got = normalizar_modelo_query(mod, marca)
        r &= chk(got == esp, f"'{mod}' [{marca}] -> {got}")
    return r


async def t_iphone_14_pro():
    print("\n[5] iPhone 14 Pro NO incluye 14 Pro Max")
    resp = await obtener_cotizacion_display('iPhone', '14 pro')
    print(f"  {resp[:280]}...")
    r = chk('14 PRO' in resp.upper(), "menciona 14 PRO")
    # Si hay precio, el promedio NO debe estar contaminado por Pro Max.
    # Verificacion suave: la respuesta no debe contener 'PRO MAX' en una linea de precio.
    no_max = ('PRO MAX' not in resp.upper()) or ('pro max' in resp.lower() and 'manejamos' in resp.lower())
    r &= chk(no_max, "no menciona 14 PRO MAX dentro del bloque de precios")
    return r


async def t_a21_pregunta():
    print("\n[6] Samsung A21 (no existe) -> pregunta variantes")
    resp = await obtener_cotizacion_display('Samsung', 'A21')
    print(f"  {resp[:280]}...")
    r = chk('A21' in resp.upper(), "menciona A21")
    r &= chk(('NO ofrecer precios' in resp) or ('cual es tu modelo' in resp.lower()),
             "pide confirmar variante")
    r &= chk('S' in resp.upper(), "menciona variante (A21S)")
    return r


async def t_s21_pregunta():
    print("\n[7] Samsung S21 (con variantes) -> pregunta")
    resp = await obtener_cotizacion_display('Samsung', 'S21')
    print(f"  {resp[:350]}...")
    r = chk(('NO ofrecer precios' in resp) or ('cual es tu modelo' in resp.lower()),
            "pide confirmar variante")
    r &= chk(any(v in resp.upper() for v in ('FE', 'PLUS', 'ULTRA')), "lista variantes")
    return r


async def t_s21_plus_cotiza():
    print("\n[8] Samsung S21 PLUS -> cotiza")
    resp = await obtener_cotizacion_display('Samsung', 'S21 PLUS')
    print(f"  {resp[:280]}...")
    r = chk('S21 PLUS' in resp.upper(), "menciona S21 PLUS")
    r &= chk('MXN' in resp, "incluye precio MXN")
    return r


async def t_etiquetas_limpias():
    print("\n[9] Etiquetas limpias - sin tecnicismos")
    resp = await obtener_cotizacion_display('Samsung', 'S21 PLUS')
    r = True
    cliente_visible = resp.split(":\n\n", 1)[-1] if ":\n\n" in resp else resp
    for p in ('INCELL', 'CARTAN', 'COG', 'COF', 'FHD'):
        r &= chk(p not in cliente_visible.upper(), f"sin '{p}' en cuerpo cliente")
    return r


async def main():
    print("=" * 60)
    print("  Tests pricing nuevo")
    print("=" * 60)
    res = [
        t_parser(), t_categorias(), t_norm_desc(), t_norm_query(),
        await t_iphone_14_pro(), await t_a21_pregunta(),
        await t_s21_pregunta(), await t_s21_plus_cotiza(),
        await t_etiquetas_limpias(),
    ]
    ok = sum(1 for x in res if x)
    print(f"\n{'=' * 60}\n  {ok}/{len(res)} suites pasaron\n{'=' * 60}")
    return ok == len(res)


if __name__ == '__main__':
    asyncio.run(main())
