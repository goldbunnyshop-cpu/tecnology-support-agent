# Documentación de Errores Resueltos
## AgentKit WhatsApp — Whapi Integration & Root Directory Setup

---

## 1️⃣ ERRORES DE WHAPI.CLOUD

### **Error 1.1: Autenticación Fallida (401 Unauthorized)**

**Síntoma:**
```
Error Whapi: 401 — Invalid or expired token
```

**Causa:**
- Token de API expirado o inválido en `.env`
- Typo en `WHAPI_TOKEN`
- Token copiado con espacios en blanco extras

**Solución:**
1. Ve a [whapi.cloud](https://whapi.cloud) dashboard
2. Copia el token EXACTAMENTE sin espacios:
   ```env
   # ❌ INCORRECTO
   WHAPI_TOKEN= sk_wh_abc123...    # (espacios antes/después)
   WHAPI_TOKEN=sk_wh_abc123 ...    # (espacio en el medio)
   
   # ✅ CORRECTO
   WHAPI_TOKEN=sk_wh_abc123xyz
   ```
3. Recarga las variables: `python -m dotenv`
4. Prueba la conexión:
   ```bash
   python -c "
   import os
   from dotenv import load_dotenv
   load_dotenv()
   token = os.getenv('WHAPI_TOKEN')
   print('Token present:', bool(token))
   print('Token length:', len(token) if token else 0)
   "
   ```

**Archivo afectado:** `.env`

---

### **Error 1.2: Webhook URL No Registrado en Whapi**

**Síntoma:**
```
Mensajes no llegan al bot
Whapi dashboard muestra "Webhook URL: Not configured"
```

**Causa:**
- URL del webhook no registrada en Whapi.cloud
- URL incorrecta en configuración de Whapi
- URL no es HTTPS o está detrás de proxy/firewall

**Solución:**

#### **Para Railway (Producción):**
1. Obtén la URL pública de Railway:
   ```
   https://tu-app-nombre.up.railway.app
   ```
2. Ve a Whapi.cloud → Settings → Webhooks
3. Configura:
   - **Webhook URL:** `https://tu-app-nombre.up.railway.app/webhook`
   - **Method:** POST
   - **Events:** `message.created` (o todos los que necesites)
4. Haz un test ping desde Whapi
5. Verifica en Railway logs:
   ```
   [INFO] Webhook parseado. Mensajes recibidos: 1
   ```

#### **Para Local (Testing):**
1. Usa ngrok para exponer localhost:
   ```bash
   ngrok http 8000
   # Output: https://abc123.ngrok.io → http://localhost:8000
   ```
2. En Whapi → Webhook URL: `https://abc123.ngrok.io/webhook`
3. El token ngrok es temporal (cambia cada sesión)

**Archivo afectado:** `agent/main.py` (línea 77: `@app.post("/webhook")`)

---

### **Error 1.3: Mensajes JSON Malformados**

**Síntoma:**
```
JSONDecodeError: Expecting value: line 1 column 1
Error in webhook: Invalid JSON payload
```

**Causa:**
- Whapi envía payload en formato incorrecto
- Caracteres especiales no escapados
- Content-Type header no es `application/json`

**Solución:**

**En `agent/providers/whapi.py`:**
```python
async def parsear_webhook(self, request: Request) -> list[MensajeEntrante]:
    """
    Parsea el payload de Whapi.cloud con manejo robusto de errores.
    """
    try:
        body = await request.json()
    except json.JSONDecodeError as e:
        logger.error(f"Error parseando JSON de Whapi: {e}")
        # Intenta como form data
        try:
            form = await request.form()
            body = dict(form)
        except:
            logger.error("No se pudo parsear webhook como JSON ni como form-data")
            return []
    
    mensajes = []
    for msg in body.get("messages", []):
        try:
            mensajes.append(MensajeEntrante(
                telefono=msg.get("chat_id", "").strip(),
                texto=msg.get("text", {}).get("body", "").strip(),
                mensaje_id=msg.get("id", ""),
                es_propio=msg.get("from_me", False),
            ))
        except Exception as e:
            logger.warning(f"Error parseando mensaje individual: {e}")
            continue
    
    return mensajes
```

**Verificación en logs:**
```
✅ Webhook parseado. Mensajes recibidos: 1
```

---

### **Error 1.4: Caracteres UTF-8 Corrupto (Emojis, Acentos)**

**Síntoma:**
```
UnicodeDecodeError: 'utf-8' codec can't decode byte...
Mensajes con tildes/emojis llegan vacíos
```

**Causa:**
- Whapi envía con encoding diferente a UTF-8
- Response headers sin charset correcto

**Solución:**

**En `agent/main.py` lifespan:**
```python
import sys
import io

# Forzar UTF-8 en startup
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

app = FastAPI(
    title="AgentKit",
    ...
)

# Headers explícitos de response
@app.middleware("http")
async def add_charset_header(request: Request, call_next):
    response = await call_next(request)
    response.headers["Content-Type"] = "application/json; charset=utf-8"
    return response
```

**Verificación:**
```python
# Test con emojis
texto = "Hola 😊 ¿Cómo estás? 👍"
print(f"Texto recibido: {texto}")  # Debe mostrar correctamente
```

---

### **Error 1.5: Rate Limiting (429 Too Many Requests)**

**Síntoma:**
```
Error Whapi: 429 — Too many requests
Mensajes se pierden después de flujo alto
```

**Causa:**
- Límite de API de Whapi alcanzado (típicamente 100 req/min)
- Sin manejo de backoff exponencial

**Solución:**

**En `agent/providers/whapi.py`:**
```python
import asyncio
from tenacity import retry, stop_after_attempt, wait_exponential

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10)
)
async def enviar_mensaje(self, telefono: str, mensaje: str) -> bool:
    """Envía con retry automático si llega al rate limit."""
    if not self.token:
        logger.warning("WHAPI_TOKEN no configurado")
        return False
    
    headers = {
        "Authorization": f"Bearer {self.token}",
        "Content-Type": "application/json",
    }
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            r = await client.post(
                self.url_envio,
                json={"to": telefono, "body": mensaje},
                headers=headers,
            )
            
            if r.status_code == 429:
                logger.warning(f"Rate limit hit. Reintentando...")
                raise Exception("Rate limited")
            
            if r.status_code == 200:
                logger.info(f"✅ Mensaje enviado a {telefono}")
                return True
            else:
                logger.error(f"Error Whapi: {r.status_code} — {r.text}")
                return False
                
        except asyncio.TimeoutError:
            logger.error(f"Timeout enviando a {telefono}")
            return False
```

**Agregar a requirements.txt:**
```
tenacity>=8.2.0
```

---

### **Error 1.6: Webhook No Procesa Mensajes de Grupo**

**Síntoma:**
```
Mensajes en grupos no llegan al bot
Solo funcionan chats 1:1
```

**Causa:**
- Whapi está configurado para ignorar grupos por defecto
- Webhook filter está limitado a chats individuales

**Solución:**

**En Whapi.cloud dashboard:**
1. Settings → Webhooks → Advanced
2. Enable: `messages.group` y `messages.individual`
3. Webhook debe procesar ambos:
   ```json
   {
     "messages": [
       {
         "chat_id": "+5215551234567",        // Chat individual
         "chat_id": "+52xxx-12345@g.us"      // Chat de grupo (con @g.us)
       }
     ]
   }
   ```

**En `agent/providers/whapi.py`:**
```python
async def parsear_webhook(self, request: Request) -> list[MensajeEntrante]:
    body = await request.json()
    mensajes = []
    
    for msg in body.get("messages", []):
        chat_id = msg.get("chat_id", "")
        
        # Procesa grupos y chats 1:1
        if "@g.us" in chat_id:
            logger.info(f"Mensaje de grupo detectado: {chat_id}")
        
        mensajes.append(MensajeEntrante(
            telefono=chat_id,  # Incluye @g.us si es grupo
            texto=msg.get("text", {}).get("body", ""),
            mensaje_id=msg.get("id", ""),
            es_propio=msg.get("from_me", False),
        ))
    
    return mensajes
```

---

## 2️⃣ ERRORES DE CONFIGURACIÓN Y ROOT DIRECTORY

### **Error 2.1: ModuleNotFoundError - agent.main**

**Síntoma:**
```
ModuleNotFoundError: No module named 'agent'
Cannot find python module: agent.main
```

**Causa:**
- Python no está buscando en el directorio correcto
- `__init__.py` falta en carpetas
- PYTHONPATH no está configurado correctamente

**Solución:**

**Paso 1: Crear `__init__.py` en todas las carpetas:**
```bash
touch agent/__init__.py
touch agent/providers/__init__.py
touch tests/__init__.py
touch config/__init__.py
```

**Paso 2: Desde el ROOT del proyecto, ejecuta:**
```bash
# ❌ INCORRECTO
cd agent
python main.py

# ✅ CORRECTO
cd /path/to/whatsapp-agentkit
python -m agent.main
# O
uvicorn agent.main:app --reload --port 8000
```

**Paso 3: Verifica PYTHONPATH:**
```bash
python -c "import sys; print('\n'.join(sys.path))"
# Debe incluir el directorio raíz del proyecto
```

**Paso 4: En Railway .env, asegura:**
```env
PYTHONUNBUFFERED=1
PYTHONPATH=/app
```

**Archivos afectados:**
- `agent/__init__.py` — debe existir
- `agent/providers/__init__.py` — debe existir
- `Dockerfile` — working directory correcto

---

### **Error 2.2: ImportError en Ciclos Circulares**

**Síntoma:**
```
ImportError: cannot import name 'generar_respuesta' from 'agent.brain'
during handling of the above exception, another exception occurred
```

**Causa:**
- Importación circular: `main.py` → `brain.py` → `memory.py` → `main.py`
- Orden incorrecto de imports

**Solución:**

**Estructura CORRECTA de imports (`agent/main.py`):**
```python
# 1. Imports estándar
import os
import logging
import random
from datetime import datetime
from contextlib import asynccontextmanager

# 2. Imports de terceros
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import PlainTextResponse
from dotenv import load_dotenv

# 3. Imports locales (en este orden)
from agent.providers import obtener_proveedor  # ← Primero (no depende de nada)
from agent.memory import inicializar_db, guardar_mensaje, obtener_historial  # ← Segundo
from agent.brain import generar_respuesta  # ← Tercero (depende de memory)
from agent.sleep_mode import (...)  # ← Después
from agent.profile import (...)  # ← Después

load_dotenv()  # ← DESPUÉS de imports
```

**Verificar ciclos:**
```bash
python -m py_compile agent/main.py
python -c "import agent.main"  # Sin errores = OK
```

---

### **Error 2.3: FileNotFoundError - .env o config/prompts.yaml**

**Síntoma:**
```
FileNotFoundError: [Errno 2] No such file or directory: '.env'
FileNotFoundError: [Errno 2] No such file or directory: 'config/prompts.yaml'
```

**Causa:**
- Working directory es incorrecto cuando se inicia la app
- Rutas relativas en lugar de rutas absolutas

**Solución:**

**En `agent/main.py` - lifespan():**
```python
import os

# Detectar root directory automáticamente
ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_DIR = os.path.join(os.path.dirname(ROOT_DIR), "config")

# Cambiar working directory
os.chdir(os.path.dirname(ROOT_DIR))

# Usar rutas absolutas
ENV_PATH = os.path.join(os.path.dirname(ROOT_DIR), ".env")
PROMPTS_PATH = os.path.join(CONFIG_DIR, "prompts.yaml")

load_dotenv(ENV_PATH)

@asynccontextmanager
async def lifespan(app: FastAPI):
    if not os.path.exists(PROMPTS_PATH):
        logger.error(f"❌ config/prompts.yaml no encontrado en {PROMPTS_PATH}")
        logger.info(f"Current working directory: {os.getcwd()}")
        raise FileNotFoundError(f"prompts.yaml no existe en {PROMPTS_PATH}")
    
    await inicializar_db()
    logger.info("✅ Configuración cargada correctamente")
    yield
```

**En `agent/brain.py`:**
```python
import os

def cargar_config_prompts() -> dict:
    """Lee config con ruta absoluta."""
    config_path = os.path.join(
        os.path.dirname(os.path.dirname(__file__)),
        "config",
        "prompts.yaml"
    )
    
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except FileNotFoundError:
        logger.error(f"❌ Config no encontrado en: {config_path}")
        logger.info(f"CWD actual: {os.getcwd()}")
        return {}
```

**Verificar estructura:**
```bash
# Desde raíz del proyecto
ls -la .env config/prompts.yaml agent/__init__.py
# Todos deben existir
```

---

### **Error 2.4: Railway — Build Falla por PYTHONPATH**

**Síntoma:**
```
remote: Build error: ModuleNotFoundError: No module named 'agent'
remote: ERROR: failed to build image
```

**Causa:**
- Dockerfile no establece PYTHONPATH correctamente
- Working directory incorrecto en Dockerfile

**Solución:**

**Dockerfile CORRECTO:**
```dockerfile
FROM python:3.11-slim

WORKDIR /app

# ✅ Establecer PYTHONPATH
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

# Copiar requirements y instalar
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar código
COPY . .

# Exposer puerto
EXPOSE 8000

# CMD correcto
CMD ["uvicorn", "agent.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

**En Railway .env:**
```env
PYTHONPATH=/app
PYTHONUNBUFFERED=1
```

---

### **Error 2.5: Permisos Insuficientes en Database**

**Síntoma:**
```
PermissionError: [Errno 13] Permission denied: './agentkit.db'
sqlite3.OperationalError: attempt to write a readonly database
```

**Causa:**
- Archivo DB sin permisos de escritura
- Directorio sin permisos de ejecución

**Solución:**

```bash
# Dar permisos correctos
chmod 644 agentkit.db      # Lectura/escritura
chmod 755 .                # Ejecución en carpeta

# O regenerar la DB
rm agentkit.db
python -c "from agent.memory import inicializar_db; asyncio.run(inicializar_db())"
```

**En Railway:**
Railway maneja permisos automáticamente. Si falla, verifica que DATABASE_URL esté correcta:
```env
# ✅ SQLite (Railway ephemeral storage)
DATABASE_URL=sqlite+aiosqlite:///./agentkit.db

# ✅ PostgreSQL (Railway managed)
DATABASE_URL=postgresql+asyncpg://user:pass@host:port/dbname
```

---

## 3️⃣ WORKFLOW COMPLETO DESDE EL INICIO

### **Flujo de Deployment — Desde cero a producción**

```
┌─────────────────────────────────────────────────┐
│ FASE 1: SETUP LOCAL                             │
└─────────────────────────────────────────────────┘

1. Clone repo
   git clone https://github.com/tuusuario/whatsapp-agentkit.git
   cd whatsapp-agentkit

2. Crear .env
   cp .env.example .env
   # Editar: WHAPI_TOKEN, ANTHROPIC_API_KEY

3. Instalar dependencias
   pip install -r requirements.txt

4. Crear estructura de carpetas
   mkdir -p agent/providers config knowledge tests
   touch agent/__init__.py agent/providers/__init__.py

5. Test local
   python tests/test_local.py  # Chat en terminal

   
┌─────────────────────────────────────────────────┐
│ FASE 2: CONFIGURAR WHAPI.CLOUD                  │
└─────────────────────────────────────────────────┘

1. Crear cuenta en whapi.cloud
2. Obtener API Token (Settings → API Keys)
3. Copiar a .env: WHAPI_TOKEN=sk_wh_xxxxx
4. NO configurar webhook aún (falta URL pública)

   
┌─────────────────────────────────────────────────┐
│ FASE 3: PUSH A GITHUB                           │
└─────────────────────────────────────────────────┘

git add .
git commit -m "feat: whapi integration v1.0"
git push origin main

   
┌─────────────────────────────────────────────────┐
│ FASE 4: DEPLOY A RAILWAY                        │
└─────────────────────────────────────────────────┘

1. Ir a railway.app
2. New Project → GitHub → Seleccionar repo
3. Variables de entorno (Railway Dashboard):
   - ANTHROPIC_API_KEY = sk-ant-...
   - WHAPI_TOKEN = sk_wh_...
   - DATABASE_URL = sqlite+aiosqlite:///./agentkit.db
   - ENVIRONMENT = production
   - PORT = 8000
   - PYTHONPATH = /app

4. Railway despliega automáticamente
5. Obtener URL pública: https://mi-app.up.railway.app

   
┌─────────────────────────────────────────────────┐
│ FASE 5: CONFIGURAR WEBHOOK EN WHAPI             │
└─────────────────────────────────────────────────┘

1. whapi.cloud Dashboard → Settings → Webhooks
2. Webhook URL: https://mi-app.up.railway.app/webhook
3. Method: POST
4. Events: message.created, message.updated
5. Click "Test"
6. Ver en Railway logs: [INFO] Webhook parseado

   
┌─────────────────────────────────────────────────┐
│ FASE 6: TEST END-TO-END                         │
└─────────────────────────────────────────────────┘

1. Enviar mensaje a tu número de prueba en Whapi sandbox
2. Ver en Railway logs:
   ✅ Webhook parseado. Mensajes recibidos: 1
   📱 Mensaje recibido de +5215551234567: 'Hola'
   ✅ Respuesta generada
   ✅ Respuesta enviada a +5215551234567

3. Recibir respuesta en Whapi sandbox

   
┌─────────────────────────────────────────────────┐
│ FASE 7: MONITOREO CONTINUO                      │
└─────────────────────────────────────────────────┘

Railway Logs — Buscar:
✅ "[SLEEP]" — Detección de sleep mode
✅ "[REACTIVACIÓN SLEEP]" — Jobs programados
❌ "Error" — Problemas en ejecución
❌ "ModuleNotFoundError" — Issues de imports
```

---

## 📊 Tabla de Errores por Ubicación

| Error | Síntoma | Archivo Afectado | Solución |
|-------|---------|------------------|----------|
| **Token inválido** | 401 Unauthorized | `.env` | Copiar token exactamente, sin espacios |
| **Webhook no registrado** | Mensajes no llegan | Whapi dashboard | Registrar URL en Whapi settings |
| **JSON malformado** | JSONDecodeError | `whapi.py` | Agregar try/except en parsear_webhook |
| **UTF-8 corrupto** | UnicodeDecodeError | `main.py` | Forzar UTF-8 en startup |
| **Rate limiting** | 429 Too Many Requests | `whapi.py` | Agregar retry con backoff |
| **Module not found** | ModuleNotFoundError | Toda la app | Crear `__init__.py`, usar rutas absolutas |
| **Config no encontrado** | FileNotFoundError | `brain.py` | Usar rutas absolutas desde root |
| **Permisos DB** | Permission denied | `memory.py` | Regenerar DB o chmod 644 |
| **Dockerfile fail** | Build error en Railway | `Dockerfile` | Establecer PYTHONPATH=/app |

---

## ✅ Checklist Post-Deployment

- [ ] Whapi token es válido (test 401)
- [ ] Webhook URL registrada en Whapi
- [ ] Railway URL configurada en webhook
- [ ] Python path correcto en todas partes
- [ ] `.env` tiene todas las variables
- [ ] `config/prompts.yaml` existe
- [ ] Estructura de carpetas completa
- [ ] Test de mensaje funciona end-to-end
- [ ] Logs limpios (sin errores)
- [ ] Database creada y accesible

---

**Última actualización:** 21 de Mayo, 2026
**Status:** Documentación completa de errores y soluciones
