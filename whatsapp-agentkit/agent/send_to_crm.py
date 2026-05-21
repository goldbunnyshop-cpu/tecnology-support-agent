#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Integración: Agentkit → Auto-CRM

Envía datos de citas detectadas al sistema de notificaciones y transacciones
del Auto-CRM (Next.js/PostgreSQL).

Uso:
    from agent.send_to_crm import crear_transaccion_desde_cita, enviar_notificacion_whatsapp

    # Crear transacción en CRM
    transaction_id = await crear_transaccion_desde_cita(
        cliente_nombre="Juan",
        cliente_phone="+52123456789",
        dispositivo_marca="iPhone",
        dispositivo_modelo="14",
        descripcion="Pantalla rota",
        fecha_cita=datetime.now(),
        asesor="Sofia"
    )

    # Enviar notificación al cliente
    if transaction_id:
        await enviar_notificacion_whatsapp(
            transaction_id=transaction_id,
            cliente_phone="+52123456789",
            template_name="cita-agendada-whatsapp"
        )
"""

import os
import httpx
import logging
from datetime import datetime
from typing import Optional
from zoneinfo import ZoneInfo

logger = logging.getLogger("agentkit")

CRM_BASE_URL = os.getenv("CRM_API_URL", "http://localhost:3000/api")
CRM_API_KEY = os.getenv("CRM_API_KEY", "")

ZONA_CDMX = ZoneInfo("America/Mexico_City")


async def crear_transaccion_desde_cita(
    cliente_nombre: str,
    cliente_phone: str,
    dispositivo_marca: str,
    dispositivo_modelo: str,
    descripcion: str,
    fecha_cita: datetime,
    asesor: str = "Sofia",
) -> Optional[int]:
    """
    Crea una transacción en Auto-CRM desde una cita detectada en WhatsApp.

    Esta función sincroniza el appointment detectado por Agentkit con el
    sistema de CRM para que Christian pueda:
    - Ver la cita en el dashboard
    - Marcar como completada cuando esté lista
    - Triggear automáticamente notificaciones al cliente

    Args:
        cliente_nombre: Nombre del cliente (ej: "Juan Pérez")
        cliente_phone: Teléfono WhatsApp (ej: "+52123456789")
        dispositivo_marca: Marca del dispositivo (ej: "iPhone", "Samsung", "PS5")
        dispositivo_modelo: Modelo (ej: "14", "S23", "")
        descripcion: Descripción del problema (ej: "Pantalla rota")
        fecha_cita: datetime de cuándo está agendada
        asesor: Nombre del asesor asignado (default: "Sofia")

    Returns:
        ID de la transacción creada, o None si hubo error
    """

    logger.info(
        f"[SEND_TO_CRM] Creando transacción: {cliente_nombre} - "
        f"{dispositivo_marca} {dispositivo_modelo} - {fecha_cita.isoformat()}"
    )

    # Generar folio único (formato: YYYYMMDD-HHMM)
    folio_numero = int(fecha_cita.timestamp())

    # Preparar payload para Auto-CRM
    payload = {
        # Información del cliente
        "clienteName": cliente_nombre,
        "clientePhone": cliente_phone,

        # Información del dispositivo
        "marca": dispositivo_marca,
        "modelo": dispositivo_modelo,
        "descripcion": descripcion,

        # Información financiera (inicialmente 0)
        "saldoPendiente": 0,
        "costo": 0,
        "formaPago": "Pendiente",
        "total": 0,
        "gananciaReal": 0,

        # Metadata de origen y estado
        "source": "whatsapp",  # Identificar que viene de WhatsApp
        "citaProgramada": "Si",
        "citaConfirmada": "Si",
        "convertido": "No",
        "diasConversion": None,
    }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            headers = {}
            if CRM_API_KEY:
                headers["X-API-Key"] = CRM_API_KEY

            response = await client.post(
                f"{CRM_BASE_URL}/transactions",
                json=payload,
                headers=headers,
            )

            if response.status_code == 201:
                data = response.json()
                # El CRM retorna el ID en "id" o "folio"
                transaction_id = data.get("id") or data.get("folio")
                logger.info(
                    f"[SEND_TO_CRM] ✅ Transacción creada en CRM: {transaction_id} "
                    f"(Cliente: {cliente_nombre}, Tel: {cliente_phone})"
                )
                return transaction_id
            else:
                logger.error(
                    f"[SEND_TO_CRM] ❌ Error al crear transacción en CRM "
                    f"(Status {response.status_code}): {response.text}"
                )
                return None

    except httpx.TimeoutException:
        logger.error(
            f"[SEND_TO_CRM] ❌ Timeout conectando al CRM en {CRM_BASE_URL}"
        )
        return None
    except httpx.ConnectError:
        logger.error(
            f"[SEND_TO_CRM] ❌ No se puede conectar al CRM en {CRM_BASE_URL}. "
            f"Verifica que el servidor Next.js está corriendo."
        )
        return None
    except Exception as e:
        logger.error(
            f"[SEND_TO_CRM] ❌ Error inesperado al crear transacción: {type(e).__name__}: {e}"
        )
        return None


async def enviar_notificacion_whatsapp(
    transaction_id: int,
    cliente_phone: str,
    template_name: str = "cita-agendada-whatsapp",
    immediate: bool = True,
) -> bool:
    """
    Envía una notificación vía WhatsApp desde el sistema de Auto-CRM.

    La notificación se encola en PostgreSQL y será procesada por:
    1. El script procesar-notificaciones-whatsapp.ts cada 5 minutos
    2. Que llamará al endpoint /send-whatsapp de Agentkit
    3. Que enviará via Whapi.cloud al cliente

    Args:
        transaction_id: ID de la transacción creada en el paso anterior
        cliente_phone: Teléfono del cliente (ej: "+52123456789")
        template_name: Nombre del template a usar en Auto-CRM
            - "cita-agendada-whatsapp": Confirmación de cita agendada
            - "recordatorio-cita-24h": Recordatorio 24h antes
            - "reparacion-lista-whatsapp": Reparación completada
            - "recordatorio-seguimiento-whatsapp": Follow-up después de 7 días
        immediate: Si True, intenta enviar ahora. Si False, solo encola.

    Returns:
        True si la notificación se encoló exitosamente, False si hubo error
    """

    logger.info(
        f"[SEND_TO_CRM] Encolando notificación WhatsApp: "
        f"template={template_name}, transactionId={transaction_id}, "
        f"immediate={immediate}"
    )

    payload = {
        "transactionId": transaction_id,
        "templateId": template_name,
        "immediate": immediate,
    }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            headers = {"Content-Type": "application/json"}
            if CRM_API_KEY:
                headers["X-API-Key"] = CRM_API_KEY

            response = await client.post(
                f"{CRM_BASE_URL}/notifications/send",
                json=payload,
                headers=headers,
            )

            if response.status_code in [200, 201]:
                logger.info(
                    f"[SEND_TO_CRM] ✅ Notificación encolada para "
                    f"{cliente_phone} (template: {template_name})"
                )
                return True
            else:
                logger.error(
                    f"[SEND_TO_CRM] ❌ Error al enviar notificación "
                    f"(Status {response.status_code}): {response.text}"
                )
                return False

    except httpx.TimeoutException:
        logger.error(
            f"[SEND_TO_CRM] ❌ Timeout al enviar notificación al CRM"
        )
        return False
    except httpx.ConnectError:
        logger.error(
            f"[SEND_TO_CRM] ❌ No se puede conectar al CRM para enviar notificación"
        )
        return False
    except Exception as e:
        logger.error(
            f"[SEND_TO_CRM] ❌ Error inesperado al enviar notificación: "
            f"{type(e).__name__}: {e}"
        )
        return False


async def crear_y_notificar_desde_cita(
    cliente_nombre: str,
    cliente_phone: str,
    dispositivo_marca: str,
    dispositivo_modelo: str,
    descripcion: str,
    fecha_cita: datetime,
    asesor: str = "Sofia",
) -> dict:
    """
    Función de conveniencia que:
    1. Crea la transacción en Auto-CRM
    2. Envía automáticamente una notificación de confirmación

    Returns:
        {
            "success": bool,
            "transaction_id": int (si success=True),
            "notificacion_enviada": bool,
            "error": str (si success=False)
        }
    """

    logger.info(
        f"[SEND_TO_CRM] Iniciando flujo: crear_y_notificar "
        f"para {cliente_nombre} ({cliente_phone})"
    )

    # Paso 1: Crear transacción
    transaction_id = await crear_transaccion_desde_cita(
        cliente_nombre=cliente_nombre,
        cliente_phone=cliente_phone,
        dispositivo_marca=dispositivo_marca,
        dispositivo_modelo=dispositivo_modelo,
        descripcion=descripcion,
        fecha_cita=fecha_cita,
        asesor=asesor,
    )

    if not transaction_id:
        return {
            "success": False,
            "transaction_id": None,
            "notificacion_enviada": False,
            "error": "No se pudo crear la transacción en el CRM",
        }

    # Paso 2: Enviar notificación
    notif_enviada = await enviar_notificacion_whatsapp(
        transaction_id=transaction_id,
        cliente_phone=cliente_phone,
        template_name="cita-agendada-whatsapp",
        immediate=True,  # Encolar para procesar en los próximos 5 minutos
    )

    return {
        "success": True,
        "transaction_id": transaction_id,
        "notificacion_enviada": notif_enviada,
        "error": None,
    }
