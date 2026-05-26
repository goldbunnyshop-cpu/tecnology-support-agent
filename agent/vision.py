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
Analiza la imagen y responde SOLO con un objeto JSON sin texto adicional.

IMPORTANTE: No uses precios de catálogo ni listas de servicios fijos. Solo describe lo que ves en la imagen.

{
  "dispositivo": "nombre del dispositivo (ej: iPhone 12, PS4, Samsung Galaxy S21, laptop HP, etc.) o 'No identificado' si no puedes determinarlo",
  "dano_visible": "descripción concisa del daño o problema visual detectado, o 'No se aprecia daño visible' si todo parece bien",
  "severidad": "leve | moderada | grave | no_determinable",
  "reparacion_necesaria": "descripción técnica de lo que hay que hacer físicamente (ej: sustituir el panel LCD, reemplazar la batería, limpiar los pines del puerto USB-C). Usa lenguaje técnico neutro, sin nombres de paquetes de servicio. 'Diagnóstico físico requerido' si no puedes determinarlo",
  "refaccion_ml": "término de búsqueda para la refacción principal en MercadoLibre México (ej: 'pantalla iPhone 12 original', 'batería Samsung S21', 'ventilador PS4 CUH-1200'). Cadena vacía si no requiere refacción (limpieza, diagnóstico, etc.)",
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
    """Descarga media de Whapi por URL directa, preservando el token en cada redirect."""
    if not url or not token:
        return None
    headers = {"Authorization": f"Bearer {token}"}
    try:
        async with httpx.AsyncClient(timeout=20) as c:
            for intento in range(4):
                r = await c.get(url, headers=headers, follow_redirects=False)
                if r.status_code == 200:
                    content_type = r.headers.get("content-type", "image/jpeg").split(";")[0].strip()
                    logger.info(f"[VISION] URL descargada — {len(r.content)} bytes, {content_type}")
                    return r.content, content_type
                if r.status_code in (301, 302, 303, 307, 308):
                    url = r.headers.get("location", "")
                    if not url:
                        return None
                    continue
                logger.warning(f"[VISION] HTTP {r.status_code} descargando URL")
                return None
            return None
    except Exception as e:
        logger.error(f"[VISION] Excepción descargando URL: {e}")
        return None


async def descargar_media_por_id(media_id: str, token: str, mime_type: str = "image/jpeg") -> tuple[bytes, str] | None:
    """
    Descarga media de Whapi probando los endpoints documentados en orden.
    Preserva el Authorization header en cada redirect (httpx lo eliminaría en cross-origin).
    """
    if not media_id or not token:
        logger.warning(f"[VISION] media_id o token vacíos — abortando descarga")
        return None

    token_preview = token[:10] + "..."
    headers = {"Authorization": f"Bearer {token}"}

    # Endpoints de Whapi a probar en orden
    endpoints = [
        f"https://gate.whapi.cloud/messages/media/{media_id}",
        f"https://gate.whapi.cloud/media/{media_id}",
        f"https://gate.whapi.cloud/files/{media_id}",
    ]

    try:
        async with httpx.AsyncClient(timeout=20) as c:
            for endpoint in endpoints:
                url = endpoint
                logger.info(f"[VISION] Intentando → {url} | token: {token_preview}")

                for _ in range(4):  # hasta 3 redirects por endpoint
                    r = await c.get(url, headers=headers, follow_redirects=False)
                    logger.info(f"[VISION] HTTP {r.status_code} ← {url[:70]}")

                    if r.status_code == 200:
                        content_type = r.headers.get("content-type", mime_type).split(";")[0].strip()
                        logger.info(f"[VISION] ✓ Descarga OK — {len(r.content)} bytes, {content_type}")
                        return r.content, content_type

                    if r.status_code in (301, 302, 303, 307, 308):
                        nueva_url = r.headers.get("location", "")
                        if not nueva_url:
                            logger.warning("[VISION] Redirect sin Location header")
                            break
                        logger.info(f"[VISION] Redirect → {nueva_url[:70]}")
                        url = nueva_url
                        continue

                    # 4xx/5xx no recuperable para este endpoint
                    logger.warning(f"[VISION] HTTP {r.status_code} en {endpoint[:60]} — probando siguiente")
                    break  # pasa al siguiente endpoint

            logger.error(f"[VISION] Todos los endpoints fallaron para media_id='{media_id}'")
            return None

    except Exception as e:
        logger.error(f"[VISION] Excepción descargando media_id='{media_id}': {e}")
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
    """
    Genera el mensaje al cliente basado en el análisis de visión.

    Casos:
    A — Daño visible → diagnóstico + invitación al módulo
    B/C — Equipo identificado sin daño → confirmar dispositivo, preguntar qué falla tiene
    D — Imagen borrosa o dispositivo no identificado → pedir descripción del problema
    """
    # ── Caso D: imagen borrosa / no se pudo analizar ──────────────────────────
    if not analisis.get("puede_diagnosticar", True):
        if tipo_media == "video":
            return (
                "Recibí tu video \U0001f3a5 pero no pude ver el problema con claridad. "
                "¿Puedes describirme qué falla presenta tu equipo? "
                "Por ejemplo: no enciende, se congela, hace ruido extraño, etc."
            )
        return (
            "La foto quedó un poco borrosa. "
            "Cuéntame, ¿qué problema tiene tu equipo?"
        )

    dispositivo = analisis.get("dispositivo", "")
    dano        = analisis.get("dano_visible", "")
    hay_dano    = bool(dano and dano != "No se aprecia daño visible")

    # ── Casos B/C: equipo identificado pero sin daño visible ─────────────────
    if not hay_dano:
        if dispositivo and dispositivo != "No identificado":
            return (
                f"✅ Por la foto veo que tienes un *{dispositivo}*. "
                f"¡Perfecto, así puedo asesorarte mejor! 😊 "
                f"Cuéntame, ¿qué problema tiene o qué servicio necesitas?"
            )
        # No se identificó el dispositivo y sin daño
        return (
            "Recibí tu foto \U0001f4f8 No pude identificar bien el equipo. "
            "¿Puedes contarme qué dispositivo es y cuál es el problema?"
        )

    # ── Caso A: hay daño visible → flujo de diagnóstico ──────────────────────
    reparacion = analisis.get("reparacion_necesaria", "Diagnóstico físico requerido")
    precio     = analisis.get("precio_estimado", "Por cotizar")
    intro      = "Vi la foto de tu equipo \U0001f4f8" if tipo_media == "image" else "Revisé tu video \U0001f3a5"
    equipo_txt = dispositivo or "tu equipo"
    desc_dano  = f"Parece que tienes {dano} en tu {equipo_txt}."

    if reparacion == "Diagnóstico físico requerido" or precio == "Por cotizar":
        return (
            f"{intro} {desc_dano} "
            f"Para un diagnóstico preciso necesitamos revisarlo en nuestro módulo. "
            f"El diagnóstico es sin costo y lo hacemos en el momento. ¿Te gustaría traerlo?"
        )

    return (
        f"{intro} {desc_dano} "
        f"Con base en lo que vemos, el costo aproximado es de *{precio} MXN*. "
        f"Este es un diagnóstico preliminar — el precio exacto se confirma cuando lo revisamos físicamente. "
        f"¿Te gustaría traerlo a nuestro módulo?"
    )
