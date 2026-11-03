# agent/providers/base.py — Clase base para proveedores de WhatsApp
# Generado por AgentKit

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from fastapi import Request

# Una respuesta puede mandarse en varios mensajes de WhatsApp: el texto se separa con este
# marcador (ej. cotización de iPhone: 1) precios, 2) valor del servicio). Cada proveedor lo parte.
SEPARADOR_MENSAJES = "[[SIGUIENTE]]"
PAUSA_ENTRE_MENSAJES = 2  # segundos


def partir_mensaje(texto) -> list[str]:
    if not isinstance(texto, str) or SEPARADOR_MENSAJES not in texto:
        return [texto]
    return [p.strip() for p in texto.split(SEPARADOR_MENSAJES) if p.strip()]


def unir_mensaje(texto: str) -> str:
    """Versión de una sola pieza (historial, logs, Messenger)."""
    return "\n\n".join(partir_mensaje(texto)) if isinstance(texto, str) else texto


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
    media_url: str = ""              # URL directa de descarga (imágenes/videos)
    media_thumbnail_b64: str = ""    # Thumbnail JPEG en base64 (videos de Whapi)
    media_id: str = ""               # ID de media de Whapi (fallback si URL vacía)
    media_mime_type: str = ""        # MIME type declarado por el proveedor
    canal: str = "whatsapp"          # whatsapp | messenger | instagram


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
