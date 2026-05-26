# ⚠️ CHECKLIST: CREDENCIALES NECESARIAS ANTES DE RAILWAY

**IMPORTANTE**: Debes tener TODAS estas credenciales configuradas ANTES de hacer el deploy.  
Sin ellas, Railway construirá el proyecto pero **el agente NO FUNCIONARÁ**.

---

## 🔑 CREDENCIALES OBLIGATORIAS

### 1️⃣ ANTHROPIC API KEY (CRÍTICO)
**¿Qué es?** Token para acceder a Claude API  
**¿Dónde obtenerla?**
```
1. Ve a https://console.anthropic.com
2. Login con tu cuenta de Anthropic
3. Settings → API Keys
4. Crea una nueva key (comienza con "sk-ant-v0-...")
5. Cópiala (solo aparece una vez)
```
**En Railway**: `ANTHROPIC_API_KEY = sk-ant-v0-...`  
**Estado**: ☐ Tengo mi API key lista

---

### 2️⃣ WHAPI TOKEN (CRÍTICO - para Whapi.cloud)
**¿Qué es?** Token para enviar/recibir mensajes en WhatsApp Business  
**¿Dónde obtenerlo?**
```
1. Ve a https://whapi.cloud
2. Login a tu cuenta
3. Dashboard → API Settings
4. Copia el "API Token" (largo string)
```
**En Railway**: `WHAPI_TOKEN = ...`  
**Estado**: ☐ Tengo mi WHAPI_TOKEN listo

**⚠️ SI CAMBIAS DE PROVEEDOR:**
- **Meta Cloud API**: Necesitas `META_ACCESS_TOKEN`, `META_PHONE_NUMBER_ID`, `META_VERIFY_TOKEN`
- **Twilio**: Necesitas `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_PHONE_NUMBER`

---

## 📊 CREDENCIALES OPCIONALES (pero recomendadas)

### 3️⃣ GOOGLE SERVICE ACCOUNT (Para Google Calendar)
**¿Para qué?** Sincronizar citas agendadas con tu Google Calendar  
**¿Dónde obtenerla?**
```
1. Ve a https://console.cloud.google.com
2. Crea un nuevo proyecto o usa uno existente
3. Habilita "Google Calendar API"
4. Crea una "Service Account"
5. Descarga el JSON de credenciales
6. Guarda el JSON en: config/google-service-account.json
```
**Estado**: ☐ Tengo JSON de Google descargado

### 4️⃣ RESEND API KEY (Para enviar emails con digest)
**¿Para qué?** Enviar resumen diario por email  
**¿Dónde obtenerla?** (Opcional)
```
1. Ve a https://resend.com
2. Sign up (gratis para desarrollo)
3. API Keys → Crea una nueva
4. Cópiala
```
**En Railway**: `RESEND_API_KEY = ...` (opcional)  
**Estado**: ☐ Lo quiero configurar / ☐ No lo necesito por ahora

---

## 🗂️ CHECKLIST ANTES DE HACER git push

```bash
# ANTES de git push, verifica que tienes:

☐ ANTHROPIC_API_KEY ready (sk-ant-v0-...)
☐ WHAPI_TOKEN ready (o META_* / TWILIO_* si usas otro)
☐ Google Service Account JSON (si quieres calendario)
☐ Archivo .env LOCAL con todas estas variables
☐ Archivo .env.example SIN valores secretos (solo templates)

# Verifica que .env está en .gitignore:
grep -i ".env" .gitignore    # Debe mostrar: .env
```

---

## 🚀 EL ORDEN CORRECTO

### Orden INCORRECTO (lo que yo sugerí):
```
1. git push a GitHub
2. Railway deploy
3. Luego agrega variables
❌ NO FUNCIONA — el agente falla en startup
```

### Orden CORRECTO:
```
1. ✅ Obtén TODAS tus credenciales
2. ✅ Verifica que funcionan LOCALMENTE (python tests/test_local.py)
3. ✅ git push a GitHub
4. ✅ Railway deploy
5. ✅ En Railway dashboard → Variables → agrega TODAS
6. ✅ Railway rebuilda automáticamente
7. ✅ Agente arranca exitosamente
```

---

## 🧪 VERIFICAR LOCALMENTE ANTES DE RAILWAY

```bash
cd C:\Users\Elitebook\whatsapp-agentkit

# Crea .env local (sin commitear)
cp .env.example .env
# Abre .env y completa:
# ANTHROPIC_API_KEY=sk-ant-...
# WHAPI_TOKEN=...

# Instala dependencias
pip install -r requirements.txt

# Test local (simula WhatsApp sin necesidad de números reales)
python tests/test_local.py

# Si funciona aquí, funcionará en Railway
```

---

## 📋 LISTA FINAL ANTES DE HACER PUSH

### Paso 0: Reunir credenciales
- [ ] ANTHROPIC_API_KEY obtenida y verificada
- [ ] WHAPI_TOKEN obtenida y verificada  
- [ ] Google JSON descargado (si lo quieres)
- [ ] Test local exitoso (`python tests/test_local.py`)

### Paso 1: Preparar repo
```bash
git init
git add .
# Verifica que .env NO se agrega:
git status | grep ".env"    # NO debe aparecer .env

git commit -m "feat: agente WhatsApp - listo para Railway"
git remote add origin https://github.com/TU-USUARIO/whatsapp-agentkit.git
git push -u origin main
```

### Paso 2: Railway
```
1. https://railway.app → New Project → Deploy from GitHub
2. Selecciona whatsapp-agentkit
3. Railway construye (2-5 minutos)
```

### Paso 3: Variables en Railway (AQUÍ ES DONDE VA TODO)
```
Railway Dashboard → tu proyecto → Variables

ANTHROPIC_API_KEY = sk-ant-v0-...
WHATSAPP_PROVIDER = whapi
WHAPI_TOKEN = ...
PORT = 8000
ENVIRONMENT = production
DATABASE_URL = postgresql+asyncpg://... (Railway genera esto)
```

### Paso 4: Webhook
```
Whapi.cloud → Settings → Webhooks
URL: https://tu-proyecto.up.railway.app/webhook
Método: POST
```

### Paso 5: Test
```
Manda un mensaje WhatsApp
Verifica logs en Railway dashboard
Debe aparecer: "✅ Servidor AgentKit corriendo en puerto 8000"
```

---

## ⚠️ PUNTOS CRÍTICOS QUE ME FALTÓ MENCIONAR

1. **El agente NO puede iniciar sin ANTHROPIC_API_KEY**
   - Si no está, Railway mostrará error en logs: `ANTHROPIC_API_KEY not found`
   
2. **Sin WHAPI_TOKEN no recibe mensajes**
   - Railway correrá, pero ningún mensaje llegará
   - Webhook nunca será llamado

3. **Google Calendar es EXTRA**
   - Sin JSON de Google: el agente sigue funcionando
   - Solo no puede agendar en calendario
   - (Las citas se guardan en la BD de todas formas)

4. **Las credenciales NUNCA deben ir en código**
   - SIEMPRE en variables de entorno
   - SIEMPRE en .env local (no committed)
   - SIEMPRE en Railway dashboard (no en Dockerfile)

5. **Si cambias de proveedor WhatsApp**
   - Cambia WHATSAPP_PROVIDER en .env
   - Agrega las variables del nuevo proveedor
   - El código es agnóstico (funciona con los 3)

---

## 🎯 RESUMEN: ¿QUÉ NECESITAS AHORA?

| Credencial | Prioridad | Tengo | Dónde |
|-----------|-----------|-------|-------|
| ANTHROPIC_API_KEY | 🔴 CRÍTICA | ☐ | console.anthropic.com |
| WHAPI_TOKEN | 🔴 CRÍTICA | ☐ | whapi.cloud |
| Google JSON | 🟡 Recomendada | ☐ | console.cloud.google.com |
| RESEND_API_KEY | 🟢 Opcional | ☐ | resend.com |

---

## ✅ SIGUIENTES PASOS

1. **Obtén** ANTHROPIC_API_KEY y WHAPI_TOKEN
2. **Verifica** localmente: `python tests/test_local.py`
3. **Cuando funcione localmente**, entonces sí:
   - `git push` a GitHub
   - Railway deploy
   - Variables en dashboard

**Si salteas la verificación local, Railway también fallará.**

---

Generado: 25 de mayo, 2026  
Para: Christian (goldbunnyshop@gmail.com)
