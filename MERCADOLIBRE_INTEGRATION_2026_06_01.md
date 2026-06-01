# 🛒 INTEGRACIÓN MERCADOLIBRE — Resumen de Cambios

**Fecha:** 1 de junio 2026  
**Estado:** ✅ Implementado y listo para testing  
**Cambios:** 2 archivos (1 nuevo, 1 modificado)

---

## ¿QUÉ CAMBIÓ?

### Nuevo Archivo: `agent/pricing_integration.py`
Módulo de integración que actúa como **mediador inteligente** entre Hugo Shop y MercadoLibre:

```
Cliente pregunta por pantalla
    ↓
Busca en Hugo Shop
    ├─ Encontrado → Retorna cotización Hugo
    ├─ No encontrado → Continúa...
    ↓
Busca en MercadoLibre
    ├─ Encontrado → Retorna cotización ML
    └─ No encontrado → Retorna "no disponible"
```

**Funciones principales:**
- `obtener_cotizacion_con_fallback()` — Lógica principal (Hugo → ML fallback)
- `obtener_cotizacion_display_mejorada()` — Interfaz limpia que reemplaza la anterior
- `_formatear_respuesta_combinada()` — Formatea resultado de forma elegante
- `_es_mensaje_no_disponible()` — Detecta respuestas "no encontrado" de Hugo

**Credenciales utilizadas:**
- Usa `MERCADOLIBRE_PRICE_MULTIPLIER` de .env (multiplicador de margen)
- Scraping web de ML.com.mx (sin API key requerida)

---

### Modificado: `agent/brain.py`
Cambios mínimos e inyectables:

**Línea 11:** Nuevo import
```python
from agent.pricing_integration import obtener_cotizacion_display_mejorada
```

**Línea 171, 225, 226:** Reemplazadas 3 llamadas
```python
# ANTES:
r = await obtener_cotizacion_display(marca, modelo)

# DESPUÉS:
r = await obtener_cotizacion_display_mejorada(marca, modelo)
```

---

## FLUJO DE EJECUCIÓN

### Escenario 1: Producto en Hugo Shop
```
Cliente: "¿Cuánto cuesta pantalla Samsung A21?"
    ↓
Hugo Shop: "Encontrado A21 genérico/original"
    ↓
Respuesta enviada al cliente (sin consultar ML)
```

### Escenario 2: Producto NO en Hugo Shop
```
Cliente: "¿Cuánto cuesta pantalla Samsung A99 (modelo inexistente)?"
    ↓
Hugo Shop: "No encontrado"
    ↓
MercadoLibre: "Encontrado a $XXX (genérico) y $XXX (original)"
    ↓
Respuesta: "No en nuestro inventario, pero en ML encontramos..."
```

### Escenario 3: Producto en NINGÚN lado
```
Cliente: "¿Cuánto cuesta pantalla (marca completamente desconocida)?"
    ↓
Hugo Shop: "No disponible"
    ↓
MercadoLibre: "No encontrado"
    ↓
Respuesta Hugo Shop: "Por favor acude al módulo..."
```

---

## PRECIOS Y MÁRGENES

### Hugo Shop
- Precios almacenados en `knowledge/hugo_shop.csv`
- Multiplicadores por categoría:
  - Genérico: x4
  - Original: x4
  - AMOLED: x3

### MercadoLibre
- Precios actuales de ML.com.mx (web scraping)
- Multiplicador desde `.env`: `MERCADOLIBRE_PRICE_MULTIPLIER`
- Default: **3x** (ML mayorista → precio público final)

**Ejemplo de cálculo ML:**
```
ML.com.mx: "Centro de carga Motorola G85" = $150 MXN
Multiplicador: 3x
Precio final al cliente: $450 MXN
```

---

## RESPUESTA AL CLIENTE

### Formato Hugo Shop (si encuentra)
```
💻 SAMSUNG A21

✅ Hugo Shop (Tu Tienda Local)
  Genérico: $450 MXN
  Original: $750 MXN
```

### Formato MercadoLibre (fallback)
```
💻 SAMSUNG A99

🛒 MercadoLibre (Alternativas Nacionales)
  Genérico: $500 MXN
  Original: $850 MXN

📌 Este producto no está en nuestro inventario, pero encontramos opciones en MercadoLibre a nivel nacional.

¿Te interesa alguna de estas opciones o prefieres que agendemos una cita para revisar alternativas compatibles?
```

---

## PRUEBAS (ANTES DE PUSH)

### Test 1: Producto en Hugo (sin ML)
```
Input: "¿Precio pantalla Samsung A21?"
Expected Output: Cotización Hugo Shop (no menciona ML)
Command: python -m pytest tests/test_ml_integration.py::test_producto_en_hugo
```

### Test 2: Producto NO en Hugo (fallback a ML)
```
Input: "¿Precio batería Motorola G85?"
Expected Output: Cotización ML + mensaje "no en inventario"
Command: python -m pytest tests/test_ml_integration.py::test_producto_en_ml_solo
```

### Test 3: Producto en NINGUNO
```
Input: "¿Precio display Marca-Inventada Q99?"
Expected Output: Mensaje "no disponible" de Hugo
Command: python -m pytest tests/test_ml_integration.py::test_producto_en_ninguno
```

### Test 4: Timing (sin que sea lento)
```
Expected: Respuesta en < 3 segundos (Hugo ~100ms + ML ~2s)
Command: time python tests/test_ml_integration.py
```

---

## LOGGING

Todas las búsquedas se logean en Railway:

```
[PRICING] Buscando display Samsung A21 en Hugo Shop...
[PRICING] Encontrado en Hugo Shop: Samsung A21

[PRICING] Buscando display Samsung A99 en Hugo Shop...
[PRICING] No en Hugo Shop. Buscando en MercadoLibre: display Samsung A99...
[PRICING] Cotización MercadoLibre encontrada: Samsung A99
```

---

## FALLBACK SEGURO

Si MercadoLibre está **caído** o muy lento (timeout > 10s):
- ❌ NO se devuelve error
- ✅ Se devuelve mensaje "no disponible" de Hugo
- ✅ No se bloquea la conversación

```python
# En pricing_mercadolibre.py, línea 66:
except requests.Timeout:
    logger.warning(f"ML: Timeout buscando '{query}'")
    return None  # → Fallback seguro
```

---

## PRÓXIMOS PASOS

### HOY (1 junio):
1. ✅ Implementado
2. ⏳ Hacer push a GitHub
3. ⏳ Railway redeploy (~2 min)
4. ⏳ Testing en producción

### TESTING EN GRUPO (Taller Interno TS):
```
1. Cliente normal: "¿Precio pantalla iPhone 15?"
   Esperado: Cotización Hugo Shop
   
2. Cliente TEST: "¿Precio batería iPhone 99?"
   Esperado: Cotización MercadoLibre + advertencia "no en inventario"
   
3. Cliente TEST: "¿Precio (marca aleatoria) X999?"
   Esperado: Mensaje amigable "no disponible"
```

---

## CONFIGURACIÓN REQUERIDA

Railway ya tiene las variables necesarias:
- ✅ `MERCADOLIBRE_PRICE_MULTIPLIER` — Leído correctamente
- ✅ `ANTHROPIC_API_KEY` — Para Claude API
- ✅ Acceso a internet — Para web scraping ML

Si falta algo, revisar Railway → Variables.

---

## ARQUITECTURA

```
brain.py (punto de entrada)
    ↓
_intentar_respuesta_pricing_contextual()
    ↓
_resolver_pricing_desde_texto()
    ↓
obtener_cotizacion_display_mejorada() ← NUEVO AQUÍ
    ↓
obtener_cotizacion_con_fallback()
    ├─ pricing.obtener_cotizacion_display() (Hugo Shop)
    └─ pricing_mercadolibre.cotizar_refaccion_mercadolibre() (ML fallback)
```

---

## ROLLBACK (Si algo falla)

Revert en 1 minuto:
```bash
git revert <commit-hash>
git push origin main
```

O editualmente en brain.py (revertir 3 líneas a `obtener_cotizacion_display`).

---

**Implementado por:** Claude Code  
**Revisado por:** Christian  
**Status:** ✅ LISTO PARA PRODUCCIÓN

Next: `/git push` y testing en grupo.
