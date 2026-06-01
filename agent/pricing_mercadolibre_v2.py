# agent/pricing_mercadolibre_v2.py — Web scraping robusto con Playwright + caché + reintentos
# Versión mejorada: usa Playwright para renderizar JavaScript, con fallback inteligente

import logging
import asyncio
import json
import re
from typing import Optional, Dict
from datetime import datetime, timedelta
from sqlalchemy import select, String, Float, DateTime, Integer
from sqlalchemy.orm import Mapped, mapped_column

logger = logging.getLogger("agentkit")

# Verificar que Playwright está disponible
try:
    from playwright.async_api import async_playwright
    PLAYWRIGHT_AVAILABLE = True
    logger.info("[ML] ✅ Playwright disponible para scraping robusto")
except ImportError:
    logger.error("[ML] ❌ Playwright no instalado. Web scraping de MercadoLibre desactivado.")
    PLAYWRIGHT_AVAILABLE = False

# NO importar Base/async_session aquí — causa ciclo circular con memory.py
# Se importan dinámicamente cuando se usan
Base = None
async_session = None

# Configuración
MULTIPLICADOR_MARGEN = 4.0  # Tu multiplicador: costo ML × 4 = precio cliente
CACHE_DURACION_HORAS = 4    # Caché válido por 4 horas
TIMEOUT_SCRAPE = 30000      # 30 segundos en milisegundos para Playwright
MAX_REINTENTOS = 3
RETRY_DELAY = 2             # segundos entre reintentos


# Clase de caché — se define dinámicamente para evitar importación circular
PrecioMercadoLibreCache = None

def _crear_tabla_cache():
    """Crea la clase PrecioMercadoLibreCache dinámicamente para evitar ciclo circular."""
    global PrecioMercadoLibreCache
    if PrecioMercadoLibreCache is not None:
        return  # Ya creada

    if not PLAYWRIGHT_AVAILABLE:
        logger.warning("[ML] Playwright no disponible, caché desactivado")
        return

    try:
        from agent.memory import Base as _Base

        class _PrecioMercadoLibreCache(_Base):
            """Tabla para cachear precios de MercadoLibre"""
            __tablename__ = "precios_ml_cache"

            id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
            refaccion: Mapped[str] = mapped_column(String(200), index=True)
            modelo: Mapped[str] = mapped_column(String(200), index=True)
            precio_generico_ml: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
            precio_original_ml: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
            timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
            datos_crudos: Mapped[Optional[str]] = mapped_column(String(2000))

            def esta_vigente(self) -> bool:
                """Verifica si el caché sigue siendo válido"""
                vencimiento = self.timestamp + timedelta(hours=CACHE_DURACION_HORAS)
                return datetime.utcnow() < vencimiento

            def __repr__(self):
                return f"<Cache ML: {self.refaccion} {self.modelo} @ {self.timestamp}>"

        PrecioMercadoLibreCache = _PrecioMercadoLibreCache
        logger.debug("[ML] Tabla PrecioMercadoLibreCache creada dinámicamente")
    except ImportError as e:
        logger.warning(f"[ML] No se pudo crear tabla caché: {e}")
        PrecioMercadoLibreCache = None


class BuscadorMercadoLibreV2:
    """Web scraper robusto con Playwright (renderiza JavaScript)"""

    def __init__(self):
        self.url_base = "https://listado.mercadolibre.com.mx"

    async def obtener_precio_con_cache(
        self, refaccion: str, modelo: str
    ) -> Optional[Dict]:
        """
        Obtiene precio: primero intenta caché, luego scraping con reintentos
        """
        if not PLAYWRIGHT_AVAILABLE:
            logger.error("[ML] Playwright no disponible, scraping desactivado")
            return None

        # 1. Intentar caché primero
        cache = await self._obtener_del_cache(refaccion, modelo)
        if cache and cache.esta_vigente():
            logger.info(f"[ML CACHE VÁLIDO] {refaccion} {modelo}")
            return self._formatear_resultado_cache(cache, fuente="cache")

        # 2. Caché expirado o no existe → scraping con reintentos
        logger.info(f"[ML SCRAPE INICIO] {refaccion} {modelo} (reintentos: {MAX_REINTENTOS})")

        for intento in range(1, MAX_REINTENTOS + 1):
            try:
                resultado = await self._scrape_mercadolibre_playwright(refaccion, modelo)
                if resultado:
                    # Guardar en caché
                    await self._guardar_en_cache(refaccion, modelo, resultado)
                    logger.info(f"[ML ÉXITO] {refaccion} {modelo} en intento {intento}")
                    return resultado

            except Exception as e:
                logger.warning(f"[ML INTENTO {intento}/{MAX_REINTENTOS}] Falló: {e}")
                if intento < MAX_REINTENTOS:
                    await asyncio.sleep(RETRY_DELAY)

        # 3. Scraping falló completamente → fallback a caché expirado
        if cache:
            logger.warning(f"[ML FALLBACK] Usando caché expirado para {refaccion} {modelo}")
            return self._formatear_resultado_cache(cache, fuente="cache_expirado")

        # 4. Nada funcionó
        logger.error(f"[ML FALLO TOTAL] No se encontró {refaccion} {modelo}")
        return None

    async def _scrape_mercadolibre_playwright(self, refaccion: str, modelo: str) -> Optional[Dict]:
        """
        Scraping con Playwright - BÚSQUEDAS SEPARADAS + FILTRO NACIONAL.

        Estrategia:
        1. Busca SEPARADAS: "genérico" y "original" (garantiza categoría correcta)
        2. Extrae MÚLTIPLES precios de cada búsqueda
        3. Filtra solo VENDEDORES NACIONALES (bloquea internacionales)
        4. Selecciona 3º PRECIO MÁS BAJO (evita stock agotado en 1º lugar)
        5. Retorna genérico y original por separado
        """
        resultado = {}

        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                context = await browser.new_context(
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                )
                page = await context.new_page()

                # BÚSQUEDAS SEPARADAS (no mezcladas)
                búsquedas = {
                    "generico": f"{refaccion} {modelo} genérico",
                    "original": f"{refaccion} {modelo} original",
                }

                for tipo, query in búsquedas.items():
                    try:
                        url = f"{self.url_base}/{query.replace(' ', '-')}"
                        logger.debug(f"[ML] Navegando a {tipo}: {url}")

                        await page.goto(url, wait_until="networkidle", timeout=TIMEOUT_SCRAPE)
                        await asyncio.sleep(1)

                        html = await page.content()

                        # Extraer precios NACIONALES SOLO
                        precios = self._extraer_precios_nacionales(html)

                        if precios:
                            # Ordenar menor a mayor
                            precios_unicos = sorted(set(precios))

                            # Seleccionar 3º más bajo (evita agotados/lotes)
                            # Si hay menos de 3, tomar el máximo disponible
                            idx = min(2, len(precios_unicos) - 1)  # índice 2 = 3º elemento
                            precio_seleccionado = precios_unicos[idx]

                            resultado[tipo] = precio_seleccionado
                            logger.info(
                                f"[ML {tipo.upper()}] {len(precios_unicos)} precio(s) nacional(es): "
                                f"{precios_unicos[:5]} ... → Seleccionado 3º: ${precio_seleccionado:.0f} MXN"
                            )
                        else:
                            logger.debug(f"[ML] No se encontraron precios nacionales para {tipo}")

                    except Exception as e:
                        logger.warning(f"[ML] Error scrapeando {tipo}: {e}")

                await browser.close()

        except Exception as e:
            logger.error(f"[ML] Error Playwright: {e}")

        if not resultado.get("generico"):
            return None

        # Construir respuesta final
        precio_generico = resultado.get("generico")
        precio_original = resultado.get("original", precio_generico)

        return {
            "refaccion": refaccion,
            "modelo": modelo,
            "precio_generico": int(precio_generico * MULTIPLICADOR_MARGEN) if precio_generico else None,
            "precio_original": int(precio_original * MULTIPLICADOR_MARGEN) if precio_original and precio_original != precio_generico else None,
            "timestamp": datetime.utcnow().isoformat(),
            "fuente": "scrape",
        }

    def _extraer_precios_nacionales(self, html: str) -> list[float]:
        """
        Extrae precios NACIONALES SOLO.
        Bloquea: envíos internacionales, "envío desde [país]", China, USA, etc.
        Mantiene: "Envío a todo México", "Envío nacional", "Desde México"
        """
        precios = []

        # Palabras clave que indican INTERNACIONAL (a bloquear)
        bloqueadas = [
            "enviado desde", "envío desde",
            "usa", "china", "internacional", "from usa", "from china",
            "tardan", "días hábiles", "meses", "semanas",
            "extranjero", "overseas", "import",
        ]

        # Palabras clave que garantizan NACIONAL (permitir)
        nacional_keywords = [
            "méxico", "envío a todo", "envío nacional",
            "stock en méxico", "disponible méxico",
        ]

        html_lower = html.lower()

        # Verificar si la página CONTIENE indicadores internacionales
        tiene_internacionales = any(palabra in html_lower for palabra in bloqueadas)

        # Si tiene internacionales pero también tiene keywords nacionales, proceder
        # Si es SOLO internacional, bloquear
        if tiene_internacionales and not any(kw in html_lower for kw in nacional_keywords):
            logger.debug("[ML] Página contiene solo vendedores internacionales - BLOQUEADO")
            return []

        # Extraer precios (mismo método que antes, pero con contexto nacional)
        # Patrón 1: data-price attributes
        matches = re.findall(r'data-price=["\']([0-9.,]+)["\']', html)
        for match in matches:
            precio = self._limpiar_precio(match)
            if precio and precio > 0:
                precios.append(precio)

        # Patrón 2: spans con clase de precio estándar ML
        matches = re.findall(
            r'<span[^>]*class="[^"]*andes-money-amount__fraction[^"]*"[^>]*>([^<]+)</span>',
            html
        )
        for match in matches:
            precio = self._limpiar_precio(match)
            if precio and precio > 0:
                precios.append(precio)

        # Patrón 3: búsqueda general de números con formato de precio
        matches = re.findall(r'\$\s*[\d.,]+', html)
        for match in matches:
            precio_str = match.replace("$", "").strip()
            precio = self._limpiar_precio(precio_str)
            if precio and precio > 0:
                precios.append(precio)

        logger.debug(f"[ML NACIONAL] Extraídos {len(precios)} precios (filtrado internacional)")
        return precios if precios else []

    def _extraer_todos_precios_de_html(self, html: str) -> list[float]:
        """DEPRECATED - usar _extraer_precios_nacionales() en su lugar"""
        return self._extraer_precios_nacionales(html)

    def _extraer_precio_de_html(self, html: str) -> Optional[float]:
        """Extrae PRIMER precio del HTML (deprecated, usar _extraer_todos_precios_de_html)"""
        precios = self._extraer_todos_precios_de_html(html)
        return precios[0] if precios else None

    def _limpiar_precio(self, texto: str) -> Optional[float]:
        """Convierte string de precio a float"""
        try:
            limpio = texto.replace("$", "").strip()

            # Detectar si usa coma o punto como separador decimal
            if limpio.count(",") > limpio.count("."):
                # Formato Latino: 1.500,00 → 1500.00
                limpio = limpio.replace(".", "").replace(",", ".")
            else:
                # Formato USA: 1,500.00 → 1500.00
                limpio = limpio.replace(",", "")

            precio = float(limpio)
            return precio if precio > 0 else None
        except (ValueError, AttributeError):
            return None

    async def _obtener_del_cache(
        self, refaccion: str, modelo: str
    ) -> Optional[object]:
        """Obtiene precio del caché si existe"""
        if PrecioMercadoLibreCache is None:
            return None

        try:
            from agent.memory import async_session as _async_session
            async with _async_session() as session:
                query = select(PrecioMercadoLibreCache).where(
                    (PrecioMercadoLibreCache.refaccion == refaccion)
                    & (PrecioMercadoLibreCache.modelo == modelo)
                )
                result = await session.execute(query)
                return result.scalars().first()
        except Exception as e:
            logger.warning(f"Error al leer caché: {e}")
            return None

    async def _guardar_en_cache(
        self, refaccion: str, modelo: str, resultado: Dict
    ) -> bool:
        """Guarda precio en caché"""
        if PrecioMercadoLibreCache is None:
            return False

        try:
            from agent.memory import async_session as _async_session
            async with _async_session() as session:
                cache = PrecioMercadoLibreCache(
                    refaccion=refaccion,
                    modelo=modelo,
                    precio_generico_ml=resultado.get("precio_generico"),
                    precio_original_ml=resultado.get("precio_original"),
                    timestamp=datetime.utcnow(),
                    datos_crudos=json.dumps(resultado),
                )
                session.add(cache)
                await session.commit()
                logger.info(f"[CACHÉ GUARDADO] {refaccion} {modelo}")
                return True
        except Exception as e:
            logger.error(f"Error al guardar caché: {e}")
            return False

    def _formatear_resultado_cache(
        self, cache: object, fuente: str = "cache"
    ) -> Dict:
        """Convierte registro de caché a formato de respuesta"""
        return {
            "refaccion": cache.refaccion,
            "modelo": cache.modelo,
            "precio_generico": int(cache.precio_generico_ml * MULTIPLICADOR_MARGEN)
            if cache.precio_generico_ml else None,
            "precio_original": int(cache.precio_original_ml * MULTIPLICADOR_MARGEN)
            if cache.precio_original_ml else None,
            "timestamp": cache.timestamp.isoformat(),
            "fuente": fuente,
        }


# API pública
async def cotizar_refaccion_mercadolibre_v2(
    refaccion: str, modelo: str
) -> Optional[Dict]:
    """
    Cotiza una refacción en MercadoLibre con caché + reintentos
    Retorna None si Playwright no está disponible o si hay error crítico.
    """
    if not PLAYWRIGHT_AVAILABLE:
        logger.error("[ML] Web scraping desactivado: Playwright no disponible")
        return None

    if async_session is None:
        logger.error("[ML] Web scraping desactivado: async_session no disponible")
        return None

    buscador = BuscadorMercadoLibreV2()
    return await buscador.obtener_precio_con_cache(refaccion, modelo)
