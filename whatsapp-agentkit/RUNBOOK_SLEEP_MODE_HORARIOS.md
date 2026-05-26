# 📋 RUNBOOK: Sleep Mode + Horarios + Reactivación a 7 Horas

**Documento creado:** 2026-05-21
**Responsable:** Christian (Técnico de reparación + Marketing digital)
**Estado:** Especificación lista para implementación

---

## **CONTEXTO DEL PROYECTO**

**Problema original:**
- Bot respondía 24/7 sin validar horarios de operación
- Sleep mode existía pero con horarios ANTIGUOS (10 AM - 9 PM)
- Sin reactivación automática tras mensajes en horario de descanso
- Duplicidades en código causaban crashes anteriores

**Solución propuesta:**
Implementar 3-capas:
1. Horario de operación del BOT (6 AM - 23:59 PM)
2. Sleep mode con mensajes aleatorios (00:00 - 5:59 AM)
3. Reactivación automática a +7 horas

---

## **ARQUITECTURA DECIDIDA**

### **Layer 1: Horarios de Operación**

| Período | Bot | Módulo | Acción |
|---------|-----|--------|--------|
| 6:00 AM - 10:00 AM (L-V) | ✅ Responde | ❌ Cerrado | Valida pero informa horario |
| 10:00 AM - 9:00 PM (L-V) | ✅ Responde | ✅ Abierto | Responde normalmente |
| 9:00 PM - 11:59 PM | ✅ Responde | ❌ Cerrado | Valida pero informa horario |
| 12:00 AM - 5:59 AM | ❌ Sleep mode | ❌ Cerrado | Envía mensaje + programa reactivación |
| Sábados 11 AM - 8 PM | ✅ Responde | ✅ Abierto | Responde normalmente |
| Domingos 11 AM - 8 PM | ✅ Responde | ✅ Abierto | Responde normalmente |

### **Layer 2: Selección de Asesor (Personalidades Separadas)**

**Decisión:** Mantener 6 personalidades diferentes (OPCIÓN A)

**Agentes (personalidades fijas):**
1. **Sofía** — Empática y paciente
2. **Valentina** — Profesional y directa
3. **Camila** — Amigable y cercana
4. **Diego** — Técnico y preciso
5. **Andrés** — Amigable y resolutivo
6. **Rodrigo** — Formal y confiable

**Lógica de selección:**
```
1. Buscar en BD: ¿Cliente tiene asesor anterior (asesor_ultimo)?
   SI  → Usar ese asesor (CONTINUIDAD)
   NO  → Extraer de historial últimos 10 mensajes
        ¿Hay asesor detectado?
        SI  → Usar ese
        NO  → Elegir aleatoriamente entre los 6
```

### **Layer 3: Reactivación a +7 Horas (Opción 2 - Recomendada)**

**Trigger:** Cliente envía mensaje entre 00:00 - 5:59 AM

**Flujo:**
```
00:00 - 5:59 AM: Cliente escribe
    ↓
Bot.sleep_mode.py:
  - Detecta: "Fuera de horario"
  - Envía: Mensaje aleatorio (Opción B)
  - Programa: Reactivación a NOW + 7 horas
  ↓
A las 7 horas exactas:
  - Bot envía: "Gracias por la espera, estamos dando prioridad..."
  - Bot retoma conversación normal
```

**Implementación:**
- Usar: `reminder_scheduler.py` (APScheduler ya existe)
- Nueva función: `programar_reactivacion_sleep(telefono, hora_retoma)`
- Almacenamiento: Campo en BD: `sleep_mode_reactivacion_time`

---

## **ARCHIVOS A MODIFICAR**

### **1. `agent/sleep_mode.py` (CRÍTICO)**

**Cambios:**
```python
# ❌ VIEJO (línea 13-21)
HORARIOS_ATENCION = {
    "lunes": {"inicio": 10, "fin": 21},      # 10 AM - 9 PM
    ...
}

# ✅ NUEVO
HORARIOS_ATENCION_BOT = {
    "lunes": {"inicio": 6, "fin": 24},       # 6 AM - 23:59 PM
    "martes": {"inicio": 6, "fin": 24},      # BOT SIEMPRE OPERATIVO
    ...
}

HORARIOS_ATENCION_MODULO = {
    "lunes": {"inicio": 10, "fin": 21},      # 10 AM - 9 PM (Lo que mostramos al cliente)
    ...
}

# ❌ VIEJO: Mensaje fijo (línea 65-79)
def obtener_mensaje_fuera_horario() -> str:
    return f"""Hola 👋
Gracias por escribirnos. Ahorita estamos fuera..."""

# ✅ NUEVO: 3 variaciones aleatorias (Opción B)
_MENSAJES_SLEEP_MODE = [
    "Hola, soy [ASESOR] de Technology Support 😊\nRecibí tu mensaje y créeme que estoy anotando todo para retomarlo cuando abramos.\nNuestro equipo retoma operaciones a las 6:00 am.\n¡Te atenderé con prioridad en ese momento! Que descanses bien.",
    
    "Buenas noches, te habla [ASESOR] de Technology Support.\nHe registrado tu consulta y será atendida con prioridad cuando retomemos operaciones.\nNuestro equipo está disponible a partir de las 6:00 am.\n¡Descansa, estamos aquí para ti! 🙏",
    
    "¡Hola! Soy [ASESOR], asesor de Technology Support 😊\nAnotado tu mensaje — no se me olvida. A las 6:00 am retomamos y tú serás de los primeros.\nQue descanses tranquilo, ¡vuelvo en un rato con la solución!",
]
```

**Nuevas funciones:**
```python
def obtener_mensaje_sleep_mode_aleatorio(asesor: str) -> str:
    """Retorna uno de 3 mensajes aleatorios personalizados"""
    import random
    msg = random.choice(_MENSAJES_SLEEP_MODE)
    return msg.replace("[ASESOR]", asesor)

def calcular_hora_reactivacion(ahora: datetime) -> datetime:
    """Suma 7 horas al timestamp actual (mensaje en sleep mode)"""
    return ahora + timedelta(hours=7)
```

### **2. `agent/profile.py` (Actualizar falsos positivos)**

**Cambios:**
```python
# ❌ VIEJO (línea 16-19) — Todavía tiene nombres de hombre
_FALSOS_POSITIVOS = {
    "Sofia", "Valentina", "Camila", "Diego", "Andres", "Rodrigo",
    ...
}

# ✅ NUEVO — Solo mujeres (o los nuevos que elijas)
_FALSOS_POSITIVOS = {
    "Sofia", "Valentina", "Camila", "Diego", "Andres", "Rodrigo",
    "Tecnology", "Support", ...
}

# NOTA: Los nombres de hombre siguen aquí como falsos positivos
# (para NO confundirlos con nombres de clientes)
# Pero en prompts.yaml solo están las mujeres ACTIVAS
```

**Agregar nueva función:**
```python
def extraer_asesor_de_historial(historial: list[dict]) -> str | None:
    """Busca en los últimos 10 mensajes del asistente quién está atendiendo.
    
    Busca patrones como:
    - "Soy Sofia, asesor de..."
    - "Te habla Valentina"
    - "Hola, soy Camila"
    """
    asesores_validos = {"Sofia", "Valentina", "Camila", "Diego", "Andres", "Rodrigo"}
    
    for msg in historial[-10:]:  # Últimos 10 mensajes
        if msg.get("role") != "assistant":
            continue
        content = msg.get("content", "")
        
        for asesor in asesores_validos:
            if asesor.lower() in content.lower():
                # Validar que aparezca en contexto de presentación
                if any(x in content.lower() for x in ["soy", "te habla", "hola", "asesor"]):
                    return asesor
    
    return None
```

### **3. `agent/main.py` (Integración central)**

**Cambios en webhook_handler (línea 74 en adelante):**

```python
# Después de obtener historial (línea 120)
historial = await obtener_historial(msg.telefono)

# ✅ NUEVO: Seleccionar asesor
from agent.profile import extraer_asesor_de_historial
import random

asesor = extraer_asesor_de_historial(historial)
if not asesor:
    asesor = random.choice(["Sofia", "Valentina", "Camila", "Diego", "Andres", "Rodrigo"])

# En la llamada a generar_respuesta (línea 144):
# ❌ VIEJO
respuesta = await generar_respuesta(msg.texto, historial)

# ✅ NUEVO
respuesta = await generar_respuesta(msg.texto, historial, asesor=asesor)

# En sleep mode (línea 108):
# ❌ VIEJO
respuesta_sleep = obtener_mensaje_fuera_horario()

# ✅ NUEVO
from agent.sleep_mode import obtener_mensaje_sleep_mode_aleatorio, calcular_hora_reactivacion
respuesta_sleep = obtener_mensaje_sleep_mode_aleatorio(asesor)
await guardar_mensaje(msg.telefono, "user", msg.texto)
await guardar_mensaje(msg.telefono, "assistant", respuesta_sleep)

# Programar reactivación a +7 horas
hora_reactivacion = calcular_hora_reactivacion(datetime.now(ZONA_MEXICO))
await programar_reactivacion_sleep(msg.telefono, asesor, hora_reactivacion)
```

### **4. `agent/reminder_scheduler.py` (Nueva función)**

**Agregar:**
```python
async def programar_reactivacion_sleep(
    telefono: str,
    asesor: str,
    hora_retoma: datetime,
) -> str:
    """Programa un mensaje de reactivación después del sleep mode (+7 horas)"""
    
    async def enviar_reactivacion():
        from agent.brain import generar_respuesta
        from agent.memory import guardar_mensaje, obtener_historial
        from agent.providers import obtener_proveedor
        
        proveedor = obtener_proveedor()
        historial = await obtener_historial(telefono)
        
        # Mensaje de reactivación aleatorio
        mensajes_retoma = [
            f"Gracias por tu paciencia, estamos aquí. ¿En qué te ayudamos?",
            f"Hola de nuevo 😊 Retomamos operaciones. Cuéntame, ¿sigue en pie tu consulta?",
            f"¡Volvimos! Dime qué necesitas y lo resolvemos.",
        ]
        import random
        mensaje = random.choice(mensajes_retoma)
        
        await guardar_mensaje(telefono, "assistant", mensaje)
        await proveedor.enviar_mensaje(telefono, mensaje)
        logger.info(f"[REACTIVACIÓN] Enviado a {telefono} a las {hora_retoma}")
    
    scheduler.add_job(
        enviar_reactivacion,
        'date',
        run_date=hora_retoma,
        id=f"sleep_retoma_{telefono}_{hora_retoma.timestamp()}",
    )
```

### **5. `config/prompts.yaml` (Sin cambios si las personalidades están OK)**

**Solo verificar:**
- ✅ Las 6 personalidades están presentes
- ✅ No hay referencias a horarios viejos
- ✅ System prompt plantilla usa `ASESOR_NOMBRE` y `ASESOR_PERSONALIDAD`

---

## **LÓGICA DE CONTINUIDAD (Ya existe, solo verificar)**

**En `agent/profile.py` línea 113:**
```python
asesor_anterior = perfil.asesor_ultimo or ""
```

**Cómo funciona:**
1. Se guarda `asesor_ultimo` en BD después de cada respuesta
2. Próxima conversación: se recupera automáticamente
3. Si no existe, se elige aleatoriamente

**Implementación faltante:** Guardar asesor en BD después de respuesta
```python
# En main.py después de enviar respuesta (línea 164):
await guardar_asesor_en_perfil(msg.telefono, asesor)  # ← NUEVA
```

---

## **RESUMEN DE CAMBIOS**

| Archivo | Cambio | Complejidad | Riesgo |
|---------|--------|-------------|--------|
| `sleep_mode.py` | Horarios + Mensajes aleatorios | 🟡 Medio | 🟢 Bajo |
| `profile.py` | Falsos positivos + Extraer asesor | 🟢 Bajo | 🟢 Bajo |
| `main.py` | Seleccionar asesor + Sleep mode | 🟡 Medio | 🟡 Medio |
| `reminder_scheduler.py` | Nueva función reactivación | 🟡 Medio | 🟡 Medio |
| `config/prompts.yaml` | Verificar (sin cambios) | 🟢 Bajo | 🟢 Bajo |

**Impacto total:** 🟡 Medio (no hay riesgo de crash si se implementa bien)

---

## **TESTING ANTES DE DEPLOY**

1. **Test 1:** Cliente envía mensaje a las 1:05 AM
   - ✅ Recibe mensaje sleep mode
   - ✅ Se programa reactivación a las 8:05 AM
   - ✅ A las 8:05 AM recibe mensaje de retoma

2. **Test 2:** Cliente continúa a las 8:05 AM
   - ✅ Mismo asesor lo atiende
   - ✅ Responde con continuidad

3. **Test 3:** Cliente nuevo a las 7:00 AM
   - ✅ Se asigna asesor aleatorio
   - ✅ Asesor es coherente en toda la conversación

4. **Test 4:** Verificar NO hay duplicidades
   - ✅ sleep_mode.py activado correctamente
   - ✅ main.py NO duplica validaciones
   - ✅ scheduler NO crea múltiples tareas

---

## **DEPLOYMENT CHECKLIST**

- [ ] Actualizar `sleep_mode.py` (horarios + mensajes)
- [ ] Actualizar `profile.py` (falsos positivos + extraer asesor)
- [ ] Actualizar `main.py` (seleccionar asesor + integración)
- [ ] Agregar función en `reminder_scheduler.py`
- [ ] Verificar `prompts.yaml` tiene las 6 personalidades
- [ ] Hacer prueba local con `tests/test_local.py`
- [ ] Deploy a Railway
- [ ] Monitorear logs por errores de scheduler

---

## **NOTAS IMPORTANTES**

1. **No hay crash risk** — sleep_mode.py ya existe, solo se actualizan horarios
2. **Asesor selección es nuevo** — pero basado en lógica EXISTENTE en profile.py
3. **Reactivación es nuevo** — pero usa APScheduler que ya está en el proyecto
4. **Mensajes son NUEVOS y aleatorios** — Opción B aprobada

---

**Documento versionado:** v1.0 (Especificación lista)
**Próximo paso:** Implementación según orden de Christian
