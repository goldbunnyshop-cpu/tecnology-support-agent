# 🚀 Phase 1: Quick Start (5 minutos)

## Lo que se hizo
- ✅ Script Python para conectar Agentkit con Auto-CRM (`agent/send_to_crm.py`)
- ✅ Integración en detector de citas (`agent/cita_detector.py` modificado)
- ✅ Script para crear templates de notificación (`scripts/create-whatsapp-templates.ts`)
- ✅ Documentación completa

## Ahora ejecuta esto (en orden):

### 1️⃣ Terminal 1 - Auto-CRM
```bash
cd C:\Users\Elitebook\auto-crm
npm run dev
```
Espera: `✓ Ready in Xs`

### 2️⃣ Terminal 2 - Agentkit  
```bash
cd C:\Users\Elitebook\whatsapp-agentkit
python -m uvicorn agent.main:app --reload --port 8000
```
Espera: `Uvicorn running on http://0.0.0.0:8000`

### 3️⃣ Terminal 3 - Crear Templates
```bash
cd C:\Users\Elitebook\auto-crm
npx tsx scripts/create-whatsapp-templates.ts
```
**Debe mostrar:**
```
✅ Template creado: "Cita Agendada - WhatsApp"
✅ Template creado: "Recordatorio Cita 24h - WhatsApp"
✅ Template creado: "Reparación Lista - WhatsApp"
✅ Template creado: "Recordatorio Seguimiento - WhatsApp"
```

### 4️⃣ Verificar Instalación httpx (en Terminal 3)
```bash
cd C:\Users\Elitebook\whatsapp-agentkit
python -c "from agent.send_to_crm import crear_transaccion_desde_cita; print('✅ OK')"
```
Si no funciona:
```bash
pip install httpx
```

## 5️⃣ Prueba: Envía un mensaje en WhatsApp

**Al bot del Agentkit:**
```
Quiero agendar mi iPhone 14 para mañana a las 3pm, está rota la pantalla
```

**Verifica los logs:**

Terminal 2 debe mostrar:
```
[SEND_TO_CRM] ✅ Transacción creada en CRM: 12345
[SEND_TO_CRM] ✅ Notificación encolada
```

### 6️⃣ Verifica en Terminal 3

```powershell
# Ver transacción creada
curl http://localhost:3000/api/transactions | ConvertFrom-Json | Select-Object -ExpandProperty data | Select-Object -First 1

# Ver notificación encolada
curl http://localhost:3000/api/notifications/queue | ConvertFrom-Json | Select-Object -ExpandProperty data
```

## ✅ Si ves esto = ¡FUNCIONA!

- Logs muestran `[SEND_TO_CRM] ✅`
- Transacción aparece en `/api/transactions`
- Notificación aparece en `/api/notifications/queue` con status `pending`

## ❌ Si hay error

1. **"Connection refused"** → Verifica que ambos servicios están corriendo
2. **"Module not found: send_to_crm"** → Reinicia Terminal 2
3. **"httpx not found"** → `pip install httpx` en Terminal 3
4. **"Template no encontrado"** → Ejecuta nuevamente el paso 3

## 📚 Documentación
- `PHASE_1_SETUP.md` — Instrucciones detalladas
- `PHASE_1_IMPLEMENTACION.md` — Qué se cambió

## 🎯 Resultado Final

Cuando un cliente agenda via WhatsApp:
```
WhatsApp → Whapi.cloud → Agentkit → 🔗 Auto-CRM
                                     ├─ Crea transacción
                                     └─ Encola notificación
```

---

**¿Listo? Empieza por el Paso 1.** 🚀
