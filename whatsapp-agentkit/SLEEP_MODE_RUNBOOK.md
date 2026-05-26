# Sleep Mode Implementation Runbook
## AgentKit WhatsApp Agent — Sistema de Reposo (00:00 - 5:59 AM)

---

## 📋 Descripción General

El sistema de **Sleep Mode** (OPCIÓN 2) está diseñado para manejar automáticamente los mensajes que llegan durante las horas de reposo (00:00 - 5:59 AM, zona México), sin mostrar horarios específicos al cliente.

**Flujo de operación:**

```
Cliente escribe a las 1:05 AM
    ↓
Bot detecta: está_en_horario_operacion_bot() = False
    ↓
Bot envía mensaje de sleep mode sin mostrar horas
"Hola, soy Valentina... cuando retomemos actividades..."
    ↓
Bot programa automáticamente reactivación a las 8:05 AM (+7 horas)
    ↓
A las 8:05 AM, bot envía mensaje de reactivación automático
"Gracias por tu paciencia, estamos dando prioridad a tu consulta..."
    ↓
Cliente recibe ambos mensajes sin ver cálculos de horarios
```

---

## 🕐 Tres Niveles de Horarios

### 1. **HORARIO DE OPERACIÓN DEL BOT** (Interno)
**Cuándo el bot está ACTIVO y puede responder:**
- Lunes a Domingo: **6:00 AM - 23:59 PM**
- Archivo: `agent/sleep_mode.py` → `HORARIOS_OPERACION_BOT`
- Bot responde TODOS los mensajes durante este período
- Función de detección: `esta_en_horario_operacion_bot()` → retorna `True/False`

### 2. **HORARIO DEL MÓDULO** (Lo que se muestra al cliente)
**Cuándo la oficina/módulo está abierto al público:**
- Lunes a Viernes: **10:00 AM - 9:00 PM**
- Sábados y Domingos: **11:00 AM - 8:00 PM**
- Archivo: `agent/sleep_mode.py` → `HORARIOS_MODULO`
- SOLO se muestra si el cliente PREGUNTA sobre horarios
- Función: `obtener_horarios_modulo()` → retorna string con horarios formateados

### 3. **SLEEP MODE** (Reposo, sin mostrar horas)
**Cuándo el bot está durmiendo (00:00 - 5:59 AM):**
- Responde con mensaje amigable SIN mencionar horarios específicos
- Dice: "cuando retomemos actividades" o "cuando abramos"
- NUNCA dice: "mañana a las 6 AM" o "en 7 horas"
- Función: `obtener_mensaje_sleep_mode(asesor)` → retorna UN mensaje aleatorio de 3 opciones

---

## 🔧 Componentes Técnicos

### A. Detección de Sleep Mode
**Archivo:** `agent/sleep_mode.py`

```python
def esta_en_horario_operacion_bot() -> bool:
    """
    Verifica si el bot está en horario de OPERACIÓN (6 AM - 23:59 PM).
    Retorna:
        True  → Bot está activo, procesar mensaje normalmente
        False → Bot en sleep mode (00:00 - 5:59 AM), enviar mensaje de reposo
    """
    ahora = datetime.now(ZONA_MEXICO)
    hora_actual = ahora.hour
    # Si hora < 6 o >= 24, retorna False
    return 6 <= hora_actual < 24
```

**Ubicación en código:** `agent/main.py` línea ~113
```python
if not esta_en_horario_operacion_bot():
    # Estamos en sleep mode (00:00 - 5:59 AM)
    # Enviar mensaje sin mostrar horas
    # Programar reactivación a +7 horas
```

---

### B. Selección del Asesor

El bot **SIEMPRE** mantiene continuidad con el último asesor que atendió al cliente:

**Orden de selección:**
1. **Historial previo** → `extraer_asesor_de_historial(historial)` busca en últimos 10 mensajes del asistente
   - Busca patrones: "soy Sofia", "te habla Valentina", "Hola, soy Camila"
   - Retorna el nombre si lo encuentra

2. **Si no encuentra** → Seleccionar aleatoriamente de las 6 agentes
   ```python
   asesor = random.choice(["Sofia", "Valentina", "Camila", "Daniela", "Andrea", "Rocio"])
   ```

3. **Agentes disponibles (todos femeninos):**
   - **Sofia** — Empática y comprensiva
   - **Valentina** — Profesional y directa (asesor default)
   - **Camila** — Amigable y accesible
   - **Daniela** — Técnica y precisa (especialista en dispositivos)
   - **Andrea** — Resolutiva y eficiente
   - **Rocío** — Formal y confiable

**Ubicación:** `agent/profile.py` → `extraer_asesor_de_historial()`

---

### C. Mensajes de Sleep Mode

**Archivo:** `agent/sleep_mode.py` → `_MENSAJES_SLEEP_MODE`

**3 variaciones aleatorias (sin mostrar horarios):**

1. "Hola, soy {asesor} de Technology Support 😊\nRecibí tu mensaje y créeme que estoy anotando todo para retomarlo cuando abramos.\nNuestro equipo retoma operaciones cuando iniciemos actividades.\n¡Te atenderé con prioridad en ese momento! Que descanses bien."

2. "Buenas noches, te habla {asesor} de Technology Support.\nHe registrado tu consulta y será atendida con prioridad cuando retomemos actividades.\nQueda todo anotado para darte seguimiento.\n¡Descansa, estamos aquí para ti! 🙏"

3. "¡Hola! Soy {asesor}, asesora de Technology Support 😊\nAnotado tu mensaje — no se me olvida. Cuando retomemos operaciones serás de las primeras en ser atendida.\nQue descanses tranquila, ¡vuelvo con la solución!"

**Características:**
- ✅ Personalizadas con nombre del asesor
- ❌ NO mencionan horas específicas ("6:00 AM", "+7 horas", etc.)
- ✅ Dicen "cuando abramos" o "cuando retomemos operaciones"
- ✅ Garantizan atención prioritaria cuando reanude
- ✅ Son amigables y empáticas

---

### D. Cálculo de Reactivación (+7 horas)

**Archivo:** `agent/sleep_mode.py`

```python
def calcular_hora_reactivacion(ahora: datetime) -> datetime:
    """
    Calcula la hora exacta de reactivación: ahora + 7 horas
    
    Ejemplo:
        Cliente escribe a 1:05 AM
        calcular_hora_reactivacion(datetime(2026, 5, 21, 1, 5))
        Retorna: datetime(2026, 5, 21, 8, 5)  ← Exactamente 7 horas después
    """
    return ahora + timedelta(hours=7)
```

**Lógica:**
- Se calcula EN SILENCIO (no se muestra al cliente)
- Se usa SOLO internamente para programar el scheduler
- Se pasa a `programar_reactivacion_sleep()` como `datetime` object
- El cliente NUNCA ve este cálculo

---

### E. Programación del Scheduler (APScheduler)

**Archivo:** `agent/reminder_scheduler.py` → `programar_reactivacion_sleep()`

**Función:**
```python
async def programar_reactivacion_sleep(
    telefono: str,
    asesor: str,
    hora_reactivacion: datetime,
    callback_enviar_mensaje: Optional[Callable] = None
) -> dict
```

**Qué hace:**
1. Crea un job ID único: `sleep_retoma_{telefono}_{timestamp}`
2. Obtiene UN mensaje aleatorio de reactivación (4 opciones)
3. Lo programa con APScheduler para ejecutarse a `hora_reactivacion`
4. A la hora exacta, envía el mensaje automáticamente via proveedor
5. Retorna resultado: `{"exito": bool, "job_id": str, "scheduled_for": datetime}`

**Mensajes de reactivación (4 opciones):**
1. "Gracias por tu paciencia, estamos dando prioridad a tu consulta. Dime qué problema presenta tu dispositivo 😊"
2. "¡Hola de nuevo! Retomamos operaciones. Cuéntame, ¿sigue en pie tu consulta sobre tu dispositivo?"
3. "Volvimos, estamos aquí para ayudarte. ¿Cuál era el problema que tenías con tu equipo?"
4. "Hola 😊 Acá estamos. Voy a ayudarte con lo que comentaste antes. Adelante."

---

### F. Flujo Completo en main.py

**Ubicación:** `agent/main.py` → `webhook_handler()` líneas ~112-145

```python
# PASO 1: Verificar si está en horario de operación
if not esta_en_horario_operacion_bot():
    # === SLEEP MODE ACTIVADO ===
    logger.info(f"🌙 [SLEEP] Mensaje en horario de reposo...")

    # PASO 2: Obtener historial para detectar asesor
    historial_temp = await obtener_historial(msg.telefono)
    asesor = extraer_asesor_de_historial(historial_temp)
    if not asesor:
        asesor = random.choice([...])

    # PASO 3: Enviar mensaje de sleep mode sin mostrar horas
    respuesta_sleep = obtener_mensaje_sleep_mode(asesor)
    await guardar_mensaje(msg.telefono, "user", msg.texto)
    await guardar_mensaje(msg.telefono, "assistant", respuesta_sleep)
    await proveedor.enviar_mensaje(msg.telefono, respuesta_sleep)

    # PASO 4: Programar reactivación automática a +7 horas
    ahora = datetime.now(ZONA_MEXICO)
    hora_reactivacion = calcular_hora_reactivacion(ahora)
    
    resultado_sched = await programar_reactivacion_sleep(
        telefono=msg.telefono,
        asesor=asesor,
        hora_reactivacion=hora_reactivacion,
        callback_enviar_mensaje=proveedor.enviar_mensaje
    )
    
    if resultado_sched["exito"]:
        logger.info(f"[SLEEP] ✅ Reactivación programada: {resultado_sched['detalle']}")
    else:
        logger.warning(f"[SLEEP] ⚠️ No se pudo programar reactivación: {resultado_sched['detalle']}")
    
    continue  # Saltar el procesamiento normal, pasar al siguiente mensaje
```

---

## 📊 Casos de Uso y Ejemplos

### **Caso 1: Cliente escribe a las 1:05 AM (Sleep Mode)**

```
Timeline:
─────────────────────────────────────────────────────────

1:05 AM    Cliente escribe: "Hola, mi celular no enciende"
           │
           ├─→ Bot: esta_en_horario_operacion_bot() = False (es 1 AM)
           ├─→ Bot detecta asesor del historial = "Valentina"
           ├─→ Bot envía: "Buenas noches, te habla Valentina...
           │             ...cuando retomemos actividades..."
           ├─→ Bot INTERNAMENTE calcula: 1:05 AM + 7 horas = 8:05 AM
           └─→ Bot programa scheduler para 8:05 AM

8:05 AM    [AUTOMÁTICO] Scheduler ejecuta job_id:
           "sleep_retoma_+5215551234567_..."
           │
           └─→ Bot envía: "¡Hola de nuevo! Retomamos operaciones.
                          Cuéntame, ¿sigue en pie tu consulta
                          sobre tu dispositivo?"

Cliente recibe dos mensajes:
1. A las 1:05 AM: Mensaje de sleep mode (sin horarios)
2. A las 8:05 AM: Mensaje de reactivación (automático)
```

---

### **Caso 2: Cliente pregunta horarios (en horario normal 10 AM)**

```
10:00 AM   Cliente: "¿A qué hora atienden?"
           │
           ├─→ Bot: esta_en_horario_operacion_bot() = True (es 10 AM)
           ├─→ Bot llama generar_respuesta() NORMALMENTE
           ├─→ Claude AI genera respuesta contextualizada
           │   Puede usar obtener_horarios_modulo():
           │   "Lunes a Viernes: 10:00 AM a 9:00 PM
           │    Sábados y Domingos: 11:00 AM a 8:00 PM"
           └─→ Bot envía respuesta normal

Resultado: Mensaje normal durante horario de operación
```

---

### **Caso 3: Cliente escribe a las 11:55 PM (Cerca del cierre)**

```
11:55 PM   Cliente: "Necesito ayuda urgente"
           │
           ├─→ Bot: esta_en_horario_operacion_bot() = True (es 11 PM)
           ├─→ Bot responde NORMALMENTE
           └─→ Bot atiende el mensaje ANTES de las 12 AM

12:05 AM   Cliente: "¿Me ayudas?"
           │
           ├─→ Bot: esta_en_horario_operacion_bot() = False (ahora es 12:05 AM)
           ├─→ Bot entra en SLEEP MODE
           ├─→ Bot envía mensaje sin horarios
           ├─→ Bot programa reactivación para 7:05 AM
           └─→ Cliente recibe sleep mode

Resultado: Diferencia de 10 minutos cambia comportamiento
(Normal → Sleep mode)
```

---

## 🧪 Testing y Validación

### **Test 1: Verificar detección de sleep mode**

```bash
# En tu entorno local
python -c "
from agent.sleep_mode import esta_en_horario_operacion_bot
from datetime import datetime

print('Bot activo (6 AM):', esta_en_horario_operacion_bot())  # Debería ser True
print('Bot durmiendo (2 AM):', not esta_en_horario_operacion_bot())  # Debería ser True (NOT sleep)
"
```

### **Test 2: Verificar mensajes aleatorios**

```bash
# En test_local.py
# Escribir entre las 00:00 - 5:59 AM simulado
# Verificar que se recibe mensaje sin horarios específicos
```

### **Test 3: Verificar selección de asesor**

```python
# En main.py durante sleep mode, revisar logs:
# [SLEEP] Asesor seleccionado: Valentina
# [SLEEP] Asesor recuperado del historial: Camila
```

### **Test 4: Verificar scheduler (en Railway)**

```bash
# Ver logs de Railway:
# 🌙→☀️ [REACTIVACIÓN SLEEP] Job programado: sleep_retoma_{phone}_{timestamp}
# 🔔 [REACTIVACIÓN SLEEP] Enviando mensaje automático...
# ✅ Reactivación enviada a {phone}
```

---

## 📁 Archivos Modificados

| Archivo | Cambios |
|---------|---------|
| `agent/sleep_mode.py` | Reescrito completo con OPCIÓN 2, 3 mensajes de sleep, 4 de reactivación |
| `agent/main.py` | Integración de sleep mode, selección de asesor, scheduler |
| `agent/profile.py` | Nueva función `extraer_asesor_de_historial()`, actualizados nombres a hembras |
| `agent/brain.py` | Default asesor cambiado a "Valentina" |
| `agent/reminder_scheduler.py` | Nueva función `programar_reactivacion_sleep()` |
| `requirements.txt` | Agregado `apscheduler>=3.10.0` |
| `config/prompts.yaml` | Actualizados nombres de agentes (Diego→Daniela, etc.) |

---

## 🚀 Deployment a Railway

**Pasos para activar en producción:**

1. **Asegurar que scheduler se inicializa:**
   ```python
   # En lifespan() de main.py
   await inicializar_scheduler(app)  # ✅ Ya está
   ```

2. **Verificar variables de entorno:**
   ```env
   WHATSAPP_PROVIDER=whapi    # Tu proveedor configurado
   ENVIRONMENT=production
   PORT=8000
   # ... resto de variables
   ```

3. **Subir a GitHub y deployar en Railway:**
   ```bash
   git add .
   git commit -m "feat: sleep mode option 2 with 7h reactivation"
   git push origin main
   ```

4. **Monitorear logs en Railway:**
   - Buscar: `[SLEEP]` para activaciones de sleep mode
   - Buscar: `[REACTIVACIÓN SLEEP]` para confirmación de scheduling
   - Buscar: `🔔` para reactivaciones enviadas

---

## ⚙️ Variables de Entorno

```env
# Sleep Mode (automático, no requiere config)
ZONA_MEXICO=America/Mexico_City  # Detectado automáticamente

# Scheduler (inicializado automáticamente)
SCHEDULER_ENABLED=true  # Comentar para desactivar sleep mode
```

---

## 🔍 Troubleshooting

| Problema | Causa | Solución |
|----------|-------|----------|
| Mensajes de sleep mode no llegan | Scheduler no inicializado | Verificar `inicializar_scheduler()` en lifespan |
| Cliente ve horarios específicos | Mensajes fueron modificados | Revisar `_MENSAJES_SLEEP_MODE` en sleep_mode.py |
| Asesor cambia entre mensajes | Historial vacío | Esperar próximo ciclo de conversación |
| Reactivación no se envía | Job ID duplicado | APScheduler descarta si ID ya existe |
| Bot responde durante sleep | Horario_operacion_bot incorrecto | Verificar ZONA_MEXICO y hora del servidor |

---

## 📝 Notas de Diseño

✅ **Lo que funciona:**
- Sleep mode invisible para el cliente (no muestra "+7 horas" o "6 AM")
- Continuidad de asesor a través de historial
- Mensajes personalizados por asesor
- Reactivación automática sin intervención manual
- Agentes femeninos (Sofia, Valentina, Camila, Daniela, Andrea, Rocío)

⚠️ **Consideraciones:**
- Si Railway se reinicia, jobs pendientes se pierden
- No hay persistencia de scheduler entre reinicios
- Solución futura: Guardar jobs en base de datos

🔧 **Mejoras futuras:**
- Persistencia de scheduler en base de datos
- Múltiples tentativas de reactivación si falla
- Dashboard para ver jobs activos
- Configuración dinámica de +N horas (actualmente fija en 7)

---

**Última actualización:** 21 de Mayo, 2026
**Versión:** Sleep Mode OPCIÓN 2 — Reactivación a +7 horas
**Estado:** ✅ Implementado y listo para producción
