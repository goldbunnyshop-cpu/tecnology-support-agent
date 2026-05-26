# 🔧 Quick Reference Commands — Restauración de Estado Actual
## AgentKit WhatsApp — Palabras Clave para Futuros Workflows

---

## 🎯 COMANDOS PRINCIPALES (Úsalos en nuevos workflows)

### **Comando 1: Estado Actual Completo**
```
"AGENTKIT_STATE_SNAPSHOT_MAY21_2026"
```
**Qué hace:** Trae TODA la documentación actual al contexto  
**Cuándo usarlo:** Cuando algo falla y necesitas restaurar desde el último estado conocido bueno  
**Resultado:** Acceso a todo (Sleep Mode, Agentes, Errores, Precios, Documentación)

---

### **Comando 2: Solo Troubleshooting**
```
"AGENTKIT_ERRORS_MANIFEST"
```
**Qué hace:** Trae SOLO los errores resueltos (11 errores documentados)  
**Cuándo usarlo:** Cuando algo específico falla en Whapi o Root Directory  
**Resultado:** Soluciones rápidas organizadas por error

---

### **Comando 3: Solo Aprendizajes Críticos**
```
"AGENTKIT_LEARNINGS_CRITICAL"
```
**Qué hace:** Trae solo los aprendizajes clave (tiempos, agentes, sleep mode)  
**Cuándo usarlo:** Cuando necesites recordar reglas de negocio  
**Resultado:** Lo esencial sin ruido

---

### **Comando 4: Verificación de Integraciones**
```
"AGENTKIT_INTEGRATIONS_CHECK"
```
**Qué hace:** Trae checklist de qué está conectado (Whapi, Google Calendar, Hugo Shop, etc.)  
**Cuándo usarlo:** Para auditar qué funciona y qué no  
**Resultado:** Status de cada integración

---

## 📋 IMPLEMENTACIÓN — 3 OPCIONES

### **OPCIÓN A: Archivo de "Snapshot" (RECOMENDADO)**

Crear archivo `AGENTKIT_STATE_SNAPSHOT.md` que contenga:
- Checksum de estado actual
- Lista de archivos críticos
- Versiones de dependencias
- Última verificación

**Ventaja:** Simple, visual, fácil de mantener  
**Desventaja:** Requiere actualización manual

**Implementar así:**
```bash
# 1. Crear archivo snapshot
cat > AGENTKIT_STATE_SNAPSHOT.md << 'EOF'
# Estado Snapshot - 21 Mayo 2026
## ✅ STATUS: OPERATIVO EN RAILWAY
- Sleep Mode: ✅ OPCIÓN 2 (sin horas)
- Agentes: ✅ 6 femeninos (Sofia, Valentina, Camila, Daniela, Andrea, Rocío)
- Reactivación: ✅ Automática +7 horas
- Tiempos: ✅ 4-6 horas documentados
- Hugo Shop: ⚠️ PARCIALMENTE INTEGRADO

## 📁 Archivos críticos:
- config/prompts.yaml ✅
- agent/sleep_mode.py ✅
- agent/main.py ✅
- agent/reminder_scheduler.py ✅

## 🔗 Dependencias:
- apscheduler>=3.10.0 ✅
- anthropic>=0.40.0 ✅
- fastapi>=0.104.0 ✅

## 📚 Documentación:
- SLEEP_MODE_RUNBOOK.md
- ERRORS_RESOLVED_DOCUMENTATION.md
- DISPLAY_PRICING_STRATEGY.md
- COMPLETE_WORKFLOW_DOCUMENTATION.md
EOF

# 2. Comprometer a Git
git add AGENTKIT_STATE_SNAPSHOT.md
git commit -m "chore: state snapshot for future recovery"
git push origin main
```

---

### **OPCIÓN B: README Dinámico con Índice**

Crear `CURRENT_STATE.md` que se actualice automáticamente:

```markdown
# Current State & Quick Links
**Last Updated:** 21 Mayo 2026  
**Status:** ✅ OPERATIVO

## 🚨 Si algo falla, leer en ESTE ORDEN:
1. [ERRORS_RESOLVED_DOCUMENTATION.md](#) — Encontrar error
2. [SLEEP_MODE_RUNBOOK.md](#) — Si es sleep mode
3. [DISPLAY_PRICING_STRATEGY.md](#) — Si es precios
4. [COMPLETE_WORKFLOW_DOCUMENTATION.md](#) — Entender timeline

## 🎯 Palabras clave para buscar en docs:
- "sleep mode" → SLEEP_MODE_RUNBOOK.md
- "whapi" → ERRORS_RESOLVED_DOCUMENTATION.md
- "hugo shop" → DISPLAY_PRICING_STRATEGY.md
- "timeline" → COMPLETE_WORKFLOW_DOCUMENTATION.md

## 📊 Estado actual:
| Componente | Status | Loc |
|-----------|--------|-----|
| Sleep Mode | ✅ | sleep_mode.py |
| Agentes | ✅ | prompts.yaml |
| Precios | ⚠️ | DISPLAY_PRICING_STRATEGY.md |
```

**Ventaja:** Dinámico, resumen visual  
**Desventaja:** Requiere actualización frecuente

---

### **OPCIÓN C: Sistema de Versionado con Git Tags**

```bash
# 1. Crear tag de estado conocido bueno
git tag -a "agentkit-v1.0-stable-may21" -m "Sleep Mode v2, 6 Agentes, +7h Reactivation, Hugo Shop Docs"

# 2. Para recuperar en futuro:
git describe --tags
# Output: agentkit-v1.0-stable-may21

# 3. Si algo falla, restaurar:
git checkout agentkit-v1.0-stable-may21
```

**Ventaja:** Versionado profesional, fácil rollback  
**Desventaja:** Requiere entender Git

---

## 🔄 FLUJO DE RECUPERACIÓN ANTE FALLO

### **Paso 1: Identificar el problema**
```
Error X en componente Y
↓
Buscar "AGENTKIT_ERRORS_MANIFEST"
```

### **Paso 2: Encontrar solución**
```
"AGENTKIT_ERRORS_MANIFEST" → Error Type X
↓
Ver solución en ERRORS_RESOLVED_DOCUMENTATION.md
```

### **Paso 3: Aplicar fix**
```
Ejecutar pasos en solución
↓
Testear en local
↓
Push a Railway
```

### **Paso 4: Actualizar snapshot**
```
Actualizar AGENTKIT_STATE_SNAPSHOT.md con nueva fecha
↓
Commit: "fix: recovered from error X, updated snapshot"
```

---

## 📌 PALABRAS CLAVE POR PROBLEMA

| Problema | Palabra Clave | Archivo |
|----------|--------------|---------|
| Bot no responde en Whapi | `WHAPI_401_UNAUTHORIZED` | ERRORS_RESOLVED_DOCUMENTATION.md |
| Import error / module not found | `MODULE_NOT_FOUND_ROOT_DIR` | ERRORS_RESOLVED_DOCUMENTATION.md |
| Sleep mode mostrando horas | `SLEEP_MODE_NO_TIMES` | SLEEP_MODE_RUNBOOK.md |
| Precios no actualizan | `HUGO_SHOP_NOT_CONNECTED` | DISPLAY_PRICING_STRATEGY.md |
| Railway build falla | `RAILWAY_PYTHONPATH_ERROR` | ERRORS_RESOLVED_DOCUMENTATION.md |
| Scheduler no programa | `SCHEDULER_NOT_INIT` | SLEEP_MODE_RUNBOOK.md |

---

## 🔗 LLAMADA RÁPIDA DESDE OTRO WORKFLOW

**Opción A: Prompt directo**
```
"Lee AGENTKIT_STATE_SNAPSHOT.md y trae al contexto:
1. Estado actual del sistema
2. Si hubiera un error en [COMPONENTE X], ¿dónde está documentado?"
```

**Opción B: Comando implícito**
```
"Estoy trabajando en AgentKit. Estado = AGENTKIT_STATE_SNAPSHOT_MAY21_2026.
Necesito cambiar [X]. ¿Afecta algo de lo que ya funciona?"
```

**Opción C: Con archivo de referencia**
```
"He leído CURRENT_STATE.md. El sistema tiene [estos componentes].
Antes de hacer [cambio], ¿qué puedo romper?"
```

---

## 📝 PLANTILLA PARA NUEVOS WORKFLOWS

**Cuando abras un nuevo workflow y necesites contexto:**

```
Context Instruction:
- Current State: AGENTKIT_STATE_SNAPSHOT_MAY21_2026
- Last Stable: 21 Mayo 2026
- Docs Available: ERRORS_RESOLVED_DOCUMENTATION.md, SLEEP_MODE_RUNBOOK.md

If anything breaks:
1. Check AGENTKIT_ERRORS_MANIFEST
2. Find error in ERRORS_RESOLVED_DOCUMENTATION.md
3. Apply fix
4. Update AGENTKIT_STATE_SNAPSHOT.md
```

---

## ✅ CHECKLIST PARA USAR EN FUTUROS WORKFLOWS

- [ ] Leí el estado actual (AGENTKIT_STATE_SNAPSHOT.md)
- [ ] Entiendo qué está funcionando bien
- [ ] Sé dónde están los errores documentados
- [ ] Conocco las palabras clave para buscar
- [ ] Si falla, tengo un plan de recuperación
- [ ] Voy a actualizar snapshot después de cualquier cambio

---

## 🎯 RECOMENDACIÓN FINAL

**Implementar las 3 opciones juntas:**

1. **OPCIÓN A (Snapshot):** Archivo simple de referencia rápida
2. **OPCIÓN B (README):** Índice dinámico visible siempre
3. **OPCIÓN C (Git Tags):** Para versionado profesional

**Uso en futuro:**
- Workflow nuevo = "AGENTKIT_STATE_SNAPSHOT_MAY21_2026"
- Error específico = "AGENTKIT_ERRORS_MANIFEST"
- Necesito entender = "Lee CURRENT_STATE.md"

---

**Creado:** 21 Mayo 2026
**Versión:** 1.0
**Status:** Listo para usar en futuros workflows
