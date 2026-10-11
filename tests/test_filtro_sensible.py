from agent.filtro_sensible import es_consulta_sensible, respuesta_sensible, RESPUESTA_SENSIBLE, RESPUESTA_SENSIBLE_INSISTENTE

DEBE_ACTIVAR = [
    "¿hacen bypass de FRP?", "me pide la cuenta de google después de formatear", "quiero quitar la cuenta google",
    "necesito quitar el icloud de un iphone", "el iphone tiene bloqueo de activación", "se puede quitar el apple id del dueño anterior",
    "olvidé el patrón de mi celular", "quiero quitar el pin", "cuánto cobran por desbloquear un celular / liberarlo?",
    "liberar mi cel de telcel", "el celular está bloqueado por compañía", "reparan el IMEI?", "mi imei está en lista negra",
    "me lo pueden rootear", "desbloquear bootloader", "hacen jailbreak a ps4?", "chipean la switch?", "mi consola tiene ban online",
    "quitan el baneo de xbox", "instalan juegos piratas", "cambio de región de la ps5", "tiene cfw?", "tiene MDM mi tablet",
    "me instalas juegos gratis?", "modifican el software de la consola", "FRP", "by pass google",
]
NO_DEBE_ACTIVAR = [
    "mi switch no enciende", "se cayó mi celular y el display no sirve", "cuánto cuesta el display de un samsung a54",
    "necesito liberar espacio en mi celular", "no funciona el desbloqueo facial", "no funciona el desbloqueo por huella",
    "el control de ps5 tiene drift", "quiero un mantenimiento a mi laptop", "mi laptop no carga", "la bateria del iphone 12",
    "cuál es el horario", "dónde están ubicados", "quiero agendar una cita", "mi ps4 hace mucho ruido", "restablecer mi laptop de fabrica",
    "el celular no carga", "hola buenas tardes", "mi xbox no lee discos", "quiero respaldar mis fotos",
]

def test_activa():
    falló = [m for m in DEBE_ACTIVAR if not es_consulta_sensible(m)]
    assert not falló, falló

def test_no_activa():
    falló = [m for m in NO_DEBE_ACTIVAR if es_consulta_sensible(m)]
    assert not falló, falló

def test_seguimiento_y_insistencia():
    h = []
    r1 = respuesta_sensible("hacen bypass de frp?", h)
    assert r1 == RESPUESTA_SENSIBLE
    h = [{"role": "user", "content": "hacen bypass de frp?"}, {"role": "assistant", "content": r1}]
    assert respuesta_sensible("¿y cuánto cuesta?", h) == RESPUESTA_SENSIBLE_INSISTENTE
    assert respuesta_sensible("gracias, mañana paso", h) is None
    assert respuesta_sensible("mi switch no enciende", []) is None
