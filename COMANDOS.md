# Comandos del grupo interno — Arquitectura, fixes y guía

> Documento vivo de los **comandos del grupo "Taller Interno TS"** (notificaciones,
> CRM, control de números, pausas, cupones).
> Última actualización: **2026-06-05**.
> Sirve para entender cómo funcionan, qué se reparó y cómo extenderlos sin romperlos.

---

## 1. Cómo llega y se procesa un comando

```
Operador escribe en el grupo "Taller Interno TS" (WhatsApp)
   ▼
agent/main.py  _procesar_lote_mensajes()  (msg.es_grupo == True)
   ├─ 1º procesar_comando_control()  → stop / on / stopped   (agent/commands_control.py)
   │      └─ si es comando de control: responde al chat_id del grupo y termina
   └─ 2º procesar_comando_grupo()    → todos los demás comandos (agent/commands.py)
```

**Regla de oro aprendida (la causa de casi todos los bugs de esta familia):**
> El **webhook entrante** (main.py) decide si responde a un cliente leyendo la **BD**
> (tablas `stopped_numbers` y `pausas` en `agent/memory.py`). Cualquier comando que
> "detenga" o "pause" DEBE escribir en esa BD. Los stores **en memoria** (dicts en
> singletons) NO los lee nadie en el webhook → el comando parece funcionar (responde
> "✅ hecho") pero el agente sigue contestando.

---

## 2. Catálogo de comandos

Escribe `menu` en el grupo para ver la lista en vivo. Resumen:

| Comando | Formato | Qué hace | Store / dependencia |
|---------|---------|----------|---------------------|
| `listo` | `listo: NÚM EQUIPO` | Avisa equipo listo | Whapi |
| `demora` | `demora: NÚM TIEMPO EQUIPO` | Avisa más tiempo | Whapi |
| `diagnostico` | `diagnostico: NÚM EQUIPO DESC` | Informa diagnóstico | Whapi |
| `presupuesto` | `presupuesto: NÚM EQUIPO PRECIO` | Envía presupuesto | Whapi |
| `clabe` | `clabe: NÚM` | Envía CLABE (`.env CLABE_CUENTA`) | Whapi |
| `pago` | `pago: NÚM MONTO` | Opciones de pago | Whapi |
| `password` / `llamar` / `cita` | `cmd: NÚM` | Mensajes fijos | Whapi |
| `pausa` | `pausa: NÚM` | Pausa el agente 2 h con ese cliente | **BD `pausas`** |
| `reanudar` | `reanudar: NÚM` | Reactiva al agente con ese cliente | **BD `pausas`** |
| `reanudar todo` | (texto exacto) | Limpia TODAS las pausas | **BD `pausas`** |
| `nota` | `nota: FOLIO NÚM EQUIPO [MODELO] FALLA TOTAL PAGO [refaccion:COSTO]` | Registra orden CRM | Google Sheets (CRM) |
| `orden` | `orden: NÚM EQUIPO TOTAL PAGO [REFACCIÓN]` | Orden CRM folio auto | Google Sheets (CRM) |
| `estatus` | `estatus: FOLIO recibido\|proceso\|listo\|entregado` | Cambia estatus | Google Sheets (CRM) |
| `consultar` | `consultar: FOLIO` | Muestra una orden | Google Sheets (CRM) |
| `stop` | `stop: NÚM` | Detiene al agente con ese cliente (silencio total) | **BD `stopped_numbers`** |
| `on` / `unblock` | `on: NÚM` / `unblock: NÚM` | Reactiva (quita el stop) | **BD `stopped_numbers`** |
| `stopped` | (texto exacto) | Lista números detenidos | **BD `stopped_numbers`** |
| `2nd` | `2nd: NÚM` | 2º seguimiento + cupón 15 % | Claude (API) + Sheets cupones |
| `noshow` | `noshow: NÚM` | Reconexión no-show + cupón 10 % | Claude (API) + Sheets cupones |
| `reporte` / `pendientes` | (texto) | Resúmenes | Leads/CRM |

> `stop` vs `pausa`: **stop** es permanente (hasta `on`/`unblock`); **pausa** es temporal (2 h).

---

## 3. Bugs reparados (2026-06-05) y por qué

### 3.1 `stop` no detenía la conversación
Había **dos sistemas de bloqueo**: un dict en memoria en `commands.py` (`_NUMEROS_BLOQUEADOS`,
que NADIE lee en el webhook) y la tabla `stopped_numbers` en BD (la que sí lee
`main.py` vía `validar_numero_activo` → `numero_esta_stopped`).
**Fix:** `stop`/`unblock` ahora llaman a `agent.memory.detener_numero` /
`reactivar_numero` (BD) y extraen el número con `re.sub(r"\D","",payload)` (tolera
espacios/guiones). `_variantes_telefono` cruza 10↔13 dígitos en ambos lados.

### 3.2 `2nd` / `noshow` mandaban error
Llamaban a `crm.registrar_cupon`, `crm.crear_hoja_cupones` y
`brain.generar_mensaje_noshow` que **no existían** → AttributeError/ImportError.
**Fix:** creadas. Las de cupones (`crm.py`) escriben en una hoja "Cupones" de Sheets y
son **resilientes** (si no hay `GOOGLE_SHEET_ID`, loguean y siguen — no truenan).
`generar_mensaje_noshow` (`brain.py`) es un wrapper de `generar_respuesta`.
**Requieren créditos de API de Anthropic** para generar el mensaje.

### 3.3 Confirmación de `stop`/`on` al grupo fallaba (Whapi 400)
`main.py` respondía al **nombre** del grupo (`"Taller Interno TS"`) en vez de al
**chat_id** (`...@g.us`). Whapi rechaza el nombre.
**Fix:** responde a `getattr(msg, "chat_id_raw", ...)`.

### 3.4 `pausa` se "saltaba" antes de los 120 min / re-pausar no renovaba
Dos desincronizaciones memoria↔BD en `pausa_manager.py`:
- `procesar_pausa` hacía `return "ya pausado"` por un **dict en memoria**
  (`pausas_activas`) que nunca expira **sin renovar la BD**.
- `reanudar_pausa` tenía **comentada** la llamada a la BD → `reanudar` solo borraba
  memoria; el agente seguía pausado hasta expirar.
- Agravado porque la BD era **efímera** (SQLite) y un redeploy borraba las pausas.
**Fix:** `procesar_pausa` consulta `esta_pausada` (BD) y **siempre** renueva con
`pausar_conversacion`; `reanudar_pausa` llama a `reanudar_conversacion` (BD). Además
la BD ahora es **PostgreSQL** (persistente, ver §4).

### 3.5 Menú incompleto
Faltaban `on:` y `stopped` (existían y funcionaban, no estaban listados). **Agregados.**

---

## 4. Persistencia: PostgreSQL (crítico)

`stop`, `pausa`, historial de conversaciones, dedup, citas → todo vive en la BD
(`agent/memory.py`). En Railway la BD debe ser **PostgreSQL** (servicio Postgres +
variable `DATABASE_URL = ${{ Postgres.DATABASE_URL }}`). Si se usa SQLite sin volumen,
los datos se **borran en cada redeploy** y los `stop`/`pausa` "se olvidan".

`agent/memory.py` detecta el dialecto solo:
- Con `DATABASE_URL` de Postgres → usa Postgres (convierte `postgres://` a `+asyncpg`).
- DDL dialect-aware: la tabla `citas` usa `SERIAL`/`TIMESTAMP` en Postgres y
  `AUTOINCREMENT`/`DATETIME` en SQLite (¡`AUTOINCREMENT` NO existe en Postgres!).
- Migraciones (`ALTER TABLE ADD COLUMN`) corren **una transacción por columna**: en
  Postgres un ALTER que falla aborta toda la transacción, así que hay que aislarlos.

---

## 5. Archivos

| Archivo | Rol |
|---------|-----|
| `agent/commands.py` | Comandos generales del grupo + texto del menú (`TEXTO_MENU`). |
| `agent/commands_control.py` | `stop` / `on` / `stopped` (patrones estrictos de solo dígitos). |
| `agent/pausa_manager.py` | Lógica de `pausa` / `reanudar` (delega a la BD). |
| `agent/memory.py` | Tablas y funciones de BD: `detener_numero`, `numero_esta_stopped`, `pausar_conversacion`, `esta_pausada`, `reanudar_conversacion`, `_variantes_telefono`. |
| `agent/crm.py` | CRM en Sheets + cupones (`registrar_cupon`, `crear_hoja_cupones`). |
| `agent/main.py` | Webhook: enruta comandos del grupo y aplica los guards de stop/pausa. |

---

## 6. Cómo depurar comandos (sin WhatsApp)

```bash
# Detección + parseo de todos los comandos
python -c "
from agent.commands import parsear_comando, parsear_listo, parsear_nota
print(parsear_comando('stop: 5541576331'))
print(parsear_nota('13054 5541576331 iPhone 13 pantalla 1200 tarjeta refaccion:500'))
"

# Flujo stop / pausa contra la BD (usa SQLite local)
python -c "
import asyncio, logging; logging.disable(logging.CRITICAL)
from agent.memory import inicializar_db, detener_numero, numero_esta_stopped, esta_pausada
from agent.pausa_manager import obtener_pausa_manager
async def main():
    await inicializar_db()
    await detener_numero('5215541576331')
    print('stopped:', await numero_esta_stopped('5541576331'))   # True (variantes)
    mgr = await obtener_pausa_manager()
    await mgr.procesar_pausa('5215599887766', duracion_horas=2)
    print('pausada:', await esta_pausada('5599887766'))          # True
asyncio.run(main())
"
```

**Síntoma → primer sospechoso:**
- "El comando dice OK pero el agente sigue respondiendo" → store en memoria vs BD
  (revisa que el handler escriba en `agent.memory`, no en un dict del singleton).
- "Funciona y al rato se olvida" → BD efímera (falta PostgreSQL, ver §4).
- "Whapi 400 al confirmar en el grupo" → se está respondiendo al nombre del grupo en
  vez del `chat_id` (`...@g.us`).
- "`2nd`/`noshow` dan error" → falta de créditos de API o `GOOGLE_SHEET_ID` (el
  mensaje igual se envía aunque el cupón no se registre).

---

## 7. Cómo agregar un comando nuevo

1. Agrégalo a `COMANDOS_VALIDOS` y documéntalo en `TEXTO_MENU` (`agent/commands.py`).
2. Si lleva payload, escribe un `parsear_<cmd>()`.
3. Añade el bloque `if cmd == "<cmd>":` en `procesar_comando_grupo`.
4. Si "detiene"/"pausa"/persiste algo, **escribe en la BD** (`agent/memory.py`), nunca
   solo en memoria.
5. Responde con `_responder(...)` (usa el `chat_id_raw` del grupo, no su nombre).
