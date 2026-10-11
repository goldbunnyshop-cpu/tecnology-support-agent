# agent/pdf_generator.py — Generador de PDF de notas de servicio (Playwright)
# Plantilla: templates/service_note.html (réplica de la nota física, media carta 140x216 mm)

import os
import re
import base64
import asyncio
import logging
import unicodedata
import html as _html

logger = logging.getLogger("agentkit")

TEMPLATE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "templates")
PAGE_W, PAGE_H = "140mm", "216mm"


def _render_checkbox(valor) -> str:
    """Devuelve la clase CSS 'checked' (casilla marcada) o ''."""
    if isinstance(valor, bool):
        return "checked" if valor else ""
    if isinstance(valor, str) and valor.strip().lower() in ("si", "sí", "true", "1", "checked", "x"):
        return "checked"
    return ""


def _norm(s) -> str:
    s = unicodedata.normalize("NFD", str(s or "").lower())
    return "".join(c for c in s if unicodedata.category(c) != "Mn").strip()


def _logo_data_uri() -> str:
    ruta = os.path.join(TEMPLATE_DIR, "logo.png")
    try:
        with open(ruta, "rb") as f:
            return "data:image/png;base64," + base64.b64encode(f.read()).decode("ascii")
    except OSError:
        logger.warning(f"[PDF] logo no encontrado en {ruta} — el PDF sale sin logo")
        return ""


def _derivar(data: dict) -> dict:
    """Casillas y campos que se calculan a partir de otros datos."""
    d: dict = {}

    fp = _norm(data.get("forma_pago"))
    d["checked_efectivo"] = fp.startswith("efectivo")
    d["checked_tarjeta"] = fp.startswith("tarjeta")
    d["checked_transferencia"] = fp.startswith("trans")

    cal = _norm(data.get("calidad") or data.get("tipo_refaccion"))
    d["checked_ref_premium"] = "premium" in cal
    d["checked_ref_original"] = cal.startswith("original")
    d["checked_ref_generica"] = cal.startswith(("generic", "econom"))

    est = _norm(data.get("estado"))
    d["checked_prendido"] = est == "prendido"
    d["checked_apagado"] = est == "apagado"

    m = re.fullmatch(r"(\d{1,2})/(\d{1,2})/(\d{4})", str(data.get("fecha", "")).strip())
    if m:
        d["fecha_dia"], d["fecha_mes"], d["fecha_anio"] = m.group(1).zfill(2), m.group(2).zfill(2), m.group(3)
    return d


def _clabe_html(data: dict) -> str:
    # Una sola fuente de verdad: la misma variable que usa el comando "clabe:"
    clabe = re.sub(r"\D", "", str(data.get("clabe") or os.getenv("CLABE_CUENTA", "")))
    if not clabe:
        return ""
    return f"CLABE interbancaria <b>{_html.escape(clabe)}</b> &middot; Hey Banco<br>"


def render_html(data: dict) -> str:
    ruta_template = os.path.join(TEMPLATE_DIR, "service_note.html")
    if not os.path.exists(ruta_template):
        raise FileNotFoundError(f"Template no encontrado: {ruta_template}")
    with open(ruta_template, "r", encoding="utf-8") as f:
        doc = f.read()

    payload = {**_derivar(data), **data}

    for k, v in payload.items():
        if k.startswith("checked_"):
            v = _render_checkbox(v)
        else:
            # El texto viene de WhatsApp: escapar para que nadie rompa la plantilla con < > &
            v = _html.escape(str(v), quote=True)
        doc = doc.replace("{{" + k + "}}", v)

    # Bloques HTML propios (no se escapan)
    doc = doc.replace("{{logo_src}}", _logo_data_uri())
    doc = doc.replace("{{clabe_html}}", _clabe_html(data))

    # Cualquier campo que no vino queda en blanco (no se imprime "{{campo}}")
    return re.sub(r"\{\{[a-z0-9_]+\}\}", "", doc)


def generar_pdf(data: dict) -> bytes:
    """
    Genera el PDF de la nota de servicio con Playwright (Chromium). Media carta 140x216 mm.

    data (todas opcionales salvo folio/total en la práctica):
        folio, fecha (DD/MM/AAAA), cliente, telefono, domicilio,
        equipo_tipo, marca, modelo, imei, hora_entrada, fecha_entrega,
        tiempo_diagnostico, diagnostico, falla, caracteristicas, riesgos,
        roto, abollado, carcaza, estrellado, chip, funda, accesorios   (texto, ej. "NO")
        calidad (premium|original|generica), estado (prendido|apagado),
        total, anticipo, saldo, forma_pago (efectivo|tarjeta|transferencia),
        checked_mismo_dia, checked_sujeto_diag, checked_aut_firma, checked_aut_whatsapp,
        checked_presup_si, checked_presup_no   (bool)
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        logger.error("playwright no instalado. Ejecuta: pip install playwright && python -m playwright install chromium")
        raise

    documento = render_html(data)

    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-dev-shm-usage"],  # necesario en Docker/Railway (root)
        )
        page = browser.new_page()
        page.set_content(documento, wait_until="load")
        pdf_bytes = page.pdf(
            width=PAGE_W,
            height=PAGE_H,
            margin={"top": "0mm", "right": "0mm", "bottom": "0mm", "left": "0mm"},
            print_background=True,
        )
        browser.close()

    logger.info(f"PDF generado — folio {data.get('folio', '?')} ({len(pdf_bytes)} bytes)")
    return pdf_bytes


async def generar_pdf_async(data: dict) -> bytes:
    """Versión no bloqueante para usar dentro de handlers async (FastAPI)."""
    return await asyncio.to_thread(generar_pdf, data)
