# TECNOLOGY SUPPORT — Estado del Proyecto WhatsApp Agent

> **Archivo único de referencia.** Consolida estado, historial de bugs, arquitectura y pendientes.
> Última actualización: **10 de julio 2026 (sesión 3)**.
> Para no romper nada: leer `COTIZADOR.md` (motor de precios) y `COMANDOS.md` (grupo interno)
> antes de tocar `pricing.py`, `pricing_fallback.py`, `brain.py` o `commands*.py`.

---

## 1. ESTADO ACTUAL

### Infraestructura
| Componente | Estado |
|---|---|
| Webhook WhatsApp (Whapi) | ✅ Productivo — Railway |
| Claude AI (claude-sonnet-4-6) | ✅ Productivo |
| Google Calendar (citas) | ✅ Productivo |
| PostgreSQL Railway | ✅ Productivo |
| SQLite local (cache catálogo) | ✅ Productivo |
| Deploy (Railway → GitHub main) | ✅ Auto-deploy |
| Docker container | ✅ Productivo |

### Features operativos
- ✅ Recibir y responder mensajes WhatsApp
- ✅ Motor de cotización de pantallas (Hugo Shop + Google Sheets fusionados)
- ✅ Agendar citas automáticas → Google Calendar + PostgreSQL
- ✅ Leads: creación, estados, asignación de asesores
- ✅ Sleep mode (silencio 00:00–06:30)
- ✅ Pausa manual: `pausa: NÚMERO` (2 h)
- ✅ Sistema STOP/ON: bloqueo permanente de números
- ✅ Análisis de imágenes/videos (Claude Vision)
- ✅ Seguimiento automático y retomas (cada 10 min)
- ✅ Smart reminders (1 h antes de cita)
- ✅ Notificaciones al grupo interno "Taller Interno TS"
- ✅ Comandos del grupo: `listo`, `demora`, `nota`, `orden`, `presupuesto`, `2nd`, `noshow`, etc.
- ✅ Comando `masivo` / `masivo preview` — seguimiento masivo a leads sin cita
- ✅ Estado `noshow` en leads — excluye del scheduler y del masivo automático
- ✅ Deduplicación de mensajes y citas
- ✅ Caché de catálogo SQLite (TTL 24 h, refresh 3 AM CDMX)
- ✅ Módulos auxiliares con Haiku 4.5 (cita_detector, followup, vision, reports) — ~50% menos costo API
- ✅ Sistema de evals — `tests/eval/run_eval.py` (52 casos)

### Pendientes
| Tarea | Prioridad | Esfuerzo |
|---|---|---|
| Integración Auto-CRM bidireccional | 🔴 Alta | 3-4 h |
| Caché de slots Calendar | 🟡 Media | 2 h |
| Comandos `/reportes`, `/stats` en WhatsApp | 🟢 Baja | 1.5 h |

---

## 2. ARQUITECTURA

```
Cliente WhatsApp
    │
    ▼
Whapi.cloud → POST /webhook
    │
agent/main.py
    ├─ Guards: sleep mode / pausa / stop
    ├─ Grupo interno → commands_control.py + commands.py
    └─ Cliente externo
           ├─ agent/brain.py
           │     ├─ Motor de precios (intercepta ANTES de Claude)
           │     │     └─ pricing_fallback.py → pricing.py + pricing_sheets.py
           │     └─ Claude API (claude-sonnet-4-6) — para el resto
           ├─ agent/memory.py (PostgreSQL + SQLite)
           ├─ agent/leads.py
           ├─ agent/google_calendar.py (citas)
           ├─ agent/vision.py (imágenes)
           └─ agent/notifications.py → grupo interno
```

### Archivos clave
| Archivo | Rol |
|---|---|
| `agent/brain.py` | Orquestador IA: detecta consultas de precio, llama Claude, gestiona contexto |
| `agent/pricing.py` | Hugo Shop CSV: búsqueda, matching, multiplicadores, formateador |
| `agent/pricing_sheets.py` | Google Sheets: DISPLAYS + BATERÍAS, búsqueda por score |
| `agent/pricing_fallback.py` | Pipeline fusionado Hugo+Sheets, fallback fixoem.com |
| `agent/memory.py` | PostgreSQL/SQLite: mensajes, leads, citas, pausas, stopped_numbers |
| `agent/main.py` | FastAPI webhook: guards, routing, envío de respuestas |
| `agent/commands.py` | Comandos del grupo interno (menú, listo, demora, nota…) |
| `agent/commands_control.py` | stop / on / stopped (escriben en BD) |
| `agent/pausa_manager.py` | pausa / reanudar (escriben en BD) |
| `agent/cita_detector.py` | Detecta intención de cita, guarda en PostgreSQL |
| `agent/google_calendar.py` | Crea eventos en Google Calendar |
| `config/prompts.yaml` | System prompt del agente |
| `knowledge/hugo_shop.csv` | Catálogo de precios Hugo Shop (~1100 filas) |

---

## 3. MOTOR DE COTIZACIÓN — FLUJO Y REGLAS

> Documentación completa en `COTIZADOR.md`. Aquí el resumen ejecutivo.

### Flujo para una consulta de display
```
brain.py detecta precio → _resolver_pricing_desde_texto()
    ↓
pricing_fallback.py: cotizar_con_fallback(marca, modelo, "display")
    ↓
_cotizar_display_fusionado(marca, modelo)
    1. recolectar_categorias_hugo(marca, modelo)   ← Hugo Shop CSV (primario)
    2. Si Hugo vacío + marca="" → buscar_modelo_sin_marca(modelo) ← FIX Bug S24 Ultra
    3. recolectar_categorias_display_sheets(marca, modelo)  ← Google Sheets (complementa)
    4. cotizar_fuentes_externas()  ← fixoem.com (último recurso)
    5. _mensaje_no_disponible()    ← captura de lead (nombre + contacto)
```

### Multiplicadores (NO cambiar sin consenso)
| Calidad | Multiplicador | Fuente |
|---|---|---|
| GENERICO (Incell, Copia, IPS) | ×4 | Hugo y Sheets |
| ORIGINAL (Oled, Original) | ×4 | Hugo y Sheets |
| AMOLED | ×3 | Hugo y Sheets |
| Tapas iPhone | ×8 | pricing_fallback |
| Tapas otras marcas | ×5 | pricing_fallback |

### Hugo Shop — parseo del CSV
- Columnas: `CODIGO, DESCRIPCION, CALIDAD, COLOR, PRECIO_1, PRECIO_2`
- Filas-header `SAMSUNG,,,,,` anclan la marca de toda la sección
- `PRECIO_1` está en USD; se multiplica para llegar a MXN
- Una descripción puede cubrir varios modelos: `H40 LITE/E40/V40` (separados por `/`)
- `ALIAS_MARCAS`: mapea 'poco'→'XIAOMI', 'galaxy'→'SAMSUNG', 'zte'→'ZTE', etc.

---

## 4. HISTORIAL COMPLETO DE BUGS Y FIXES

> Orden cronológico. Los más recientes al final.

---

### Mayo 15, 2026 — Sistema de citas (ARREGLOS_REALIZADOS)

**Bug: Tags de cita no se procesaban**
- `tag = None` (código desactivado) → citas no llegaban a Google Calendar ni a PostgreSQL
- Fix: Crear `parsear_tag_agendar()` + `quitar_tags()` en `main.py`; habilitar el bloque de ejecución
- Fix: Cliente ya no ve el tag `[[AGENDAR:...]]` en la respuesta

**Bug: Caracteres mojibake (UTF-8)**
- `Â¡` en lugar de `¡` al enviar por Whapi
- Fix `agent/providers/whapi.py`: validación explícita UTF-8 + `Content-Type: charset=utf-8`

**Bug: Notificaciones al grupo no llegaban**
- Sin logging = errores silenciosos, sin reintentos
- Fix `agent/appointment_notifications.py`: 3 reintentos, logging detallado por etapa

**Bug: Citas no se guardaban en PostgreSQL**
- Usaba ORM con modelo no importado correctamente
- Fix: raw SQL con `text(...)` en `cita_detector.py`

---

### Mayo 28, 2026 — Auditoría completa (BITACORA / LISTA_PENDIENTES)

**Mejoras aplicadas:**
- Ruido de logs DEBUG reducido (aiosqlite, sqlalchemy)
- Fallback de Google Calendar: si falla, cita se guarda en PostgreSQL de todas formas
- Deduplicación por `evento_id` funcional

---

### Mayo 29, 2026 — Multiplicadores eliminados accidentalmente (PRECIO_FIX)

**Bug crítico: precios 10× más baratos**
- `agent/pricing_productos.py`: se había reemplazado `precio_usd * multiplier` por `int(precio_usd)`
- Samsung S23 Ultra mostraba $145 MXN en vez de $1200+ MXN
- Fix: restaurar `multiplier = MULTIPLICADOR_POR_CATEGORIA.get(categoria, 4)` + `precio_mxn = int(precio_usd * multiplier)`

---

### Mayo 31, 2026 — Router de pricing (REPORTE_CAMBIOS)

**Bug: Motor de precios se disparaba con cualquier cosa**
- "precio del mantenimiento" → daba cotización de display
- "¿el diagnóstico tiene costo?" → pedía variante de display
- "cambio de batería" → pedía variante de display (en vez de cotizar batería)
- Fix `brain.py`: `_PATRON_NO_DISPLAY` (mantenimiento, diagnóstico, batería, consola, software…) delega a Claude; `_PATRON_DISPLAY` solo dispara con `display/pantalla/mica/cristal/gorilla`
- Resultado: tasa de aprobación evals 77% → 90%

---

### Junio 1, 2026 — Sistema STOP/ON (ESTADO_FINAL_2026_06_01)

**Feature: bloqueo permanente de números**
- `agent/memory.py`: nueva tabla `StoppedNumber` (PostgreSQL)
- `agent/commands_control.py`: procesa `stop: NÚM` / `on: NÚM` / `stopped`
- `agent/main.py`: guard `numero_esta_stopped()` en el webhook
- Regla clave: store **en BD** (no en dict en memoria) para sobrevivir reinicios

**Feature: integración MercadoLibre (fallback)**
- `agent/pricing_mercadolibre_v2.py`: búsquedas separadas genérico/original, 3er precio más bajo, filtro nacional
- Fallback: Hugo Shop primero; si no tiene → MercadoLibre

---

### Junio 3, 2026 — Cotizaciones espontáneas de iPhone 12 (DIAGNOSTICO_COTIZACIONES)

**Bug: bot daba precios de iPhone 12 sin que el cliente lo pidiera**
- La búsqueda en Sheets aceptaba cualquier producto con ≥2 palabras genéricas (`display`, `de`)
- Fix `pricing_sheets.py`: `_titulo_coincide_modelo()` — si el "modelo" es texto basura, no devuelve nada → pide marca+modelo al cliente

---

### Junio 5, 2026 — Motor de cotización refactorizado (COTIZADOR)

**Bug: una sola calidad con etiqueta equivocada**
- `pricing_sheets.formatear_cotizacion_sheets` tomaba `max(p1,p2,p3)` de una fila y etiquetaba todo como "Calidad Original"
- Fix: nueva ruta `recolectar_categorias_display_sheets()` agrupa TODAS las filas por calidad

**Bug: clasificación de calidad incorrecta en Sheets**
- `Incell FHD` (genérico) caía en ORIGINAL
- Fix: `clasificar_calidad_titulo()` con prioridad INCELL/COPIA > FHD

**Mejora: mensaje cuando falta el modelo**
- `_mensaje_no_disponible()` ahora pide nombre y contacto (captura de lead)
- Antes: listaba equipos que sí tiene; ahora: invita al técnico a conseguirlo

**Mejora: fusión de fuentes**
- Hugo manda. Sheets solo complementa calidades que falten
- `_fusionar_categorias()` en `pricing_fallback.py`

---

### Junio 5, 2026 — Bugs de comandos del grupo (COMANDOS)

**Bug: `stop` no detenía la conversación**
- Había dos stores: dict en memoria (`_NUMEROS_BLOQUEADOS` — NADIE lo lee en el webhook) + BD (la que sí lee `main.py`)
- Fix: `stop/on` ahora usan `agent.memory.detener_numero/reactivar_numero` (BD)

**Bug: `2nd` / `noshow` lanzaban AttributeError/ImportError**
- Llamaban a `crm.registrar_cupon` y `brain.generar_mensaje_noshow` que no existían
- Fix: creados en `crm.py` y `brain.py`; resilientes si falta `GOOGLE_SHEET_ID`

**Bug: confirmación de `stop`/`on` al grupo daba Whapi 400**
- `main.py` respondía al **nombre** del grupo en vez del `chat_id` (`...@g.us`)
- Fix: responder a `getattr(msg, "chat_id_raw", ...)`

**Bug: `pausa` se "saltaba" / `reanudar` no funcionaba**
- `procesar_pausa` retornaba "ya pausado" por dict en memoria sin renovar BD
- `reanudar_pausa` tenía comentada la llamada a BD
- Fix: ambas funciones delegan siempre a BD (`pausar_conversacion` / `reanudar_conversacion`)
- Fix adicional: BD migrada de SQLite efímero a PostgreSQL persistente

---

### Junio 16, 2026 — Triplicación de notificaciones (BUGFIXES)

**Bug 1: cita crea 2 eventos en Google Calendar → 2 notificaciones al grupo**
- `agendar_cita()` crea el evento (paso 1)
- `guardar_cita_automatica()` en `cita_detector.py` también llamaba a `crear_en_google_calendar()` (paso 2 duplicado)
- Dos eventos con dos IDs distintos → anti-duplicados no los filtraba
- Fix `cita_detector.py`: eliminar el bloque de creación de Calendar dentro de `guardar_cita_automatica()`

**Bug 2: timezone crash silencioso en PostgreSQL**
- `fecha_hora` con `tzinfo=ZoneInfo("America/Mexico_City")` en columna `TIMESTAMP WITHOUT TIME ZONE`
- Fix: `fecha_hora_naive = fecha_hora.replace(tzinfo=None)` antes de insertar

**Bug 3: precio incorrecto cuando el modelo estaba en turno anterior**
- `if es_display:` sin `modelo_actual` llamaba a `_resolver_pricing_desde_texto(mensaje)` con texto crudo
- Fix `brain.py`: antes de usar texto crudo, buscar `_buscar_ultimo_modelo_historial(historial)`

**Bug 4: `stop` / `pausa` fallaban cuando `marca_actual` detectada sin keywords de precio**
- Bot preguntaba "¿de qué equipo es?" → cliente respondía "Huawei P40" → motor no cotizaba
- Fix `brain.py`: nuevo bloque que detecta respuesta a `_FALLBACK_TRIGGERS` del último mensaje del asistente → activa cotización

**Mejora: caché SQLite del catálogo sobrevive reinicios de Railway**
- Antes: catálogo en RAM perdido en cada redeploy
- Fix `pricing_sheets.py`: caché en `catalog_cache.db` (SQLite, TTL 24 h)
- Scheduler `pricing_scheduler.py`: refresh diario a las 3 AM CDMX
- Endpoint: `POST /admin/reload-catalogo` para recarga manual

**Mejora: compresión de cotizaciones en el historial**
- Cotizaciones largas (300-600 chars) se guardan comprimidas: `[Cotización enviada: iPhone 15 Plus — $2,800–$3,500 MXN]`
- Fix `main.py`: función `_para_historial(respuesta)` aplicada en los 5 puntos de `guardar_mensaje`

---

### Junio 27, 2026 — Bugs del motor de pricing (commit 3c751a7)

**Bug 1 (Samsung S24 Ultra — precio incorrecto $18,800 en vez de $7,500 MXN)**
- Causa: cliente dice "s24 ultra" sin decir "samsung" → `_extraer_marca_modelo()` retorna marca vacía → Hugo falla con brand="" → Sheets aplica ×4 sobre precios ya en MXN → $4,700 × 4 = $18,800 incorrecto
- Hugo SÍ tiene S24 Ultra a $1,875 (PRECIO_1 USD) → $1,875 × 4 = $7,500 MXN correcto
- Fix `pricing_fallback.py` (`_cotizar_display_fusionado`): cuando Hugo falla y `marca=""`, llamar a `buscar_modelo_sin_marca(modelo)` ANTES de ir a Sheets

**Bug 2 (ZTE V41 Smart — no encontrado)**
- Causa: mensaje "ZTE V41 Smart" tiene marca+modelo pero sin keywords de precio → `es_consulta_precio=False`, `es_display=False` → no se activa el motor → Claude dice "no tenemos información"
- ZTE V41 Smart SÍ está en Hugo a $184 × 4 = $736 MXN
- Fix `brain.py` (`_intentar_respuesta_pricing_contextual`): cuando `marca_actual AND modelo_actual` están detectados y el mensaje tiene ≤4 tokens (solo el dispositivo), cotizar implícitamente

**Bug 3 (Poco M5s — no encontrado)**
- Causa: descripción "POCO M5S" dentro de "NOTE10 4G/10S/POCO M5S" (sección XIAOMI) se parseaba como `base='poco', variante='m5s'` pero el query normaliza como `base='m5', variante='s'` → sin coincidencia
- Fix `pricing.py` (`_parsear_chunk_descripcion`): cuando el primer token de un chunk es una marca conocida (en `ALIAS_MARCAS`: poco, redmi, galaxy…), stripearla y re-parsear el resto. 'POCO M5S' → strip 'poco' → re-parsear 'm5s' → `('m5', 's')` ✓

---

### Junio 27, 2026 (sesión 2) — Seguimientos, costos y comando masivo

**Bug: seguimientos 2/3/4 nunca se enviaban**
- Causa: `registrar_seguimiento_enviado` ponía `seguimiento_realizado = True` tras enviar el seg 1.
  La query `obtener_leads_para_seguimiento` filtra `seguimiento_realizado == False` → el lead quedaba bloqueado para siempre. Solo el seguimiento 1 (2h) corría.
- Fix `leads.py` (`registrar_seguimiento_enviado`): después de incrementar, si `seguimientos_enviados < MAX_SEGUIMIENTOS` → poner `seguimiento_realizado = False`. Solo pone `True` cuando se agotaron los 4.

**Bug: intervalo del seguimiento 3 incorrecto (36h en vez de 72h)**
- `_INTERVALOS_SEGUIMIENTO[2]` estaba en `timedelta(hours=36)`.
- Fix `leads.py`: cambiado a `timedelta(hours=72)` (3 días completos).
- Secuencia correcta: seg 1 = 2h | seg 2 = 24h | seg 3 = 72h | seg 4 = 7 días.

**Optimización de costos Claude API (~50% ahorro)**
- Problema: `cita_detector.py` usaba Sonnet 4.6 en CADA mensaje del cliente para clasificar si era cita o no (tarea simple). Mismo para followup, vision, reports.
- Fix: cambiar a `claude-haiku-4-5-20251001` en 4 módulos:
  - `cita_detector.py` — clasificación sí/no de cita (max_tokens 500→200)
  - `followup.py` — generación de mensajes de seguimiento (max_tokens 250→200)
  - `vision.py` — análisis de imágenes de daños (max_tokens 450→400)
  - `reports.py` — resumen semanal (max_tokens 80, sin cambio)
- `brain.py` mantiene Sonnet 4.6 (respuesta principal al cliente).
- Historial en `main.py`: reducido de 20 a 10 mensajes (con compresión activa, suficiente contexto).

**Feature: comando `masivo` y `masivo preview`**
- Desde el grupo "Taller Interno TS", envía un seguimiento personalizado (con Haiku) a todos los leads sin cita confirmada.
- `masivo preview` → lista los leads elegibles SIN enviar nada. Usar siempre primero.
- `masivo` → envía y reporta resumen al grupo.
- Archivo: `agent/commands.py` — funciones `_cmd_masivo_preview` y `_cmd_seguimiento_masivo`.

**Feature: estado `noshow` en leads**
- Antes: el comando `noshow: NÚMERO` enviaba el cupón pero NO cambiaba el estado del lead. El cliente `noshow` podía recibir seguimientos automáticos y masivos.
- Fix: `noshow:` ahora llama a `marcar_lead_noshow(telefono)` → `estado = "noshow"`, `seguimiento_realizado = True`.
- El scheduler `obtener_leads_para_seguimiento` y `obtener_leads_sin_cita` excluyen `noshow`.
- Si el cliente noshow vuelve a escribir → `crear_o_actualizar_lead` detecta `estado == "noshow"` y lo resetea a `activo` con contador en 0.

**Protección anti-doble envío en masivo**
- Si el scheduler automático ya envió un seguimiento en las últimas 12h, `obtener_leads_sin_cita` excluye al lead para que `masivo` no lo pise.
- Filtro: `seguimiento_enviado_en <= ahora - 12h` (o `NULL` si nunca se envió uno).

---

### Julio 10, 2026 (sesión 3) — Fix `stop:` no silenciaba seguimientos automáticos

**Bug crítico: números bloqueados con `stop:` seguían recibiendo seguimientos**
- Causa: `ejecutar_seguimientos()` y `ejecutar_retomas()` en `agent/followup.py` no consultaban la tabla `stopped_numbers`. El guard `numero_esta_stopped()` solo existía en `main.py` (mensajes entrantes). Las tareas del scheduler corrían su loop sin ningún filtro de stop.
- Resultado: un cliente al que se le aplicaba `stop:` dejaba de recibir respuestas del agente, pero seguía recibiendo los seguimientos automáticos cada 2h / 24h / 72h / 7d y las retomas nocturnas.
- Fix `agent/followup.py` (`ejecutar_seguimientos`):
  ```python
  from agent.memory import numero_esta_stopped
  if await numero_esta_stopped(lead.telefono):
      logger.info(f"[SEGUIMIENTO] Omitido — {lead.telefono} está STOPPED")
      continue
  ```
- Fix `agent/followup.py` (`ejecutar_retomas`): mismo check con log `[RETOMA] Omitida — STOPPED`.
- Los números ya bloqueados en la BD actúan de inmediato sin necesidad de volver a bloquearlos.
- El comando `masivo` ya tenía el check desde la sesión anterior (no necesitó cambio).

**Bug: git HEAD desconectado — Railway no desplegaba**
- Causa: HEAD estaba `detached from 812e121`. Los commits nuevos existían localmente pero no estaban en la rama `main`. Railway jalona `origin/main` → nunca detectaba cambios.
- Además: `.git/index.lock` y `.git/HEAD.lock` bloqueaban `git status` y `git add`.
- Fix (PowerShell):
  ```powershell
  Remove-Item ".git\index.lock" -Force -ErrorAction SilentlyContinue
  Remove-Item ".git\HEAD.lock" -Force -ErrorAction SilentlyContinue
  git branch -f main 7729d7d   # apuntar main al commit más reciente
  git checkout main
  git push origin main
  ```

---

## 5. REGLAS PARA NO ROMPER NADA

### Reglas de oro aprendidas de bugs pasados

1. **Stores de estado → SIEMPRE en BD** (`agent/memory.py`), nunca en dicts en memoria. Si el store es en RAM y el webhook no lo lee, el comando "funciona" pero el agente sigue respondiendo. Aplica a: `stop`, `pausa`, historial.

2. **Timestamps con PostgreSQL → `.replace(tzinfo=None)`** antes de insertar en columnas `TIMESTAMP WITHOUT TIME ZONE`.

3. **Confirmaciones al grupo → usar `chat_id_raw` (`...@g.us`)**, nunca el nombre del grupo ("Taller Interno TS"). Whapi rechaza el nombre.

4. **Multiplicadores del catálogo → NUNCA remover**. Precio sin multiplicador = pérdida económica directa. Verificar siempre que el precio resultante está en rango 500–10,000 MXN para displays comunes.

5. **Hugo Shop manda sobre Sheets**. Sheets solo complementa calidades que Hugo no tenga. Si Hugo tiene un precio y Sheets tiene otro para la misma calidad, se queda Hugo.

6. **`_parsear_chunk_descripcion` es recursiva (Fix Bug 3)**. Si el primer token es una marca (`ALIAS_MARCAS`), se stripea y se re-parsea el resto. No romper esta recursión.

7. **El motor de pricing intercepta ANTES de Claude**. Si `_intentar_respuesta_pricing_contextual()` retorna algo, Claude no se llama. Si retorna `None`, Claude toma el control.

8. **Para agregar soporte a un modelo nuevo**: solo agregarlo al CSV (`knowledge/hugo_shop.csv`) bajo la sección de su marca. El matching es automático.

9. **`stop:` debe silenciar TODAS las salidas**: el guard `numero_esta_stopped()` debe estar tanto en `main.py` (mensajes entrantes) como en `followup.py` (`ejecutar_seguimientos` y `ejecutar_retomas`). Si se agrega un nuevo punto de envío, añadir el check ahí también.

---

## 6. COMANDOS DE OPERACIÓN

### Deploy
```powershell
cd C:\Users\Elitebook\whatsapp-agentkit
git add agent/archivo_modificado.py
git commit -m "fix: descripción del cambio"
git push origin main
# Railway redeploya automático en ~2 min
```

### Test local sin WhatsApp (motor de precios)
```bash
python -c "
import asyncio, logging; logging.disable(logging.CRITICAL)
from agent.pricing_fallback import cotizar_con_fallback
async def main():
    print(await cotizar_con_fallback('samsung', 'a54', 'display'))
    print(await cotizar_con_fallback('', 's24 ultra', 'display'))   # Bug 1 fix
    print(await cotizar_con_fallback('zte', 'v41 smart', 'display'))  # Bug 2 fix
    print(await cotizar_con_fallback('poco', 'm5s', 'display'))       # Bug 3 fix
asyncio.run(main())
"
```

### Evals
```bash
python tests/eval/run_eval.py                         # 52 casos
python tests/eval/run_eval.py --solo m01-precio-display,m07-display-samsung
```

### Comandos del grupo interno — referencia rápida

| Comando | Qué hace |
|---|---|
| `masivo preview` | Lista leads sin cita que recibirían el masivo — **usar siempre antes de masivo** |
| `masivo` | Envía seguimiento personalizado a todos los leads sin cita confirmada |
| `noshow: NÚM` | Marca el cliente como noshow + envía cupón 10% — lo excluye del masivo/scheduler |
| `stop: NÚM` | Silencia permanentemente un número |
| `on: NÚM` | Reactiva un número silenciado |
| `stopped` | Lista todos los números silenciados actualmente |
| `pausa: NÚM` | Pausa el agente 2h con ese cliente (tú atiendes manualmente) |
| `reanudar: NÚM` | Reanuda el agente con ese cliente |
| `reporte` | Resumen del día (leads + CRM + pendientes) |
| `menu` | Muestra todos los comandos disponibles |

> Referencia completa → `COMANDOS.md`

### Variables de entorno en Railway (críticas)
| Variable | Descripción |
|---|---|
| `WHAPI_TOKEN` | Token Whapi.cloud |
| `ANTHROPIC_API_KEY` | API key de Claude |
| `GOOGLE_CREDENTIALS_JSON` | JSON de Service Account (Google) |
| `GOOGLE_CALENDAR_ID` | ID del calendario de citas |
| `GOOGLE_SHEET_ID` | ID del spreadsheet CRM |
| `GRUPO_CHRISTIAN_INTERNO` | chat_id del grupo interno (`...@g.us`) |
| `DATABASE_URL` | `${{ Postgres.DATABASE_URL }}` (Railway) |
| `ENVIRONMENT` | `production` |
| `ADMIN_TOKEN` | Token para `/admin/reload-catalogo` |
| `NUMERO_EXCEPCION_PRUEBAS` | Número que no respeta sleep mode |

---

## 7. ARCHIVOS .MD QUE PERMANECEN

| Archivo | Por qué se conserva |
|---|---|
| `ESTADO_PROYECTO.md` | Este archivo — consolidación completa |
| `CLAUDE.md` | Instrucciones del agente (NO TOCAR) |
| `AGENTS.md` | Config del sistema (NO TOCAR) |
| `README.md` | Presentación pública del repo |
| `README_ARQUITECTURA.md` | Referencia técnica de arquitectura |
| `COTIZADOR.md` | Referencia viva del motor de precios + recetas |
| `COMANDOS.md` | Referencia viva de comandos del grupo interno |
| `RUNBOOK_OPERACION_DIARIA.md` | Checklist diario + incidencias comunes |

---

*Consolidado el 27 de junio 2026. Archivos origen eliminados para evitar confusión.*
