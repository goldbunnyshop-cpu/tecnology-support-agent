# Filtro de servicios de software sensibles (regla legal)

**Qué hace:** si un cliente (WhatsApp o Messenger) pregunta por FRP/bypass, cuentas Google/Apple/iCloud, bloqueo de activación,
PIN/patrón, liberación de compañía, MDM, IMEI, root/bootloader o modificaciones de consolas (jailbreak, CFW, chip, desbaneo,
juegos, cambio de región), el bot responde SIEMPRE un texto fijo, sin IA, sin precio, sin factibilidad y sin método:

> Ese tipo de servicio de software no se puede valorar por mensaje. El técnico lo revisa físicamente en el módulo para saber si es posible. ¿Le comparto la ubicación y el horario? 😊

Si ya se respondió eso y el cliente insiste (o pregunta "¿y cuánto cuesta?", "¿se puede?"), responde la versión corta con la ubicación.

**Dónde está:**
- `agent/filtro_sensible.py` — patrones, textos y lógica (módulo puro).
- `agent/brain.py` — `generar_respuesta()` lo ejecuta ANTES del motor de precios y de Claude.
- `config/prompts.yaml` — sección "SERVICIOS DE SOFTWARE SENSIBLES" (respaldo si algo se escapa del filtro) y ya no anuncia "desbloqueo".
- `tests/test_filtro_sensible.py` — frases que deben y no deben activarlo.

**Cómo agregar una palabra:** añadir el patrón en `_PATRONES` (texto sin acentos, minúsculas) y la frase en `DEBE_ACTIVAR` del test.

**Pendiente / límites:**
- Los comandos del grupo interno (`diagnostico:`, etc.) mandan al cliente lo que se escriba: el equipo no debe escribir detalles de estos servicios por chat.
- Es filtro por palabras: una redacción muy rara puede escaparse (el prompt sirve de respaldo); un falso positivo solo manda al cliente al módulo.
- Sin alertas al grupo (decisión del dueño). No es asesoría legal; conviene que un abogado revise el procedimiento del módulo.
