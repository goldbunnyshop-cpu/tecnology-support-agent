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


def test_captura_y_foto_ilegible_tambien_son_fijas():
    from agent.vision import FOTO_ILEGIBLE
    cap = {"puede_diagnosticar": True, "es_captura_pantalla": True, "modelo_probable": "Google Pixel 6 Pro"}
    assert respuesta_foto_equipo(cap, []) == PEDIR_FOTO_TRASERA      # caso Nubia: ya no se describe la foto
    assert respuesta_foto_equipo({"puede_diagnosticar": False}, []) == FOTO_ILEGIBLE
    h = [{"role": "assistant", "content": FOTO_ILEGIBLE}]
    assert respuesta_foto_equipo(DANO, h) == FOTO_TRASERA_RECIBIDA

def test_aviso_grupo_con_mencion():
    from agent.vision import mensaje_grupo_foto_trasera, numero_mencion
    assert numero_mencion("5541576331") == "5215541576331"
    assert numero_mencion("5215541576331") == "5215541576331"
    txt = mensaje_grupo_foto_trasera("5215537195598@s.whatsapp.net",
                                     {"marca": "Samsung", "modelo_probable": "Galaxy A54"},
                                     [{"role": "user", "content": "se rompió la pantalla"}], "5541576331")
    assert txt.startswith("@5215541576331") and "reanudar: 5215537195598" in txt and "Galaxy A54" in txt


def test_foto_de_pantalla_encendida_sin_modelo_pide_trasera():
    # Caso Nubia: foto del celular con la pantalla encendida que la IA tomó como "captura"
    a = {"puede_diagnosticar": True, "es_captura_pantalla": True, "modelo_probable": ""}
    assert respuesta_foto_equipo(a, []) == PEDIR_FOTO_TRASERA


def test_historial_foto_marca_estimacion():
    from agent.vision import construir_contexto_historial
    t = construir_contexto_historial({"tipo_dispositivo": "celular", "marca": "Google",
                                      "modelo_probable": "Pixel 6 Pro", "dano_visible": "pantalla rota"})
    assert "NO confirmada" in t and "Pixel 6 Pro" in t
