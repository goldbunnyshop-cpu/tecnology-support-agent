# Bitacora de Cambios - 2026-05-28

Este documento resume los cambios realizados en esta sesion para dejar el agente funcional en local y en Railway.

## 1) Objetivo de la sesion
- Revisar el proyecto completo antes de mejoras.
- Corregir errores criticos de ejecucion.
- Desplegar en Railway y validar endpoints/webhook.
- Ajustar comportamiento operativo (sleep mode, retoma, excepcion de pruebas).

## 2) Cambios de codigo aplicados

### 2.1 Factory de proveedores robusto
Archivo: `agent/providers/__init__.py`

Se amplio la seleccion de proveedor por `WHATSAPP_PROVIDER`:
- `whapi` -> `ProveedorWhapi`
- `messenger` -> `ProveedorMessenger`
- `meta_inbox` o `meta` -> `ProveedorMetaInbox`

Impacto:
- Evita caidas por `ValueError` cuando se usa otro proveedor distinto a `whapi`.

### 2.2 Compatibilidad de modelo de mensaje de entrada
Archivo: `agent/providers/base.py`

Se agrego el campo:
- `canal: str = "whatsapp"`

Impacto:
- Evita incompatibilidad con proveedores que ya enviaban `canal` (ej. meta inbox/messenger).

### 2.3 Correccion de envio en scheduler de citas
Archivo: `agent/main.py`

Se corrigio llamada incompatible de `enviar_mensaje(...)` que usaba kwargs no soportados (`numero`, `texto`, `grupo_id`).
Ahora usa firma consistente:
- `await proveedor.enviar_mensaje(destino, reporte)`

Impacto:
- El envio programado de reporte de citas deja de fallar por firma incorrecta.

### 2.4 Excepcion para numero de pruebas
Archivo: `agent/main.py`

Se agrego variable:
- `NUMERO_EXCEPCION_PRUEBAS` (default `5627557362`)

Y se aplico para saltar:
- bloqueo por pausa manual
- sleep mode nocturno

Impacto:
- Permite pruebas en horario nocturno sin bloquear al numero definido.

### 2.5 Ajuste de retoma nocturna
Archivo: `agent/main.py`

Cambio de logica:
- Antes: `+8h` con piso de 9:00 AM
- Ahora: `+7h` con piso de `06:30 AM` (regla hibrida `max(+7h, 06:30)`)

Impacto:
- Se alinea a operacion solicitada.

### 2.6 Mensajes operativos en configuracion
Archivo: `config/prompts.yaml`

Se agrego bloque:
- `mensajes_operativos.sleep_mode`
- `mensajes_operativos.reactivacion`
- `mensajes_operativos.resumen_9am`

Nota:
- Ya estan documentados en config para futura edicion sin tocar logica.

## 3) Validaciones realizadas

### 3.1 Local
- `python -m compileall agent` -> OK
- `import agent.main` -> OK
- Levante de Uvicorn local -> OK
- Endpoints verificados:
  - `GET /` -> 200
  - `GET /webhook` -> 200
  - `GET /diagnostico/grupos` -> 200 (grupo detectado)

### 3.2 Git y despliegue
- Commit aplicado y push a `main`:
  - `5951e6d fix: provider factory and scheduler send compatibility`
- Railway levanta aplicacion correctamente y webhook publico accesible.

## 4) Hallazgos en logs de Railway (lo "raro")

### 4.1 `/data` a veces aparece `exists=False`
Esto puede pasar al inicio de un contenedor antes de montar el volumen o en reinicios parciales.
Luego en otro arranque se observa `exists=True` y uso de SQLite persistente, lo cual indica que el volumen SI esta montado cuando todo inicia correctamente.

### 4.2 Mucho `DEBUG:aiosqlite`
Es ruido de log, no error fatal.
Causa probable:
- nivel de log en `DEBUG` por `ENVIRONMENT` no tomado como `production` o configuracion de logger global.

Recomendacion:
- Verificar variable `ENVIRONMENT=production` en Railway.
- Si persiste, forzar nivel de librerias:
  - `logging.getLogger("aiosqlite").setLevel(logging.WARNING)`
  - `logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)`

### 4.3 Warning de Google Calendar
Log reportado:
- `GOOGLE_CREDENTIALS no configurado en Railway`

Interpretacion:
- El scheduler intenta leer calendario y no encuentra credenciales utiles en runtime.

Recomendacion:
- Confirmar variable exacta consumida por el modulo (`GOOGLE_CREDENTIALS` o `GOOGLE_CREDENTIALS_JSON`).
- Validar formato JSON valido y sin comillas rotas.
- Si no se usara Calendar temporalmente, desactivar esas tareas para evitar ruido.

## 5) Estado actual
- Webhook operativo.
- Proveedor Whapi operativo.
- Base funcional para produccion.
- Ajustes de sleep/retoma/excepcion aplicados.

## 6) Pendientes recomendados (siguiente iteracion)
1. Limpiar logging de produccion (reducir DEBUG ruidoso).
2. Corregir o desactivar integracion Google Calendar segun decision operativa.
3. Corregir textos con mojibake en archivos historicos/cadena de prompts (mejora UX).
4. Consolidar migraciones para evitar warnings de "duplicate column" repetitivos en arranque.

## 7) Variables clave (referencia rapida)
- `WHATSAPP_PROVIDER=whapi`
- `WHAPI_TOKEN=...`
- `ANTHROPIC_API_KEY=...`
- `ENVIRONMENT=production`
- `NUMERO_EXCEPCION_PRUEBAS=5627557362`
- `GRUPO_CHRISTIAN_INTERNO=120363423715417410@g.us`

---
Actualizado por Codex: 2026-05-28

## 8) Ajustes adicionales (Google Calendar + Logs)

Fecha: 2026-05-28 (segunda iteracion)

### 8.1 Compatibilidad de variables de Google Calendar en runtime
Archivo: `agent/google_calendar.py`

Se corrigio lectura de variables para que coincida con Railway:
- `GOOGLE_CALENDAR_ID` (prioritario) y fallback a `CALENDAR_ID`
- Credenciales: ahora acepta en orden:
  - `GOOGLE_CREDENTIALS`
  - `GOOGLE_CREDENTIALS_JSON`
  - `GOOGLE_SERVICE_ACCOUNT_JSON`

Impacto:
- El warning `GOOGLE_CREDENTIALS no configurado` desaparece cuando ya existe
  `GOOGLE_CREDENTIALS_JSON` en Railway.
- El calendario usado se alinea con `GOOGLE_CALENDAR_ID`.

### 8.2 Reduccion de ruido de logs en produccion
Archivo: `agent/main.py`

Se agrego ajuste de niveles en entorno no desarrollo:
- `aiosqlite` -> `WARNING`
- `sqlalchemy.engine` -> `WARNING`
- `httpx` -> `WARNING`

Impacto:
- Logs mas limpios para operacion diaria y monitoreo.
