# tests/test_precio_display_x3.py — Regla de precio de displays vigente (sep-2026)
import os
os.environ.setdefault("ANTHROPIC_API_KEY", "x")

from agent.pricing import (
    formatear_cotizacion_hugo,
    etiqueta_calidad_cliente,
    modelo_para_cliente,
)


def _p(costo, calidad="ORIG S/M"):
    return {"PRECIO_USD": costo, "CALIDAD": calidad, "DESCRIPCION": "X"}


def test_piso_menor_600():
    t = formatear_cotizacion_hugo("samsung", "A15", [_p(150)])  # x3 = 450
    assert "Calidad genérica: $600 MXN / Calidad original: $900 MXN" in t


def test_rango_600_1000_suma_300():
    t = formatear_cotizacion_hugo("alcatel", "5024", [_p(208)])  # x3 = 624
    assert "Calidad genérica: $624 MXN / Calidad original: $924 MXN" in t


def test_rango_1000_4000_directo_con_calidad():
    t = formatear_cotizacion_hugo("motorola", "EDGE 30 NEO", [_p(1081, "OLED S/M")])  # x3 = 3243
    assert "* OLED sin marco: $3,243 MXN" in t


def test_mayor_4000_transfiere_otras_marcas():
    t = formatear_cotizacion_hugo("samsung", "S25 ULTRA", [_p(1500)])  # x3 = 4500
    assert "técnico" in t and "$4,500" not in t


def test_mezcla_con_opcion_tecnico():
    t = formatear_cotizacion_hugo("samsung", "S24", [_p(318, "INCELL S/M"), _p(1460, "OLED S/M")])
    assert "$954 MXN / Calidad original: $1,254 MXN" in t
    assert "se la cotiza un técnico" in t and "$4,380" not in t


def test_iphone_una_linea_por_calidad_el_mas_caro():
    t = formatear_cotizacion_hugo("iphone", "14", [
        _p(318, "INCELL+ S/M(MOVIL IC)"), _p(337, "HG FHD INCELL COG S/M (B)"),   # genérica: más caro 337 → 1,011
        _p(418, "HG FHD S/M(BOUTIQUE)"), _p(1032, "ORIG"),                       # original: más caro 1032 → 3,096
        _p(875, "DD-SOFT OLED S/M"), _p(1460, "DD-SOFT OLED S/M"),               # premium: más caro 1460 → 4,380
    ])
    assert "* Calidad genérica: $1,011 MXN" in t
    assert "* Calidad original (autoprogramable): $3,096 MXN" in t
    assert "* Calidad premium (OLED): $4,380 MXN" in t   # iPhone: >$4,000 se cotiza igual
    assert "técnico" not in t and t.count("\n* ") == 3


def test_iphone_piso_y_mas_300():
    t = formatear_cotizacion_hugo("iphone", "XR", [_p(150, "INCELL S/M"), _p(250, "HG FHD S/M")])
    assert "Calidad genérica: $600 MXN" in t and "Calidad original (autoprogramable): $1,050 MXN" in t
    t = formatear_cotizacion_hugo("iphone", "XR", [_p(150, "INCELL S/M"), _p(180, "ORIG")])
    assert "Calidad original (autoprogramable): $900 MXN" in t


def test_etiquetas():
    assert etiqueta_calidad_cliente("INCELL C/M(BOUTIQUE)", False) == "Calidad genérica con marco"
    assert etiqueta_calidad_cliente("AA HARD OLED C/M(BOUTIQUE)", False) == "Calidad original HARD OLED con marco"
    assert etiqueta_calidad_cliente("CARTAN HARD OLED S/M", True) == "HARD calidad premium sin marco"
    assert "MOVIL" not in etiqueta_calidad_cliente("INCELL+ S/M(MOVIL IC)", True)
    assert etiqueta_calidad_cliente("OLED S/M", False) == "OLED sin marco"  # OLED solo cambia en iPhone


def test_iphone_quita_x_11_a_17():
    assert modelo_para_cliente("iphone", "X14PRO MAX") == "14PRO MAX"
    assert modelo_para_cliente("iphone", "X11") == "11"
    for m in ("X", "XR", "XS", "XS MAX"):
        assert modelo_para_cliente("iphone", m) == m
    assert modelo_para_cliente("samsung", "X14") == "X14"
