# agent/vision.py — Análisis visual de imágenes y videos con Claude Vision
# Generado por AgentKit

import base64
import logging
import os
import httpx
from anthropic import AsyncAnthropic
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger("agentkit")

client = AsyncAnthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

PROMPT_VISION = """Eres el técnico experto de Tecnology Support, un taller de reparación de dispositivos electrónicos.
Analiza la imagen y responde SOLO con un objeto JSON sin texto adicional:

{
  "dispositivo": "nombre del dispositivo (ej: iPhone 12, PS4, Samsung Galaxy S21, laptop HP, etc.) o 'No identificado' si no puedes determinarlo",
  "dano_visible": "descripción concisa del daño o problema visual detectado, o 'No se aprecia daño visible' si todo parece bien",
  "severidad": "leve | moderada | grave | no_determinable",
  "servicio_sugerido": "nombre del servicio más probable (ej: cambio de pantalla, limpieza interna, cambio de batería, reparación de puerto de carga, etc.) o 'Diagnóstico físico requerido'",
  "rango_precio": "rango aproximado en MXN (ej: $500-$800) o 'Por cotizar' si no puedes estimarlo",
  "nota_tecnica": "observación técnica breve para el equipo interno, máximo 1 oración",
  "puede_diagnosticar": true
}

Si la imagen no muestra ningún dispositivo electrónico o es completamente ilegible, responde:
{
  "puede_diagnosticar": false,
  "motivo": "breve explicación"
}

Responde SOLO el JSON, sin markdown, sin explicaciones adicionales."""


async def descargar_media(url: str, token: str) -> tuple[bytes, str] | None:
    """Descarga media de Whapi usando el token de autorización."""
    try:
        headers = {"Authorization": f"Bearer {token}"}
        async with httpx.AsyncClient(timeout=20) as client_http:
            r = await client_http.get(url, headers=headers, follow_redirects=True)
            if r.status_code != 200:
                logger.warning(f"Error descargando media {url}: {r.status_code}")
                return None
            content_type = r.headers.get("content-type", "image/jpeg").split(";")[0].strip()
            return r.content, content_type
    except Exception as e:
        logger.error(f"Excepción descargando media: {e}")
        return None


def _mime_a_tipo_anthropic(mime_type: str) -> str:
    """Mapea MIME type al valor que acepta Anthropic."""
    tabla = {
        "image/jpeg": "image/jpeg",
        "image/jpg":  "image/jpeg",
        "image/png":  "image/png",
        "image/gif":  "image/gif",
        "image/webp": "image/webp",
    }
    return tabla.get(mime_type.lower(), "image/jpeg")


async def _llamar_vision(imagen_b64: str, media_type: str) -> dict:
    """Llama a Claude Vision con la imagen en base64 y retorna el dict parseado."""
    import json

    try:
        response = await client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=400,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": media_type,
                                "data": imagen_b64,
                            },
                        },
                        {
                            "type": "text",
                            "text": PROMPT_VISION,
                        },
                    ],
                }
            ],
        )
        raw = response.content[0].text.strip()
        # Limpiar markdown si Claude lo agrega por error
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        return json.loads(raw.strip())
    except Exception as e:
        logger.error(f"Error en Claude Vision: {e}")
        return {"puede_diagnosticar": False, "motivo": "Error interno de análisis"}


async def analizar_imagen_bytes(imagen_bytes: bytes, mime_type: str) -> dict:
    """Analiza bytes de imagen con Claude Vision."""
    imagen_b64 = base64.standard_b64encode(imagen_bytes).decode("utf-8")
    media_type = _mime_a_tipo_anthropic(mime_type)
    return await _llamar_vision(imagen_b64, media_type)


async def analizar_thumbnail_b64(thumbnail_b64: str) -> dict:
    """Analiza el thumbnail JPEG de un video (ya en base64 desde Whapi)."""
    return await _llamar_vision(thumbnail_b64, "image/jpeg")


def construir_respuesta_cliente(analisis: dict, tipo_media: str, asesor: str = "Sofia") -> str:
    """Genera el mensaje al cliente basado en el análisis de visión."""
    if not analisis.get("puede_diagnosticar", True):
        if tipo_media == "video":
            return (
                "Recibí tu video \U0001f3a5 Vi el contenido pero necesito más contexto para diagnosticar. "
                "¿Puedes describirme qué falla presenta tu equipo? "
                "Por ejemplo: no enciende, se congela, hace ruido extraño, etc."
            )
        return (
            "Recibí tu imagen \U0001f4f8 pero no pude identificar el dispositivo con claridad. "
            "¿Puedes tomar otra foto con mejor iluminación o más cerca del problema? "
            "¡Así podré darte un diagnóstico más preciso!"
        )

    dispositivo = analisis.get("dispositivo", "tu equipo")
    dano = analisis.get("dano_visible", "")
    servicio = analisis.get("servicio_sugerido", "Diagnóstico físico requerido")
    precio = analisis.get("rango_precio", "Por cotizar")
    severidad = analisis.get("severidad", "no_determinable")

    if tipo_media == "video" and severidad == "no_determinable":
        return (
            f"Vi tu video \U0001f3a5 Pude revisar el estado visual de tu {dispositivo}. "
            f"Para un diagnóstico preciso de la falla funcional, necesitamos revisarlo físicamente en el taller. "
            f"¿Te gustaría traerlo a nuestro módulo? Hacemos el diagnóstico sin costo."
        )

    intro = "Vi la foto de tu equipo \U0001f4f8" if tipo_media == "image" else "Revisé tu video \U0001f3a5"

    if dano and dano != "No se aprecia daño visible":
        descripcion_dano = f"Parece que tienes {dano} en tu {dispositivo}."
    else:
        descripcion_dano = f"Revisé tu {dispositivo} y no aprecio daño físico visible."

    if servicio == "Diagnóstico físico requerido":
        cierre = (
            "Para confirmarlo necesitamos revisarlo en el taller. "
            "El diagnóstico es sin costo. ¿Te gustaría traerlo?"
        )
        return f"{intro} {descripcion_dano} {cierre}"

    return (
        f"{intro} {descripcion_dano} "
        f"Basándonos en lo que vemos, el servicio que necesitas es *{servicio}* "
        f"con un costo aproximado de *{precio} MXN*. "
        f"Este es un diagnóstico preliminar — el precio exacto se confirma cuando lo revisamos físicamente. "
        f"¿Te gustaría traerlo a nuestro módulo?"
    )
