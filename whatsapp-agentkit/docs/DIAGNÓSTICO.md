# 🔍 Guía de Diagnóstico — Bot No Responde

**Última actualización:** 2026-05-21

Cuando el bot no responde a algunos mensajes o responde con retraso, sigue esta guía.

---

## 🚨 Síntomas Comunes

| Síntoma | Probable Causa |
|---------|---|
| Bot no responde en ABSOLUTO | Webhook no configurado / Whapi.cloud down |
| Bot responde después de 5+ minutos | API de Claude lenta o timeout |
| Bot responde solo después de que respondo manualmente | Error silencioso en el procesamiento |
| Bot responde a algunos mensajes pero no a otros | Problema en la BD o error en detectar dispositivo |
| Mensaje "Error 500 en webhook" | Exception en agent/main.py o agent/brain.py |

---

## 📋 Checklist de Diagnóstico

### Paso 1: Revisar Railway Logs

**Lugar:** https://railway.app → Tu proyecto → Logs

**Busca:**
```
ERROR
Exception
Traceback
FALLO
❌
```

**Copiar los últimos 50 logs de error y compartir conmigo.**

### Paso 2: Verificar Webhook de WhatsApp

**Si usas Whapi.cloud:**
1. Ve a https://whapi.cloud
2. Ve a **Settings → Webhooks**
3. Verifica que esté ACTIVO (toggle verde)
4. Verifica que la URL sea correcta: `https://tu-app.up.railway.app/webhook`

**Si usas Meta Cloud API:**
1. Ve a https://developers.facebook.com
2. Tu app → WhatsApp → Configuration
3. Callback URL debe ser: `https://tu-app.up.railway.app/webhook`
4. Verify Token debe coincidir con `META_VERIFY_TOKEN` en Railway

### Paso 3: Ejecutar Script de Diagnóstico

En tu máquina local:

```bash
# Asegurar que .env esté configurado
cd C:\Users\Elitebook\whatsapp-agentkit

# Ejecutar diagnóstico
python tests/diagnostico.py
```

**Esto verifica:**
- ✅ Variables de entorno
- ✅ Conexión a base de datos
- ✅ Carga del proveedor de WhatsApp
- ✅ Conexión a Claude API
- ✅ Flujo completo (guardar → generar → guardar → responder)

**Si hay errores, te dirá exactamente dónde están.**

### Paso 4: Revisar Logs Detallados en Railway

Con la mejora de logging que acabamos de hacer, deberías ver líneas como:

```
🔵 PASO 1: Parseando webhook...
✅ Webhook parseado. Mensajes recibidos: 1
🔵 PASO 3: Obteniendo historial de 5541234567...
✅ Historial obtenido: 5 mensajes previos
🔵 PASO 5: Generando respuesta...
✅ Respuesta generada (156 caracteres)
🔵 PASO 6: Guardando en memoria...
✅ Mensajes guardados en BD
🔵 PASO 7: Enviando respuesta por WhatsApp...
✅ Respuesta enviada a 5541234567
✅ Ciclo completo exitoso para 5541234567
```

**Si ves:**
```
❌ FALLO en parseo de webhook: [error]
```
→ Problema con Whapi.cloud / Meta / Twilio

**Si ves:**
```
❌ FALLO generando respuesta: [error]
```
→ Problema con Claude API

**Si ves:**
```
❌ FALLO guardando en BD: [error]
```
→ Problema con la base de datos

---

## 🛠️ Soluciones Comunes

### Problema: "Error parseando webhook"

**Causa:** Whapi.cloud no está enviando datos correctamente o URL es incorrecta.

**Solución:**
1. Verifica que la URL en Whapi.cloud sea exacta: `https://tu-app.up.railway.app/webhook`
2. Desactiva y reactiva el webhook en Whapi.cloud
3. Envía un mensaje de prueba desde WhatsApp
4. Revisa los logs en Railway

### Problema: "Error generando respuesta"

**Causa:** Claude API está down, timeout, o API key no es válida.

**Solución:**
1. Verifica que `ANTHROPIC_API_KEY` esté correcta en Railway
2. Prueba generar respuesta localmente: `python tests/test_local.py`
3. Si falla localmente → problema con ANTHROPIC_API_KEY
4. Si funciona localmente pero no en Railway → problema de network/timeout

### Problema: "Error guardando en BD"

**Causa:** Base de datos (SQLite o PostgreSQL) está down o corrupta.

**Solución:**
1. Si usas SQLite: Elimina `agentkit.db` y deja que Railway lo recree
2. Si usas PostgreSQL: Verifica que la BD está corriendo
3. Revisa `DATABASE_URL` en Railway

### Problema: "El bot responde después de mi respuesta manual"

**Causa:** El primer mensaje del cliente llegó y fue procesado, pero hubo error silencioso. Cuando tú respodiste, el sistema vio un nuevo mensaje y procesó exitosamente.

**Solución:**
1. Ejecuta `python tests/diagnostico.py` localmente
2. Revisa los logs en Railway buscando "❌ FALLO"
3. Verifica que `ANTHROPIC_API_KEY` sea válida
4. Verifica que la BD tiene espacio (no está llena)

---

## 📊 Monitoreo Proactivo

Para que no vuelva a pasar:

### 1. Verificar logs DIARIAMENTE

```bash
# En Railway, filtra por "❌ FALLO" cada día
```

### 2. Hacer un test local DIARIAMENTE

```bash
python tests/test_local.py

# Envía 3-5 mensajes de ejemplo
# Verifica que el bot responde rápido
```

### 3. Agregar alertas en Railway

Railway tiene **Health Checks** y **Deploy Notifications** para alertarte si algo falla.

---

## 🔗 Checklist Rápido

Cuando el bot no responda, chequea EN ESTE ORDEN:

- [ ] ¿Webhook está ACTIVO en Whapi.cloud / Meta?
- [ ] ¿Railway está corriendo? (no está en CRASHED state)
- [ ] ¿`ANTHROPIC_API_KEY` es válida?
- [ ] ¿Base de datos tiene conexión?
- [ ] ¿Logs de Railway muestran errores?
- [ ] ¿Ejecuté `python tests/diagnostico.py` localmente?

Si TODAS son sí y sigue sin responder → **contacta soporte.**

---

## 📞 Información para Reportar

Si me reportas un problema, incluye:

1. **Error exacto de Railway logs** (copiar-pegar)
2. **Salida de `python tests/diagnostico.py`**
3. **Último mensaje que envió el cliente (antes de que fallara)**
4. **Hora del fallo (para buscar en logs)**
5. **Quién estaba respondiendo** (¿bot automático o Christian manual?)

---

## 🚀 Mejora Futura

Para evitar estos problemas, se puede:
- Agregar retry automático (si falla, reintentar en 5 segundos)
- Agregar monitoreo en tiempo real (alertas a tu telegram)
- Agregar heartbeat check (verificar que todo está vivo cada 5 minutos)
- Usar PostgreSQL en lugar de SQLite (más robusto en producción)
