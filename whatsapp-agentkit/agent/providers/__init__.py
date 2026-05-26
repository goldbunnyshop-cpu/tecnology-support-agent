# agent/providers/__init__.py — Factory de proveedores
# Generado por AgentKit — VERSIÓN SIMPLIFICADA: Solo Whapi.cloud

import os
from agent.providers.base import ProveedorWhatsApp


def obtener_proveedor() -> ProveedorWhatsApp:
    """
    Retorna el proveedor Whapi.cloud.

    Para cambiarlo en el futuro, actualiza WHATSAPP_PROVIDER en .env
    """
    from agent.providers.whapi import ProveedorWhapi
    return ProveedorWhapi()
