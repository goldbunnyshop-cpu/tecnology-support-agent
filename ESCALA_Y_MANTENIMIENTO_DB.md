# Escala y Mantenimiento de Base de Datos — Tecnology Support Agent

> Documento de referencia para consultas futuras sobre rendimiento, escala y mantenimiento
> preventivo de la base de datos PostgreSQL del agente de WhatsApp.
> **Última actualización:** 2026-10-06

---

## 1. Cómo funciona el comando `stop:`

El comando `stop: NÚMERO` (enviado desde el grupo interno) llama a `detener_numero()` en
`memory.py`, que inserta un registro en la tabla `stopped_numbers` con `activo=True`.

**En cada mensaje entrante**, `main.py` ejecuta en orden:

| # | Función | Tabla consultada | Tiempo aprox. |
|---|---------|-----------------|---------------|
| 1 | `validar_numero_activo()` | `stopped_numbers` | ~0.1 ms |
| 2 | `esta_pausada()` | `pausas` | ~0.2 ms |
| 3 | `mensaje_ya_procesado()` | `mensajes_procesados` | ~0.1 ms |
| 4 | `obtener_perfil()` | `clientes_perfil` | ~0.2 ms |
| 5 | `obtener_historial()` | `mensajes` | ~1–5 ms |
| 6 | `guardar_mensaje()` × 2 | `mensajes` | ~2 ms |

**Total por mensaje: ~4–8 ms en condiciones normales.**

---

## 2. ¿Qué pasa a 10,000 números detenidos?

### El `stopped_numbers` NO es el cuello de botella

La columna `numero` es `PRIMARY KEY` → índice B-tree automático → PostgreSQL lo resuelve en
~0.1 ms sin importar si hay 100 o 100,000 filas. **Este check no escala mal.**

### Los riesgos reales a escala son:

#### A) Tabla `pausas` — crece sin límite si no se limpia
- Cada intervención manual de Christian inserta una fila nueva.
- Las filas antiguas se marcan `activa=False` pero **nunca se borran** sin mantenimiento.
- A 5,000 clientes con 10 pausas c/u = 50,000 filas muertas que degradan autovacuum.

#### B) Tabla `mensajes` — el peso real de la operación
- Cada conversación genera ~2 filas por intercambio.
- A 10K clientes con 30 mensajes promedio = **300,000 filas**.
- El query de historial está indexado por `telefono` pero la tabla completa pesa.

#### C) Pool de conexiones agotado bajo carga concurrente
- Con 8 queries/mensaje y 4 clientes escribiendo simultáneamente = 32 conexiones.
- Railway Hobby PostgreSQL: máximo **25 conexiones** simultáneas.
- Sin pool configurado correctamente → mensajes descartados o demorados.

#### D) Cold start de Railway (no es DB, pero se siente igual)
- El plan Hobby apaga el servicio tras ~15 min de inactividad.
- Al llegar el primer mensaje después del silencio, tarda **3–8 segundos** en arrancar.
- **Solución real:** plan Pro de Railway (~$20/mes) elimina el cold start.

---

## 3. Fixes aplicados (2026-10-06)

### Fix A — Funciones de limpieza en `memory.py`

Se agregaron tres funciones al final de `agent/memory.py`:

```python
limpiar_pausas_expiradas(dias=7)    # Borra pausas inactivas > 7 días
limpiar_mensajes_antiguos(dias=90)  # Borra mensajes > 90 días (conserva últimos 20)
limpiar_stopped_inactivos(dias=180) # Borra stopped reactivados > 180 días
ejecutar_mantenimiento_db()         # Llama a las tres en secuencia
```

### Fix B — Loop semanal en `followup.py`

Se agregó `_loop_mantenimiento_db()` al scheduler principal. Corre automáticamente
**todos los lunes a las 03:00 CDMX** sin intervención manual.

Se ve en logs como:
```
[MAINT] Próximo mantenimiento DB: 2026-10-13 03:00 CDMX (162.3h)
[MAINT] Semana limpia ✅ pausas=847 msgs=12450 stopped=3
```

### Fix C — Pool de conexiones ampliado en `memory.py`

```python
# ANTES
_engine_kwargs = {"pool_size": 5, "max_overflow": 10, "pool_pre_ping": True}

# DESPUÉS
_engine_kwargs = {"pool_size": 10, "max_overflow": 20, "pool_pre_ping": True, "pool_recycle": 1800}
```

| Parámetro | Antes | Después | Efecto |
|-----------|-------|---------|--------|
| `pool_size` | 5 | 10 | Conexiones persistentes siempre abiertas |
| `max_overflow` | 10 | 20 | Ráfagas de hasta 30 conexiones en pico |
| `pool_recycle` | — | 1800 s | Recicla conexiones cada 30 min (evita drops de Railway) |

---

## 4. Capacidad estimada tras los fixes

| Métrica | Antes | Después |
|---------|-------|---------|
| Clientes simultáneos (sin degradar) | ~3 | ~8–10 |
| Mensajes/hora sostenidos | ~500 | ~2,000 |
| Números en `stopped_numbers` sin impacto | ilimitado | ilimitado |
| Tamaño max `pausas` antes de limpiar | ilimitado | ~7 días |
| Tamaño max `mensajes` activos | ilimitado | ~90 días |
| Clientes totales históricos soportados | ~10K | ~50K+ |

---

## 5. Comandos útiles de diagnóstico (Railway CLI o psql)

```sql
-- Ver tamaño de cada tabla
SELECT relname, pg_size_pretty(pg_total_relation_size(oid))
FROM pg_class WHERE relkind = 'r' ORDER BY pg_total_relation_size(oid) DESC;

-- Cuántos números detenidos hay activos
SELECT COUNT(*) FROM stopped_numbers WHERE activo = TRUE;

-- Cuántas pausas muertas (candidatas a limpieza)
SELECT COUNT(*) FROM pausas WHERE activa = FALSE;

-- Cuántos mensajes hay y cuánto espacio ocupan
SELECT COUNT(*), MIN(timestamp), MAX(timestamp) FROM mensajes;

-- Ejecutar limpieza manual si hace falta
-- (normalmente lo hace el scheduler automático)
DELETE FROM pausas WHERE activa = FALSE AND fecha_pausa < NOW() - INTERVAL '7 days';
DELETE FROM mensajes WHERE timestamp < NOW() - INTERVAL '90 days';
```

---

## 6. Señales de alerta a monitorear en Railway logs

| Log | Qué significa | Acción |
|-----|--------------|--------|
| `[MAINT] limpiar_pausas_expiradas: 0 filas eliminadas` | Normal en primera semana | Ninguna |
| `TimeoutError: QueuePool limit` | Pool de conexiones agotado | Escalar Railway o reducir carga |
| `[INIT] ⚠️ RAILWAY DETECTADO pero DATABASE_URL apunta a SQLite` | BD no persistente | Agregar PostgreSQL en Railway |
| `[MAINT] Error en mantenimiento DB` | Fallo de limpieza | Revisar logs, ejecutar manual |
| Cold start evidente (3-8s de latencia inicial) | Plan Hobby activo | Considerar plan Pro ($20/mes) |

---

## 7. Límites a vigilar según volumen de negocio

| Volumen | Acción recomendada |
|---------|--------------------|
| < 1,000 clientes activos/mes | Sin cambios, arquitectura actual suficiente |
| 1,000–10,000 clientes activos/mes | Los fixes actuales cubren este rango |
| 10,000–50,000 clientes activos/mes | Agregar Redis para caché de `esta_pausada` y `numero_esta_stopped` |
| > 50,000 clientes activos/mes | Migrar a arquitectura con worker queue (Celery/ARQ) + read replicas |
