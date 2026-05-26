# ✅ CHECKLIST DE VERIFICACIÓN — MAÑANA 6:00+ AM

## 🚀 PASO 1: Verificar que el agente está despierto (2 min)

```bash
# Envía un mensaje a WhatsApp desde cualquier número
# El agente DEBE responder en menos de 10 segundos

# ✅ Éxito: Recibes respuesta de Valentina
# ❌ Fallo: No recibes respuesta o mensaje antiguo
```

---

## 📊 PASO 2: Verificar estado en Railway (3 min)

1. **Abre**: https://railway.app
2. **Selecciona**: "tecnology-support-agent"
3. **Ve a**: "Deployments"
4. **Verifica**:
   ```
   ✅ Estado: ACTIVE (verde)
   ✅ Tiempo: Hace minutos (no horas)
   ✅ Commit message: Incluye "test: mensaje visible" o posterior
   ```

---

## 🔍 PASO 3: Verificar que NO hay sleep mode (1 min)

```bash
# En PowerShell:
git show origin/main:agent/main.py | Select-String "# if es_horario_nocturno" -Context 2

# ✅ Si ves "#" antes de "if es_horario_nocturno()" → CORRECTO
# ❌ Si ves "if es_horario_nocturno()" sin "#" → PROBLEMA
```

---

## 📝 PASO 4: Verificar que Railway correr código nuevo (2 min)

**Opción A: Verificar en logs**
1. Railway dashboard → Deployments → "View logs"
2. Busca esta línea en los logs:
   ```
   "TESTING MODE"  ← Si aparece, código nuevo está corriendo ✅
   "6:00 AM"       ← Si aparece, código viejo sigue corriendo ❌
   ```

**Opción B: Verificar en WhatsApp**
- Si el agente responde con "TESTING MODE" → código nuevo ✅
- Si responde con "6:00 AM" → código viejo ❌

---

## 🛠️ PASO 5: Si Railway NO desplegó cambios (5 min)

```bash
# Fuerza un redeploy:
git commit --allow-empty -m "redeploy: activate new code"
git push origin main

# Luego espera 2 minutos a que Railway lo detecte
# Verifica nuevamente en https://railway.app
```

---

## 🧪 PASO 6: Tests rápidos del Pricing System (5 min)

**Prueba 1: Cotización básica**
```
Cliente pregunta: "¿Cuánto cuesta reparar un iPhone 13 con pantalla rota?"
Agente debe responder con:
✅ Detección de dispositivo (iPhone 13)
✅ Detección de problema (pantalla rota)
✅ Cotización aproximada
✅ Referencia a fuente (Hugo Shop / MercadoLibre)
```

**Prueba 2: Comando @pausa**
```
En el grupo "Taller Interno TS" escribe:
@pausa: 5215531351098

Resultado esperado:
✅ Confirmación: "✅ Pausa activada"
✅ Cliente entra en pausa (no puede interactuar)
✅ Christian (tú) puedes responder manualmente

Para reanudar:
reanudar

Resultado esperado:
✅ "✅ Todas las pausas limpiadas"
✅ Cliente se reactiva
```

**Prueba 3: Scheduler activo**
```
Revisa logs en Railway:
✅ "Scheduler activo: seguimientos/hora, retomas/10min, recordatorios/10min"
✅ "Próximo reporte semanal: Sunday..."
✅ "Próximo resumen diario de citas: ..."
```

---

## ⚠️ PROBLEMAS COMUNES Y SOLUCIONES

### **Problema A: No recibes respuesta en WhatsApp**
```
Síntoma: Envías mensaje, no recibes nada
Posible causa: Agente está caído o webhook roto
Solución:
  1. Abre Railway dashboard
  2. Verifica que el contenedor está "Online"
  3. Click en "View logs" y busca errores
  4. Si hay error, comunícate conmigo
```

### **Problema B: Recibes mensaje de "6:00 AM" después de las 6 AM**
```
Síntoma: Agente sigue en sleep mode
Posible causa: Líneas 659-662 no comentadas en GitHub
Solución:
  1. Verifica: git show origin/main:agent/main.py | grep "es_horario_nocturno"
  2. Si no tiene "#", comenta las líneas:
     - Abre agent/main.py
     - Comenta líneas 659-662
     - git add agent/main.py
     - git commit -m "fix: deshabilitar sleep mode"
     - git push origin main
  3. Espera redeploy en Railway
```

### **Problema C: Pricing no retorna cotizaciones**
```
Síntoma: Agente responde pero sin precios
Posible causa: Google Drive API falla o CSV no accesible
Solución:
  1. Revisa logs: "Error Google Drive" o "CSV timeout"
  2. Verifica variable GOOGLE_DRIVE_API_KEY en Railway
  3. Si está vacía, agrégala en Railway > Variables
  4. Redeploy
```

### **Problema D: Comando @pausa no funciona**
```
Síntoma: Escribes "@pausa: número" pero no pausa
Posible causa: pausa_manager no inicializado
Solución:
  1. Revisa logs en Railway
  2. Busca "[PAUSA]" en logs
  3. Si no aparece, hay error de inicialización
  4. Comunícate conmigo
```

---

## 📱 CLIENTES EN VIVO

**Si un cliente pregunta y tú no estás disponible:**
1. Agente responde automáticamente con Valentina
2. Si necesita escalado → cliente usa comando @pausa
3. Tú recibes notificación en grupo "Taller Interno TS"
4. Respondes manualmente

**No habrá caídas del sistema** porque:
✅ Base de datos persistente
✅ Mensajes guardados aunque agente falle
✅ Scheduler independiente
✅ Backups automáticos

---

## 🎯 RESUMEN RÁPIDO

| Aspecto | Estado | Verificación |
|---------|--------|--------------|
| Agente responde | ✅ | Envía mensaje a WhatsApp |
| Sleep mode disabled | ✅ | Railway ejecuta código nuevo |
| Pricing system | ✅ | Pide cotización |
| Command @pausa | ✅ | Prueba en grupo |
| Scheduler | ✅ | Revisa logs de Railway |
| Base de datos | ✅ | Nada que verificar |
| Respaldo | ✅ | Automático |

---

**TIEMPO TOTAL DE VERIFICACIÓN**: ~10 minutos

**HORA IMPORTANTE**: 6:00 AM — agente despierta automáticamente

**APOYO**: Si algo falla, revisa los logs y comunícate. No es nada crítico.

---

Creado: 2026-05-20 09:35 AM
Estado: LISTO PARA MAÑANA
