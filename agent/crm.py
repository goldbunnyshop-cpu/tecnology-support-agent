# agent/crm.py — CRM: Google Sheets (ORDENES) + Google Drive

import os
import re
import json
import logging
import asyncio
from datetime import datetime
from zoneinfo import ZoneInfo

from googleapiclient.discovery import build
from google.oauth2.service_account import Credentials

logger = logging.getLogger("agentkit")

ZONA          = ZoneInfo("America/Mexico_City")
SCOPES        = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

SHEET_ID      = os.getenv("GOOGLE_SHEET_ID", "")
DRIVE_ROOT_ID = os.getenv("GOOGLE_DRIVE_FOLDER_ID", "root")
COMISION_PCT  = float(os.getenv("COMISION_TARJETA_PCT", "3.6")) / 100

ESTATUS_VALIDOS = ("Recibido", "En proceso", "Listo", "Entregado")

# Índices de columna en ORDENES (0-based)
C_FOLIO     = 0   # A
C_FECHA     = 1   # B
C_CLIENTE   = 2   # C
C_TELEFONO  = 3   # D
C_EQUIPO    = 4   # E
C_MODELO    = 5   # F
C_FALLA     = 6   # G
C_ESTATUS   = 7   # H
C_TOTAL     = 8   # I
C_PAGO      = 9   # J
C_COMISION  = 10  # K
C_REFACCION = 11  # L
C_GANANCIA  = 12  # M
C_DRIVE     = 13  # N
C_FACTURA   = 14  # O

HEADER_ORDENES = [
    "Folio", "Fecha ingreso", "Cliente", "Teléfono", "Equipo", "Modelo",
    "Falla", "Estatus", "Total cobrado", "Forma de pago", "Comisión bancaria",
    "Costo refacción", "Ganancia real", "Link Drive", "Factura",
]


# ─── Autenticación ────────────────────────────────────────────────────────────

def _creds():
    raw = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON", "")
    if not raw:
        raise RuntimeError("GOOGLE_SERVICE_ACCOUNT_JSON no configurado")
    return Credentials.from_service_account_info(json.loads(raw), scopes=SCOPES)


def _sheets_svc():
    return build("sheets", "v4", credentials=_creds())


def _drive_svc():
    return build("drive", "v3", credentials=_creds())


# ─── Cálculos financieros ─────────────────────────────────────────────────────

def _bloque(folio_num: int) -> str:
    """folio 1-100 → Bloque-001, 101-200 → Bloque-002, etc."""
    n = (max(folio_num, 1) - 1) // 100 + 1
    return f"Bloque-{n:03d}"


def _comision(total: float, forma_pago: str) -> float:
    """Comisión solo si el pago es con tarjeta."""
    return round(total * COMISION_PCT, 2) if "tarjeta" in forma_pago.lower() else 0.0


def _ganancia(total: float, comision: float, refaccion: float) -> float:
    return round(total - comision - refaccion, 2)


# ─── Búsqueda de fila ─────────────────────────────────────────────────────────

def _fila_de_folio(all_values: list[list], folio: str) -> int | None:
    """
    Busca el folio en all_values (incluye header en [0]).
    Retorna el número de fila de Google Sheets (1-based).
    """
    target = str(folio).lstrip("0") or "0"
    for idx, row in enumerate(all_values):
        if row and str(row[0]).lstrip("0") == target:
            return idx + 1  # Sheet es 1-based
    return None


def _safe(row: list, idx: int) -> str:
    return str(row[idx]) if idx < len(row) else ""


# ─── Google Drive: carpetas ───────────────────────────────────────────────────

def _buscar_o_crear(drive, nombre: str, parent_id: str) -> str:
    q = (
        f"name='{nombre}' and mimeType='application/vnd.google-apps.folder' "
        f"and '{parent_id}' in parents and trashed=false"
    )
    res = drive.files().list(q=q, fields="files(id)").execute()
    if res.get("files"):
        return res["files"][0]["id"]
    carpeta = drive.files().create(
        body={
            "name":     nombre,
            "mimeType": "application/vnd.google-apps.folder",
            "parents":  [parent_id],
        },
        fields="id",
    ).execute()
    return carpeta["id"]


def _crear_carpeta_ticket_sync(folio: str) -> str:
    """Crea /AÑO/Bloque-XXX/Ticket-NNNN en Drive. Retorna link de la carpeta."""
    drive   = _drive_svc()
    num     = int(re.sub(r"\D", "", folio) or "1")
    anio    = str(datetime.now(ZONA).year)
    bloque  = _bloque(num)
    ticket  = f"Ticket-{folio.zfill(4)}"

    id_anio   = _buscar_o_crear(drive, anio,   DRIVE_ROOT_ID)
    id_bloque = _buscar_o_crear(drive, bloque, id_anio)
    id_ticket = _buscar_o_crear(drive, ticket, id_bloque)

    try:
        drive.permissions().create(
            fileId=id_ticket,
            body={"type": "anyone", "role": "reader"},
        ).execute()
    except Exception as e:
        logger.warning(f"[CRM] Sin permiso público en carpeta: {e}")

    link = f"https://drive.google.com/drive/folders/{id_ticket}"
    logger.info(f"[CRM] Drive: {anio}/{bloque}/{ticket} → {link}")
    return link


# ─── Google Sheets: inicializar hoja ─────────────────────────────────────────

def _asegurar_hoja_ordenes_sync():
    """Crea la hoja ORDENES con headers si no existe."""
    if not SHEET_ID:
        logger.warning("[CRM] GOOGLE_SHEET_ID no configurado — CRM desactivado")
        return

    svc  = _sheets_svc()
    meta = svc.spreadsheets().get(spreadsheetId=SHEET_ID).execute()
    hojas = [s["properties"]["title"] for s in meta.get("sheets", [])]

    if "ORDENES" not in hojas:
        svc.spreadsheets().batchUpdate(
            spreadsheetId=SHEET_ID,
            body={"requests": [{"addSheet": {"properties": {"title": "ORDENES"}}}]},
        ).execute()
        logger.info("[CRM] Hoja ORDENES creada")

    # Escribir header solo si la hoja está vacía
    res = svc.spreadsheets().values().get(
        spreadsheetId=SHEET_ID, range="ORDENES!A1:O1"
    ).execute()
    if not res.get("values"):
        svc.spreadsheets().values().update(
            spreadsheetId=SHEET_ID,
            range="ORDENES!A1",
            valueInputOption="USER_ENTERED",
            body={"values": [HEADER_ORDENES]},
        ).execute()
        logger.info("[CRM] Headers escritos en ORDENES")


# ─── CRUD ────────────────────────────────────────────────────────────────────

def _registrar_sync(
    folio: str, telefono: str, cliente: str,
    equipo: str, modelo: str, falla: str,
    total: float, forma_pago: str, refaccion: float = 0.0,
) -> dict:
    if not SHEET_ID:
        raise RuntimeError("GOOGLE_SHEET_ID no configurado")

    svc      = _sheets_svc()
    com      = _comision(total, forma_pago)
    gan      = _ganancia(total, com, refaccion)
    folio_fmt = folio.zfill(4)

    # Crear carpeta Drive
    try:
        link_drive = _crear_carpeta_ticket_sync(folio)
    except Exception as e:
        logger.warning(f"[CRM] Error Drive: {e}")
        link_drive = ""

    fecha = datetime.now(ZONA).strftime("%d/%m/%Y %H:%M")
    fila  = [
        folio_fmt, fecha, cliente, telefono, equipo, modelo, falla,
        "Recibido", total, forma_pago, com, refaccion, gan, link_drive, "",
    ]

    svc.spreadsheets().values().append(
        spreadsheetId=SHEET_ID,
        range="ORDENES!A:O",
        valueInputOption="USER_ENTERED",
        insertDataOption="INSERT_ROWS",
        body={"values": [fila]},
    ).execute()

    logger.info(f"[CRM] Orden registrada: #{folio_fmt} {equipo} ${total} ({forma_pago})")
    return {
        "folio": folio_fmt, "cliente": cliente, "equipo": equipo,
        "total": total, "comision": com, "refaccion": refaccion,
        "ganancia": gan, "link_drive": link_drive, "estatus": "Recibido",
    }


def _actualizar_estatus_sync(folio: str, nuevo_estatus: str) -> bool:
    if not SHEET_ID:
        return False
    svc = _sheets_svc()
    res = svc.spreadsheets().values().get(
        spreadsheetId=SHEET_ID, range="ORDENES!A:A"
    ).execute()
    fila = _fila_de_folio(res.get("values", []), folio)
    if fila is None:
        logger.warning(f"[CRM] Folio {folio} no encontrado")
        return False
    svc.spreadsheets().values().update(
        spreadsheetId=SHEET_ID,
        range=f"ORDENES!H{fila}",
        valueInputOption="USER_ENTERED",
        body={"values": [[nuevo_estatus]]},
    ).execute()
    logger.info(f"[CRM] Folio #{folio.zfill(4)} → {nuevo_estatus}")
    return True


def _consultar_sync(folio: str) -> dict | None:
    if not SHEET_ID:
        return None
    svc = _sheets_svc()
    res = svc.spreadsheets().values().get(
        spreadsheetId=SHEET_ID, range="ORDENES!A:O"
    ).execute()
    values = res.get("values", [])
    if not values:
        return None
    fila = _fila_de_folio(values, folio)
    if fila is None:
        return None
    row = values[fila - 1]  # fila es 1-based → índice 0-based
    return {
        "folio":     _safe(row, C_FOLIO),
        "fecha":     _safe(row, C_FECHA),
        "cliente":   _safe(row, C_CLIENTE),
        "telefono":  _safe(row, C_TELEFONO),
        "equipo":    _safe(row, C_EQUIPO),
        "modelo":    _safe(row, C_MODELO),
        "falla":     _safe(row, C_FALLA),
        "estatus":   _safe(row, C_ESTATUS),
        "total":     _safe(row, C_TOTAL),
        "forma_pago":_safe(row, C_PAGO),
        "comision":  _safe(row, C_COMISION),
        "refaccion": _safe(row, C_REFACCION),
        "ganancia":  _safe(row, C_GANANCIA),
        "link_drive":_safe(row, C_DRIVE),
        "factura":   _safe(row, C_FACTURA),
    }


def _ordenes_facturables_sync() -> list[dict]:
    """Órdenes con pago tarjeta o transferencia sin factura asignada."""
    if not SHEET_ID:
        return []
    svc = _sheets_svc()
    res = svc.spreadsheets().values().get(
        spreadsheetId=SHEET_ID, range="ORDENES!A:O"
    ).execute()
    values = res.get("values", [])
    result = []
    for row in values[1:]:  # saltar header
        pago    = _safe(row, C_PAGO).lower()
        factura = _safe(row, C_FACTURA).strip()
        if ("tarjeta" in pago or "transferencia" in pago) and not factura:
            result.append({
                "folio":   _safe(row, C_FOLIO),
                "cliente": _safe(row, C_CLIENTE),
                "total":   _safe(row, C_TOTAL),
                "pago":    pago,
                "estatus": _safe(row, C_ESTATUS),
            })
    return result


# ─── API pública (async) ──────────────────────────────────────────────────────

async def inicializar_crm():
    try:
        await asyncio.to_thread(_asegurar_hoja_ordenes_sync)
        logger.info("[CRM] Hoja ORDENES lista")
    except Exception as e:
        logger.error(f"[CRM] Error inicializando: {e}")


async def registrar_orden(
    folio: str, telefono: str, cliente: str,
    equipo: str, modelo: str, falla: str,
    total: float, forma_pago: str, refaccion: float = 0.0,
) -> dict:
    return await asyncio.to_thread(
        _registrar_sync,
        folio, telefono, cliente, equipo, modelo, falla, total, forma_pago, refaccion,
    )


async def actualizar_estatus_orden(folio: str, nuevo_estatus: str) -> bool:
    return await asyncio.to_thread(_actualizar_estatus_sync, folio, nuevo_estatus)


async def consultar_orden(folio: str) -> dict | None:
    return await asyncio.to_thread(_consultar_sync, folio)


async def obtener_ordenes_facturables() -> list[dict]:
    return await asyncio.to_thread(_ordenes_facturables_sync)


def _mapa_ordenes_por_telefono_sync() -> dict[str, list[dict]]:
    """
    Carga TODA la hoja ORDENES una sola vez y devuelve un dict
    {telefono_normalizado: [{"folio":..., "estatus":...}, ...]}
    """
    if not SHEET_ID:
        return {}
    try:
        svc = _sheets_svc()
        res = svc.spreadsheets().values().get(
            spreadsheetId=SHEET_ID, range="ORDENES!A:O"
        ).execute()
        values = res.get("values", [])
        mapa: dict[str, list] = {}
        for row in values[1:]:  # saltar header
            tel = re.sub(r"\D", "", _safe(row, C_TELEFONO))
            if not tel:
                continue
            entrada = {
                "folio":   _safe(row, C_FOLIO),
                "estatus": _safe(row, C_ESTATUS),
                "equipo":  _safe(row, C_EQUIPO),
            }
            mapa.setdefault(tel, []).append(entrada)
        return mapa
    except Exception as e:
        logger.warning(f"[CRM] Error cargando mapa de órdenes: {e}")
        return {}


async def obtener_mapa_ordenes_por_telefono() -> dict[str, list[dict]]:
    """Dict {tel: [órdenes]} cargado en un solo request a Sheets."""
    return await asyncio.to_thread(_mapa_ordenes_por_telefono_sync)
