from agent.vision import respuesta_foto_equipo, PEDIR_FOTO_TRASERA, FOTO_TRASERA_RECIBIDA

DANO = {"puede_diagnosticar": True, "es_captura_pantalla": False, "dano_visible": "pantalla rota", "vista": "frontal"}


def test_foto_dano_pide_trasera():
    r = respuesta_foto_equipo(DANO, [])
    assert r == PEDIR_FOTO_TRASERA and "costo" not in r and "diagn" not in r


def test_foto_dano_con_historial_tambien_pide_trasera():
    h = [{"role": "user", "content": "se me rompió la pantalla"}, {"role": "assistant", "content": "¿Qué modelo es?"}]
    assert respuesta_foto_equipo(DANO, h) == PEDIR_FOTO_TRASERA


def test_segunda_foto_tras_pedirla():
    h = [{"role": "assistant", "content": PEDIR_FOTO_TRASERA}]
    assert respuesta_foto_equipo(DANO, h) == FOTO_TRASERA_RECIBIDA


def test_foto_trasera_directa():
    assert respuesta_foto_equipo(dict(DANO, vista="trasera"), []) == FOTO_TRASERA_RECIBIDA


def test_captura_ajustes_y_foto_ilegible_siguen_flujo_anterior():
    assert respuesta_foto_equipo({"puede_diagnosticar": True, "es_captura_pantalla": True}, []) is None
    assert respuesta_foto_equipo({"puede_diagnosticar": False}, []) is None
