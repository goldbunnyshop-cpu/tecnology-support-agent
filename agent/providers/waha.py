# agent/providers/waha.py — Adaptador para WAHA (WhatsApp HTTP API, self-hosted)
# Reemplazo gratuito de Whapi: misma conexión por QR (WhatsApp Web), pero corre
# en tu propio Railway. Variables de entorno:
#   WHATSAPP_PROVIDER=waha
#   WAHA_URL=https://<tu-servicio-waha>.up.railway.app   (sin "/" al final)
#   WAHA_API_KEY=<la misma key que pusiste en el servicio WAHA>
#   WAHA_SESSION=default                                  (WAHA Core solo permite "default")

import os
import json
import base64
import logging
import httpx
from dataclasses import dataclass
from urllib.parse import urlparse
from fastapi import Request
import asyncio
from agent.providers.base import ProveedorWhatsApp, MensajeEntrante, partir_mensaje, PAUSA_ENTRE_MENSAJES
# Reusamos el registro de ecos de whapi.py: main.py importa es_eco_del_bot desde ahí.
from agent.providers.whapi import registrar_envio_bot

logger = logging.getLogger("agentkit")

_cache_grupos: dict[str, str] = {}
_cache_lids: dict[str, str] = {}


def _limpiar(s: str) -> str:
    return (s or "").replace("@s.whatsapp.net", "").replace("@c.us", "").replace("@g.us", "").replace("@lid", "")


def _ids_grupo_interno() -> set[str]:
    ids = set()
    for var in ("GRUPO_CHRISTIAN_INTERNO", "GRUPO_INTERNO_ID"):
        v = os.getenv(var, "").strip()
        if v:
            ids.add(_limpiar(v))
    return ids


@dataclass
class MensajeEntranteWaha(MensajeEntrante):
    fuente: str = "desconocido"
    fuente_detalle: str = ""


def _es_difusion(chat_id: str) -> bool:
    c = str(chat_id or "").lower()
    return c.endswith("@broadcast") or c.endswith("@newsletter")


class ProveedorWaha(ProveedorWhatsApp):

    def __init__(self):
        self.base = os.getenv("WAHA_URL", "").rstrip("/")
        self.api_key = os.getenv("WAHA_API_KEY", "")
        self.session = os.getenv("WAHA_SESSION", "default")
        if not self.base:
            logger.warning("[WAHA] WAHA_URL no configurado")

    # ── utilidades ────────────────────────────────────────────────────────────
    def _headers(self) -> dict:
        h = {"Content-Type": "application/json; charset=utf-8"}
        if self.api_key:
            h["X-Api-Key"] = self.api_key
        return h

    @staticmethod
    def _chat_id(destino: str) -> str:
        """Número → 52155...@c.us ; deja intactos @g.us / @lid / @c.us."""
        d = str(destino or "").strip()
        sufijo = ""
        if "@" in d:
            d, sufijo = d.split("@", 1)
            if sufijo in ("g.us", "lid", "broadcast", "newsletter"):
                return f"{d}@{sufijo}"
        num = "".join(ch for ch in d if ch.isdigit())
        # México: WhatsApp usa 521 + 10 dígitos. Whapi completaba el prefijo solo; WAHA no
        # (error real: "recipient is not on WhatsApp: no LID found for 5541576331").
        if len(num) == 10:
            num = "521" + num
        elif len(num) == 12 and num.startswith("52") and not num.startswith("521"):
            num = "521" + num[2:]
        return num + "@c.us"

    async def _post(self, path: str, payload: dict, timeout: int = 20) -> httpx.Response | None:
        try:
            body = json.dumps(payload, ensure_ascii=True).encode("ascii")
            async with httpx.AsyncClient(timeout=timeout) as c:
                return await c.post(f"{self.base}{path}", content=body, headers=self._headers())
        except Exception as e:
            logger.error(f"[WAHA] Excepción POST {path}: {e}")
            return None

    async def _resolver_lid(self, lid: str) -> str:
        """WhatsApp a veces manda '123@lid' en vez del teléfono. Intenta obtener el número real."""
        if lid in _cache_lids:
            return _cache_lids[lid]
        try:
            async with httpx.AsyncClient(timeout=8) as c:
                r = await c.get(
                    f"{self.base}/api/{self.session}/lids/{lid.replace('@', '%40')}",
                    headers=self._headers(),
                )
                if r.status_code == 200:
                    pn = (r.json() or {}).get("pn") or ""
                    if pn:
                        _cache_lids[lid] = pn
                        return pn
        except Exception as e:
            logger.warning(f"[WAHA] No se pudo resolver LID {lid}: {e}")
        return lid

    async def _nombre_grupo(self, group_id: str) -> str:
        if _limpiar(group_id) in _ids_grupo_interno():
            return os.getenv("GRUPO_INTERNO_NOMBRE", "Taller Interno TS")
        if group_id in _cache_grupos:
            return _cache_grupos[group_id]
        try:
            async with httpx.AsyncClient(timeout=8) as c:
                r = await c.get(
                    f"{self.base}/api/{self.session}/groups/{group_id.replace('@', '%40')}",
                    headers=self._headers(),
                )
                if r.status_code == 200:
                    data = r.json() or {}
                    nombre = data.get("subject") or data.get("name") or (data.get("groupMetadata") or {}).get("subject") or ""
                    if nombre:
                        _cache_grupos[group_id] = nombre
                    return nombre
        except Exception:
            pass
        return ""

    def _url_media(self, url: str) -> str:
        """WAHA puede devolver http://localhost:3000/api/files/... → reescribir a WAHA_URL."""
        if not url:
            return ""
        p = urlparse(url)
        return f"{self.base}{p.path}" + (f"?{p.query}" if p.query else "")

    # ── webhook entrante ─────────────────────────────────────────────────────
    async def parsear_webhook(self, request: Request) -> list[MensajeEntrante]:
        try:
            body = await request.json()
        except Exception as e:
            logger.error(f"[WAHA] JSON inválido en webhook: {e}")
            return []
        if not isinstance(body, dict):
            return []

        evento = body.get("event", "")
        if evento not in ("message", "message.any"):
            return []

        m = body.get("payload") or {}
        from_me = bool(m.get("fromMe"))
        # En mensajes propios el chat es "to"; en entrantes es "from"
        chat = (m.get("to") if from_me else m.get("from")) or ""
        if _es_difusion(chat) or _es_difusion(m.get("from") or ""):
            return []
        es_grupo = chat.endswith("@g.us")

        if chat.endswith("@lid"):
            chat = await self._resolver_lid(chat)

        remitente = ""
        nombre_grupo = ""
        if es_grupo:
            part = m.get("participant") or m.get("author") or ""
            if part.endswith("@lid"):
                part = await self._resolver_lid(part)
            remitente = _limpiar(part)
            nombre_grupo = await self._nombre_grupo(chat)

        # Tipo de mensaje
        media = m.get("media") or {}
        mime = (media.get("mimetype") or "").lower()
        tipo = "text"
        if m.get("hasMedia"):
            if mime.startswith("image/"):
                tipo = "image"
            elif mime.startswith("video/"):
                tipo = "video"
            elif mime.startswith("audio/"):
                tipo = "voice" if "ogg" in mime else "audio"
            else:
                tipo = "document"

        texto = (m.get("body") or "") if tipo == "text" else ""

        msg = MensajeEntranteWaha(
            telefono=_limpiar(chat),
            texto=texto,
            mensaje_id=str(m.get("id", "")),
            es_propio=from_me,
            tipo=tipo,
            es_grupo=es_grupo,
            remitente=remitente,
            nombre_grupo=nombre_grupo,
            chat_id_raw=chat,
            media_url=self._url_media(media.get("url") or "") if tipo in ("image", "video") else "",
            media_mime_type=mime or ("image/jpeg" if tipo == "image" else ""),
            fuente="organico",
        )
        msg.source = str(m.get("source", "") or "")
        return [msg]

    # ── descarga de media (la usa main.py en lugar de vision.descargar_media) ─
    async def descargar_media(self, url: str) -> tuple[bytes, str] | None:
        if not url:
            return None
        try:
            async with httpx.AsyncClient(timeout=30, follow_redirects=True) as c:
                r = await c.get(url, headers={"X-Api-Key": self.api_key} if self.api_key else {})
                if r.status_code == 200:
                    ct = r.headers.get("content-type", "image/jpeg").split(";")[0].strip()
                    return r.content, ct
                logger.warning(f"[WAHA] HTTP {r.status_code} descargando media")
        except Exception as e:
            logger.error(f"[WAHA] Excepción descargando media: {e}")
        return None

    # ── envíos ───────────────────────────────────────────────────────────────
    async def enviar_typing(self, telefono: str) -> None:
        await self._post("/api/startTyping", {"session": self.session, "chatId": self._chat_id(telefono)}, timeout=5)

    async def enviar_mensaje(self, destino: str, mensaje: str, mentions: list[str] | None = None) -> bool:
        partes = partir_mensaje(mensaje)
        if len(partes) > 1:
            ok = True
            for i, parte in enumerate(partes):
                if i:
                    await asyncio.sleep(PAUSA_ENTRE_MENSAJES)
                ok = await self.enviar_mensaje(destino, parte, mentions) and ok
            return ok
        if _es_difusion(destino):
            logger.error(f"[WAHA] BLOQUEADO envio a {destino} (estado/canal)")
            return False
        if not self.base:
            logger.warning("[WAHA] WAHA_URL no configurado — mensaje no enviado")
            return False

        texto = mensaje.encode("utf-8", errors="replace").decode("utf-8") if isinstance(mensaje, str) else str(mensaje)

        if not str(destino).endswith("@g.us"):
            try:
                from agent.horario import ajustar_promesas
                texto = ajustar_promesas(texto)
            except Exception as e:
                logger.error(f"[HORARIO] No se pudo ajustar el mensaje: {e}")

        payload = {"session": self.session, "chatId": self._chat_id(destino), "text": texto}
        if mentions:
            payload["mentions"] = [self._chat_id(x) for x in mentions]

        registrar_envio_bot(destino, texto)  # antes de enviar: el eco llega muy rápido
        r = await self._post("/api/sendText", payload)
        if r is None or r.status_code not in (200, 201):
            logger.error(f"[WAHA] Error enviando a {destino}: {getattr(r, 'status_code', 'sin respuesta')} — {getattr(r, 'text', '')[:200]}")
            return False
        try:
            data = r.json() or {}
            mid = data.get("id")
            if isinstance(mid, dict):
                mid = mid.get("_serialized") or mid.get("id")
            if mid:
                registrar_envio_bot(destino, mensaje_id=str(mid))
        except Exception:
            pass
        logger.info(f"[WAHA] ✅ Mensaje enviado a {destino}")
        return True

    async def _enviar_archivo(self, path: str, destino: str, data: bytes, mime: str, filename: str, caption: str) -> bool:
        if _es_difusion(destino):
            logger.error(f"[WAHA] BLOQUEADO envio a {destino} (estado/canal)")
            return False
        payload = {
            "session": self.session,
            "chatId": self._chat_id(destino),
            "file": {"mimetype": mime, "filename": filename, "data": base64.standard_b64encode(data).decode("ascii")},
            "caption": caption,
        }
        r = await self._post(path, payload, timeout=60)
        if r is None or r.status_code not in (200, 201):
            logger.error(
                f"[WAHA] Error {path} a {destino}: {getattr(r, 'status_code', 'sin respuesta')} — "
                f"{getattr(r, 'text', '')[:200]} (en WAHA Core el envío de archivos puede no estar disponible)"
            )
            return False
        logger.info(f"[WAHA] ✅ {filename} enviado a {destino}")
        return True

    async def enviar_imagen_bytes(self, destino: str, imagen_bytes: bytes, mime_type: str = "image/jpeg", caption: str = "") -> bool:
        return await self._enviar_archivo("/api/sendImage", destino, imagen_bytes, mime_type, "imagen.jpg", caption)

    async def enviar_documento_bytes(self, destino: str, documento_bytes: bytes, filename: str = "documento.pdf",
                                     caption: str = "", mime_type: str = "application/pdf") -> bool:
        return await self._enviar_archivo("/api/sendFile", destino, documento_bytes, mime_type, filename, caption)
