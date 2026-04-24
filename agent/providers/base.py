# agent/providers/base.py — Clase base para proveedores de WhatsApp
# Generado por AgentKit

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from fastapi import Request


@dataclass
class MensajeEntrante:
    """Mensaje normalizado — mismo formato sin importar el proveedor."""
    telefono: str
    texto: str
    mensaje_id: str
    es_propio: bool
    tipo: str = "text"      # text | image | video | audio | document | sticker | voice
    es_grupo: bool = False  # True si viene de un grupo de WhatsApp


class ProveedorWhatsApp(ABC):

    @abstractmethod
    async def parsear_webhook(self, request: Request) -> list[MensajeEntrante]:
        ...

    @abstractmethod
    async def enviar_mensaje(self, telefono: str, mensaje: str) -> bool:
        ...

    async def validar_webhook(self, request: Request) -> dict | int | None:
        return None

    async def enviar_typing(self, telefono: str) -> None:
        pass
