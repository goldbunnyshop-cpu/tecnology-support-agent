from datetime import datetime
from zoneinfo import ZoneInfo
from agent.horario import fuera_de_horario, texto_retoma, minutos_hasta_apertura, ajustar_promesas, nota_claude

Z = ZoneInfo("America/Mexico_City")
def d(y, m, dd, h, mi=0): return datetime(y, m, dd, h, mi, tzinfo=Z)

# 2026-10-29 es jueves; 2026-10-31 sábado; 2026-11-01 domingo
def test_rangos():
    assert fuera_de_horario(d(2026, 10, 29, 2))          # madrugada
    assert fuera_de_horario(d(2026, 10, 29, 10, 15))     # antes de 10:30
    assert not fuera_de_horario(d(2026, 10, 29, 10, 30))
    assert not fuera_de_horario(d(2026, 10, 29, 20, 59))
    assert fuera_de_horario(d(2026, 10, 29, 21, 0))      # cierra 9 pm entre semana
    assert fuera_de_horario(d(2026, 10, 31, 20, 0))      # sábado cierra 8 pm
    assert not fuera_de_horario(d(2026, 10, 31, 11, 30))

def test_textos_retoma():
    assert texto_retoma(d(2026, 10, 29, 2)) == "hoy a partir de las 10:30"
    assert texto_retoma(d(2026, 10, 29, 22)) == "mañana a partir de las 10:30"
    assert texto_retoma(d(2026, 10, 30, 22)) == "mañana a partir de las 11:30"   # viernes noche → sábado
    assert minutos_hasta_apertura(d(2026, 10, 29, 10, 0)) == 30

def test_ajusta_promesas_solo_fuera_de_horario():
    t = "Le transfiero con un responsable. En breve le escribe por este mismo chat."
    noche = ajustar_promesas(t, d(2026, 10, 29, 23))
    assert "mañana a partir de las 10:30" in noche and "En breve" not in noche
    assert ajustar_promesas(t, d(2026, 10, 29, 15)) == t
    t2 = "En un lapso no mayor a 30 minutos un técnico especialista te atenderá personalmente 😊"
    assert "hoy a partir de las 10:30" in ajustar_promesas(t2, d(2026, 10, 29, 3))
    t3 = "¡Gracias! 📸 Con esta foto identificamos el modelo exacto de su equipo y en breve le confirmamos."
    assert "en breve" not in ajustar_promesas(t3, d(2026, 10, 29, 3))

def test_nota_claude():
    assert nota_claude(d(2026, 10, 29, 15)) == ""
    assert "FUERA DE HORARIO" in nota_claude(d(2026, 10, 29, 23))
