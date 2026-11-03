# Bitácora — septiembre a noviembre 2026

> Resumen de todo lo que cambió en el agente de WhatsApp de Tecnology Support entre el 1 de septiembre y el 2 de noviembre de 2026.
> Incluye la migración de Whapi a WAHA (2 nov), el ajuste de costos de la API y la corrección de precios.
> Documentos de detalle que siguen vigentes: `BUGS_RESUELTOS_OCT2026.md`, `NOTA_SERVICIO_PDF.md`, `FILTRO_SOFTWARE_SENSIBLE.md`, `ESCALA_Y_MANTENIMIENTO_DB.md`.
> **Ojo:** `FIXES_SUMMARY.md` (agosto) describe multiplicadores x4 / imobile x1.5 que **ya no aplican** (ver sección 4).

---

## 1. Estado actual (2 nov 2026, noche)

| Pieza | Estado |
|---|---|
| Proveedor de WhatsApp | **WAHA Core** (gratis, self-hosted en Railway). Whapi desactivado por falta de pago. |
| Proyecto Railway | `helpful-prosperity`: servicios `tecnology-support-agent`, `waha` (con volumen `/app/.sessions`) y `Postgres` |
| Sesión de WhatsApp | `default`, motor GOWS, estado WORKING |
| Modelo de IA | `claude-sonnet-4-6` (respuestas) y `claude-haiku-4-5` (fotos, citas, seguimientos, reportes) |
| API key | una sola: "Whastapp Anthropic" |
| Gasto API | $41.03 en 30 días (≈ $1.37/día; ≈ $1.60/día desde el 28 oct) |
| Catálogo de displays | **solo Hugo Shop** (`knowledge/hugo_shop.csv`) con regla x3 |
| Horario del bot | 24 h; fuera de horario avisa que el equipo humano retoma 10:30 (L-V) / 11:30 (S-D) |

---

## 2. Cambios de septiembre 2026

| Fecha | Cambio |
|---|---|
| 07-sep | Motor de precios: modelos con prefijo de palabra (Edge 50 Fusion); el piso no inventa "Original" si no hay stock; acentos en variantes. |
| 14-sep | Menú inicial por categoría de dispositivo y presentación como asistente virtual en el primer mensaje. |
| 14-sep | Detección de intervención manual del dueño: lo que escribe Christian se guarda como `[DUEÑO]` y el bot no lo contradice ni re-cotiza encima. |
| 14-sep | Fixes: fuga del bloque "DISPONIBILIDAD REAL" al cliente, "10 +" → "10+", guarda para que un precio no se tome como modelo. |
| 17-sep | **Regla de precio de displays x3** definida (en chat, no se aplicó al código hasta el 2 nov — ver sección 4). |

## 3. Cambios de octubre 2026

| Fecha | Cambio |
|---|---|
| 06-oct | Pool de base de datos ampliado y limpieza semanal automática de tablas (lunes 3:00 am). Ver `ESCALA_Y_MANTENIMIENTO_DB.md`. |
| 06–11-oct | Bugs de octubre (detalle en `BUGS_RESUELTOS_OCT2026.md`): S24 FE, selector "Original", Edge 60 Fusion, menú con texto libre, no pedir fotos automáticas, **sin rangos de precio en consolas/controles**, no revelar al "dueño", controles de consolas obsoletas. |
| 11-oct | Triage para fallas sin daño visible, advertencia de "errores por capas", **diagnóstico $200 bonificable**. |
| 11-oct | Consolas: apagado repentino y errores de arranque Xbox → siempre diagnóstico. Garantía universal: la reparación nunca cuesta más que el equipo. |
| 11-oct | **Nota de servicio en PDF** (comando `nota:`). Ver `NOTA_SERVICIO_PDF.md`. |
| 11-oct | **Filtro legal de software sensible** (FRP, cuentas, IMEI, jailbreak…): respuesta fija sin IA. Ver `FILTRO_SOFTWARE_SENSIBLE.md`. |
| 19–21-oct | **Servicio a domicilio**: solo si el cliente lo pregunta; precio normal + $400 con desglose; cobertura 8 km por CP/colonia (`config/cobertura_domicilio.csv`); nunca se niega, se transfiere a un responsable; aviso al grupo y pausa. |
| 21-oct | **Fotos**: el bot ya no describe el daño ni habla de costos; solo pide foto trasera; aviso al grupo con @mención a Christian y pausa de 2 h. Nunca "diagnóstico sin costo". |
| 28-oct | Cliente foráneo (viene a CDMX en cierta fecha): confirma fecha, da ubicación completa, avisa que se confirma la refacción antes del viaje. Modelo estimado por IA de una foto = no confirmado. |
| 28-oct | Fotos y videos: respuesta siempre fija (sin excepción para "capturas"). |
| 29-oct | Eco de Whapi: lo que envía el bot ya no se guarda como `[DUEÑO]` (el motor de precios dejaba de cotizar). Catálogo con prefijos W/F, WF. Primer mensaje con pregunta se atiende directo (menú solo si únicamente saluda). |
| 29-oct | **Bot 24 h**: se quitó el modo nocturno; fuera de horario cotiza e informa y cambia "en breve" por "mañana a partir de las 10:30". |

---

## 4. Cambios del 2 de noviembre 2026

### 4.1 Migración de Whapi a WAHA (reemplazo temporal)
**Motivo:** no se pudo pagar la mensualidad de Whapi; Railway y los créditos de la API sí están pagados.

**Código (`agent/providers/waha.py`, nuevo):**
- Recibe el webhook de WAHA (`message`, `message.any`) y lo normaliza al mismo `MensajeEntrante` que usaba Whapi.
- Envía texto (`/api/sendText`), "escribiendo…" (`/api/startTyping`), imagen (`/api/sendImage`) y documento PDF (`/api/sendFile`).
- Reusa el registro de ecos de Whapi para que lo que manda el bot no se tome como intervención del dueño.
- Resuelve números `@lid` al teléfono real.
- `agent/providers/__init__.py`: `WHATSAPP_PROVIDER=waha` activa el adaptador.
- `agent/main.py`: las fotos se descargan del servidor WAHA (no de Whapi).
- `agent/appointment_notifications.py` y `agent/followup.py`: los avisos al grupo usan el proveedor activo y el ID fijo del grupo (antes buscaban el grupo en la API de Whapi).

**Railway:**
- Servicio nuevo `waha` (imagen `devlikeapro/waha`), volumen en `/app/.sessions`, dominio `waha-production-d22d.up.railway.app`.
- Variables de `waha`: `PORT=3000`, `WHATSAPP_API_PORT=3000`, `WHATSAPP_DEFAULT_ENGINE=GOWS`, `WHATSAPP_HOOK_URL=https://${{tecnology-support-agent.RAILWAY_PUBLIC_DOMAIN}}/webhook`, `WHATSAPP_HOOK_EVENTS=message.any`, `WAHA_DASHBOARD_USERNAME=admin`, `WAHA_API_KEY`, `WAHA_DASHBOARD_PASSWORD`.
- Variables nuevas del bot: `WHATSAPP_PROVIDER=waha`, `WAHA_URL`, `WAHA_API_KEY` (igual a la de `waha`), `GRUPO_CHRISTIAN_INTERNO=120363423715417410@g.us`. `WHAPI_TOKEN` se dejó para poder regresar.
- Se cerró la sesión de Whapi en el teléfono y se escaneó el QR en `https://waha-production-d22d.up.railway.app/dashboard`.

**Para regresar a Whapi:** pagar Whapi, cambiar `WHATSAPP_PROVIDER=whapi`, cerrar la sesión de WAHA en el teléfono y volver a vincular Whapi.

**Diferencias de WAHA Core contra Whapi:**
- No detecta si el lead viene de un anuncio (todo queda como "orgánico").
- Envío de imágenes y PDF en Core: sin confirmar; si falla, el log dice `[WAHA] Error /api/sendFile`.
- Mismo riesgo de bloqueo (ambos son conexiones no oficiales).
- Si WhatsApp cierra la sesión, el bot queda mudo hasta reescanear el QR (no hay alerta todavía).

### 4.2 Errores encontrados después de la migración (corregidos)
| Error | Causa | Arreglo |
|---|---|---|
| `NameError: timedelta` en el mantenimiento semanal de BD | faltaba el import en `agent/followup.py` (error previo a WAHA) | se agregó `timedelta` al import |
| **El bot publicó 9 estados de WhatsApp** (vistos por hasta 1,834 contactos) | WAHA entrega los estados de los contactos como mensajes de `status@broadcast`; el bot los contestaba y eso publica un estado. Whapi no los mandaba. | `waha.py` ignora `status@broadcast` y canales (`@newsletter`) y bloquea cualquier envío a ellos |
| Avisos con foto a Christian fallaban: `recipient is not on WhatsApp: 5541576331` | WAHA necesita el número con `521`; Whapi lo completaba solo | `waha.py` completa `521` en números de 10 dígitos |

### 4.3 Revisión del gasto de créditos
- Consola de Anthropic: una sola key (el bot). No hay fuga.
- 1 nov (UTC) $3.06 · 2 nov $1.67. Los $5 recargados el 1 nov se agotaron; la recarga del 2 nov estaba casi intacta ($4.94).
- 60% del costo era reescribir la caché: cada conversación nueva cargaba ~13,200 tokens de instrucciones.
- Decisión: **opción A — compactar las instrucciones** (se descartó usar Haiku para mensajes simples).

### 4.4 Instrucciones del bot compactadas (`config/prompts.yaml`)
- De ~13,200 a ~6,150 tokens. Ahorro estimado ≈ 40% del costo diario.
- Se verificaron 57 reglas del original (precios, horarios, domicilio, legal, citas, reseña, tag `[[AGENDAR:...]]`).
- Contradicciones resueltas:
  - Fotos: solo foto trasera (modelo) o pregunta vidrio vs. pantalla; se quitó "pide fotos o videos".
  - Precios: displays, baterías y tapas con precio del sistema sí; lo demás no se inventa.
  - Se quitó "te doy un rango" (contradecía "nunca rangos").
  - Identidad: admite ser asistente virtual si se lo preguntan; nunca menciona Claude/OpenAI ni detalles técnicos. Se quitó "(yo, Claude)".
  - Drones y cámaras: se dejan como servicio que sí se atiende.
  - Se quitaron el aviso del 26 de julio, el ejemplo de precios falsos de displays ("$800 / $1,200 / AMOLED $1,400") y el voseo ("Podés").
- Evaluación (12 casos): 10/12. Las 2 fallas eran del evaluador (precio PS5 viejo y la regla de identidad).

### 4.5 Precios de mantenimiento de consolas
Sin duplicados en el código: los precios viven en `config/prompts.yaml` (el ejemplo de domicilio en `agent/filtro_domicilio.py` coincide).

| Consola | Precio (IVA incluido, tarjetas sin comisión) |
|---|---|
| PS5 | $1,400 |
| PS4 / PS4 Slim / PS4 Pro | $900 |
| PSP | $400 |
| PS Vita | $600 |
| Xbox One (2013) | $600 |
| Xbox One S / One X | $800 |
| Xbox Series S | $1,200 |
| Xbox Series X | $1,400 |
| Nintendo Switch / Switch Lite | $600 |
| Nintendo Switch OLED | $800 |
| Wii | $500 |
| Wii U | $600 |
| PS3, PS2, PS1, Xbox 360, Xbox original, GameCube | No se da mantenimiento (sí se reparan sus controles) |

El evaluador (`tests/eval/dataset.py`, `tests/eval/judge.py`) tenía una lista vieja (PS5 $1,300, PS4 $850, PS3 $450, Series S $1,100, Xbox One $950, One S/X $600, Switch $500) y se actualizó a esta tabla.

### 4.6 Precios de displays — regla x3 aplicada al código
**Antes (código de julio, seguía en producción):** Hugo Shop x4 (AMOLED x3) promediando productos, imobile (Google Sheets) x1.5 y fixoem como respaldo.

**Ahora (`agent/pricing.py` → `formatear_cotizacion_hugo`, `agent/pricing_fallback.py`):** solo Hugo Shop, renglón por renglón del catálogo:

| Costo PRECIO_1 × 3 | Precio al cliente |
|---|---|
| menos de $600 | Genérica $600 / Original $900 |
| $600 a $999 | Genérica = x3 / Original = x3 + $300 |
| $1,000 a $4,000 | x3 exacto con la calidad tal cual del catálogo |
| más de $4,000 | no se cotiza: lo cotiza un técnico |

Etiquetas: C/M = con marco, S/M = sin marco, ORIG/AA/COF = calidad original, INCELL = calidad genérica, OLED (solo iPhone) = calidad premium; se quitan CARTAN, BOUTIQUE y la etiqueta de proveedor "(MOVIL IC)". iPhone X11–X17 se muestran como 11–17 (X, XR, XS y XS MAX no cambian).
Si Hugo no tiene el modelo → mensaje de técnico (no se inventa precio). Baterías y tapas siguen con su flujo (Google Sheets).
Pruebas: `tests/test_precio_display_x3.py`.

Ejemplos (catálogo actual del repo):

| Modelo | Antes | Ahora |
|---|---|---|
| Alcatel 5024 | Original $832 | Genérica $624 / Original $924 |
| Samsung A54 | Con marco $1,132 | Genérica $849 / Original $1,149 |
| Samsung S24 FE | Original $2,240 · Con marco $2,628 | HG HARD OLED sin marco $1,680 · con marco $1,971 |
| Motorola Edge 30 Neo | Original $4,324 | OLED sin marco $3,243 |
| iPhone XR | Original $952 | $600/$900 · $819/$1,119 |
| iPhone 14 | Genérica $1,272 · Original $3,251 | 6 opciones de $954 a $3,096 + 1 que cotiza el técnico |

---

## 5. Pendientes

1. **Actualizar `knowledge/hugo_shop.csv`** con el catálogo más reciente: el que está en el repo es de julio (ej. Alcatel 5030 1SE cuesta $185 en el CSV y $169 en la lista de septiembre).
2. Decidir si en displays con muchas opciones (iPhone 14: 7 renglones) se muestran todas o solo las más baratas por calidad.
3. Matching: "Samsung A32 4G" y "Redmi Note 13 4G" vuelven a preguntar la variante aunque el cliente ya la dijo.
4. Evaluador: el caso `m03-identidad-bot` espera que el bot nunca admita ser asistente virtual; el prompt dice que sí lo admita si se lo preguntan. Falta decidir y alinear.
5. WAHA: probar envío de fotos y PDF (`nota:`) en Core; agregar alerta si la sesión se cae; decidir si se queda WAHA, se regresa a Whapi o se migra a la API oficial de Meta (desde el 1 oct 2026 Meta cobra los mensajes de servicio después de 1,000 gratis al mes; las conversaciones que vienen de anuncios Click-to-WhatsApp son gratis hasta 7 días).
6. Pendientes previos: Honor Magic 6 y Samsung S21 Ultra en catálogo (`BUGS_RESUELTOS_OCT2026.md`).
