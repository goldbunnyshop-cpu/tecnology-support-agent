from agent.filtro_domicilio import (
    es_consulta_domicilio, evaluar_domicilio, respuesta_domicilio, en_modo_domicilio, resolver_ubicacion,
    mensaje_grupo_domicilio, RESPUESTA_DOMICILIO, RESPUESTA_PEDIR_CP, RESPUESTA_DOMICILIO_PRECIO, TXT_FUERA,
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


def _h(*pares):
    return [{"role": r, "content": c} for r, c in pares]


H_INICIO = _h(("user", "tienen servicio a domicilio?"), ("assistant", RESPUESTA_DOMICILIO))


def test_activa():
    assert not [m for m in DEBE_ACTIVAR if not es_consulta_domicilio(m)]


def test_no_activa():
    assert not [m for m in NO_DEBE_ACTIVAR if es_consulta_domicilio(m)]


def test_primera_vez_pide_cp():
    d = evaluar_domicilio("tienen servicio a domicilio?", [])
    assert d.texto == RESPUESTA_DOMICILIO and not d.transferir


def test_cp_dentro_transfiere():
    d = evaluar_domicilio("14000", H_INICIO)          # Tlalpan Centro, junto al módulo
    assert d.transferir and d.ubicacion.cobertura == "dentro" and "sí llegamos" in d.texto


def test_cp_en_primer_mensaje():
    d = evaluar_domicilio("tienen servicio a domicilio en el 14000?", [])
    assert d.transferir and d.ubicacion.cobertura == "dentro"


def test_cp_borde_valida_con_tecnico():
    d = evaluar_domicilio("mi cp es 03330", H_INICIO)  # Xoco: borde
    assert d.transferir and d.ubicacion.cobertura == "borde" and "ubicación" in d.texto


def test_cp_fuera_nunca_niega():
    for cp in ("07300", "55000", "62000"):            # GAM, Ecatepec, Cuernavaca
        d = evaluar_domicilio(f"es el {cp}", H_INICIO)
        assert d.transferir and d.texto == TXT_FUERA


def test_colonia_y_alcaldia():
    u = resolver_ubicacion("vivo en Toriello Guerra, Tlalpan")
    assert u and u.cobertura == "dentro" and u.alcaldia == "Tlalpan"


def test_solo_alcaldia_pide_cp():
    d = evaluar_domicilio("en tlalpan", H_INICIO)
    assert not d.transferir and d.texto == RESPUESTA_PEDIR_CP


def test_no_se_atora():
    h = H_INICIO + _h(("user", "por aqui cerca"), ("assistant", RESPUESTA_PEDIR_CP))
    d = evaluar_domicilio("pues cerca del metro", h)
    assert d.transferir and d.texto == TXT_FUERA


def test_precio_sin_cifras():
    d = evaluar_domicilio("¿y cuánto cuesta?", H_INICIO)
    assert d.texto == RESPUESTA_DOMICILIO_PRECIO and "$" not in d.texto


def test_despues_de_transferir_no_repite():
    h = H_INICIO + _h(("user", "14000"), ("assistant", evaluar_domicilio("14000", H_INICIO).texto))
    assert evaluar_domicilio("gracias", h) is None and en_modo_domicilio(h)


def test_no_aplica_a_otras_consultas():
    assert respuesta_domicilio("cuánto cuesta la pantalla del a54", []) is None


def test_aviso_grupo():
    d = evaluar_domicilio("14000", H_INICIO)
    txt = mensaje_grupo_domicilio("5215512345678@s.whatsapp.net", d, H_INICIO, "14000")
    assert "reanudar: 5215512345678" in txt and "DENTRO" in txt
