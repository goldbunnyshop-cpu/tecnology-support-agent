# AgentKit — Arquitectura del Sistema de Citas

## 🏗️ Estructura General

```
WhatsApp (Cliente)
    ↓
Proveedor (Whapi.cloud / Meta / Twilio)
    ↓
FastAPI Webhook (/webhook)
    ↓
[DETECTOR AUTOMÁTICO DE CITAS] ← NUEVO ✨
    ↓
Google Calendar API + PostgreSQL (Railway)
    ↓
Daily Reports (HTML + Texto)
    ↓
Dashboard + Reportes
```

---

## 📊 Componentes Implementados

### 1. **Detector Automático de Citas** (`agent/cita_detector.py`)

Analiza los mensajes de WhatsApp y detecta automáticamente si el cliente está agendando una cita.

**Flujo:**
```
Mensaje de WhatsApp
    ↓
Claude API (analizar intención)
    ↓
¿Es cita? SÍ/NO
    ↓ (SÍ)
Parsear campos (nombre, dispositivo, fecha, hora, problema, asesor)
    ↓
Google Calendar API (crear evento)
    ↓
PostgreSQL (guardar con fuente="automatica")
    ↓
Respuesta automática al cliente
```

**Características:**
- Usa Claude Sonnet para análisis inteligente (entiende lenguaje natural)
- Parsea fechas en español ("Sábado 18 de mayo, 10:30 a.m.")
- Guarda automáticamente en PostgreSQL
- Crea eventos en Google Calendar (si está configurado)
- Diferencia entre citas históricas (`fuente="historico"`) y automáticas (`fuente="automatica"`)

**Integración en main.py:**
```python
from agent.cita_detector import procesar_mensaje_para_cita

# En el webhook handler, ANTES de generar respuesta:
resultado_cita = await procesar_mensaje_para_cita(msg.texto, msg.telefono, historial)

if resultado_cita.get("es_cita") and resultado_cita.get("guardada"):
    # Cita detectada y guardada automáticamente
    respuesta = resultado_cita["mensaje_respuesta"]
    await proveedor.enviar_mensaje(msg.telefono, respuesta)
```

---

### 2. **Daily Reports** (`reportes_diarios.py`)

Genera reportes formateados de todas las citas.

**Características:**
- Reportes de HOY (citas del día actual)
- Reportes de PRÓXIMOS 7 DÍAS
- Formatos: Texto legible + HTML completo
- Estadísticas: total, por asesor, por dispositivo
- Guardados en carpeta `reportes/`

**Uso:**
```bash
python reportes_diarios.py
```

**Salida:**
- `reportes/reporte_hoy.html` — Reporte visual de hoy
- `reportes/reporte_7dias.html` — Reporte visual de próximos 7 días

---

### 3. **Endpoints de Reportes** (`agent/reportes_api.py`)

Endpoints FastAPI para acceder a los reportes vía API.

**Endpoints disponibles:**
```
GET /api/reportes/hoy/texto          → Reporte de hoy en JSON (texto)
GET /api/reportes/hoy/html           → Descarga reporte de hoy (HTML)
GET /api/reportes/7dias/html         → Descarga reporte 7 días (HTML)
GET /api/reportes/generar            → Genera reportes manualmente
GET /api/salud                        → Verificación de salud
```

**Para integrar en main.py:**
```python
from agent.reportes_api import setup_reportes_routes
setup_reportes_routes(app)
```

---

### 4. **Scheduler de Reportes** (`schedule_reportes.py`)

Genera los reportes automáticamente cada mañana a las 6:00 AM (CDMX).

**Uso:**
```bash
# Ejecutar manualmente
python schedule_reportes.py

# O agregar a cron para que se ejecute diariamente
0 6 * * * cd /path/to/agentkit && python schedule_reportes.py
```

---

## 🔄 Flujo Completo de una Cita

### Escenario: Cliente agenda cita vía WhatsApp

```
1. CLIENTE ESCRIBE EN WHATSAPP
   "Hola, quiero agendar mi PS5 para el sábado 18 de mayo a las 3pm.
    La pantalla no funciona"

2. WEBHOOK RECIBE MENSAJE
   POST /webhook
   ↓
   
3. PARSING DEL MENSAJE
   Telefono: +5659866275
   Texto: "Hola, quiero agendar mi PS5..."
   ↓
   
4. DETECTOR AUTOMÁTICO (NUEVO)
   ├─ Claude analiza: ¿Es cita? → SÍ
   ├─ Parsea: 
   │  ├─ Nombre: (se obtiene del perfil o se pide)
   │  ├─ Dispositivo: PS5
   │  ├─ Problema: Pantalla no funciona
   │  ├─ Fecha: Sábado 18 de mayo, 15:00
   │  └─ Asesor: (se asigna según disponibilidad)
   ├─ Google Calendar: Crea evento
   ├─ PostgreSQL: Guarda en tabla `citas`
   │  └─ fuente: "automatica"
   └─ Respuesta: ✅ CITA AGENDADA
   ↓
   
5. RESPUESTA AL CLIENTE
   "✅ CITA AGENDADA
    👤 Juan Pérez
    📱 PS5
    ⏰ Sábado 18 de mayo, 15:00
    ⚠️ Pantalla no funciona
    👨‍💼 Asesor: Sofia
    Te confirmaremos en breve."
   ↓
   
6. NOTIFICACIÓN A CHRISTIAN
   (En grupo interno de WhatsApp)
   Cita agendada automáticamente
   ↓
   
7. CITA EN EL SISTEMA
   ├─ Google Calendar: Visible en calendario
   └─ PostgreSQL: Consultable en reportes
```

---

## 📈 Estadísticas y Reportes

### Tabla `citas` en PostgreSQL

```
Campos:
├─ id (PK)
├─ nombre (cliente)
├─ telefono
├─ dispositivo
├─ problema
├─ fecha_hora (datetime con timezone)
├─ asesor
├─ fuente: "historico" | "automatica"
└─ creada_en (timestamp)
```

### Ejemplo de datos

```
id | nombre            | dispositivo  | fecha_hora           | asesor    | fuente
---+-------------------+--------------+---------------------+-----------+-----------
1  | Jose Luis Miranda | PS5          | 2026-05-09 11:30    | Sofia     | historico
2  | Juan Pérez        | iPhone 14    | 2026-05-18 15:00    | Valentina | automatica
3  | Maria García      | Laptop Dell  | 2026-05-20 10:00    | Camila    | automatica
```

---

## 🚀 Comandos de Instalación y Uso

### 1. Instalar dependencias
```bash
pip install schedule
```

### 2. Crear reportes manualmente
```bash
python reportes_diarios.py
```

### 3. Ejecutar scheduler de reportes
```bash
python schedule_reportes.py
```

### 4. Acceder a reportes vía API
```bash
# Reporte de hoy (JSON)
curl http://localhost:8000/api/reportes/hoy/texto

# Descargar reporte HTML
curl http://localhost:8000/api/reportes/7dias/html > reporte.html
```

---

## 🔐 Variables de Entorno Necesarias

```bash
# Ya tienes en .env:
ANTHROPIC_API_KEY=sk-ant-...
WHATSAPP_PROVIDER=whapi
WHAPI_TOKEN=...
DATABASE_URL=postgresql+asyncpg://...

# Opcionales (Google Calendar):
GOOGLE_CREDENTIALS_PATH=config/credentials.json
GOOGLE_CALENDAR_ID=tecnotogysupportmx@gmail.com
```

---

## ✅ Estado Actual

| Componente | Estado | Descripción |
|-----------|--------|-------------|
| 17 citas históricas | ✅ Completado | Importadas a PostgreSQL |
| Detector automático | ✅ Completado | Detecta y guarda citas automáticamente |
| Daily reports | ✅ Completado | Genera reportes HTML y texto |
| Endpoints API | ✅ Completado | Acceso a reportes vía REST |
| Scheduler | ✅ Completado | Reportes automáticos cada mañana |
| Google Calendar | 🟡 Configurable | Funciona si está setup Google Cloud |

---

## 📋 Próximas Fases

1. **Fase Operativa:**
   - [ ] Configurar Google Calendar en Google Cloud Console
   - [ ] Integrar endpoints de reportes en main.py
   - [ ] Probar detector automático con clientes reales
   - [ ] Crear dashboard en Auto-CRM

2. **Fase 2 - Sincronización de Leads:**
   - [ ] Endpoint GET /api/leads (sincronización automática)
   - [ ] Enriquecer leads con: email, empresa, dispositivo, presupuesto
   - [ ] Integración con Auto-CRM

3. **Fase 3 - Operativo Completo:**
   - [ ] Dashboard de seguimiento
   - [ ] Alertas automáticas
   - [ ] Reportes de conversión

---

## 🧪 Testing Local

Para probar el detector automático sin WhatsApp real:

```python
from agent.cita_detector import procesar_mensaje_para_cita
import asyncio

# Test
mensaje = "Quiero agendar mi PS5 para el sábado 16 de mayo a las 11am. Se calienta mucho."
resultado = asyncio.run(procesar_mensaje_para_cita(mensaje, telefono="5551234567"))
print(resultado)
```

---

**Generado:** 2026-05-15  
**Responsable:** AgentKit
