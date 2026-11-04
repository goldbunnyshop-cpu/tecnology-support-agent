# El bot respeta el plazo que da el cliente ("el viernes les confirmo") antes de volver a escribirle.
import asyncio
import random
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from agent.espera_cliente import detectar_espera

MX = ZoneInfo("America/Mexico_City")
MIERCOLES = datetime(2026, 11, 4, 15, 0, tzinfo=MX)


def _f(texto):
    r = detectar_espera(texto, MIERCOLES)
    return r.strftime("%d/%m %H:%M") if r else None


def test_plazos_del_cliente():
    assert _f("el viernes les confirmo") == "06/11 12:00"
    assert _f("El viernes en la tarde te aviso") == "06/11 17:00"
    assert _f("la próxima semana paso") == "09/11 12:00"
    assert _f("el mes que entra lo llevo") == "02/12 12:00"
    assert _f("mañana te digo") == "05/11 12:00"
    assert _f("en 2 horas te confirmo") == "04/11 17:15"
    assert _f("cuando me paguen la quincena lo llevo") == "16/11 12:00"
    assert _f("el 20 de noviembre paso") == "20/11 12:00"
    assert _f("lo platico con mi esposa y les aviso") == "06/11 12:00"


def test_no_es_espera():
    for texto in ("gracias", "ok", "el lunes", "el viernes quiero cita a las 3", "cuánto cuesta la pantalla"):
        assert _f(texto) is None, texto


def test_seguimiento_espera_al_dia_que_dijo(monkeypatch):
    from agent import leads
    from agent.memory import inicializar_db

    tel = f"52155{random.randint(10**7, 10**8 - 1)}"

    async def correr():
        await inicializar_db()
        await leads.crear_o_actualizar_lead(tel, mensaje_texto="cuánto cuesta la pantalla del iphone 13")
        await leads.crear_o_actualizar_lead(tel, mensaje_texto="el viernes les confirmo")
        lead = next(l for l in await leads.obtener_todos_los_leads() if l.telefono == tel)
        assert lead.seguimiento_pausado_hasta is not None and lead.espera_texto
        # 3 horas después (antes del viernes) NO toca seguimiento
        real_utcnow = datetime.utcnow
        class _DT(datetime):
            @classmethod
            def utcnow(cls):
                return real_utcnow() + timedelta(hours=3)
        monkeypatch.setattr(leads, "datetime", _DT)
        assert tel not in [l.telefono for l in await leads.obtener_leads_para_seguimiento()]
        # Ya pasado el plazo sí toca
        class _DT2(datetime):
            @classmethod
            def utcnow(cls):
                return lead.seguimiento_pausado_hasta + timedelta(minutes=5)
        monkeypatch.setattr(leads, "datetime", _DT2)
        assert tel in [l.telefono for l in await leads.obtener_leads_para_seguimiento()]

    asyncio.run(correr())
