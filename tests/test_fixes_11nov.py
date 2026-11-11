# Fixes 11 nov 2026: estatus de reparación, tablets/iPad sin precio inventado, cristal de cámara.
import asyncio

from agent.brain import _intentar_respuesta_pricing_contextual as cotizar
from agent.estatus_equipo import es_pregunta_estatus


def test_pregunta_estatus():
    for t in ("ya esta listo mi equipo?", "¿ya quedó?", "ya puedo pasar por mi celular?",
              "cuando paso a recoger mi tableta", "¿Cómo va mi celular?", "ya está lista mi tableta?",
              "Ya lo repararon?", "a que hora puedo ir por el?"):
        assert es_pregunta_estatus(t), t
    for t in ("cuanto tarda si lo llevo hoy", "en cuanto tiempo queda listo?", "si lo dejo hoy queda listo el mismo dia?",
              "cuanto cuesta la pantalla", "ya está bien gracias", "el touch no funciona"):
        assert not es_pregunta_estatus(t), t


def _r(msg, hist=None):
    return asyncio.run(cotizar(msg, hist or [])) or ""


def test_tablet_siempre_tecnico():
    h = [{"role": "user", "content": "necesito cambiar el touch de mi ipad 9"},
         {"role": "assistant", "content": "Claro, ¿qué modelo es?"}]
    for msg, hist in (("cuanto cuesta el cambio de touch de ipad", []), ("cuanto el touch del ipad 9", []),
                      ("cuanto cuesta?", h), ("y la pantalla?", h)):
        r = _r(msg, hist)
        assert "técnico" in r and "$" not in r, (msg, r)
    # Si ahora pregunta por un celular, se cotiza normal
    assert "MXN" in _r("y la pantalla de un samsung a15?", h)


def test_cristales_de_camara_no_son_display():
    h = [{"role": "user", "content": "cuanto la pantalla del samsung a15"}]
    for msg in ("cuanto los cristales de la camara", "y cuanto cuesta cambiar los cristales de la camara?",
                "tambien el vidrio de la camara cuanto"):
        r = _r(msg, h)
        assert "cámara" in r and "técnico" in r and "MXN" not in r, (msg, r)
