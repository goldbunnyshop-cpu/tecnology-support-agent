#!/usr/bin/env python3
"""Test para verificar que el sistema de seguimientos está funcionando correctamente."""

import asyncio
import sys
import os
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from agent.memory import inicializar_db, async_session, guardar_mensaje
from agent.leads import (
    crear_o_actualizar_lead,
    obtener_leads_para_seguimiento,
    registrar_seguimiento_enviado,
    Lead,
)
from sqlalchemy import select


async def test_ciclo_seguimientos():
    """
    Simula el ciclo completo:
    1. Cliente envía mensaje
    2. Se crea el lead
    3. Pasa el tiempo (esperar 2h para primer seguimiento)
    4. Se envía el primer seguimiento
    5. Cliente responde
    6. Se verifica que seguimiento_realizado se haya reseteado
    """
    await inicializar_db()

    telefono = "+5512345678"
    print("=" * 70)
    print("TEST: Ciclo completo de seguimiento de leads")
    print("=" * 70)
    print()

    # PASO 1: Cliente envía un mensaje
    print("PASO 1: Cliente envía mensaje")
    print(f"  Crear lead: {telefono}")
    await crear_o_actualizar_lead(telefono, fuente="test", asesor_asignado="Sofia")

    # Verificar que se creó el lead
    async with async_session() as session:
        result = await session.execute(select(Lead).where(Lead.telefono == telefono))
        lead = result.scalar_one_or_none()
        print(f"  ✓ Lead creado")
        print(f"    - estado: {lead.estado}")
        print(f"    - seguimientos_enviados: {lead.seguimientos_enviados}")
        print(f"    - seguimiento_realizado: {lead.seguimiento_realizado}")
        print(f"    - ultimo_mensaje: {lead.ultimo_mensaje}")
        print()

    # PASO 2: Simular que pasaron 2+ horas
    print("PASO 2: Simular que pasaron 2+ horas")
    async with async_session() as session:
        result = await session.execute(select(Lead).where(Lead.telefono == telefono))
        lead = result.scalar_one_or_none()
        # Cambiar ultimo_mensaje a 2 horas atrás
        lead.ultimo_mensaje = datetime.utcnow() - timedelta(hours=2, minutes=1)
        await session.commit()
    print(f"  ✓ Actualizado último_mensaje a hace 2 horas")
    print()

    # PASO 3: Obtener leads que necesitan seguimiento
    print("PASO 3: Obtener leads para seguimiento")
    leads_para_seguimiento = await obtener_leads_para_seguimiento()
    print(f"  ✓ Encontrados {len(leads_para_seguimiento)} lead(s) para seguimiento")
    if leads_para_seguimiento:
        for lead in leads_para_seguimiento:
            print(f"    - {lead.telefono}: {lead.seguimientos_enviados} seguimientos enviados")
    print()

    # PASO 4: Registrar que se envió el seguimiento
    print("PASO 4: Simular envío del primer seguimiento")
    if leads_para_seguimiento:
        await registrar_seguimiento_enviado(telefono, prioridad="medio")
        async with async_session() as session:
            result = await session.execute(select(Lead).where(Lead.telefono == telefono))
            lead = result.scalar_one_or_none()
            print(f"  ✓ Seguimiento registrado")
            print(f"    - estado: {lead.estado}")
            print(f"    - seguimientos_enviados: {lead.seguimientos_enviados}")
            print(f"    - seguimiento_realizado: {lead.seguimiento_realizado}")
            print(f"    - seguimiento_enviado_en: {lead.seguimiento_enviado_en}")
            print()

    # PASO 5: Cliente responde
    print("PASO 5: Cliente responde al seguimiento")
    print(f"  Llamando crear_o_actualizar_lead() para actualizar lead...")
    await crear_o_actualizar_lead(telefono, asesor_asignado="Sofia")

    async with async_session() as session:
        result = await session.execute(select(Lead).where(Lead.telefono == telefono))
        lead = result.scalar_one_or_none()
        print(f"  ✓ Lead actualizado después de respuesta del cliente")
        print(f"    - estado: {lead.estado} (debería ser 'activo')")
        print(f"    - seguimientos_enviados: {lead.seguimientos_enviados} (debería ser 0)")
        print(f"    - seguimiento_realizado: {lead.seguimiento_realizado} (debería ser False)")
        print()

        # Verificación crítica
        if lead.estado == "activo" and lead.seguimientos_enviados == 0 and not lead.seguimiento_realizado:
            print("  ✅ ÉXITO: Lead se reseteó correctamente después de respuesta del cliente")
        else:
            print("  ❌ ERROR: Lead no se reseteó correctamente")
            print(f"     Estado: {lead.estado} != 'activo'")
            print(f"     Seguimientos: {lead.seguimientos_enviados} != 0")
            print(f"     Seguimiento realizado: {lead.seguimiento_realizado} != False")
    print()

    # PASO 6: Verificar que ahora puede recibir un nuevo seguimiento después de 2 horas
    print("PASO 6: Verificar que puede recibir nuevo seguimiento")
    async with async_session() as session:
        result = await session.execute(select(Lead).where(Lead.telefono == telefono))
        lead = result.scalar_one_or_none()
        # Cambiar ultimo_mensaje a 2 horas atrás del NUEVO tiempo actual
        lead.ultimo_mensaje = datetime.utcnow() - timedelta(hours=2, minutes=1)
        await session.commit()

    leads_para_seguimiento = await obtener_leads_para_seguimiento()
    print(f"  ✓ Encontrados {len(leads_para_seguimiento)} lead(s) para seguimiento")
    if telefono in [l.telefono for l in leads_para_seguimiento]:
        print(f"  ✅ ÉXITO: El lead {telefono} califica para nuevo seguimiento")
    else:
        print(f"  ❌ ERROR: El lead {telefono} NO califica para nuevo seguimiento")

    print()
    print("=" * 70)
    print("TEST COMPLETADO")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(test_ciclo_seguimientos())
