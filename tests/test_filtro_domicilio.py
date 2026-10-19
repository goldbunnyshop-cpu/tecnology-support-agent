from agent.filtro_domicilio import (
    es_consulta_domicilio, respuesta_domicilio, en_modo_domicilio,
    RESPUESTA_DOMICILIO, RESPUESTA_DOMICILIO_PRECIO,
)

DEBE_ACTIVAR = [
    "¿tienen servicio a domicilio?", "hacen reparaciones a domicilio?", "cuánto cobran a domicilio",
    "pueden venir a mi casa?", "¿van a domicilio?", "pasan por el equipo?", "recogen la laptop?",
    "el técnico puede ir hasta mi oficina?", "servicio en casa", "vienen por mi celular?",
    "atienden a domicilio en Coyoacán?", "Servicio A Domicilio",
]
NO_DEBE_ACTIVAR = [
    "cuánto cuesta el display de un samsung a54", "mi switch no enciende", "dónde están ubicados",
    "quiero agendar una cita", "voy saliendo de mi casa", "lo dejé en casa", "hola buenas tardes",
    "mi laptop no carga", "el control de ps5 tiene drift", "cuál es el horario",
]


def test_activa():
    fallo = [m for m in DEBE_ACTIVAR if not es_consulta_domicilio(m)]
    assert not fallo, fallo


def test_no_activa():
    fallo = [m for m in NO_DEBE_ACTIVAR if es_consulta_domicilio(m)]
    assert not fallo, fallo


def test_flujo_sin_precios():
    assert respuesta_domicilio("tienen servicio a domicilio?", []) == RESPUESTA_DOMICILIO
    h = [{"role": "user", "content": "tienen servicio a domicilio?"},
         {"role": "assistant", "content": RESPUESTA_DOMICILIO}]
    assert en_modo_domicilio(h)
    assert respuesta_domicilio("¿y cuánto cuesta?", h) == RESPUESTA_DOMICILIO_PRECIO
    assert respuesta_domicilio("Juan, Samsung A54, pantalla rota, Tlalpan", h) is None
    assert respuesta_domicilio("cuánto cuesta la pantalla del a54", []) is None
    assert not en_modo_domicilio([])
