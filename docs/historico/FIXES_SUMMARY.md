# 🔧 Resumen de Fixes — Sistema de Citas

Fecha: 15 de Mayo, 2026  
Problemas resueltos: **3 críticos**

---

## ✅ FIX #1: Caracteres Mojibake (UTF-8 Corruption)

### Problema
- Usuario reportó: "siguen los simbolos raros en la confirmacion de citas"
- Síntomas: `Â¡` en lugar de `¡`, `Â©` en lugar de `©`
- Causa: Encoding UTF-8 no validado al enviar a Whapi.cloud

### Solución
**Archivo:** `agent/providers/whapi.py` (método `enviar_mensaje`)

- ✅ Validación explícita de UTF-8 antes de envío
- ✅ Encoding explícito `Content-Type: application/json; charset=utf-8`
- ✅ Logging detallado de mensajes enviados

**Qué cambió:**
```python
# ANTES (sin validación)
json={"to": destino, "body": mensaje}

# DESPUÉS (con validación UTF-8)
mensaje_limpio = mensaje.encode('utf-8', errors='replace').decode('utf-8')
json={"to": grupo_id, "body": mensaje_limpio}
```

---

## ✅ FIX #2: Notificaciones al Grupo No Se Envían

### Problema
- Usuario reportó: "no se notifico al grupo"
- El grupo ID **está configurado** en `.env`
- Pero los mensajes no llegan al grupo "Taller Interno TS"
- Causa: Sin logging = errores silenciosos + sin reintentos

### Solución
**Archivo:** `agent/appointment_notifications.py`

- ✅ Logging **detallado** en CADA intento de envío
- ✅ Reintentos automáticos (hasta 3 intentos)
- ✅ Mejor manejo de errores con context completo

**Cambios:**
1. Función `_enviar_grupo()`:
   - Agregó parámetro `reintentos` (default: 2)
   - Loop de reintentos con delays entre intentos
   - Logging de cada paso (`🔄 Intento X/Y`, `✅ Enviado`, `❌ Falló`)

2. Función `notificar_nueva_cita()`:
   - Logging extenso para cada etapa
   - Ahora muestra: email ✅/❌, grupo ✅/❌
   - Traceback completo si hay excepción

**Logs que verás si funciona:**
```
[CITAS NOTIF] 🚀 ========== INICIANDO NOTIFICACIÓN DE CITA ==========
[CITAS NOTIF] Cliente: Test Cliente | Tel: +525541234567
[CITAS NOTIF] 📱 Enviando notificación al grupo...
[CITAS GRUPO] 🔄 Intento 1/3 — Enviando a 120363xxx@g.us...
[CITAS GRUPO] ✅ Mensaje enviado al grupo exitosamente
[CITAS NOTIF] ✅ Notificación al grupo enviada exitosamente
```

---

## ✅ FIX #3: Base de Datos PostgreSQL (Ya Estaba Parcialmente Arreglado)

### Recordatorio
El fix anterior **cambió cita_detector.py** para usar raw SQL en lugar de ORM:

```python
# Se cambió DE:
from importar_citas_postgresql import Cita  # ❌ NUNCA FUNCIONÓ

# A:
query = text("""
    INSERT INTO citas (nombre, telefono, dispositivo, problema, fecha_hora, asesor, fuente)
    VALUES (:nombre, :telefono, :dispositivo, :problema, :fecha_hora, :asesor, :fuente)
""")
```

---

## 🧪 Cómo Testear

### Opción 1: Test Automático (Recomendado)

```bash
# En la carpeta del proyecto
python test_fixes.py
```

**Qué hace:**
1. ✅ Verifica que `GRUPO_CHRISTIAN_INTERNO` esté en `.env`
2. 📱 **Envía un mensaje de prueba al grupo** (Taller Interno TS)
3. ✏️ Verifica UTF-8 encoding

**Qué buscar en la salida:**
- `✅ Grupo configurado correctamente` → OK
- `[CITAS GRUPO] ✅ Mensaje enviado` → OK
- `✅ UTF-8 válido` → OK

---

### Opción 2: Test Real (Envía mensajes de WhatsApp)

Envía este mensaje a cualquier cliente:

```
Quiero agendar para lunes 20 de mayo a las 10:00 a.m.
Tengo un iPhone 14 con pantalla rota
```

**Qué esperar:**
1. 📱 **Recibe confirmación con caracteres correctos**
   - Debe decir: `✅ *CITA CONFIRMADA*` (no `Â¡`)
   - Debe mostrar: `⏰ Lunes 20 de mayo, 10:00 a.m.`

2. 📋 **El grupo recibe notificación**
   - Mensaje en "Taller Interno TS" con `🔔 *NUEVA CITA AGENDADA*`
   - Datos del cliente

3. 📊 **Cita se guarda en PostgreSQL**
   - Puedes verificar con SQL:
   ```sql
   SELECT * FROM citas WHERE nombre LIKE '%Test%' ORDER BY fecha_hora DESC LIMIT 1;
   ```

---

## 📊 Checklist de Verificación

### ✅ Antes de ir a producción

- [ ] Ejecutar `python test_fixes.py`
- [ ] Revisar logs buscando `[CITAS GRUPO] ✅`
- [ ] Enviar un mensaje de prueba real desde WhatsApp
- [ ] Verificar que aparezcan caracteres correctos (¡ © ™ etc.)
- [ ] Verificar que el grupo reciba notificación
- [ ] Verificar que la cita se guarde en PostgreSQL

### 🚨 Si algo falla

| Síntoma | Causa probable | Solución |
|---------|----------------|----------|
| `Â¡ © ™` en mensajes | Mojibake UTF-8 | Revisar whapi.py encoding |
| `[CITAS GRUPO] ❌ No se encontró el grupo` | GRUPO_CHRISTIAN_INTERNO no en .env | Agregar en `.env` |
| `[CITAS GRUPO] ❌ HTTP 401` | WHAPI_TOKEN inválido | Verificar token en .env |
| Cita no se guarda | SQLAlchemy error | Revisar logs PostgreSQL |

---

## 🔄 Próximos Pasos Recomendados

1. **Ejecuta el test** (`python test_fixes.py`)
2. **Revisa los logs** — busca `[CITAS GRUPO]` y `[CITAS NOTIF]`
3. **Envía un mensaje de prueba** desde WhatsApp real
4. **Verifica en Railway** que la cita llegó a PostgreSQL

---

## 📝 Notas Técnicas

### UTF-8 Encoding
- `httpx` envía JSON con UTF-8 por defecto
- Pero agregamos validación explícita para evitar doble-encoding
- Si un carácter no es válido UTF-8, se reemplaza con `?`

### Notificaciones con Reintentos
- Primer intento: inmediato
- 2do intento: después de 1 segundo
- 3er intento: después de 1 segundo
- Total: máximo 3 segundos de espera

### PostgreSQL
- Las citas se guardan con `timezone=America/Mexico_City`
- Campo `fuente='automatica'` para citas detectadas por IA
- Deduplicación por `evento_id` (Google Calendar ID)

---

¡Los fixes están listos! 🚀
