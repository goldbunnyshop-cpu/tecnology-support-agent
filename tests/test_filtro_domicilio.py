from agent.filtro_domicilio import (
    es_consulta_domicilio, evaluar_domicilio, respuesta_domicilio, en_modo_domicilio, resolver_ubicacion,
    mensaje_grupo_domicilio, RESPUESTA_DOMICILIO, RESPUESTA_PEDIR_CP, TXT_FUERA, NOTA_CARGO,
    agregar_cargo_domicilio, texto_desglose,
)

DEBE_ACTIVAR = [
    "¿tienen servicio a domicilio?", "hacen reparaciones a domicilio?", "cuánto cobran a domicilio",
    "pueden venir a mi casa?", "¿van a domicilio?", "pasan por el equipo?", "recogen la laptop?",
    "el técnico puede ir hasta mi oficina?", "servicio en casa", "vienen por mi celular?",
    "atienden a domicilio en Coyoacán?", "Servicio A Domicilio",
    "me lo pueden recoger?", "pueden pasar por el equipo?", "podrían venir a mi oficina?",
]
NO_DEBE_ACTIVAR = [
    "cuánto cuesta el display de un samsung a54", "mi switch no enciende", "dónde están ubicados",
    "quiero agendar una cita", "voy saliendo de mi casa", "lo dejé en casa", "hola buenas tardes",
    "mi laptop no carga", "el control de ps5 tiene drift", "cuál es el horario",
    # Casos reales / frases del cliente sobre sí mismo
    "Gracias, más tarde paso a recoger mi equipo", "Yo paso, no hay alguien que la reciba en mi domicilio",
    "tengo que ir a mi casa por el cargador", "voy a recoger mi celular", "mañana paso a recogerlo",
    "voy a ir a mi casa y regreso", "lo llevo mañana al módulo",
]


def _h(*pares):
    return [{"role": r, "content": c} for r, c in pares]


H_INICIO = _h(("user", "tienen servicio a domicilio?"), ("assistant", RESPUESTA_DOMICILIO + "\n\n" + NOTA_CARGO))


def test_activa():
    assert not [m for m in DEBE_ACTIVAR if not es_consulta_domicilio(m)]


def test_no_activa():
    assert not [m for m in NO_DEBE_ACTIVAR if es_consulta_domicilio(m)]


def test_primera_vez_pide_cp():
    d = evaluar_domicilio("tienen servicio a domicilio?", [])
    assert d.texto.startswith(RESPUESTA_DOMICILIO) and NOTA_CARGO in d.texto and not d.transferir


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


def test_precio_en_modo_domicilio_lo_contesta_flujo_normal():
    assert evaluar_domicilio("¿y cuánto cuesta?", H_INICIO) is None


def test_cotizacion_previa_ps5_desglose():
    h = _h(("user", "cuánto el mantenimiento de ps5"),
           ("assistant", "El mantenimiento de PS5 es de $1,400 MXN, incluye limpieza y pasta térmica."))
    d = evaluar_domicilio("lo pueden hacer a domicilio?", h)
    assert "$1,400 + servicio a domicilio $400 = *$1,800 MXN*" in d.texto and not d.transferir


def test_cotizacion_display_varias_opciones():
    q = ("Para SAMSUNG A54 tenemos estas opciones:\n\n* Calidad genérica: $1,200 MXN\n"
         "* Calidad original: $1,500 MXN\n\nCual opcion te interesa?")
    r = agregar_cargo_domicilio(q)
    assert "Calidad genérica: $1,200 + $400 = *$1,600 MXN*" in r
    assert "Calidad original: $1,500 + $400 = *$1,900 MXN*" in r
    assert agregar_cargo_domicilio(r) == r          # no duplica
    assert agregar_cargo_domicilio("¿De qué modelo es?") == "¿De qué modelo es?"


def test_diagnostico_domicilio():
    assert "$200 + $400 = $600" in NOTA_CARGO


def test_despues_de_transferir_no_repite():
    h = H_INICIO + _h(("user", "14000"), ("assistant", evaluar_domicilio("14000", H_INICIO).texto))
    assert evaluar_domicilio("gracias", h) is None and en_modo_domicilio(h)


def test_no_aplica_a_otras_consultas():
    assert respuesta_domicilio("cuánto cuesta la pantalla del a54", []) is None


def test_aviso_grupo():
    d = evaluar_domicilio("14000", H_INICIO)
    txt = mensaje_grupo_domicilio("5215512345678@s.whatsapp.net", d, H_INICIO, "14000")
    assert "reanudar: 5215512345678" in txt and "DENTRO" in txt


def test_cliente_declina_sale_de_modo():
    h = H_INICIO + _h(("user", "Yo paso, no hay alguien que la reciba"), ("assistant", "Perfecto, aquí la esperamos"))
    assert not en_modo_domicilio(h)
    assert evaluar_domicilio("a qué hora cierran?", h) is None
    assert evaluar_domicilio("mejor la llevo yo", H_INICIO) is None
