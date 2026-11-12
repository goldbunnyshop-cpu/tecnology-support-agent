# Una misma cita (mismo teléfono, día y hora) solo se avisa UNA vez al grupo interno,
# aunque llegue con distinto evento_id (ej. Claude repitió [[AGENDAR]] y se creó otro evento).
import asyncio
import random


def test_misma_cita_un_solo_aviso(monkeypatch):
    from agent import appointment_notifications as an
    from agent.memory import inicializar_db

    enviados = []

    async def falso_grupo(msg, reintentos=2, mentions=None):
        enviados.append(msg)
        return True

    monkeypatch.setattr(an, "_enviar_grupo", falso_grupo)

    async def correr():
        await inicializar_db()
        datos = dict(nombre="Raúl", telefono=f"52155{random.randint(10**7, 10**8 - 1)}", dispositivo="PS4", problema="Led azul",
                     fecha_texto="jueves 5 de noviembre", hora_texto="10:30 a.m.", asesor="Sofia")
        await an.notificar_nueva_cita(**datos, evento_id=f"a{random.random()}")
        await an.notificar_nueva_cita(**datos, evento_id=f"b{random.random()}")   # evento duplicado
        await an.notificar_nueva_cita(**{**datos, "problema": "Falla de led azul"}, evento_id=f"c{random.random()}")

    asyncio.run(correr())
    assert len(enviados) == 1
