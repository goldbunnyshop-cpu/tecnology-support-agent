# agent/pdf_generator.py — Generador de PDF de notas de servicio
# Generado por AgentKit

import os
import logging

logger = logging.getLogger("agentkit")

TEMPLATE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "templates")


def _render_checkbox(valor: bool | str) -> str:
    """Convierte un valor booleano a 'checked' para el checkbox HTML."""
    if isinstance(valor, bool):
        return "checked" if valor else ""
    if isinstance(valor, str) and valor.lower() in ("si", "sí", "true", "1", "checked"):
        return "checked"
    return ""


def generar_pdf(data: dict) -> bytes:
    """
    Genera un PDF de nota de servicio a partir de un dict de datos.

    data puede contener:
        folio, cliente, telefono, domicilio, equipo_tipo, marca, modelo,
        imei, falla, diagnostico, total, anticipo, saldo, forma_pago,
        tipo_refaccion, otro_servicio,
        checked_mant, checked_refac, checked_soft, checked_otro (bool)
    """
    try:
        import weasyprint
    except ImportError:
        logger.error("weasyprint no instalado. Ejecuta: pip install weasyprint")
        raise

    ruta_template = os.path.join(TEMPLATE_DIR, "service_note.html")
    if not os.path.exists(ruta_template):
        raise FileNotFoundError(f"Template no encontrado: {ruta_template}")

    with open(ruta_template, "r", encoding="utf-8") as f:
        html = f.read()

    defaults = {
        "folio": "00000",
        "cliente": "",
        "telefono": "",
        "domicilio": "",
        "equipo_tipo": "",
        "marca": "",
        "modelo": "",
        "imei": "",
        "falla": "",
        "diagnostico": "",
        "total": "0",
        "anticipo": "0",
        "saldo": "0",
        "forma_pago": "",
        "tipo_refaccion": "",
        "otro_servicio": "",
        "checked_mant": False,
        "checked_refac": False,
        "checked_soft": False,
        "checked_otro": False,
    }

    payload = {**defaults, **data}

    for k, v in payload.items():
        if k.startswith("checked_"):
            v = _render_checkbox(v)
        html = html.replace("{{" + k + "}}", str(v))

    pdf_bytes = weasyprint.HTML(string=html).write_pdf()
    logger.info(f"PDF generado — folio {payload['folio']} ({len(pdf_bytes)} bytes)")
    return pdf_bytes
