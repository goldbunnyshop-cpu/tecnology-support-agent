# Integración de Smart Reminders (Recordatorios Inteligentes)
**Fecha**: 2026-05-17  
**Estado**: Listo para integrar

---

## 📋 Resumen

He creado un sistema de recordatorios inteligentes que:

✅ **Salta "24h antes"** si la cita está confirmada para mañana  
✅ **Envía "24h antes"** si la cita es en 2+ días  
✅ **Siempre envía "90 min antes"** (si su hora no pasó)  
✅ **Siempre envía "10 min antes"** (si su hora no pasó)  

### Archivos creados:

```
agent/smart_reminders.py        ← Lógica de timing (no depende de nada)
agent/reminder_scheduler.py     ← Programación en tiempo real (usa APScheduler)
requirements.txt                ← Agregado: apscheduler>=3.10.4
INTEGRACION_SMART_REMINDERS.md  ← Este archivo
```

---

## 🔧 Paso 1: Instalar dependencias

```bash
pip install -r requirements.txt
```

O solo APScheduler:

```bash
pip install apscheduler>=3.10.4
```

---

## 🔌 Paso 2: Integración en `agent/main.py`

Necesitas inicializar el scheduler en el lifespan del servidor FastAPI.

**Busca donde tienes esto en main.py:**

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup/shutdown del servidor."""
    # ... lo que ya tengas ...
    yield
```

**Reemplázalo con:**

```python
from agent.reminder_scheduler import inicializar_scheduler

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup/shutdown del servidor."""
    
    # Inicializar base de datos
    await inicializar_db()
    logger.info("Base de datos inicializada")
    
    # ✅ NUEVO: Inicializar scheduler de recordatorios
    await inicializar_scheduler(app)
    logger.info("Scheduler de recordatorios inicializado")
    
    logger.info(f"Servidor AgentKit corriendo en puerto {PORT}")
    logger.info(f"Proveedor de WhatsApp: {proveedor.__class__.__name__}")
    
    yield
    
    # Cleanup aquí si necesitas
```

---

## 🎯 Paso 3: Integración en `agent/cita_detector.py`

Cuando detectes que una cita fue **CONFIRMADA**, llama a `manejar_cita_confirmada`.

**Busca donde confirmas la cita** (probablemente una función como `procesar_confirmacion_cita`):

```python
# ANTES (lo que probablemente tienes):
if cita_confirmada:
    # agregar a google calendar
    # enviar confirmación al cliente
    pass

# DESPUÉS (nuevo flujo):
from agent.reminder_scheduler import manejar_cita_confirmada

if cita_confirmada:
    # 1. Agregar a Google Calendar (ya existe)
    await agregar_cita_a_calendar(...)
    
    # 2. ✅ NUEVO: Programar recordatorios inteligentes
    await manejar_cita_confirmada(
        telefono=numero_cliente,
        fecha_cita="2026-05-20",  # Formato YYYY-MM-DD
        hora_cita="15:00",         # Formato HH:MM
        nombre_cliente="Juan Pérez",
        proveedor_whatsapp=proveedor
    )
```

---

## 🧪 Paso 4: Prueba local

Crear un archivo `test_smart_reminders.py`:

```python
import asyncio
from datetime import datetime, timedelta
from agent.smart_reminders import ReminderSchedule

async def test_logica_recordatorios():
    """Prueba la lógica sin necesidad de proveedor real."""
    
    ahora = datetime.now()
    
    # TEST 1: Cita mañana
    print("\n" + "="*60)
    print("TEST 1: Cita mañana (confirma hoy)")
    print("="*60)
    manana = (ahora + timedelta(days=1)).strftime("%Y-%m-%d")
    s1 = ReminderSchedule(manana, "15:00", ahora)
    plan1 = s1.obtener_schedule_reminders()
    print(plan1["resumen"])
    
    # TEST 2: Cita en 2 días
    print("\n" + "="*60)
    print("TEST 2: Cita en 2 días (confirma hoy)")
    print("="*60)
    en_2_dias = (ahora + timedelta(days=2)).strftime("%Y-%m-%d")
    s2 = ReminderSchedule(en_2_dias, "10:00", ahora)
    plan2 = s2.obtener_schedule_reminders()
    print(plan2["resumen"])
    
    # TEST 3: Cita en 5 días
    print("\n" + "="*60)
    print("TEST 3: Cita en 5 días (confirma hoy)")
    print("="*60)
    en_5_dias = (ahora + timedelta(days=5)).strftime("%Y-%m-%d")
    s3 = ReminderSchedule(en_5_dias, "14:30", ahora)
    plan3 = s3.obtener_schedule_reminders()
    print(plan3["resumen"])

if __name__ == "__main__":
    asyncio.run(test_logica_recordatorios())
```

Ejecutar:

```bash
python test_smart_reminders.py
```

---

## 📊 Diagrama de flujo

```
Cliente confirma cita
         ↓
   cita_detector.py
   (detecta confirmación)
         ↓
manejar_cita_confirmada()
         ├─ Agregar a Google Calendar ✓
         ├─ Programar recordatorios inteligentes ← NUEVO
         │  ├─ Evalúa: ¿Mañana o después?
         │  ├─ Si mañana → saltea 24h, programa 90min + 10min
         │  ├─ Si después → programa 24h + 90min + 10min
         │  └─ Guarda en APScheduler (se ejecuta en background)
         └─ Enviar confirmación al cliente
                ↓
        (Espera 90 min - 10 min - etc)
                ↓
        APScheduler ejecuta reminders
        en tiempo real (background)
```

---

## 🎬 Ejemplo completo: Flujo de una cita

```
Domingo 15:00 → Cliente confirma cita para MARTES 15:00

ReminderSchedule calcula:
  • Tiempo hasta cita: 2 días
  • Cita en > 24h: SÍ

Recordatorios programados:
  ✅ 24h antes (Lunes 15:00): "Tienes una cita el 2026-05-21 a las 15:00"
  ✅ 90min antes (Martes 13:30): "Tu cita es en 90 minutos"
  ✅ 10min antes (Martes 14:50): "Tu cita es en 10 minutos"

---

Domingo 15:00 → Cliente confirma cita para LUNES 15:00

ReminderSchedule calcula:
  • Tiempo hasta cita: 1 día
  • Cita en < 24h: SÍ

Recordatorios programados:
  ⏭️ 24h antes: SALTADO (cita muy cercana)
  ✅ 90min antes (Lunes 13:30): "Tu cita es en 90 minutos"
  ✅ 10min antes (Lunes 14:50): "Tu cita es en 10 minutos"
```

---

## 🔧 Configuración (variables de entorno)

El scheduler usa zona horaria de **America/Mexico_City**. Si necesitas cambiar:

**En `agent/reminder_scheduler.py`, línea ~92:**

```python
scheduler.add_job(
    enviar_recordatorio,
    trigger=DateTrigger(run_date=dt_recordatorio),
    ...
    timezone="America/Mexico_City"  # ← CAMBIAR AQUÍ
)
```

Zonas soportadas: `America/New_York`, `Europe/London`, `Asia/Tokyo`, etc.

---

## 📝 Logs esperados

Cuando todo funcione, deberías ver en logs:

```
[INFO] Scheduler de recordatorios inicializado

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

[INFO] Enviando recordatorio 24h a +525-1234567
[INFO] Enviando recordatorio 90min a +525-1234567
[INFO] Enviando recordatorio 10min a +525-1234567
```

---

## ⚙️ Funciones disponibles

### `ReminderSchedule` (smart_reminders.py)

Uso directo (sin scheduler, solo lógica):

```python
from agent.smart_reminders import ReminderSchedule

schedule = ReminderSchedule(
    fecha_cita="2026-05-20",
    hora_cita="15:00"
)

plan = schedule.obtener_schedule_reminders()
print(plan["resumen"])
```

### `programar_recordatorios_cita()` (reminder_scheduler.py)

Programa en APScheduler:

```python
from agent.reminder_scheduler import programar_recordatorios_cita

resultado = await programar_recordatorios_cita(
    telefono="+525-1234567",
    fecha_cita="2026-05-20",
    hora_cita="15:00",
    nombre_cliente="Juan Pérez",
    callback_enviar_mensaje=proveedor.enviar_mensaje
)

if resultado["exito"]:
    print(f"✅ {resultado['detalle']}")
```

### `manejar_cita_confirmada()` (reminder_scheduler.py)

Función de alto nivel (la más fácil de usar):

```python
from agent.reminder_scheduler import manejar_cita_confirmada

await manejar_cita_confirmada(
    telefono="+525-1234567",
    fecha_cita="2026-05-20",
    hora_cita="15:00",
    nombre_cliente="Juan Pérez",
    proveedor_whatsapp=proveedor
)
```

### `cancelar_recordatorios_cita()` (reminder_scheduler.py)

Si el cliente cancela la cita:

```python
from agent.reminder_scheduler import cancelar_recordatorios_cita

resultado = await cancelar_recordatorios_cita(
    telefono="+525-1234567",
    fecha_cita="2026-05-20"
)

print(f"Cancelados {resultado['cancelados']} recordatorios")
```

---

## 🛠️ Troubleshooting

**Problema**: "ModuleNotFoundError: No module named 'apscheduler'"  
**Solución**: `pip install apscheduler`

**Problema**: Recordatorios no se envían  
**Verificar**:
1. ¿El scheduler está inicializado en main.py? (revisar logs)
2. ¿La función `callback_enviar_mensaje` es async? (debe serlo)
3. ¿El teléfono tiene formato correcto? (ej: "+525-1234567")

**Problema**: Recordatorios se envían a hora equivocada  
**Verificar**: Zona horaria en reminder_scheduler.py línea 92

---

## 📊 Base de datos (opcional)

Para persistencia, podrías guardar los recordatorios programados en BD:

```python
class CitaReminder(Base):
    __tablename__ = "cita_reminders"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    telefono: Mapped[str] = mapped_column(String(50))
    fecha_cita: Mapped[str] = mapped_column(String(10))
    hora_cita: Mapped[str] = mapped_column(String(5))
    tipo: Mapped[str] = mapped_column(String(20))  # "24h", "90min", "10min"
    datetime_recordatorio: Mapped[datetime] = mapped_column(DateTime)
    enviado: Mapped[bool] = mapped_column(Boolean, default=False)
    creado: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
```

(Esto es OPCIONAL, APScheduler almacena en memoria durante la ejecución)

---

## ✅ Checklist de integración

- [ ] `pip install -r requirements.txt` ejecutado
- [ ] `agent/smart_reminders.py` existe
- [ ] `agent/reminder_scheduler.py` existe
- [ ] `agent/main.py` → añadido init scheduler en lifespan
- [ ] `agent/cita_detector.py` → llamadas a `manejar_cita_confirmada()`
- [ ] Prueba local: `python test_smart_reminders.py` ✓
- [ ] Servidor inicia sin errores
- [ ] Logs muestran "Scheduler de recordatorios inicializado"

---

## 📞 Próximos pasos

1. **Integra** estos cambios en tu código existente
2. **Prueba** localmente con `test_smart_reminders.py`
3. **Deploy** a Railway (actualizar requirements.txt primero)
4. **Monitorea** los logs para ver los recordatorios siendo programados y enviados

¿Preguntas sobre la integración?
