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

    if proveedor == "whapi":
        from agent.providers.whapi import ProveedorWhapi
        return ProveedorWhapi()
    elif proveedor == "meta_inbox":
        from agent.providers.meta_inbox import ProveedorMetaInbox
        return ProveedorMetaInbox()
    elif proveedor == "meta":
        from agent.providers.meta import ProveedorMeta
        return ProveedorMeta()
    elif proveedor == "twilio":
        from agent.providers.twilio import ProveedorTwilio
        return ProveedorTwilio()
    else:
        raise ValueError(f"Proveedor no soportado: {proveedor}. Usa: whapi, meta_inbox, meta, o twilio")
