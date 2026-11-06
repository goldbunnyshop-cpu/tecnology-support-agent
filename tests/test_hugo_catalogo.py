# Cotización de displays (no iPhone) contra el catálogo Hugo Shop con la regla x3.
# Casos reales donde el bot fallaba hasta el 6 nov 2026 (4G/5G, "NOTE10PRO" pegado, etiquetas de proveedor).
import asyncio
import re

from agent import pricing as P


def _precios(marca, modelo):
    t = asyncio.run(P.obtener_cotizacion_display(marca, modelo))
    return {int(x.replace(",", "")) for x in re.findall(r"\$([\d,]+) MXN", t)}, t


def test_red_4g_5g_no_esconde_opciones():
    # "A15 4G/5G" OLED ($615 × 3 = $1,845) antes no salía ni con "a15" ni con "a15 4g"
    for q in ("a15", "a15 4g"):
        precios, _ = _precios("samsung", q)
        assert {600, 900, 1845} <= precios, (q, precios)
    # Moto G50: el cliente dijo "4g" y el bot le volvía a preguntar 4G o 5G (loop)
    precios, t = _precios("moto", "g50 4g")
    assert precios == {600, 900} and "versiones" not in t
    # Con 5G no se le ofrece la pantalla que el catálogo marca solo para 4G
    precios, _ = _precios("xiaomi", "redmi note 13 pro 5g")
    assert 1608 not in precios and 1728 in precios
    # OPPO A78 4G: el OLED ($778 × 3 = $2,334) no salía
    assert 2334 in _precios("oppo", "a78 4g")[0]


def test_modelo_pegado_en_catalogo():
    # Catálogo: "REDMI NOTE10PRO" (pegado) y "REDMI NOTE10 PRO" → mismas opciones
    precios, _ = _precios("xiaomi", "redmi note 10 pro")
    assert {600, 900, 702, 1002, 1680} <= precios


def test_regla_x3():
    # < $600 → piso 600/900 · 600–999 → x3 y x3+300 · ≥ 1,000 → x3
    assert P.precio_x3_por_calidad(519, "GENERICA") == 600
    assert P.precio_x3_por_calidad(519, "ORIGINAL") == 900
    assert P.precio_x3_por_calidad(849, "ORIGINAL") == 1149
    assert P.precio_x3_por_calidad(1812, "ORIGINAL") == 1812


def test_etiquetas_sin_marcas_de_proveedor():
    assert P.etiqueta_calidad_cliente("HG AMOLED C/M", False) == "Calidad AMOLED con marco"
    assert P.etiqueta_calidad_cliente("AA-SOFT OLED C/M", False) == "Calidad original SOFT OLED con marco"
    assert "original" not in P.etiqueta_calidad_cliente("AA TLED INCELL S/M BOUTIQUE", False)
