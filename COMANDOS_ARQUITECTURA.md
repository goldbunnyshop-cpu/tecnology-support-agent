# Sistema Unificado de Comandos — WhatsApp AgentKit

**Fecha:** 23 de mayo, 2026  
**Estado:** ✅ Implementado v2.1 (cupones integrados en CRM)  
**Ubicación:** `agent/commands.py` + `agent/crm.py`

---

## 📋 Resumen Ejecutivo

El sistema de comandos ha sido **consolidado y extendido con cupones de descuento**:

- ✅ **23 comandos existentes** (de notifications.py + pausa_manager.py)
- ✅ **4 nuevos comandos** para seguimiento: `stop`, `2nd`, `unblock`, `noshow`
- ✅ **Sistema de cupones:** 15% (`2nd`) y 10% (`noshow`), válidos 8 días
- ✅ **Autorización abierta:** Cualquiera en el grupo "Taller Interno TS"
- ✅ **Case-insensitive:** Todos los comandos funcionan con mayúscula o minúscula
- ✅ **Bloqueo en-memoria:** No persistente, se limpia al reiniciar
- ✅ **Integración en webhook:** main.py ahora procesa comandos ANTES de Claude
- ✅ **Integración en CRM:** Cupones registrados en ClientePerfil (Google Sheets) — v2.1

---

## 🏗️ Arquitectura

```
webhook → (PASO 2.5) Verificar bloqueo
         → (PASO 2.6) Procesar comandos
         → (PASO 3+) Enviar a Claude (si no era comando)
```

### Archivos Clave

| Archivo | Propósito |
|---------|-----------|
| **commands.py** | Sistema unificado de comandos + inicializar_sistema_cupones() |
| **crm.py** | MODIFICADO: Nuevo módulo ClientePerfil con funciones de cupones |
| **main.py** | MODIFICADO: Integración de comandos + inicialización de cupones |
| **notifications.py** | OBSOLETO: Ahora solo para alertas a Christian |
| **pausa_manager.py** | OBSOLETO: Lógica movida a commands.py |

---

## 🎯 Comandos Disponibles

### 1. Notificaciones al Cliente (12 comandos)

```
listo: NÚMERO EQUIPO
  → Cliente listo para recoger
  Ej: listo: 5541576331 iPhone 13

demora: NÚMERO TIEMPO EQUIPO
  → Necesita más tiempo
  Ej: demora: 5541576331 2 horas iPhone 13

presupuesto: NÚMERO EQUIPO PRECIO
  → Envía presupuesto
  Ej: presupuesto: 5541576331 iPhone 13 500

diagnostico: NÚMERO EQUIPO DESCRIPCIÓN
  → Informa diagnóstico
  Ej: diagnostico: 5541576331 iPhone 13 pantalla rota

password: NÚMERO
  → Solicita contraseña

llamar: NÚMERO
  → Pide que llame

cita: NÚMERO
  → Información de ubicación/horarios

pausa: NÚMERO
  → Pausa agente 2h (tu atiendes)

reanudar: NÚMERO
  → Reanuda agente

clabe: NÚMERO
  → Envía CLABE de cuenta

pago: NÚMERO MONTO
  → Instrucciones de pago
  Ej: pago: 5541576331 1200
```

### 2. CRM / Órdenes (4 comandos)

```
nota: FOLIO NÚMERO EQUIPO [MODELO] FALLA TOTAL PAGO [refaccion:COSTO]
  → Registra en Google Sheets
  Ej: nota: 13054 5541576331 iPhone 13 pantalla 1200 tarjeta refaccion:500

orden: NÚMERO EQUIPO TOTAL PAGO [REFACCIÓN]
  → Registra orden (folio auto-asignado)
  Ej: orden: 5541576331 PS5 2500 tarjeta 350

estatus: FOLIO NUEVO_ESTATUS
  → Actualiza estatus de orden
  Ej: estatus: 45 listo
  Estatus válidos: recibido | proceso | listo | entregado

consultar: FOLIO
  → Datos completos de una orden
  Ej: consultar: 45
```

### 3. Sistema de Bloqueo (3 NUEVOS)

```
stop: NÚMERO
  → Bloquea cliente (no responde, no modifica BD)
  ⛔ El agente NO responderá a este número
  💾 No persistente: se limpia al reiniciar servidor
  Ej: stop: 5541576331

2nd: NÚMERO
  → Segundo seguimiento: genera mensaje persuasivo para agendar cita/visita
  📝 Lee últimos 10 mensajes como contexto (ej: cliente inactivo desde marzo)
  🤖 Claude genera mensaje empático y persuasivo
  ✅ Envía mensaje al cliente y desbloquea automáticamente
  Ej: 2nd: 5541576331

unblock: NÚMERO
  → Desbloquea número sin enviar mensaje persuasivo
  🔓 Cliente recupera respuestas normales del agente
  💬 Útil para seguimientos normales (cotizaciones, info, etc.)
  Ej: unblock: 5541576331
```

### 4. Reportes (2 comandos)

```
reporte
  → Resumen del día (leads + CRM + pendientes)

pendientes
  → Lista clientes pendientes de seguimiento
```

---

## 🔓 Autorización

**ANTES:** Solo Ulises (5633500566) y Christian (5541576331)  
**AHORA:** Cualquiera en el grupo "Taller Interno TS"

```python
# En commands.py, línea ~393:
# ✅ CUALQUIER REMITENTE puede ejecutar comandos
# ✅ Solo se verifica: está en grupo "Taller Interno TS"
```

---

## 🚫 Sistema de Bloqueo

### ¿Cómo funciona?

```python
# Memory local (NO persistente)
_NUMEROS_BLOQUEADOS = {
    "5541576331": {
        "razon": "Bloqueado por usuario",
        "bloqueado_en": datetime.now(),
    }
}
```

### Casos de uso

1. **Cliente problemático:** `stop: 5541576331` → agente NO responde (bloquea)
2. **Segundo seguimiento:** `2nd: 5541576331` → genera mensaje persuasivo para agendar cita/visita (lee contexto de últimos 10 msgs, envía al cliente, desbloquea)
3. **Recuperar normalidad:** `unblock: 5541576331` → desbloquea sin mensaje (para seguimientos normales: cotizaciones, info, etc.)
4. **Bloqueos temporales:** No persistentes — se limpian al reiniciar servidor
5. **Historial como contexto:** `2nd` usa los últimos 10 mensajes para que Claude entienda dónde está el cliente en la conversación

### Flujo en webhook

```python
# main.py PASO 2.5
if esta_bloqueado(msg.telefono):
    logger.info("Número bloqueado — ignorando")
    continue  # No responder
```

---

## 📝 Implementación en main.py

```python
# Imports (línea 37)
from agent.commands import procesar_comando_grupo, esta_bloqueado

# PASO 2.5: Bloqueo (línea ~165)
if esta_bloqueado(msg.telefono):
    continue

# PASO 2.6: Comandos (línea ~170)
es_comando = await procesar_comando_grupo(
    msg, proveedor, guardar_mensaje, obtener_historial
)
if es_comando:
    continue  # No procesar como mensaje normal

# PASO 3+: Claude (flujo normal si no era comando)
```

---

## 🔧 Consolidación Lograda

### Antes (Dispersado)

- notifications.py: 23 comandos + procesamiento
- pausa_manager.py: 3 comandos + PausaManager class
- main.py: Sin integración de comandos

### Después (Unificado)

- **commands.py**: Todos los comandos + 3 nuevos (stop, 2nd, unblock)
- **main.py**: Integración de comandos en webhook
- **notifications.py**: Solo alertas a Christian (sin modificar)
- **pausa_manager.py**: Mantener para compatibilidad (pero usar commands.py)

---

## 📊 Cambios de Código

### Nuevas Funciones en commands.py

```python
# Bloqueo en-memoria
bloquear_numero(telefono, razon)      # Bloquea
desbloquear_numero(telefono)          # Desbloquea
esta_bloqueado(telefono) -> bool      # Verifica
obtener_razon_bloqueo(telefono) -> str

# Comando "stop"
if cmd == "stop":
    phone = parsear_phone_simple(payload)
    bloquear_numero(phone_fmt, "Bloqueado con comando 'stop'")
    await _responder(f"⛔ Número bloqueado — agente no responde")

# Comando "2nd" (Segundo Seguimiento - Persuasivo)
if cmd == "2nd":
    phone = parsear_phone_simple(payload)
    historial = await obtener_historial_fn(phone_fmt, limite=10)
    # Generar mensaje PERSUASIVO con Claude (contexto: últimos 10 msgs)
    mensaje = await generar_respuesta(prompt_persuasivo, historial)
    # Enviar al cliente
    await proveedor.enviar_mensaje(phone_fmt, mensaje)
    # Desbloquear después
    desbloquear_numero(phone_fmt)

# Comando "unblock"
if cmd == "unblock":
    phone = parsear_phone_simple(payload)
    desbloquear_numero(phone_fmt)
    # Sin mensaje persuasivo — agente responde normalmente
```

---

## 🎟️ Sistema de Cupones — v2.1 (Integración en CRM)

**NUEVO:** Los cupones generados por `2nd` y `noshow` se registran automáticamente en **ClientePerfil** (Google Sheets).

### Estructura de ClientePerfil

```
Hoja: "ClientePerfil"
Columnas:
  A: Teléfono (normalizados)
  B: Nombre (capturado de historial)
  C: Cupones_Activos (JSON array)
  D: Cupones_Usados (JSON array)
  E: Última_Actualización (timestamp)
```

### Estructura de un Cupón

```json
{
  "codigo": "15OFFABC123",
  "porcentaje": 15,
  "fecha_generacion": "2026-05-23T14:30:00-05:00",
  "fecha_expiracion": "2026-05-31T14:30:00-05:00",
  "estado": "activo",
  "folio_aplicado": null
}
```

### Flujo de Cupones

1. **Generación:** `2nd` o `noshow` → `generar_cupon(15)` o `generar_cupon(10)`
2. **Registro:** `await crm.registrar_cupon(phone, codigo, porcentaje, dias_validez=8)`
3. **Persistencia:** Se escribe en ClientePerfil + se calcula fecha_expiracion
4. **Validación:** `await crm.validar_cupon(phone, codigo)` → verifica no esté vencido
5. **Uso:** `await crm.marcar_cupon_usado(phone, codigo, folio_orden)` → lo mueve a cupones_usados

### Funciones Públicas en crm.py

```python
# Inicializar
await crear_hoja_cupones()  # Crea ClientePerfil en Sheets

# Gestionar cupones
await registrar_cupon(telefono, codigo, porcentaje, dias_validez=8)
await consultar_cupones_activos(telefono) -> list[dict]
await validar_cupon(telefono, codigo) -> dict | None
await marcar_cupon_usado(telefono, codigo, folio_orden) -> bool
```

### Cambios en commands.py

- `procesar_comando_grupo()` ahora inicia `inicializar_sistema_cupones()` en startup (via main.py)
- Comando `2nd`: Registra cupón 15% en ClientePerfil
- Comando `noshow`: Registra cupón 10% en ClientePerfil
- Ambos incluyen logs de éxito con el código de cupón y fecha de vencimiento

---

## ⚠️ Limitaciones & Trade-offs

| Aspecto | Decisión | Por Qué |
|--------|----------|--------|
| **Persistencia de cupones** | ✅ Google Sheets (ClientePerfil) | Sincronizable con CRM, sin BD local |
| **Persistencia de bloqueos** | ⏳ Memory local (no persistente) | Bloqueos son temporales. Para persistencia, agregar fecha_desbloqueo |
| **Autorización** | Cualquiera en grupo | Flexible. Si necesitas restricción, volver a usar lista blanca |
| **Duración** | Bloqueos hasta reinicio | Se limpian al restart. Para duraciones X horas, agregar fecha_desbloqueo |

---

## 🚀 Roadmap Futuro

### v2.2 — Dashboard de Cupones

```
Comando: 'cupones' o 'cupones: [número]'
  → Muestra cupones activos/usados del cliente
  → Próximos a vencer (< 2 días)
  → Historial de aplicación
```

### v2.3 — Persistencia de Bloqueos

```sql
-- Agregar a ClientePerfil
ALTER TABLE clientes_perfil ADD bloqueado_hasta DATETIME NULL;
```

### v2.4 — Configuración Avanzada de Seguimiento

```
stop: NÚMERO 48h         → Bloquea 48 horas (automático en fecha_desbloqueo)
2nd: NÚMERO -cotizar    → Segundo seguimiento con ángulo de cotización (en lugar de persuasivo)
unblock: NÚMERO 24h      → Desbloquea temporalmente por 24 horas
```

### v2.5 — Reportes de Cupones

```
Comando: 'reporte cupones'
  → Cupones generados (hoy, semana, mes)
  → Tasa de uso (cuántos fueron aplicados)
  → Ingresos con descuento
  → Clientes con cupones próximos a vencer
```

---

## 🧪 Testing Local

### Fase 1: Menú y Bloqueos
```bash
menu                      # Ver menú completo
stop: 5541576331          # Bloquear cliente
stop: 5541576331          # Cliente no responde (agente silenciado)
unblock: 5541576331       # Desbloquear sin mensaje
```

### Fase 2: Cupones (Seguimiento)
```bash
2nd: 5541576331           # Segundo seguimiento + cupón 15%
# Esperar ~3s a que se registre en ClientePerfil
# Verificar logs: [2ND] Cupón: 15OFFXXXXX

noshow: 5541576331        # No-show + cupón 10%
# Esperar ~3s
# Verificar logs: [NOSHOW] Cupón: 10OFFXXXXX
```

### Fase 3: Verificar CRM
```bash
# En Google Sheets:
# 1. Ir a hoja "ClientePerfil"
# 2. Buscar número 5541576331
# 3. Ver columnas: Cupones_Activos, Cupones_Usados, Última_Actualización
# 4. Verificar que el JSON tenga el cupón con fecha_expiracion
```

### Fase 4: Logs
```bash
# Ver todos los comandos
tail -f /path/to/logs | grep "\[CMD\]"

# Ver cupones específicamente
tail -f /path/to/logs | grep "\[CRM\]\|\[2ND\]\|\[NOSHOW\]"
```

---

## 📞 Soporte

### Comandos en General
- **Errores en comandos:** Revisar `agent/commands.py` línea mencionada en log
- **Bloqueos no funcionan:** Verificar que `main.py` tiene línea ~165 de PASO 2.5
- **Integración fallida:** Asegurar que importó `procesar_comando_grupo` en main.py

### Cupones (v2.1)
- **Cupones no se registran:** Verificar que `GOOGLE_SHEET_ID` está en `.env`
- **ClientePerfil no se crea:** Revisar credenciales de Google Sheets en `agent/crm.py`
- **Cupones no aparecen en Sheets:** Buscar logs `[CRM] Cupón ... registrado`
- **Error al validar cupón:** Confirmar que no está vencido (función valida automáticamente)
- **Cupón vencido (9+ días):** Sistema calcula vencimiento como `ahora + dias_validez`. Por defecto 8 días.

---

**Documentación por:** Claude AgentKit  
**Versión:** 2.1 — Cupones integrados en CRM  
**Próxima revisión:** Cuando agregues dashboard de cupones o persistencia de bloqueos  
