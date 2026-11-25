# 24 nov 2026: "y la batería?" con modelo en el historial NO debe cotizar con la hoja de
# proveedor BATERÍAS iPHONE (x4). Toda pieza que no sea display va al técnico.
import asyncio

from agent.brain import _intentar_respuesta_pricing_contextual as cotizar

HIST = [
    {"role": "user", "content": "cuanto cuesta la pantalla de un iphone 14 pro max"},
    {"role": "assistant", "content": "Para iPhone 14 Pro Max tenemos estas opciones: ..."},
]


def _r(msg, hist=None):
    return asyncio.run(cotizar(msg, hist if hist is not None else HIST)) or ""


def test_bateria_por_contexto_va_al_tecnico():
    for msg in ("y la batería?", "también la bateria", "y la pila", "ademas la batería"):
        r = _r(msg)
        assert "técnico" in r and "$" not in r and "MXN" not in r, (msg, r)


def test_tapa_por_contexto_va_al_tecnico():
    r = _r("y también la tapa")
    assert "técnico" in r and "$" not in r, r


def test_bateria_directa_va_al_tecnico():
    r = _r("cuanto cuesta la bateria del iphone 14 pro max", [])
    assert "técnico" in r and "MXN" not in r, r


def test_no_rompe_display_ni_quejas():
    r = _r("cuanto cuesta la pantalla de un iphone 14 pro max", [])
    assert "necesito confirmarte" not in r, r
    r = _r("mi iphone no carga, creo que es la bateria", [])
    assert "necesito confirmarte" not in r, r
    r = _r("cuanto cuesta cambiar los botones del control de ps5", [])
    assert "necesito confirmarte" not in r, r
