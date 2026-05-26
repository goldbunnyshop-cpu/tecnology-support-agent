# 🚀 RAILWAY DEPLOY — VERSIÓN CORRECTA

**Para**: Christian (email: goldbunnyshop@gmail.com)  
**Referencia**: tecnology-support-agent-production.up.railway.app  
**Contexto**: Ya conoces Railway. Esto solo te dice QUÉ EXACTAMENTE necesitas.

---

## ⚠️ EL ERROR DE MIS INSTRUCCIONES ANTERIORES

**Yo dije:**
```
1. git push
2. Railway deploy
3. Luego agrega variables
```

**Esto está MAL** porque:
- Railway construirá el proyecto ✓
- Pero el agente NO ARRANCARÁ en startup
- Faltarán: ANTHROPIC_API_KEY, WHAPI_TOKEN

---

## ✅ EL FLUJO CORRECTO

### ANTES de cualquier cosa: **Verifica localmente**

```bash
cd C:\Users\Elitebook\whatsapp-agentkit

# 1. Obtén tus credenciales (de Anthropic y Whapi)
# 2. Crea .env local
cat > .env << EOF
ANTHROPIC_API_KEY=sk-ant-v0-...
WHATSAPP_PROVIDER=whapi
WHAPI_TOKEN=...
PORT=8000
ENVIRONMENT=development
DATABASE_URL=sqlite+aiosqlite:///./agentkit.db
EOF

# 3. Test local
pip install -r requirements.txt
python tests/test_local.py
```

**Si falla localmente, fallará en Railway.**  
**Si funciona localmente, funcionará en Railway.**

---

### CUANDO funcione localmente: git + Railway

```bash
# .env NO va en Git
grep "\.env" .gitignore    # Debe existir .env aquí

# Push (sin .env)
git init
git add .
git commit -m "feat: agente WhatsApp - verified locally"
git remote add origin https://github.com/TU-USUARIO/whatsapp-agentkit.git
git push -u origin main

# Railway
# 1. Dashboard → New Project → Deploy from GitHub → whatsapp-agentkit
# 2. Railway construye (2-5 min)
```

---

### EN Railway dashboard: Variables

```
ANTHROPIC_API_KEY = sk-ant-v0-...
WHATSAPP_PROVIDER = whapi
WHAPI_TOKEN = ...
PORT = 8000
ENVIRONMENT = production
DATABASE_URL = postgresql+asyncpg://[auto-generated por Railway]
```

**Luego Railway auto-redeploy y el agente arranca.**

---

## 🔑 CREDENCIALES EXACTAS QUE NECESITAS

### OBLIGATORIAS (sin éstas, no funciona):

```
1. ANTHROPIC_API_KEY
   - De: https://console.anthropic.com/settings/keys
   - Comienza con: sk-ant-v0-
   - Acción: Cópiala, usa en .env local, verifica con test_local.py

2. WHAPI_TOKEN  
   - De: https://whapi.cloud → Dashboard → API Settings
   - Acción: Cópialo, usa en .env local, verifica con test_local.py
```

**NO HAGAS GIT PUSH HASTA QUE AMBAS FUNCIONEN LOCALMENTE.**

---

### OPCIONALES (el agente funciona sin éstas):

```
3. Google Service Account JSON
   - Necesario SOLO si quieres sincronizar Google Calendar
   - Archivo debe ir en: config/google-service-account.json
   - Si no lo tienes: agente sigue funcionando, solo no agenda en calendar

4. RESEND_API_KEY  
   - Necesario SOLO si quieres digest diario por email
   - Opcional: agente funciona sin esto
```

---

## 🧪 PRUEBA LOCAL EXACTA

```bash
# Paso 1: Preparar .env
cp .env.example .env
nano .env  # Edita y agrega:
# ANTHROPIC_API_KEY=sk-ant-v0-... (tu key real)
# WHAPI_TOKEN=... (tu token real)

# Paso 2: Instalar
pip install -r requirements.txt

# Paso 3: Test interactivo (simula WhatsApp sin servidor real)
python tests/test_local.py

# Escribe mensajes de prueba:
# "Hola, ¿cuál es tu nombre?"
# "Quiero agendar una cita"
# "Cuáles son tus precios?"

# Ctrl+C para salir
```

**Si ves respuestas del agente → está listo para Railway**  
**Si da error → falta credencial o tiene error de código**

---

## 📊 DECISIÓN DE PROVEEDOR WHATSAPP

**Tu actual**: Whapi.cloud  
**Configuración**:
```
WHATSAPP_PROVIDER = whapi
WHAPI_TOKEN = [tu token]
```

**Si cambias a Meta**:
```
WHATSAPP_PROVIDER = meta
META_ACCESS_TOKEN = ...
META_PHONE_NUMBER_ID = ...
META_VERIFY_TOKEN = agentkit-verify
```

**Si cambias a Twilio**:
```
WHATSAPP_PROVIDER = twilio
TWILIO_ACCOUNT_SID = ...
TWILIO_AUTH_TOKEN = ...
TWILIO_PHONE_NUMBER = ...
```

El código es agnóstico. Solo cambia las variables.

---

## 📋 CHECKLIST FINAL

```
ANTES DE GIT PUSH:
☐ ANTHROPIC_API_KEY obtenida (console.anthropic.com)
☐ WHAPI_TOKEN obtenida (whapi.cloud)
☐ .env local creado con ambas
☐ python tests/test_local.py funciona
☐ Agente responde mensajes de prueba localmente

DESPUÉS DE GIT PUSH:
☐ Repository en GitHub public
☐ Railway Dashboard → Variables agregadas
☐ Railway auto-rebuildeó
☐ Logs muestran: "✅ Servidor AgentKit corriendo en puerto 8000"

CONFIGURAR WEBHOOK:
☐ Whapi.cloud → Webhooks → URL: https://tu-app.up.railway.app/webhook
☐ Test: envía mensaje WhatsApp real
☐ Verificar logs en Railway
```

---

## 🆘 TROUBLESHOOTING

| Problema | Causa | Solución |
|----------|-------|----------|
| `ANTHROPIC_API_KEY not found` en Railway logs | Variable no está en dashboard | Agrega en Railway → Variables |
| Mensajes no llegan al agente | Webhook no está configurado | Ve a Whapi → Settings → Webhooks |
| Error en `tests/test_local.py` | WHAPI_TOKEN inválido | Verifica en whapi.cloud que sea el token correcto |
| "Connection refused" localmente | Falta `pip install -r requirements.txt` | Instala dependencias |
| Railway falla en deployment | Falta PostgreSQL | Agrega PostgreSQL add-on en Railway |

---

## 📞 RESUMEN PARA TI

1. **Obtén credenciales** (Anthropic + Whapi)
2. **Verifica localmente** (python tests/test_local.py)
3. **Cuando funcione local** → git push
4. **Railway** → agrega variables en dashboard
5. **Configura webhook** en Whapi
6. **Test con mensaje real** de WhatsApp

**Eso es todo.**

---

Generado: 25 de mayo, 2026 - 16:45  
Por: Claude (reconociendo el error)
