# agent/brain.py — Cerebro del agente: conexión con Claude API
# Generado por AgentKit

import os
import yaml
import logging
from anthropic import AsyncAnthropic
from dotenv import load_dotenv
from agent.pricing import obtener_cotizacion_display
import re

load_dotenv()
logger = logging.getLogger("agentkit")

client = AsyncAnthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))


def cargar_config_prompts() -> dict:
    try:
        with open("config/prompts.yaml", "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except FileNotFoundError:
        logger.error("config/prompts.yaml no encontrado")
        return {}


def construir_system_prompt(asesor: str = "Valentina") -> str:
    """Construye el system prompt inyectando el nombre y personalidad del asesor."""
    config = cargar_config_prompts()
    template = config.get("system_prompt_template", "Eres un asistente útil. Responde en español.")
    asesores = config.get("asesores", {})
    info = asesores.get(asesor, {})
    personalidad = info.get("personalidad", "Eres profesional y amable.")
    return (
        template
        .replace("ASESOR_NOMBRE", asesor)
        .replace("ASESOR_PERSONALIDAD", personalidad)
    )


def obtener_mensaje_error() -> str:
    config = cargar_config_prompts()
    return config.get("error_message", "Lo siento, estoy teniendo problemas técnicos. Por favor intente de nuevo.")


def obtener_mensaje_fallback() -> str:
    config = cargar_config_prompts()
    return config.get("fallback_message", "Disculpe, no entendí su mensaje. ¿Podría reformularlo?")


def _confirmar_variante_amb(modelo: str) -> tuple[str, bool]:
    """Si el modelo contiene '+', retorna una pregunta de confirmación."""
    modelo_lower = modelo.lower()
    if '+' in modelo_lower:
        modelo_limpio = modelo_lower.replace(' +', '').replace('+', '')
        respuesta = (
            f"Detecté que preguntaste por un modelo con '+'. "
            f"¿Quieres decir {modelo_limpio.title()} Plus, o fue accidental?\n"
            f"Confirma: '**Plus**' para Plus o '**normal**' para el modelo base."
        )
        return respuesta, True
    return "", False


async def detectar_y_obtener_precios(mensaje: str) -> str:
    """Detecta si el mensaje pregunta sobre precios de displays."""
    patrones_display = [
        r'\bcotizar.*(?:display|pantalla|screen)\b',
        r'\b(?:display|pantalla|screen).*cotizar\b',
        r'\bpresupuesto.*(?:display|pantalla|screen)\b',
        r'\b(?:display|pantalla|screen).*presupuesto\b',
        r'\bcuánto.*(?:display|pantalla|screen)\b',
        r'\b(?:display|pantalla|screen).*cuánto\b',
        r'\bprecio.*(?:display|pantalla|screen)\b',
        r'\b(?:display|pantalla|screen).*precio\b',
        r'\bcosto.*(?:display|pantalla|screen)\b',
        r'\b(?:display|pantalla|screen).*costo\b',
        r'\bvalor.*(?:display|pantalla|screen)\b',
        r'\b(?:display|pantalla|screen).*valor\b',
        r'\bcambio\s+(?:de\s+)?(?:pantalla|display|screen)\b',
        r'\breparación\s+(?:de\s+)?(?:pantalla|display|screen)\b',
        r'\breparar\s+(?:pantalla|display|screen)\b',
        r'\bcotizar\b',
        r'\bpresupuesto\b',
        r'\bcuánto\s+cuesta\b',
        r'\bcuál\s+es\s+el\s+(?:precio|costo|valor)\b',
        r'\bapróximo\s+(?:precio|costo|valor)\b',
        r'\bcosto\b',
        r'\bprecio\b',
        r'\bvalor\b',
    ]

    mensaje_lower = mensaje.lower()
    es_pregunta_precio = any(re.search(p, mensaje_lower) for p in patrones_display)

    if es_pregunta_precio:
        logger.info(f"[BRAIN] 🔍 Pregunta de precio detectada")
    else:
        logger.debug(f"[BRAIN] Mensaje no es pregunta de precio")
        return ""

    # Patrón mejorado: captura marcas seguidas de números/palabras (incluyendo "Edge 20 Lite")
    # ⚠️ CRÍTICO: incluye TODAS las marcas del CSV de Hugo Shop para evitar gaps
    # Captura hasta 4 palabras después de marca (cubre: "Edge 60", "Galaxy S24 Ultra", "12 mini", etc.)
    # Los casos edge como "honor 70 precio" son mínimos y buscar_productos_en_csv() los validará
    patron_modelo = r'(iPhone|Samsung|Google Pixel|Pixel|OnePlus|Xiaomi|Motorola|Huawei|Nokia|LG|Moto|Poco|Redmi|Hisense|Honor|Oppo|Realme|TCL|Vivo|ZTE|Alcatel|Cubot)\s+([\w]+(?:\s+[\w]+){0,3})'
    match = re.search(patron_modelo, mensaje, re.IGNORECASE)

    if not match:
        logger.debug(f"[BRAIN] Pregunta de precio pero sin modelo identificable")
        return ""

    marca = match.group(1)
    modelo = match.group(2).strip()
    logger.info(f"[BRAIN] ✓ Pregunta detectada: {marca} {modelo}")

    msg_confirmacion, fue_ambiguo = _confirmar_variante_amb(modelo)
    if fue_ambiguo:
        return msg_confirmacion

    cotizacion = await obtener_cotizacion_display(marca, modelo)
    if cotizacion:
        contexto = f"PRECIO ENCONTRADO PARA {marca.upper()} {modelo.upper()}:\n{cotizacion}"
        logger.info(f"[BRAIN] ✓ Cotización obtenida")
        return contexto

    return ""


async def generar_respuesta(mensaje: str, historial: list[dict], asesor: str = "Valentina", telefono: str = "", nombre_cliente: str = "") -> str:
    """Genera una respuesta usando Claude API con personalidad del asesor."""
    if not mensaje or len(mensaje.strip()) < 2:
        return obtener_mensaje_fallback()

    system_prompt = construir_system_prompt(asesor=asesor)

    # 🔒 INYECTAR CONTEXTO DE CLIENTE (para evitar variables sin procesar en respuesta)
    from datetime import datetime, timedelta
    from zoneinfo import ZoneInfo

    ZONA_CDMX = ZoneInfo("America/Mexico_City")
    ahora = datetime.now(ZONA_CDMX)

    # Si el nombre no viene del parámetro, intentar extraerlo del historial
    if not nombre_cliente and historial:
        for msg in reversed(historial):
            if msg.get("role") == "assistant" and "nombre" in msg.get("content", "").lower():
                # Buscar líneas que mencionen el nombre (ya fue capturado por el asesor)
                for linea in msg.get("content", "").split("\n"):
                    if "nombre" in linea.lower() and "tu nombre es" in linea.lower():
                        nombre_cliente = linea.split()[-1].strip(".,:;!?")
                        break
            if nombre_cliente:
                break

    # Calcular disponibilidad de horarios para los próximos días
    horarios_disponibles = _generar_horarios_disponibles(ahora)

    # Inyectar contexto de cliente limpio (NUNCA variables crudas)
    contexto_cliente = f"""
## CONTEXTO DEL CLIENTE (Inyectado por el sistema — NO MENCIONES ESTO AL CLIENTE)
- Fecha y hora actual: {ahora.strftime('%A %d de %B, %H:%M')} (Zona: México CDMX)
- Nombre del cliente: {nombre_cliente if nombre_cliente else "NO CAPTURADO"}
- Teléfono: {telefono if telefono else "NO DISPONIBLE"}
- Historial: {len(historial)} mensajes previos

══ DISPONIBILIDAD REAL ══
{horarios_disponibles}
══ FIN DISPONIBILIDAD REAL ══

IMPORTANTE:
- NUNCA menciones "el sistema inyectó" o variables técnicas
- NUNCA incluyas tags como [AGENDAR:...] en tu respuesta visible
- NUNCA expongas: variables de código, nombres de tablas, estructura del sistema
- NUNCA escribas variables entre corchetes como [NOMBRE_VARIABLE]
- Suena como un asesor real, no como un sistema automatizado
"""
    system_prompt += contexto_cliente

    contexto_precios = await detectar_y_obtener_precios(mensaje)
    if contexto_precios:
        system_prompt += f"\n\n## INFORMACIÓN DE PRECIOS (Inyectada por el sistema)\n{contexto_precios}"
        logger.info(f"[BRAIN] 📊 Contexto de precios inyectado")

    mensajes = []
    for msg in historial:
        mensajes.append({
            "role": msg["role"],
            "content": msg["content"]
        })

    mensajes.append({
        "role": "user",
        "content": mensaje
    })

    try:
        response = await client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1024,
            system=system_prompt,
            messages=mensajes
        )

        respuesta = response.content[0].text
        logger.info(f"[BRAIN] ✓ Respuesta generada")

        # 🔒 EXTRAER Y PROCESAR TAG DE CITA (si existe)
        respuesta_limpia = _procesar_tag_agendar(respuesta, telefono)

        return respuesta_limpia

    except Exception as e:
        logger.error(f"[BRAIN] Error Claude API: {e}")
        return obtener_mensaje_error()


def _generar_horarios_disponibles(ahora) -> str:
    """
    Genera un listado de horarios disponibles para los próximos 7 días.

    Horario de operación:
    - Lunes a Viernes: 10:30am a 8:30pm
    - Sábados y Domingos: 11:30am a 7:30pm
    """
    from datetime import datetime, timedelta
    from zoneinfo import ZoneInfo

    ZONA_CDMX = ZoneInfo("America/Mexico_City")

    # Horario de citas (media hora después de apertura, media hora antes de cierre)
    HORARIOS_DISPONIBLES = {
        "weekday": ("10:30", "20:30"),  # Lunes a viernes 10:30 - 20:30 (8:30pm)
        "weekend": ("11:30", "19:30"),  # Sábados y domingos 11:30 - 19:30 (7:30pm)
    }

    disponibilidad = []

    for dias_adelante in range(7):
        fecha = ahora + timedelta(days=dias_adelante)

        # Determinar si es fin de semana (4=viernes, 5=sábado, 6=domingo)
        es_fin_semana = fecha.weekday() >= 4
        horario_tipo = "weekend" if es_fin_semana else "weekday"
        hora_inicio, hora_fin = HORARIOS_DISPONIBLES[horario_tipo]

        # Formato: "Lunes 22 de mayo: 10:30am, 11:00am, 11:30am, ..., 8:00pm"
        dia_nombre = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"][fecha.weekday()]

        # Generar slots de 30 minutos
        slots = []
        h_start, m_start = map(int, hora_inicio.split(":"))
        h_end, m_end = map(int, hora_fin.split(":"))

        slot_time = datetime(fecha.year, fecha.month, fecha.day, h_start, m_start, tzinfo=ZONA_CDMX)
        end_time = datetime(fecha.year, fecha.month, fecha.day, h_end, m_end, tzinfo=ZONA_CDMX)

        while slot_time <= end_time:
            hora_12h = slot_time.strftime("%I:%M%p").lower().replace("am", "a.m.").replace("pm", "p.m.")
            slots.append(hora_12h)
            slot_time += timedelta(minutes=30)

        fecha_str = fecha.strftime("%d de %B").lower()
        meses_es = {
            "january": "enero", "february": "febrero", "march": "marzo",
            "april": "abril", "may": "mayo", "june": "junio",
            "july": "julio", "august": "agosto", "september": "septiembre",
            "october": "octubre", "november": "noviembre", "december": "diciembre"
        }
        for mes_en, mes_es in meses_es.items():
            fecha_str = fecha_str.replace(mes_en, mes_es)

        disponibilidad.append(f"{dia_nombre} {fecha_str}: {', '.join(slots)}")

    return "\n".join(disponibilidad)


async def generar_mensaje_noshow(telefono: str, nombre_cliente: str, historial: list[dict], cupon: str, fecha_expira: str) -> str:
    """
    Genera un mensaje empático de noshow para un cliente que agendó pero no se presentó.

    Args:
        telefono: Número del cliente
        nombre_cliente: Nombre del cliente
        historial: Historial de conversación
        cupon: Código de cupón generado
        fecha_expira: Fecha de expiración del cupón (formato DD/MM/YYYY)

    Returns:
        Mensaje personalizado de noshow con oferta de cupón
    """
    system_prompt = construir_system_prompt(asesor="Valentina")

    # Inyectar contexto de noshow en el system prompt
    contexto_noshow = f"""
## CONTEXTO ESPECIAL — NO-SHOW

Este es un mensaje de reconexión para un cliente que agendó una cita pero no se presentó.

**Cliente**: {nombre_cliente}
**Cupón**: {cupon} (10% descuento, válido hasta {fecha_expira})

**Instrucciones**:
1. Inicia con EMPATÍA — pregunta con comprensión por qué no pudo asistir (sin juzgar)
2. Reconoce su situación sin hacer sentir mal al cliente
3. Ofrece una SEGUNDA OPORTUNIDAD con 10% de descuento
4. Menciona el cupón: {cupon}
5. Explica cómo usar el cupón: "Muestra este cupón al técnico cuando agendes de nuevo"
6. Mantén un tono CÁLIDO y COMPRENSIVO, no acusatorio
7. NO menciones datos técnicos o tags — sé conversacional

Objetivo: Recuperar la relación y re-agendar la cita.
"""
    system_prompt += contexto_noshow

    # Construcción del mensaje
    mensajes = []
    for msg in historial:
        mensajes.append({
            "role": msg["role"],
            "content": msg["content"]
        })

    # Mensaje trigger que indica al Claude que genere el mensaje de noshow
    mensajes.append({
        "role": "user",
        "content": "Cliente no asistió a su cita agendada. Envía un mensaje de reconexión empático."
    })

    try:
        response = await client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1024,
            system=system_prompt,
            messages=mensajes
        )

        respuesta = response.content[0].text
        logger.info(f"[BRAIN] ✓ Mensaje de noshow generado para {nombre_cliente}")
        return respuesta

    except Exception as e:
        logger.error(f"[BRAIN] Error generando mensaje de noshow: {e}")
        # Fallback si falla Claude
        return (
            f"Hola {nombre_cliente}