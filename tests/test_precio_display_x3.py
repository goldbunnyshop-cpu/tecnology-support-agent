# tests/test_precio_display_x3.py — Regla de precio de displays vigente (sep-2026)
import os
os.environ.setdefault("ANTHROPIC_API_KEY", "x")

import pytest
import agent.pricing as pricing
from agent.pricing import (
    formatear_cotizacion_hugo,
    etiqueta_calidad_cliente,
    modelo_para_cliente,
    aplicar_escalera_iphone,
)


@pytest.fixture(autouse=True)
def _sin_catalogo_real(monkeypatch):
    # Las pruebas de formato usan productos de ejemplo, no la escalera del catálogo real
    monkeypatch.setattr(pricing, "tabla_iphone", lambda: {})


def _p(costo, calidad="ORIG S/M", desc="X"):
    return {"PRECIO_USD": costo, "CALIDAD": calidad, "DESCRIPCION": desc}


def test_piso_menor_600():
    t = formatear_cotizacion_hugo("samsung", "A15", [_p(150)])  # x3 = 450
    assert "Calidad genérica: $600 MXN / Calidad original: $900 MXN" in t


def test_rango_600_1000_suma_300():
    t = formatear_cotizacion_hugo("alcatel", "5024", [_p(208)])  # x3 = 624
    assert "Calidad genérica: $624 MXN / Calidad original: $924 MXN" in t


def test_rango_1000_4000_directo_con_calidad():
    t = formatear_cotizacion_hugo("motorola", "EDGE 30 NEO", [_p(1081, "OLED S/M")])  # x3 = 3243
    assert "Calidad OLED sin marco: $3,243 MXN" in t


def test_mayor_4000_transfiere_otras_marcas():
    t = formatear_cotizacion_hugo("samsung", "S25 ULTRA", [_p(1500)])  # x3 = 4500
    assert "técnico" in t and "$4,500" not in t


def test_mezcla_con_opcion_tecnico():
    t = formatear_cotizacion_hugo("samsung", "S24", [_p(318, "INCELL S/M"), _p(1460, "OLED S/M")])
    assert "$954 MXN / Calidad original: $1,254 MXN" in t
    assert "se la cotiza un técnico" in t and "$4,380" not in t


def test_iphone_tres_calidades_el_mas_caro():
    t = formatear_cotizacion_hugo("iphone", "14", [
        _p(318, "INCELL+ S/M(MOVIL IC)"), _p(337, "HG FHD INCELL COG S/M (B)"),   # genérica: 337 → 1,011
        _p(875, "DD-SOFT OLED S/M"),                                             # original (OLED): 875 → 2,625
        _p(1032, "ORIG", "X14-(Diagnóstico) (Diagnóstico)"),                     # premium: 1032 → 3,096
    ])
    assert "Calidad genérica: $1,011 MXN" in t
    assert "Calidad original: $2,625 MXN" in t
    assert "Calidad premium" in t and "pieza desconocida" in t and "$3,096 MXN" in t
    assert "autoprogramable" not in t.lower() and "Diagn" not in t and "OLED" not in t
    assert t.count(" MXN") == 3


def test_iphone_mayor_4000_se_cotiza():
    t = formatear_cotizacion_hugo("iphone", "15 PRO MAX", [_p(1685, "ORIG", "X15PRO MAX (Diagnóstico)")])
    assert "$5,055 MXN" in t and "técnico" not in t


def test_iphone_piso_y_mas_300():
    t = formatear_cotizacion_hugo("iphone", "XR", [_p(150, "INCELL S/M"), _p(250, "ORIG S/M")])
    assert "Calidad genérica: $600 MXN" in t and "Calidad original: $1,050 MXN" in t
    t = formatear_cotizacion_hugo("iphone", "XR", [_p(150, "INCELL S/M"), _p(180, "ORIG")])
    assert "Calidad original: $900 MXN" in t


def test_etiquetas():
    assert etiqueta_calidad_cliente("INCELL C/M(BOUTIQUE)", False) == "Calidad genérica con marco"
    assert etiqueta_calidad_cliente("AA HARD OLED C/M(BOUTIQUE)", False) == "Calidad original HARD OLED con marco"
    assert etiqueta_calidad_cliente("CARTAN HARD OLED S/M", False) == "Calidad HARD OLED sin marco"
    assert "MOVIL" not in etiqueta_calidad_cliente("INCELL+ S/M(MOVIL IC)", True)
    assert etiqueta_calidad_cliente("OLED S/M", False) == "Calidad OLED sin marco"  # siempre empieza con "Calidad"


def test_iphone_quita_x_11_a_17():
    assert modelo_para_cliente("iphone", "X14PRO MAX") == "14PRO MAX"
    assert modelo_para_cliente("iphone", "X11") == "11"
    for m in ("X", "XR", "XS", "XS MAX"):
        assert modelo_para_cliente("iphone", m) == m
    assert modelo_para_cliente("samsung", "X14") == "X14"


def test_iphone_piso_solo_incell_agrega_original_900():
    t = formatear_cotizacion_hugo("iphone", "8", [_p(150, "INCELL S/M")])  # x3 = 450
    assert "Calidad genérica: $600 MXN" in t and "Calidad original: $900 MXN" in t


def test_iphone_piso_solo_original_agrega_generica_600():
    t = formatear_cotizacion_hugo("iphone", "8", [_p(150, "ORIG S/M")])  # x3 = 450
    assert "Calidad genérica: $600 MXN" in t and "Calidad original: $900 MXN" in t


def test_iphone_diagnostico_en_calidad_es_premium():
    t = formatear_cotizacion_hugo("iphone", "17", [_p(900, "DD-SOFT OLED S/M (Diagnóstico)", "X17(MOVIL IC)")])
    assert "Calidad premium" in t and "$2,700 MXN" in t and "Diagn" not in t


def test_iphone_fhd_es_generica():
    t = formatear_cotizacion_hugo("iphone", "14", [_p(325, "FHD S/M")])          # $975
    assert "Calidad genérica: $975 MXN" in t and "Calidad original" not in t
    t = formatear_cotizacion_hugo("iphone", "12", [_p(270, "HG FHD S/M(BOUTIQUE)"), _p(603, "AA HARD OLED FHD COF")])
    assert "Calidad genérica: $810 MXN" in t and "Calidad original: $1,809 MXN" in t


def test_iphone_premium_siempre_la_mas_cara():
    t = formatear_cotizacion_hugo("iphone", "13 PRO MAX", [
        _p(908, "DD-SOFT OLED S/M (Diagnóstico)", "X13PRO MAX"),   # 2,724
        _p(996, "HG SOFT OLED(ORIG BOUTIQUE)"),                     # 2,988
    ])
    assert "Calidad original: $2,724 MXN" in t and "$2,988 MXN" in t.split("Calidad premium")[1]


def test_todas_las_etiquetas_empiezan_con_calidad():
    import re
    for prods in ([_p(1081, "OLED S/M")], [_p(657, "AA HARD OLED C/M(BOUTIQUE)")], [_p(560, "HG HARD OLED S/M")]):
        t = formatear_cotizacion_hugo("samsung", "S24 FE", prods)
        for linea in re.findall(r"^\* (.+)$", t, flags=re.M):
            assert linea.startswith("Calidad") or linea.startswith("Opción"), linea


def test_iphone_sin_calidad_es_generica():
    t = formatear_cotizacion_hugo("iphone", "16 PRO", [_p(669, "S/M")])   # 2,007
    assert "Calidad genérica: $2,007 MXN" in t


def test_escalera_misma_linea():
    t = aplicar_escalera_iphone({"13": {"GENERICA": 1173}, "14": {"GENERICA": 975}, "15": {"GENERICA": 1305}})
    assert t["14"]["GENERICA"] == 1371          # 1,173 + (1,173 − 975)
    assert t["15"]["GENERICA"] == 1437          # 15 ($1,305) quedó abajo del 14 ajustado → 1,371 + 66


def test_escalera_dentro_de_generacion():
    t = aplicar_escalera_iphone({"15": {"ORIGINAL": 3000}, "15PRO": {"ORIGINAL": 2800}, "15PROMAX": {"ORIGINAL": 3100}})
    assert t["15PRO"]["ORIGINAL"] == 3200       # Pro ≥ normal: 3,000 + 200
    assert t["15PROMAX"]["ORIGINAL"] == 3300    # Pro Max ≥ Pro: 3,200 + 100



def test_lista_manual_iphone(tmp_path, monkeypatch):
    csvp = tmp_path / "precios_iphone.csv"
    csvp.write_text("modelo,generica,original,premium,nota\n13 mini,1250,1850,,\n14 Pro Max,1800,2800,3850,\nSE 2020,600,900,,\nSE 2022,700,1000,,\n", encoding="utf-8")
    monkeypatch.setattr(pricing, "RUTA_PRECIOS_IPHONE", str(csvp))
    pricing._cache_manual["mtime"] = None
    t = pricing.cotizar_iphone_manual("13 mini")
    assert "Calidad genérica: $1,250 MXN" in t and "Calidad original: $1,850 MXN" in t and "premium" not in t
    t = pricing.cotizar_iphone_manual("iphone 14 pro max")
    assert "$3,850 MXN" in t and "pieza desconocida" in t
    assert "SE 2020" in pricing.cotizar_iphone_manual("se") and "SE 2022" in pricing.cotizar_iphone_manual("se")
    assert "$700 MXN" in pricing.cotizar_iphone_manual("2022")
    assert "técnico" in pricing.cotizar_iphone_manual("20")


def test_iphone_dos_mensajes_sin_face_id():
    from agent.providers.base import partir_mensaje
    t = pricing._formatear_iphone("13", {"GENERICA": 1300, "ORIGINAL": 2000, "PREMIUM": 3300})
    m1, m2 = partir_mensaje(pricing._limpiar_si_hace_falta(t) if hasattr(pricing, "_limpiar_si_hace_falta") else t.split("\n\n", 1)[1])
    assert "$1,300 MXN" in m1 and "$3,300 MXN" in m1 and "MXN" not in m2
    assert "puede gastar más batería" in m1 and m1.count("pieza desconocida") == 3
    assert "especialistas en equipos Apple" in m2 and "Limpieza interna" in m2
    assert "bocinas, micrófonos, conectores y puerto de carga" in m2 and "después de la tarjeta madre" in m2
    assert "face id" not in t.lower()


def test_iphone_lcd_y_modelos_sin_aviso():
    for modelo in ("11", "XR", "SE 2022", "8 Plus"):
        t = pricing._formatear_iphone(modelo, {"GENERICA": 1100, "ORIGINAL": 1700, "PREMIUM": 2500})
        m1 = t.split("[[SIGUIENTE]]")[0]
        assert "Calidad genérica: $1,100 MXN\n🔸 Calidad original: $1,700 MXN" in m1
        assert "premium" not in m1.lower() and "pieza desconocida" not in m1 and "colores" not in m1


async def _no_dormir(*_):
    return None


def test_waha_parte_en_dos_envios(monkeypatch):
    import asyncio
    from agent.providers import waha
    enviados = []
    p = waha.ProveedorWaha()
    p.base = "http://x"
    async def falso_post(path, payload, timeout=20):
        enviados.append(payload["text"])
        class R: status_code = 201; text = ""; json = staticmethod(lambda: {})
        return R()
    monkeypatch.setattr(p, "_post", falso_post)
    monkeypatch.setattr(waha.asyncio, "sleep", _no_dormir)
    assert asyncio.run(p.enviar_mensaje("5512345678", "uno\n[[SIGUIENTE]]\ndos"))
    assert len(enviados) == 2 and enviados[0].startswith("uno") and enviados[1].startswith("dos")


def test_domicilio_va_con_los_precios():
    from agent.filtro_domicilio import agregar_cargo_domicilio
    t = agregar_cargo_domicilio("🔹 Calidad genérica: $1,300 MXN\n[[SIGUIENTE]]\nTu servicio incluye...")
    precios, valor = t.split("[[SIGUIENTE]]")
    assert "domicilio" in precios.lower() and "domicilio" not in valor.lower()
