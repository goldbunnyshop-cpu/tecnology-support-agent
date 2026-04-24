# agent/tools.py — Herramientas del agente para Tecnology Support
# Generado por AgentKit

import os
import yaml
import logging
from datetime import datetime

logger = logging.getLogger("agentkit")

# Precios base de referencia (multiplicar por 3 para precio final al cliente)
SERVICIOS_DIAGNOSTICO = {
    "costo": 200,
    "moneda": "MXN",
    "tiempo_horas": 2,
    "bonificable": True,
    "descripcion": "Diagnóstico físico del dispositivo. Se bonifica si acepta la reparación."
}

CALIDADES_REFACCION = ["Genérica", "Tipo original"]

UBICACION = "https://maps.app.goo.gl/XdCSu743LpyY6aAt7"

HORARIO = {
    "lunes_viernes": {"apertura": "10:00", "cierre": "21:00"},
    "sabado_domingo": {"apertura": "11:00", "cierre": "20:00"},
}


def cargar_info_negocio() -> dict:
    """Carga la información del negocio desde business.yaml."""
    try:
        with open("config/business.yaml", "r", encoding="utf-8") as f:
            return yaml.safe_load(f)
    except FileNotFoundError:
        logger.error("config/business.yaml no encontrado")
        return {}


def obtener_horario() -> dict:
    """Retorna el horario de atención del negocio y si está abierto ahora."""
    ahora = datetime.now()
    dia_semana = ahora.weekday()  # 0=lunes, 6=domingo
    hora_actual = ahora.hour + ahora.minute / 60

    if dia_semana < 5:  # Lunes a Viernes
        apertura = 10.0
        cierre = 21.0
        horario_texto = "Lunes a Viernes de 10:00am a 9:00pm"
    else:  # Sábado y Domingo
        apertura = 11.0
        cierre = 20.0
        horario_texto = "Sábados y Domingos de 11:00am a 8:00pm"

    esta_abierto = apertura <= hora_actual < cierre

    return {
        "horario_texto": horario_texto,
        "esta_abierto": esta_abierto,
        "horario_completo": "Lunes a Viernes de 10:00am a 9:00pm / Sábados y Domingos de 11:00am a 8:00pm",
    }


def obtener_info_diagnostico() -> dict:
    """Retorna información sobre el diagnóstico físico."""
    return {
        "costo": "$200 MXN",
        "tiempo": "Aproximadamente 2 horas",
        "bonificacion": "Si acepta el presupuesto de reparación, el diagnóstico es gratuito",
        "ubicacion": UBICACION,
    }


def obtener_calidades_disponibles() -> list[str]:
    """Retorna las calidades de refacciones disponibles."""
    return CALIDADES_REFACCION


def buscar_en_knowledge(consulta: str) -> str:
    """
    Busca información relevante en los archivos de /knowledge.
    Retorna el contenido más relevante encontrado.
    """
    resultados = []
    knowledge_dir = "knowledge"

    if not os.path.exists(knowledge_dir):
        return "No hay archivos de conocimiento disponibles."

    for archivo in os.listdir(knowledge_dir):
        ruta = os.path.join(knowledge_dir, archivo)
        if archivo.startswith(".") or not os.path.isfile(ruta):
            continue
        try:
            with open(ruta, "r", encoding="utf-8") as f:
                contenido = f.read()
                if consulta.lower() in contenido.lower():
                    resultados.append(f"[{archivo}]: {contenido[:500]}")
        except (UnicodeDecodeError, IOError):
            continue

    if resultados:
        return "\n---\n".join(resultados)
    return "No encontré información específica sobre eso en mis archivos."


def registrar_solicitud_cita(telefono: str, nombre: str, dispositivo: str, problema: str, fecha_preferencia: str) -> dict:
    """
    Registra la solicitud de cita de un cliente.
    Retorna confirmación con los datos registrados.
    """
    cita = {
        "telefono": telefono,
        "nombre": nombre,
        "dispositivo": dispositivo,
        "problema": problema,
        "fecha_preferencia": fecha_preferencia,
        "costo_diagnostico": "$200 MXN (bonificable)",
        "ubicacion": UBICACION,
        "estado": "pendiente_confirmacion",
    }
    logger.info(f"Cita solicitada: {nombre} — {dispositivo} — {fecha_preferencia}")
    return cita


def registrar_lead(telefono: str, nombre: str, dispositivo: str, interes: str) -> dict:
    """
    Registra un lead de cliente interesado en el servicio.
    """
    lead = {
        "telefono": telefono,
        "nombre": nombre,
        "dispositivo": dispositivo,
        "interes": interes,
        "fecha_registro": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "estado": "nuevo",
    }
    logger.info(f"Lead registrado: {nombre} — {dispositivo}")
    return lead


def escalar_a_tecnico(telefono: str, motivo: str) -> str:
    """
    Marca una conversación para escalamiento al técnico.
    Se usa para servicios de software, soporte post-venta complejo o cotizaciones especiales.
    """
    logger.info(f"Escalamiento requerido: {telefono} — Motivo: {motivo}")
    return (
        "He registrado su consulta y un técnico especializado le contactará a la brevedad. "
        "También puede acudir directamente a nuestro módulo de reparación: "
        f"{UBICACION}"
    )
