# MercadoLibre Scraping — Fix para Railway Crash

## El Problema
- BeautifulSoup (`bs4`) no estaba en `requirements.txt` → crash en Railway
- Scraping frágil a cambios de HTML en MercadoLibre
- Sin reintentos ni caché → timeout frecuentes

## La Solución
**`pricing_mercadolibre_v2.py`** — Scraper robusto con:

✅ **Caché inteligente** — Guarda precios por 4 horas  
✅ **Reintentos automáticos** — 3 intentos con espera entre ellos  
✅ **Múltiples parsers** — Si ML cambia HTML, intenta alternativas  
✅ **Fallback a caché expirado** — Mejor dar un precio viejo que fallar  
✅ **Timeout más largo** — 30s en lugar de 10s  

## Flujo de Cotización

```
Cliente pregunta: "¿Cuánto cuesta una batería para motorola g85?"
          ↓
Hugo Shop → ¿Tienes batería motorola g85?
          ↓
NO → MercadoLibre (via pricing_mercadolibre_v2.py)
          ↓
¿Existe en caché vigente (< 4 horas)?
          SÍ → Devolver precio del caché (rápido ⚡)
          NO → Scraping con 3 reintentos
               ↓
               ¿Encontró precio?
               SÍ → Guardar en caché + devolver
               NO → ¿Hay caché expirado?
                    SÍ → Usar precio viejo
                    NO → No disponible
```

## Cambios Realizados

### 1. **requirements.txt**
Agregado:
```
beautifulsoup4>=4.12.0
requests>=2.31.0
```

### 2. **pricing_mercadolibre_v2.py** (nuevo)
Clase `BuscadorMercadoLibreV2` con:
- Tabla `PrecioMercadoLibreCache` en SQLite
- 3 estrategias de parsing de HTML
- Retry logic con backoff exponencial
- Fallback inteligente a caché

### 3. **pricing_integration.py**
Actualizado para usar la versión v2:
```python
from agent.pricing_mercadolibre_v2 import cotizar_refaccion_mercadolibre_v2
```

### 4. **memory.py**
Agregado import en `inicializar_db()` para registrar tabla de caché

---

## Prueba Local Antes de Push

### 1️⃣ Instala dependencias nuevas
```bash
pip install -r requirements.txt
```

### 2️⃣ Ejecuta el test
```bash
python test_mercadolibre.py
```

**Esperado:**
```
   ▶ Cotizando: batería para motorola g85
     ✅ Encontrado (fuente: scrape)
        Genérico: $600 MXN
        Original: $1,000 MXN
```

En la segunda ejecución, verás `fuente: cache` (significa que funcionó el caché).

### 3️⃣ Si todos los precios salen `None`
- MercadoLibre está bloqueando requests
- Intenta con VPN o espera 30 minutos
- El caché fallback seguirá funcionando aunque haya error temporal

---

## Deploy a Railway

### 1️⃣ Commit y push
```bash
git add requirements.txt agent/pricing_mercadolibre_v2.py agent/pricing_integration.py agent/memory.py test_mercadolibre.py

git commit -m "feat: scraping robusto de MercadoLibre con caché y reintentos

- Agregar pricing_mercadolibre_v2.py con múltiples estrategias de parsing
- Implementar tabla de caché precios_ml_cache en SQLite
- Retry logic: 3 intentos con backoff exponencial
- Fallback a caché expirado si todo falla
- Timeout aumentado a 30s
- Agregar beautifulsoup4 y requests a requirements.txt
- Fixes crash de Railway causado por bs4 faltante"

git push origin main
```

### 2️⃣ Railway auto-redeploy
- Esperá 2-3 minutos para que Railway detecte cambios
- Verás en los logs: `[BD] Tablas listas: ... precios_ml_cache`

### 3️⃣ Monitoreo
En Railway → Logs, busca:
```
[ML CACHE VÁLIDO]    ← Usando caché (rapido ⚡)
[ML SCRAPE INICIO]   ← Haciendo scraping
[ML ÉXITO]           ← Scraping exitoso
[ML INTENTO 1/3]     ← Reintentando
[ML FALLBACK]        ← Usando caché expirado
[ML FALLO TOTAL]     ← No encontró (devuelve "no disponible")
```

---

## Tu Modelo de Negocio (Resumido)

| Categoría | Fuente | Margen |
|-----------|--------|--------|
| **Displays** | Hugo Shop (BD local) | 2-3x |
| **Otras refacciones** | MercadoLibre (scraping) | 4x |
| **Ejemplo** | Batería ML: $150 → Tú: $600 | 4x |

**Ventaja:** Cotizas EN TIEMPO REAL → Precios justos → Clientes pagan, no leads basura.

---

## Respuestas Frecuentes

### ¿Qué pasa si MercadoLibre me bloquea?
El caché sigue funcionando por 4 horas. Después, verás "no disponible" pero sin que la app se caiga.

### ¿Por qué caché de 4 horas?
- Los aranceles no cambian hora a hora
- 4h es un balance: datos frescos pero sin abrumar a ML

### ¿Puedo ajustar el multiplicador × 4?
Sí, edita `MULTIPLICADOR_MARGEN` en `pricing_mercadolibre_v2.py`.

### ¿Cómo limpiar la caché manualmente?
```sql
DELETE FROM precios_ml_cache;
```
Accedes via Railway → Data → PostgreSQL (o CLI).

---

## Rollback (si algo sale mal)

Si después del push ves crashes:

```bash
git revert HEAD
git push origin main
# Railway redeploy automático
```

---

## Siguiente Paso (Opcional, Futuro)

Cuando quieras reducir dependencias o acelerar:
- **API de precios** (MarketStack, API.cloud) — más fiable que scraping
- **Base datos local** — lista de precios que actualizas manualmente 1x/mes
- **Webhook de ML** — si ellos ofrecen (no ofrecen, pero buena idea)

Por ahora, **este fix debería darte estabilidad y velocidad**.

---

**Creado:** 1 de junio 2026  
**Autor:** Claude + Christian (Tech Support)  
**Estado:** ✅ Listo para producción
