# 🔍 DIAGNÓSTICO: Problema de Precios iPhone 14 Pro — 26 Mayo 2026

## 📊 Situación Actual

**Lo que reportaste:**
```
"no retorna precios solo de iphone 14 pero mal 
da el mismo precio en la calidad generica y calidad original"
```

**Logs de Railway:**
```
[PRICING] Cotización: iPhone 14 Pro (OLED) → Genérico: $7,040, Original: $7,040
```

---

## 🧪 Análisis Local

He ejecutado el mismo código localmente (`agent/pricing.py`) y **funciona correctamente**:

```
Para iphone 14 pro tenemos estas opciones:

* Display Genérico: $2,082 MXN      ✓ Diferente
* Display Calidad Original: $4,508 MXN  ✓ Diferente
* Display AMOLED: $5,216 MXN        ✓ Diferente
```

### Desglose de cálculos locales:

**GENERICO:**
- X14 PRO: $398 USD
- X14PRO (MOVIL IC)- 120HZ: $385 USD
- X14PRO MAX CARTAN: $464 USD
- X14PRO MAX(MOVIL IC): $483 USD
- X14PRO MAX(MOVIL IC): $846 USD
- X14PRO(MOVIL IC): $548 USD
- **Promedio: $520.67 USD × 4 = $2,082 MXN** ✓

**ORIGINAL:**
- X14PRO (MOVIL IC): $1,080 USD
- X14PRO MAX: $1,240 USD
- X14PRO MAX (MOVIL IC): $996 USD
- X14PRO(MOVIL IC): $1,192 USD
- **Promedio: $1,127 USD × 4 = $4,508 MXN** ✓

**AMOLED:**
- X14PRO MAX-(Diagnostico): $1,250 USD
- X14PRO-(Diagnostico): $1,358 USD
- **Promedio: $1,304 USD × 4 = $5,216 MXN** ✓

---

## 🚨 Conclusión

**El problema NO es el código** — funciona perfectamente en local.

**El problema PROBABLEMENTE es:**
1. El CSV en Railway es diferente (está corrupto, incompleto o tiene datos incorrectos)
2. O el CSV no se cargó correctamente al hacer el deploy
3. O hay un caché antiguo en Railway que no se limpió

**No explicaría $7,040 en ambas categorías:**
- $7,040 / 4 = $1,760 USD promedio
- Esto NO coincide con ninguno de nuestros promedios locales

---

## ✅ Cómo Diagnosticar en Railway

He creado un script de diagnóstico que puedes ejecutar en Railway:

### Opción 1: Via Railway CLI (más rápido)

```bash
# 1. Conéctate a Railway
railway login

# 2. Ejecuta el script directamente en el servidor
railway run python diagnostic_pricing.py
```

### Opción 2: Via Dashboard (más lento pero visible)

1. Ve a https://railway.app/dashboard
2. Abre tu proyecto "tecnology-support-agent"
3. Click en la tab "Deployments"
4. Click en el último deploy (verde/success)
5. Busca los logs para ver cualquier error al cargar CSV

### Opción 3: Añade logging temporal a Railway

Si quieres ver qué está pasando en tiempo real:

1. Abre `agent/pricing.py`
2. Añade esta línea al inicio de `buscar_productos_en_csv()` (alrededor de línea 140):

```python
logger.info(f"[PRICING] DEBUG: Encontrados {len(resultados)} productos para {marca} {modelo}")
for prod in resultados[:3]:  # Primeros 3
    logger.info(f"[PRICING] DEBUG: {prod.get('DESCRIPCION')} - CALIDAD: {prod.get('CALIDAD')} - PRECIO: {prod.get('PRECIO_1')}")
```

3. Haz git push
4. Monitorea los logs en Railway mientras escribes "test precio iphone 14 pro" en WhatsApp

---

## 🛠️ Posibles Soluciones

### Solución 1: Recargar CSV en Railway

A veces el CSV no se carga correctamente. Prueba esto:

1. En Railway → Tu proyecto → Settings → Environment → Variables
2. Añade una variable temporal: `RELOAD_CSV=true`
3. Haz un deploy (el código buscará esta variable al iniciar)
4. Observa los logs
5. Elimina la variable después

### Solución 2: Verificar integridad del CSV en Railway

El CSV podría estar corrupto. Ejecuta en Railway:

```bash
railway run python -c "
from agent.pricing import cargar_csv_hugo
datos = cargar_csv_hugo()
print(f'Total productos cargados: {len(datos)}')
for prod in datos[:5]:
    print(prod.get('DESCRIPCION', '?'))
"
```

Si retorna menos de 1000 productos, el CSV es el problema.

### Solución 3: Reinstalar CSV en Railway

1. Descarga el CSV limpio local:
   ```bash
   cp knowledge/hugo_shop.csv knowledge/hugo_shop_backup.csv
   ```

2. Limpia y recodifica el CSV:
   ```bash
   python -c "
import pandas as pd
df = pd.read_csv('knowledge/hugo_shop.csv', encoding='utf-8')
df.to_csv('knowledge/hugo_shop_clean.csv', encoding='utf-8', index=False)
"
   ```

3. Actualiza `agent/pricing.py` línea 17:
   ```python
   RUTA_CSV_HUGO = 'knowledge/hugo_shop_clean.csv'
   ```

4. Haz git push y verifica el resultado

---

## 📋 Checklist de Diagnóstico

- [ ] Ejecuté `diagnostic_pricing.py` en Railway
- [ ] Verifiqué los logs de Railway buscando errores al cargar CSV
- [ ] Conté cuántos productos se cargaron en Railway (debe ser ~1094)
- [ ] Verifiqué que los primeros 3 productos de iphone 14 pro tengan precios diferentes
- [ ] Probé "test precio iphone 14 pro" en WhatsApp después del diagnóstico
- [ ] El agente ahora retorna precios diferentes para cada categoría ✓

---

## 🔗 Archivos Relacionados

- `agent/pricing.py` — Motor de cotización (líneas 143-250 son críticas)
- `knowledge/hugo_shop.csv` — Base de datos de productos
- `diagnostic_pricing.py` — Script de diagnóstico (nuevo)

---

## 📞 Siguiente Paso

1. **Ejecuta el diagnóstico en Railway** usando uno de los métodos arriba
2. **Comparte conmigo los logs** que genere
3. Basado en eso, ajustaremos lo necesario

¿Necesitas ayuda para ejecutar el diagnostic script?
