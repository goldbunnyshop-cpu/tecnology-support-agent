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
    # OPPO A78 4G: el OLED ($778 × 3 = $2,334) no salía
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
    assert {702, 1002, 1680} <= precios   # misma calidad con 2 precios → el más caro


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


def test_descripcion_breve_por_calidad_todas_las_marcas():
    _, t = _precios("samsung", "a15")
    assert "🔹 Calidad genérica: $600 MXN\nFunciona bien para uso diario" in t
    assert "🔸 Calidad original: $900 MXN\nColores, brillo y respuesta táctil como la de fábrica." in t
    assert "⭐ Calidad OLED con marco: $1,845 MXN\nPantalla OLED" in t
    # La descripción va una sola vez por calidad y no se repiten etiquetas idénticas
    _, t = _precios("motorola", "edge 40 neo")
    assert t.count("Pantalla OLED:") == 1 and t.count("Calidad AMOLED con marco") == 1 and "$2,334 MXN" in t


def test_sin_marca_confirma_antes_de_cotizar():
    import asyncio
    from agent.brain import _intentar_respuesta_pricing_contextual as f
    r = asyncio.run(f("pantalla g50", []))     # solo existe en Moto
    assert "¿Tu equipo es Moto G50?" in r and "MXN" not in r
    assert "IPHONE" not in asyncio.run(f("display note 13 pro", []))
    h = [{"role": "user", "content": "display a55"}, {"role": "assistant", "content": "¿Tu equipo es ZTE A55?"}]
    assert "$600 MXN" in asyncio.run(f("sí", h))
    assert "$1,200 MXN" in asyncio.run(f("no, es samsung", h))


def test_lista_manual_otras_marcas_samsung_a55():
    import asyncio
    from agent.brain import _intentar_respuesta_pricing_contextual as f
    for q in ("cuanto cuesta el display de samsung a55", "pantalla galaxy a55 5g", "samsung a55"):
        r = asyncio.run(f(q, []))
        assert "Calidad genérica: $1,200 MXN" in r and "Calidad original: $1,800 MXN" in r, (q, r)
        assert "Pierde la función de huella en la pantalla." in r and "técnico" not in r
    # Sin marca: ahora existen Samsung A55 (manual) y ZTE A55 (Hugo) → pregunta la marca
    r = asyncio.run(f("display a55", []))
    assert "SAMSUNG" in r and "ZTE" in r and "MXN" not in r
