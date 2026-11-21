# agent/aviso_citas_hoy.py — Aviso masivo a las citas de HOY (cambio de horario por fuerza mayor)
#
# Uso (vía endpoint /admin/avisar-citas-hoy):
#   - Por defecto es DRY-RUN: solo lista a quién se enviaría.
#   - Con confirmar=true envía el mensaje a cada cliente con cita hoy.
#
# Fuentes de citas (se unen y se deduplican por teléfono):
#   1) Google Calendar (eventos del día)
#   2) Tabla `citas` (detectadas automáticamente)

import asyncio
import logging
import random
import re
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import text

logger = logging.getLogger("agentkit")

ZONA_CDMX = ZoneInfo("America/Mexico_City")

# Hora a partir de la cual se atiende hoy
HORA_INICIO = time(13, 0)
TEXTO_HORARIO = "de 1:00 pm a 8:00 pm"

# Anti-duplicados en memoria: {(fecha_iso, ultimos10)}
_ENVIADOS: set[tuple[str, str]] = set()


def _ultimos10(tel: str) -> str:
    digitos = re.sub(r"\D", "", tel or "")
    return digitos[-10:] if len(digitos) >= 10 else ""


def _destino_whapi(tel: str) -> str:
    """Normaliza a dígitos con lada de país. 10 dígitos -> prefijo 52."""
    digitos = re.sub(r"\D", "", tel or "")
    if len(digitos) == 10:
        return "52" + digitos
    return digitos


def _parsear_hora_txt(hora_txt: str) -> time | None:
    """'11:30 a.m.' / '1:00 p.m.' -> time."""
    m = re.match(r"\s*(\d{1,2}):(\d{2})\s*([ap])", (hora_txt or "").lower())
    if not m:
        return None
    h, mi, ampm = int(m.group(1)), int(m.group(2)), m.group(3)
    if ampm == "p" and h != 12:
        h += 12
    if ampm == "a" and h == 12:
        h = 0
    return time(h, mi)


def _hora_bonita(t: time | None) -> str:
    if not t:
        return ""
    h12 = t.hour % 12 or 12
    return f"{h12}:{t.minute:02d} {'am' if t.hour < 12 else 'pm'}"


def construir_mensaje(nombre: str, hora: time | None) -> str:
    nombre = (nombre or "").strip()
    saludo = f"Hola {nombre.title()} 👋" if nombre and nombre.lower() != "cliente" else "Hola 👋"
    base = (
        f"{saludo} Te avisamos de Tecnology Support: por causas de fuerza mayor "
        f"el día de hoy estaremos atendiendo {TEXTO_HORARIO}."
    )
    if hora and hora < HORA_INICIO:
        detalle = (
            f"\n\nTu cita de hoy era a las {_hora_bonita(hora)}; te pedimos pasar a partir de la "
            f"1:00 pm. Si prefieres reagendar para otro día, solo respóndenos por aquí."
        )
    else:
        detalle = (
            f"\n\nTu cita de hoy"
            + (f" ({_hora_bonita(hora)})" if hora else "")
            + " se mantiene dentro de ese horario. Si prefieres reagendar, solo respóndenos por aquí."
        )
    return base + detalle + "\n\nOfrecemos una disculpa por las molestias 🙏"


async def _citas_calendar(hoy) -> list[dict]:
    try:
        from agent.google_calendar import obtener_eventos_del_dia
        eventos = await obtener_eventos_del_dia(hoy)
    except Exception as e:
        logger.warning(f"[AVISO-HOY] Error leyendo Google Calendar: {e}")
        return []
    return [
        {
            "nombre": ev.get("nombre", ""),
            "telefono": ev.get("telefono", ""),
            "hora": _parsear_hora_txt(ev.get("hora", "")),
            "fuente": "calendar",
        }
        for ev in eventos
    ]


async def _citas_tabla(hoy) -> list[dict]:
    from agent.memory import async_session
    inicio = datetime(hoy.year, hoy.month, hoy.day, 0, 0)
    fin = inicio + timedelta(days=1)
    try:
        async with async_session() as session:
            r = await session.execute(
                text(
                    "SELECT nombre, telefono, fecha_hora FROM citas "
                    "WHERE fecha_hora >= :ini AND fecha_hora < :fin"
                ),
                {"ini": inicio, "fin": fin},
            )
            filas = r.fetchall()
    except Exception as e:
        logger.warning(f"[AVISO-HOY] Error leyendo tabla citas: {e}")
        return []
    out = []
    for nombre, tel, fh in filas:
        if isinstance(fh, str):
            try:
                fh = datetime.fromisoformat(fh)
            except Exception:
                fh = None
        out.append(
            {"nombre": nombre or "", "telefono": tel or "", "hora": fh.time() if fh else None, "fuente": "tabla"}
        )
    return out


async def obtener_destinatarios() -> tuple[list[dict], list[dict]]:
    """Retorna (con_telefono_unicos, sin_telefono) para las citas de hoy."""
    hoy = datetime.now(ZONA_CDMX).date()
    todas = (await _citas_calendar(hoy)) + (await _citas_tabla(hoy))

    vistos: dict[str, dict] = {}
    sin_tel: list[dict] = []
    for c in todas:
        clave = _ultimos10(c["telefono"])
        if not clave:
            sin_tel.append(c)
            continue
        # Si el mismo teléfono viene de dos fuentes, nos quedamos con la que trae hora
        if clave not in vistos or (vistos[clave]["hora"] is None and c["hora"] is not None):
            vistos[clave] = c
    return list(vistos.values()), sin_tel


async def avisar_citas_hoy(proveedor, confirmar: bool = False) -> dict:
    """Envía (o simula) el aviso a todas las citas de hoy."""
    hoy_iso = datetime.now(ZONA_CDMX).date().isoformat()
    destinatarios, sin_tel = await obtener_destinatarios()

    resultado = {
        "modo": "ENVIO" if confirmar else "DRY-RUN",
        "fecha": hoy_iso,
        "total_con_telefono": len(destinatarios),
        "sin_telefono": [f"{c['nombre']} ({_hora_bonita(c['hora'])})" for c in sin_tel],
        "enviados": [],
        "omitidos_ya_enviados": [],
        "fallidos": [],
        "ejemplo_mensaje": construir_mensaje(
            destinatarios[0]["nombre"] if destinatarios else "Juan",
            destinatarios[0]["hora"] if destinatarios else time(11, 30),
        ),
        "destinatarios": [
            {"nombre": c["nombre"], "telefono": _destino_whapi(c["telefono"]), "hora": _hora_bonita(c["hora"])}
            for c in destinatarios
        ],
    }
    if not confirmar:
        return resultado

    from agent.memory import guardar_mensaje

    for c in destinatarios:
        clave = (hoy_iso, _ultimos10(c["telefono"]))
        etiqueta = f"{c['nombre']} ({_hora_bonita(c['hora'])})"
        if clave in _ENVIADOS:
            resultado["omitidos_ya_enviados"].append(etiqueta)
            continue
        destino = _destino_whapi(c["telefono"])
        msg = construir_mensaje(c["nombre"], c["hora"])
        try:
            ok = await proveedor.enviar_mensaje(destino, msg)
        except Exception as e:
            logger.error(f"[AVISO-HOY] Error enviando a {destino}: {e}")
            ok = False
        if ok:
            _ENVIADOS.add(clave)
            resultado["enviados"].append(etiqueta)
            try:
                # Para que el bot sepa qué se le dijo al cliente si responde
                await guardar_mensaje(destino, "assistant", msg)
            except Exception as e:
                logger.warning(f"[AVISO-HOY] No se guardó en historial {destino}: {e}")
        else:
            resultado["fallidos"].append(etiqueta)
        # Pausa aleatoria entre envíos para no parecer spam
        await asyncio.sleep(random.uniform(4, 9))

    logger.info(
        f"[AVISO-HOY] enviados={len(resultado['enviados'])} "
        f"fallidos={len(resultado['fallidos'])} omitidos={len(resultado['omitidos_ya_enviados'])}"
    )
    return resultado
