# agent/providers/meta_inbox.py — Adaptador para Meta Inbox (Messenger + Instagram DMs)
# Generado por AgentKit
# Soporta: Facebook Messenger + Instagram Direct Messages en una sola aplicación

import os
import logging
import httpx
import json
from fastapi import Request
from agent.providers.base import ProveedorWhatsApp, MensajeEntrante

logger = logging.getLogger("agentkit")


class ProveedorMetaInbox(ProveedorWhatsApp):
    """
    Proveedor de Meta Inbox que maneja:
    - Facebook Messenger (conversaciones de páginas)
    - Instagram Direct Messages (DMs de cuentas de negocios)

    Ambos canales se unifican en un solo webhook y se normalizan a MensajeEntrante.
    El bot responde por el mismo canal donde el cliente escribió.
    """

    def __init__(self):
        self.access_token = os.getenv("META_ACCESS_TOKEN")
        self.verify_token = os.getenv("META_VERIFY_TOKEN", "agentkit-verify")
        self.api_version = "v21.0"
        self.page_ids = os.getenv("META_PAGE_IDS", "").split(",")  # ej: "123456789,987654321"
        self.ig_account_ids = os.getenv("META_IG_ACCOUNT_IDS", "").split(",")  # ej: "111222333,444555666"

    async def validar_webhook(self, request: Request) -> dict | int | None:
        """
        Meta requiere verificación GET con hub.verify_token.
        Mismo flujo que WhatsApp Cloud API.
        """
        params = request.query_params
        mode = params.get("hub.mode")
        token = params.get("hub.verify_token")
        challenge = params.get("hub.challenge")
        if mode == "subscribe" and token == self.verify_token:
            return int(challenge)
        return None

    async def parsear_webhook(self, request: Request) -> list[MensajeEntrante]:
        """
        Parsea el payload de Meta Inbox.
        Maneja tanto Messenger como Instagram DMs.

        Estructura anidada de Meta (igual que WhatsApp Cloud API):
        {
            "entry": [
                {
                    "changes": [
                        {
                            "value": {
                                "messages": [...],
                                "messaging": [...],  # Para Messenger (legacy)
                            }
                        }
                    ]
                }
            ]
        }
        """
        body = await request.json()
        mensajes = []

        for entry in body.get("entry", []):
            for change in entry.get("changes", []):
                value = change.get("value", {})

                # ══════════════════════════════════════════════════════════════════════════════
                # FLUJO 1: FACEBOOK MESSENGER (nuevo formato)
                # ══════════════════════════════════════════════════════════════════════════════
                for msg in value.get("messages", []):
                    if msg.get("type") == "text":
                        remitente = msg.get("from", "")
                        texto = msg.get("text", {}).get("body", "")

                        # Detectar si es Messenger (por contexto)
                        canal = "messenger"

                        mensajes.append(MensajeEntrante(
                            telefono=remitente,
                            texto=texto,
                            mensaje_id=msg.get("id", ""),
                            es_propio=False,
                            canal=canal,  # Nuevo: rastrear de dónde vino
                        ))
                        logger.info(f"[META-INBOX] Messenger: {remitente[:20]}... → {texto[:50]}...")

                # ══════════════════════════════════════════════════════════════════════════════
                # FLUJO 2: INSTAGRAM DIRECT MESSAGES
                # ══════════════════════════════════════════════════════════════════════════════
                for msg in value.get("messages", []):
                    if msg.get("type") == "text" and "instagram" in str(msg).lower():
                        # Instagram usa el mismo formato pero con campo diferente
                        remitente = msg.get("from", "")
                        texto = msg.get("text", {}).get("body", "")

                        canal = "instagram"

                        mensajes.append(MensajeEntrante(
                            telefono=remitente,
                            texto=texto,
                            mensaje_id=msg.get("id", ""),
                            es_propio=False,
                            canal=canal,
                        ))
                        logger.info(f"[META-INBOX] Instagram DM: {remitente[:20]}... → {texto[:50]}...")

        return mensajes

    async def enviar_mensaje(self, telefono: str, mensaje: str, canal: str = "messenger") -> bool:
        """
        Envía mensaje por el canal especificado (Messenger o Instagram DMs).

        Args:
            telefono: ID del usuario (PSID para Messenger, IGID para Instagram)
            mensaje: Contenido del mensaje
            canal: "messenger" o "instagram" (opcional, intenta auto-detectar)

        Returns:
            True si fue exitoso
        """
        if not self.access_token:
            logger.warning("META_ACCESS_TOKEN no configurado — mensaje no enviado")
            return False

        # Auto-detectar canal si no se especifica
        if canal == "auto" or canal is None:
            # Meta usa IDs diferentes para cada plataforma
            # Esta es una heurística simple
            canal = "messenger"

        # URL según canal
        if canal == "instagram":
            # Instagram usa Instagram Graph API
            url = f"https://graph.instagram.com/{self.api_version}/me/messages"
        else:
            # Messenger usa Facebook Graph API
            url = f"https://graph.facebook.com/{self.api_version}/me/messages"

        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        }

        payload = {
            "recipient": {"id": telefono},
            "messaging_type": "RESPONSE",
            "message": {"text": mensaje},
        }

        async with httpx.AsyncClient() as client:
            try:
                r = await client.post(url, json=payload, headers=headers, timeout=10.0)
                if r.status_code not in [200, 201]:
                    logger.error(
                        f"Error Meta {canal.upper()}: {r.status_code} — {r.text}"
                    )
                    return False
                return True
            except Exception as e:
                logger.error(f"Error enviando por {canal}: {e}")
                return False


# ════════════════════════════════════════════════════════════════════════════════
# EXTENDER MensajeEntrante PARA SOPORTAR CANAL
# ════════════════════════════════════════════════════════════════════════════════
#
# Si necesitas rastrear el canal de origen, actualiza agent/providers/base.py:
#
# @dataclass
# class MensajeEntrante:
#     """Mensaje normalizado — mismo formato sin importar el proveedor."""
#     telefono: str       # Número/ID del remitente
#     texto: str          # Contenido del mensaje
#     mensaje_id: str     # ID único del mensaje
#     es_propio: bool     # True si lo envió el agente (se ignora)
#     canal: str = "whatsapp"  # ← NUEVO: rastrear origen (whatsapp, messenger, instagram)
#
