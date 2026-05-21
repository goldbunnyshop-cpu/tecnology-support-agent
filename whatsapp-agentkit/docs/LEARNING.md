# 📚 Aprendizaje y Retroalimentación del Bot

**Última actualización:** 2026-05-21

---

## 📖 Filosofía del Bot

El bot de Tecnology Support no es un cotizador automático. Es un **asesor que genera confianza** invitando clientes al módulo con información aproximada pero honesta.

### Principios clave:
1. **Nunca prometer, siempre verificar** — "El técnico te dará el presupuesto exacto"
2. **Explicar la complejidad** — No es solo el display, puede haber daños internos
3. **Analogía del choque de carros** — Parabrisas roto ≠ motor dañado, pero no sabemos hasta verificar
4. **Rango aproximado, no precio fijo** — Dar rango genera confianza, no frustración

---

## 🎯 Reglas de Cotización

### Hugo Shop (displays solamente)
- **INCELL** → ×4 (genérico)
- **OLED** → ×4 (original)  
- **AMOLED** → ×3 (original)

### Cuando hay UN SOLO tipo:
- **Genérico** = precio × multiplicador
- **Original** = (precio × multiplicador) × 1.25

Ejemplo Samsung A22 INCELL $200:
- Genérico: $200 × 4 = $800
- Original: $800 × 1.25 = $1,000

### Cuando hay MÚLTIPLES tipos:
- Multiplicar rango (menor × mult, mayor × mult)
- Respuesta: "El rango va desde $X hasta $Y, depende de la calidad pero lo verifica el técnico en el módulo"

Ejemplo Samsung A55 (INCELL $200 + OLED $300):
- Rango: $800 a $1,200
- "Va desde $800 hasta $1,200, depende de la calidad"

### MercadoLibre (fallback)
- **Solo si NO hay resultados en Hugo Shop**
- Busca "genérico" + "original"
- Multiplica por 3
- NUNCA revelar la fuente

---

## 💬 Servicios y Respuestas

### ✅ Servicios que cotizamos (con rango):
- Displays, baterías, tapas traseras
- Displays touch
- Reparaciones a nivel componente
- Quitar cuentas (Google/Apple)
- Centros de carga (especial: explicar complejidad)

### ❌ Servicios SOLO en módulo (sin chat):
- Software/virus: "Solo el técnico en módulo"
- Desbloqueos: "Verificar en persona"
- Recuperación datos: "Módulo"
- **Costo:** Nunca mayor al valor del dispositivo
- **Requisito:** Verificar equipo EN PERSONA (obligatorio)

---

## 🔧 Casos especiales

### Centro de Carga
**Dar precio aproximado BUT:**
- Puede no ser solo el puerto
- Puede ser flex de interconexión
- Puede ser tarjeta lógica
- Puede ser corto circuito
- Puede ser batería
- **Cierre:** "El técnico diagnostica la falla real"

### Display
**Usar analogía del choque:**
```
"Es como un choque de carros: visiblemente está roto el parabrisas (el display), 
pero no sabemos si el motor sufrió daños internos (la tarjeta lógica).

En el 85% de casos es solo el parabrisas, pero a veces hay más daños. 
Solo verificando con el cambio sabemos si hay afectaciones extras."
```

**Contexto adicional:**
- Marco doblado = hay que reparar/cambiar también
- Display nuevo en marco doblado = NO resuelve todo
- "No solo es display, hay que valorar la situación"

### IP Ratings — Crítico para displays en equipos premium
**Problema:** Cliente cambia display y pierde certificación IP68 de fábrica.

**Realidad técnica:**
- IP68 original = diseño completo de fábrica con todos los sellos originales
- Al cambiar display = se usan sellos nuevos que NO recuperan IP68
- Nuestros sellos: IP67 en teoría, pero funcionan como IP66
- IP66 = resistencia a polvo + salpicaduras de agua potentes
- IP66 ≠ sumergible en agua (NO aplica para inmersión)

**Equipos con IP68 (avisar al cliente):**
- Samsung S24 Ultra, S25 Ultra
- iPhone 14, 15, 16 Pro
- Google Pixel 7, 8 Pro
- OnePlus 12 Pro
- Sony Xperia 1 Mark VI

**Equipos con IP67:**
- Samsung S24, S25
- iPhone 15, 16
- Google Pixel 8a, 8 Pro
- Otros flagships estándar

**Costo de sellos:**
- **Displays (calidad ORIGINAL + AMOLED):** Sellos incluidos en el precio
- **Tapas traseras:** Sellos se cotizan APARTE (no incluido)
- **Otros cambios:** Evaluar caso a caso

**Qué garantizar al cliente:**
✅ Garantizamos: Polvo + salpicaduras de agua después del cambio
✅ Aplicamos: Sellos de cada fabricante según especificación
❌ NO garantizamos: Inmersión en agua
❌ NO recupera: IP68 original de fábrica

**Respuesta clara al cliente:**
```
"Al cambiar el display, aplicamos los sellos de fábrica para proteger contra 
polvo y salpicaduras (IP66), pero no recupera el IP68 original porque es 
una refacción. Se recomienda evitar sumergir el equipo en agua después del cambio.

Los sellos están incluidos en el costo del display."
```

---

## 🚫 NUNCA hacer esto:
- ❌ Revelar Hugo Shop o MercadoLibre como fuente
- ❌ Dar precio fijo genérico ($900, $500)
- ❌ Prometer que "seguro es solo el display"
- ❌ Cotizar software/desbloqueo sin verificar en persona
- ❌ Usar mismo arranque dos veces seguidas
- ❌ Responder párrafos largos para preguntas simples

---

## 📊 Métricas de éxito (observar)
- ¿El cliente agendó una cita?
- ¿El cliente se sorprendió negativamente con el presupuesto final?
- ¿El cliente recomendaría el servicio?
- ¿Volvió a escribir con más preguntas (señal de confianza)?

---

## 🔄 Retroalimentación (actualizar cuando veas patrones)

### Conversaciones que funcionan bien:
*[Aquí anotar ejemplos de chats donde el cliente agendó cita]*

### Conversaciones problemáticas:
*[Aquí anotar errores, sorpresas, cliente frustrado]*

### Mejoras identificadas:
*[Aquí anotar cambios a hacer en prompts.yaml o tools.py]*

---

## 📝 Plantilla para retroalimentación

Cuando encuentres un patrón, documenta así:

```markdown
### Fecha: 2026-05-XX
**Problema:** [Qué pasó mal]
**Contexto:** [Ejemplos de chats]
**Causa:** [Por qué pasó]
**Solución:** [Cambio a hacer]
**Archivo afectado:** config/prompts.yaml o agent/tools.py
**Estado:** ⏳ Pendiente / ✅ Implementado
```

---

## 🎓 Notas importantes para el futuro

1. **El bot mejora con datos reales** — Cada conversación enseña algo
2. **La confianza > precisión en precio** — Es mejor rango aproximado que sorpresa
3. **El módulo es el hero** — Todo lleva a "verifícalo con el técnico en el módulo"
4. **La analogía del choque es oro** — Mantenla, es lo que genera comprensión
