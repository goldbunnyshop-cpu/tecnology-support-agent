# 📚 Documentación — Aprendizaje del Bot

Esta carpeta contiene toda la documentación sobre **cómo piensa y actúa el bot**, así como **feedback y mejoras continuas**.

---

## 📖 Archivos

### `LEARNING.md` — Base de conocimiento del bot
Contiene:
- **Filosofía:** Por qué el bot responde como lo hace
- **Reglas de cotización:** Cómo multiplica precios de Hugo Shop
- **Casos especiales:** Centro de carga, displays, software
- **Nunca hacer:** Trampas comunes a evitar
- **Métricas:** Cómo saber si el bot está funcionando bien

**Cuándo leerlo:** Cuando necesites entender la lógica completa del bot o entrenar a alguien más.

---

### `FEEDBACK_LOG.md` — Registro vivo de mejoras
Contiene:
- **Bugs encontrados:** Problemas detectados en chats reales
- **Patrones identificados:** Cosas que pasan repetidamente
- **Soluciones implementadas:** Cambios ya hechos
- **Próximas cosas a observar:** Métricas a monitorear

**Cuándo actualizarlo:** Cada vez que identifiques algo en una conversación que se pueda mejorar.

---

## 🔄 Cómo funciona el aprendizaje

### 1️⃣ Lee las conversaciones del bot

Busca patrones:
- ¿El cliente agendó cita?
- ¿Se sorprendió con el presupuesto final?
- ¿Entendió la explicación de variabilidad?
- ¿Preguntó sobre software/desbloqueo?

### 2️⃣ Documenta en `FEEDBACK_LOG.md`

Usa el template:
```markdown
### [FECHA] — [TIPO: Bug/Mejora/Patrón]
**Resumen:** [Una línea]
**Contexto:** [Qué pasó]
**Solución:** [Qué cambiar]
**Estado:** ⏳ Pendiente
```

### 3️⃣ Implementa la solución

Edita:
- `config/prompts.yaml` (sistema prompt del bot)
- `agent/tools.py` (funciones auxiliares)
- `agent/pricing_mercadolibre.py` (cotizaciones)

### 4️⃣ Marca como implementado

Cambia estado a ✅ Implementado en `FEEDBACK_LOG.md`

### 5️⃣ Hace push a GitHub

```powershell
git add docs/
git commit -m "docs: registrar feedback y mejoras"
git push origin main
```

Railway redeploya automáticamente.

---

## 💡 Ejemplos de mejoras

### Ejemplo 1: Cliente frustrado
```
Cliente: "¿Cuánto cuesta un display?"
Bot: "$1,200"
Cliente: "En MercadoLibre cuesta $400 😤"
Mejora: Explicar rango + "depende de la calidad"
```

### Ejemplo 2: Cliente sin información
```
Cliente: "¿Hay que cambiar batería o qué?"
Bot: [Sin respuesta clara]
Mejora: Usar analogía del choque = cliente entiende
```

### Ejemplo 3: Patrón de éxito
```
Múltiples clientes: "¿Cuándo puedo ir al módulo?"
Patrón: Bot invita a módulo y cliente agenda
Conclusión: Funcionando bien, mantener así
```

---

## 🎯 Qué buscar en las conversaciones

### ✅ Señales de éxito
- Cliente pregunta cuándo puede agendar
- Cliente menciona que confía en el servicio
- Cliente comparte el número con alguien más
- Cliente entiende la analogía del choque

### ⚠️ Señales de alerta
- Cliente se va sin agendar
- Cliente pregunta en 5+ chats por "precio fijo"
- Cliente dice "en otro lado es más barato"
- Cliente se frustra por explicación larga

### 🔴 Señales críticas
- Cliente usa palabras como "engaño" o "ocultan"
- Cliente dice que se le cobró diferente
- Cliente dice que no entiende por qué el rango

---

## 📝 Checklist para retroalimentación

Cada vez que revises conversaciones:

- [ ] ¿Agendó cita el cliente?
- [ ] ¿Entendió el rango aproximado?
- [ ] ¿Preguntó sobre software/desbloqueo?
- [ ] ¿Se quejó de algo?
- [ ] ¿Hay patrón repetido?
- [ ] ¿Necesita cambio en prompts.yaml?
- [ ] ¿Necesita cambio en código?

---

## 🚀 Próximas áreas a documentar

- [ ] Mejora de respuestas por tipo de cliente (adulto mayor vs. joven)
- [ ] Casos de clientes que regresaron vs. que no regresaron
- [ ] Análisis de preguntas más frecuentes
- [ ] Optimization de pasos para agendar cita
- [ ] Performance del bot (velocidad, errores)

---

## 📞 Contacto

Si tienes dudas sobre la lógica del bot, lee `LEARNING.md` primero.
Si identificas una mejora, regístrala en `FEEDBACK_LOG.md`.
