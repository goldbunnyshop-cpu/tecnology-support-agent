# agent/providers/__init__.py — Factory de proveedores
# Generado por AgentKit

import os
from agent.providers.base import ProveedorWhatsApp


def obtener_proveedor() -> ProveedorWhatsApp:
    """
    Retorna el proveedor configurado en .env.

    Opciones:
    - whapi: Solo WhatsApp (Whapi.cloud)
    - meta_inbox: Meta Inbox (Facebook Messenger + Instagram DMs)
    - meta: Meta Cloud API (WhatsApp oficial)
    - twilio: Twilio WhatsApp
    """
    proveedor = os.getenv("WHATSAPP_PROVIDER", "whapi").lower()

    if proveedor =