# agent/tools.py — Herramientas del agente para Tecnology Support
# Generado por AgentKit

"""
COTIZACIONES INTELIGENTES — Lógica principal
"""

import os
import yaml
import logging
import requests
from datetime import datetime
from functools import lru_cache
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

logger = logging.getLogger("agentkit")

# Precios base de referencia
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
        "citas_apertura": "10:30",
        "citas_cierre": "20:30",
    },
    "sabado_domingo": {
        "apertura": "11:00",
        "cierre": "20:00",
        "citas_apertura": "11:30",
        "citas_cierre": "19:30",
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
    dia_semana = ahora.weekday()
    hora_actual = ahora.hour + ahora.minute / 60

    if dia_semana <= 4:
        apertura = 10.0
        cierre = 21.0
        citas_apertura = 10.5
        citas_cierre = 20.5
        horario_texto = "Lunes a Viernes de 10:00am a 9:00pm"
    else:
        apertura = 11.0
        cierre = 20.0
        citas_apertura = 11.5
        citas_cierre = 19.5
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
        "Celular (iPhone, Samsung, Motorola, etc.)\n"
        "Laptop (Windows, Mac, Linux)\n"
        "Consola (PS4, PS5, Xbox, Nintendo Switch)\n\n"
        "¿Cuál es tu dispositivo? Así te doy presupuesto exacto."
    )


def detectar_tipo_dispositivo_en_mensaje(mensaje: str, historial: list[dict] = None) -> str:
    """
    Detecta el tipo de dispositivo mencionado en el mensaje.
    """
    mensaje_lower = mensaje.lower()

    dispositivos = {
        "celular": ["iphone", "samsung", "motorola", "xiaomi", "huawei", "celular", "teléfono", "phone", "móvil", "android"],
        "laptop": ["laptop", "notebook", "macbook", "windows", "mac", "linux", "computadora", "pc", "thinkpad", "dell", "hp", "asus"],
        "consola": ["ps4", "ps5", "playstation", "xbox", "nintendo", "switch", "consola", "gaming"],
    }

    for tipo, palabras in dispositivos.items():
        if any(palabra in mensaje_lower for palabra in palabras):
            return tipo

    if historial:
        for msg in reversed(historial):
            if msg.get("role") == "user":
                for tipo, palabras in dispositivos.items():
                    if any(palabra in msg.get("content", "").lower() for palabra in palabras):
                        return tipo

    return "ambiguo"


# INTEGRACIÓN HUGO SHOP — Consulta de precios de displays
HUGO_SHOP_SHEET_ID = os.getenv("HUGO_SHOP_SHEET_ID", "")
HUGO_SHOP_RANGE = "A1:F500"


def detectar_tipo_display(calidad_str: str) -> tuple[str, float]:
    """
    Determina el multiplicador según el tipo de display en la columna CALIDAD.
    REGLA: UNICAMENTE AMOLED = x3, TODO lo demás = x4
    """
    calidad_lower = calidad_str.lower()

    # UNICAMENTE AMOLED se multiplica por 3
    if "amoled" in calidad_lower:
        return ("AMOLED", 3.0)

    # TODO lo demás (incluyendo OLED, ORIG, INCELL, etc.) = x4
    return ("DISPLAY", 4.0)


@lru_cache(maxsize=128)
def obtener_precio_display(marca: str, modelo: str, tipo_display: str = "ambos") -> dict:
    """
    Consulta el precio de un display desde Hugo Shop en Google Sheets.
    ESTRUCTURA REAL:
    - Col A: CÓDIGO o MARCA (encabezado cuando B está vacío)
    - Col B: MODELO
    - Col C: CALIDAD (incell, generico, c/m, s/m, oled, amoled, orig, cof, etc.)
    - Col D: COLOR
    - Col E: PRECIO (el que se usa)
    - Col F: Se ignora
    """
    if not HUGO_SHOP_SHEET_ID:
        logger.warning("HUGO_SHOP_SHEET_ID no configurado")
        return {
            "marca": marca.title(),
            "modelo": modelo,
            "precio_generico": None,
            "precio_original": None,
            "encontrado": False,
            "razon": "Hugo Shop aún no conectado",
            "nota": "El técnico te da el precio exacto en el diagnóstico (2 horas)"
        }

    try:
        url = f"https://docs.google.com/spreadsheets/d/{HUGO_SHOP_SHEET_ID}/export?format=csv&range={HUGO_SHOP_RANGE}"
        response = requests.get(url, timeout=5)
        response.raise_for_status()

        lineas = response.text.strip().split("\n")
        marca_actual = ""
        marca_lower = marca.lower()
        modelo_lower = modelo.lower()

        for linea in lineas[1:]:  # Saltar encabezado
            # Manejar comillas en CSV
            partes = []
            for part in linea.split(","):
                part = part.strip().strip('"')
                partes.append(part)

            if not partes or len(partes) < 2:
                continue

            col_a = partes[0].strip().lower()
            col_b = partes[1].strip().lower() if len(partes) > 1 else ""
            col_c = partes[2].strip().lower() if len(partes) > 2 else ""
            col_e = partes[4].strip() if len(partes) > 4 else ""

            # Detectar si es un encabezado de marca (A tiene valor, B está vacío o es corto)
            if col_a and not col_b:
                marca_actual = col_a
                continue

            # Si B está vacío, saltear
            if not col_b:
                continue

            try:
                # Buscar coincidencia: marca actual + modelo en B
                if marca_actual == marca_lower and modelo_lower in col_b:
                    # Parsear precio
                    precio_str = col_e.replace("$", "").replace(",", "").strip()
                    precio_base = float(precio_str)

                    # Detectar tipo según CALIDAD
                    tipo_display_det, multiplicador = detectar_tipo_display(col_c)
                    precio_final = int(precio_base * multiplicador)

                    logger.info(f"Encontrado: {marca} {modelo} | Tipo: {tipo_display_det} | Base: ${precio_base} x {multiplicador} = ${precio_final}")

                    return {
                        "marca": marca.title(),
                        "modelo": modelo,
                        "precio_generico": precio_final,
                        "precio_original": precio_final,
                        "encontrado": True,
                        "tipo_display": tipo_display_det,
                        "calidad": col_c,
                        "nota": "Con garantía 90 días + cambio mismo día + diagnóstico incluido"
                    }

            except (ValueError, IndexError) as e:
                logger.debug(f"Error parseando línea: {linea} — {e}")
                continue

        logger.warning(f"Modelo no encontrado en Hugo Shop: {marca} {modelo}")
        return {
            "marca": marca.title(),
            "modelo": modelo,
            "precio_generico": None,
            "precio_original": None,
            "encontrado": False,
            "razon": f"{marca} {modelo} no está en nuestro catálogo actual",
            "nota": "El técnico te confirma disponibilidad y precio en el módulo"
        }

    except requests.RequestException as e:
        logger.error(f"Error consultando Hugo Shop: {e}")
        return {
            "marca": marca.title(),
            "modelo": modelo,
            "precio_generico": None,
            "precio_original": None,
            "encontrado": False,
            "razon": "Problema temporal conectando con catálogo",
            "nota": "El técnico te da el precio exacto sin sorpresas en el diagnóstico"
        }


def obtener_precio_display_ambas_variantes(marca: str, modelo: str) -> dict:
    """
    Busca ambas variantes: normal (x4) y AMOLED (x3).
    Retorna: genérico (TODO menos AMOLED, x4) y original (AMOLED, x3)
    """
    if not HUGO_SHOP_SHEET_ID:
        return {
            "marca": marca.title(),
            "modelo": modelo,
            "precio_generico": None,
            "precio_original": None,
            "encontrado_generico": False,
            "encontrado_original": False,
            "razon": "Hugo Shop no conectado",
            "nota": "El técnico te da el precio exacto en el diagnóstico (2 horas)"
        }

    try:
        url = f"https://docs.google.com/spreadsheets/d/{HUGO_SHOP_SHEET_ID}/export?format=csv&range={HUGO_SHOP_RANGE}"
        response = requests.get(url, timeout=5)
        response.raise_for_status()
        lineas = response.text.strip().split("\n")

        precio_generico = None
        precio_original = None
        encontrado_generico = False
        encontrado_original = False

        marca_actual = ""
        marca_lower = marca.lower()
        modelo_lower = modelo.lower()

        for linea in lineas[1:]:
            # Manejar comillas en CSV
            partes = []
            for part in linea.split(","):
                part = part.strip().strip('"')
                partes.append(part)

            if not partes or len(partes) < 2:
                continue

            col_a = partes[0].strip().lower()
            col_b = partes[1].strip().lower() if len(partes) > 1 else ""
            col_c = partes[2].strip().lower() if len(partes) > 2 else ""
            col_e = partes[4].strip() if len(partes) > 4 else ""

            # Detectar encabezado de marca
            if col_a and not col_b:
                marca_actual = col_a
                continue

            # Saltar filas sin modelo
            if not col_b:
                continue

            try:
                # Buscar coincidencia: marca actual + modelo
                if marca_actual == marca_lower and modelo_lower in col_b:
                    precio_str = col_e.replace("$", "").replace(",", "").strip()
                    precio_base = float(precio_str)
                    tipo_display_det, multiplicador = detectar_tipo_display(col_c)
                    precio_final = int(precio_base * multiplicador)

                    # Clasificar: AMOLED es original (x3), todo lo demás es genérico (x4)
                    if not encontrado_original and tipo_display_det == "AMOLED":
                        precio_original = precio_final
                        encontrado_original = True
                        logger.info(f"Variante AMOLED (original): {marca} {modelo} ({col_c}) -> ${precio_final}")

                    if not encontrado_generico and tipo_display_det != "AMOLED":
                        precio_generico = precio_final
                        encontrado_generico = True
                        logger.info(f"Variante normal (genérica): {marca} {modelo} ({col_c}) -> ${precio_final}")

                    # Si encontramos ambas, terminar
                    if encontrado_generico and encontrado_original:
                        break

            except (ValueError, IndexError) as e:
                logger.debug(f"Error parseando: {linea} — {e}")
                continue

        return {
            "marca": marca.title(),
            "modelo": modelo,
            "precio_generico": precio_generico,
            "precio_original": precio_original,
            "encontrado_generico": encontrado_generico,
            "encontrado_original": encontrado_original,
            "nota": "Con garantía 90 días + cambio mismo día + diagnóstico incluido"
        }

    except requests.RequestException as e:
        logger.error(f"Error consultando Hugo Shop: {e}")
        return {
            "marca": marca.title(),
            "modelo": modelo,
            "precio_generico": None,
            "precio_original": None,
            "encontrado_generico": False,
            "encontrado_original": False,
            "razon": "Problema temporal conectando",
            "nota": "El técnico te da el precio exacto en el diagnóstico"
        }


def formatear_respuesta_precio(marca: str, modelo: str, tipo_display: str = "ambos") -> str:
    """
    Formatea la respuesta de precio de una forma amigable para el cliente.
    Si hay múltiples variantes, muestra el rango de precios (desde...hasta).
    Las variantes corresponden a diferentes calidades (genérica hasta AMOLED).
    """
    precio = obtener_precio_display_ambas_variantes(marca, modelo)

    if not precio["encontrado_generico"] and not precio["encontrado_original"]:
        return f"Para {marca} {modelo}, el técnico te confirma disponibilidad y precio exacto en el diagnóstico (2 horas, $200 MXN bonificables). {precio['nota']}"

    respuesta = f"Para {precio['marca']} {precio['modelo']}:\n\n"

    # Si hay ambas variantes, mostrar rango
    if precio["encontrado_generico"] and precio["encontrado_original"]:
        precio_minimo = min(precio['precio_generico'], precio['precio_original'])
        precio_maximo = max(precio['precio_generico'], precio['precio_original'])
        respuesta += f"Precio desde ${precio_minimo:,} hasta ${precio_maximo:,} MXN\n"
        respuesta += f"(Variantes por calidad: genérica a original AMOLED)\n\n"
    # Si solo hay una variante, mostrar ese precio
    elif precio["encontrado_generico"]:
        respuesta += f"Precio: ${precio['precio_generico']:,} MXN\n\n"
    elif precio["encontrado_original"]:
        respuesta += f"Precio: ${precio['precio_original']:,} MXN (AMOLED)\n\n"

    respuesta += f"Incluye:\n"
    respuesta += f"- Garantía 90 días\n"
    respuesta += f"- Cambio el mismo día si pasas en la tarde\n"
    respuesta += f"- Diagnóstico de daño interno incluido\n\n"
    respuesta += f"El técnico te confirmará la variante exacta en el módulo (diagnóstico 2 horas, $200 MXN bonificables)."

    return respuesta
