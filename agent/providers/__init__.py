# agent/providers/__init__.py — Factory de proveedores
# Generado por AgentKit

import os
from agent.providers.base import ProveedorWhatsApp


def obtener_proveedor() -> ProveedorWhatsApp:
    """Retorna el proveedor de WhatsApp configurado en .env."""
    proveedor = os.getenv("WHATSAPP_PROVIDER", "whapi").lower()

    if proveedor == "whapi":
        from agent.providers.whapi import ProveedorWhapi
        return ProveedorWhapi()
    if proveedor == "messenger":
        from agent.providers.messenger import ProveedorMessenger
        return ProveedorMessenger()
    if proveedor in {"meta_inbox", "meta"}:
        from agent.providers.meta_inbox import ProveedorMetaInbox
        return ProveedorMetaInbox()
    else:
        raise ValueError(
            f"Proveedor no soportado: {proveedor}. "
            "Usa uno de: whapi, messenger, meta_inbox (o meta)."
        )
