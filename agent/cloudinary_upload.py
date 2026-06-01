# agent/cloudinary_upload.py — Subida de imágenes/PDF a Cloudinary
# Generado por AgentKit

import os
import logging

logger = logging.getLogger("agentkit")


def configurar_cloudinary():
    """Configura el SDK de Cloudinary con variables de entorno."""
    try:
        import cloudinary
    except ImportError:
        logger.error("cloudinary no instalado. Ejecuta: pip install cloudinary")
        raise

    cloudinary.config(
        cloud_name=os.getenv("CLOUDINARY_CLOUD_NAME"),
        api_key=os.getenv("CLOUDINARY_API_KEY"),
        api_secret=os.getenv("CLOUDINARY_API_SECRET"),
        secure=True,
    )
    logger.info("Cloudinary configurado correctamente")


async def subir_imagen(ruta: str, folder: str = "service_notes") -> str:
    """
    Sube una imagen o PDF a Cloudinary y retorna la URL segura.

    Args:
        ruta: Ruta local del archivo a subir
        folder: Carpeta en Cloudinary (default: service_notes)

    Returns:
        URL pública del archivo subido
    """
    try:
        import cloudinary.uploader
    except ImportError:
        logger.error("cloudinary no instalado")
        return ""

    if not os.path.exists(ruta):
        logger.error(f"Archivo no encontrado: {ruta}")
        return ""

    try:
        result = cloudinary.uploader.upload(ruta, folder=folder)
        url = result.get("secure_url", "")
        if url:
            logger.info(f"Subido a Cloudinary: {url}")
        else:
            logger.warning(f"Cloudinary no devolvió secure_url: {result}")
        return url
    except Exception as e:
        logger.error(f"Error subiendo a Cloudinary: {e}")
        return ""
