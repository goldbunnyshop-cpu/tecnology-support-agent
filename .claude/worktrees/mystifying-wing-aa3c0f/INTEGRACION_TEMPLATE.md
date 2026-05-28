# Template de Integración — Smart Reminders

Usa este documento para integrar exactamente qué código cambiar en tus archivos existentes.

---

## 1️⃣ Actualizar `agent/main.py`

### BUSCA esta sección (lifespan):

```python
from contextlib import asynccontextmanager
from fastapi import FastAPI

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Inicialización
    await inicializar_db()
    logger.info("Base de datos inicializada")
    
    # ... resto del código ...
    
    yield
    
    # Cleanup si necesitas
```

### REEMPLAZA CON:

```python
from contextlib import asynccontextmanager
from fastapi import FastAPI
from agent.reminder_scheduler import inicializar_scheduler  # ← AGREGAR IMPORT

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Inicialización
    await inicializar_db()
    logger.info("Base de datos inicializada")
    
    # ✅ NUEVO: Inicializar scheduler de recordatorios
    await inicializar_scheduler(app)
    logger.info("Scheduler de recordatorios inicializado")
    
    # ... resto del código que ya tengas ...
    
    yield
    
    # Cleanup si necesitas
```

---

## 2️⃣ Actualizar `agent/cita_detector.py`

### BUSCA donde confirmas la cita:

```python
# Ejemplo de lo que probablemente tienes:
def procesar_confirmacion_cita(numero, fecha, hora, nombre):
    # ... detectar que cliente confirmó ...
    
    if cliente_confirmo:
        # Agrega cita a Google Calendar
        await agregar_cita_a_calendar(
            nombre_cliente=nombre,
            dispositivo="...",
            problema="...",
            fecha_str=fecha,
            hora_str=hora,
            asesor="agente"
        )
        
        # Envía confirmación al cliente
        await proveedor.enviar_mensaje(numero, "✅ Cita confirmada!")
```

### REEMPLAZA CON:

```python
from agent.reminder_scheduler import manejar_cita_confirmada  # ← AGREGAR IMPORT

async def procesar_confirmacion_cita(numero, fecha, hora, nombre):
    # ... detectar que cliente confirmó ...
    
    if cliente_confirmo:
        # ✅ Nuevo flujo de 3 pasos:
        
        # 1. Agregar a Google Calendar
        try:
            await agregar_cita_a_calendar(
                nombre_cliente=nombre,
                dispositivo="...",
                problema="...",
                fecha_str=fecha,
                hora_str=hora,
                asesor="agente"
            )
        except Exception as e:
            logger.warning(f"Error en Google Calendar: {e}")
        
        # 2. ✅ NUEVO: Programar recordatorios inteligentes
        await manejar_cita_confirmada(
            telefono=numero,           # Número del cliente
            fecha_cita=fecha,          # Formato YYYY-MM-DD
            hora_cita=hora,            # Formato HH:MM
            nombre_cliente=nombre,
            proveedor_whatsapp=proveedor
        )
        
        # 3. Confirmación será enviada por manejar_cita_confirmada()
        # No necesitas enviar manual, ya está incluido
```

**Eso es todo.** `manejar_cita_confirmada()` hace el resto:
- ✅ Envía confirmación al cliente
- ✅ Programa 24h (si aplica)
- ✅ Programa 90min
- ✅ Programa 10min

---

## 3️⃣ Actualizar `requirements.txt`

Solo verifica que APScheduler esté. Ya lo agregué, pero confirma:

```txt
...
apscheduler>=3.10.4
```

Si no está, agrégalo al final.

---

## 4️⃣ Instalar y Probar

```bash
# Instalar
pip install -r requirements.txt

# Test rápido (valida lógica)
python test_smart_reminders.py

# Iniciar servidor
uvicorn agent.main:app --reload --port 8000

# En otro terminal - cliente de prueba
python test_google_calendar.py  # o tu script de test
```

---

## 5️⃣ Verificar en Logs

Cuando arranca, deberías ver:

```
[INFO] Base de datos inicializada
[INFO] Scheduler de recordatorios inicializado
[INFO] Servidor AgentKit corriendo en puerto 8000
```

Cuando se confirma una cita:

```
[INFO] Plan para +525-1234567:
  📅 Cita: 2026-05-20 a las 15:00
  ⏱️ Tiempo hasta cita: 2 days, 5:00:00
  📢 Recordatorios:
    • 24h: ✅ ENVIAR
    • 90min: ✅ ENVIAR
    • 10min: ✅ ENVIAR

[INFO] [Juan Pérez] Recordatorio 24h programado para 2026-05-19 15:00:00
[INFO] [Juan Pérez] Recordatorio 90min programado para 2026-05-20 13:30:00
[INFO] [Juan Pérez] Recordatorio 10min programado para 2026-05-20 14:50:00
```

---

## 🎯 Resumen rápido

| Archivo | Cambio | Líneas |
|---------|--------|--------|
| `agent/main.py` | Agregar import + init scheduler en lifespan | ~5 líneas |
| `agent/cita_detector.py` | Agregar import + llamar `manejar_cita_confirmada()` | ~10 líneas |
| `requirements.txt` | Verificar `apscheduler>=3.10.4` | 0 (ya agregado) |

**Total de cambios**: ~15 líneas de código nuevo.

---

## 🆘 Si falla

**Error: "ModuleNotFoundError: No module named 'apscheduler'"**
```bash
pip install apscheduler
```

**Error: "Scheduler not initialized"**
→ Verificar que `inicializar_scheduler()` fue llamado en `lifespan`

**Recordatorios no se envían**
→ Revisar logs, buscar "programado para" para confirmar que se programaron
→ Verificar zona horaria (America/Mexico_City)

---

Done. Los archivos están listos. Solo integra estos cambios en tus archivos existentes.
