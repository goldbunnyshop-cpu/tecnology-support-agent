#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Detector automático de citas en mensajes de WhatsApp.
Analiza mensajes entrantes, detecta patrones de citas y las guarda automáticamente.
"""

import logging
import re
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from typing import Optional
import os
import asyncio

from anthropic import AsyncAnthropic
from agent.reminder_scheduler import manejar_cita_confirmada
from agent.send_to_crm import crear_y_notificar_desde_cita

logger = logging.getLogger("agentkit")

ZONA_CDMX = ZoneInfo("America/Mexico_City")

# Cliente de Anthropic para análisis inteligente de citas
client = AsyncAnthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

MESES_ES = {
    1: "enero", 2: "febrero", 3: "marzo", 4: "abril", 5: "mayo", 6: "junio",
    7: "julio", 8: "agosto", 9: "septiembre", 10: "octubre", 11: "noviembre", 12: "diciembre"
}

DIAS_ES = {
    0: "lunes", 1: "martes", 2: "miércoles", 3: "jueves",
    4: "viernes", 5: "sábado", 6: "domingo"
}


async def analizar_mensaje_para_cita(mensaje: str, contexto_historial: list[dict] = None) -> Optional[dict]:
    """
    Usa Claude para analizar si un mensaje contiene intención de agendar una cita.

    Args:
        mensaje: Texto del mensaje de WhatsApp
        contexto_historial: Historial previo de la conversación

    Returns:
        Dict con campos extraídos si es cita, None si no lo es
    """

    prompt = f"""Analiza este mensaje de WhatsApp de un cliente que quiere agendar una cita de reparación.

MENSAJE DEL CLIENTE:
"{mensaje}"

Por favor, identifica si el cliente está intentando agendar una cita para reparación.
Si SÍ es una cita, extrae EXACTAMENTE estos datos (si no están claros, marca como "NO ESPECIFICADO"):

1. NOMBRE_CLIENTE: Nombre del cliente (ej: "Juan", "Maria García")
2. DISPOSITIVO: Qué dispositivo necesita reparación (ej: "iPhone 14", "PS5", "Laptop Dell")
3. PROBLEMA: Qué problema tiene el dispositivo (ej: "pantalla rota", "no enciende", "batería muerta")
4. FECHA_PROPUESTA: Fecha sugerida en formato "Día # de mes, HH:MM" (ej: "Sábado 18 de mayo, 10:00 a.m.")
5. ASESOR_SOLICITADO: Si el cliente mencionó un asesor específico (ej: "Sofia", "Camila")

SI el mensaje NO contiene intención clara de agendar, responde solo: "NO_ES_CITA"

Responde EXACTAMENTE en este formato:
ES_CITA: SÍ | NO
NOMBRE_CLIENTE: [nombre o "NO ESPECIFICADO"]
DISPOSITIVO: [dispositivo o "NO ESPECIFICADO"]
PROBLEMA: [problema o "NO ESPECIFICADO"]
FECHA_PROPUESTA: [fecha hora o "NO ESPECIFICADO"]
ASESOR_SOLICITADO: [asesor o "CUALQUIERA"]
CONFIANZA: [ALTA | MEDIA | BAJA]
"""

    try:
        response = await client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=500,
            messages=[{"role": "user", "content": prompt}]
        )

        respuesta = response.content[0].text
        logger.info(f"[CITA_DETECTOR] Análisis Claude: {respuesta[:100]}")

        if "NO_ES_CITA" in respuesta:
            return None

        if "ES_CITA: NO" in respuesta:
            return None

        # Parsear respuesta
        campos = {}
        for linea in respuesta.split("\n"):
            if ":" in linea:
                clave, valor = linea.split(":", 1)
                clave = clave.strip().upper()
                valor = valor.strip()
                campos[clave] = valor

        if campos.get("ES_CITA") == "SÍ":
            return campos

        return None

    except Exception as e:
        logger.error(f"[CITA_DETECTOR] Error analizando con Claude: {e}")
        return None


def _parsear_fecha_hora_flexible(fecha_str: str) -> Optional[datetime]:
    """
    Parsea fechas en español con mayor flexibilidad.
    Soporta formatos como: "Sábado 18 de mayo, 10:00 a.m."

    VALIDACIONES:
    - NUNCA agendar citas en el pasado
    - Máximo 365 días en el futuro
    - NUNCA agendar con años anteriores al actual
    """
    if not fecha_str or "NO ESPECIFICADO" in fecha_str:
        return None

    try:
        # Normalizar espacios y caso
        fecha_str = fecha_str.strip().lower()

        # Crear mapeo inverso de meses
        meses_inversos = {v.lower(): k for k, v in MESES_ES.items()}

        # Buscar patrón: "número de mes_nombre, hora:minutos a/pm"
        patron = r"(\d{1,2})\s+de\s+(\w+),?\s+(\d{1,2}):(\d{2})\s*(a\.?m\.?|p\.?m\.?)"
        match = re.search(patron, fecha_str)

        if not match:
            return None

        dia_num = int(match.group(1))
        mes_name = match.group(2).lower()
        hora = int(match.group(3))
        minuto = int(match.group(4))
        ampm = match.group(5).lower()

        # Resolver mes
        mes_num = meses_inversos.get(mes_name)
        if not mes_num:
            return None

        # Resolver hora
        if "p" in ampm and hora != 12:
            hora += 12
        elif "a" in ampm and hora == 12:
            hora = 0

        # Resolver año (VALIDACIÓN: NUNCA años pasados)
        ahora = datetime.now(ZONA_CDMX)
        año = ahora.year

        try:
            fecha = datetime(año, mes_num, dia_num, hora, minuto, 0, tzinfo=ZONA_CDMX)

            # 🐛 FIX CRÍTICO: Si la fecha propuesta ya pasó este año, usar el PRÓXIMO año
            if fecha < ahora:
                fecha = datetime(año + 1, mes_num, dia_num, hora, minuto, 0, tzinfo=ZONA_CDMX)

            # VALIDACIÓN ADICIONAL: Máximo 365 días en el futuro (evitar errores de entrada)
            fecha_maxima = ahora + timedelta(days=365)
            if fecha > fecha_maxima:
                logger.warning(
                    f"[CITA_DETECTOR] Fecha rechazada (más de 365 días): {fecha.isoformat()}. "
                    f"Ahora: {ahora.isoformat()}"
                )
                return None

            # VALIDACIÓN FINAL: Asegurar que NO sea en el pasado
            if fecha < ahora:
                logger.error(
                    f"[CITA_DETECTOR] ❌ BUG DETECTADO: Fecha resultó en el pasado. "
                    f"Fecha: {fecha.isoformat()}, Ahora: {ahora.isoformat()}"
                )
                return None

            logger.info(f"[CITA_DETECTOR] Fecha parseada correctamente: {fecha.isoformat()}")
            return fecha

        except ValueError as ve:
            logger.warning(f"[CITA_DETECTOR] Fecha inválida (ValueError): {ve}")
            return None

    except Exception as e:
        logger.debug(f"[CITA_DETECTOR] Error parseando fecha '{fecha_str}': {e}")
        return None


async def guardar_cita_automatica(
    nombre: str,
    dispositivo: str,
    problema: str,
    fecha_hora: datetime,
    asesor: str = "ASIGNADO",
    telefono: str = "",
):
    """
    Guarda una cita automáticamente detectada en PostgreSQL.
    """
    logger.info(
        f"[CITA_DETECTOR] ▶ guardar_cita_automatica iniciada "
        f"(nombre={nombre!r} tel={telefono!r} dispositivo={dispositivo!r} "
        f"fecha_hora={fecha_hora.isoformat() if fecha_hora else None} asesor={asesor!r})"
    )
    try:
        from agent.memory import async_session, DATABASE_URL

        # Log qué BD estamos usando (sin exponer credenciales)
        db_kind = "PostgreSQL" if "postgresql" in DATABASE_URL else ("SQLite" if "sqlite" in DATABASE_URL else "desconocido")
        logger.info(f"[CITA_DETECTOR] BD destino: {db_kind}")

        # Crear evento en Google Calendar si está configurado (no crítico)
        try:
            from agent.google_calendar_sync import agregar_cita_a_calendar

            fecha_str = fecha_hora.strftime("%Y-%m-%d")
            hora_str = fecha_hora.strftime("%H:%M")

            await agregar_cita_a_calendar(
                nombre_cliente=nombre,
                dispositivo=dispositivo,
                problema=problema,
                fecha_str=fecha_str,
                hora_str=hora_str,
                asesor=asesor
            )
        except Exception as cal_e:
            logger.warning(f"[CITA_DETECTOR] Google Calendar saltado (no crítico): {cal_e}")

        # Guardar en PostgreSQL directamente con SQLAlchemy
        logger.info("[CITA_DETECTOR] Abriendo sesión SQLAlchemy…")
        async with async_session() as session:
            from sqlalchemy import text
            query = text("""
                INSERT INTO citas (nombre, telefono, dispositivo, problema, fecha_hora, asesor, fuente)
                VALUES (:nombre, :telefono, :dispositivo, :problema, :fecha_hora, :asesor, :fuente)
            """)
            params = {
                "nombre": nombre,
                "telefono": telefono,
                "dispositivo": dispositivo,
                "problema": problema,
                "fecha_hora": fecha_hora,
                "asesor": asesor,
                "fuente": "automatica",
            }
            logger.info(f"[CITA_DETECTOR] Ejecutando INSERT con params={params}")
            await session.execute(query, params)
            await session.commit()
            logger.info("[CITA_DETECTOR] COMMIT exitoso")

        logger.info(
            f"[CITA_DETECTOR] ✅ Cita guardada en {db_kind}: "
            f"{nombre} — {fecha_hora.strftime('%d/%m %H:%M')} — tel={telefono}"
        )

        # ✅ NUEVO: Programar recordatorios inteligentes (24h, 90min, 10min)
        try:
            from agent.providers import obtener_proveedor
            fecha_str = fecha_hora.strftime("%Y-%m-%d")
            hora_str = fecha_hora.strftime("%H:%M")
            proveedor = obtener_proveedor()

            await manejar_cita_confirmada(
                telefono=telefono,
                fecha_cita=fecha_str,
                hora_cita=hora_str,
                nombre_cliente=nombre,
                proveedor_whatsapp=proveedor
            )
            logger.info(f"[CITA_DETECTOR] ✓ Recordatorios inteligentes programados para {nombre}")
        except Exception as rem_e:
            logger.warning(f"[CITA_DETECTOR] Recordatorios no programados (no crítico): {rem_e}")

        return True

    except Exception as e:
        logger.error(f"[CITA_DETECTOR] ❌ Error guardando cita: {type(e).__name__}: {e}")
        import traceback
        logger.error(f"[CITA_DETECTOR] Traceback:\n{traceback.format_exc()}")
        return False


# DEPRECATED: Función reemplazada por google_calendar_sync.agregar_cita_a_calendar()
# Ver: agent/google_calendar_sync.py


async def procesar_mensaje_para_cita(
    mensaje: str,
    telefono: str = "",
    historial: list[dict] = None
) -> dict:
    """
    Función principal que llamará agent/main.py para procesar citas automáticas.

    Returns:
        {"es_cita": bool, "cita": {...}, "mensaje_respuesta": str}
    """

    # Analizar el mensaje con Claude
    analisis = await analizar_mensaje_para_cita(mensaje, historial)

    if not analisis:
        return {
            "es_cita": False,
            "mensaje_respuesta": None
        }

    # Extraer y validar datos
    nombre = analisis.get("NOMBRE_CLIENTE", "").replace("NO ESPECIFICADO", "Cliente").strip()
    dispositivo = analisis.get("DISPOSITIVO", "").replace("NO ESPECIFICADO", "Dispositivo").strip()
    problema = analisis.get("PROBLEMA", "").replace("NO ESPECIFICADO", "Problema").strip()
    fecha_str = analisis.get("FECHA_PROPUESTA", "")
    asesor = analisis.get("ASESOR_SOLICITADO", "ASIGNADO").strip()
    confianza = analisis.get("CONFIANZA", "MEDIA")

    # Parsear fecha
    fecha_hora = _parsear_fecha_hora_flexible(fecha_str)

    if not fecha_hora:
        logger.warning(f"[CITA_DETECTOR] No se pudo parsear fecha: {fecha_str}")
        return {
            "es_cita": False,
            "mensaje_respuesta": "❌ No entendí bien la fecha/hora. Por favor especifica: 'Quiero agendar para [día] de [mes] a las [hora]'"
        }

    # Si la confianza es baja, pedir confirmación al usuario
    if confianza == "BAJA":
        return {
            "es_cita": True,
            "requiere_confirmacion": True,
            "datos_extraidos": {
                "nombre": nombre,
                "dispositivo": dispositivo,
                "problema": problema,
                "fecha_hora": fecha_hora,
                "asesor": asesor,
            },
            "mensaje_respuesta": f"✅ Detecté tu cita:\n👤 {nombre}\n📱 {dispositivo}\n⏰ {fecha_hora.strftime('%A %d de %B, %H:%M')}\n\n¿Es correcto? (sí/no)"
        }

    # Guardar la cita automáticamente si confianza es ALTA o MEDIA
    exito = await guardar_cita_automatica(
        nombre=nombre,
        dispositivo=dispositivo,
        problema=problema,
        fecha_hora=fecha_hora,
        asesor=asesor,
        telefono=telefono
    )

    if exito:
        fecha_formateada = fecha_hora.strftime("%A %d de %B, %H:%M").replace(
            "Monday", "lunes"
        ).replace(
            "Tuesday", "martes"
        ).replace(
            "Wednesday", "miércoles"
        ).replace(
            "Thursday", "jueves"
        ).replace(
            "Friday", "viernes"
        ).replace(
            "Saturday", "sábado"
        ).replace(
            "Sunday", "domingo"
        )

        # 🔗 INTEGRACIÓN AUTO-CRM: Crear transacción y enviar notificación
        logger.info(f"[CITA_DETECTOR] 🔗 Iniciando integración con Auto-CRM para {nombre}")
        try:
            crm_result = await crear_y_notificar_desde_cita(
                cliente_nombre=nombre,
                cliente_phone=telefono,
                dispositivo_marca=dispositivo.split()[0] if dispositivo else "Dispositivo",  # Primera palabra (marca)
                dispositivo_modelo=dispositivo.split()[1] if len(dispositivo.split()) > 1 else "",
                descripcion=problema,
                fecha_cita=fecha_hora,
                asesor=asesor,
            )

            if crm_result["success"]:
                logger.info(
                    f"[CITA_DETECTOR] ✅ Cita vinculada a Auto-CRM "
                    f"(Transaction ID: {crm_result['transaction_id']})"
                )
            else:
                logger.warning(
                    f"[CITA_DETECTOR] ⚠️ No se pudo vincular con Auto-CRM: "
                    f"{crm_result['error']}"
                )
        except Exception as crm_e:
            logger.warning(
                f"[CITA_DETECTOR] ⚠️ Error integrando con Auto-CRM (no crítico): {crm_e}"
            )

        return {
            "es_cita": True,
            "guardada": True,
            "datos": {
                "nombre": nombre,
                "dispositivo": dispositivo,
                "problema": problema,
                "fecha_hora": fecha_hora,
                "asesor": asesor,
            },
            "mensaje_respuesta": f"✅ *CITA AGENDADA*\n\n👤 {nombre}\n📱 {dispositivo}\n⏰ {fecha_formateada}\n⚠️ {problema}\n👨‍💼 Asesor: {asesor}\n\nTe confirmaremos en breve."
        }
    else:
        return {
            "es_cita": True,
            "guardada": False,
            "mensaje_respuesta": "❌ Hubo un error guardando tu cita. Por favor intenta de nuevo o contacta a soporte."
        }
