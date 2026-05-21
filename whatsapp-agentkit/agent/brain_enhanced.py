# agent/brain.py — Cerebro del agente con lógica de cotización de precios
# Generado por AgentKit + Pricing System

import os
import yaml
import logging
import asyncio
from anthropic import AsyncAnthropic
from dotenv import load_dotenv
from typing import Optional, Dict, List, Tuple

load_dotenv()
logger = logging.getLogger("agentkit")

client = AsyncAnthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

# ============================================================================
# IMPORTAR MÓDULO DE PRECIOS
# ============================================================================
from agent.pricing import CotizadorPrecios, obtener_cotizador


def cargar_config_prompts() -> dict:
    try:
        with open("config/prompts.yaml", "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except FileNotFoundError:
        logger.error("config/prompts.yaml no encontrado")
        return {}


def construir_system_prompt_base(asesor: str = "Sofia") -> str:
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


def construir_system_prompt_completo(
    asesor: str = "Sofia",
    contexto_cliente: str = "",
    include_pricing: bool = True
) -> str:
    """
    Construye system prompt completo con soporte para cotización de precios.

    Args:
        asesor: Nombre del asesor
        contexto_cliente: Contexto adicional del cliente
        include_pricing: Si incluir instrucciones de precios

    Returns:
        System prompt completo con todas las instrucciones
    """
    base_prompt = construir_system_prompt_base(asesor)

    if include_pricing:
        # ====================================================================
        # SECCIÓN 1: COTIZACIÓN DE PRECIOS Y REPARACIÓN
        # ====================================================================
        pricing_instructions = """

### 📱 REPARACIÓN Y COTIZACIÓN DE DISPOSITIVOS

Eres especialista en cotización de reparación de dispositivos electrónicos (pantallas, baterías, puertos de carga, etc).

**MÓDELOS Y DISPOSITIVOS QUE COTIZAS:**
- Samsung (Galaxy A, S, Note, M, J series)
- iPhone (todas las generaciones)
- Google Pixel
- Xiaomi, Redmi, Poco
- Motorola, Moto G
- OnePlus
- Huawei, Honor
- OPPO, Vivo
- LG, Nokia
- Y otros (consulta si tienes cobertura)

**TIPOS DE REPARACIÓN QUE COTIZAS:**
1. **Pantalla/Display**: LCD, OLED, AMOLED, Incell (con o sin marco)
2. **Batería**: Reemplazo de batería original o compatible
3. **Puerto de carga**: Reparación o reemplazo del puerto USB, USB-C, Lightning
4. **Otros**: Botones, micrófono, parlante (consultar disponibilidad)

**ESTRATEGIA DE COTIZACIÓN:**

Cuando el cliente pregunta por una reparación:
1. **Identifica el modelo exacto** (ej: "Samsung Galaxy A12", "iPhone 13 Pro")
2. **Pregunta el tipo de pantalla** si es ambiguo:
   - "¿Es pantalla OLED, AMOLED, o estándar (LCD/Incell)?"
   - Si el cliente no sabe y tú no estás seguro → ejecuta comando `pausa: NÚMERO`
3. **Busca en motor de precios** usando la función de cotización
4. **Cálculo de precio final:**
   - INCELL/OLED: Base × 4
   - AMOLED: Base × 3
   - Precios son exclusivos de material e instalación

**DISPOSITIVOS DE GAMA ALTA (requieren validación humana):**
- iPhone (cualquier modelo)
- Samsung Galaxy S, Galaxy Note
- Google Pixel (cualquier modelo)
- Equipos con precio base > $15,000 MXN

Si cliente tiene GAMA ALTA + es persona de 3ª edad:
→ Muestra DUAL PRECIO: "[$precio_genérico (pantalla genérica)] o [$precio_original (pantalla original)]"
→ Esto estimula decisión de compra incluso si los precios son iguales

**CUANDO HAY INCERTIDUMBRE:**
Si no estás 100% seguro del tipo de pantalla (OLED vs AMOLED confusion, equipos no catalogados):
→ Ejecuta comando: `@pausa: {TELEFONO_CLIENTE}`
→ Respuesta al cliente: "Le comunicamos con un técnico especializado para confirmar la especificación exacta"

**NUNCA REVELES LAS FUENTES DE PRECIO:**
❌ NO digas "según Hugo Shop", "según MercadoLibre", "según Fixoem"
✅ SIEMPRE usa nombres de almacenes internos:
   - Hugo Shop → "nuestro almacén de Naucalpan"
   - MercadoLibre → "nuestro proveedor en Texas"
   - Fixoem → "nuestro centro en Monterrey"

**ENVÍOS Y PLAZOS:**
- Envío LOCAL (CDMX): 24-48 horas
- Envío NACIONAL (MercadoLibre): 15-20 días → REQUIERE 50% ANTICIPO + ORDEN FORMAL
- Si cliente viene a taller: Cotizar ese día, entregar en 24-72 horas

**MONTO MÍNIMO PARA COTIZACIÓN:**
- No cotices reparaciones < $200 MXN
- Para reparaciones de bajo costo, ofrece alternativa: "mejor cambiar por un equipo refurbished"

### 📋 COMANDO PAUSA (intervención humana)

Cuando necesites detener la conversación y escalarlo a Christian:
Escribe: `@pausa: {NÚMERO_CLIENTE}`

Ejemplos válidos:
- `@pausa: 5541234567`
- `@pausa: 55 4123 4567`

Después de ejecutar pausa:
1. El bot se pausa automáticamente
2. Se notifica al grupo interno de WhatsApp
3. Christian atiende directamente al cliente
4. Conversación se reanuda cuando Christian lo indique

**CASOS PARA ACTIVAR PAUSA:**
- Incertidumbre sobre modelo o especificación técnica
- Cliente solicita garantía o términos especiales
- Necesita aprobación de reparación gama alta
- Cliente quiere negociar precio
- Problema técnico fuera de scope estándar
- Cliente solicita presupuesto formal por escrito
"""
        base_prompt += pricing_instructions

    # ====================================================================
    # SECCIÓN 2: COMPORTAMIENTO GENERAL
    # ====================================================================
    comportamiento = """

### 🎯 INSTRUCCIONES DE COMPORTAMIENTO

**RESPONDE EN ESPAÑOL** - El cliente es hispanohablante

**TONO:**
- Profesional pero amable
- Accesible, sin jerga técnica innecesaria
- Eres un asesor técnico, no un vendedor agresivo

**FORMATO DE RESPUESTAS:**
- Párrafos cortos (máx 3 líneas)
- Usa emojis relevantes para claridad visual
- Para listas: máx 4 opciones
- Siempre cierra con pregunta o siguiente paso

**SI NO SABES:**
- "No tengo información sobre ese modelo, déjame consultar con mi equipo"
- "Eso está fuera de nuestro servicio, pero te recomendamos..."

**SI ES CONSULTA NO TÉCNICA:**
- Derivar a general@empresa.com
- O agendar cita presencial: "¿Te parece bien que programemos una cita con un técnico?"
"""
    base_prompt += comportamiento

    # ====================================================================
    # SECCIÓN 3: CONTEXTO DEL CLIENTE
    # ====================================================================
    if contexto_cliente:
        base_prompt += f"""

### 👤 CONTEXTO DEL CLIENTE

{contexto_cliente}
"""

    return base_prompt


def obtener_mensaje_error() -> str:
    config = cargar_config_prompts()
    return config.get(
        "error_message",
        "Lo siento, estoy teniendo problemas técnicos. Por favor intente de nuevo."
    )


def obtener_mensaje_fallback() -> str:
    config = cargar_config_prompts()
    return config.get(
        "fallback_message",
        "Disculpe, no entendí su mensaje. ¿Podría reformularlo?"
    )


def obtener_system_prompt_por_tipo(tipo_dispositivo: str, asesor: str = "Sofia") -> Optional[str]:
    """
    Obtiene el system prompt específico para un tipo de dispositivo.

    Args:
        tipo_dispositivo: "celular" | "consola" | "laptop" | "ambiguo"
        asesor: Nombre del asesor

    Returns:
        System prompt específico o None si no existe
    """
    config = cargar_config_prompts()

    # Mapeo de tipos a claves de prompts
    mapa_tipos = {
        "celular": "system_prompt_celular",
        "consola": "system_prompt_consola",
        "laptop": "system_prompt_laptop",
    }

    clave = mapa_tipos.get(tipo_dispositivo)
    if not clave:
        return None

    prompt = config.get(clave)
    if not prompt:
        return None

    # Reemplazar placeholders de asesor
    asesores = config.get("asesores", {})
    info = asesores.get(asesor, {})
    personalidad = info.get("personalidad", "Eres profesional y amable.")

    prompt = prompt.replace("ASESOR_NOMBRE", asesor).replace("ASESOR_PERSONALIDAD", personalidad)

    logger.info(f"[BRAIN] System prompt cargado para tipo={tipo_dispositivo}, asesor={asesor}")
    return prompt


# ============================================================================
# INTEGRACIÓN CON COTIZADOR
# ============================================================================

async def enriquecer_respuesta_con_cotizacion(
    respuesta_base: str,
    descripcion_dispositivo: Optional[str],
    cliente_datos: Optional[Dict] = None
) -> str:
    """
    Si la respuesta menciona reparación, intenta cotizar automáticamente.

    Args:
        respuesta_base: Respuesta inicial de Claude
        descripcion_dispositivo: Descripción del dispositivo a cotizar
        cliente_datos: Datos del cliente (edad, equipos, etc)

    Returns:
        Respuesta enriquecida con cotización o respuesta original si falla
    """
    if not descripcion_dispositivo:
        return respuesta_base

    try:
        cotizador = await obtener_cotizador()
        if cotizador:
            cotizacion = await cotizador.cotizar(descripcion_dispositivo)
            if cotizacion:
                respuesta_base += f"\n\n💰 Cotización: ${cotizacion.precio_final:,.0f} MXN"
                logger.info(f"[PRICING] ✅ Cotización agregada: ${cotizacion.precio_final:,.0f} MXN")

        logger.info(f"[PRICING] Enriquecimiento de cotización para: {descripcion_dispositivo}")
        return respuesta_base
    except Exception as e:
        logger.error(f"[PRICING] Error enriqueciendo respuesta: {e}")
        return respuesta_base


# ============================================================================
# GENERACIÓN DE RESPUESTA PRINCIPAL
# ============================================================================

async def generar_respuesta(
    mensaje: str,
    historial: list[dict],
    asesor: str = "Sofia",
    contexto_cliente: str = "",
    include_pricing: bool = True,
    descripcion_dispositivo: Optional[str] = None,
    tipo_dispositivo: Optional[str] = None,
) -> str:
    """
    Genera respuesta usando Claude con soporte para cotización de precios y multi-dispositivo.

    Args:
        mensaje: Mensaje del usuario
        historial: Historial de conversación
        asesor: Nombre del asesor
        contexto_cliente: Contexto adicional del cliente
        include_pricing: Si incluir instrucciones de precios
        descripcion_dispositivo: Descripción del dispositivo para cotización
        tipo_dispositivo: Tipo específico ("celular", "consola", "laptop", "ambiguo")
                         Si no es None, usa system prompt específico en lugar del genérico

    Returns:
        Respuesta generada por Claude
    """
    if not mensaje or len(mensaje.strip()) < 2:
        return obtener_mensaje_fallback()

    # Intentar obtener system prompt específico por tipo
    system_prompt = None
    if tipo_dispositivo and tipo_dispositivo != "ambiguo":
        system_prompt = obtener_system_prompt_por_tipo(tipo_dispositivo, asesor)

    # Si no hay prompt específico o tipo es ambiguo, usar prompt genérico
    if not system_prompt:
        system_prompt = construir_system_prompt_completo(
            asesor=asesor,
            contexto_cliente=contexto_cliente,
            include_pricing=include_pricing
        )

    mensajes = [{"role": m["role"], "content": m["content"]} for m in historial]
    mensajes.append({"role": "user", "content": mensaje})

    try:
        response = await client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1024,
            system=system_prompt,
            messages=mensajes,
        )
        respuesta = response.content[0].text
        logger.info(
            f"[{asesor}] Respuesta generada (tipo={tipo_dispositivo}) "
            f"({response.usage.input_tokens} in / {response.usage.output_tokens} out)"
        )

        # Enriquecer con cotización si es aplicable
        if include_pricing and descripcion_dispositivo:
            respuesta = await enriquecer_respuesta_con_cotizacion(
                respuesta,
                descripcion_dispositivo,
                None
            )

        return respuesta

    except Exception as e:
        logger.error(f"Error Claude API: {e}")
        return obtener_mensaje_error()


# ============================================================================
# HELPERS PARA DETECTAR COMANDOS
# ============================================================================

def detectar_comando_pausa(texto: str) -> Optional[str]:
    """Detecta si el texto contiene comando @pausa: NÚMERO

    Returns:
        Número telefónico si se detecta, None si no
    """
    import re
    # Buscar @pausa: seguido de números
    match = re.search(r'@pausa:\s*(\d+)', texto)
    if match:
        return match.group(1)
    return None


def texto_contiene_reparacion(texto: str) -> bool:
    """Detecta si el usuario pregunta sobre reparación"""
    palabras_clave = [
        'reparar', 'reparación', 'pantalla', 'display', 'batería', 'bateria',
        'puerto', 'carga', 'botón', 'boton', 'cotización', 'cotizacion',
        'precio', 'cuánto cuesta', 'cuanto cuesta', '¿cuánto?', '¿cuanto?',
        'arreglar', 'arreglo', 'cambiar', 'reemplazo', 'remplazo'
    ]
    texto_lower = texto.lower()
    return any(palabra in texto_lower for palabra in palabras_clave)
