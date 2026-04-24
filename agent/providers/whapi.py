# agent/providers/whapi.py — Adaptador para Whapi.cloud
# Generado por AgentKit

import os
import logging
import httpx
from dataclasses import dataclass, field
from fastapi import Request
from agent.providers.base import ProveedorWhatsApp, MensajeEntrante

logger = logging.getLogger("agentkit")


@dataclass
class MensajeEntranteWhapi(MensajeEntrante):
    """Extiende MensajeEntrante con datos de referral de Facebook Ads."""
    fuente: str = "desconocido"
    fuente_detalle: str = ""


class ProveedorWhapi(ProveedorWhatsApp):
    """Proveedor de WhatsApp usando Whapi.cloud (REST API simple)."""

    def __init__(self):
        self.token = os.getenv("WHAPI_TOKEN")
        self.url_envio = "https://gate.whapi.cloud/messages/text"

    def _detectar_fuente(self, msg: dict) -> tuple[str, str]:
        """
        Detecta si el mensaje viene de un anuncio de Facebook/Instagram.
        Whapi incluye el campo 'referral' cuando el usuario clickea un
        anuncio de Click-to-WhatsApp.
        """
        referral = msg.get("referral") or msg.get("ad") or {}
        if not referral:
            return "organico", ""

        source_type = referral.get("source_type", "").lower()
        source_url = referral.get("source_url", "")
        headline = referral.get("headline", "")
        ctwa_clid = referral.get("ctwa_clid", "")

        if source_type == "ad" or ctwa_clid:
            # Determinar si es Facebook o Instagram por la URL
            if "instagram" in source_url.lower():
                fuente = "instagram_ad"
            else:
                fuente = "facebook_ad"
            detalle = headline or source_url or ctwa_clid
            return fuente, detalle[:200]

        return "organico", ""

    async def parsear_webhook(self, request: Request) -> list[MensajeEntrante]:
        """Parsea el payload de Whapi.cloud, detectando fuente de anuncios."""
        body = await request.json()
        mensajes = []
        for msg in body.get("messages", []):
            fuente, detalle = self._detectar_fuente(msg)
            chat_id = msg.get("chat_id", "")
            # Limpiar el chat_id: remover sufijo @s.whatsapp.net si viene así
            telefono = chat_id.replace("@s.whatsapp.net", "").replace("@c.us", "")
            mensajes.append(MensajeEntranteWhapi(
                telefono=telefono or chat_id,
                texto=msg.get("text", {}).get("body", ""),
                mensaje_id=msg.get("id", ""),
                es_propio=msg.get("from_me", False),
                fuente=fuente,
                fuente_detalle=detalle,
            ))
        return mensajes

    async def enviar_mensaje(self, telefono: str, mensaje: str) -> bool:
        """Envía mensaje via Whapi.cloud."""
        if not self.token:
            logger.warning("WHAPI_TOKEN no configurado — mensaje no enviado")
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
