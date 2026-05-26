# agent/pricing_mercadolibre.py — Web scraping de precios en MercadoLibre
# Para refacciones que Hugo Shop no vende (centros de carga, baterías, tapas traseras, etc)

import requests
import logging
import asyncio
from typing import Optional, Dict, Tuple
from bs4 import BeautifulSoup
from datetime import datetime

logger = logging.getLogger("agentkit")

# Multiplicador para márgenes de ganancia
# ML vende a mayoristas, nosotros vendemos al público final
MULTIPLICADOR_MARGEN = 3.0

# Encabezados para no ser bloqueados por ML
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}


class BuscadorMercadoLibre:
    """Web scraper ligero de MercadoLibre para refacciones"""

    def __init__(self):
        self.url_base = "https://listado.mercadolibre.com.mx"
        self.timeout = 10

    def buscar_precio_ml(self, query: str) -> Optional[float]:
        """
        Busca un producto en ML y retorna el precio del primer resultado

        Args:
            query: Búsqueda (ej: "centro de carga motorola g85")

        Returns:
            Precio en MXN o None si no encuentra
        """
        try:
            # URL de búsqueda
            url = f"{self.url_base}/{query.replace(' ', '-')}"

            response = requests.get(url, headers=HEADERS, timeout=self.timeout)
            response.raise_for_status()

            soup = BeautifulSoup(response.content, 'html.parser')

            # Buscar el primer resultado con clase de precio
            # MercadoLibre usa varias clases, intentamos las comunes
            precio_elementos = soup.find_all('span', class_='andes-money-amount__fraction')

            if precio_elementos:
                # Tomar el primer precio encontrado
                precio_texto = precio_elementos[0].text.strip()
                # Remover puntos de miles (ej: "1.500" -> "1500")
                precio_limpio = precio_texto.replace('.', '').replace(',', '.')
                precio = float(precio_limpio)

                logger.info(f"ML encontró '{query}': ${precio:.2f} MXN")
                return precio
            else:
                logger.warning(f"ML: No se encontró precio para '{query}'")
                return None

        except requests.Timeout:
            logger.warning(f"ML: Timeout buscando '{query}'")
            return None
        except requests.RequestException as e:
            logger.error(f"ML: Error buscando '{query}': {e}")
            return None
        except Exception as e:
            logger.error(f"ML: Error parseando precio para '{query}': {e}")
            return None

    async def cotizar_refaccion_doble(self, refaccion: str, modelo: str) -> Optional[Dict]:
        """
        Cotiza una refacción haciendo dos búsquedas: genérico + original

        Args:
            refaccion: Tipo de refacción (ej: "centro de carga", "batería", "tapa trasera")
            modelo: Modelo del dispositivo (ej: "motorola g85", "iPhone 12")

        Returns:
            Dict con precios multiplicados por 3:
            {
                'refaccion': 'centro de carga',
                'modelo': 'motorola g85',
                'precio_generico': 450,      # ML price * 3
                'precio_original': 750,       # ML price * 3
                'timestamp': '2026-05-21T...'
            }
            O None si no encuentra ninguno
        """

        # Búsqueda 1: Genérico
        query_generico = f"{refaccion} {modelo} genérico"
        precio_generico_ml = await asyncio.to_thread(self.buscar_precio_ml, query_generico)

        # Búsqueda 2: Original
        query_original = f"{refaccion} {modelo} original"
        precio_original_ml = await asyncio.to_thread(self.buscar_precio_ml, query_original)

        # Si no encontró nada, retornar None
        if not precio_generico_ml and not precio_original_ml:
            logger.warning(f"ML: No encontró '{refaccion}' para '{modelo}'")
            return None

        # Aplicar multiplicador (ML -> precio final al cliente)
        precio_generico_final = precio_generico_ml * MULTIPLICADOR_MARGEN if precio_generico_ml else None
        precio_original_final = precio_original_ml * MULTIPLICADOR_MARGEN if precio_original_ml else None

        resultado = {
            'refaccion': refaccion,
            'modelo': modelo,
            'precio_generico': round(precio_generico_final, 0) if precio_generico_final else None,
            'precio_original': round(precio_original_final, 0) if precio_original_final else None,
            'timestamp': datetime.now().isoformat(),
        }

        logger.info(f"Cotización ML: {refaccion} {modelo} → Genérico: ${resultado['precio_generico']}, Original: ${resultado['precio_original']}")
        return resultado


async def cotizar_refaccion_mercadolibre(refaccion: str, modelo: str) -> Optional[Dict]:
    """
    Función pública para cotizar una refacción en MercadoLibre

    Ejemplo de uso:
        resultado = await cotizar_refaccion_mercadolibre("centro de carga", "motorola g85")
        # Retorna:
        # {
        #     'refaccion': 'centro de carga',
        #     'modelo': 'motorola g85',
        #     'precio_generico': 450,
        #     'precio_original': 900,
        #     'timestamp': '2026-05-21T...'
        # }
    """
    buscador = BuscadorMercadoLibre()
    return await buscador.cotizar_refaccion_doble(refaccion, modelo)
