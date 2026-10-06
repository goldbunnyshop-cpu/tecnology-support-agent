# Bugs Resueltos — Octubre 2026
> Registro de los bugs detectados en conversaciones reales con clientes y sus correcciones.
> Todos los fixes fueron validados contra logs de Railway y capturas de WhatsApp.

---

## BUG #1 — Motor de pricing no disparaba para Samsung S24 FE
**Síntoma**: Cliente preguntó precio de pantalla del S24 FE y el bot respondió con pregunta en lugar de cotizar.
**Causa**: El motor de pricing no reconocía "S24 FE" como variante del S24.
**Fix**: `agent/brain.py` — normalización de variantes con sufijo "FE/fe".

---

## BUG #2 — "Original" no devolvía precio específico tras mostrar opciones
**Síntoma**: Bot mostraba "Genérica $X / Original $Y" y cuando el cliente respondía "Original", el bot decía "¡Perfecto!" en lugar de confirmar el precio.
**Causa**: El selector de calidad no detectaba la respuesta de una sola palabra.
**Fix**: `agent/brain.py` — `_CALIDAD_SELECTORES` con re-cotización automática usando historial.

---

## BUG #3 — Motorola Edge 60 Fusion devolvía precio incorrecto ($900 en lugar de ~$3,200)
**Síntoma**: Cliente pidió precio de display Motorola Edge 60 Fusion. El motor retornó precio de un modelo diferente.
**Causa**: El motor hacía match con "Motorola 60" (modelo más barato) ignorando "Edge" y "Fusion".
**Fix**: `agent/pricing.py` / `agent/pricing_fallback.py` — matching más específico para modelos con prefijo de palabra.

---

## BUG #4 — Honor Magic 6 no estaba en catálogo
**Síntoma**: El bot no pudo cotizar el Honor Magic 6. Christian tuvo que intervenir manualmente con el precio ($1,850).
**Causa**: El modelo no existía en el CSV ni en Google Sheets.
**Fix**: Agregar Honor Magic 6 al catálogo de precios (Google Sheets / hugo_shop.csv).
**Estado**: PENDIENTE — requiere acción manual de Christian en el catálogo.

---

## BUG #5 — False positive [MANUAL]: eco de Whapi marcado como intervención del dueño
**Síntoma**: Log de Railway mostraba `[MANUAL] Intervención del dueño guardada` inmediatamente después de que el bot envió el followup final a Magali ("Hola Magali, es la última vez que te escribimos..."). El bot confundió el eco de Whapi con una intervención manual de Christian.
**Causa**: Cuando el bot envía un mensaje via API, Whapi reenvía un webhook con `from_me=True` — indistinguible del mensaje manual del dueño sin tracking adicional.
**Fix planeado**: `agent/main.py` — diccionario `_ULTIMA_RESPUESTA_BOT: dict[str, float]` con timestamps. Si `from_me=True` llega en los 30 segundos siguientes al último envío del bot al mismo número → es eco, se ignora sin guardar `[DUEÑO]`.
**Estado**: PENDIENTE de implementación.

---

## BUG #6 — Samsung S21 Ultra: precio no cotizado + menú no reconoció modelo en texto libre
**Síntoma (A)**: Cliente escribió "De un Samsung S21 ultra" como respuesta al menú. El bot respondió "No reconocí tu selección" y repitió el menú.
**Causa A**: `_MENU_OPCIONES` solo mapeaba coincidencias exactas de número o palabra ("celular", "1", etc.). Texto libre con modelo no hacía match.
**Fix A**: `agent/main.py` — detección secundaria por marcas conocidas (25+ marcas de celular, consolas, laptops, tablets) antes de reenviar el menú.

**Síntoma (B)**: El S21 Ultra tenía pantalla curva y el bot nunca dio el precio, dijo "el precio puede variar, necesito verificar con el técnico".
**Causa B**: Samsung S21 Ultra no estaba siendo cotizado correctamente por el motor.
**Fix parcial**: Investigar en catálogo; agregar si falta.
**Estado**: PENDIENTE verificación en catálogo.

---

## BUG #7 — Análisis de imagen incoherente y solicitud automática de fotos
**Síntoma**: El bot pedía foto a todos los clientes después de describir el problema, sin importar que ya hubieran declarado el modelo. Cuando el cliente mandaba la foto del frente de la pantalla rota, el bot generaba texto incoherente ("No determinable con certeza. No determinable parcialmente...").
**Causa**: El PASO 3 del system prompt instruía pedir fotos después de cada descripción de problema. El análisis de visión es genérico y no sabe identificar modelos desde fotos del frente.
**Fix**: `config/prompts.yaml` — PASO 3 reescrito:
- NUNCA pedir foto automáticamente
- Solo pedirla si el cliente no sabe el modelo (foto de la parte trasera) o si hay ambigüedad vidrio vs. OLED
- Si el cliente envía foto voluntariamente: usarla como contexto pero no retrasar el precio

---

## BUG #8 — Bot daba rangos de precio para reparaciones de controles/consolas
**Síntoma**: Cliente preguntó precio de drift/joystick de controles Xbox/Nintendo. El bot inventó rango "$800-$1,200 MXN" (y peor, "$1,500-$1,600 para 6 controles" con matemática incorrecta).
**Causa**: El motor de pricing no cubre consolas/controles → Claude improvisa rangos cuando el cliente insiste en un número.
**Fix**: `config/prompts.yaml` — Nueva regla explícita:
- PROHIBIDO dar rangos de precio para controles y consolas
- Respuesta correcta: diagnóstico $200 bonificable + "reparar siempre es más barato que comprar uno nuevo"
- Aplica a: drift, joystick, botones, gatillos, carcasas, fallas de encendido

---

## BUG #9 — Bot revelaba al cliente que "el dueño del módulo ya confirmó"
**Síntoma**: Después de que Christian intervino manualmente con el precio del Realme 12+ ($600/$900), el bot le dijo al cliente: "El dueño del módulo ya confirmó que tenemos disponibilidad para el Realme 12+".
**Causa**: El texto del contexto inyectado decía "El dueño del negocio intervino directamente". Claude lo parafraseaba literalmente hacia el cliente, exponiendo el flujo interno.
**Fix**: `agent/main.py` — El contexto ahora dice "INFORMACIÓN DEL SISTEMA: El siguiente dato ya fue confirmado internamente..." con instrucción explícita: "NUNCA menciones al 'dueño' ni que alguien 'confirmó' o 'intervino'."

---

## Bugs pendientes de resolución completa

| Bug | Descripción | Pendiente |
|-----|-------------|-----------|
| #4  | Honor Magic 6 sin precio | Agregar al catálogo manualmente |
| #5  | False positive [MANUAL] por eco Whapi | Implementar supresión por timestamp (30s) |
| #6B | Samsung S21 Ultra no cotizado | Verificar y agregar al catálogo |

---

*Última actualización: 2026-10-06*
