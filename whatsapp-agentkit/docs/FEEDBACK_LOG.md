# 📋 Log de Feedback y Mejoras

**Propósito:** Registro vivo de errores, patrones y mejoras del bot basadas en conversaciones reales.

Actualizar este archivo cada vez que identifiques algo que mejorar.

---

## 📌 Template para cada entrada

```markdown
### [FECHA] — [TIPO: Bug/Mejora/Patrón/Éxito]

**Resumen:** [Una línea de qué pasó]

**Contexto:**
- Cliente preguntaba por: [dispositivo/servicio]
- Respuesta del bot: [qué respondió]
- Resultado: [qué pasó - agendó cita / se frustró / preguntó más]

**Análisis:**
- ¿Qué salió bien/mal?
- ¿Por qué?
- ¿Cómo afecta al negocio?

**Solución:** 
- Cambio sugerido: [qué editar]
- Archivo: `config/prompts.yaml` o `agent/tools.py`
- Prioridad: 🔴 Alta / 🟡 Media / 🟢 Baja

**Estado:** ⏳ Pendiente / 🔄 En progreso / ✅ Implementado

---
```

---

## 📈 Entradas actuales

### [2026-05-21] — Bug/Mejora: Eliminar $900 fallback

**Resumen:** El bot respondía con "$900" genérico, cliente se frustró. Cambio a cotizaciones inteligentes.

**Contexto:**
- Cliente preguntaba por distintos servicios
- Bot respondía: "El costo es aproximadamente $900"
- Resultado: Múltiples conversaciones con respuesta genérica

**Análisis:**
- El $900 es un fallback sin contexto
- No explica variabilidad según técnico/equipo/complejidad
- Genera desconfianza (parece precio fijo)

**Solución:**
- Reemplazar con: "Depende del técnico, complejidad, marca/modelo, calidad refacción"
- Implementar cotización variable por Hugo Shop + MercadoLibre
- Archivo: `config/prompts.yaml` + `agent/tools.py`

**Estado:** ✅ Implementado (2026-05-21)

---

### [2026-05-21] — Mejora: Centro de carga sin cotización

**Resumen:** Cliente preguntó "centro de carga motorola g85", bot no respondió con precio.

**Contexto:**
- Pregunta: "¿Cuánto cuesta un centro de carga para Motorola G85?"
- Bot no encontró en Hugo Shop (que solo vende displays)
- Bot no buscó en MercadoLibre
- Resultado: Cliente sin respuesta clara

**Análisis:**
- Hugo Shop ≠ centro de carga
- Motor de cotización no estaba integrado
- MercadoLibre requería búsqueda "genérico" + "original"

**Solución:**
- Crear `agent/pricing_mercadolibre.py` con web scraping
- Buscar doble: "genérico" + "original"
- Multiplicar por 3
- Archivo: `agent/pricing_mercadolibre.py` + integración en `brain.py`

**Estado:** 🔄 En progreso (creado modulo, falta integración)

---

### [2026-05-21] — Patrón: Necesidad de cotizaciones inteligentes

**Resumen:** El bot debe explicar QUÉ da el precio aproximado, no solo el número.

**Contexto:**
- Cliente pregunta: "¿Cuánto cuesta cambiar display?"
- Respuesta efectiva: Rango + "depende de la calidad/modelo"
- Respuesta inefectiva: "$1,200" (número fijo)

**Análisis:**
- La confianza = explicación > precisión
- Rango genera cita, número fijo genera comparación online
- Explicación de variabilidad prepara al cliente para sorpresas

**Solución:**
- Documentar en `LEARNING.md` ✅
- Implementar en `prompts.yaml` ✅
- Usar analogía del choque para displays

**Estado:** ✅ Implementado

---

## 🎯 Próximas cosas a observar

- [ ] ¿El cliente agenda después de cotización aproximada?
- [ ] ¿Se sorprende negativamente con presupuesto real?
- [ ] ¿Entiende la analogía del choque de carros?
- [ ] ¿Pregunta por software/desbloqueo y acepta ir al módulo?
- [ ] ¿El rango de displays es realista o muy amplio?

---

## 📊 Estadísticas rápidas (actualizar mensualmente)

| Métrica | Enero | Febrero | Observaciones |
|---------|-------|---------|---------------|
| Chats totales | — | — | — |
| Citas agendadas | — | — | — |
| Clientes sorprendidos negativamente | — | — | — |
| Preguntas de software | — | — | — |

---

## 🔗 Referencias

- Filosofía: ver `docs/LEARNING.md`
- Reglas de cotización: `config/prompts.yaml` (líneas 220-290)
- Código de cotización: `agent/pricing.py` + `agent/pricing_mercadolibre.py`
