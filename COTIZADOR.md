# Cotizador de refacciones — Arquitectura, fixes y guía

> Documento vivo del **motor de precios** del agente de WhatsApp.
> Última actualización: **2026-06-05**.
> Sirve para entender cómo cotiza, qué se reparó y cómo extenderlo sin romperlo.

---

## 1. Qué hace el cotizador

Cuando un cliente pregunta el precio de una refacción (display, batería, tapa…), el agente
responde **sin llamar a Claude** (lo intercepta `brain.py` antes de la IA) usando el motor de
precios. El objetivo de negocio:

- Para **displays**: ofrecer SIEMPRE las calidades disponibles, idealmente **dos precios**:
  - **Calidad Generica** (la barata: paneles Incell / Copia)
  - **Calidad Original** (la cara: paneles OLED / Original)
  - y **AMOLED** como tercera si existe.
- Si una fuente solo trae una calidad, se **complementa** con la otra fuente.
- Si el cliente **no dice el modelo**, se le **pide marca + modelo** (NUNCA inventar un precio).
- Si una línea cubre **varios modelos compatibles** (`Edge 50 / Moto G85`,
  `Honor X6B / X6B Plus / Play 50M`), solo se devuelve el modelo que pidió el cliente.

---

## 2. Flujo y archivos

```
Cliente (WhatsApp)
   │  "¿cuánto cuesta la pantalla de un samsung a54?"
   ▼
agent/brain.py
   _intentar_respuesta_pricing_contextual()  → detecta consulta de precio + extrae marca/modelo
   _resolver_pricing_desde_texto()           → llama al pipeline
   ▼
agent/pricing_fallback.py
   cotizar_con_fallback(marca, modelo, refaccion)
      ├─ refaccion == "display"  → _cotizar_display_fusionado()   (FUSIÓN Hugo + Sheets)
      └─ batería/tapa/otros      → Google Sheets → fixoem/Sheet genérico
   ▼
   Resultado: texto "INFORMACION PARA EL CLIENTE..." → brain lo limpia y lo envía
```

| Archivo | Rol |
|---------|-----|
| `agent/pricing.py` | **Hugo Shop** (CSV local) + helpers compartidos (clasificador, formateador de calidades, multiplicadores). |
| `agent/pricing_sheets.py` | **Google Sheets** (displays + baterías Android/iPhone). |
| `agent/pricing_fallback.py` | **Orquestador**: fusiona fuentes; fallback a **fixoem.com** + Sheet genérico. |
| `agent/brain.py` | Detecta la consulta de precio, extrae marca/modelo y llama al pipeline. |

---

## 3. Fuentes de datos y su estructura (⚠️ no obvio)

### 3.1 Hugo Shop — `knowledge/hugo_shop.csv`
Columnas: `CODIGO, DESCRIPCION, CALIDAD, COLOR, PRECIO_1, PRECIO_2`.
- La **calidad está en su propia columna** (`ORIG`, `OLED`, `INCELL`, `AMOLED`, `HG FHD INCELL COG`…).
- Filas-header de marca (`SAMSUNG,,,,,`) separan secciones y anclan la marca de cada producto.
- Precio usado = **`PRECIO_1`** (está en USD; se multiplica para llegar a MXN).
- Una descripción puede cubrir varios modelos: `H40 LITE/E40/V40`, `V60/E60`.

### 3.2 Google Sheets — hoja **DISPLAYS** (gid `1452574805`)
> **El bug raíz vivía aquí.** Las 3 columnas de precio son
> `Precio Unitario | P. Mayoreo 1 | P. Mayoreo 2` del **MISMO** display (distinto volumen),
> **NO** son genérico/original/amoled.

- La **calidad se lee del NOMBRE** del producto:
  - `Incell`, `Copia`, `IPS`, `LCD`, `COG` → **GENERICO**
  - `Oled`, `Original` → **ORIGINAL**
  - `Amoled` → **AMOLED**
- Un mismo modelo aparece en **varias filas** con distinta calidad:
  - `iPhone 13 Pro Max Incell FHD` → $690 (genérico)
  - `iPhone 13 Pro Max Oled Hard` → $1,120 (original)
- Precio base usado = **`Precio Unitario`** (1ª columna, el precio de 1 pieza).
- Líneas multi-modelo: `iPhone 12 / 12 Pro`, `Honor X6B / X6B Plus / Play 50M`.

### 3.3 Google Sheets — **BATERÍAS ANDROID / iPHONE**
Precio único (sin tiers de calidad). Se muestra el `Precio Unitario`.

### 3.4 fixoem.com (último recurso)
Búsqueda Shopify; precios en MXN × 3. Solo se usa si Hugo y Sheets no tienen la pieza.

---

## 4. Reglas de negocio (confirmadas por el dueño, 2026-06-05)

### Multiplicadores (`MULTIPLICADOR_POR_CATEGORIA` en `pricing.py`)
| Calidad | Multiplicador | Aplica a |
|---------|--------------|----------|
| GENERICO | **×4** | Hugo (sobre PRECIO_1 USD) y Sheets (sobre Precio Unitario) |
| ORIGINAL | **×4** | idem |
| AMOLED | **×3** | idem |
| Tapas iPhone | ×8 | `pricing_fallback._multiplicador_para` |
| Tapas otras marcas | ×5 | idem |

> Sin tope de precio (`PRICING_UMBRAL_CONSULTAR = 999999999`): se muestran todos los precios.

### Clasificación de calidad
- **Hugo** usa `obtener_categoria()` (lee la columna CALIDAD). **No tocar** sin re-evaluar
  (riesgo de regresión en evals).
- **Sheets / fixoem** usan `clasificar_calidad_titulo()` (lee el NOMBRE). Regla clave:
  **INCELL/COPIA dominan sobre FHD** — un `Incell FHD` es **genérico** (FHD es resolución,
  no calidad premium).

### Variantes (regla estricta)
Si el modelo es ambiguo (`iPhone 13` → 13 / 13 Pro / 13 Pro Max; `Edge 50` → 50 / 50 Fusion /
50 Neo), **NO se cotiza**: se pregunta la variante exacta primero. Aplica tanto en Hugo como
en Sheets.

### Fusión de fuentes (`_fusionar_categorias`)
**Hugo manda.** Google Sheets solo **aporta las calidades que falten**. Ejemplo: si Hugo solo
trae Original y Sheets tiene Genérica, el resultado muestra ambas, con la Original de Hugo intacta.

---

## 5. Qué se reparó (2026-06-05)

### Bug 1 — Una sola calidad y etiqueta equivocada
`pricing_sheets.formatear_cotizacion_sheets` tomaba `max(p1,p2,p3)` de **una** fila y lo
etiquetaba siempre como "Calidad Original". Como las 3 columnas son volúmenes del mismo
producto, tiraba la calidad genérica y la etiqueta podía estar mal.
**Fix:** nueva ruta `recolectar_categorias_display_sheets()` agrupa TODAS las filas del modelo
por calidad (del nombre) y `formatear_cotizacion_tiers()` muestra una línea por calidad.

### Bug 2 — Precios al azar cuando el cliente NO daba modelo
En el log de Railway (3 jun), `"¿cuánto cuesta la pantalla?"` (sin modelo) devolvía:
- `iPhone 12 al azar → $2,320`
- `Hisense E50 al azar → $760`

Porque la búsqueda en Sheets aceptaba cualquier producto con ≥2 palabras genéricas en común
(`display`, `de`…).
**Fix:** la ruta de displays exige `_titulo_coincide_modelo()` — si el "modelo" es basura
(sin coincidencia real), no devuelve nada → se le pide marca + modelo al cliente.

### Bug 3 — Calidad de Sheets mal clasificada
`Incell FHD` (genérico) y `Copia Alta` (genérico) caían en ORIGINAL.
**Fix:** `clasificar_calidad_titulo()` con prioridad INCELL/COPIA > FHD.

### Mejora — Mensaje cuando falta el modelo
`_mensaje_no_disponible()` (rama sin marca/modelo) ahora es cálido y empuja al cliente a dar
marca + modelo, en vez del texto seco anterior.

### Funciones nuevas / refactor
- `pricing.py`: `clasificar_calidad_titulo`, `_categorias_finales`, `formatear_cotizacion_tiers`,
  `_resolver_match_hugo` (núcleo de matching), `recolectar_categorias_hugo` (versión estructurada).
- `pricing_sheets.py`: `_categorias_desde_productos_sheet`, `_recolectar_iphone_sheets`,
  `recolectar_categorias_display_sheets`. Se eliminó `_cotizar_display_iphone` (reemplazada).
- `pricing_fallback.py`: `_fusionar_categorias`, `_cotizar_display_fusionado`; `cotizar_con_fallback`
  reescrita (display = fusión; resto = Sheets → fixoem).

---

## 6. Cómo probar localmente (sin WhatsApp ni créditos de API)

El motor de precios **no usa la API de Claude**, así que se prueba directo:

```bash
python -c "
import asyncio, logging; logging.disable(logging.CRITICAL)
from agent.pricing_fallback import cotizar_con_fallback
async def main():
    print(await cotizar_con_fallback('samsung','a54','display'))      # dos calidades
    print(await cotizar_con_fallback('iphone','13 pro max','display'))# dos calidades
    print(await cotizar_con_fallback('iphone','13','display'))        # pregunta variante
    print(await cotizar_con_fallback('', 'cuánto cuesta la pantalla','display'))  # pide modelo
asyncio.run(main())
"
```

### Evals
```bash
python tests/eval/run_eval.py            # todo (REQUIERE créditos de API de Anthropic)
python tests/eval/run_eval.py --solo m01-precio-display,m07-display-samsung
```
- Los casos de **motor de pricing de display** (`m01`, `m07`) se evalúan con reglas deterministas
  y pasan **sin créditos**.
- Los casos conversacionales necesitan créditos (llaman a Claude + juez Opus). Sin créditos
  dan 0 — eso NO es regresión de código, es falta de saldo.

---

## 7. Limitaciones conocidas / deuda técnica

1. **`brain.py` extrae "modelos" basura.** Mensajes como "cuánto cuesta la reparación de"
   se pasan como `modelo`. El motor ahora lo neutraliza (pide modelo), pero idealmente
   `brain._modelo_plausible()` debería filtrar antes de llamar al pipeline.
2. **Promedio dentro de una calidad mezcla rangos amplios.** Si Hugo tiene varias filas
   ORIGINAL (boutique cara + OLED normal), se promedian en un solo precio. Si se quiere el
   más bajo/alto en vez del promedio, cambiar en `formatear_cotizacion_tiers` / `_categorias_finales`.
3. **Créditos de Anthropic.** El agente en vivo comparte la API key del motor; si se agotan
   créditos, las respuestas **conversacionales** fallan (las cotizaciones de display siguen
   funcionando porque no usan Claude). Revisar saldo en console.anthropic.com.
4. **Caché de Sheets:** TTL 1 h (`PRICING_SHEETS_CACHE_TTL`). Un cambio de precio en el Sheet
   tarda hasta 1 h en reflejarse.

---

## 8. Cómo extender (recetas)

### Agregar una nueva calidad (ej. "TFT")
1. `pricing.py` → `MULTIPLICADOR_POR_CATEGORIA` (añadir multiplicador) y `ETIQUETAS_CATEGORIA`
   (etiqueta para el cliente).
2. `clasificar_calidad_titulo()` (Sheets) y `obtener_categoria()` (Hugo) → mapear la palabra clave.
3. `formatear_cotizacion_tiers()` → añadir la categoría al orden de impresión.

### Agregar un nuevo proveedor de precios
1. Crear `agent/pricing_<fuente>.py` con un colector que devuelva
   `{"tipo": "ok", "marca", "modelo", "categorias": {CAT: [precios_mxn]}}`.
2. Integrarlo en `pricing_fallback._cotizar_display_fusionado` (fusionar) o como nuevo paso
   del fallback.

### Cambiar de "pedir variante" a "cotizar la más vendida"
Modificar las ramas `tipo == "variante"` en `_resolver_match_hugo` / `_recolectar_iphone_sheets`.

---

## 9. Despliegue

Push a `main` → **Railway redeploya automáticamente**. Subir solo los archivos del cotizador
para evitar ruido de fin-de-línea (CRLF):

```powershell
git add agent/pricing.py agent/pricing_sheets.py agent/pricing_fallback.py tests/test_pricing_sheets.py
git commit -m "feat: cotizador dos calidades + rechaza consultas sin modelo"
git push origin main
```
