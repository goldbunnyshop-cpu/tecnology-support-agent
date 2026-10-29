from agent.cliente_foraneo import es_cliente_foraneo, cliente_foraneo_en_historial

SI = [
    "Si, pero yo estaré en la ciudad de México como por el 7 de noviembre",
    "llego a la cdmx el viernes", "no vivo en la ciudad", "soy de Puebla",
    "cuando vaya a la ciudad se lo llevo", "estoy fuera de la ciudad", "vengo de provincia",
    "bajo al df el 15",
]
NO = [
    "se estrelló el display de mi celular", "a las 2 pm", "por la tarde", "gracias",
    "paso mañana al módulo", "estoy en Coyoacán", "voy saliendo", "voy para allá", "ya voy para allá",
]


def test_detecta():
    assert not [t for t in SI if not es_cliente_foraneo(t)]


def test_no_detecta():
    assert not [t for t in NO if es_cliente_foraneo(t)]


def test_historial():
    h = [{"role": "user", "content": "yo estaré en la Ciudad de México como por el 7 de noviembre"},
         {"role": "assistant", "content": "Perfecto"}]
    assert cliente_foraneo_en_historial(h, "por la tarde")
