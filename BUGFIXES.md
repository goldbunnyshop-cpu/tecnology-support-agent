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
