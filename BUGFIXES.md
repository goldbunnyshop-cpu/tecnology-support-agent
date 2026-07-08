# Registro de correcciones — Tecnology Support WhatsApp Bot

> Sesión de debug: 16 de junio de 2026  
> Archivos modificados: `agent/cita_detector.py`, `agent/brain.py`, `agent/pricing_sheets.py`, `agent/pricing_scheduler.py`, `agent/main.py`

---

## Bug 1 — Triplicación de notificaciones de citas en el grupo interno

**Síntoma:** Al agendar una cita, el grupo interno de WhatsApp recibía el mismo mensaje 2 o 3 veces.

**Causa raíz:** Doble creación del evento en Google Calendar.

- `agendar_cita()` en `google_calendar.py` crea el evento (Paso 1).
- Inmediatamente después, `main.py` llama a `guardar_cita_automatica()` en `cita_detector.py`.
- Esa función **también** llamaba a `crear_en_google_calendar()` internamente (Paso 2 duplicado).
- El sistema anti-duplicados en `appointment_notifications.py` usa `evento_id` para evitar notificaciones repetidas, pero como eran **dos eventos distintos** con **dos IDs distintos**, ambos pasaban el filtro y generaban notificaciones separadas.

**Fix aplicado — `agent/cita_detector.py`:**  
Se eliminó el bloque que llamaba a `crear_en_google_calendar()` dentro de `guardar_cita_automatica()`. La función ahora tiene una sola responsabilidad: persistir la cita en PostgreSQL.

```python
# ELIMINADO (líneas 188-198 originales):
# try:
#     await crear_en_google_calendar(nombre=nombre, ...)
# except Exception as cal_e:
#     logger.warning(f"[CITA_DETECTOR] Google Calendar saltado: {cal_e}")

# REEMPLAZADO POR comentario explicativo:
# NOTA: Google Calendar ya fue creado por agendar_cita() en google_calendar.py
# No crear aquí — causaría evento duplicado y triplica notificaciones al grupo.
```

---

## Bug 2 — Crash silencioso al guardar citas en PostgreSQL (timezone)

**Síntoma:** Las citas se agendaban en Google Calendar pero **no se persistían en PostgreSQL**. El log mostraba el error pero no era obvio en producción.

**Error exacto en log:**
```
DBAPIError: invalid input for query argument $5:
datetime.datetime(2026, 6, 16, 19, 30, tzinfo=zoneinfo.ZoneInfo(key='America/Mexico_City'))
TypeError: can't subtract offset-naive and offset-aware datetimes
```

**Causa raíz:** La columna `fecha_hora` en PostgreSQL es `TIMESTAMP WITHOUT TIME ZONE`. El código pasaba un `datetime` con `tzinfo=ZoneInfo("America/Mexico_City")`. PostgreSQL con asyncpg rechaza datetimes timezone-aware en columnas sin zona.

**Fix aplicado — `agent/cita_detector.py`:**

```python
# ANTES:
"fecha_hora": fecha_hora,

# DESPUÉS:
# PostgreSQL usa TIMESTAMP WITHOUT TIME ZONE — quitar tzinfo antes de insertar
fecha_hora_naive = fecha_hora.replace(tzinfo=None) if fecha_hora else None
"fecha_hora": fecha_hora_naive,
```

> **Nota:** La hora local se preserva. Solo se elimina el metadata de zona horaria. La interpretación de la hora en CDMX sigue siendo correcta.

---

## Bug 3 — Precios inconsistentes cuando el modelo se mencionó en turno anterior

**Síntoma:** Si un cliente decía "Es un Motorola Stylus 2023" en un mensaje y luego en el siguiente decía "¿cuánto cuesta la pantalla?", el bot no encontraba precio o daba un resultado incorrecto.

**Causa raíz:** En `agent/brain.py`, el bloque `if es_display:` sin `modelo_actual` llamaba directamente a `_resolver_pricing_desde_texto(mensaje)` usando el texto completo del mensaje como query (ej: `"solo la pantalla, se le cayó mi hijo"`). Ese texto no matchea ningún producto en el catálogo.

El código tenía lógica de recuperación de historial (`_buscar_ultimo_modelo_historial`) pero solo se activaba en rutas posteriores, **después** del bloque `if es_display:`.

**Fix aplicado — `agent/brain.py`:**

```python
# ANTES (línea 320):
if es_display:
    return await _resolver_pricing_desde_texto(mensaje)

# DESPUÉS:
if es_display:
    modelo_hist = _buscar_ultimo_modelo_historial(historial)
    marca_hist = _buscar_ultima_marca_historial(historial)
    if modelo_hist:
        # Usar contexto del historial antes de buscar con texto crudo
        r = await cotizar_con_fallback(marca_hist or "", modelo_hist)
        return _limpiar_respuesta_pricing(r)
    return await _resolver_pricing_desde_texto(mensaje)
```

---

## Mejora 1 — Catálogo de precios persiste entre reinicios de Railway (SQLite)

**Problema:** El catálogo de 741 productos (DISPLAYS, BATERÍAS ANDROID, BATERÍAS iPHONE) se descargaba de Google Sheets cada hora. Si Google Sheets no estaba disponible o el caché expiraba en un momento de alta demanda, la consulta fallaba o era lenta.

**Solución implementada — `agent/pricing_sheets.py`:**

Se agrega una capa de caché SQLite (`catalog_cache.db`) en el servidor de Railway. El catálogo ahora tiene **tres niveles de caché en orden de prioridad**:

1. **Memoria RAM** — más rápido, se pierde al reiniciar (TTL: 24h)
2. **SQLite en Railway** — sobrevive reinicios del contenedor (TTL: 24h)
3. **Google Sheets** — solo se consulta si los dos anteriores están vacíos o expirados

El TTL cambió de **1 hora a 24 horas**. Configurable con la variable de entorno `PRICING_SHEETS_CACHE_TTL` (en segundos).

**Tarea cron diaria — `agent/pricing_scheduler.py`:**  
Todos los días a las **3:00 AM hora CDMX** el scheduler descarga el catálogo fresco de Sheets y actualiza el SQLite. La laptop del operador no necesita estar encendida.

**Endpoint de recarga manual — `agent/main.py`:**

```http
POST /admin/reload-catalogo
X-Admin-Token: {ADMIN_TOKEN}
```

Fuerza la recarga inmediata desde Sheets sin reiniciar el servidor. Útil cuando se actualizan precios en Google Sheets y no se quiere esperar hasta las 3 AM.

---

## Mejora 2 — Compresión de cotizaciones en el historial de conversación

**Problema:** Cada respuesta de cotización completa (300–600 caracteres con precios en varias calidades) se guardaba completa en el historial de PostgreSQL. Con el límite de 20 mensajes, si la conversación tuvo 8 cotizaciones, Claude recibía esos 8 bloques completos como contexto en cada turno — gastando miles de tokens innecesariamente.

**Solución implementada — `agent/main.py`:**

Se agrega la función `_para_historial(respuesta)` que detecta respuestas de cotización por patrones (`$1,234`, longitud > 200 chars) y guarda una versión comprimida en memoria:

```
Texto enviado al cliente:
  📱 *iPhone 15 Plus*
  ✅ Calidad Genérica: $2,800 MXN
  ✅ Calidad Original: $3,500 MXN
  ...

Texto guardado en historial:
  [Cotización enviada: iPhone 15 Plus — $2,800–$3,500 MXN]
```

Se aplica en los 5 puntos donde se guarda `guardar_mensaje(..., "assistant", ...)` en `main.py`.

---

## Bug 4 — Doble recordatorio al cliente y al grupo (efecto cascada del Bug 1)

**Síntoma:** José de Jesús recibió 2 mensajes de recordatorio en su WhatsApp personal Y el grupo interno recibió 2 mensajes de "⏰ RECORDATORIO" para la misma cita. Lo mismo con Rodolfo.

**Log (líneas 596–612):**
```
[CITAS GRUPO] 🔄 Intento 1/2 — Enviando... — ⏰ *RECORDATORIO: Cita de José de Jesús...*
[CITAS GRUPO] ✅ Mensaje enviado al grupo exitosamente
[CITAS] Recordatorio 1h — José de Jesús 2:00 p.m. ...
[CITAS GRUPO] 🔄 Intento 1/2 — ... ← SEGUNDA VEZ (duplicado)
...
[RECORDATORIO] ✅ Enviado a 5215572114286 (José de Jesús)
[RECORDATORIO] ✅ Enviado a 5215572114286 (José de Jesús) ← SEGUNDA VEZ
```

**Causa raíz:** El Bug 1 creaba dos eventos de Google Calendar para cada cita. El poller de recordatorios consultaba el Calendar y encontraba DOS eventos "José de Jesús a las 2:00 PM" con IDs distintos. Como el anti-duplicados usa `evento_id`, ambos pasaban el filtro y disparaban recordatorio independiente.

**Fix:** Es efecto cascada del Bug 1. Al eliminar la segunda creación de evento en `cita_detector.py`, el Calendar solo tendrá UN evento por cita y los recordatorios también serán únicos. **No requiere cambio adicional de código.**

---

## Bug 5 — Precio no consultado cuando cliente responde "marca modelo" al fallback

**Síntoma:** El bot preguntaba "¿de qué equipo es?" y el cliente respondía con marca+modelo ("Huawei p40"). El motor de pricing NO detectaba eso como consulta de precio y delegaba a Claude. Claude respondía "déjame verificar" pero nunca hacía la búsqueda real.

**Log (líneas 947–953):**
```
[PRICING-DEBUG] Mensaje: 'Huawei p40'
[PRICING-DEBUG] es_consulta_precio=False, es_display=False, es_no_display=False, es_modelo_breve=False
[PRICING-DEBUG] marca_actual='huawei', modelo_actual='p40'
[PRICING-DEBUG] NO ES CONSULTA PRECIO → delegando a Claude
→ Claude: "Para el Huawei P40 déjame verificar disponibilidad y precio exacto..."
```

**Causa raíz:** La condición en `brain.py` para activar el motor de pricing requería que al menos un flag fuera `True` (`es_display`, `es_consulta_precio`, o `es_modelo_breve`). Un mensaje como "Huawei p40" solo tiene marca+modelo detectados, sin keywords de precio → ningún flag activo → se delegaba a Claude.

**Fix aplicado — `agent/brain.py` (nuevo bloque antes de `marca_suelta`):**

```python
# Si cliente responde con marca+modelo al fallback "solo dime de qué equipo es"
if modelo_actual and marca_actual and not es_display and not es_consulta_precio:
    _ult_asistente = next(
        (h["content"] for h in reversed(historial) if h["role"] == "assistant"), ""
    ).lower()
    _FALLBACK_TRIGGERS = ("solo dime de qué equipo es", "de qué equipo es", ...)
    if any(t in _ult_asistente for t in _FALLBACK_TRIGGERS):
        r = await cotizar_con_fallback(marca_actual, modelo_actual)
        return _limpiar_respuesta_pricing(r)
```

---

## Mejora 3 — Captura de lead cuando el precio no está disponible

**Problema:** Cuando marca+modelo eran conocidos pero no había precio en catálogo, `_mensaje_no_disponible()` respondía con una lista de "equipos que SÍ tenemos" y no pedía datos de contacto. El cliente quedaba bloqueado sin opción de ser contactado por el técnico.

**Log:** Cliente pregunta display Huawei P40 → no encontrado → bot lista otros equipos → cliente abandona (o Claude improvisa captura fragile).

**Fix aplicado — `agent/pricing.py` (`_mensaje_no_disponible()`):**

```python
# ANTES:
"❌ Disculpa, no tenemos *MARCA MODELO* disponible...\n✅ Pero tenemos: Samsung, iPhone..."

# DESPUÉS:
"❌ Aún no tenemos display para *MARCA MODELO* en inventario.\n"
"Pero nuestro técnico puede conseguirlo especialmente para ti. 🔍\n\n"
"Solo déjame:\n📛 *Tu nombre*\n📞 *¿Prefieres WhatsApp o llamada?*\n\n"
"Te confirmamos precio y disponibilidad en menos de 24 horas. ¿Te parece?"
```

El cliente da su nombre, el bot ya tiene su número de WhatsApp. Claude se encarga de guardar el contexto como lead calificado (instrucción en system prompt).

---

## Variables de entorno relacionadas

| Variable | Descripción | Default |
|---|---|---|
| `PRICING_SHEETS_CACHE_TTL` | TTL del catálogo en segundos | `86400` (24h) |
| `CATALOG_DB_PATH` | Ruta del SQLite del catálogo | `./catalog_cache.db` |
| `ADMIN_TOKEN` | Token para endpoints `/admin/*` | *(requerido)* |
| `GOOGLE_SHEETS_ID` | ID del spreadsheet de precios | *(hardcoded como fallback)* |

---

## Cómo verificar que los fixes están activos

**Bug 1 resuelto** — En el log, al agendar una cita ya NO debe aparecer la secuencia:
```
[CALENDAR] ✅ Cita agendada: ...
[CITA_DETECTOR] 📅 Evento creado en Google Calendar: ...   ← esto ya no debe salir
```
Solo debe aparecer la primera línea, no la segunda.

**Bug 2 resuelto** — En el log ya no debe aparecer `DBAPIError` ni `TypeError: can't subtract offset-naive`. La línea `[CITA_DETECTOR] COMMIT exitoso` debe aparecer siempre que se agenda una cita.

**Bug 3 resuelto** — En el log, cuando `es_display=True` y `modelo_actual='None'`, debe aparecer:
```
[PRICING-DEBUG] Display sin modelo actual → usando historial: marca='motorola' modelo='stylus 2023'
```

**Mejoras activas** — Al arrancar Railway, el log debe mostrar:
```
[INIT] Catálogo de precios listo — 741 productos
[SHEETS] Catálogo desde SQLite (741 productos, edad=X.Xh)
```
