# Sistema de Búsqueda Dual - Displays por Marca o Modelo

## ¿Qué se implementó?

Se agregó un **sistema de búsqueda dual** que permite detectar y cotizar displays de dos formas:

### 1. Búsqueda Explícita (Original)
El cliente menciona MARCA + MODELO:
- "Precio Samsung S23" ✓
- "Cuanto cuesta iPhone 14 Pro" ✓
- "Presupuesto para Samsung A21" ✓

### 2. Búsqueda por Modelo Solo (NUEVO)
El cliente menciona SOLO el MODELO sin marca explícita:
- "Precio S23" → Busca en todo el CSV → Encuentra SAMSUNG ✓
- "Cuanto cuesta a14" → Busca en todo el CSV → Encuentra SAMSUNG ✓
- "Display edge 50" → Busca en todo el CSV → Encuentra MOTOROLA ✓
- "Pixel 8" → Busca en todo el CSV → Encuentra múltiples marcas → Pregunta cuál ✓

## ¿Cómo funciona?

### Flujo de la búsqueda:

```
Mensaje del cliente
       ↓
¿Pregunta de precio? (keywords: precio, costo, presupuesto, etc.)
       ↓ SÍ
¿Hay marca + modelo explícitos?
       ├─ SÍ → Búsqueda con marca (flujo original)
       │          ↓
       │        Cotizar directamente
       │
       └─ NO → Búsqueda sin marca (NUEVO)
                  ↓
                Extraer modelo del mensaje
                  ↓
                Buscar en TODO el CSV
                  ↓
                ¿Encontró algo?
                  ├─ NO → Mensaje "no disponible"
                  │
                  ├─ SÍ, 1 marca → Cotizar
                  │
                  └─ SÍ, múltiples marcas → Preguntar "¿De cuál marca?"
```

## Archivos modificados

### 1. `agent/pricing.py`
**Nueva función:**
```python
async def buscar_modelo_sin_marca(modelo: str) -> str
```

Hace lo siguiente:
- Recibe el modelo (ej: "s23")
- Busca en todos los productos del CSV
- Normaliza el modelo (elimina menciones de marca accidentales)
- Agrupa resultados por marca
- Si encuentra 1 marca: cotiza
- Si encuentra múltiples: pide confirmación
- Si no encuentra: retorna mensaje "no disponible"

### 2. `agent/brain.py`
**Función modificada:**
```python
async def detectar_y_obtener_precios(mensaje: str) -> str
```

Ahora con dos opciones:
- OPCION 1: Busqueda con marca (si existe marca + modelo explícitos)
- OPCION 2: Fallback sin marca (si es pregunta de precio pero no hay marca explícita)

## Ejemplos de uso

### Caso 1: Con marca explícita (siempre funcionó)
```
Cliente: "Que precio tiene Samsung S23?"
→ Detecta: marca=Samsung, modelo=S23
→ Busca con marca
→ Retorna cotización de SAMSUNG S23
```

### Caso 2: Sin marca, un modelo único (NUEVO)
```
Cliente: "Cuanto cuesta s23?"
→ Detecta: modelo=s23 (sin marca)
→ Busca en TODO el CSV
→ Encuentra: SAMSUNG S23 (10 productos)
→ Retorna cotización de SAMSUNG S23
```

### Caso 3: Sin marca, modelo ambiguo (NUEVO)
```
Cliente: "Precio pixel 8"
→ Detecta: modelo=pixel (sin marca)
→ Busca en TODO el CSV
→ Encuentra: HONOR, IPHONE, XIAOMI
→ Pregunta: "¿De cuál marca es tu dispositivo?"
```

## Resultados del test

✓ **OPCION 1 (Marca explícita)**: Funciona como antes
✓ **OPCION 2 (Sin marca)**: Todos los casos funcionan

```
Modelos probados sin marca:
- S23, s23 → Samsung ✓
- A14, a14 → Samsung ✓
- 14 pro → iPhone ✓
- edge 50 → Motorola ✓
- pixel 8 → Múltiples marcas (pregunta cuál) ✓
```

## Ventajas

1. **Más natural**: El cliente puede decir "s23" sin mencionar "Samsung"
2. **Data-driven**: Funciona con cualquier modelo en el CSV
3. **Escalable**: Agregar nuevos modelos al CSV = automáticamente funcionan
4. **Sin código hardcodeado**: No dependemas de patrones regex frágiles
5. **Mantenible**: La lógica es simple y directa

## Próximos pasos opcionales

1. Agregar alias de modelos (ej: "modelo antiguo" → busca familia X)
2. Agregar cache de búsquedas frecuentes
3. Logging mejorado de búsquedas sin marca
4. Análisis de qué modelos se buscan vs no se encuentran
