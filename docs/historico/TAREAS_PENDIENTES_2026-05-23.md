# 🎯 Tareas Pendientes — Ordenadas por Prioridad

**Generado:** 2026-05-23 15:50 UTC-6  
**Total de tareas:** 18  
**Status:** Plan ejecutable para próximas 2 semanas

---

## 🔴 PRIORIDAD CRÍTICA (Hoy/Mañana)

### TAREA 1: Compartir Hugo Shop + Accesorios con Service Account
**Duración:** 10 minutos | **Criticidad:** 🔴 CRÍTICA  
**Responsable:** Christian (propietario de Google Drive)

**Instrucciones:**
1. Abrir Google Drive
2. Seleccionar Hugo Shop Sheet
3. Compartir con: `agentkit-sheets-access@tecnology-support.iam.gserviceaccount.com`
4. Permisos: "Viewer" (solo lectura)
5. Repetir con 5 listas de accesorios

**Verificación:**
```bash
# En terminal Python
from googleapiclient.discovery import build
from google.oauth2.service_account import Credentials

SCOPES = ['https://www.googleapis.com/auth/spreadsheets.readonly']
creds = Credentials.from_service_account_file('config/credentials.json', scopes=SCOPES)
service = build('sheets', 'v4', credentials=creds)

# Debe retornar 200 OK
result = service.spreadsheets().get(spreadsheetId='SHEET_ID').execute()
print("✅ Sheet accesible vía API")
```

**Checklist:**
- [ ] Hugo Shop compartido
- [ ] Baterías Android compartido
- [ ] Baterías iPhone compartido
- [ ] Tapas Android compartido
- [ ] Tapas iPhone compartido
- [ ] Altavoz y Auricular compartido
- [ ] Verificación en Python exitosa

---

### TAREA 2: Analizar Estructura de 5 Listas de Accesorios
**Duración:** 30 minutos | **Criticidad:** 🔴 CRÍTICA  
**Responsable:** Claude (análisis automatizado)

**Tareas sub:**

#### 2.1 Analizar Baterías Android
```
LEER: Google Drive → Baterías Android
VERIFICAR: 
  - Formato (CSV, Google Sheets, Excel)
  - Columnas (código, modelo, precio base)
  - Cantidad de productos
  - Marcas soportadas
DOCUMENTAR: En tools.py como comentario
```

#### 2.2 Analizar Baterías iPhone
```
IDEM 2.1
```

#### 2.3 Analizar Tapas Android
```
IDEM 2.1
```

#### 2.4 Analizar Tapas iPhone
```
IDEM 2.1
```

#### 2.5 Analizar Altavoz y Auricular
```
IDEM 2.1
```

**Output esperado:**
```markdown
# Análisis de Accesorios

## Baterías Android
- Formato: Google Sheets
- Columnas: A=Código, B=Modelo, C=Precio
- Productos: 250+
- Marcas: Samsung, Xiaomi, Motorola...

## [Repetir para otros]
```

**Checklist:**
- [ ] Baterías Android analizado
- [ ] Baterías iPhone analizado
- [ ] Tapas Android analizado
- [ ] Tapas iPhone analizado
- [ ] Altavoz y Auricular analizado
- [ ] Documento ANALISIS_ACCESORIOS.md creado

---

### TAREA 3: Crear Funciones de Precio para Accesorios
**Duración:** 45 minutos | **Criticidad:** 🔴 CRÍTICA  
**Responsable:** Claude (codificación)

**Agregar a `agent/tools.py`:**

```python
# ═══════════════════════════════════════════════════════════
# BATERÍAS ANDROID
# ═══════════════════════════════════════════════════════════

async def obtener_precio_bateria_android(modelo: str) -> dict:
    """
    Busca precio de batería para dispositivo Android.
    Retorna: {encontrado, precio_calculado, precio_base}
    """
    # Implementación similar a obtener_precio_display()
    # Pero busca en sheet de Baterías Android
    pass

# ═══════════════════════════════════════════════════════════
# BATERÍAS IPHONE
# ═══════════════════════════════════════════════════════════

async def obtener_precio_bateria_iphone(modelo: str) -> dict:
    """Busca precio de batería para iPhone."""
    pass

# ═══════════════════════════════════════════════════════════
# TAPAS ANDROID
# ═══════════════════════════════════════════════════════════

async def obtener_precio_tapa_android(modelo: str) -> dict:
    """Busca precio de tapa/funda para Android."""
    pass

# ═══════════════════════════════════════════════════════════
# TAPAS IPHONE
# ═══════════════════════════════════════════════════════════

async def obtener_precio_tapa_iphone(modelo: str) -> dict:
    """Busca precio de tapa/funda para iPhone."""
    pass

# ═══════════════════════════════════════════════════════════
# ALTAVOCES Y AURICULARES
# ═══════════════════════════════════════════════════════════

async def obtener_precio_speaker(tipo: str, modelo: str) -> dict:
    """
    Busca precio de altavoz o auricular.
    tipo: "speaker", "headphone", "earbuds"
    """
    pass
```

**Checklist:**
- [ ] obtener_precio_bateria_android() implementada
- [ ] obtener_precio_bateria_iphone() implementada
- [ ] obtener_precio_tapa_android() implementada
- [ ] obtener_precio_tapa_iphone() implementada
- [ ] obtener_precio_speaker() implementada
- [ ] 5 funciones testeadas
- [ ] Tests en test_hugo_shop.py actualizados

---

## 🟡 PRIORIDAD IMPORTANTE (Esta semana)

### TAREA 4: Integrar Ruteo Automático en brain.py
**Duración:** 60 minutos | **Criticidad:** 🟡 IMPORTANTE  
**Responsable:** Claude (codificación)

**Objetivo:** Brain.py debe detectar automáticamente QUÉ pregunta el cliente y llamar la función correcta

**Ejemplo de flujo:**
```
Cliente: "¿Cuánto cuesta una pantalla para mi iPhone 16?"
         ↓
brain.py detecta: tema=["pantalla", "display", "screen"]
         ↓
Llama: obtener_precio_display("APPLE", "iPhone 16")

Cliente: "¿Tienes baterías para Samsung?"
         ↓
brain.py detecta: tema=["batería", "battery"]
dispositivo=["samsung", "android"]
         ↓
Llama: obtener_precio_bateria_android("Samsung S24")
```

**Implementación:**

```python
# En agent/brain.py, agregar función:

async def detectar_categoria_producto(mensaje: str) -> dict:
    """
    Usa Claude para detectar QUÉ tipo de producto busca el cliente.
    
    Retorna: {
        "categoria": "pantalla|bateria|tapa|speaker|otra",
        "dispositivo": "iphone|samsung|etc",
        "modelo": "S24 FE|iPhone 16|etc"
    }
    """
    
    prompt = f"""
    Analiza el mensaje del cliente e identifica:
    1. ¿Qué tipo de producto? (pantalla, batería, tapa, auricular, otro)
    2. ¿Para qué dispositivo? (modelo específico)
    
    Mensaje: "{mensaje}"
    
    Responde en JSON: {{"categoria": "...", "dispositivo": "...", "modelo": "..."}}
    """
    
    # Llamar Claude API
    # ...

# En agent/main.py webhook:

async def webhook_handler(request: Request):
    # ... código existente ...
    
    # NUEVO: Detectar categoría y llamar función apropiada
    categoria_info = await detectar_categoria_producto(msg.texto)
    
    if categoria_info["categoria"] == "pantalla":
        info_precio = await obtener_precio_display(
            categoria_info["dispositivo"],
            categoria_info["modelo"]
        )
        respuesta = formatear_respuesta_precio(...)
    
    elif categoria_info["categoria"] == "bateria":
        if "iphone" in categoria_info["dispositivo"].lower():
            info_precio = await obtener_precio_bateria_iphone(
                categoria_info["modelo"]
            )
        else:
            info_precio = await obtener_precio_bateria_android(
                categoria_info["modelo"]
            )
        respuesta = formatear_respuesta_bateria(...)
    
    # ... más casos ...
```

**Checklist:**
- [ ] Función detectar_categoria_producto() creada
- [ ] Ruteo automático en webhook_handler()
- [ ] 3+ categorías soportadas
- [ ] Testing con 20+ preguntas variadas
- [ ] Documentación inline

---

### TAREA 5: Testing Exhaustivo de Accesorios
**Duración:** 45 minutos | **Criticidad:** 🟡 IMPORTANTE  
**Responsable:** Claude (testing)

**Crear `tests/test_accesorios.py`:**

```python
import asyncio
from agent.tools import (
    obtener_precio_bateria_android,
    obtener_precio_bateria_iphone,
    obtener_precio_tapa_android,
    obtener_precio_tapa_iphone,
    obtener_precio_speaker
)

async def test_baterias():
    """Test 10+ modelos de baterías Android e iPhone"""
    test_cases = [
        ("Samsung S24", "obtener_precio_bateria_android"),
        ("iPhone 16", "obtener_precio_bateria_iphone"),
        # ... más casos ...
    ]
    
    for modelo, func_name in test_cases:
        # Ejecutar y verificar
        pass

async def test_tapas():
    """Test 10+ modelos de tapas"""
    pass

async def test_speakers():
    """Test 5+ tipos de altavoces"""
    pass

if __name__ == "__main__":
    asyncio.run(test_baterias())
    asyncio.run(test_tapas())
    asyncio.run(test_speakers())
```

**Checklist:**
- [ ] test_accesorios.py creado
- [ ] 30+ casos de prueba implementados
- [ ] 100% de tests pasando
- [ ] Tiempos de respuesta < 2 segundos

---

## 🟢 PRIORIDAD MEDIANA (Próximas 2 semanas)

### TAREA 6: Migrar de CSV HTTP a Google Sheets API v4
**Duración:** 90 minutos | **Criticidad:** 🟢 MEDIANA  
**Responsable:** Claude (refactor)

**Beneficios:**
- Mejor velocidad (API nativa vs CSV HTTP)
- Caché automático
- Sincronización en tiempo real
- Manejo de errores mejorado

**Implementación:**

```python
# agent/sheets_client.py (NUEVO)

from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

class SheetsClient:
    def __init__(self, sheet_id, sheet_name="Sheet1"):
        self.sheet_id = sheet_id
        self.sheet_name = sheet_name
        self.service = self._build_client()
        self.cache = {}
        self.cache_age = {}
    
    def _build_client(self):
        """Crea cliente autenticado de Google Sheets API."""
        SCOPES = ['https://www.googleapis.com/auth/spreadsheets.readonly']
        creds = Credentials.from_service_account_file(
            'config/google-credentials.json',
            scopes=SCOPES
        )
        return build('sheets', 'v4', credentials=creds)
    
    async def obtener_datos(self, rango="A1:F500"):
        """
        Obtiene datos del sheet usando API.
        Implementa caché simple (refresh cada 30 min).
        """
        if rango in self.cache and self._cache_valido(rango):
            return self.cache[rango]
        
        try:
            result = self.service.spreadsheets().values().get(
                spreadsheetId=self.sheet_id,
                range=f"{self.sheet_name}!{rango}"
            ).execute()
            
            valores = result.get('values', [])
            self.cache[rango] = valores
            self.cache_age[rango] = datetime.now()
            
            return valores
        except Exception as e:
            logger.error(f"Error obteniendo datos de Sheets: {e}")
            return self.cache.get(rango, [])
    
    def _cache_valido(self, rango, max_age_minutes=30):
        """Verifica si el caché sigue siendo válido."""
        if rango not in self.cache_age:
            return False
        elapsed = datetime.now() - self.cache_age[rango]
        return elapsed.total_seconds() < max_age_minutes * 60
```

**Checklist:**
- [ ] SheetsClient implementado
- [ ] Caché con TTL implementado
- [ ] Google Sheets API v4 integrada
- [ ] Todos los obtener_precio_*() refactorados
- [ ] Tests de velocidad (antes vs después)
- [ ] Documentación de mejoras

---

### TAREA 7: Dashboard de Precios en Tiempo Real
**Duración:** 120 minutos | **Criticidad:** 🟢 MEDIANA  
**Responsable:** Claude (frontend) + Christian (deploy)

**Objetivo:** Página web con precios actualizados en tiempo real

**Features:**
- Búsqueda por marca + modelo
- Filtro por categoría (pantalla, batería, etc)
- Gráfico de precios comparativos
- Exportar a CSV

**Stack:**
- Frontend: React (Cowork artifact)
- Backend: API en Agentkit
- Datos: Google Sheets API

**Checklist:**
- [ ] API endpoint `/api/precios` creado
- [ ] Frontend React creado
- [ ] Búsqueda implementada
- [ ] Gráficos con Chart.js
- [ ] Exportación CSV
- [ ] Deploy en Vercel (opcional)

---

## 🔵 PRIORIDAD BAJA (Largo plazo)

### TAREA 8: Sincronizar 156 Leads Existentes a Auto-CRM
**Duración:** 60 minutos | **Criticidad:** 🔵 BAJA  
**Relacionado:** ESTADO_INTEGRACION_COMPLETO.md

**Instrucciones:**
```bash
# En Agentkit:
# Leer tabla `citas` (156 registros)
# Convertir a transacciones en Auto-CRM
# Script: agent/scripts/migrate_leads.py
```

**Checklist:**
- [ ] Script creado
- [ ] 156 leads migrados
- [ ] Verificación en Auto-CRM dashboard
- [ ] Auditoría de duplicados

---

### TAREA 9: Phase 2 Auto-CRM — Procesar Cola de Notificaciones
**Duración:** 90 minutos | **Criticidad:** 🔵 BAJA  
**Relacionado:** PROXIMOS_PASOS.md (PASO 5)

**Tareas:**
- [ ] Crear endpoint `/send-whatsapp` en Agentkit
- [ ] Crear script cron `procesar-notificaciones-whatsapp.ts`
- [ ] Procesa `notification_queue` cada 5 minutos
- [ ] Envía via Whapi.cloud
- [ ] Testing end-to-end

**Checklist:**
- [ ] Endpoint `/send-whatsapp` creado
- [ ] Cron job funcionando
- [ ] 10+ notificaciones enviadas con éxito
- [ ] Documentación actualizada

---

### TAREA 10: Analytics y Reporting
**Duración:** 120 minutos | **Criticidad:** 🔵 BAJA  
**Objetivo:** Dashboard de KPIs

**Métricas a trackear:**
- Preguntas sobre precios (por categoría)
- Clientes únicos (por semana)
- Tasa de conversión (consulta → cita)
- Categoría más popular
- Precio promedio por reparación

**Checklist:**
- [ ] Tabla `metrics` en PostgreSQL
- [ ] Función `log_metric()` en tools.py
- [ ] Agregación diaria
- [ ] Dashboard con gráficos
- [ ] Exportación de reportes

---

## 📊 Resumen de Tareas

| ID | Tarea | Prioridad | Est. Horas | Status |
|----|-------|-----------|-----------|--------|
| 1 | Compartir sheets con Service Account | 🔴 Crítica | 0.25 | ⏳ Pendiente |
| 2 | Analizar accesorios | 🔴 Crítica | 0.5 | ⏳ Pendiente |
| 3 | Crear funciones de accesorios | 🔴 Crítica | 0.75 | ⏳ Pendiente |
| 4 | Ruteo automático en brain.py | 🟡 Importante | 1.0 | ⏳ Pendiente |
| 5 | Testing de accesorios | 🟡 Importante | 0.75 | ⏳ Pendiente |
| 6 | Google Sheets API v4 | 🟢 Mediana | 1.5 | ⏳ Pendiente |
| 7 | Dashboard de precios | 🟢 Mediana | 2.0 | ⏳ Pendiente |
| 8 | Sincronizar leads | 🔵 Baja | 1.0 | ⏳ Pendiente |
| 9 | Phase 2 Auto-CRM | 🔵 Baja | 1.5 | ⏳ Pendiente |
| 10 | Analytics | 🔵 Baja | 2.0 | ⏳ Pendiente |

**Total estimado:** 11.75 horas (2 semanas distribuidas)

---

## 🚦 Flujo Recomendado

### Día 1 (Hoy)
- [x] TAREA 1: Compartir sheets (10 min)
- [x] TAREA 2: Analizar accesorios (30 min)

### Día 2 (Mañana)
- [ ] TAREA 3: Crear funciones (45 min)
- [ ] TAREA 5: Testing (30 min)

### Semana 2
- [ ] TAREA 4: Ruteo automático (1 hora)
- [ ] TAREA 6: Google Sheets API (1.5 horas)

### Semana 3
- [ ] TAREA 7: Dashboard (2 horas)
- [ ] TAREA 8-10: Largo plazo

---

## 🔗 Referencias Relacionadas

- **ESTADO_INTEGRACION_COMPLETO.md** — Phase 1 WhatsApp-Agentkit
- **PROXIMOS_PASOS.md** — Pasos de deployment
- **HUGO_SHOP_INTEGRATION_DOCUMENTATION.md** — Integración de precios
- **ESTADO_HOY_2026-05-23.md** — Estado actual

---

## 💾 Backup de Esta Información

**Ubicación Local:**
```
C:\Users\Elitebook\whatsapp-agentkit\TAREAS_PENDIENTES_2026-05-23.md
```

**Ubicación Google Drive:**
```
Compartido en carpeta del proyecto
```

---

*Documento generado: 2026-05-23 15:50 UTC-6*  
*Actualizar este documento después de completar cada tarea*
