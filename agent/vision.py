# agent/vision.py — Análisis visual de imágenes y videos con Claude Vision
# Generado por AgentKit

import base64
import json
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
  "refaccion_ml": "término de búsqueda para la refacción principal en MercadoLibre México (ej: 'pantalla iPhone 12 original', 'batería Samsung S21', 'ventilador PS4 CUH-1200'). Cadena vacía si el servicio es mano de obra sin refacción (ej: limpieza, diagnóstico)",
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
    tabla = {
        "image/jpeg": "image/jpeg",
        "image/jpg":  "image/jpeg",
        "image/png":  "image/png",
        "image/gif":  "image/gif",
        "image/webp": "image/webp",
    }
    return tabla.get(mime_type.lower(), "image/jpeg")


async def _buscar_precio_minimo_ml(termino: str) -> float | None:
    """Consulta la API pública de MercadoLibre México y retorna el precio mínimo encontrado."""
    if not termino:
        return None
    try:
        async with httpx.AsyncClient(timeout=10) as c:
            r = await c.get(
                "https://api.mercadolibre.com/sites/MLM/search",
                params={"q": termino, "limit": 20},
            )
            if r.status_code != 200:
                logger.warning(f"ML API {r.status_code} para '{termino}'")
                return None
            items = r.json().get("results", [])
            # Filtrar precios razonables (evitar accesorios de $10 o dispositivos completos de $50k)
            precios = [
                item["price"]
                for item in items
                if 80 <= item.get("price", 0) <= 15_000
            ]
            if not precios:
                return None
            precio_min = min(precios)
            logger.info(f"ML precio mínimo '{termino}': ${precio_min:.0f}")
            return precio_min
    except Exception as e:
        logger.warning(f"Error consultando ML: {e}")
        return None


def _formatear_precio(valor: float) -> str:
    """Redondea al múltiplo de 50 más cercano y formatea con comas."""
    redondeado = round(valor / 50) * 50
    return f"${redondeado:,.0f}"


async def _llamar_vision(imagen_b64: str, media_type: str) -> dict:
    """Llama a Claude Vision con la imagen en base64 y retorna el dict parseado."""
    try:
        response = await client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=450,
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
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        return json.loads(raw.strip())
    except Exception as e:
        logger.error(f"Error en Claude Vision: {e}")
        return {"puede_diagnosticar": False, "motivo": "Error interno de análisis"}


async def _enriquecer_con_precio_ml(analisis: dict) -> dict:
    """Busca la refacción en ML y calcula el precio de servicio (mínimo ML × 3)."""
    if not analisis.get("puede_diagnosticar", False):
        return analisis

    termino = analisis.get("refaccion_ml", "").strip()
    if not termino:
        analisis["precio_estimado"] = "Por cotizar"
        return analisis

    precio_min = await _buscar_precio_minimo_ml(termino)
    if precio_min:
        precio_servicio = precio_min * 3
        analisis["precio_estimado"] = _formatear_precio(precio_servicio)
        logger.info(f"Precio estimado calculado: {analisis['precio_estimado']} (refacción ${precio_min:.0f} × 3)")
    else:
        analisis["precio_estimado"] = "Por cotizar"

    return analisis


async def analizar_imagen_bytes(imagen_bytes: bytes, mime_type: str) -> dict:
    """Analiza bytes de imagen con Claude Vision y enriquece con precio de ML."""
    imagen_b64 = base64.standard_b64encode(imagen_bytes).decode("utf-8")
    media_type = _mime_a_tipo_anthropic(mime_type)
    analisis = await _llamar_vision(imagen_b64, media_type)
    return await _enriquecer_con_precio_ml(analisis)


async def analizar_thumbnail_b64(thumbnail_b64: str) -> dict:
    """Analiza el thumbnail JPEG de un video (ya en base64 desde Whapi)."""
    analisis = await _llamar_vision(thumbnail_b64, "image/jpeg")
    return await _enriquecer_con_precio_ml(analisis)


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
    precio = analisis.get("precio_estimado", "Por cotizar")
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
        return (
            f"{intro} {descripcion_dano} "
            f"Para confirmarlo necesitamos revisarlo en el taller. "
            f"El diagnóstico es sin costo. ¿Te gustaría traerlo?"
        )

    if precio == "Por cotizar":
        return (
            f"{intro} {descripcion_dano} "
            f"Basándonos en lo que vemos, el servicio que necesitas es *{servicio}*. "
            f"El costo exacto te lo confirmamos cuando lo revisemos físicamente. "
            f"¿Te gustaría traerlo a nuestro módulo?"
        )

    return (
        f"{intro} {descripcion_dano} "
        f"Basándonos en lo que vemos, el servicio que necesitas es *{servicio}* "
        f"con un costo aproximado de *{precio} MXN*. "
        f"Este es un diagnóstico preliminar — el precio exacto se confirma cuando lo revisamos físicamente. "
        f"¿Te gustaría traerlo a nuestro módulo?"
    )
