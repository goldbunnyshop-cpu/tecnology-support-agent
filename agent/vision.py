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

PROMPT_VISION = """Eres el técnico experto de Tecnology Support, taller de reparación en La Comer Tlalpan, CDMX.
Analiza la imagen y responde SOLO con un objeto JSON sin texto adicional ni markdown.

══════════════════════════════════════════════════════════════
CASO A — CAPTURA DE PANTALLA de sistema / configuración / "Acerca del dispositivo"
══════════════════════════════════════════════════════════════
Si la imagen muestra una PANTALLA de sistema (HyperOS, MIUI, One UI, iOS, etc.) con texto
como "Nombre del dispositivo", "Modelo", "Model number", "About phone", versión de Android,
número de serie, especificaciones técnicas (procesador, RAM, almacenamiento), etc.:

→ LEE EL TEXTO TAL COMO APARECE. No intentes identificar por diseño físico.
→ Extrae el nombre y modelo EXACTO que aparece escrito en la pantalla.
→ Ignora el chip/procesador para identificar el modelo — usa solo el nombre del dispositivo.
→ Usa este formato JSON:

{
  "puede_diagnosticar": true,
  "es_captura_pantalla": true,
  "tipo_dispositivo": "celular | tablet | laptop | otro",
  "marca": "marca exacta que aparece en pantalla, o la deduces del nombre del sistema (HyperOS→Xiaomi, One UI→Samsung, iOS→Apple)",
  "modelo_probable": "nombre exacto del dispositivo tal como aparece escrito en la pantalla (ej: 'Redmi 13', 'Samsung Galaxy S22', 'iPhone 14 Pro')",
  "dano_visible": "sin daño visible",
  "puerto_afectado": "No aplica",
  "severidad": "no_determinable",
  "nota_tecnica": "Captura de pantalla de configuración. Modelo leído del texto: [escribe aquí exactamente lo que dice en pantalla]",
  "pregunta_cliente": ""
}

══════════════════════════════════════════════════════════════
CASO B — FOTO FÍSICA del dispositivo con daño visible
══════════════════════════════════════════════════════════════
Si la imagen muestra un dispositivo físico (no una pantalla de sistema):

{
  "puede_diagnosticar": true,
  "es_captura_pantalla": false,
  "tipo_dispositivo": "celular | consola | laptop | tablet | otro",
  "marca": "Apple | Samsung | Motorola | Xiaomi | Huawei | Sony PlayStation | Microsoft Xbox | Nintendo | HP | Dell | Lenovo | otra | No identificada",
  "modelo_probable": "mejor estimación según diseño de cámara, forma, logo visible (ej: 'Moto G serie media', 'PS4 Slim', 'iPhone 12-14') o 'No determinado'",
  "dano_visible": "pantalla rota | pantalla sin imagen | puerto dañado | no enciende | daño físico externo | sin daño visible | otro",
  "puerto_afectado": "USB-C | Lightning | micro-USB | HDMI | USB-A | lector SD | ninguno | No aplica",
  "severidad": "leve | moderada | grave | no_determinable",
  "nota_tecnica": "observación técnica de 1 línea para el técnico",
  "pregunta_cliente": "pregunta corta para confirmar el modelo si no fue posible determinarlo (ej: '¿Puedes ver el modelo en Ajustes → Acerca del teléfono?'). Deja vacío si el modelo es claro."
}

══════════════════════════════════════════════════════════════
Si la imagen es ilegible, borrosa, o no muestra ningún dispositivo:
{
  "puede_diagnosticar": false,
  "motivo": "breve explicación"
}

Responde SOLO el JSON, sin markdown, sin texto adicional."""


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


async def _llamar_vision(imagen_b64: str, media_type: str) -> dict:
    """Llama a Claude Vision con la imagen en base64 y retorna el dict parseado."""
    try:
        response = await client.messages.create(
            model="claude-haiku-4-5-20251001",  # Haiku: análisis de imagen básico, 4× más barato
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
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        return json.loads(raw.strip())
    except Exception as e:
        logger.error(f"Error en Claude Vision: {e}")
        return {"puede_diagnosticar": False, "motivo": "Error interno de análisis"}


def construir_contexto_historial(analisis: dict, tipo_media: str = "image") -> str:
    """Genera el texto que se guarda en el historial en lugar de '[imagen recibida]'.

    Ejemplo: '[imagen: celular Motorola Moto G serie media - pantalla rota]'
    Esto permite que brain.py tenga contexto en el siguiente mensaje del cliente.
    """
    if not analisis.get("puede_diagnosticar", True):
        return f"[{tipo_media} recibida: no se pudo identificar el equipo]"

    tipo  = analisis.get("tipo_dispositivo", "") or ""
    marca = analisis.get("marca", "") or ""
    modelo = analisis.get("modelo_probable", "") or ""
    dano  = analisis.get("dano_visible", "") or ""
    puerto = analisis.get("puerto_afectado", "") or ""

    if marca in ("No identificada", "otra", ""):
        marca = ""
    if modelo == "No determinado":
        modelo = ""
    if dano in ("sin daño visible", "No aplica", ""):
        dano = ""
    if puerto in ("ninguno", "No aplica", ""):
        puerto = ""

    partes_equipo = " ".join(filter(None, [tipo, marca, modelo])) or "equipo no identificado"
    partes_dano   = " - ".join(filter(None, [dano, f"puerto {puerto}" if puerto else ""]))
    resumen = partes_equipo + (f" - {partes_dano}" if partes_dano else "")

    return f"[{tipo_media}: {resumen}]"


async def analizar_imagen_bytes(imagen_bytes: bytes, mime_type: str) -> dict:
    """Analiza bytes de imagen con Claude Vision. El precio se confirma en el módulo."""
    imagen_b64 = base64.standard_b64encode(imagen_bytes).decode("utf-8")
    media_type = _mime_a_tipo_anthropic(mime_type)
    analisis = await _llamar_vision(imagen_b64, media_type)
    # No hay fuente automática de precios (ML descontinuado): el precio se cotiza en módulo.
    analisis.setdefault("precio_estimado", "Por cotizar")
    return analisis


async def analizar_thumbnail_b64(thumbnail_b64: str) -> dict:
    """Analiza el thumbnail JPEG de un video (ya en base64 desde Whapi)."""
    analisis = await _llamar_vision(thumbnail_b64, "image/jpeg")
    return await _enriquecer_con_precio_ml(analisis)


def construir_respuesta_cliente(analisis: dict, tipo_media: str, asesor: str = "Sofia") -> str:
    """
    Genera el mensaje al cliente basado en el análisis de visión.

    Casos:
    A — Daño visible → descripción + invitación al módulo
    B — Equipo identificado sin daño visible → confirmar y preguntar qué falla
    C — No identificado → preguntar específicamente según lo que sí se vio
    """
    # ── Caso C: imagen ilegible / no se pudo analizar ─────────────────────────
    if not analisis.get("puede_diagnosticar", True):
        motivo = analisis.get("motivo", "")
        if tipo_media == "video":
            return (
                "Recibí tu video \U0001f3a5 pero no pude ver el problema con claridad. "
                "¿Puedes describirme qué falla presenta tu equipo? "
                "Por ejemplo: no enciende, se congela, hace ruido extraño, etc."
            )
        return (
            "La foto quedó un poco oscura o borrosa \U0001f4f8 "
            "¿Puedes contarme qué equipo es y qué le está pasando?"
        )

    marca          = analisis.get("marca", "") or ""
    modelo_prob    = analisis.get("modelo_probable", "") or ""
    tipo_disp      = analisis.get("tipo_dispositivo", "") or ""
    dano           = analisis.get("dano_visible", "") or ""
    puerto         = analisis.get("puerto_afectado", "") or ""
    pregunta_suger = analisis.get("pregunta_cliente", "") or ""

    marca_mostrar  = marca if marca not in ("No identificada", "otra", "") else ""
    modelo_mostrar = modelo_prob if modelo_prob != "No determinado" else ""
    equipo_txt     = " ".join(filter(None, [marca_mostrar, modelo_mostrar])) or tipo_disp or "tu equipo"

    hay_dano = bool(dano and dano not in ("sin daño visible", "No aplica", ""))
    hay_puerto = bool(puerto and puerto not in ("ninguno", "No aplica", ""))

    # ── Caso A: daño visible ──────────────────────────────────────────────────
    if hay_dano:
        intro = "Vi la foto 📸" if tipo_media == "image" else "Revisé tu video 🎥"

        # Puerto dañado en consola / celular
        if hay_puerto and "puerto" in dano.lower():
            desc = f"Veo daño en el puerto *{puerto}* de tu {equipo_txt}."
        else:
            desc = f"Veo que tu *{equipo_txt}* tiene {dano}."

        pregunta_final = pregunta_suger or "¿Te gustaría traerlo para revisarlo sin costo?"
        return (
            f"{intro} {desc} "
            f"El diagnóstico es sin costo y lo hacemos en el momento. "
            f"{pregunta_final}"
        )

    # ── Caso B: equipo identificado, sin daño visible ─────────────────────────
    if equipo_txt and equipo_txt != "tu equipo":
        pregunta_final = pregunta_suger or "¿Qué problema o servicio necesitas?"
        return (
            f"Recibí tu foto \U0001f4f8 Por el diseño parece un *{equipo_txt}*. "
            f"{pregunta_final}"
        )

    # ── Caso C: no se identificó nada claro ───────────────────────────────────
    pregunta_final = pregunta_suger or "¿Qué equipo es y qué le está pasando?"
    return (
        f"Recibí tu foto \U0001f4f8 "
        f"{pregunta_final}"
    )
