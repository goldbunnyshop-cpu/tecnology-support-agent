# agent/providers/messenger.py — Adaptador para Meta Messenger
# Generado por AgentKit

import hashlib
import hmac
import logging
import os

import httpx
from fastapi import Request

from agent.providers.base import MensajeEntrante, ProveedorWhatsApp

logger = logging.getLogger("agentkit")


class ProveedorMessenger(ProveedorWhatsApp):
    """Proveedor para Facebook Messenger (Meta Graph API)."""

    API_VERSION = "v21.0"

    def __init__(self):
        self.page_access_token = os.getenv("META_PAGE_ACCESS_TOKEN", "")
        self.page_id           = os.getenv("META_PAGE_ID", "")
        self.app_secret        = os.getenv("META_APP_SECRET", "")
        self.verify_token      = os.getenv("META_MESSENGER_VERIFY_TOKEN", "ts-messenger-2026")

    # ── Verificación GET del webhook ──────────────────────────────────────────

    async def validar_webhook(self, request: Request) -> str | None:
        params    = request.query_params
        mode      = params.get("hub.mode")
        token     = params.get("hub.verify_token")
        challenge = params.get("hub.challenge", "")
        if mode == "subscribe" and token == self.verify_token:
            logger.info("[MESSENGER] Webhook verificado por Meta")
            return challenge
        logger.warning(
            f"[MESSENGER] Verificación fallida — mode='{mode}' token='{token}' "
            f"esperado='{self.verify_token}'"
        )
        return None

    # ── Parseo de mensajes entrantes ─────────────────────────────────────────

    async def parsear_webhook(self, request: Request) -> list[MensajeEntrante]:
        body = await request.json()
        if body.get("object") != "page":
            return []

        mensajes: list[MensajeEntrante] = []
        for entry in body.get("entry", []):
            for evento in entry.get("messaging", []):
                sender_id = evento.get("sender", {}).get("id", "")
                page_id   = evento.get("recipient", {}).get("id", "")

                # Ignorar mensajes que envía la propia página
                if sender_id == page_id or sender_id == self.page_id:
                    continue

                msg = evento.get("message", {})
                if not msg or msg.get("is_echo"):
                    continue

                texto     = msg.get("text", "") or ""
                mid       = msg.get("mid", "")

                # Prefijo "fb_" para distinguir de conversaciones WhatsApp en BD
                telefono = f"fb_{sender_id}"

                mensajes.append(MensajeEntrante(
                    telefono   = telefono,
                    texto      = texto,
                    mensaje_id = mid,
                    es_propio  = False,
                    tipo       = "text",
                ))
                logger.info(f"[MESSENGER] Mensaje de {sender_id}: {texto[:60]}")

        return mensajes

    # ── Envío de mensajes ────────────────────────────────────────────────────

    async def enviar_mensaje(self, destino: str, mensaje: str) -> bool:
        """
        destino puede ser "fb_PSID" (prefijado) o el PSID directo.
        """
        if not self.page_access_token:
            logger.warning("[MESSENGER] META_PAGE_ACCESS_TOKEN no configurado")
            return False

        psid = destino.removeprefix("fb_")
        url  = f"https://graph.facebook.com/{self.API_VERSION}/me/messages"

        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.post(
                url,
                params={"access_token": self.page_access_token},
                json={
                    "recipient": {"id": psid},
                    "message":   {"text": mensaje},
                    "messaging_type": "RESPONSE",
                },
            )
        if r.status_code == 200:
            logger.info(f"[MESSENGER] ✅ Enviado a {psid}")
            return True
        logger.error(f"[MESSENGER] ❌ Error {r.status_code}: {r.text[:200]}")
        return False

    # ── Verificación de firma X-Hub-Signature-256 ────────────────────────────

    def verificar_firma(self, payload: bytes, signature: str) -> bool:
        """Valida que el webhook viene de Meta (opcional pero recomendado)."""
        if not self.app_secret or not signature:
            return True  # permisivo si no está configurado
        expected = "sha256=" + hmac.new(
            self.app_secret.encode(), payload, hashlib.sha256
        ).hexdigest()
        return hmac.compare_digest(expected, signature)
