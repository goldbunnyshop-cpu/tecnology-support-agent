# agent/pricing.py — Motor de cotización con múltiples fuentes de precio
# Integración: Hugo Shop CSV (Google Drive), MercadoLibre, Fixoem

import os
import csv
import json
import logging
import aiohttp
import asyncio
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Dict, List, Tuple
from dataclasses import dataclass, asdict
from enum import Enum
import re

logger = logging.getLogger("agentkit")

# ============================================================================
# ENUMS Y TIPOS
# ============================================================================

class CalidadDispositivo(Enum):
    """Tipos de calidad de pantalla según Hugo Shop"""
    ORIG = "ORIG"           # Original
    INCELL = "INCELL"       # Incell (pantalla integrada)
    OLED = "OLED"           # OLED
    AMOLED = "AMOLED"       # AMOLED
    UNKNOWN = "UNKNOWN"     # Desconocido


class FuentePrecio(Enum):
    """Fuentes de precio con jerarquía"""
    HUGO_SHOP = "hugo_shop"      # P1 (CSV local)
    MERCADO_LIBRE = "ml"         # P2 (cached)
    FIXOEM = "fixoem"            # P3 (cached)
    FALLBACK = "fallback"        # Cache anterior


@dataclass
class CotizacionPrecio:
    """Estructura de una cotización de precio"""
    modelo: str                    # ej: "Samsung Galaxy A12"
    codigo: str                    # Código Hugo Shop
    descripcion: str              # Descripción completa
    calidad: CalidadDispositivo   # Tipo de pantalla
    color: str                    # Color
    precio_base: float            # Precio base (PRECIO_1)
    fuente: FuentePrecio          # De dónde vino el precio
    multiplicador: float          # Factor aplicado (3x, 4x)
    precio_final: float           # Precio final cotizado
    timestamp: str                # Cuándo se obtuvo

    def a_dict(self) -> dict:
        d = asdict(self)
        d['calidad'] = self.calidad.value
        d['fuente'] = self.fuente.value
        return d


# ============================================================================
# CACHE Y ALMACENAMIENTO
# ============================================================================

class CacheManager:
    """Gestiona cacheo local de precios con fallback"""

    def __init__(self, cache_dir: str = "data/cache"):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.hugo_cache = self.cache_dir / "hugo_shop.json"
        self.ml_cache = self.cache_dir / "mercado_libre.json"
        self.fixoem_cache = self.cache_dir / "fixoem.json"
        self.backup_dir = self.cache_dir / "backup"
        self.backup_dir.mkdir(parents=True, exist_ok=True)

    def guardar_hugo_shop(self, datos: List[Dict]) -> bool:
        """Guarda CSV de Hugo Shop con backup automático"""
        try:
            # Backup del cache anterior si existe
            if self.hugo_cache.exists():
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                backup_path = self.backup_dir / f"hugo_shop_{timestamp}.json"
                import shutil
                shutil.copy(self.hugo_cache, backup_path)
                logger.info(f"Backup creado: {backup_path}")

            # Guardar nuevo cache
            with open(self.hugo_cache, 'w', encoding='utf-8') as f:
                json.dump({
                    'timestamp': datetime.now().isoformat(),
                    'data': datos
                }, f, ensure_ascii=False, indent=2)
            logger.info(f"Cache Hugo Shop actualizado: {len(datos)} productos")
            return True
        except Exception as e:
            logger.error(f"Error guardando Hugo Shop cache: {e}")
            return False

    def cargar_hugo_shop(self) -> Optional[List[Dict]]:
        """Carga cache de Hugo Shop, con fallback a backup si es necesario"""
        if self.hugo_cache.exists():
            try:
                with open(self.hugo_cache, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    logger.info(f"Cache Hugo Shop cargado: {len(data.get('data', []))} productos")
                    return data.get('data', [])
            except Exception as e:
                logger.error(f"Error cargando cache: {e}")

        # Intentar cargar backup más reciente
        backups = sorted(self.backup_dir.glob("hugo_shop_*.json"), reverse=True)
        if backups:
            try:
                with open(backups[0], 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    logger.warning(f"Cargado backup: {backups[0].name}")
                    return data.get('data', [])
            except Exception as e:
                logger.error(f"Error cargando backup: {e}")

        return None

    def guardar_precios_externos(self, fuente: FuentePrecio, datos: Dict) -> bool:
        """Guarda precios de MercadoLibre o Fixoem con timestamp"""
        cache_file = self.ml_cache if fuente == FuentePrecio.MERCADO_LIBRE else self.fixoem_cache
        try:
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump({
                    'timestamp': datetime.now().isoformat(),
                    'data': datos
                }, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            logger.error(f"Error guardando cache {fuente.value}: {e}")
            return False

    def cargar_precios_externos(self, fuente: FuentePrecio, max_edad_horas: int = 24) -> Optional[Dict]:
        """Carga precios externos con validación de antigüedad"""
        cache_file = self.ml_cache if fuente == FuentePrecio.MERCADO_LIBRE else self.fixoem_cache
        if cache_file.exists():
            try:
                with open(cache_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    timestamp = datetime.fromisoformat(data['timestamp'])
                    edad = datetime.now() - timestamp

                    if edad < timedelta(hours=max_edad_horas):
                        logger.info(f"Cache {fuente.value} válido (edad: {edad})")
                        return data.get('data', {})
                    else:
                        logger.warning(f"Cache {fuente.value} expirado (edad: {edad})")
                        return None
            except Exception as e:
                logger.error(f"Error cargando cache externo: {e}")
        return None


# ============================================================================
# DETECCIÓN DE DISPOSITIVO Y CALIDAD
# ============================================================================

class DetectorDispositivo:
    """Detecta tipo de dispositivo y calidad desde descripción"""

    # Patrones para detectar calidad (case-insensitive)
    PATRONES_CALIDAD = {
        CalidadDispositivo.OLED: r'\boled\b',
        CalidadDispositivo.AMOLED: r'\bamoled\b',
        CalidadDispositivo.INCELL: r'\bincell\b|\binc\b',
        CalidadDispositivo.ORIG: r'\borig\b|\boriginal\b|\boficial\b',
    }

    # Dispositivos de gama alta (requieren intervención humana)
    MARCAS_GAMA_ALTA = {'iPhone', 'Samsung Galaxy S', 'Google Pixel', 'OnePlus'}
    PRECIO_UMBRAL_GAMA_ALTA = 15000  # en pesos

    @staticmethod
    def detectar_calidad(descripcion: str) -> CalidadDispositivo:
        """Detecta tipo de pantalla desde descripción"""
        desc_lower = descripcion.lower()

        # Buscar en orden de especificidad (OLED > AMOLED > INCELL > ORIG)
        for calidad, patron in DetectorDispositivo.PATRONES_CALIDAD.items():
            if re.search(patron, desc_lower):
                return calidad

        return CalidadDispositivo.UNKNOWN

    @staticmethod
    def extraer_marca_modelo(descripcion: str) -> str:
        """Extrae marca y modelo de la descripción"""
        # Tomar primeras 2-3 palabras como marca/modelo
        palabras = descripcion.split()[:3]
        return " ".join(palabras).strip()

    @staticmethod
    def es_gama_alta(marca_modelo: str, precio: float) -> bool:
        """Detecta si es dispositivo de gama alta que requiere revisión"""
        # Si el precio supera umbral
        if precio > DetectorDispositivo.PRECIO_UMBRAL_GAMA_ALTA:
            return True

        # Si contiene marca de gama alta
        for marca in DetectorDispositivo.MARCAS_GAMA_ALTA:
            if marca.lower() in marca_modelo.lower():
                return True

        return False


# ============================================================================
# MOTOR DE MULTIPLICADORES
# ============================================================================

class MotorMultiplicadores:
    """Calcula multiplicadores según fuente y tipo de dispositivo"""

    # Multiplicadores base por fuente
    MULTIPLICADORES_BASE = {
        FuentePrecio.HUGO_SHOP: {
            CalidadDispositivo.INCELL: 4.0,
            CalidadDispositivo.OLED: 4.0,
            CalidadDispositivo.AMOLED: 3.0,
            CalidadDispositivo.ORIG: 4.0,
            CalidadDispositivo.UNKNOWN: 3.5,
        },
        FuentePrecio.MERCADO_LIBRE: 3.0,
        FuentePrecio.FIXOEM: 3.0,
        FuentePrecio.FALLBACK: 3.0,
    }

    @staticmethod
    def obtener_multiplicador(fuente: FuentePrecio, calidad: CalidadDispositivo) -> float:
        """Obtiene multiplicador para fuente y calidad"""
        if fuente == FuentePrecio.HUGO_SHOP:
            return MotorMultiplicadores.MULTIPLICADORES_BASE[fuente].get(
                calidad,
                MotorMultiplicadores.MULTIPLICADORES_BASE[fuente][CalidadDispositivo.UNKNOWN]
            )
        else:
            return MotorMultiplicadores.MULTIPLICADORES_BASE.get(fuente, 3.0)

    @staticmethod
    def calcular_precio_final(precio_base: float, fuente: FuentePrecio,
                             calidad: CalidadDispositivo) -> float:
        """Calcula precio final aplicando multiplicador"""
        multiplicador = MotorMultiplicadores.obtener_multiplicador(fuente, calidad)
        return precio_base * multiplicador


# ============================================================================
# INTEGRACIÓN GOOGLE DRIVE
# ============================================================================

class IntegradorGoogleDrive:
    """Descarga y parsea CSV de Hugo Shop desde Google Drive"""

    def __init__(self, file_id: str = None):
        # File ID debe configurarse en environment o parámetro
        self.file_id = file_id or os.getenv("GOOGLE_DRIVE_HUGO_SHOP_ID")
        self.download_url_template = "https://docs.google.com/uc?id={}&export=download"

    async def descargar_csv(self) -> Optional[str]:
        """Descarga CSV desde Google Drive"""
        if not self.file_id:
            logger.error("GOOGLE_DRIVE_HUGO_SHOP_ID no configurado")
            return None

        try:
            url = self.download_url_template.format(self.file_id)
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                    if resp.status == 200:
                        content = await resp.text(encoding='utf-8')
                        logger.info(f"CSV descargado: {len(content)} bytes")
                        return content
                    else:
                        logger.error(f"Error descargando CSV: HTTP {resp.status}")
                        return None
        except asyncio.TimeoutError:
            logger.error("Timeout descargando CSV de Google Drive")
            return None
        except Exception as e:
            logger.error(f"Error descargando CSV: {e}")
            return None

    @staticmethod
    def parsear_csv(contenido: str) -> List[Dict]:
        """Parsea contenido CSV a lista de productos"""
        productos = []
        try:
            lineas = contenido.strip().split('\n')
            # Detectar si la primera línea es header
            reader = csv.DictReader(lineas)

            for row in reader:
                if not row.get('CÓDIGO'):
                    continue

                try:
                    precio_1 = float(row.get('PRECIO_1', '0').replace(',', '.'))
                except (ValueError, AttributeError):
                    precio_1 = 0.0

                producto = {
                    'codigo': row.get('CÓDIGO', '').strip(),
                    'descripcion': row.get('DESCRIPCIÓN', '').strip(),
                    'calidad': row.get('CALIDAD', 'UNKNOWN').strip().upper(),
                    'color': row.get('COLOR', '').strip(),
                    'precio_1': precio_1,
                }

                if producto['precio_1'] > 0:  # Solo productos con precio válido
                    productos.append(producto)

            logger.info(f"CSV parseado: {len(productos)} productos válidos")
            return productos
        except Exception as e:
            logger.error(f"Error parseando CSV: {e}")
            return []


# ============================================================================
# COTIZADOR PRINCIPAL
# ============================================================================

class CotizadorPrecios:
    """Orquestador principal de cotización con fallback inteligente"""

    def __init__(self, file_id_drive: str = None):
        self.cache = CacheManager()
        self.detector = DetectorDispositivo()
        self.drive = IntegradorGoogleDrive(file_id_drive)
        self.hugo_datos = None  # Cache en memoria
        self.ultima_actualizacion = None

    async def actualizar_hugo_shop(self) -> bool:
        """Descarga e integra actualización de Hugo Shop desde Google Drive"""
        logger.info("Iniciando actualización Hugo Shop...")

        # Descargar CSV
        csv_contenido = await self.drive.descargar_csv()
        if not csv_contenido:
            logger.warning("No se pudo descargar CSV, usando cache local")
            self.hugo_datos = self.cache.cargar_hugo_shop()
            return bool(self.hugo_datos)

        # Parsear
        productos = IntegradorGoogleDrive.parsear_csv(csv_contenido)
        if not productos:
            logger.warning("CSV vacío o inválido, usando cache local")
            self.hugo_datos = self.cache.cargar_hugo_shop()
            return bool(self.hugo_datos)

        # Guardar en cache y memoria
        exito = self.cache.guardar_hugo_shop(productos)
        if exito:
            self.hugo_datos = productos
            self.ultima_actualizacion = datetime.now()
            logger.info(f"Hugo Shop actualizado: {len(productos)} productos")
            return True
        else:
            logger.error("Error guardando cache, intentando cache anterior")
            self.hugo_datos = self.cache.cargar_hugo_shop()
            return bool(self.hugo_datos)

    async def inicializar(self):
        """Inicializa el cotizador cargando datos"""
        # Intentar actualizar desde Drive
        exito = await self.actualizar_hugo_shop()
        if not exito:
            logger.error("CRÍTICO: No hay datos de precios disponibles")

    def buscar_en_hugo_shop(self, marca_modelo: str,
                           calidad_esperada: Optional[CalidadDispositivo] = None) -> Optional[Dict]:
        """Busca producto en Hugo Shop by marca/modelo"""
        if not self.hugo_datos:
            logger.warning("Hugo Shop no cargado")
            return None

        marca_modelo_lower = marca_modelo.lower()

        # Búsqueda exacta primero
        for prod in self.hugo_datos:
            if marca_modelo_lower in prod['descripcion'].lower():
                # Si hay calidad esperada, buscar coincidencia exacta
                if calidad_esperada:
                    prod_calidad = CalidadDispositivo(prod['calidad']) if prod['calidad'] != 'UNKNOWN' else CalidadDispositivo.UNKNOWN
                    if prod_calidad == calidad_esperada:
                        return prod
                else:
                    return prod

        # Si no encuentra, retornar el más cercano
        for prod in self.hugo_datos:
            if any(palabra in prod['descripcion'].lower()
                   for palabra in marca_modelo_lower.split()[:2]):
                return prod

        return None

    async def cotizar(self, descripcion_dispositivo: str,
                     cliente_es_mayor: bool = False,
                     cliente_usa_gama_alta: bool = False) -> Optional[CotizacionPrecio]:
        """Cotiza un dispositivo con lógica completa de fuentes y multiplicadores

        Args:
            descripcion_dispositivo: Ej "Samsung Galaxy A12 display AMOLED"
            cliente_es_mayor: Si es cliente de tercera edad (muestra dual precio)
            cliente_usa_gama_alta: Si usa equipos de gama alta

        Returns:
            CotizacionPrecio con precio final calculado o None si no se encuentra
        """

        # Paso 1: Detectar marca/modelo y calidad
        marca_modelo = self.detector.extraer_marca_modelo(descripcion_dispositivo)
        calidad = self.detector.detectar_calidad(descripcion_dispositivo)
        es_gama_alta = self.detector.es_gama_alta(marca_modelo, 0)  # Se verifica después con precio

        logger.info(f"Cotización: {marca_modelo} | Calidad: {calidad.value} | Gama Alta: {es_gama_alta}")

        # Paso 2: Buscar en Hugo Shop (P1)
        if self.hugo_datos:
            resultado = self.buscar_en_hugo_shop(marca_modelo, calidad)
            if resultado:
                precio_base = resultado['precio_1']

                # Verificar gama alta después de obtener precio
                es_gama_alta = self.detector.es_gama_alta(marca_modelo, precio_base)

                # Calcular multiplicador
                try:
                    calidad_enum = CalidadDispositivo(resultado['calidad'].upper())
                except (ValueError, AttributeError):
                    calidad_enum = CalidadDispositivo.UNKNOWN

                multiplicador = MotorMultiplicadores.obtener_multiplicador(
                    FuentePrecio.HUGO_SHOP,
                    calidad_enum
                )
                precio_final = precio_base * multiplicador

                cotizacion = CotizacionPrecio(
                    modelo=marca_modelo,
                    codigo=resultado['codigo'],
                    descripcion=resultado['descripcion'],
                    calidad=calidad_enum,
                    color=resultado['color'],
                    precio_base=precio_base,
                    fuente=FuentePrecio.HUGO_SHOP,
                    multiplicador=multiplicador,
                    precio_final=precio_final,
                    timestamp=datetime.now().isoformat(),
                )

                logger.info(f"Cotización Hugo Shop: ${precio_final:.2f} ({resultado['calidad']}×{multiplicador})")
                return cotizacion

        # Paso 3: Fallback genérico con precios base realistas (TEMPORAL mientras se activa Hugo Shop)
        logger.warning(f"Hugo Shop no disponible, usando fallback genérico para {marca_modelo}")

        # Tabla de precios base genéricos por dispositivo
        precios_fallback = {
            # Samsung - dispositivos comunes
            'samsung': 250,           # Base para Samsung estándar
            'galaxy a12': 280,
            'galaxy a13': 300,
            'galaxy a21': 280,
            'galaxy a22': 320,
            'galaxy a32': 350,
            'galaxy a52': 400,
            'galaxy s10': 500,
            'galaxy s20': 800,
            'galaxy s21': 950,
            'galaxy s22': 1100,
            'galaxy note': 600,

            # iPhone
            'iphone 6': 400,
            'iphone 7': 450,
            'iphone 8': 500,
            'iphone x': 800,
            'iphone 11': 900,
            'iphone 12': 1200,
            'iphone 13': 1400,
            'iphone 14': 1600,
            'iphone 15': 1800,
            'iphone se': 600,

            # Otros smartphones comunes
            'xiaomi': 250,
            'redmi': 220,
            'motorola': 280,
            'moto g': 300,
            'oppo': 280,
            'vivo': 280,
            'google pixel': 600,
            'oneplus': 400,
            'huawei': 320,
            'honor': 300,
            'nokia': 200,
            'lg': 280,

            # CONSOLAS - PRECIOS DE SERVICIO/REPARACIÓN
            'xbox series s': 400,     # Reparación típica
            'xbox series x': 450,
            'xbox one': 350,
            'playstation 5': 450,
            'playstation 4': 350,
            'playstation 3': 250,
            'nintendo switch': 300,
            'switch oled': 350,

            # TABLETS
            'ipad': 500,
            'ipad air': 600,
            'ipad pro': 800,
            'ipad mini': 450,
            'samsung tab': 400,
            'galaxy tab': 400,

            # LAPTOPS / COMPUTADORAS
            'macbook': 800,
            'laptop': 600,
            'notebook': 500,
            'dell': 600,
            'hp': 550,
            'lenovo': 500,
            'asus': 550,

            # ACCESORIOS/PERIFÉRICOS
            'bateria': 150,
            'battery': 150,
            'cargador': 100,
            'charger': 100,
            'puerto': 200,
            'puerto usb': 200,
            'botón': 100,
            'micrófono': 150,
            'speaker': 150,
            'auricular': 120,
            'headphone': 150,
        }

        # Buscar precio base del dispositivo
        precio_base = None
        marca_lower = marca_modelo.lower()

        for clave, precio in precios_fallback.items():
            if clave in marca_lower:
                precio_base = precio
                break

        # Si no encontró, usar promedio genérico
        if precio_base is None:
            precio_base = 300  # Promedio general
            logger.warning(f"Dispositivo no catalogado, usando precio genérico: ${precio_base}")

        # Aplicar multiplicador según calidad
        try:
            calidad_enum = CalidadDispositivo(calidad.value.upper())
        except (ValueError, AttributeError):
            calidad_enum = CalidadDispositivo.UNKNOWN

        multiplicador = MotorMultiplicadores.obtener_multiplicador(
            FuentePrecio.FALLBACK,
            calidad_enum
        )
        precio_final = precio_base * multiplicador

        cotizacion = CotizacionPrecio(
            modelo=marca_modelo,
            codigo=f"FALLBACK-{datetime.now().strftime('%s')}",
            descripcion=f"Precio genérico - {calidad_enum.value}",
            calidad=calidad_enum,
            color="N/A",
            precio_base=precio_base,
            fuente=FuentePrecio.FALLBACK,
            multiplicador=multiplicador,
            precio_final=precio_final,
            timestamp=datetime.now().isoformat(),
        )

        logger.warning(f"Cotización FALLBACK: ${precio_final:.2f} ({calidad_enum.value}×{multiplicador})")
        return cotizacion

    async def cotizar_con_incertidumbre(self, descripcion: str) -> Tuple[Optional[CotizacionPrecio], bool]:
        """Cotiza retornando (cotizacion, tiene_incertidumbre)

        Si hay incertidumbre sobre la calidad (ej OLED vs AMOLED),
        retorna (None, True) para que el agente ejecute pausa.
        """
        calidad = self.detector.detectar_calidad(descripcion)

        # Si no se detectó calidad o está ambiguo, hay incertidumbre
        if calidad == CalidadDispositivo.UNKNOWN:
            logger.warning(f"Incertidumbre detectada en: {descripcion}")
            return None, True

        cotizacion = await self.cotizar(descripcion)
        return cotizacion, False


# ============================================================================
# EXPORTS
# ============================================================================

async def obtener_cotizador() -> CotizadorPrecios:
    """Factory para obtener cotizador inicializado"""
    cotizador = CotizadorPrecios()
    await cotizador.inicializar()
    return cotizador


# ============================================================================
# FUNCIÓN PÚBLICA: OBTENER COTIZACIÓN DISPLAY
# ============================================================================

# Cotizador global inicializado al arrancar el servidor
_cotizador_global = None


def _generar_cotizacion_fallback(marca: str, modelo: str) -> str:
    """Genera cotización con fallback cuando Hugo Shop no está disponible"""

    # Tabla de precios base por dispositivo (costo wholesale aproximado)
    precios_fallback = {
        'samsung galaxy a12': 280, 'samsung a12': 280,
        'samsung galaxy a13': 300, 'samsung a13': 300,
        'samsung galaxy a21': 280, 'samsung a21': 280,
        'samsung galaxy a22': 320, 'samsung a22': 320,
        'samsung galaxy a32': 350, 'samsung a32': 350,
        'samsung galaxy a52': 400, 'samsung a52': 400,
        'samsung galaxy a55': 420, 'samsung a55': 420,
        'samsung galaxy s10': 500, 'samsung s10': 500,
        'samsung galaxy s20': 800, 'samsung s20': 800,
        'samsung galaxy s21': 950, 'samsung s21': 950,
        'samsung galaxy s22': 1100, 'samsung s22': 1100,
        'samsung galaxy s23': 1200, 'samsung s23': 1200,
        'samsung galaxy s24': 1300, 'samsung s24': 1300,
        'samsung': 350,  # Base para Samsung desconocido

        'iphone 6': 400, 'iphone 7': 450, 'iphone 8': 500, 'iphone x': 800,
        'iphone 11': 900, 'iphone 12': 1200, 'iphone 13': 1400,
        'iphone 14': 1600, 'iphone 15': 1800, 'iphone 16': 2000,
        'iphone': 1000,  # Base para iPhone desconocido

        'motorola moto edge 50 fusion': 450, 'moto edge 50': 450,
        'motorola moto g': 300, 'moto g': 300,
        'motorola': 280,

        'xiaomi': 250, 'redmi': 220, 'oppo': 280, 'vivo': 280,
        'google pixel': 600, 'pixel': 600, 'oneplus': 400, 'huawei': 320,
        'nokia': 200, 'lg': 280, 'honor': 300,
    }

    # Buscar precio base
    consulta = f"{marca} {modelo}".lower()
    precio_base = None

    # Búsqueda exacta primero
    for clave, precio in sorted(precios_fallback.items(), key=lambda x: -len(x[0])):
        if clave in consulta:
            precio_base = precio
            break

    # Si no encontró, usar promedio
    if precio_base is None:
        precio_base = 350
        logger.info(f"[PRICING] Dispositivo no catalogado, usando precio genérico: ${precio_base}")

    # Calcular precios con multiplicadores
    precio_generico = int(precio_base * 3.5)  # Multiplicador 3.5x para genérico
    precio_original = int(precio_base * 4.0)  # Multiplicador 4x para original

    respuesta = f"Para {marca} {modelo} tenemos estas opciones:\n"
    respuesta += f"• Display Genérico (Incell): ${precio_generico:,} MXN\n"
    respuesta += f"• Display Original: ${precio_original:,} MXN\n"
    respuesta += "\nAmbos con diagnóstico, garantía 90 días y cambio el mismo día. ¿Cuál te interesa?"

    logger.info(f"[PRICING] 💬 Cotización fallback: {marca} {modelo} → Genérico: ${precio_generico:,}, Original: ${precio_original:,}")
    return respuesta


async def inicializar_cotizador():
    """Inicializa el cotizador global al arrancar el servidor"""
    global _cotizador_global
    try:
        logger.info("[PRICING] Inicializando cotizador global...")
        _cotizador_global = CotizadorPrecios()
        await _cotizador_global.inicializar()
        logger.info("[PRICING] ✅ Cotizador global inicializado")
    except Exception as e:
        logger.error(f"[PRICING] Error inicializando cotizador: {e}")
        _cotizador_global = None


async def obtener_cotizacion_display(marca: str, modelo: str) -> str:
    """
    Obtiene cotización de display para un modelo específico.
    Busca en Hugo Shop cache y retorna texto formateado para el cliente.

    Args:
        marca: Marca del dispositivo (ej: "iPhone", "Samsung")
        modelo: Modelo específico (ej: "16", "S24")

    Returns:
        String con opciones de precio formateado o mensaje de fallback
    """
    logger.info(f"[PRICING] 💰 Buscando cotización: {marca} {modelo}")

    # Si hay cotizador global inicializado, usarlo
    if _cotizador_global:
        logger.info(f"[PRICING] Usando cotizador global inicializado")
        try:
            descripcion = f"{marca} {modelo}".lower()
            cotizacion = await _cotizador_global.cotizar(descripcion)

            if cotizacion and cotizacion.precio_final > 0:
                # Usar el sistema de cotizaciones del CotizadorPrecios
                precio_generico = int(cotizacion.precio_base * MotorMultiplicadores.obtener_multiplicador(
                    FuentePrecio.HUGO_SHOP,
                    CalidadDispositivo.UNKNOWN
                ))
                precio_original = int(cotizacion.precio_final)

                respuesta = f"Para {marca} {modelo} tenemos:\n"
                respuesta += f"• Display Genérico (Incell): ${precio_generico:,} MXN\n"
                respuesta += f"• Display Original: ${precio_original:,} MXN\n"
                respuesta += "\nAmbos incluyen diagnóstico, garantía 90 días y cambio el mismo día. ¿Cuál te interesa?"

                logger.info(f"[PRICING] ✅ Cotización generada por CotizadorPrecios: {marca} {modelo}")
                return respuesta
        except Exception as e:
            logger.warning(f"[PRICING] Error usando CotizadorPrecios: {e}, fallback a cache local")

    # Fallback: intentar cargar desde cache local
    try:
        cache_manager = CacheManager()
        productos = cache_manager.cargar_hugo_shop()

        if not productos:
            logger.warning(f"[PRICING] ⚠️ Cache Hugo Shop vacío, usando fallback genérico para: {marca} {modelo}")
            # Generar cotización de fallback
            return _generar_cotizacion_fallback(marca, modelo)

        # Buscar productos que coincidan
        consulta = f"{marca} {modelo}".lower()
        coincidencias = [p for p in productos if consulta in p.get("DESCRIPCIÓN", "").lower()]

        if not coincidencias:
            logger.warning(f"[PRICING] Sin coincidencias en cache para: {consulta}, usando fallback")
            return _generar_cotizacion_fallback(marca, modelo)

        # Procesar cotizaciones (máximo 2 opciones: genérico y original)
        cotizaciones = []
        for producto in coincidencias[:2]:
            try:
                precio_base = float(producto.get("PRECIO_1", 0))
                if precio_base <= 0:
                    continue

                descripcion = producto.get("DESCRIPCIÓN", "")
                calidad = DetectorDispositivo.detectar_calidad(descripcion)
                multiplicador = MotorMultiplicadores.obtener_multiplicador(
                    FuentePrecio.HUGO_SHOP,
                    calidad
                )
                precio_final = int(precio_base * multiplicador)

                # Determinar etiqueta (Genérico o Original)
                if "original" in descripcion.lower() or calidad in [CalidadDispositivo.OLED, CalidadDispositivo.AMOLED]:
                    etiqueta = "Original"
                else:
                    etiqueta = "Genérico (Incell)"

                cotizaciones.append({
                    "etiqueta": etiqueta,
                    "precio": precio_final,
                    "calidad": calidad.value
                })
            except (ValueError, KeyError):
                continue

        if not cotizaciones:
            return "Para ese modelo te doy el precio exacto en el diagnóstico (2 horas)."

        # Formatear respuesta para el cliente
        respuesta = f"Para {marca} {modelo} tenemos:\n"
        for cot in cotizaciones[:2]:
            respuesta += f"• Display {cot['etiqueta']}: ${cot['precio']:,} MXN\n"

        respuesta += "\nAmbos incluyen diagnóstico, garantía 90 días y cambio el mismo día. ¿Cuál te interesa?"

        logger.info(f"[PRICING] ✅ Cotización generada desde cache: {marca} {modelo}")
        return respuesta

    except Exception as e:
        logger.error(f"[PRICING] 🚨 Error obteniendo cotización: {e}")
        # Fallback final
        return _generar_cotizacion_fallback(marca, modelo)
