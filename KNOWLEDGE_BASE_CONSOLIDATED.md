# 🎯 AGENTKIT TECHNOLOGY SUPPORT — KNOWLEDGE BASE CONSOLIDADA

**Última actualización:** 2 de junio de 2026  
**Estado:** ✅ Producción 95% funcional | 🔄 Integración Google Sheets en progreso  
**Ubicación producción:** Railway — `technology-support-agent-production.up.railway.app`

---

## 📋 TABLA DE CONTENIDOS

1. [Resumen Ejecutivo](#resumen-ejecutivo)
2. [Estado Actual](#estado-actual)
3. [Arquitectura del Sistema](#arquitectura-del-sistema)
4. [Fuentes de Precios](#fuentes-de-precios)
5. [Setup & Deployment](#setup--deployment)
6. [Próximos Pasos](#próximos-pasos)
7. [Troubleshooting](#troubleshooting)

---

## RESUMEN EJECUTIVO

### 📊 Métricas de Salud

| Métrica | Estado |
|---------|--------|
| **Webhook WhatsApp** | ✅ Funcionando (Whapi) |
| **Claude AI** | ✅ claude-sonnet-4-6 integrado |
| **Google Calendar** | ✅ Agendar citas automáticas |
| **Base de datos** | ✅ PostgreSQL (Railway) + SQLite (Local) |
| **Deploy** | ✅ Railway automático |
| **Líneas de código** | 15,000+ (27 módulos Python) |
| **Bloqueadores críticos** | ❌ 0 (ninguno) |

### ✅ LO QUE ESTÁ HECHO

**Core Features:**
- ✅ Recibir mensajes WhatsApp vía Whapi.cloud
- ✅ Procesar con Claude AI (claude-sonnet-4-6)
- ✅ Agendar citas automáticas en Google Calendar
- ✅ Crear y clasificar leads automáticamente
- ✅ Sleep mode (pausa 00:00-06:30)
- ✅ Pausa manual desde grupo interno
- ✅ Análisis de imágenes (Vision)
- ✅ Notificaciones al grupo interno
- ✅ Seguimiento y retomas automáticas
- ✅ Sistema STOP/ON (bloqueo de números)
- ✅ Fallback MercadoLibre para precios

**Infraestructura:**
- ✅ Despliegue en Railway
- ✅ Base de datos PostgreSQL (cloud) + SQLite (local)
- ✅ Docker container
- ✅ Logs y monitoreo
- ✅ Health checks

### ⏳ LO QUE FALTA (5% del proyecto)

**ALTA PRIORIDAD (Esta semana):**
1. **Integración Google Sheets** — Consolidar 3 fuentes de precios
   - Impacto: Menú completo de precios desde Google Sheets
   - Esfuerzo: 4-6 horas
   - Estado: Hojas exploradas, estructura mapeada
   - Hojas a integrar: Displays (18 items) | Baterías Android (212 items) | Baterías iPhone (99 items)

2. **Auto-CRM Sync** — Sincronizar leads con Auto-CRM
   - Impacto: Todos los leads en un solo lugar
   - Esfuerzo: 3-4 horas
   - Estado: Módulos creados, no integrados

**MEDIA PRIORIDAD (Próximas 2 semanas):**
3. **Performance Calendar** — Caché de slots para búsqueda rápida
   - Esfuerzo: 2 horas
   - Estado: Optimizable

**BAJA PRIORIDAD:**
4. **Comandos** — Permitir `/reportes`, `/stats` en WhatsApp
   - Esfuerzo: 1.5-2 horas

---

## ESTADO ACTUAL

### 🔧 Cambios Realizados (Junio 2026)

**Hoy implementado:**
1. ✅ Sistema STOP/ON (bloqueo permanente de números)
2. ✅ Integración MercadoLibre como fallback de Hugo Shop
3. ✅ Documentación completa de ambos sistemas

**Archivos nuevos:**
- `agent/pricing_integration.py` — 150 líneas, integración Hugo+ML
- `agent/commands_control.py` — 180 líneas, procesamiento STOP/ON
- Tests completos para ambos sistemas

**Archivos modificados:**
- `agent/memory.py` — Nueva tabla `StoppedNumber`
- `agent/main.py` — Integración STOP/ON en webhook
- `agent/brain.py` — Import + 3 líneas para pricing integrado

---

## ARQUITECTURA DEL SISTEMA

```
WhatsApp Cliente
    ↓
Agent Webhook (Whapi)
    ├─ Sleep Mode (00:00-06:30)
    ├─ Pausa Manual (pausa: NÚMERO)
    ├─ STOP/ON (stop: NÚMERO) ← Bloqueo permanente
    ├─ Commands (cita, cotización, lead)
    ├─ Pricing Pipeline ← MEJORA EN PROGRESO
    │   ├─ Hugo Shop (primero)
    │   ├─ Google Sheets (nuevo) ← EN PROGRESO
    │   └─ MercadoLibre (fallback)
    ├─ Vision (análisis de imágenes)
    ├─ Smart Reminders
    └─ CRM Sync

Salida:
    ├─ WhatsApp Response
    ├─ Google Calendar (citas)
    ├─ Auto-CRM (leads)
    └─ Email (notificaciones)
```

---

## FUENTES DE PRECIOS

### 🔄 PIPELINE DE PRECIOS (Versión 2 - EN CONSTRUCCIÓN)

#### 1️⃣ Hugo Shop (Primaria)
- **URL:** https://hugoshop.com.mx
- **Método:** Web scraping
- **Estructura:** Genérico (precio bajo) / Original (precio alto)
- **Estado:** ✅ Funcionando
- **Casos cubiertos:** Displays, Baterías Android, Baterías iPhone, Tapas, Glass

**Ejemplo:**
```
Cliente: "¿Precio batería iPhone 15?"
Hugo Shop: ✅ Encontrado
Respuesta: "Batería iPhone 15: $XXX (genérica) o $YYY (original)"
```

#### 2️⃣ Google Sheets (Nueva - EN PROGRESO)
- **URL:** https://docs.google.com/spreadsheets/d/1sMVr7rUp2dz_4h4NUEwFjH-iVqOjUWjJNYx5ptfgT2U/edit
- **Acceso:** Sheet API (con credenciales: `tecnologysupportmx@gmail.com`)
- **Método:** Lectura directa de API
- **Estructura:** Múltiples hojas, cada una con estructura diferente
- **Estado:** 🔄 Mapeado, pendiente integración

**Hojas prioritarias:**

| Hoja | Rows | Items | Estructura |
|------|------|-------|-----------|
| **DISPLAYS** | 431-448 | 18 | Nombre \| Categoría (fija) \| 3 Precios |
| **BATERÍAS ANDROID** | 5-216 | 212 | Nombre \| P. Unitario \| Mayoreo 1 \| Mayoreo 2 |
| **BATERÍAS iPHONE** | 5-103 | 99 | Nombre \| P. Unitario \| 20pz Surtido \| 50pz Surtido |

**Regla de precios (replicar en integración):**
- Si existe precio genérico Y original → mostrar ambos
- Si solo existe uno → aplicar regla de estimación

**Nota importante:** 
- La hoja contiene fórmulas BUSCARY que referencian una hoja "may_disp2" (override)
- Solo consultar para precios, no explorar lógica interna

**Ejemplo:**
```
Cliente: "¿Precio display Samsung?"
Hugo Shop: ❌ No tiene
Google Sheets: ✅ Encontrado en hoja DISPLAYS
Respuesta: "Display Samsung A21: $150 (genérica) o $250 (original)"
```

#### 3️⃣ MercadoLibre (Fallback)
- **URL:** https://fixoem.com/ / Búsqueda ML
- **Método:** Web scraping
- **Estructura:** Precio unitario + disponibilidad
- **Estado:** ✅ Funcionando
- **Casos cubiertos:** Cuando no está en Hugo ni en Google Sheets

**Ejemplo:**
```
Cliente: "¿Precio pantalla Motorola X5?"
Hugo Shop: ❌ No tiene
Google Sheets: ❌ No tiene
MercadoLibre: ✅ Encontrado a $XXX
Respuesta: "No en nuestro inventario, pero en el mercado está a $XXX"
```

### 🎯 LÓGICA DE FALLBACK

```python
def obtener_precio(producto):
    # 1. Intentar Hugo Shop
    resultado = buscar_hugo_shop(producto)
    if resultado:
        return resultado  # OK, salir
    
    # 2. Si no está en Hugo, intentar Google Sheets
    resultado = buscar_google_sheets(producto)
    if resultado:
        return resultado  # OK, salir
    
    # 3. Si no está en Google Sheets, intentar MercadoLibre
    resultado = buscar_mercadolibre(producto)
    if resultado:
        return resultado  # OK, salir
    
    # 4. Si no está en ninguno
    return "No disponible"
```

---

## SETUP & DEPLOYMENT

### Local (Testing)

```bash
# 1. Clonar repo
git clone https://github.com/Hainrixz/whatsapp-agentkit.git
cd whatsapp-agentkit

# 2. Crear entorno virtual
python -m venv venv
source venv/bin/activate  # Mac/Linux
# o
venv\Scripts\activate  # Windows

# 3. Instalar dependencias
pip install -r requirements.txt

# 4. Crear .env con tus credenciales
cp .env.example .env
# Editar .env con:
# - ANTHROPIC_API_KEY
# - WHAPI_TOKEN
# - GOOGLE_CALENDAR_CREDENTIALS
# - DATABASE_URL (local)

# 5. Test local (chat en terminal)
python tests/test_local.py

# 6. Arrancar servidor local
uvicorn agent.main:app --reload --port 8000
```

### Railway (Producción)

```bash
# 1. Push a GitHub
git add .
git commit -m "feat: integración Google Sheets para precios"
git push origin main

# 2. Railway hace redeploy automático (~2 min)

# 3. Verificar URL
curl https://technology-support-agent-production.up.railway.app/
# Debe devolver: {"status": "ok"}

# 4. Verificar webhook en Whapi/Meta/Twilio
# (URL debe ser: https://technology-support-agent-production.up.railway.app/webhook)
```

### Variables en Railway

```env
# Claude API
ANTHROPIC_API_KEY=sk-ant-...

# WhatsApp
WHAPI_TOKEN=...
WHATSAPP_PROVIDER=whapi

# Google Sheets
GOOGLE_SHEETS_ID=1sMVr7rUp2dz_4h4NUEwFjH-iVqOjUWjJNYx5ptfgT2U
GOOGLE_SHEETS_CREDS=<JSON credenciales>

# Google Calendar
GOOGLE_CALENDAR_CREDENTIALS=<JSON credenciales>

# Base de datos
DATABASE_URL=postgresql://user:pass@...

# Sistema
PORT=8000
ENVIRONMENT=production
```

---

## PRÓXIMOS PASOS

### 📅 SEMANA 1 (Esta semana)

**TAREA 1: Integración Google Sheets** (4-6 horas)

Pasos:
1. [ ] Crear módulo `agent/pricing_sheets.py`
   - Leer Google Sheets API
   - Parsear hojas Displays, Baterías Android, Baterías iPhone
   - Implementar caché local (actualizar cada 1 hora)
   
2. [ ] Modificar `agent/pricing_integration.py`
   - Agregar Google Sheets a pipeline (entre Hugo y ML)
   - Mantener fallback MercadoLibre como último recurso
   
3. [ ] Tests
   - Validar lectura de Google Sheets
   - Validar fallback correcto
   - Validar formato de respuestas

4. [ ] Deploy
   - Push a GitHub
   - Validar en Railway
   - Test en grupo interno

**TAREA 2: Auto-CRM Sync** (3-4 horas)

Pasos:
1. [ ] Conectar API de Auto-CRM
2. [ ] Sincronizar leads creados por agente
3. [ ] Validar en Railway

---

### 📞 CHECKLIST DIARIO (2 minutos)

```
☐ Railway: servicio en "Running"
☐ GET / → 200 OK
☐ Mensaje de WhatsApp → respuesta < 10s
☐ Logs: sin errores repetitivos críticos
☐ Google Calendar: citas se agendan correctamente
☐ Precios: consultando Hugo Shop + Google Sheets + ML
```

---

## TROUBLESHOOTING

### Problema: Webhook no recibe mensajes
**Solución:**
1. Verificar URL en Whapi/Meta/Twilio: `https://technology-support-agent-production.up.railway.app/webhook`
2. Verificar WHAPI_TOKEN en Railway Settings
3. Revisar logs: `railway logs`

### Problema: Precios no aparecen
**Solución:**
1. Verificar que Hugo Shop está accesible
2. Si Hugo falla, revisar que Google Sheets tiene credenciales
3. Si Google Sheets falla, MercadoLibre debería funcionar como fallback
4. Si todo falla: `No disponible`

### Problema: Citas no se agendando
**Solución:**
1. Verificar credenciales de Google Calendar en Railway
2. Revisar que `GOOGLE_CALENDAR_CREDENTIALS` está configurado
3. Probar: `python tests/test_local.py` → comando "cita"

---

## 🔗 REFERENCIAS RÁPIDAS

| Recurso | Link |
|---------|------|
| **Railway Dashboard** | https://railway.app/dashboard |
| **Google Sheets** | https://docs.google.com/spreadsheets/d/1sMVr7rUp2dz_4h4NUEwFjH-iVqOjUWjJNYx5ptfgT2U/edit |
| **Whapi.cloud** | https://whapi.cloud |
| **Claude API** | https://platform.anthropic.com/settings/api-keys |
| **GitHub Repo** | https://github.com/Hainrixz/whatsapp-agentkit |

---

## 📞 CONTACTO & SOPORTE

**Responsables:**
- **Implementación:** Claude Code
- **Aprobación:** Christian (goldbunnyshop@gmail.com)

**Próxima sesión:** Integración Google Sheets + Auto-CRM Sync

---

**Documento consolidado desde 26 archivos .md**  
**Versión:** 2.0 (consolidada)  
**Estado:** ✅ LISTO PARA REFERENCIA  
**Última revisión:** 2 de junio de 2026

