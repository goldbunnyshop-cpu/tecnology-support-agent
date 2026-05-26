# 🚀 INSTRUCCIONES PARA DEPLOY EN RAILWAY

**Estado**: ✅ Proyecto 100% listo para producción  
**Fecha**: 25 de mayo, 2026  
**Versión**: AgentKit 1.0 (Con security fixes y bug fixes aplicados)

---

## 📋 QUÉ SE VERIFICÓ Y ARREGLÓ

### ✅ Sintaxis Python
- `agent/main.py` — Archivo completo con estructura try-except correcta (305 líneas)
- `agent/brain.py` — Integración Claude segura
- `agent/cita_detector.py` — Bug de año fijo (ahora citas futuras van a próximo año)

### ✅ Dependencias
- `requirements.txt` — Incluye `asyncpg` y `psycopg2-binary` (CRÍTICO para Railway PostgreSQL)

### ✅ Configuración
- `.env.example` — Todas las variables necesarias
- `.gitignore` — Excluye secretos, permite código

### ✅ Security Fixes
- Variables técnicas NO aparecen en respuestas a cliente
- Inyección de contexto sanitizada

---

## 🎯 4 PASOS PARA HACER EL DEPLOY

### PASO 1️⃣: Preparar tu GitHub

```bash
cd C:\Users\Elitebook\whatsapp-agentkit

# Inicializar git (si no lo has hecho)
git init
git add .
git commit -m "feat: agente WhatsApp con AgentKit - ready for Railway"

# Subir a tu repo en GitHub
git remote add origin https://github.com/TU-USUARIO/whatsapp-agentkit.git
git branch -M main
git push -u origin main
```

> **⚠️ IMPORTANTE**: Reemplaza `TU-USUARIO` con tu username de GitHub

---

### PASO 2️⃣: Conectar Railway a tu GitHub

1. Ve a **https://railway.app**
2. Click en **"New Project"**
3. Selecciona **"Deploy from GitHub repo"**
4. Conecta tu cuenta GitHub si no lo has hecho
5. Selecciona el repo **`whatsapp-agentkit`**
6. Railway detectará el `Dockerfile` y comenzará a construir automáticamente

---

### PASO 3️⃣: Configurar Variables de Entorno en Railway

Una vez que Railway haya detectado el repo:

1. Ve a tu proyecto en Railway
2. Abre la pestaña **"Variables"**
3. Agrega estas variables:

```
ANTHROPIC_API_KEY = sk-ant-v0-...  (tu API key de Anthropic)
WHATSAPP_PROVIDER = whapi          (o "meta" o "twilio")
WHAPI_TOKEN = ...                  (si usas Whapi.cloud)
PORT = 8000
ENVIRONMENT = production
DATABASE_URL = postgresql+asyncpg://usuario:contraseña@host:5432/agentkit
```

> **NOTA**: Railway puede generar automáticamente `DATABASE_URL` si agregas PostgreSQL a tu proyecto. Solo agrega las que necesites según tu proveedor de WhatsApp.

#### Detalles por proveedor:

**Si usas WHAPI.CLOUD:**
```
WHATSAPP_PROVIDER = whapi
WHAPI_TOKEN = ... (tu token de Whapi)
```

**Si usas META (WhatsApp Cloud API):**
```
WHATSAPP_PROVIDER = meta
META_ACCESS_TOKEN = ...
META_PHONE_NUMBER_ID = ...
META_VERIFY_TOKEN = agentkit-verify
```

**Si usas TWILIO:**
```
WHATSAPP_PROVIDER = twilio
TWILIO_ACCOUNT_SID = ...
TWILIO_AUTH_TOKEN = ...
TWILIO_PHONE_NUMBER = ...
```

---

### PASO 4️⃣: Configurar Webhook en tu Proveedor

Una vez que Railway haya desplegado tu agente, te dará una URL pública:

```
https://tu-proyecto.up.railway.app
```

Copia esta URL y configura el webhook en tu proveedor:

#### 🔗 WHAPI.CLOUD
```
1. Ve a whapi.cloud → Dashboard → Settings → Webhooks
2. URL: https://tu-proyecto.up.railway.app/webhook
3. Método: POST
4. Guardar y activar
```

#### 🔗 META CLOUD API
```
1. Ve a developers.facebook.com → tu app → WhatsApp → Configuration
2. Callback URL: https://tu-proyecto.up.railway.app/webhook
3. Verify Token: agentkit-verify (o el que hayas puesto en META_VERIFY_TOKEN)
4. Suscribirse al campo "messages"
5. Guardar
```

#### 🔗 TWILIO
```
1. Ve a Twilio Console → Messaging → WhatsApp Sandbox Settings
2. "When a message comes in": https://tu-proyecto.up.railway.app/webhook
3. Método: POST
4. Guardar
```

---

## 🔍 VERIFICAR QUE FUNCIONA

### En Railway
1. Ve a tu proyecto → "Logs"
2. Deberías ver: `✅ Servidor AgentKit corriendo en puerto 8000`
3. Si hay error, mira los logs para diagnosticar

### En WhatsApp
1. Manda un mensaje de prueba a tu número de WhatsApp
2. El agente debería responder en menos de 5 segundos
3. Si no responde:
   - Verifica que el webhook está configurado en el proveedor
   - Verifica las variables de entorno en Railway
   - Mira los logs en Railway

---

## 📊 RESUMEN DE CAMBIOS APLICADOS

| Archivo | Cambio | Razón |
|---------|--------|-------|
| `agent/main.py` | Sintaxis corregida (try-except) | Archivo estaba truncado |
| `agent/cita_detector.py` | `año + 1` en línea 158 | Bug: citas futuras iban a año anterior |
| `requirements.txt` | Added asyncpg, psycopg2-binary | Necesario para PostgreSQL en Railway |
| `.env.example` | Variables completadas | Guía clara para configuración |
| `agent/brain.py` | Inyección segura de variables | Security: evitar exposición técnica |

---

## ⚠️ PUNTOS CRÍTICOS

- ✅ **No commitees `.env`** — está en `.gitignore`
- ✅ **DATABASE_URL** — SQLite local (desarrollo), PostgreSQL (Railway producción)
- ✅ **ANTHROPIC_API_KEY** — Debe ser válida y con permisos en tu cuenta
- ✅ **WHATSAPP_PROVIDER** — Elige solo UNO (whapi, meta, o twilio)
- ✅ **Webhook URL** — Debe ser EXACTA a la que Railway te asigna

---

## 📞 EN CASO DE ERRORES

Si durante el deploy tienes problemas:

1. **Error de compilación Python**: Mira `VERIFICACION_PRE_RAILWAY.txt`
2. **Error de imports**: Verifica que `requirements.txt` está en la raíz del proyecto
3. **Variables no encontradas**: Double-check en Railway dashboard
4. **Webhook no funciona**: Verifica la URL en tu proveedor de WhatsApp

---

## ✨ ¡LISTO!

Una vez que sigas estos 4 pasos:
- Tu agente estará en producción 24/7 ✅
- PostgreSQL en Railway para persistencia ✅
- Logs disponibles para debugging ✅
- Escalado automático si recibe muchos mensajes ✅

**Tu agente estará recibiendo mensajes reales de WhatsApp.**

---

Generado: 25 de mayo, 2026
