# 🧪 Configuración Número de Prueba

## Número: **5627557362**

### ✅ Características habilitadas:

| Función | Estado |
|---------|--------|
| **Horario nocturno** | ❌ DESHABILITADO (24/7 disponible) |
| **Detección de espía de precios** | ❌ DESHABILITADO |
| **Restricción de horarios** | ❌ DESHABILITADO |
| **Cotización completa** | ✅ HABILITADA |
| **Acceso a todos los flujos** | ✅ CELULAR + CONSOLA + LAPTOP |
| **Cross-sell** | ✅ HABILITADO |
| **Citas con Google Calendar** | ✅ HABILITADA |
| **Agendar sin restricciones** | ✅ HABILITADO |

---

## 🎯 Qué puedes probar:

### 1. **Celular** (cotización automática)
```
"Se me rompió la pantalla del iPhone 13"
"Cuánto cuesta cambiar batería en Samsung"
"Mi Pixel tiene problema de carga"
```

### 2. **Consola** (diagnóstico)
```
"Mi PS5 no enciende"
"Xbox Series X se apaga sola"
"Nintendo Switch tiene problema de lectura"
```

### 3. **Laptop** (cambio + diagnóstico)
```
"Batería de mi MacBook no dura"
"La laptop no enciende"
"Dell tiene sobrecalentamiento"
```

### 4. **Cross-sell**
```
Primero: "Mi consola está fallando" → Flujo CONSOLA
Luego: "Y también se me rompió el celular" → Flujo CELULAR (cross-sell detectado)
```

### 5. **Agendar cita** (sin restricción de horario)
```
"Quiero agendar para mañana a las 3pm"
"Puedo ir el viernes a las 9am"
(Funciona incluso a las 3am - sin restricción nocturna)
```

---

## 🔧 Cómo agregar más números de prueba:

**Opción 1: Editar archivo config/numeros_prueba.txt**
```
# Números de prueba/testing — Sin restricciones
5627557362
5551234567  ← Agregar aquí
5559876543  ← Y aquí
```

**Opción 2: Código en main.py**
```python
_NUMEROS_PRUEBA = {"5627557362", "5551234567"}
```

---

## 📊 Logs para debugging:

Cuando el número 5627557362 envíe un mensaje, verás logs como:
```
[PRUEBA] 5627557362 — bypass horario nocturno habilitado
[MULTI-TIPO] 5627557362 tiene historial: ['celular']
[BRAIN] System prompt cargado para tipo=celular, asesor=Sofia
```

---

## ⚙️ Configuración técnica:

**main.py (línea ~98)**
```python
_NUMEROS_PRUEBA = {"5627557362"}  # Números de testing sin restricciones

def _es_numero_prueba(telefono: str) -> bool:
    """True si es un número de testing"""
    return any(telefono.endswith(n) or n.endswith(telefono) for n in _NUMEROS_PRUEBA)
```

**Archivos que lee:**
- `config/numeros_prueba.txt` — Dinámico (se recarga cada vez)
- `agent/main.py` — _NUMEROS_PRUEBA hardcodeado

---

## 🚀 Próximos pasos:

1. ✅ **Código deployado** — El número ya está configurado
2. ⏳ **Push a GitHub** — Pendiente (ejecutar desde PowerShell)
3. ⏳ **Redeploy a Railway** — Automático después del push
4. 🧪 **Testing** — Envía mensajes desde ese número

---

## 📝 Notas:

- El número se detecta automáticamente en cada request
- NO aparece en leads como cliente normal (está en lista interna)
- Las conversaciones de prueba se guardan en BD normalmente (puedes auditar después)
- Si descubres que algo no funciona, usa estos logs para debuggear
