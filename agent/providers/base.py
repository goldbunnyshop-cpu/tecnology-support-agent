# agent/providers/base.py — Clase base para proveedores de WhatsApp
# Generado por AgentKit

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from fastapi import Request


@dataclass
class MensajeEntrante:
    """Mensaje normalizado — mismo formato sin importar el proveedor."""
    telefono: str       # Chat al que responder (individual: sender, grupo: group_id sin sufijo)
    texto: str
    mensaje_id: str
    es_propio: bool
    tipo: str = "text"          # text | image | video | audio | document | sticker | voice
    es_grupo: bool = False
    remitente: str = ""         # Sender real (útil en grupos donde telefono es el group_id)
    nombre_grupo: str = ""      # Nombre del grupo si es_grupo
    chat_id_raw: str = ""       # chat_id original con sufijo (@s.whatsapp.net / @g.us)


class ProveedorWhatsApp(ABC):

    @abstractmethod
    async def parsear_webhook(self, request: Request) -> list[MensajeEntrante]:
        ...

    @abstractmethod
    async def enviar_mensaje(self, destino: str, mensaje: str) -> bool:
        """Envía a un número individual o a un group_id con sufijo @g.us."""
        ...

    async def validar_webhook(self, request: Request) -> dict | int | None:
        return None

    async def enviar_typing(self, telefono: str) -> None:
        pass
