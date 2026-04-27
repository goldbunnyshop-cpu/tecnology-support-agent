# agent/crm.py — CRM: Google Sheets (Bloque-XXX) + Google Drive

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

ZONA             = ZoneInfo("America/Mexico_City")
SCOPES           = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

SHEET_ID         = os.getenv("GOOGLE_SHEET_ID", "")
DRIVE_ROOT_ID    = os.getenv("GOOGLE_DRIVE_FOLDER_ID", "root")
COMISION_PCT     = float(os.getenv("COMISION_TARJETA_PCT", "3.6")) / 100
MAX_FILAS_BLOQUE = 100

ESTATUS_VALIDOS = ("Recibido", "En proceso", "Listo", "Entregado")

# Índices de columna (0-based)
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

HEADER = [
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


# ─── Cálculos ────────────────────────────────────────────────────────────────

def _nombre_bloque(num: int) -> str:
    return f"Bloque-{num:03d}"

def _comision(total: float, forma_pago: str) -> float:
    return round(total * COMISION_PCT, 2) if "tarjeta" in forma_pago.lower() else 0.0

def _ganancia(total: float, comision: float, refaccion: float) -> float:
    return round(total - comision - refaccion, 2)

def _safe(row: list, idx: int) -> str:
    return str(row[idx]) if idx < len(row) else ""


# ─── Estructura de bloques ────────────────────────────────────────────────────

def _bloque_y_fila_de_folio(folio_num: int) -> tuple[str, int]:
    """
    Dado un folio consecutivo (1, 2, …), retorna (nombre_bloque, fila_sheets).
    Folio 1-100   → Bloque-001, filas 2-101
    Folio 101-200 → Bloque-002, filas 2-101
    La fila 1 siempre es el header.
    """
    bloque_num = (folio_num - 1) // MAX_FILAS_BLOQUE + 1
    fila       = (folio_num - 1) % MAX_FILAS_BLOQUE + 2
    return _nombre_bloque(bloque_num), fila


def _listar_bloques_sync(svc) -> list[str]:
    """Retorna nombres de todos los Bloque-XXX existentes, ordenados."""
    meta = svc.spreadsheets().get(spreadsheetId=SHEET_ID).execute()
    return sorted(
        s["properties"]["title"]
        for s in meta.get("sheets", [])
        if re.match(r"^Bloque-\d{3}$", s["properties"]["title"])
    )


def _crear_bloque_sync(svc, nombre: str):
    """Crea una nueva hoja con header."""
    svc.spreadsheets().batchUpdate(
        spreadsheetId=SHEET_ID,
        body={"requests": [{"addSheet": {"properties": {"title": nombre}}}]},
    ).execute()
    svc.spreadsheets().values().update(
        spreadsheetId=SHEET_ID,
        range=f"'{nombre}'!A1",
        valueInputOption="USER_ENTERED",
        body={"values": [HEADER]},
    ).execute()
    logger.info(f"[CRM] Bloque creado: {nombre}")


def _siguiente_folio_y_bloque_sync() -> tuple[int, str]:
    """
    Determina el próximo folio consecutivo global y el bloque activo.
    Crea Bloque-001 si no hay ninguno.
    Crea el siguiente bloque si el actual alcanzó MAX_FILAS_BLOQUE.
    """
    svc    = _sheets_svc()
    bloques = _listar_bloques_sync(svc)

    if not bloques:
        _crear_bloque_sync(svc, "Bloque-001")
        return 1, "Bloque-001"

    ultimo_bloque = bloques[-1]
    res = svc.spreadsheets().values().get(
        spreadsheetId=SHEET_ID, range=f"'{ultimo_bloque}'!A:A"
    ).execute()
    filas_datos = max(0, len(res.get("values", [])) - 1)

    total_ordenes = (len(bloques) - 1) * MAX_FILAS_BLOQUE + filas_datos
    next_folio    = total_ordenes + 1

    if filas_datos >= MAX_FILAS_BLOQUE:
        nuevo_bloque = _nombre_bloque(len(bloques) + 1)
        _crear_bloque_sync(svc, nuevo_bloque)
        return next_folio, nuevo_bloque

    return next_folio, ultimo_bloque


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


def _crear_carpeta_ticket_sync(folio_num: int, bloque: str) -> str:
    """Crea /AÑO/Bloque-XXX/Ticket-NNNNN en Drive. Retorna link público."""
    drive  = _drive_svc()
    anio   = str(datetime.now(ZONA).year)
    ticket = f"Ticket-{folio_num:05d}"

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


# ─── Google Sheets: inicialización ───────────────────────────────────────────

def _asegurar_bloque_inicial_sync():
    """Asegura que Bloque-001 exista con headers al arrancar."""
    if not SHEET_ID:
        logger.warning("[CRM] GOOGLE_SHEET_ID no configurado — CRM desactivado")
        return
    svc     = _sheets_svc()
    bloques = _listar_bloques_sync(svc)
    if not bloques:
        _crear_bloque_sync(svc, "Bloque-001")
        logger.info("[CRM] Bloque-001 creado")
    else:
        logger.info(f"[CRM] Bloques existentes: {', '.join(bloques)}")


# ─── CRUD ────────────────────────────────────────────────────────────────────

def _registrar_sync(
    telefono: str, cliente: str,
    equipo: str, modelo: str, falla: str,
    total: float, forma_pago: str, refaccion: float = 0.0,
) -> dict:
    if not SHEET_ID:
        raise RuntimeError("GOOGLE_SHEET_ID no configurado")

    folio_num, bloque_activo = _siguiente_folio_y_bloque_sync()
    svc = _sheets_svc()

    com = _comision(total, forma_pago)
    gan = _ganancia(total, com, refaccion)

    try:
        link_drive = _crear_carpeta_ticket_sync(folio_num, bloque_activo)
    except Exception as e:
        logger.warning(f"[CRM] Error Drive: {e}")
        link_drive = ""

    fecha = datetime.now(ZONA).strftime("%d/%m/%Y %H:%M")
    fila  = [
        f"{folio_num:05d}", fecha, cliente, telefono,
        equipo, modelo, falla,
        "Recibido", total, forma_pago, com, refaccion, gan, link_drive, "",
    ]

    svc.spreadsheets().values().append(
        spreadsheetId=SHEET_ID,
        range=f"'{bloque_activo}'!A:O",
        valueInputOption="USER_ENTERED",
        insertDataOption="INSERT_ROWS",
        body={"values": [fila]},
    ).execute()

    logger.info(
        f"[CRM] Orden #{folio_num:05d} en {bloque_activo} "
        f"| {equipo} ${total} ({forma_pago})"
    )
    return {
        "folio_crm":  f"{folio_num:05d}",
        "bloque":     bloque_activo,
        "folio":      f"{folio_num:05d}",   # backward compat
        "cliente":    cliente,
        "equipo":     equipo,
        "total":      total,
        "comision":   com,
        "refaccion":  refaccion,
        "ganancia":   gan,
        "link_drive": link_drive,
        "estatus":    "Recibido",
    }


def _actualizar_estatus_sync(folio: str, nuevo_estatus: str) -> bool:
    if not SHEET_ID:
        return False
    folio_num = int(re.sub(r"\D", "", folio) or "0")
    if not folio_num:
        logger.warning(f"[CRM] Folio inválido: {folio}")
        return False
    bloque, fila = _bloque_y_fila_de_folio(folio_num)
    svc = _sheets_svc()
    svc.spreadsheets().values().update(
        spreadsheetId=SHEET_ID,
        range=f"'{bloque}'!H{fila}",
        valueInputOption="USER_ENTERED",
        body={"values": [[nuevo_estatus]]},
    ).execute()
    logger.info(f"[CRM] Folio #{folio_num:05d} → {nuevo_estatus}")
    return True


def _consultar_sync(folio: str) -> dict | None:
    if not SHEET_ID:
        return None
    folio_num = int(re.sub(r"\D", "", folio) or "0")
    if not folio_num:
        return None
    bloque, fila = _bloque_y_fila_de_folio(folio_num)
    svc = _sheets_svc()
    res = svc.spreadsheets().values().get(
        spreadsheetId=SHEET_ID, range=f"'{bloque}'!A{fila}:O{fila}"
    ).execute()
    values = res.get("values", [])
    if not values or not values[0]:
        return None
    row = values[0]
    return {
        "folio":      _safe(row, C_FOLIO),
        "fecha":      _safe(row, C_FECHA),
        "cliente":    _safe(row, C_CLIENTE),
        "telefono":   _safe(row, C_TELEFONO),
        "equipo":     _safe(row, C_EQUIPO),
        "modelo":     _safe(row, C_MODELO),
        "falla":      _safe(row, C_FALLA),
        "estatus":    _safe(row, C_ESTATUS),
        "total":      _safe(row, C_TOTAL),
        "forma_pago": _safe(row, C_PAGO),
        "comision":   _safe(row, C_COMISION),
        "refaccion":  _safe(row, C_REFACCION),
        "ganancia":   _safe(row, C_GANANCIA),
        "link_drive": _safe(row, C_DRIVE),
        "factura":    _safe(row, C_FACTURA),
    }


# ─── Iteración sobre todos los bloques ───────────────────────────────────────

def _iter_todas_las_ordenes_sync(svc) -> list[list]:
    """Carga todas las filas de datos de todos los Bloque-XXX (sin headers)."""
    bloques = _listar_bloques_sync(svc)
    todas: list[list] = []
    for bloque in bloques:
        res = svc.spreadsheets().values().get(
            spreadsheetId=SHEET_ID, range=f"'{bloque}'!A:O"
        ).execute()
        rows = res.get("values", [])
        todas.extend(rows[1:])   # saltar header
    return todas


def _ordenes_facturables_sync() -> list[dict]:
    """Órdenes con pago electrónico sin factura asignada."""
    if not SHEET_ID:
        return []
    svc  = _sheets_svc()
    rows = _iter_todas_las_ordenes_sync(svc)
    result = []
    for row in rows:
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


def _mapa_ordenes_por_telefono_sync() -> dict[str, list[dict]]:
    """Dict {tel: [órdenes]} cargado en un solo recorrido."""
    if not SHEET_ID:
        return {}
    try:
        svc  = _sheets_svc()
        rows = _iter_todas_las_ordenes_sync(svc)
        mapa: dict[str, list] = {}
        for row in rows:
            tel = re.sub(r"\D", "", _safe(row, C_TELEFONO))
            if not tel:
                continue
            mapa.setdefault(tel, []).append({
                "folio":   _safe(row, C_FOLIO),
                "estatus": _safe(row, C_ESTATUS),
                "equipo":  _safe(row, C_EQUIPO),
            })
        return mapa
    except Exception as e:
        logger.warning(f"[CRM] Error cargando mapa de órdenes: {e}")
        return {}


def _ordenes_del_dia_sync() -> list[dict]:
    """Órdenes registradas hoy (CDMX)."""
    if not SHEET_ID:
        return []
    hoy = datetime.now(ZONA).strftime("%d/%m/%Y")
    try:
        svc  = _sheets_svc()
        rows = _iter_todas_las_ordenes_sync(svc)
        result = []
        for row in rows:
            if _safe(row, C_FECHA).startswith(hoy):
                result.append({
                    "folio":    _safe(row, C_FOLIO),
                    "cliente":  _safe(row, C_CLIENTE),
                    "equipo":   _safe(row, C_EQUIPO),
                    "total":    _safe(row, C_TOTAL),
                    "ganancia": _safe(row, C_GANANCIA),
                    "estatus":  _safe(row, C_ESTATUS),
                    "pago":     _safe(row, C_PAGO),
                })
        return result
    except Exception as e:
        logger.warning(f"[CRM] Error órdenes del día: {e}")
        return []


def _ordenes_por_estatus_sync(estatus: str) -> list[dict]:
    """Órdenes con un estatus específico (case-insensitive)."""
    if not SHEET_ID:
        return []
    try:
        svc  = _sheets_svc()
        rows = _iter_todas_las_ordenes_sync(svc)
        result = []
        for row in rows:
            if _safe(row, C_ESTATUS).lower() == estatus.lower():
                result.append({
                    "folio":    _safe(row, C_FOLIO),
                    "cliente":  _safe(row, C_CLIENTE),
                    "equipo":   _safe(row, C_EQUIPO),
                    "telefono": _safe(row, C_TELEFONO),
                    "total":    _safe(row, C_TOTAL),
                })
        return result
    except Exception as e:
        logger.warning(f"[CRM] Error órdenes por estatus: {e}")
        return []


def _subir_reporte_a_drive_sync(ruta_local: str) -> str:
    """Sube un archivo Excel a la carpeta raíz de Drive y retorna link público."""
    try:
        from googleapiclient.http import MediaFileUpload
        drive  = _drive_svc()
        nombre = os.path.basename(ruta_local)
        media  = MediaFileUpload(
            ruta_local,
            mimetype=(
                "application/vnd.openxmlformats-officedocument"
                ".spreadsheetml.sheet"
            ),
        )
        archivo = drive.files().create(
            body={"name": nombre, "parents": [DRIVE_ROOT_ID]},
            media_body=media,
            fields="id",
        ).execute()
        file_id = archivo["id"]
        drive.permissions().create(
            fileId=file_id,
            body={"type": "anyone", "role": "reader"},
        ).execute()
        link = f"https://drive.google.com/file/d/{file_id}/view"
        logger.info(f"[CRM] Reporte subido a Drive: {link}")
        return link
    except Exception as e:
        logger.error(f"[CRM] Error subiendo reporte a Drive: {e}")
        return ""


# ─── API pública (async) ──────────────────────────────────────────────────────

async def inicializar_crm():
    try:
        await asyncio.to_thread(_asegurar_bloque_inicial_sync)
        logger.info("[CRM] Bloques CRM listos")
    except Exception as e:
        logger.error(f"[CRM] Error inicializando: {e}")


async def registrar_orden(
    telefono: str, cliente: str,
    equipo: str, modelo: str, falla: str,
    total: float, forma_pago: str, refaccion: float = 0.0,
) -> dict:
    return await asyncio.to_thread(
        _registrar_sync,
        telefono, cliente, equipo, modelo, falla, total, forma_pago, refaccion,
    )


async def actualizar_estatus_orden(folio: str, nuevo_estatus: str) -> bool:
    return await asyncio.to_thread(_actualizar_estatus_sync, folio, nuevo_estatus)


async def consultar_orden(folio: str) -> dict | None:
    return await asyncio.to_thread(_consultar_sync, folio)


async def obtener_ordenes_facturables() -> list[dict]:
    return await asyncio.to_thread(_ordenes_facturables_sync)


async def obtener_mapa_ordenes_por_telefono() -> dict[str, list[dict]]:
    return await asyncio.to_thread(_mapa_ordenes_por_telefono_sync)


async def obtener_ordenes_del_dia() -> list[dict]:
    return await asyncio.to_thread(_ordenes_del_dia_sync)


async def obtener_ordenes_por_estatus(estatus: str) -> list[dict]:
    return await asyncio.to_thread(_ordenes_por_estatus_sync, estatus)


async def subir_reporte_a_drive(ruta_local: str) -> str:
    return await asyncio.to_thread(_subir_reporte_a_drive_sync, ruta_local)
