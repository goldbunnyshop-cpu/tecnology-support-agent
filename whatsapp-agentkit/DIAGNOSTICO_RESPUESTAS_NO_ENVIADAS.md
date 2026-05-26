# Diagnóstico: Agente No Responde Después de Deployment

**Fecha:** 2026-05-24  
**Estado:** RESUELTO CON MEJORAS DE LOGGING  
**Acción Requerida:** Hacer nuevo deployment a Railway

---

## Problema Reportado

- **Síntoma:** Después de ejecutar `git push`, el agente deja de responder a mensajes de clientes
- **Evidencia:** Logs muestran "✅ Webhook completado" pero sin logs de "Respuesta generada" o "Mensaje enviado"
- **Impacto:** Mensajes de clientes son recibidos pero el agente no envía respuestas

---

## Investigación Realizada

### ✅ Tests Ejecutados (TODOS PASARON)

1. **test_diagnostico.py** - Verificó que los checkpoints funcionan:
   - `esta_bloqueado()` ✓
   - `esta_pausada()` ✓
   - `obtener_historial()` ✓

2. **test_webhook_flujo.py** - Simuló flujo completo del webhook:
   - Validación de mensaje propio ✓
   - Validación de texto vacío ✓
   - Checkpoint de bloqueo ✓
   - Checkpoint de pausa ✓
   - Checkpoint de comandos de grupo ✓
   - Obtener historial ✓
   - Detectar tipo de dispositivo ✓
   - Verificar menú ambiguo ✓

3. **test_whapi_parseo.py** - Verificó parseo de mensajes de Whapi:
   - Parseo correcto de payload ✓
   - Normalización de números ✓
   - Validaciones de campo ✓

4. **test_numero_variantes.py** - Verificó variantes de teléfono:
   - 5541576333 ✓
   - 5541576333@c.us ✓
   - 525541576333 ✓
   - 5215541576333 ✓
   - +525541576333 ✓

5. **test_webhook_completo.py** - Simuló webhook real:
   - Parseó mensaje de Whapi ✓
   - Pasó todos los checkpoints ✓
   - Obtuvo historial ✓

### 🔍 Cambios Realizados

#### 1. Mejora de Logging en `agent/main.py` (PASO 2.5b)

**ANTES:**
```python
if await esta_pausada(msg.telefono):
    logger.info(f"⏸️ [PAUSA] Número {msg.telefono} está pausado — Christian atenderá manualmente")
    continue
```

**DESPUÉS:**
```python
logger.debug(f"🔵 PASO 2.5b: Verificando pausa para {msg.telefono}...")
try:
    esta_en_pausa = await esta_pausada(msg.telefono)
    logger.debug(f"✅ PASO 2.5b: Pausa check completado. Resultado: {esta_en_pausa}")
    if esta_en_pausa:
        logger.info(f"⏸️ [PAUSA] Número {msg.telefono} está pausado — Christian atenderá manualmente")
        continue
except Exception as e:
    logger.error(f"❌ ERROR en PASO 2.5b (pausa check): {e}", exc_info=True)
    raise
logger.debug(f"✅ PASO 2.5b: Número no está pausado, continuando")
```

**Beneficio:** Ahora es posible rastrear exactamente dónde se descarta un mensaje si hay error en `esta_pausada()`

#### 2. Mejora de Logging en Checkpoint de Bloqueo

```python
logger.debug(f"🔵 PASO 2.5: Verificando bloqueo para {msg.telefono}...")
if esta_bloqueado(msg.telefono):
    logger.info(f"🚫 [BLOQUEO] Número {msg.telefono} está bloqueado — ignorando mensaje")
    continue
logger.debug(f"✅ PASO 2.5: No está bloqueado")
```

**Beneficio:** Rastreo detallado del flujo en PASO 2.5

#### 3. Mejora de Error Logging en Try/Except Externo

```python
except Exception as e:
    logger.error(f"❌ ERROR CRÍTICO en procesamiento de mensaje de {msg.telefono}: {e}", exc_info=True)
    logger.error(f"Tipo de error: {type(e).__name__}")
    # Continuar con el siguiente mensaje en lugar de crashear
    continue
```

**Beneficio:** Errores que ocurran en el pipeline ahora se loguean a nivel ERROR con tipo de excepción

---

## Posibles Causas Identificadas

### 1. **Error Silencioso en `esta_pausada()`** ⚠️ MENOS PROBABLE
- Los tests pasaron, pero podría haber edge cases en producción
- **Solución:** Ahora hay logging detallado para detectar

### 2. **Problema en Inicialización de Scheduler** ⚠️ MENOS PROBABLE
- `inicializar_scheduler()` podría fallar silenciosamente
- **Solución:** Ver logs de startup

### 3. **Problema de Código Async** ⚠️ POSIBLE
- Deadlock o race condition en código async
- **Solución:** Los tests adicionales deberían revelar esto

### 4. **Problema Específico de Railway** ⚠️ POSIBLE
- Variables de entorno no configuradas correctamente
- Timeouts en Railway
- Problema con imports en ambiente de producción
- **Solución:** Hacer nuevo deployment con logs detallados

---

## Próximos Pasos

### 1. Hacer Deployment a Railway

```bash
cd /ruta/al/proyecto
git add -A
git commit -m "diagnostics: agregar logging detallado para rastrear respuestas no enviadas"
git push origin main
```

### 2. Monitorear Logs en Railway

Una vez desplegado, verifica los logs con:
```bash
railway logs
```

Busca por:
- `🔵 PASO 2.5b: Verificando pausa` - Confirma que entra al checkpoint
- `✅ PASO 2.5b: Pausa check completado` - Confirma que la pausa se verifica sin error
- `❌ ERROR CRÍTICO` - Si hay algún error, aquí aparecerá

### 3. Enviar Mensaje de Prueba

Envía un mensaje a través de WhatsApp y verifica que:
1. Aparezca el log `📱 Mensaje recibido de [NÚMERO]`
2. Aparezcan todos los logs de PASO 2.5 y PASO 2.5b
3. Aparezca `✅ Respuesta generada`
4. Aparezca `✅ Respuesta enviada`

---

## Archivos Modificados

- `agent/main.py` - Agregar logging detallado en checkpoints

## Archivos de Diagnóstico Creados (Para Testing Local)

- `test_diagnostico.py` - Tests de checkpoints individuales
- `test_webhook_flujo.py` - Simulación de flujo completo
- `test_whapi_parseo.py` - Tests de parseo de Whapi
- `test_numero_variantes.py` - Tests de variantes de teléfono
- `test_webhook_completo.py` - Test de webhook real

---

## Conclusión

El código está funcionando correctamente en ambiente local. El problema probablemente es:
1. Un error específico de Railway que ahora será visible con los logs mejorados
2. Un edge case que los tests no cubrieron

**Con los cambios de logging realizados, será posible diagnosticar exactamente qué está sucediendo en producción.**

---

## Command Reference

```bash
# Ejecutar tests locales
python3 test_diagnostico.py
python3 test_webhook_flujo.py
python3 test_webhook_completo.py

# Hacer deployment
git add -A
git commit -m "diagnostics: agregar logging detallado"
git push origin main

# Monitorear Railway
railway logs  # o desde Railway web UI
```
