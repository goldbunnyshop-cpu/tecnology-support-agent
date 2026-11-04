# Pedir ampliar memoria/almacenamiento = venta + instalación (aviso al grupo), nunca "cómprelo en Amazon".
from agent.venta_upgrade import es_solicitud_upgrade, mensaje_grupo_upgrade


def test_detecta_solicitudes_de_mejora():
    for t in ("quiero ampliar la memoria de mi ps5", "se puede aumentar el almacenamiento?",
              "le pueden poner un ssd de 2 tb", "ya no tengo espacio en mi consola",
              "y si le agregan más memoria?", "me interesa ampliar la ram de mi laptop"):
        assert es_solicitud_upgrade(t), t


def test_no_confunde_con_reparaciones():
    for t in ("cuanto cuesta el mantenimiento del ps5", "mi ps5 se calienta", "cuánto la pantalla",
              "tengo un iphone de 128 gb y se rompio la pantalla",
              "quiero cambiar la pantalla de mi celular de 128 gb"):
        assert not es_solicitud_upgrade(t), t


def test_aviso_no_pierde_el_servicio_original():
    m = mensaje_grupo_upgrade("5215512345678", "y si le ponen un ssd de 2tb?",
                              [{"role": "user", "content": "cuanto cuesta el mantenimiento de mi ps5"}], "Sofia")
    assert "VENTA" in m and "PS5" in m and "Mantenimiento" in m and "wa.me/5215512345678" in m


def test_prompt_prohibe_mandar_a_otra_tienda():
    txt = open("config/prompts.yaml", encoding="utf-8").read()
    assert "NUNCA sugieras comprarlo en Mercado Libre, Amazon" in txt
