# 🔴 DIAGNÓSTICO CRÍTICO: BUG EN SELECCIÓN DE PRODUCTOS - COTIZACIONES INCORRECTAS

**Fecha:** 2026-06-03  
**Usuario:** Christian (goldbunnyshop@gmail.com)  
**Severidad:** CRÍTICA  
**Área Afectada:** Motor de precios - `pricing_sheets.py` - Scoring/búsqueda de productos

---

## 📋 RESUMEN EJECUTIVO

El motor de pricing está seleccionando el **producto INCORRECTO** de Google Sheets, resultando en cotizaciones muy bajas.

**Ejemplo real:**
- Cliente pregunta: "¿Precio display iPhone 13 mini?"
- Bot responde: "Display Calidad Original: $2,360 MXN" ❌
- Lo correcto sería: "Display de Diagnóstico: ~$4,000 MXN" ✅

---

## 🔍 ANÁLISIS DEL PROBLEMA

### LO QUE PASÓ (Escenario 1: iPhone 13 mini)

```
ENTRADA: "Precio display iPhone 13 mini"
       ↓
BÚSQUEDA en Google Sheets (gid=1452574805 - DISPLAYS)
       ↓
ENCONTRADOS 2 DISPLAYS para iPhone 13 mini:
  1. Display Calidad Original → 590 MXN base × 4 = 2,360 MXN ← SELECCIONADO (INCORRECTO)
  2. Display de Diagnóstico → 1,000 MXN base × 4 = 4,000 MXN ← DEBERÍA SELECCIONAR (CORRECTO)
       ↓
SALIDA: "Display Calidad Original: $2,360 MXN" ❌
```

### ROOT CAUSE

El scoring en `pricing_sheets.py` (líneas 355-373) está seleccionando el producto INCORRECTO:

```python
# Línea 369-370 (PROBLEMA)
mejor = max(mejores_resultados, key=lambda x: x[0])  # Selecciona por SCORE
```

**Hipótesis:**
- Ambos displays tienen el MISMO SCORE (porque ambos contienen "display" + "iphone" + "13" + "mini")
- Cuando hay empate, `max()` retorna el PRIMERO de la lista (orden de Google Sheets)
- El display de 590 MXN aparece ANTES en el sheet que el de 1,000 MXN
- **Resultado:** Se selecciona el de 590 MXN (INCORRECTO)

---

## 📊 DATOS EN GOOGLE SHEETS (DISPLAYS)

**Sheet:** DISPLAYS (gid=1452574805)  
**Rango:** Rows 431-448  
**Estructura:**
```
| Fila | Col B (Nombre) | Col C (Categoría) | Col D (Precio 1) | Col E (Precio 2) | Col F (Precio 3) |
|------|----------------|-------------------|------------------|------------------|------------------|
| ...  | ...            | ...               | ...              | ...              | ...              |
| ?    | Display Calidad Original [iPhone 13 mini] | Display / Display de Diagnóstico | 590 | ??? | ??? |
| ?    | Display de Diagnóstico [iPhone 13 mini]   | Display / Display de Diagnóstico | 1000 | ??? | ??? |
| ...  | ...            | ...               | ...              | ...              | ...              |
```

**PROBLEMA IDENTIFICADO:**
- La fila con "Calidad Original de 590 MXN" aparece ANTES que "de Diagnóstico de 1,000 MXN"
- Cuando ambas tienen el mismo score, se selecciona la primera
- **Resultado:** Cotización de 2,360 MXN en lugar de 4,000 MXN

---

## 🎯 SÍNTOMAS ADICIONALES

### Síntoma 2: Cotizaciones espontáneas de iPhone 12

**Reporte:** "Algunas conversaciones iniciales están dando cotizaciones de iPhone 12 display sin que el usuario haya preguntado por modelo ni marca"

**Causa probable:** 
- Mismo problema de scoring - selecciona el primer resultado aunque no sea el mejor match
- O hay un default hardcodeado que retorna iPhone 12

---

## ⚙️ ARCHIVOS AFECTADOS

### 1. `agent/pricing_sheets.py` (CRÍTICO)

**Función afectada:** `buscar_google_sheets()` (líneas 307-373)

```python
# LÍNEAS 354-373 (PROBLEMA)
mejor = max(mejores_resultados, key=lambda x: x[0])
score, producto, hoja = mejor[0], mejor[1], mejor[2]
logger.info(f"[SHEETS] Encontrado en {hoja}: '{producto.get('nombre')}' (score: {score})")
return producto
```

**Problema:**
- Cuando hay EMPATE de scores, `max()` retorna el primer resultado
- No hay desempate (tie-breaking logic)
- No hay priorización de productos por precio o nombre

### 2. `agent/pricing_sheets.py` (LÓGICA DE SCORING)

**Función:** `_score_coincidencia()` (líneas ~285-304)

```python
def _score_coincidencia(nombre_producto, tokens_query, marca, modelo):
    # Cuenta coincidencias de tokens
    coincidencias = sum(1 for tok in tokens_query if tok in nombre_lower)
    return coincidencias if coincidencias >= 2 else 0
```

**Problema:**
- Scoring muy simple: solo cuenta tokens coincidentes
- No diferencia entre buenos matches y malos matches
- No considera la CALIDAD del match (ej: "display de diagnóstico" vs "display calidad original")

---

## 📌 INFORMACIÓN GUARDADA (ESTADOS ESPERADOS)

### Multiplicador
- ✅ **Está CORRECTO en ×4**
- NO cambiar
- Google Sheets → precio base × 4 = precio cliente

### Estructura de precios esperada
```
Display Genérico:       ~800 MXN base  → $3,200 MXN cliente (×4)
Display de Diagnóstico: ~1,000 MXN base → $4,000 MXN cliente (×4)  
Display Original:       ~1,200 MXN base → $4,800 MXN cliente (×4)
```

---

## 🔧 SOLUCIONES PROPUESTAS

### Opción A: REORDENAR Google Sheets
**Más simple - Cambio manual en Google Sheets**
1. Mover la fila "Display de Diagnóstico de 1,000 MXN" a ser la PRIMERA
2. Resultado: Cuando hay empate, se selecciona la correcta (primera)
3. **Ventaja:** No tocar código
4. **Desventaja:** Frágil - depende del orden

### Opción B: MEJORAR SCORING (RECOMENDADO)
**Robusto - Cambio en código**

Agregar tie-breaking logic:
```python
# Cuando hay empate, seleccionar por:
# 1. Mejor match (score más alto) - YA HACE
# 2. Si empate → seleccionar el precio MÁS ALTO (preferir original)
# 3. Si aún hay empate → seleccionar por orden alfabético
```

**Cambio en `buscar_google_sheets()` líneas 369-370:**
```python
# ACTUAL (INCORRECTO)
mejor = max(mejores_resultados, key=lambda x: x[0])

# PROPUESTO (CORRECTO)
mejor = max(
    mejores_resultados, 
    key=lambda x: (x[0], -x[1].get('precio_3', x[1].get('p_unitario', 0)))  # Score + precio inverso
)
```

### Opción C: AGREGAR FILTRO DE CALIDAD
**Específico - Priorizar productos con ciertos keywords**
- Si encuentra "Diagnóstico" → priorizar
- Si encuentra "Original" → priorizar menos
- Si encuentra "Genérico" → priorizar menos

---

## 📋 CHECKLIST PARA CLAUDE CODE

- [ ] Revisar Google Sheets (gid=1452574805) filas 431-448
- [ ] Confirmar orden de productos (¿Calidad Original antes que Diagnóstico?)
- [ ] Revisar scoring en `pricing_sheets.py` líneas 354-373
- [ ] Implementar tie-breaking por precio (Opción B recomendada)
- [ ] Agregar logs detallados: mostrar TODOS los matches encontrados (no solo el elegido)
- [ ] Hacer test: "Precio display iPhone 13 mini" → debe retornar ~$4,000 MXN
- [ ] Hacer test: "Precio display iPhone 12" → verificar que NO es espontáneo, si hay match válido
- [ ] Verificar que el multiplicador ×4 no cambie
- [ ] Hacer deploy a Railway

---

## 🧪 TEST CASES PARA VALIDAR FIX

```
TEST 1: iPhone 13 mini display
Entrada: "Precio display iPhone 13 mini"
Esperado: ~$4,000 MXN (Display de Diagnóstico de 1,000 × 4)
Actual: $2,360 MXN (Display Calidad Original de 590 × 4) ❌

TEST 2: iPhone 12 display  
Entrada: "Precio display iPhone 12"
Esperado: ~$4,000 MXN (si existe en sheets)
Verificar: No debe retornar en conversación inicial sin contexto

TEST 3: Display Samsung S21
Entrada: "Precio display Samsung S21"
Esperado: Precio correcto según Google Sheets
Verificar: Selecciona el display CORRECTO (más alto, original)
```

---

## 📌 NOTAS IMPORTANTES

1. **El multiplicador ×4 es CORRECTO** - No cambiar
2. **El problema es la SELECCIÓN del producto** - Scoring débil
3. **Google Sheets tiene datos correctos** - Solo necesita tie-breaking en código
4. **Prioridad:** Implementar Opción B (tie-breaking por precio)
5. **Urgencia:** CRÍTICA - Las cotizaciones están saliendo incorrectas

---

## 📞 CONTACTO

**Usuario:** Christian  
**Email:** goldbunnyshop@gmail.com  
**Teléfono:** (negocio de reparación de celulares, laptops, tablets, drones, etc.)

**Última actualización:** 2026-06-03 14:XX  
**Diagnóstico por:** Claude (en sesión con Christian)
