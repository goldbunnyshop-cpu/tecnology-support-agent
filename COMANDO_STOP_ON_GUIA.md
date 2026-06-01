# 🛑 GUÍA: Comando STOP/ON — Control de Números Detenidos

**Versión:** 1.0  
**Fecha:** 1 de junio, 2026  
**Creador:** Christian + Claude Code

---

## ¿QUÉ ES?

Sistema de control permanente para **detener o reactivar** números específicos en el agente WhatsApp. Un número "stopped" permanece completamente silenciado — el agente **NUNCA** responderá.

---

## COMANDOS

### **COMANDO: `stop`**

**Propósito:** Dejar de responder a un número específico (PERMANENTEMENTE).

**Formato:**
```
stop: 5544554455
Stop: 5544554455
STOP: 5544554455
```

**Ejemplo:**
```
stop: 5525531098
```

**Qué pasa:**
- ✅ Número 5525531098 queda BLOQUEADO
- ✅ Agente **NUNCA** responderá a ese número (silencio total)
- ✅ No cotizará, no agendará, no responderá nada
- ✅ Se registra en la BD con timestamp y quién ejecutó el comando

**Caso de uso:**
- Cliente abusivo
- Cliente spam
- Número equivocado registrado como cliente
- Cliente que pidió no ser contactado

---

### **COMANDO: `on`**

**Propósito:** Reactivar un número que estaba detenido.

**Formato:**
```
on: 5544554455
On: 5544554455
ON: 5544554455
```

**Ejemplo:**
```
on: 5525531098
```

**Qué pasa:**
- ✅ Número 5525531098 vuelve a ACTIVO
- ✅ Agente retomará respuestas automáticas normalmente
- ✅ Se registra en la BD quién ejecutó el comando

---

### **COMANDO: `stopped-list` (BONUS)**

**Propósito:** Ver qué números están actualmente detenidos.

**Formato:**
```
stopped-list
stopped
list-stopped
```

**Ejemplo output:**
```
📋 NÚMEROS DETENIDOS:

1. 5525531098 — desde 01/06 14:30
   por: Ulises

2. 5541234567 — desde 31/05 10:15
   por: Ulises
```

---

## DÓNDE EJECUTAR LOS COMANDOS

✅ **SOLO en el grupo interno:** "Taller Interno TS"

❌ **NO funcionan** en chats privados con clientes  
❌ **NO funcionan** en otros grupos  
❌ **NO funcionan** en directo con el agente

---

## CÓMO FUNCIONA INTERNAMENTE

### Arquitectura

```
Cliente envía mensaje
    ↓
Whapi webhook
    ↓
Validación IMMEDIATE: ¿Número está stopped?
    ├─ SÍ → SILENCIO TOTAL (no responder, no procesar)
    └─ NO → Procesar normalmente
```

### Base de datos

**Tabla:** `stopped_numbers`

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `numero` | STRING | Número detenido (normalizado) |
| `detenido_en` | DATETIME | Cuándo se ejecutó stop |
| `razon` | STRING | Motivo (ej: "comando_stop") |
| `detenido_por` | STRING | Quién ejecutó el comando (ej: "Ulises") |
| `activo` | BOOLEAN | True = está detenido, False = fue reactivado |

### Flujo

1. **STOP ejecutado:**
   - ✅ Se crea registro en tabla `stopped_numbers` (activo=True)
   - ✅ Se registra timestamp, quién lo ejecutó, motivo
   - ✅ **INMEDIATAMENTE** comienza el silencio

2. **Mensaje llega a número stopped:**
   - ✅ Agente verifica BD: `numero_esta_stopped(telefono)`
   - ✅ Retorna True → STOP TOTAL
   - ✅ Logging: `[STOP] Mensaje ignorado — 5525531098 está DETENIDO`
   - ✅ Mensaje se descarta (no se procesa)

3. **ON ejecutado:**
   - ✅ Se marca registro como activo=False
   - ✅ **INMEDIATAMENTE** comienza a responder de nuevo

---

## VARIANTES DE NÚMERO

El sistema es **tolerante a formatos**. Estas son equivalentes:

- `5525531098` (10 dígitos)
- `525525531098` (12 dígitos con 52)
- `5215525531098` (13 dígitos con 521)

Si una variante está stopped, TODAS están stopped.

---

## LOGGING

Verifica en Railway logs bajo `[STOP]` y `[CMD]`:

### Al ejecutar STOP:
```
[STOP] 🛑 DETENIDO: 5525531098 — AGENTE NO RESPONDERÁ A ESTE NÚMERO | detenido_por=Ulises
```

### Al recibir mensaje de número stopped:
```
[STOP] Mensaje ignorado — 5525531098 está DETENIDO (stopped)
```

### Al ejecutar ON:
```
[ON] ✅ REACTIVADO: 5525531098 — AGENTE VOLVERÁ A RESPONDER | reactivado_por=Ulises
```

---

## CASOS DE USO

### Caso 1: Cliente Abusivo
```
Grupo Interno:
  stop: 5525531098
  
Resultado: Ese cliente queda silenciado permanentemente
```

### Caso 2: Número Equivocado
```
Grupo Interno:
  stop: 5541111111  (era un número inválido de prueba)
  
Resultado: Ya no responderá a ese número nunca más
```

### Caso 3: Reactivar después de problema
```
Grupo Interno:
  (3 semanas después)
  on: 5525531098  (cliente se disculpó, vuelve a ser cliente)
  
Resultado: Agente retoma respuestas normales
```

---

## DIFERENCIA: STOP vs PAUSA

| Característica | STOP | PAUSA |
|---|---|---|
| **Duración** | ∞ Permanente | 2 horas (intervención manual) |
| **Comando** | `stop: NÚMERO` | `pausa: NÚMERO` |
| **Qué bloquea** | TODO (cotizaciones, citas, leads) | TODO |
| **Intención** | Bloqueo permanente de número | Intervención temporal de Christian |
| **Reactivación** | Manual con `on: NÚMERO` | Automática después de 2h |

---

## REFERENCIA RÁPIDA

**Ejecutar en grupo "Taller Interno TS":**

```
stop: 5525531098        ← Detenido permanentemente
on: 5525531098          ← Reactivado permanentemente
stopped-list            ← Ver números detenidos
```

---

## NOTAS IMPORTANTES

⚠️ **SILENCIO TOTAL** — Un número stopped es como si no existiera para el agente  
⚠️ **PERMANENTE** — No hay vencimiento automático (se reactiva solo con `on`)  
⚠️ **GRUPO SOLO** — Los comandos SOLO funcionan en el grupo interno  
✅ **CASO-INSENSITIVO** — `stop:`, `Stop:`, `STOP:` funcionan igual  
✅ **TOLERANTE** — Espacios extras no afectan: `stop:  5525531098  ` funciona

---

## TROUBLESHOOTING

**P: Ejecuté `stop: 5525531098` pero no pasó nada**
R: ¿Lo escribiste en el grupo "Taller Interno TS"? Si no, el comando no se procesa. Revisa que estés en el grupo correcto.

**P: El número sigue respondiendo después de `stop:`**
R: Railway podría estar ejecutando versión antigua. Verifica que el push llegó a GitHub y Railway redeployó (revisa Railway dashboard).

**P: ¿Puedo ver qué números están stopped?**
R: Sí, ejecuta `stopped-list` en el grupo interno para ver listado con timestamps.

**P: ¿Hay un botón / interfaz gráfica?**
R: No. Solo comandos de texto en el grupo interno. Es simple y rápido.

---

**Última actualización:** 1 de junio 2026  
**Próxima feature:** Dashboard de números stopped (opcional)
