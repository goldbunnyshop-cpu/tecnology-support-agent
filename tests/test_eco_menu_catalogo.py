import os
os.environ.setdefault("ANTHROPIC_API_KEY", "x")


def test_eco_del_bot_no_es_dueno():
    from agent.providers.whapi import registrar_envio_bot, es_eco_del_bot
    registrar_envio_bot("5215518080154@s.whatsapp.net", "¡Perfecto! Cuéntame, ¿qué modelo de celular tienes?")
    assert es_eco_del_bot("", "5215518080154", "¡Perfecto! Cuéntame, ¿qué modelo de celular tienes?")
    assert not es_eco_del_bot("", "5215518080154", "Calidad generica $600")   # lo escribió Christian
    registrar_envio_bot("x", mensaje_id="ABC-123")
    assert es_eco_del_bot("ABC-123", "999", "otro texto")
    assert es_eco_del_bot("", "1", "", source="api")


def test_saludo_simple_vs_pregunta():
    from agent.main import _es_saludo_simple
    for t in ("Hola", "Hola, quiero cotizar", "Buenas tardes", "info", "Me interesa", "hola buenas"):
        assert _es_saludo_simple(t), t
    for t in ("¿Ofrecen garantía para todos los modelos?", "Pantalla rota de un ZTE A54",
              "¿Cuánto cuesta la reparación de pantalla?"):
        assert not _es_saludo_simple(t), t


def test_catalogo_prefijos_wf_y_marco():
    from agent.pricing import normalizar_modelo_descripcion, normalizar_modelo_query
    assert ("s20", "fe") in normalizar_modelo_descripcion("W/F S20 FE", "SAMSUNG")
    assert ("s20", "fe") in normalizar_modelo_descripcion("WF S20 FE", "SAMSUNG")
    assert normalizar_modelo_descripcion("X14PRO(MOVIL IC) S/M(BOUTIQUE)", "IPHONE") == [("14", "pro")]
    assert normalizar_modelo_query("galaxy s20 fe 5g", "samsung") == ("s20", "fe")
