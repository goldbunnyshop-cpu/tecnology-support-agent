# 🚀 CHECKLIST PRE-DEPLOY A RAILWAY

**Status**: ✅ **LISTO PARA DEPLOY**  
**Fecha**: 26 Mayo 2026  
**Cambios pendientes**: 0  
**Problemas pendientes**: 0  

---

## ✅ VERIFICACIONES COMPLETADAS

- [x] Sistema de precios funciona correctamente (x4 multiplicador)
- [x] CSV Hugo Shop accesible (1200 productos)
- [x] Scheduler de seguimiento ACTIVADO
- [x] Función duplicada ELIMINADA
- [x] Archivos sin null bytes
- [x] Sintaxis Python válida en todos los archivos
- [x] No hay funciones truncadas
- [x] Imports correctos
- [x] Base de datos SQLite operativa
- [x] Providers de WhatsApp listos

---

## 🎯 QUÉ SE CAMBIÓ

### 1. main.py — Activación de Scheduler
**Línea 12**: Agregar `import asyncio`
**Línea 40**: Agregar `from agent.followup import iniciar_scheduler as iniciar_scheduler_followup`
**Línea 75-76**: Inicializar en lifespan
```python
asyncio.create_task(iniciar_scheduler_followup())
logger.info("✅ Scheduler de seguimiento de leads ACTIVO")
```

### 2. notifications.py — Eliminar Duplicada
**Línea 8**: Agregar `from agent.commands import parsear_orden_crm`
**Líneas 304-348**: Función duplicada ELIMINADA

### 3. Limpiezas
- Remover 1172 null bytes de notifications.py
- Restaurar main.py a versión válida

---

## 🔧 INSTRUCCIONES PARA DEPLOY

### Paso 1: Git Commit
```bash
cd C:\Users\Elitebook\whatsapp-agentkit
git add .
git commit -m "fix: activar scheduler de seguimiento de leads + eliminar función duplicada

- Activar iniciar_scheduler_followup() en lifespan de main.py
- Eliminar parsear_orden_crm() duplicada de notifications.py
- Limpiar null bytes de archivos
- Scheduler ahora envía seguimientos cada 30 min, retomas, alertas"
```

### Paso 2: Git Push
```bash
git push origin main
```

### Paso 3: Railway Auto-Redeploy
- Railway detectará el push automáticamente
- Redeploy tardará ~2-3 minutos
- Puedes monitorear en: https://railway.app/dashboard

---

## 📊 VERIFICAR POST-DEPLOY

### 1. En Railway Logs, buscar:
```
✅ Scheduler de seguimiento de leads ACTIVO
```

### 2. Esperar 30 minutos y buscar:
```
Seguimiento automático: X leads para contactar
Seg 1/4 [Sofia] [urgente] → 554XXXXXXXX
```

### 3. Si algo está mal:
```bash
# Revisar errores en Railway logs
# O hacer rollback:
git revert HEAD
git push origin main
```

---

## 📋 CAMBIOS RESUMIDOS

| Archivo | Tipo | Líneas | Detalles |
|---------|------|--------|----------|
| main.py | Modificado | +4 | Imports + inicialización scheduler |
| notifications.py | Modificado | -45 | Eliminar función duplicada + import |
| followup.py | Sin cambios | 678 | Ahora se inicializa correctamente |
| pricing.py | Sin cambios | 263 | Sistema de precios intacto |

---

## ⚠️ NOTA IMPORTANTE

**El scheduler ahora REQUIERE que la base de datos esté inicializada.**

Si hay error al iniciar:
```python
asyncio.create_task(iniciar_scheduler_followup())
```

Verificar que `await inicializar_db()` se ejecutó primero (está en línea 58).

---

## 🟢 GO / NO-GO PARA DEPLOY

- [x] Código sintácticamente válido
- [x] Todas las verificaciones pasadas
- [x] Documentación completa
- [x] Sin conflictos conocidos
- [x] Tests de integridad OK

### VEREDICTO: ✅ **GO FOR DEPLOY**

---

## 📞 SOPORTE

Si hay problemas post-deploy:

1. **Revisar logs en Railway** para mensajes de error
2. **Verificar que scheduler está activo** en logs
3. **Si falla, hacer rollback** con `git revert HEAD && git push origin main`
4. **Contactar a Claude** con los logs para diagnosis

---

*Checklist generado automáticamente por auditoría de integridad*  
*Última actualización: 2026-05-26 11:00 UTC*
