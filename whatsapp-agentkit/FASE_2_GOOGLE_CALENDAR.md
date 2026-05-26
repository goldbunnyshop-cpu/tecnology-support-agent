# FASE 2: Google Calendar Integration — Resumen

## ✅ Lo que se ha generado

### **1. Módulo de sincronización: `agent/google_calendar_sync.py`**
- Conecta con Google Calendar API
- Carga credenciales de `config/credentials.json`
- Función: `agregar_cita_a_calendar()` — sincroniza citas automáticamente
- Función: `obtener_proximas_citas()` — obtiene eventos próximos
- Función: `test_conexion()` — verifica que todo funciona

### **2. Actualización: `agent/cita_detector.py`**
- Ahora llama a `google_calendar_sync.agregar_cita_a_calendar()` automáticamente
- Cuando se agenda una cita en WhatsApp → aparece en Google Calendar
- Maneja errores gracefully (no detiene el flujo si Calendar falla)

### **3. Dependencias: `requirements.txt`**
```
+ google-auth-oauthlib>=1.2.0
+ google-auth-httplib2>=0.2.0
```

### **4. Documentación: `GOOGLE_CALENDAR_SETUP.md`**
- 6 pasos paso a paso para configurar Google Calendar
- Cómo crear Cuenta de Servicio
- Cómo generar credenciales JSON
- Cómo compartir tu calendario
- Troubleshooting completo

### **5. Script de test: `test_google_calendar.py`**
- Verifica que la conexión con Google Calendar funciona
- Crea una cita de prueba
- Lista las próximas citas

---

## 📋 **Próximos pasos (orden recomendado)**

### **PASO A: Obtener credenciales (5 minutos)**
Lee: `GOOGLE_CALENDAR_SETUP.md` siguiendo los pasos 1-4

Resultado: Tendrás un archivo `config/credentials.json` con tus credenciales

### **PASO B: Test local (2 minutos)**
```bash
pip install -r requirements.txt
python test_google_calendar.py
```

Deberías ver:
```
✅ Credenciales cargadas exitosamente
✅ Conexión exitosa — X calendarios encontrados
✅ Cita de prueba creada en Google Calendar
```

### **PASO C: Validación en WhatsApp (3 minutos)**
1. Envía un mensaje de prueba que trigger una cita:
   ```
   "Hola, necesito agendar una cita para mañana a las 3pm"
   ```

2. El agente responde confirmando la cita

3. Abre tu Google Calendar (https://calendar.google.com/) y busca el evento

4. Deberías ver algo como:
   ```
   🔧 [Cliente] — [Dispositivo]
   📅 [Fecha] [Hora]
   📝 Problema: [descripción]
   ```

### **PASO D: Deploy a Railway (2 minutos)**
```bash
# 1. Crear un .example del credentials
cp config/credentials.json config/credentials.json.example

# 2. Actualizar .gitignore (credentials.json ya debe estar)
# 3. Commit
git add .
git commit -m "feat: Google Calendar integration"
git push

# 4. En Railway:
# - Cargar config/credentials.json como volumen persistente O
# - Agregar variable de entorno GOOGLE_CREDENTIALS_PATH correcta
```

---

## 🔄 **Flujo completo (después de configurar)**

```
Cliente envía mensaje por WhatsApp
    ↓
AgentKit detecta solicitud de cita
    ↓
Guarda cita en BD (SQLite/PostgreSQL)
    ↓
Envía notificación al grupo "Taller Interno TS"
    ↓
✨ SINCRONIZA CON GOOGLE CALENDAR ✨ (NUEVO)
    ↓
Cita aparece en tu Google Calendar automáticamente
    ↓
Tu equipo ve la cita en tiempo real
```

---

## 📊 **Estado de las integraciones**

| Integración | Estado | Instalada |
|-----------|--------|-----------|
| Google Calendar | ✅ LISTA | Sí, `agent/google_calendar_sync.py` |
| Email (Recordatorios) | ⏳ SIGUIENTE | No |
| Google Sheets (Reportes) | ⏳ DESPUÉS | No |

---

## 🆘 **¿Algo no funciona?**

### ❌ "File not found: config/credentials.json"
→ Debes crear ese archivo con tus credenciales (ver GOOGLE_CALENDAR_SETUP.md PASO 2)

### ❌ "Invalid JSON in credentials"
→ El archivo está corrompido. Descárgalo de nuevo desde Google Cloud

### ❌ "Permission denied"
→ No compartiste tu Google Calendar con la Cuenta de Servicio (ver STEP 3)

### ❌ "Calendar not found"
→ Cambia `GOOGLE_CALENDAR_ID=primary` en tu .env

### ⚠️ Cita no aparece en Calendar pero sí en WhatsApp
→ Revisa los logs: `docker compose logs -f agent | grep CALENDAR`

---

## ✨ **Próximo: EMAIL INTEGRATION**

Una vez que Google Calendar funcione, continuaremos con:
- **Email de confirmación** al cliente cuando se agenda cita
- **Email diario** al equipo con resumen de citas
- **Recordatorios** 30 min antes de cada cita

---

**¿Listo?** Sigue GOOGLE_CALENDAR_SETUP.md y reporta cuando hayas creado `config/credentials.json`
