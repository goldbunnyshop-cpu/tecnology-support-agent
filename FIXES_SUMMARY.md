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

---

---

# 🔧 Fixes — Sesión 1 de Agosto, 2026

Fecha: 1–3 de agosto de 2026
Problemas resueltos: **3 bugs + 3 mejoras de Vision**

---

## ✅ FIX #9: Vision B+C+A — Análisis de imágenes con modelo identificador (1 ago 2026)

### Problema
El agente daba respuestas genéricas al recibir fotos/videos de equipos dañados.
Un cliente envió la parte trasera de un Moto Edge 20 Lite → el agente respondió con texto
genérico sin intentar identificar el modelo. Christian tuvo que hacer la búsqueda manual
en Google para identificar el equipo y cotizar.

**Log del problema:**
```
[VISION] analizar_imagen_bytes invocado — media_url vacío, probando media_id
[VISION] Respuesta al cliente: "Recibí tu foto. ¿Puedes decirme qué modelo es y qué falla?"
# Demasiado genérico — no aprovechó la imagen en absoluto
```

### Causa raíz
- Prompt de visión era básico (solo detectaba daño, no intentaba identificar marca/modelo)
- El historial guardaba `"[imagen recibida]"` sin contexto — el siguiente mensaje de Claude no sabía qué imagen había llegado
- Christian no recibía la imagen reenviada, solo texto con el análisis

### Solución (3 componentes independientes)

**A — Reenvío de imagen a Christian (`agent/notifications.py` + `agent/providers/whapi.py`):**
```python
# notificar_christian_vision() ahora acepta imagen_bytes y mime_type
# Intento 1: reenvía imagen original con caption de análisis
ok = await proveedor.enviar_imagen_bytes(CHRISTIAN_NUMERO, imagen_bytes, imagen_mime, caption)
# Fallback: solo texto si falla el reenvío
await proveedor.enviar_mensaje(CHRISTIAN_NUMERO, caption)
```
`enviar_imagen_bytes()` añadido a `ProveedorWhapi` (POST /messages/image con base64).

**B — Prompt estructurado (`agent/vision.py` — `PROMPT_VISION`):**
Nuevo prompt extrae JSON estructurado con campos: `tipo_dispositivo`, `marca`, `modelo_probable`,
`dano_visible`, `puerto_afectado`, `severidad`, `nota_tecnica`, `pregunta_cliente`.
La `pregunta_cliente` es específica para confirmar el modelo (ej: "¿Puedes ver el modelo en Ajustes → Acerca del teléfono?").

**C — Contexto en historial (`agent/vision.py` — `construir_contexto_historial()`):**
```python
# ANTES: guardaba "[imagen recibida]" — cero contexto para Claude
# DESPUÉS: guarda "[imagen: celular Motorola Moto G serie media - pantalla rota]"
```
Claude Sonnet (el cerebro) ya sabe en el siguiente mensaje qué dispositivo se recibió.

**Caption enviado a Christian:**
```
📸 VISIÓN — Cliente: Roberto (5216121557941)
📱 Motorola — Moto Edge 20 Lite
🔧 Daño: pantalla rota
📋 Nota técnica: display roto con digitalizador separado
```

### Costo tokens
- Haiku Vision (4× más barato que Sonnet) + solo en mensajes de imagen
- El reenvío de imagen a Christian no genera llamada adicional a Claude
- Ahorro neto vs intervención manual de Christian: ~15 min/imagen × $0 adicional

---

## ✅ FIX #10: Seguimiento disparado antes de que pase la cita (3 ago 2026)

### Problema
Un cliente agendaba cita para el sábado → el siguiente día (miércoles) el scheduler
enviaba "Hola Roberto, ¿pudiste venir a dejarnos el iPhone el sábado?" cuando el sábado
aún no había llegado.

**Log del error (caso real Roberto Álvarez):**
```
# Cita creada: miércoles 30-jul-2026 01:22 → para sábado 1-ago-2026 11:30
Seg 1/4 [Valentina] [urgente] → 5216121557941: Hola Roberto, ¿pudiste venir a dejarnos el iPhone el sábado?
# → Enviado 30-jul a las 16:20 (sábado no había pasado todavía)
```

El cliente respondió: "No esa cita está bien, aun no pasa."
El agente pidió disculpas pero repitió el mismo error al día siguiente.

### Causa raíz
`ejecutar_seguimientos()` en `followup.py` selecciona cualquier lead donde el intervalo
post-último-mensaje ya se cumplió (primer seguimiento: 2h). No consultaba si el lead
tenía una cita futura pendiente. Claude Haiku generaba "Escenario B — ¿pudiste venir?"
leyendo "sábado" en el historial sin saber si esa fecha ya había pasado.

### Solución

**`agent/leads.py` — nueva función `tiene_cita_pendiente()`:**
```python
async def tiene_cita_pendiente(telefono: str) -> datetime | None:
    """Retorna la fecha_hora de la próxima cita FUTURA del cliente (con margen -4h), o None."""
    desde = datetime.utcnow() - timedelta(hours=4)  # ±4h post-visita antes de reanudar seguimientos
    async with async_session() as session:
        result = await session.execute(text("""
            SELECT fecha_hora FROM citas
            WHERE telefono = :tel AND fecha_hora > :desde
            ORDER BY fecha_hora ASC LIMIT 1
        """), {"tel": telefono, "desde": desde})
        row = result.first()
        return row[0] if row and row[0] else None
```

**`agent/followup.py` — guard en `ejecutar_seguimientos()`:**
```python
# No interrumpir al cliente si tiene una cita futura confirmada
cita_futura = await tiene_cita_pendiente(lead.telefono)
if cita_futura:
    logger.info(
        f"[SEGUIMIENTO] Omitido — {lead.telefono} tiene cita el "
        f"{cita_futura.strftime('%d/%m %H:%M')} (aún no ha pasado)"
    )
    continue
```

### Comportamiento después del fix

| Momento | Antes (bug) | Después (fix) |
|---------|-------------|---------------|
| Miércoles 30-jul, 16:20 | ❌ "¿pudiste venir el sábado?" | ✅ Omitido — cita pendiente 01/08 11:30 |
| Sábado 1-ago, después 15:30 (+4h) | — | ✅ Seguimiento normal reanudado |
| Cliente sin cita registrada | ✅ Seguimiento normal | ✅ Seguimiento normal (sin cambio) |

---

## ✅ FIX #11: INSERT duplicado cuando cliente confirma cita existente (3 ago 2026)

### Problema
Cuando el agente enviaba el seguimiento prematuro ("¿pudiste venir?") y el cliente
respondía "No esa cita está bien, aun no pasa", el agente generaba un tag `[[AGENDAR:...]]`
para "re-confirmar" la cita existente → `guardar_cita_automatica()` hacía un segundo
INSERT en PostgreSQL.

**Log del error:**
```
# Primer INSERT (cita original, correcto)
[CITA_DETECTOR] ✅ Cita guardada en PostgreSQL: Roberto — 01/08 11:30

# ...15 horas después, Roberto responde al seguimiento incorrecto...
[CITA_DETECTOR] ✅ Cita guardada en PostgreSQL: Roberto — 01/08 11:30  # ← DUPLICADO
```

### Causa raíz
`guardar_cita_automatica()` en `cita_detector.py` hacía INSERT directo sin verificar
si ya existía una cita para ese teléfono en la misma ventana de tiempo.

### Solución

**`agent/cita_detector.py` — dedup check ±2h antes del INSERT:**
```python
# Dedup: evitar INSERT duplicado para misma cita
if fecha_hora_naive and telefono:
    ventana_inicio = fecha_hora_naive - timedelta(hours=2)
    ventana_fin    = fecha_hora_naive + timedelta(hours=2)
    existing = await session.execute(text("""
        SELECT id FROM citas
        WHERE telefono = :tel
        AND fecha_hora >= :inicio
        AND fecha_hora <= :fin
        LIMIT 1
    """), {"tel": telefono, "inicio": ventana_inicio, "fin": ventana_fin})
    if existing.scalar():
        logger.info(
            f"[CITA_DETECTOR] Cita ya existe para {telefono} cerca de "
            f"{fecha_hora.strftime('%d/%m %H:%M')} — INSERT omitido (dedup)"
        )
        return True  # éxito sin duplicar
```

### Resultado
- Ventana ±2h: amplia para absorber ajustes de horario (ej: "a las 11" vs "a las 11:30")
- Compatible con SQLite (local) y PostgreSQL (Railway) — SQL estándar
- No requiere constraint UNIQUE en la tabla (no rompe datos existentes)
- El fix de FIX #10 previene la causa raíz; este fix es la red de seguridad

---

## 📦 Archivos modificados en esta sesión

| Archivo | Tipo | Fix |
|---------|------|-----|
| `agent/vision.py` | Mejora | `PROMPT_VISION` estructurado + `construir_contexto_historial()` + `construir_respuesta_cliente()` mejorada |
| `agent/notifications.py` | Mejora | `notificar_christian_vision()` acepta `imagen_bytes` y reenvía imagen |
| `agent/providers/whapi.py` | Mejora | `enviar_imagen_bytes()` — POST /messages/image con base64 |
| `agent/main.py` | Mejora | `_analizar_y_responder_imagen()` guarda contexto historial + pasa bytes a notificación |
| `agent/leads.py` | Bug fix | `tiene_cita_pendiente()` — consulta PostgreSQL por citas futuras |
| `agent/followup.py` | Bug fix | Guard en `ejecutar_seguimientos()` — omite leads con cita futura |
| `agent/cita_detector.py` | Bug fix | Dedup ±2h en `guardar_cita_automatica()` antes del INSERT |

## 🔗 Nota de interacción entre fixes

FIX #10 y FIX #11 son complementarios:
- **FIX #10** (seguimiento prematuro) elimina la **causa raíz** del duplicate INSERT — si no se manda el seguimiento incorrecto, el cliente no responde y el agente no re-genera el tag `[[AGENDAR:...]]`.
- **FIX #11** (dedup INSERT) es la **red de seguridad** — incluso si por otro motivo el agente re-detecta la cita, el INSERT duplicado no llega a la BD.

---

---

# 🔧 Fixes — Sesión 3 de Agosto, 2026 (parte 2)

Fecha: 3–4 de agosto de 2026  
Problema resuelto: **Loop infinito de seguimientos (caso Gustavo)**

---

## ✅ FIX #12: Loop infinito de seguimientos — counter reset + auto-STOP opt-out (3–4 ago 2026)

### Problema

Gustavo (5215511441317) recibió 8+ mensajes de seguimiento en 4 días, incluyendo después
de haber pedido explícitamente que dejaran de escribirle:

```
1-ago 07:29 — Hola Gustavo, ¿cómo resultó tu S24 Ultra?    (Seg 1/4)
1-ago 11:09 — ¿Llegaste a traer tu S24 Ultra?              (Seg 2/4)
1-ago 17:59 — "Enterado gracias"                            ← cliente responde
2-ago 07:07 — ¿Pudiste traer tu Samsung Galaxy?             (Seg 1/4) ← reiniciado!
2-ago 11:18 — Hola Gustavo, ¿llegaste a venir?             (Seg 2/4)
2-ago 12:00 — "YA NO ME ESTEN MSNDANFO MENSAGES OK"        ← cliente molesto
3-ago 07:36 — ¿Pudiste traer tu S24?                        (Seg 1/4) ← sigue!
3-ago 11:04 — Hola Gustavo, ¿llegaste a venir?             (Seg 2/4)
```

### Causa raíz (2 problemas independientes)

**Causa A — Reset incondicional del contador:**

`crear_o_actualizar_lead()` en `agent/leads.py` línea 114:
```python
# ANTES (bug):
if lead.estado in ("en_seguimiento", "perdido", "noshow"):
    lead.estado = "activo"
    lead.seguimientos_enviados = 0  # ← reset en CUALQUIER respuesta, incluso "gracias"
    lead.seguimiento_enviado_en = None
    lead.seguimiento_realizado = False
```

Cuando Gustavo respondió "Enterado gracias", el contador se reinició a 0 → la secuencia
de 4 seguimientos se reinició desde el principio → loop infinito.

**Causa B — Sin auto-STOP por opt-out:**

Cuando Gustavo escribió "YA NO ME ESTEN MSNDANFO MENSAGES OK", el agente respondió
con texto diciendo "no le mando más mensajes", pero NUNCA llamó `detener_numero()`.
El seguimiento del día siguiente continuó igual.

### Solución

**`agent/leads.py` — reset inteligente del contador:**

```python
# Keywords que indican NUEVA intención de servicio (reset válido)
_KEYWORDS_INTENCION_SERVICIO = [
    "quiero", "necesito", "precio", "cuánto", "cuanto", "cuesta", "sale",
    "reparar", "arreglar", "componer", "revisar", "falla", "daño", "dañado",
    "pantalla", "carga", "batería", "bateria", "puerto", "bocina",
    "no enciende", "no prende", "no carga", "no funciona", "no sirve",
    "agendar", "cita", "cuando", "cuándo", "horario",
    # ... marcas y dispositivos ...
]

def _tiene_intencion_servicio(texto: str) -> bool:
    """True si el mensaje contiene palabras de consulta de servicio."""
    return any(kw in texto.lower() for kw in _KEYWORDS_INTENCION_SERVICIO)
```

En `crear_o_actualizar_lead()`:
```python
async def crear_o_actualizar_lead(..., mensaje_texto: str = ""):
    ...
    if lead.estado in ("en_seguimiento", "perdido", "noshow"):
        lead.estado = "activo"
        # Solo resetear si hay nueva intención real — NO en respuestas de cortesía
        if _tiene_intencion_servicio(mensaje_texto):
            lead.seguimientos_enviados = 0
            lead.seguimiento_enviado_en = None
            lead.seguimiento_realizado = False
            logger.info(f"[LEAD] {telefono} — secuencia reiniciada (nueva intención)")
        else:
            logger.info(f"[LEAD] {telefono} — secuencia PRESERVADA (respuesta de cortesía)")
```

**`agent/main.py` — detección automática de opt-out:**

```python
_OPT_OUT_KEYWORDS = [
    "ya no me manden", "ya no me escriban", "ya no me mandes",
    "no me manden", "no me escriban", "no me molesten", "no me contacten",
    "dejen de escribirme", "paren de mandarme", "dejen de mandarme",
    "basta de mensajes", "basta ya",
    "ya no quiero mensajes", "stop", "no más mensajes",
]

_texto_lower = (msg.texto or "").lower()
if any(kw in _texto_lower for kw in _OPT_OUT_KEYWORDS):
    if not await numero_esta_stopped(msg.telefono):
        await detener_numero(msg.telefono, razon="opt_out_cliente")
        asyncio.create_task(
            proveedor.enviar_mensaje(
                GRUPO_INTERNO,
                f"⛔ *OPT-OUT AUTOMÁTICO*\n📱 {msg.telefono}\n"
                f"💬 «{msg.texto[:120]}»\n✅ Número detenido."
            )
        )
        # El agente aún responde (disculpa), pero sin seguimientos futuros
```

### Comportamiento después del fix

| Situación | Antes (bug) | Después (fix) |
|-----------|-------------|---------------|
| Cliente responde "gracias" | ❌ Reset counter → reinicia 4 mensajes | ✅ Counter preservado, secuencia continúa |
| Cliente responde "quiero reparar mi iPhone" | ✅ Reset counter (correcto) | ✅ Reset counter (correcto) |
| Cliente escribe "ya no me manden mensajes" | ❌ Agente dice que no mandará más, pero sí manda | ✅ `detener_numero()` automático + notificación a Christian |
| Cliente bloqueado manualmente desde grupo | ✅ Funciona igual que antes | ✅ Sin cambio |

### Archivos modificados

| Archivo | Cambio |
|---------|--------|
| `agent/leads.py` | `_KEYWORDS_INTENCION_SERVICIO` + `_tiene_intencion_servicio()` + parámetro `mensaje_texto` en `crear_o_actualizar_lead()` |
| `agent/main.py` | Import `detener_numero`, `numero_esta_stopped` + bloque opt-out detection + `mensaje_texto=msg.texto` en llamada a `crear_o_actualizar_lead()` |

### Decisión de diseño

El opt-out automático deja que el agente responda UNA VEZ más (mensaje de disculpa que
Claude generará dado el contexto del historial), luego aplica el STOP. Esto es mejor que
silenciar el número antes de responder porque:
1. El cliente recibe confirmación de que su solicitud fue atendida.
2. No parece que el agente simplemente ignoró su mensaje.
3. Christian recibe la notificación en paralelo vía `asyncio.create_task` (no bloquea).
