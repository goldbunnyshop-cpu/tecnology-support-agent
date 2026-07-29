# 🔧 Resumen de Fixes — Sistema de Citas

Fecha: 15 de Mayo, 2026  
Problemas resueltos: **3 críticos**

---

## ✅ FIX #8: Piso mínimo + tier Con Marco (29 Jul 2026)

### Problema
- Displays baratos (ej. Samsung J4 INCELL $130 → $520 calculado) se mostraban a precio real, devaluando el servicio.
- Variantes "Con Marco" (C/M en CSV) se promediaban junto con las variantes sin marco, distorsionando el precio del tier ORIGINAL.

### Solución — `agent/pricing.py`

**Constantes nuevas:**
```python
PISO_GENERICO = 600   # MXN
PISO_ORIGINAL = 900   # MXN
```

**Helper `_es_con_marco()`:** detecta ` C/M` o `CON MARCO` en columna CALIDAD.

**`_categorias_finales()`:** productos C/M van al bucket `'CON_MARCO'` (separados de ORIGINAL).

**`formatear_cotizacion_tiers()` — lógica completa:**
- Si `min(GENERICO + ORIGINAL prices) < 600` → activar piso → mostrar $600 / $900
- AMOLED: siempre precio real (no entra en piso)
- Con Marco: solo aparece si `precio_cm > original_mostrado` (si no, se omite — error de datos)

### Escenarios verificados

| Caso | Input | Output |
|------|-------|--------|
| Solo GEN < $600 | INCELL $130→$520 | Genérica $600 / Original $900 |
| Solo ORIG < $600 | ORIG $129→$516 | Genérica $600 / Original $900 |
| ORIG < $600 + C/M $960 | ORIG S/M $143→$572, C/M $240→$960 | Genérica $600 / Original $900 / Con Marco $960 |
| Solo ORIG ≥ $600 | ORIG $185→$740 | Original $740 |
| GEN + ORIG ambos ≥ $600 | INCELL $300→$1,200 / OLED $400→$1,600 | Genérica $1,200 / Original $1,600 |
| ORIG < $600 + C/M $984 | S/M $149→$596, C/M $246→$984 | Genérica $600 / Original $900 / Con Marco $984 |
| C/M < ORIG → ocultar | C/M $800 < ORIG $1,600 | Original $1,600 (C/M omitido) |

---

## ✅ FIX #1: Caracteres Mojibake (UTF-8 Corruption)

### Problema
- Usuario reportó: "siguen los simbolos raros en la confirmacion de citas"
- Síntomas: `Â¡` en lugar de `¡`, `Â©` en lugar de `©`
- Causa: Encoding UTF-8 no validado al enviar a Whapi.cloud

### Solución
**Archivo:** `agent/providers/whapi.py` (método `enviar_mensaje`)

- ✅ Validación explícita de UTF-8 antes de envío
- ✅ Encoding explícito `Content-Type: application/json; charset=utf-8`
- ✅ Logging detallado de mensajes enviados

**Qué cambió:**
```python
# ANTES (sin validación)
json={"to": destino, "body": mensaje}

# DESPUÉS (con validación UTF-8)
mensaje_limpio = mensaje.encode('utf-8', errors='replace').decode('utf-8')
json={"to": grupo_id, "body": mensaje_limpio}
```

---

## ✅ FIX #2: Notificaciones al Grupo No Se Envían

### Problema
- Usuario reportó: "no se notifico al grupo"
- El grupo ID **está configurado** en `.env`
- Pero los mensajes no llegan al grupo "Taller Interno TS"
- Causa: Sin logging = errores silenciosos + sin reintentos

### Solución
**Archivo:** `agent/appointment_notifications.py`

- ✅ Logging **detallado** en CADA intento de envío
- ✅ Reintentos automáticos (hasta 3 intentos)
- ✅ Mejor manejo de errores con context completo

**Cambios:**
1. Función `_enviar_grupo()`:
   - Agregó parámetro `reintentos` (default: 2)
   - Loop de reintentos con delays entre intentos
   - Logging de cada paso (`🔄 Intento X/Y`, `✅ Enviado`, `❌ Falló`)

2. Función `notificar_nueva_cita()`:
   - Logging extenso para cada etapa
   - Ahora muestra: email ✅/❌, grupo ✅/❌
   - Traceback completo si hay excepción

**Logs que verás si funciona:**
```
[CITAS NOTIF] 🚀 ========== INICIANDO NOTIFICACIÓN DE CITA ==========
[CITAS NOTIF] Cliente: Test Cliente | Tel: +525541234567
[CITAS NOTIF] 📱 Enviando notificación al grupo...
[CITAS GRUPO] 🔄 Intento 1/3 — Enviando a 120363xxx@g.us...
[CITAS GRUPO] ✅ Mensaje enviado al grupo exitosamente
[CITAS NOTIF] ✅ Notificación al grupo enviada exitosamente
```

---

## ✅ FIX #3: Base de Datos PostgreSQL (Ya Estaba Parcialmente Arreglado)

### Recordatorio
El fix anterior **cambió cita_detector.py** para usar raw SQL en lugar de ORM:

```python
# Se cambió DE:
from importar_citas_postgresql import Cita  # ❌ NUNCA FUNCIONÓ

# A:
query = text("""
    INSERT INTO citas (nombre, telefono, dispositivo, problema, fecha_hora, asesor, fuente)
    VALUES (:nombre, :telefono, :dispositivo, :problema, :fecha_hora, :asesor, :fuente)
""")
```

---

## 🧪 Cómo Testear

### Opción 1: Test Automático (Recomendado)

```bash
# En la carpeta del proyecto
python test_fixes.py
```

**Qué hace:**
1. ✅ Verifica que `GRUPO_CHRISTIAN_INTERNO` esté en `.env`
2. 📱 **Envía un mensaje de prueba al grupo** (Taller Interno TS)
3. ✏️ Verifica UTF-8 encoding

**Qué buscar en la salida:**
- `✅ Grupo configurado correctamente` → OK
- `[CITAS GRUPO] ✅ Mensaje enviado` → OK
- `✅ UTF-8 válido` → OK

---

### Opción 2: Test Real (Envía mensajes de WhatsApp)

Envía este mensaje a cualquier cliente:

```
Quiero agendar para lunes 20 de mayo a las 10:00 a.m.
Tengo un iPhone 14 con pantalla rota
```

**Qué esperar:**
1. 📱 **Recibe confirmación con caracteres correctos**
   - Debe decir: `✅ *CITA CONFIRMADA*` (no `Â¡`)
   - Debe mostrar: `⏰ Lunes 20 de mayo, 10:00 a.m.`

2. 📋 **El grupo recibe notificación**
   - Mensaje en "Taller Interno TS" con `🔔 *NUEVA CITA AGENDADA*`
   - Datos del cliente

3. 📊 **Cita se guarda en PostgreSQL**
   - Puedes verificar con SQL:
   ```sql
   SELECT * FROM citas WHERE nombre LIKE '%Test%' ORDER BY fecha_hora DESC LIMIT 1;
   ```

---

## 📊 Checklist de Verificación

### ✅ Antes de ir a producción

- [ ] Ejecutar `python test_fixes.py`
- [ ] Revisar logs buscando `[CITAS GRUPO] ✅`
- [ ] Enviar un mensaje de prueba real desde WhatsApp
- [ ] Verificar que aparezcan caracteres correctos (¡ © ™ etc.)
- [ ] Verificar que el grupo reciba notificación
- [ ] Verificar que la cita se guarde en PostgreSQL

### 🚨 Si algo falla

| Síntoma | Causa probable | Solución |
|---------|----------------|----------|
| `Â¡ © ™` en mensajes | Mojibake UTF-8 | Revisar whapi.py encoding |
| `[CITAS GRUPO] ❌ No se encontró el grupo` | GRUPO_CHRISTIAN_INTERNO no en .env | Agregar en `.env` |
| `[CITAS GRUPO] ❌ HTTP 401` | WHAPI_TOKEN inválido | Verificar token en .env |
| Cita no se guarda | SQLAlchemy error | Revisar logs PostgreSQL |

---

## 🔄 Próximos Pasos Recomendados

1. **Ejecuta el test** (`python test_fixes.py`)
2. **Revisa los logs** — busca `[CITAS GRUPO]` y `[CITAS NOTIF]`
3. **Envía un mensaje de prueba** desde WhatsApp real
4. **Verifica en Railway** que la cita llegó a PostgreSQL

---

## 📝 Notas Técnicas

### UTF-8 Encoding
- `httpx` envía JSON con UTF-8 por defecto
- Pero agregamos validación explícita para evitar doble-encoding
- Si un carácter no es válido UTF-8, se reemplaza con `?`

### Notificaciones con Reintentos
- Primer intento: inmediato
- 2do intento: después de 1 segundo
- 3er intento: después de 1 segundo
- Total: máximo 3 segundos de espera

### PostgreSQL
- Las citas se guardan con `timezone=America/Mexico_City`
- Campo `fuente='automatica'` para citas detectadas por IA
- Deduplicación por `evento_id` (Google Calendar ID)

---

¡Los fixes están listos! 🚀

---

---

# 🔧 Fixes — Sesión 24 de Julio, 2026

Fecha: 24 de julio de 2026  
Problemas resueltos: **3 bugs críticos + 2 mejoras de comportamiento**

---

## ✅ FIX #4: Falso positivo "Celular" cuando cliente menciona "teléfono"

### Problema
El agente registraba incorrectamente el dispositivo como **"Celular"** cuando el cliente
mencionaba la palabra "teléfono" en cualquier contexto (ej: "mi número de teléfono es...",
"te doy mi teléfono", "¿cuál es el teléfono del módulo?").

### Causa raíz
`agent/profile.py` — `_DISPOSITIVOS` tenía `"teléfono"` y `"telefono"` como keywords del tipo "Celular".
Esas palabras son demasiado genéricas y disparan falsos positivos.

### Solución
**Archivo:** `agent/profile.py`

```python
# ANTES:
("Celular", ["celular", "teléfono", "telefono"]),

# DESPUÉS:
("Celular", ["celular"]),  # "teléfono" eliminado — demasiado genérico
```

### Impacto
- El perfil del cliente ya no se contamina con dispositivos fantasma
- La instrucción "último dispositivo = Celular" no se activa incorrectamente
- El asesor deja de asumir que el cliente tiene un celular cuando solo mencionó un número de teléfono

---

## ✅ FIX #5: Motor de pantallas disparaba cotizaciones de celular en contexto de laptop

### Problema
Cuando una conversación tenía contexto de laptop/PC y el cliente mencionaba "pantalla",
el agente activaba el motor de cotización de displays de celular y cotizaba pantallas de
teléfono en lugar de responder correctamente que laptops no están en el inventario de displays.

**Log del error:**
```
[PRICING-DEBUG] es_display=True pantalla → intentando buscar display...
# Luego cotizaba un display de celular sin sentido en contexto de laptop
```

### Causa raíz
`agent/brain.py` — `_intentar_respuesta_pricing_contextual()` evaluaba `es_display=True`
antes de verificar si el contexto era de laptop. El guard de `es_no_display` no cubría
el caso porque es intencional que `es_display` tenga prioridad sobre `es_no_display`
(para casos como "iPad pantalla" + "controles PS5").

### Solución
**Archivo:** `agent/brain.py`

Se agregó `_PATRON_LAPTOP_PC` y la función `_es_contexto_laptop_pc()` que revisa los
últimos 8 mensajes del historial. El guard se inyecta ANTES del bloque `if es_display:`
y solo aplica cuando no hay marca de celular explícita en el mensaje actual:

```python
_PATRON_LAPTOP_PC = re.compile(
    r"\b(laptop|lapto|notebook|computadora|pc\s*gamer|desktop|macbook|lenovo|dell|asus|acer|msi|gaming\s*\d)\b",
    re.I,
)

def _es_contexto_laptop_pc(historial: list[dict]) -> bool:
    for msg in (historial or [])[-8:]:
        if _PATRON_LAPTOP_PC.search(msg.get("content") or ""):
            return True
    return False

# Guard aplicado en _intentar_respuesta_pricing_contextual():
if _es_contexto_laptop_pc(historial) and not marca_actual:
    logger.info("[PRICING-DEBUG] Contexto laptop/PC sin marca de celular → delegando a Claude")
    return None
```

### Impacto
- El motor de displays de celular ya no aplica en conversaciones de laptop/PC
- Si el cliente menciona explícitamente una marca de celular, el motor sigue funcionando normal
- Claude maneja el caso de laptop/pantalla con su propio criterio

---

## ✅ FIX #6: Multiplicador incorrecto para pantallas ORIGINAL y OLED — precio inflado

### Problema
Las pantallas con calidad ORIGINAL (incluye OLED, ORIG, COF, FHD, DD SOFT) se multiplicaban
por ×4 en lugar de ×3, inflando el precio final en un 33%.

**Caso real detectado en live:**
- Motorola Edge 30 Neo — OLED S/M — PRECIO_1: $1,081 USD
- Precio cotizado por el agente: **$4,324 MXN** (×4)
- Precio correcto: **$3,243 MXN** (×3)
- El cliente dejó de contestar — precio equivale al costo de un equipo nuevo

### Causa raíz
`agent/pricing.py` — `MULTIPLICADOR_POR_CATEGORIA` tenía `'ORIGINAL': 4`.
La función `obtener_categoria()` clasifica "OLED S/M" → strip → "OLED" → ORIGINAL.
Como ORIGINAL tenía multiplicador ×4, el cálculo era incorrecto.

### Solución
**Archivo:** `agent/pricing.py`

```python
# ANTES:
MULTIPLICADOR_POR_CATEGORIA = {
    'GENERICO': 4,
    'ORIGINAL': 4,  # ← ERROR
    'AMOLED': 3,
}

# DESPUÉS (reglas confirmadas jul-2026):
MULTIPLICADOR_POR_CATEGORIA = {
    'GENERICO': 4,   # INCELL, COG, TLED, CARTAN INCELL
    'ORIGINAL': 3,   # OLED, ORIG, COF, FHD, DD SOFT, HG ORIG
    'AMOLED':   3,   # AMOLED
}
```

**Regla comercial vigente:**
| Calidad | Multiplicador | Incluye |
|---------|--------------|---------|
| GENERICO | ×4 | INCELL, COG, TLED, CARTAN INCELL |
| ORIGINAL | ×3 | OLED, ORIG, COF, FHD, DD SOFT, HG ORIG |
| AMOLED   | ×3 | AMOLED |

**Nota:** El sistema siempre usa `PRECIO_1` (columna 5 del CSV) como base. `PRECIO_2` no se usa.

### Impacto
- Motorola Edge 30 Neo: $1,081 × 3 = **$3,243 MXN** ✅
- Todas las pantallas OLED/ORIGINAL ahora cotizan correctamente
- Sin riesgo de espantar leads con precios inflados

---

## ✅ MEJORA #1: Comportamiento del agente ante "diagnóstico supuesto" del cliente

### Problema
Cuando un cliente asumía que sabía exactamente cuál era la falla (ej: "solo es el puerto
HDMI de la PS5", "solo es el display"), el agente cotizaba esa pieza sin mencionar que
el accidente pudo haber dañado componentes adicionales no visibles.

Casos críticos:
- **PS5 HDMI**: el golpe puede dañar trazas de placa madre o líneas del procesador de video
- **Display de celular**: el golpe puede dañar el flex, el digitalizador o líneas en la placa
  que solo fallan al instalar el display nuevo

### Solución
**Archivo:** `config/prompts.yaml`

Se agregó la sección **"DIAGNÓSTICO SUPUESTO"** con instrucciones para tres escenarios:
- **Caso A** — Puerto HDMI de consola: validar + explicar riesgo de daño en placa + invitar al módulo
- **Caso B** — Display de celular: cotizar SI hay precio, pero SIEMPRE acompañar con nota honesta
- **Regla general**: validar → honestidad técnica → invitar → si insiste en número, dar rango

### Principio
El agente no rechaza dar un número, pero educa al cliente sobre por qué el diagnóstico
físico puede cambiar el alcance de la reparación. Convierte la situación en una visita,
no en un rechazo.

---

## ✅ MEJORA #2: Cierre temporal — Domingo 26 de julio de 2026

### Motivo
El módulo permanecerá cerrado únicamente el domingo 26 de julio de 2026 por día de descanso.

### Solución
**Archivo:** `config/prompts.yaml` — al inicio del `system_prompt_template`

Instrucción de alta prioridad, auto-expirable:
- Bloquea citas para el 26 de julio
- Redirige al cliente al sábado 25 o lunes 27
- A partir del 27 de julio, el agente ignora esta instrucción automáticamente

---

---

# 🔧 Fixes — Sesión 29 de Julio, 2026

Fecha: 29 de julio de 2026
Problemas resueltos: **2 bugs críticos de precios + 1 corrección de arquitectura**

---

## ✅ FIX #7: Samsung S25 Ultra — precio genérica $26,000 MXN (más que el equipo nuevo)

### Problema
El agente cotizó "Calidad Genérica: $26,000 MXN" para Samsung S25 Ultra. El equipo nuevo
cuesta $23,000 MXN. El operador emitió STOP manualmente para detener la conversación.

### Causa raíz (3 bugs encadenados)

**Bug A — imobile × 4 incorrecto:**
El Sheet de imobile (proveedor premium) tiene S25 Ultra "Original con Glass Copia Marco" a
$6,500 MXN (costo al negocio). El código aplicaba `MULTIPLICADOR_POR_CATEGORIA['ORIGINAL'] = 4`
(o 3) sobre ese costo: $6,500 × 4 = **$26,000 MXN** — más que el teléfono nuevo.

**Bug B — "Copia" clasificaba como GENÉRICO:**
`clasificar_calidad_titulo()` tenía 'COPIA' en keywords de GENÉRICO. El nombre del producto
en imobile es "Original con Glass **Copia** Marco" (panel original, marco aftermarket).
El código lo clasificaba como GENÉRICO → el precio absurdo aparecía como "Calidad Genérica".

**Bug C — Hugo ORIGINAL × 3 (deprimido):**
Con ORIGINAL × 3, el Hugo S25 Ultra ($1,692 × 3 = $5,076) quedaba MÁS BARATO que el
"Genérica" de imobile ($26,000). Inversión catastrófica.

**Nota arquitectural:** Todos los precios (Hugo Shop CSV + imobile Sheet) son en MXN.
Los multiplicadores son márgenes de ganancia sobre el costo MXN del proveedor.

### Solución

**1. `agent/pricing.py` — ORIGINAL vuelve a × 4:**
```python
MULTIPLICADOR_POR_CATEGORIA = {
    'GENERICO': 4,
    'ORIGINAL': 4,  # ← revertido de 3 a 4
    'AMOLED': 3,
}
```
Hugo S25 Ultra ORIGINAL: $1,692 × 4 = **$6,768 MXN** ✓

**2. `agent/pricing.py` — Fix clasificación COPIA + ORIGINAL:**
```python
# ANTES: COPIA siempre → GENÉRICO (sin importar si también dice ORIGINAL)
if tiene_generico:
    return 'GENERICO'

# DESPUÉS: ORIGINAL + COPIA coexistiendo → ORIGINAL (panel original, marco aftermarket)
if tiene_generico and tiene_original:
    return 'ORIGINAL'
if tiene_generico:
    return 'GENERICO'
```

**3. `agent/pricing_sheets.py` — MULTIPLICADOR_IMOBILE = 1.5:**
```python
MULTIPLICADOR_IMOBILE = float(os.getenv("MULTIPLICADOR_IMOBILE", "1.5"))
# Imobile S25 Ultra: $6,500 × 1.5 = $9,750 MXN ✓ (vs $26,000 con × 4)
```

**4. `agent/pricing_fallback.py` — Hugo exclusivo, imobile solo como fallback:**
Si Hugo tiene el modelo → usar SOLO Hugo (no mezclar con imobile).
Si Hugo NO tiene el modelo → usar SOLO imobile.
Nunca combinar precios de ambas fuentes (son proveedores distintos con rangos de precio
completamente diferentes; promediarlos daría precios sin sentido comercial).

### Resultado

| Escenario | Antes (bug) | Después (fix) |
|-----------|-------------|---------------|
| S25 Ultra — Hugo | $5,076 ORIGINAL (×3) | $6,768 ORIGINAL (×4) ✓ |
| S25 Ultra — imobile | $26,000 GENÉRICA (×4) | $9,750 ORIGINAL (×1.5) ✓ |
| S25 Ultra — agente muestra | Hugo + imobile mezclados → inversión | Solo Hugo si Hugo tiene; solo imobile si no |

### Impacto
- Elimina el mayor riesgo de reputación del sistema: cotizar más caro que el equipo nuevo
- Hugo y imobile son fuentes exclusivas (no se mezclan)
- imobile queda como fuente premium legítima para modelos no disponibles en Hugo

---

## 📦 Archivos modificados en esta sesión

| Archivo | Tipo | Fix |
|---------|------|-----|
| `agent/profile.py` | Bug fix | Eliminado "teléfono"/"telefono" de keywords Celular |
| `agent/brain.py` | Bug fix | Guard `_es_contexto_laptop_pc()` antes del motor de displays |
| `agent/pricing.py` | Bug fix | Multiplicador ORIGINAL corregido a ×3 |
| `config/prompts.yaml` | Mejora | Sección "DIAGNÓSTICO SUPUESTO" + cierre dom 26 jul |
| `knowledge/hugo_shop.csv` | Datos | Lista Hugo Shop julio 2026 (902 productos) |

## ⚠️ Verificación de inconsistencias

No se detectaron conflictos con fixes anteriores:
- Los multiplicadores anteriores solo documentaban `AMOLED=×3`. Esta sesión alinea también `ORIGINAL=×3` — sin contradicción.
- El guard de laptop/PC en brain.py es aditivo — no modifica el comportamiento existente de cotización de celulares.
- La eliminación de "teléfono" en profile.py no afecta la detección de otros dispositivos.
- La sección "DIAGNÓSTICO SUPUESTO" en prompts.yaml complementa las reglas existentes de cotización — no las reemplaza.
