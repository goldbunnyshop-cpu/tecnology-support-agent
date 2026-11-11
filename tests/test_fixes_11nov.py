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


def test_casos_reales_logs():
    from agent.estatus_equipo import equipo_en_taller
    from agent.filtro_domicilio import es_consulta_domicilio
    # 5510032479: "¿ya puedo pasar a recoger mi tablet?" → estatus, NO domicilio
    t = "Buena tarde. Quisiera saber si ya puedo pasar a recoger mi tablet"
    assert es_pregunta_estatus(t) and not es_consulta_domicilio(t)
    assert es_consulta_domicilio("¿pueden pasar a recoger mi tablet a mi casa?")
    # Equipo ya en el taller → sin seguimientos de venta
    for t in ("Hola, si. De hecho, quedaron en avisarme cuando estará lista",
              "Me refiero a que el día de ayer dejé una tablet a reparar",
              "Hola daniels, no ya que me dijeron que dentro de 2 días vaya",
              "Ya fui gracias", "Por el momento sólo espero la reparación de mi tablet"):
        assert equipo_en_taller(t), t
    assert not equipo_en_taller("cuanto cuesta la pantalla del iphone 13")
    # Cristal de cámara → "¿qué modelo?" → "iPhone 15 Pro Max y iPhone 13" → técnico, no display
    h = [{"role": "user", "content": "Una pregunta: también arreglan el cristal de las cámaras del iphone?"},
         {"role": "assistant", "content": "Sí, claro. ¿Me dice qué modelo?"}]
    r = _r("Es iPhone 15 pro Max y iPhone 13", h)
    assert "cristal de cámara" in r and "MXN" not in r, r


def test_en_taller_sin_seguimientos():
    import random
    from agent import leads
    from agent.memory import inicializar_db
    tel = f"52155{random.randint(10**7, 10**8 - 1)}"

    async def correr():
        await inicializar_db()
        await leads.crear_o_actualizar_lead(tel, mensaje_texto="cuanto cuesta el touch de mi ipad")
        await leads.crear_o_actualizar_lead(tel, mensaje_texto="ayer dejé una tablet a reparar, quedaron en avisarme")
        assert await leads.lead_en_taller(tel)
        assert tel not in [l.telefono for l in await leads.obtener_leads_para_seguimiento()]
    asyncio.run(correr())
