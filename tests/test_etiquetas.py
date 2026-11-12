# Etiqueta de WhatsApp Business "Cliente con nota de servicio" → sin seguimientos de venta.
import asyncio

from agent import etiquetas as E


def test_lee_ids_en_cualquier_formato():
    otro = [{"id": "5215510032479@c.us", "name": "Daniel"}, {"id": {"_serialized": "5215639659669@c.us"}}]
    whapi = {"chats": [{"id": "5215512345678@s.whatsapp.net"}], "messages": []}
    assert E._ids_de_chats(otro) == ["5215510032479@c.us", "5215639659669@c.us"]
    assert E._ids_de_chats(whapi) == ["5215512345678@s.whatsapp.net"]
    assert E._tel10("5215510032479@c.us") == "5510032479"


def test_nombre_etiqueta_sin_mayusculas_ni_acentos(monkeypatch):
    monkeypatch.delenv("ETIQUETA_NOTA_SERVICIO", raising=False)
    assert E.nombre_etiqueta() == E._norm("Cliente con Nota de Servicio")


def test_si_la_api_falla_no_bloquea(monkeypatch):
    monkeypatch.setenv("WHATSAPP_PROVIDER", "whapi")

    async def _falla(c):
        raise RuntimeError("sin red")

    monkeypatch.setattr(E, "_labels_whapi", _falla)
    E._cache.update(ts=0.0, telefonos=set(), ok=False)
    assert asyncio.run(E.tiene_nota_servicio("5215510032479")) is False


def test_lee_etiqueta_de_whapi(monkeypatch):
    class _R:
        def __init__(self, data):
            self._d = data

        def raise_for_status(self):
            pass

        def json(self):
            return self._d

    class _Cliente:
        async def get(self, url, headers=None):
            if url.endswith("/labels"):
                return _R({"labels": [{"id": "7", "name": "Cliente con Nota de Servicio"}, {"id": "8", "name": "Otra"}]})
            assert url.endswith("/labels/7")
            return _R({"chats": [{"id": "5215510032479@s.whatsapp.net"}, {"id": "5215639659669@s.whatsapp.net"}]})

    monkeypatch.delenv("ETIQUETA_NOTA_SERVICIO", raising=False)
    ids = asyncio.run(E._labels_whapi(_Cliente()))
    assert sorted(E._tel10(x) for x in ids) == ["5510032479", "5639659669"]

def test_cache_marca_cliente(monkeypatch):
    import time
    E._cache.update(ts=time.time(), telefonos={"5510032479"}, ok=True)
    assert asyncio.run(E.tiene_nota_servicio("5215510032479@c.us"))
    assert not asyncio.run(E.tiene_nota_servicio("5215599999999"))
