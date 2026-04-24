# agent/providers/whapi.py — Adaptador para Whapi.cloud
# Generado por AgentKit

import os
import logging
import httpx
from dataclasses import dataclass
from fastapi import Request
from agent.providers.base import ProveedorWhatsApp, MensajeEntrante

logger = logging.getLogger("agentkit")

TIPOS_MEDIA = {"image", "video", "audio", "document", "sticker", "voice", "gif"}


@dataclass
class MensajeEntranteWhapi(MensajeEntrante):
    """Extiende MensajeEntrante con datos de referral de Facebook Ads."""
    fuente: str = "desconocido"
    fuente_detalle: str = ""


class ProveedorWhapi(ProveedorWhatsApp):

    def __init__(self):
        self.token = os.getenv("WHAPI_TOKEN")
        self.url_envio = "https://gate.whapi.cloud/messages/text"

    def _detectar_fuente(self, msg: dict) -> tuple[str, str]:
        referral = msg.get("referral") or msg.get("ad") or {}
        if not referral:
            return "organico", ""
        source_type = referral.get("source_type", "").lower()
        source_url = referral.get("source_url", "")
        headline = referral.get("headline", "")
        ctwa_clid = referral.get("ctwa_clid", "")
        if source_type == "ad" or ctwa_clid:
            fuente = "instagram_ad" if "instagram" in source_url.lower() else "facebook_ad"
            detalle = headline or source_url or ctwa_clid
            return fuente, detalle[:200]
        return "organico", ""

    async def parsear_webhook(self, request: Request) -> list[MensajeEntrante]:
        body = await request.json()
        mensajes = []
        for msg in body.get("messages", []):
            chat_id = msg.get("chat_id", "")
            es_grupo = chat_id.endswith("@g.us")
            telefono = (
                chat_id
                .replace("@s.whatsapp.net", "")
                .replace("@c.us", "")
                .replace("@g.us", "")
            )
            tipo = msg.get("type", "text")
            texto = msg.get("text", {}).get("body", "") if tipo == "text" else ""
            fuente, detalle = self._detectar_fuente(msg)
            mensajes.append(MensajeEntranteWhapi(
                telefono=telefono or chat_id,
                texto=texto,
                mensaje_id=msg.get("id", ""),
                es_propio=msg.get("from_me", False),
                tipo=tipo,
                es_grupo=es_grupo,
                fuente=fuente,
                fuente_detalle=detalle,
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

    async def enviar_mensaje(self, telefono: str, mensaje: str) -> bool:
        if not self.token:
            logger.warning("WHAPI_TOKEN no configurado")
            return False
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
        }
        async with httpx.AsyncClient() as client:
            r = await client.post(
                self.url_envio,
                json={"to": telefono, "body": mensaje},
                headers=headers,
            )
            if r.status_code != 200:
                logger.error(f"Error Whapi: {r.status_code} — {r.text}")
            return r.status_code == 200
