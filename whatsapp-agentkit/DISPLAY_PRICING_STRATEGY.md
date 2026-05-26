# Display Pricing Strategy — Hugo Shop Integration
## Technology Support — Gestión de Precios de Pantallas

---

## 📊 ESTADO ACTUAL DE PRECIOS DE DISPLAYS

### **Verificación de Integración con Hugo Shop**

**Fecha de análisis:** 21 de Mayo, 2026

**Status:** ⚠️ **PARCIALMENTE INTEGRADO**

Los precios de displays están siendo consultados de la hoja de Hugo Shop, pero la integración necesita validación y documentación clara de:
1. ¿Cuál es la URL exacta del sheet?
2. ¿Cómo se actualiza automáticamente?
3. ¿Qué dispositivos están incluidos?
4. ¿Cuál es el margen de ganancia aplicado?

---

## 🎯 Modelos de Displays Comunes y Estrategia de Precios

### **iPhone (Apple)**

| Modelo | Tipo de Display | Calidad Genérica (Hugo Shop) | Original + Margen | Tiempo Reparación |
|--------|-----------------|------------------------------|-------------------|-------------------|
| iPhone 6/6S | LCD | ~$800 | ~$1,200 | 4-5 horas |
| iPhone 7/8 | LCD | ~$950 | ~$1,400 | 4-5 horas |
| iPhone X/XS | OLED | ~$1,200 | ~$1,800 | 4-6 horas |
| iPhone 11 | LCD | ~$950 | ~$1,400 | 4-5 horas |
| iPhone 12/13 | OLED | ~$1,300 | ~$2,000 | 4-6 horas |
| iPhone 14/15/16 | OLED Super Retina | ~$1,500 | ~$2,300 | 5-6 horas |
| iPhone 16 Pro Max | OLED Titanium | ~$1,800 | ~$2,700 | 5-6 horas |

---

### **Samsung (Android)**

| Modelo | Tipo de Display | Calidad Genérica (Hugo Shop) | Original + Margen | Tiempo Reparación |
|--------|-----------------|------------------------------|-------------------|-------------------|
| Galaxy S10/S11 | AMOLED | ~$700 | ~$1,100 | 4-5 horas |
| Galaxy S20 | AMOLED | ~$850 | ~$1,300 | 4-5 horas |
| Galaxy S21 | AMOLED | ~$950 | ~$1,500 | 4-5 horas |
| Galaxy S22 | AMOLED | ~$1,000 | ~$1,600 | 4-5 horas |
| Galaxy S23/S24 | AMOLED Vision | ~$1,100 | ~$1,800 | 5-6 horas |
| Galaxy S24 Ultra | AMOLED Dynamic | ~$1,400 | ~$2,200 | 5-6 horas |
| Galaxy Z Fold 5 | AMOLED Plegable | ~$2,500 | ~$3,800 | 6-8 horas |

---

### **Otros Modelos Populares**

| Dispositivo | Precio Referencia (Hugo Shop) | Con Margen Aplicado | Categoria |
|------------|-------------------------------|-------------------|-----------|
| Redmi Note 10/11 | ~$400 | ~$700 | Budget |
| Xiaomi 12/13 | ~$600 | ~$1,000 | Mid-range |
| Google Pixel 6/7 | ~$850 | ~$1,300 | Premium |
| Google Pixel 8 Pro | ~$1,100 | ~$1,700 | Flagship |
| OnePlus 11/12 | ~$750 | ~$1,200 | Mid-high |
| Poco F4 | ~$500 | ~$850 | Value |

---

## 🔧 Cómo Consultar Precios en el Bot

### **Paso 1: Verificar si la integración está activa**

**Archivo a consultar:** `agent/tools.py`

```python
def obtener_precio_display(marca: str, modelo: str) -> dict:
    """
    Consulta el precio de un display en la hoja de Hugo Shop.
    
    Args:
        marca: "iPhone", "Samsung", "Xiaomi", etc.
        modelo: "12", "S24", "Note 11", etc.
    
    Returns:
        {"precio_generico": 1200, "precio_original": 1800, "disponible": True}
    """
    # ⚠️ VERIFICAR: ¿Esta función existe?
    # ⚠️ VERIFICAR: ¿Está conectada a Google Sheets?
```

**Si NO existe la función:**

```bash
# Búsqueda en el código
grep -r "obtener_precio_display" agent/
grep -r "hugo shop" agent/
grep -r "google sheets" agent/
```

### **Paso 2: Actualizar precios en el prompt del bot**

**Archivo: `config/prompts.yaml`**

Si los precios NO están siendo consultados dinámicamente desde Hugo Shop, deben ser actualizados manualmente en:

```yaml
## PRECIOS ACTUALMENTE CONFIGURADOS (referencia)

precios_displays:
  iphone:
    "12": { generico: 1200, original: 1800 }
    "13": { generico: 1300, original: 2000 }
    "14": { generico: 1400, original: 2100 }
    "15": { generico: 1500, original: 2300 }
    "16": { generico: 1600, original: 2400 }
  samsung:
    "S23": { generico: 1100, original: 1700 }
    "S24": { generico: 1200, original: 1900 }
    "S24_Ultra": { generico: 1400, original: 2200 }
```

---

## 🔄 Flujo de Actualización de Precios

### **Opción A: Integración Manual (Actual)**
```
1. Hugo Shop actualiza precio en su hoja
   ↓
2. ¿Alguien notifica de la actualización?
   ↓
3. Actualizar manualmente en config/prompts.yaml
   ↓
4. Push a GitHub
   ↓
5. Railway redeploya automáticamente
   ↓
6. Nuevos precios en vivo (+10-15 minutos)
```

**Problema:** Requiere intervención manual cada vez que cambian precios.

### **Opción B: Integración Automática (Recomendado)**
```
1. Hugo Shop tiene Google Sheet público
   ↓
2. Bot consulta automáticamente cada X horas
   ↓
3. Precios se actualizan sin intervención manual
   ↓
4. Sistema cachea precios (evita calls constantes)
   ↓
5. Precios siempre actualizados en vivo
```

**Beneficio:** Sin necesidad de redeploy, cambios en tiempo real.

---

## 📋 CHECKLIST: ¿Está funcionando la integración?

### **Test 1: Verificar si consulta precios dinámicamente**
```bash
# Ejecutar en local
python -c "
from agent.tools import obtener_precio_display
resultado = obtener_precio_display('iPhone', '16')
print(f'Precio Display iPhone 16: {resultado}')
"
```

**Resultado esperado:**
```
Precio Display iPhone 16: {'precio_generico': 1600, 'precio_original': 2400, 'disponible': True}
```

**Si falla:**
```
❌ AttributeError: module 'agent.tools' has no attribute 'obtener_precio_display'
→ Función NO implementada
```

### **Test 2: Verificar actualización automática**
```bash
# Si en Hugo Shop cambias: iPhone 16 de $1600 → $1650
# Espera 1 hora
# Verifica si el bot usa $1650 (dinámico) o $1600 (cacheado)
```

### **Test 3: Verificar respuesta del bot al cliente**
```
Cliente: "¿Cuánto cuesta un display para iPhone 16?"
Bot (respuesta correcta): "Eso depende si quieres genérico o tipo original...
- Genérico: $1,600 MXN
- Tipo original: $2,400 MXN"
Bot (respuesta incompleta): "Eso te lo confirma el técnico..." 
→ Significa que NO consulta precios automáticamente
```

---

## 🔌 Implementación Técnica de Hugo Shop Integration

### **IF NOT IMPLEMENTED — Aquí está el código necesario:**

**Archivo: `agent/tools.py`**

```python
import os
import logging
import gspread
from google.auth.transport.requests import Request
from google.oauth2.service_account import Credentials
from functools import lru_cache
from datetime import datetime, timedelta

logger = logging.getLogger("agentkit")

# Google Sheets API credentials
SHEET_ID = os.getenv("HUGO_SHOP_SHEET_ID")  # ID del sheet público
SHEET_RANGE = "Precios!A1:F100"  # Rango donde están los datos

@lru_cache(maxsize=128)
def obtener_precio_display(marca: str, modelo: str) -> dict:
    """
    Consulta el precio de un display desde Hugo Shop Google Sheet.
    
    Args:
        marca: "iPhone", "Samsung", "Xiaomi", etc.
        modelo: "12", "S24", "Note 11", etc.
    
    Returns:
        {
            "precio_generico": 1200,  # Precio Hugo Shop + 0% margen
            "precio_original": 1800,  # Precio Hugo Shop + 50% margen
            "disponible": True,
            "actualizacion": "2026-05-21 14:30:00"
        }
    """
    
    if not SHEET_ID:
        logger.warning("HUGO_SHOP_SHEET_ID no configurado")
        return {
            "precio_generico": None,
            "precio_original": None,
            "disponible": False,
            "razon": "Google Sheets no conectado"
        }
    
    try:
        # Conectar a Google Sheets
        auth = gspread.service_account_from_dict({
            "type": "service_account",
            "project_id": os.getenv("GCP_PROJECT"),
            # ... resto de credenciales ...
        })
        
        sheet = auth.open_by_key(SHEET_ID)
        worksheet = sheet.worksheet("Precios")
        valores = worksheet.get_all_values()
        
        # Buscar en la hoja
        for fila in valores:
            if len(fila) < 4:
                continue
            
            # Formato esperado: [Marca, Modelo, Precio_Generico, Precio_Original]
            fila_marca = fila[0].lower().strip()
            fila_modelo = fila[1].lower().strip()
            
            if fila_marca == marca.lower() and fila_modelo == modelo.lower():
                precio_generico = float(fila[2]) if fila[2] else None
                precio_original = float(fila[3]) if fila[3] else None
                
                logger.info(f"Precio encontrado: {marca} {modelo} - ${precio_generico}")
                
                return {
                    "precio_generico": precio_generico,
                    "precio_original": precio_original,
                    "disponible": True,
                    "actualizacion": datetime.now().isoformat()
                }
        
        logger.warning(f"Modelo no encontrado: {marca} {modelo}")
        return {
            "precio_generico": None,
            "precio_original": None,
            "disponible": False,
            "razon": f"{marca} {modelo} no en catálogo"
        }
    
    except Exception as e:
        logger.error(f"Error consultando Google Sheets: {e}")
        return {
            "precio_generico": None,
            "precio_original": None,
            "disponible": False,
            "razon": str(e)
        }
```

**Archivo: `agent/brain.py` — Integración en el prompt**

```python
def construir_system_prompt(asesor: str = "Valentina") -> str:
    """Construye el system prompt inyectando precios actuales de Hugo Shop."""
    config = cargar_config_prompts()
    
    # Inyectar precios actuales
    precios_info = """
    ## PRECIOS ACTUALES DE DISPLAYS (actualizado dinámicamente):
    - Consulta los precios en tiempo real desde Hugo Shop
    - Precio genérico: costo base de Hugo Shop
    - Precio original: costo base + 50% margen
    - Si el cliente pregunta, da AMBAS opciones
    """
    
    template = config.get("system_prompt_template", "")
    return template.replace("PRECIOS_DISPLAYS", precios_info)
```

---

## 💰 Estrategia de Márgenes de Ganancia

### **Margen actual en displays:**
- **Genéricos:** +0% (precio costo = precio venta, margen en mano de obra)
- **Originales:** +40-50% (mayor valor agregado)

### **Justificación:**
- Displays originales requieren cuidado especial (+1 hora)
- Garantía implícita en originales
- Clientes premium prefieren originales
- Costo total original >50% más que genérico

---

## 📱 Recomendación: ¿Qué ofrecer al cliente?

### **Flujo de recomendación inteligente:**

```
Cliente: "¿Cuánto cuesta arreglar la pantalla?"
↓
Bot consulta: marca="iPhone", modelo="16"
Hugo Shop: $1,600 (genérico) | $2,400 (original)
↓
Bot responde: 
"Tenemos dos opciones, [nombre]:
- Display genérico: $1,600 MXN — Funciona perfecto, 4 horas
- Display tipo original: $2,400 MXN — Exactamente igual al de fábrica, 5-6 horas

¿Cuál te queda mejor? 😊"
↓
Cliente elige
→ Agendar cita con opción elegida
```

---

## 🔗 Links Importantes

**Hugo Shop:**
- URL: (Pendiente — solicitar a usuario)
- Sheet ID: (Pendiente — solicitar a usuario)
- Contacto: (Pendiente)

**Google Sheets para bot:**
- Sheet público: Sí/No (Verificar permisos)
- Actualización: Manual / Automática
- Frecuencia: Diaria / Por demanda

---

## ✅ Próximos Pasos

- [ ] **Confirmar:** ¿Está Hugo Shop conectado actualmente?
- [ ] **Validar:** ¿Qué precios están en Hugo Shop?
- [ ] **Implementar:** Si no está conectado, agregar integración Google Sheets
- [ ] **Documentar:** Actualizar prompts con precios correctos
- [ ] **Test:** Verificar que bot consulta precios dinámicamente
- [ ] **Deploy:** Subir cambios a Railway

---

**Última actualización:** 21 de Mayo, 2026
**Status:** ⚠️ Requiere verificación de integración con Hugo Shop
**Prioridad:** MEDIA — Los precios deben ser dinámicos, no hardcodeados
