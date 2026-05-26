# Phase 1: Integración Básica WhatsApp-Agentkit ↔ Auto-CRM

**Estado:** ✅ Código creado y listo para ejecutar  
**Fecha:** 19 de Mayo 2026  
**Objetivo:** Conectar Agentkit (Python) con Auto-CRM (Next.js) para sincronizar citas

---

## 📋 Checklist de Instalación

### Paso 1: Verificar que ambos servicios están corriendo

**Terminal 1 - Auto-CRM (Next.js):**
```bash
cd C:\Users\Elitebook\auto-crm
npm run dev
```
Espera hasta ver: `✓ Ready in X.Xs` en `http://localhost:3000`

**Terminal 2 - Agentkit (Python):**
```bash
cd C:\Users\Elitebook\whatsapp-agentkit
python -m uvicorn agent.main:app --reload --port 8000
```
Espera hasta ver: `Uvicorn running on http://0.0.0.0:8000`

---

### Paso 2: Crear los 4 Templates de Notificación en Auto-CRM

**Terminal 3:**
```bash
cd C:\Users\Elitebook\auto-crm
npx tsx scripts/create-whatsapp-templates.ts
```

**Salida esperada:**
```
🚀 Creando templates de WhatsApp para Agentkit Integration...

✅ Template creado: "Cita Agendada - WhatsApp"
✅ Template creado: "Recordatorio Cita 24h - WhatsApp"
✅ Template creado: "Reparación Lista - WhatsApp"
✅ Template creado: "Recordatorio Seguimiento - WhatsApp"

📊 Total de templates en BD: 8

✨ ¡Templates de WhatsApp-Agentkit creados exitosamente!
```

---

### Paso 3: Verificar que Agentkit tiene httpx instalado

```bash
cd C:\Users\Elitebook\whatsapp-agentkit
pip list | findstr httpx
```

Si NO aparece `httpx`, instalar:
```bash
pip install httpx
```

---

### Paso 4: Verificar Variables de Entorno

**En `C:\Users\Elitebook\whatsapp-agentkit\.env` debe estar:**
```env
CRM_API_URL=http://localhost:3000/api
CRM_API_KEY=
```

**En `C:\Users\Elitebook\auto-crm\.env.local` debe estar:**
```env
AGENTKIT_WEBHOOK_URL=http://localhost:8000
```

---

### Paso 5: Revisar los Archivos Creados

**Agentkit:**
- ✅ `agent/send_to_crm.py` — Funciones de integración
- ✅ `agent/cita_detector.py` — Modificado para llamar a send_to_crm

**Auto-CRM:**
- ✅ `scripts/create-whatsapp-templates.ts` — Script para crear templates
- ✅ Nuevos templates en la BD

---

## 🧪 Prueba Funcional: Probar el Flujo Completo

### Test 1: Agendar cita via WhatsApp

1. Abre WhatsApp y envia un mensaje al bot de Agentkit:
   ```
   Hola, quiero agendar mi iPhone 14 para mañana a las 3pm, está rota la pantalla
   ```

2. Verifica los logs:

   **Terminal 2 (Agentkit):**
   ```
   [CITA_DETECTOR] ✅ Cita guardada...
   [SEND_TO_CRM] 🔗 Iniciando integración con Auto-CRM...
   [SEND_TO_CRM] ✅ Transacción creada en CRM: 123456
   [SEND_TO_CRM] ✅ Notificación encolada para +52...
   ```

   **Terminal 1 (Auto-CRM):**
   ```
   POST /api/transactions 201
   POST /api/notifications/send 201
   ```

3. Verifica en Auto-CRM:
   - Abre `http://localhost:3000`
   - Ve a "Transacciones"
   - Debe aparecer una nueva transacción con:
     - Nombre del cliente
     - Marca/Modelo del dispositivo
     - Folio generado automáticamente

---

### Test 2: Verificar la Notificación en la Cola

**Terminal 3:**
```powershell
curl.exe http://localhost:3000/api/notifications/queue?status=pending | ConvertFrom-Json | Select-Object -ExpandProperty data | Format-Table channel, recipient, status
```

**Salida esperada:**
```
channel  recipient                status
-------  ---------                ------
whatsapp +52123456789             pending
```

---

### Test 3: Verificar Templates Creados

**Terminal 3:**
```powershell
curl.exe http://localhost:3000/api/notifications/templates | ConvertFrom-Json | Select-Object -ExpandProperty data | Format-Table name, channel | Where-Object {$_.name -like "*WhatsApp*"}
```

**Salida esperada:**
```
name                              channel
----                              -------
Cita Agendada - WhatsApp          whatsapp
Recordatorio Cita 24h - WhatsApp  whatsapp
Reparación Lista - WhatsApp       whatsapp
Recordatorio Seguimiento - WhatsApp whatsapp
```

---

## 🔍 Troubleshooting

### Problema: "CRM_API_URL not found" o "Connection refused"

**Solución:** Verificar que:
1. Auto-CRM está corriendo en `http://localhost:3000` (Terminal 1)
2. El .env de agentkit tiene `CRM_API_URL=http://localhost:3000/api`
3. Reiniciar Agentkit

### Problema: "httpx.ConnectError"

**Solución:**
```bash
cd C:\Users\Elitebook\whatsapp-agentkit
pip install --upgrade httpx
```

### Problema: "Template no encontrado"

**Solución:**
1. Ejecutar nuevamente: `npx tsx scripts/create-whatsapp-templates.ts`
2. Verificar que PostgreSQL está corriendo (si estás en Railway)

### Problema: Notificación encolada pero no aparece en la cola

**Solución:**
1. Esperar 5-10 segundos (hay latencia en la BD)
2. Verificar que la notificación se insertó:
   ```powershell
   curl.exe http://localhost:3000/api/notifications/stats | ConvertFrom-Json | Select-Object -ExpandProperty stats
   ```

---

## 📊 Flujo Completo (Resumen)

```
1. Cliente envia mensaje en WhatsApp
   ↓
2. Whapi.cloud recibe mensaje
   ↓
3. Agentkit procesa en /webhook
   ↓
4. cita_detector.py detecta intención de agendar
   ↓
5. Claude API analiza el mensaje
   ↓
6. Se guarda la cita en PostgreSQL local de Agentkit
   ↓
7. 🔗 send_to_crm.py → POST a Auto-CRM
   ├─ crear_transaccion_desde_cita() → /api/transactions
   └─ enviar_notificacion_whatsapp() → /api/notifications/send
   ↓
8. Auto-CRM crea la transacción en PostgreSQL
   ↓
9. Auto-CRM encola la notificación
   ↓
10. Script procesar-notificaciones-whatsapp.ts (próxima fase)
    tomará la notificación y la enviará via WhatsApp
```

---

## 🎯 Métricas de Éxito

✅ Cuando ejecutes `/api/notifications/stats`, debes ver:
- `queue.pending > 0` (Notificaciones encoladas)
- Nuevas transacciones aparecen en `/api/transactions`
- Los logs de Agentkit muestran `[SEND_TO_CRM] ✅`

---

## 🚀 Próximos Pasos (Phase 2)

Una vez que Phase 1 esté funcionando:

1. Crear endpoint `/send-whatsapp` en Agentkit para recibir notificaciones desde Auto-CRM
2. Crear script `procesar-notificaciones-whatsapp.ts` en Auto-CRM
3. Setup cron job cada 5 minutos
4. Probar flujo bidireccional completo

---

## 💬 Comandos Rápidos

```bash
# Terminal 1: Auto-CRM
cd C:\Users\Elitebook\auto-crm && npm run dev

# Terminal 2: Agentkit
cd C:\Users\Elitebook\whatsapp-agentkit && python -m uvicorn agent.main:app --reload --port 8000

# Terminal 3: Crear templates
cd C:\Users\Elitebook\auto-crm && npx tsx scripts/create-whatsapp-templates.ts

# Ver templates creados
curl.exe http://localhost:3000/api/notifications/templates | ConvertFrom-Json | Select-Object -ExpandProperty data | Format-Table name, channel

# Ver notificaciones encoladas
curl.exe http://localhost:3000/api/notifications/queue?status=pending | ConvertFrom-Json | Select-Object -ExpandProperty data | Format-Table channel, recipient, status

# Ver estadísticas
curl.exe http://localhost:3000/api/notifications/stats | ConvertFrom-Json | Select-Object -ExpandProperty stats
```

---

## 📞 Soporte

Si tienes problemas:

1. Revisa los logs en ambas terminales (errores con timestamp)
2. Verifica que ambos servicios están corriendo (`npm run dev` y `uvicorn`)
3. Intenta reiniciar ambos servicios
4. Busca errores de conexión en los logs de Agentkit

¿Preguntas? Revisa `INTEGRACION_WHATSAPP_AGENTKIT.md` para más detalles arquitectónicos.

---

**Created:** 2026-05-19  
**Status:** Phase 1 Ready to Execute  
**Next Review:** After successful Phase 1 test
