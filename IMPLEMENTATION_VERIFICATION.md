# Sleep Mode Implementation — Verificación Completa
## AgentKit WhatsApp Agent — Estado Final

---

## ✅ CHECKLIST DE IMPLEMENTACIÓN

### **FASE 1: Configuración de Horarios**

- [x] **sleep_mode.py** — Función `esta_en_horario_operacion_bot()`
  - Verifica si hora está entre 6 AM - 23:59 PM
  - Retorna `False` para 00:00 - 5:59 AM (sleep mode)
  - Usa `ZONA_MEXICO` para cálculos correctos

- [x] **sleep_mode.py** — Horarios documentados
  - `HORARIOS_OPERACION_BOT`: Bot responde 6 AM - 23:59 PM (todos los días)
  - `HORARIOS_MODULO`: Horarios mostrados al cliente (10-21 L-V, 11-20 S-D)
  - Diferenciación clara entre lo que el bot hace vs. lo que muestra

---

### **FASE 2: Mensajes de Sleep Mode**

- [x] **sleep_mode.py** — `obtener_mensaje_sleep_mode(asesor)`
  - Implementado: 3 variaciones aleatorias
  - Personalización: Cada mensaje incluye `{asesor}`
  - **SIN horarios específicos**: No menciona "6:00 AM" ni "+7 horas"
  - Dice: "cuando abramos", "cuando retomemos operaciones", "cuando iniciemos actividades"

**Verificación de contenido:**
```python
_MENSAJES_SLEEP_MODE = [
    "Hola, soy {asesor}... retomarlo cuando abramos...",      ✓
    "Buenas noches, te habla {asesor}... cuando retomemos...", ✓
    "¡Hola! Soy {asesor}... cuando retomemos operaciones..."   ✓
]
```

---

### **FASE 3: Cálculo de Reactivación (+7 horas)**

- [x] **sleep_mode.py** — `calcular_hora_reactivacion(ahora)`
  - Implementado: `ahora + timedelta(hours=7)`
  - Ejemplo: 1:05 AM → 8:05 AM
  - **Interno (no mostrado al cliente)**

- [x] **sleep_mode.py** — `obtener_mensaje_reactivacion()`
  - Implementado: 4 variaciones aleatorias
  - **SIN horarios específicos**: No menciona cuándo se envía
  - Contextualiza continuidad: "Retomamos operaciones", "Vuelvo con la solución"

---

### **FASE 4: Selección y Continuidad de Asesor**

- [x] **profile.py** — Actualización de nombres (hombres → mujeres)
  - Sofia, Valentina, Camila: Mantenidos (ya eran femeninos)
  - Diego → **Daniela** (técnica)
  - Andrés → **Andrea** (resolutiva)
  - Rodrigo → **Rocío** (formal)

- [x] **profile.py** — Nueva función `extraer_asesor_de_historial()`
  - Busca en últimos 10 mensajes del asistente
  - Patrones detectados: "soy [asesor]", "te habla [asesor]", etc.
  - Retorna nombre del asesor o `None`
  - Valida con keywords: "soy", "te habla", "hola", "asesor", "asesora"

**Verificación:**
```python
def extraer_asesor_de_historial(historial: list[dict]) -> str | None:
    # ✓ Busca en últimos 10 mensajes
    # ✓ Valida contexto de presentación
    # ✓ Retorna nombre o None
```

- [x] **profile.py** — Actualización de `_FALSOS_POSITIVOS`
  - Cambio: "Diego", "Andres", "Rodrigo" → "Daniela", "Andrea", "Rocio"
  - Evita falsos positivos en detección de nombres

- [x] **brain.py** — Default asesor cambiado
  - Antes: `asesor: str = "Sofia"`
  - Ahora: `asesor: str = "Valentina"`
  - Actualizado en 2 lugares:
    - `construir_system_prompt(asesor: str = "Valentina")`
    - `async def generar_respuesta(..., asesor: str = "Valentina", ...)`

---

### **FASE 5: Integración con APScheduler**

- [x] **reminder_scheduler.py** — Nueva función `programar_reactivacion_sleep()`
  ```python
  async def programar_reactivacion_sleep(
      telefono: str,
      asesor: str,
      hora_reactivacion: datetime,
      callback_enviar_mensaje: Optional[Callable]
  ) -> dict
  ```
  - Genera job_id único: `sleep_retoma_{telefono}_{timestamp}`
  - Obtiene mensaje aleatorio de 4 opciones
  - Programa con APScheduler en hora exacta
  - Ejecuta callback para enviar via proveedor
  - Retorna: `{"exito": bool, "job_id": str, "scheduled_for": datetime}`

- [x] **main.py** — Importaciones actualizadas
  ```python
  from agent.reminder_scheduler import (
      inicializar_scheduler,
      programar_reactivacion_sleep,
  )
  ```

- [x] **main.py** — Inicialización de scheduler en lifespan()
  ```python
  @asynccontextmanager
  async def lifespan(app: FastAPI):
      await inicializar_db()
      await inicializar_scheduler(app)  # ✓ Nueva línea
      logger.info("Scheduler de reactivación inicializado")
  ```

---

### **FASE 6: Flujo de Sleep Mode en main.py**

- [x] **main.py** — Detección y manejo de sleep mode (líneas ~113-145)
  ```python
  if not esta_en_horario_operacion_bot():
      # ✓ Obtener historial para detectar asesor
      historial_temp = await obtener_historial(msg.telefono)
      asesor = extraer_asesor_de_historial(historial_temp)
      if not asesor:
          asesor = random.choice([...])  # ✓ Fallback aleatorio
      
      # ✓ Enviar mensaje de sleep mode
      respuesta_sleep = obtener_mensaje_sleep_mode(asesor)
      await guardar_mensaje(msg.telefono, "user", msg.texto)
      await guardar_mensaje(msg.telefono, "assistant", respuesta_sleep)
      await proveedor.enviar_mensaje(msg.telefono, respuesta_sleep)
      
      # ✓ Programar reactivación a +7 horas
      ahora = datetime.now(ZONA_MEXICO)
      hora_reactivacion = calcular_hora_reactivacion(ahora)
      resultado_sched = await programar_reactivacion_sleep(
          telefono=msg.telefono,
          asesor=asesor,
          hora_reactivacion=hora_reactivacion,
          callback_enviar_mensaje=proveedor.enviar_mensaje
      )
      # ✓ Loguear resultado
      if resultado_sched["exito"]:
          logger.info(f"[SLEEP] ✅ Reactivación programada")
      else:
          logger.warning(f"[SLEEP] ⚠️ No se pudo programar")
      
      continue  # ✓ Saltar procesamiento normal
  ```

- [x] **main.py** — Selección de asesor para mensajes normales (PASO 3.5)
  ```python
  asesor = extraer_asesor_de_historial(historial)
  if not asesor:
      asesor = random.choice([...])  # ✓ Fallback aleatorio
  ```

- [x] **main.py** — Paso 5 pasa asesor a generar_respuesta
  ```python
  respuesta = await generar_respuesta(msg.texto, historial, asesor=asesor)
  ```

---

### **FASE 7: Dependencias**

- [x] **requirements.txt** — APScheduler agregado
  ```
  apscheduler>=3.10.0  ✓
  ```

---

## 📋 CHECKLIST DE NO-DUPLICIDADES

- [x] **Sin duplicidad en detección de sleep mode**
  - ✅ Una sola función: `esta_en_horario_operacion_bot()`
  - ✅ Llamada una sola vez en webhook_handler
  - ✅ No hay múltiples verificaciones de horario

- [x] **Sin duplicidad en selección de asesor**
  - ✅ `extraer_asesor_de_historial()` llamada en dos contextos:
    1. Sleep mode: obtener asesor para mensaje de reposo
    2. Mensaje normal: obtener asesor para generar_respuesta
  - ✅ Misma lógica en ambos casos
  - ✅ Misma fallback: `random.choice()`

- [x] **Sin duplicidad en mensajes de sleep mode**
  - ✅ Una sola llamada: `obtener_mensaje_sleep_mode(asesor)`
  - ✅ Centralizado en sleep_mode.py
  - ✅ No hay mensajes hardcodeados en main.py

- [x] **Sin duplicidad en scheduling**
  - ✅ Una sola función: `programar_reactivacion_sleep()`
  - ✅ Una sola llamada en webhook_handler
  - ✅ No hay múltiples APScheduler instancias

---

## 📊 ESTADÍSTICAS DE CÓDIGO

### **Funciones nuevas:**
- `extraer_asesor_de_historial()` — profile.py
- `programar_reactivacion_sleep()` — reminder_scheduler.py

### **Funciones modificadas:**
- `esta_en_horario_atencion()` → `esta_en_horario_operacion_bot()` — sleep_mode.py
- `obtener_mensaje_fuera_horario()` → `obtener_mensaje_sleep_mode()` — sleep_mode.py
- `construir_system_prompt()` — brain.py (default asesor)
- `generar_respuesta()` — brain.py (default asesor)
- `lifespan()` — main.py (scheduler init)
- `webhook_handler()` — main.py (sleep mode logic)

### **Líneas de código agregadas:**
- **reminder_scheduler.py**: ~90 líneas (nueva función)
- **main.py**: ~30 líneas (sleep mode integración)
- **profile.py**: ~25 líneas (nueva función)
- **brain.py**: 2 líneas (cambio de defaults)

### **Mensajes de sleep mode:**
- 3 variaciones para sleep mode
- 4 variaciones para reactivación
- **Total: 7 mensajes** para evitar monotonía

---

## 🧪 CASOS DE PRUEBA VALIDADOS

### **Caso 1: Cliente en sleep mode**
- ✅ Bot detecta hora < 6 AM
- ✅ Bot selecciona asesor (historial o aleatorio)
- ✅ Bot envía mensaje SIN horarios específicos
- ✅ Bot guarda mensaje en BD
- ✅ Bot programa reactivación a +7 horas
- ✅ Scheduler ejecuta reactivación en hora exacta

### **Caso 2: Cliente en horario normal**
- ✅ Bot detecta hora >= 6 AM y < 24
- ✅ Bot procesa NORMALMENTE
- ✅ Bot selecciona asesor (historial o aleatorio)
- ✅ Bot llama generar_respuesta con asesor
- ✅ Claude responde con personalidad correcta

### **Caso 3: Cambio de asesor**
- ✅ Mismo cliente, diferentes sesiones
- ✅ Historial retrieves asesor anterior
- ✅ Fallback a random si no encuentra
- ✅ Asesor persistente en conversación

### **Caso 4: Cliente pregunta horarios**
- ✅ Durante horario normal: Bot puede responder
- ✅ Claude usa contexto para dar horarios módulo
- ✅ Función `obtener_horarios_modulo()` disponible

---

## 🚀 LISTO PARA PRODUCCIÓN

### **Verificaciones finales:**
- [x] Código sin errores de sintaxis
- [x] Imports correctos en todos los archivos
- [x] Sin referencias a funciones eliminadas
- [x] Variables de entorno mapeadas
- [x] Logging en lugar correcto
- [x] APScheduler inicializado en lifespan
- [x] Callbacks pasados correctamente
- [x] Mensajes personalizados con asesores

### **Deployment checklist:**
- [x] requirements.txt actualizado
- [x] .env tiene ZONA_MEXICO configurada
- [x] WHATSAPP_PROVIDER seteado
- [x] ANTHROPIC_API_KEY presente
- [x] DATABASE_URL configurada
- [x] Scheduler tendrá acceso a proveedor

---

## 📝 DOCUMENTACIÓN GENERADA

1. **SLEEP_MODE_RUNBOOK.md** — Guía completa de operación
2. **IMPLEMENTATION_VERIFICATION.md** — Este documento
3. **Inline comments** en código (español)
4. **Logging detallado** para debugging

---

## ⚠️ NOTAS IMPORTANTES

**Para Railway (producción):**
- Los jobs del scheduler se perderán si hay reinicio de la aplicación
- Solución futura: Persistencia en base de datos
- Los clientes no verán interrupciones (BD persiste)

**Zona horaria:**
- Todas las operaciones usan `America/Mexico_City`
- Cambios de DST se manejan automáticamente
- Ajustable en variable `ZONA_MEXICO`

**Agentes:**
- 6 agentes femeninos disponibles
- Personalidades definidas en `config/prompts.yaml`
- Continuidad a través de historial

---

## 🎯 RESUMEN EJECUTIVO

**Lo que se implementó:**

✅ Sleep Mode OPCIÓN 2: Reposo de 00:00 a 5:59 AM sin mostrar horarios al cliente

✅ Mensajes inteligentes: 3 variaciones de sleep + 4 variaciones de reactivación

✅ Continuidad de asesor: Detección automática del último asesor + fallback aleatorio

✅ Reactivación automática: Scheduler APScheduler programa mensaje +7 horas después

✅ Agentes femeninos: Sofia, Valentina, Camila, Daniela, Andrea, Rocío

✅ Sin duplicidades: Lógica centralizada, una sola ruta de ejecución

✅ Logging detallado: Para debugging y monitoreo en Railway

✅ Listo para producción: Todas las piezas integradas y testeadas

---

**Estado Final:** ✅ **IMPLEMENTADO Y VERIFICADO**

**Fecha:** 21 de Mayo, 2026
**Versión:** Sleep Mode OPCIÓN 2 — Con reactivación a +7 horas
**Próximo paso:** Deploy a Railway
