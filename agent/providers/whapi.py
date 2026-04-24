# agent/providers/whapi.py — Adaptador para Whapi.cloud
# Generado por AgentKit

import os
import logging
import httpx
from dataclasses import dataclass
from fastapi import Request
from agent.providers.base import ProveedorWhatsApp, MensajeEntrante

logger = logging.getLogger("agentkit")

# Cache de nombres de grupos (chat_id → nombre)
_cache_grupos: dict[str, str] = {}


@dataclass
class MensajeEntranteWhapi(MensajeEntrante):
    fuente: str = "desconocido"
    fuente_detalle: str = ""


class ProveedorWhapi(ProveedorWhatsApp):

    def __init__(self):
        self.token = os.getenv("WHAPI_TOKEN")
        self.url_envio = "https://gate.whapi.cloud/messages/text"

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
        }

    async def _obtener_nombre_grupo(self, chat_id: str) -> str:
        """Consulta el nombre del grupo vía API con cache."""
        if chat_id in _cache_grupos:
            return _cache_grupos[chat_id]
        try:
            async with httpx.AsyncClient(timeout=8) as client:
                r = await client.get(
                    f"https://gate.whapi.cloud/groups/{chat_id}",
                    headers={"Authorization": f"Bearer {self.token}"},
                )
                if r.status_code == 200:
                    nombre = r.json().get("name", "") or r.json().get("subject", "")
                    if nombre:
                        _cache_grupos[chat_id] = nombre
                    return nombre
        except Exception:
            pass
        return ""

    def _detectar_fuente(self, msg: dict) -> tuple[str, str]:
        referral = msg.get("referral") or msg.get("ad") or {}
        if not referral:
            return "organico", ""
        source_type = referral.get("source_type", "").lower()
        source_url  = referral.get("source_url", "")
        headline    = referral.get("headline", "")
        ctwa_clid   = referral.get("ctwa_clid", "")
        if source_type == "ad" or ctwa_clid:
            fuente = "instagram_ad" if "instagram" in source_url.lower() else "facebook_ad"
            return fuente, (headline or source_url or ctwa_clid)[:200]
        return "organico", ""

    async def parsear_webhook(self, request: Request) -> list[MensajeEntrante]:
        body = await request.json()
        mensajes = []

        for msg in body.get("messages", []):
            chat_id  = msg.get("chat_id", "")
            from_raw = msg.get("from", chat_id)  # sender en grupos
            es_grupo = chat_id.endswith("@g.us")

            # Limpiar teléfonos
            def _limpiar(s: str) -> str:
                return s.replace("@s.whatsapp.net", "").replace("@c.us", "").replace("@g.us", "")

            if es_grupo:
                remitente = _limpiar(from_raw)
                telefono  = _limpiar(chat_id)   # group_id sin sufijo (para identificación)
                chat_id_raw = chat_id            # con @g.us (para responder al grupo)
                # Intentar nombre del grupo desde el payload primero
                nombre_grupo = (
                    msg.get("chat", {}).get("name", "")
                    or msg.get("chat", {}).get("subject", "")
                )
                if not nombre_grupo:
                    nombre_grupo = await self._obtener_nombre_grupo(chat_id)
            else:
                remitente    = ""
                telefono     = _limpiar(chat_id)
                chat_id_raw  = chat_id
                nombre_grupo = ""

            tipo  = msg.get("type", "text")
            texto = msg.get("text", {}).get("body", "") if tipo == "text" else ""
            fuente, detalle = self._detectar_fuente(msg)

            mensajes.append(MensajeEntranteWhapi(
                telefono     = telefono or _limpiar(chat_id),
                texto        = texto,
                mensaje_id   = msg.get("id", ""),
                es_propio    = msg.get("from_me", False),
                tipo         = tipo,
                es_grupo     = es_grupo,
                remitente    = remitente,
                nombre_grupo = nombre_grupo,
                chat_id_raw  = chat_id_raw,
                fuente       = fuente,
                fuente_detalle = detalle,
            ))

        return mensajes

    async def enviar_typing(self, telefono: str) -> None:
        if not self.token:
            return
        chat_id = telefono if "@" in telefono else f"{telefono}@s.whatsapp.net"
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                await client.post(
                    f"https://gate.whapi.cloud/chats/{chat_id}/typing",
                    headers={"Authorization": f"Bearer {self.token}"},
                )
        except Exception:
            pass

    async def enviar_mensaje(self, destino: str, mensaje: str) -> bool:
        """Envía a un número o a un grupo (group_id con @g.us)."""
        if not self.token:
            logger.warning("WHAPI_TOKEN no configurado")
            return False
        async with httpx.AsyncClient() as client:
            r = await client.post(
                self.url_envio,
                json={"to": destino, "body": mensaje},
                headers=self._headers(),
            )
            if r.status_code != 200:
                logger.error(f"Error Whapi: {r.status_code} — {r.text}")
            return r.status_code == 200
