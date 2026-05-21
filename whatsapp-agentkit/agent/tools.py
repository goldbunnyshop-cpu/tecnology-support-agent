# agent/tools.py — Herramientas del agente para Tecnology Support
# Generado por AgentKit

"""
COTIZACIONES INTELIGENTES — Lógica principal
==============================================

Cuando un cliente pregunta por "precio de una pantalla" o similar:

1. NUNCA responde con un número fijo ($900, $500, etc)
2. SIEMPRE explica que el precio varía según:
   - Complejidad de la reparación
   - Marca y modelo exacto del dispositivo
   - Calidad de la refacción (genérica vs tipo original)
   - Estado del equipo (corrosión, daño colateral, etc)
   - Técnico que lo atienda (experiencia, disponibilidad)

3. SIEMPRE invita al módulo para diagnóstico:
   "El técnico hace un diagnóstico en ~2 horas y te da el precio exacto sin sorpresas"

4. SIEMPRE captura marca/modelo/daño para personalizar la invitación

Este enfoque genera CONFIANZA (no promesas vagas) y CONVERSIÓN
(cliente viene al módulo en lugar de comparar precios online).
"""

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
    "lunes_viernes": {
        "apertura": "10:00",
        "cierre": "21:00",
        "citas_apertura": "10:30",  # Media hora después de abrir
        "citas_cierre": "20:30",    # Media hora antes de cerrar
    },
    "sabado_domingo": {
        "apertura": "11:00",
        "cierre": "20:00",
        "citas_apertura": "11:30",  # Media hora después de abrir
        "citas_cierre": "19:30",    # Media hora antes de cerrar
    },
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

    if dia_semana <= 4:  # Lunes a Viernes
        apertura = 10.0        # 10:00 AM (abre)
        cierre = 21.0          # 9:00 PM (cierra)
        citas_apertura = 10.5  # 10:30 AM (primeras citas)
        citas_cierre = 20.5    # 8:30 PM (últimas citas)
        horario_texto = "Lunes a Viernes de 10:00am a 9:00pm"
    else:  # Sábado y Domingo
        apertura = 11.0        # 11:00 AM (abre)
        cierre = 20.0          # 8:00 PM (cierra)
        citas_apertura = 11.5  # 11:30 AM (primeras citas)
        citas_cierre = 19.5    # 7:30 PM (últimas citas)
        horario_texto = "Sábados y Domingos de 11:00am a 8:00pm"

    esta_abierto = apertura <= hora_actual < cierre

    return {
        "horario_texto": horario_texto,
        "esta_abierto": esta_abierto,
        "horario_completo": "Lunes a Viernes 10:00am–9:00pm · Sábados y Domingos 11:00am–8:00pm · Abiertos los 7 días",
        "horario_citas": f"{int(citas_apertura)}:{int((citas_apertura % 1) * 60):02d} – {int(citas_cierre)}:{int((citas_cierre % 1) * 60):02d}",
        "citas_apertura": citas_apertura,
        "citas_cierre": citas_cierre,
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
        "timestamp": datetime.now().isoformat(),
        "estado": "nuevo_lead",
    }
    logger.info(f"Lead registrado: {nombre} — {dispositivo} — {interes}")
    return lead


def fue_ultimo_mensaje_menu_ambiguo(historial: list[dict]) -> bool:
    """
    Detecta si el último mensaje del asistente fue el menú de dispositivos ambiguo.
    """
    if not historial:
        return False

    ultimo = historial[-1]
    if ultimo.get("role") != "assistant":
        return False

    contenido = ultimo.get("content", "").lower()
    palabras_clave = ["¿qué dispositivo", "cual dispositivo", "tipo de dispositivo", "celular", "laptop", "consola"]

    return any(palabra in contenido for palabra in palabras_clave) and "?" in contenido


def generar_respuesta_post_ambiguo() -> str:
    """
    Genera una respuesta alternativa cuando el cliente insiste siendo ambiguo
    después de que el bot ya mostró el menú una vez.
    """
    return (
        "Para poder ayudarte mejor, necesito saber qué dispositivo tienes:\n\n"
        "📱 *Celular* (iPhone, Samsung, Motorola, etc.)\n"
        "💻 *Laptop* (Windows, Mac, Linux)\n"
        "🎮 *Consola* (PS4, PS5, Xbox, Nintendo Switch)\n\n"
        "¿Cuál es tu dispositivo? Así te doy presupuesto exacto."
    )


def detectar_tipo_dispositivo_en_mensaje(mensaje: str, historial: list[dict] = None) -> str:
    """
    Detecta el tipo de dispositivo mencionado en el mensaje.
    Si no hay coincidencia clara, usa el dispositivo del historial.
    Si no hay historial, retorna 'ambiguo'.
    """
    mensaje_lower = mensaje.lower()

    # Palabras clave por dispositivo
    dispositivos = {
        "celular": ["iphone", "samsung", "motorola", "xiaomi", "huawei", "celular", "teléfono", "phone", "móvil", "android"],
        "laptop": ["laptop", "notebook", "macbook", "windows", "mac", "linux", "computadora", "pc", "thinkpad", "dell", "hp", "asus"],
        "consola": ["ps4", "ps5", "playstation", "xbox", "nintendo", "switch", "consola", "gaming"],
    }

    # Buscar coincidencias en el mensaje
    for tipo, palabras in dispositivos.items():
        if any(palabra in mensaje_lower for palabra in palabras):
            return tipo

    # Si no hay coincidencia clara, usar historial
    if historial:
        for msg in reversed(historial):
            if msg.get("role") == "user":
                for tipo, palabras in dispositivos.items():
                    if any(palabra in msg.get("content", "").lower() for palabra in palabras):
                        return tipo

    return "ambiguo"
