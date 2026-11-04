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

Etiquetas: C/M = con marco, S/M = sin marco, ORIG/AA/COF = calidad original, INCELL = calidad genérica, se quitan CARTAN, BOUTIQUE y la etiqueta de proveedor "(MOVIL IC)". iPhone X11–X17 se muestran como 11–17 (X, XR, XS y XS MAX no cambian).

**iPhone (reglas del 2–3 nov):** 3 calidades, una línea por calidad, con "Calidad" siempre al inicio:
- **Calidad genérica:** INCELL, FHD (LCD) y renglones sin calidad (solo "S/M").
- **Calidad original:** OLED (HARD/SOFT), ORIG, COF, AAA. Al cliente nunca se le dice "autoprogramable".
- **Calidad premium:** solo displays de diagnóstico, con la aclaración "no muestra el mensaje de 'pieza desconocida' en el menú del iPhone". Nunca se dice "diagnóstico".
- Por calidad se toma el producto **más caro** y se aplica x3 con el piso: genérica mínimo $600; original/premium: x3 < $600 → $900, $600–$999 → x3 + $300, $1,000 o más → x3. Si solo hay una calidad y queda en piso, se ofrecen Genérica $600 y Original $900.
- Interno: la premium siempre es la más cara; si la original cuesta más que la de diagnóstico, se intercambian los precios.
- **Escalera:** un modelo nunca cuesta menos que el anterior de su misma línea (13 → 14, 13 Pro → 14 Pro, 13 Pro Max → 14 Pro Max) ni que la variante menor de su generación (Pro Max ≥ Pro ≥ normal; Plus ≥ normal). Si sale más barato: **nuevo = anterior + (anterior − nuevo)**. Ej.: 13 genérica $1,173 y 14 genérica $975 → 14 = $1,173 + $198 = **$1,371**. Se calcula sobre todo el catálogo (`tabla_iphone()`) y se recalcula solo cuando cambia el CSV.
- En iPhone **no** se manda al técnico por pasar de $4,000; se cotiza el x3.

Precios iPhone con la lista del 23 oct:

| iPhone | Calidad genérica | Calidad original | Calidad premium |
|---|---|---|---|
| 6 | $600 | $900 | — |
| 6S PLUS | $600 | $900 | — |
| 8 | $600 | $900 | — |
| SE 2020 | $600 | $900 | — |
| X | $600 | $1,446 | — |
| XR | $819 | — | — |
| XS MAX | $921 | — | — |
| 11 PRO | $756 | $1,503 | — |
| 11 PRO MAX | $930 | — | — |
| 12 | $810 | $1,809 | — |
| 12 PRO | $810 | $1,809 | — |
| 12 PRO MAX | $1,014 | $2,682 | — |
| 13 | $1,173 | $1,809 | $2,541 |
| 13 PRO | $1,305 | — | $2,847 |
| 13 PRO MAX | $1,503 | $2,724 | $2,988 |
| 14 | $1,371 | — | — |
| 14 PRO | $1,392 | $2,880 | $3,540 |
| 14 PRO MAX | $1,596 | $3,540 | — |
| 15 | $1,437 | — | $4,734 |
| 15 PLUS | $1,776 | — | — |
| 15 PRO | $1,500 | $3,540 | $4,734 |
| 15 PRO MAX | $1,887 | $3,576 | — |
| 16 | $1,500 | $3,426 | $4,734 |
| 16 PRO | $2,007 | — | $6,150 |
| 16 PRO MAX | $2,088 | — | — |
| 17 | $2,172 | $4,101 | $6,150 |
| 17 PRO | — | — | $6,150 |
| 17 PRO MAX | — | $5,244 | — |

Si Hugo no tiene el modelo → mensaje de técnico (no se inventa precio). Baterías y tapas siguen con su flujo (Google Sheets).
Pruebas: `tests/test_precio_display_x3.py` (19 casos).

**Catálogo del 23 oct 2026 (cargado el 3 nov):** `knowledge/hugo_shop.csv` se regeneró de `HUGO_SHOP_LISTA_2_Disponibles_23.OCT.26.pdf` (675 productos; Huawei NOVA Y70 viene sin precio). Los 675 precios se cruzaron contra el PDF sin diferencias. Ajustes del lector para este formato:
- Realme viene dentro de la sección OPPO ("REALME- C35", "REALME7 5G/…"): se registra también como marca REALME.
- Se quita el prefijo de marca repetido en la descripción ("XIAOMI-MI12T" → "MI12T").
- iPhone: el catálogo antepone X al modelo (X11 = iPhone 11, X13 MINI = iPhone 13 mini); el cliente escribe "iPhone 13" y se busca como X13. X, XR, XS y XS MAX son modelos reales.
- iPhone: "JK X14" (JK = marca del panel) y "2 X14PRO" (dígito suelto) se leen como X14 / X14PRO; "8G" y "6G" = iPhone 8 y 6; se quita "- 120HZ" del nombre.
- iPhone: "(Diagnóstico)" o "-DIAGNÓSTICO" se quita del nombre y se marca como calidad premium (X13, X13PRO, X13PRO MAX, X14PRO, X16PRO, X17, X17PRO).

Ejemplos:

| Modelo | Antes (código de julio) | Ahora (regla x3 + lista 23 oct) |
|---|---|---|
| Alcatel 5024 | Calidad Original: $832 | Calidad genérica: $624 / Calidad original: $924 |
| Samsung A54 | Con Marco: $1,132 | Calidad genérica: $849 / Calidad original: $1,149 · Calidad original OLED con marco: $1,812 |
| Samsung S24 FE | Calidad Original: $2,240 · Con Marco: $2,628 | Calidad original HARD OLED con marco: $1,866 |
| Motorola Edge 30 Neo | Calidad Original: $4,324 | Calidad original SOFT OLED sin marco: $2,487 |
| Oppo A17 | técnico | Calidad genérica: $600 / Calidad original: $900 · Calidad genérica: $675 / Calidad original: $975 |
| iPhone XR | Calidad Original: $952 | Calidad genérica: $609 · Calidad original: $1,119 |
| iPhone 13 | Calidad Genérica: $1,176 · Calidad Original: $3,034 | Calidad genérica: $1,173 · Calidad original: $1,809 · Calidad premium: $2,541 |
| iPhone 14 | Calidad Genérica: $1,272 · Calidad Original: $3,251 | Calidad original: $1,275 |
| iPhone 15 Pro Max | Calidad Genérica: $1,872 · Calidad Original: $4,627 | Calidad genérica: $1,596 · Calidad original: $3,504 |

**Lista manual de iPhone (3 nov, reemplaza todo lo anterior para iPhone):** Christian capturó a mano los precios al cliente de 42 modelos en `knowledge/precios_iphone.csv` (columnas `modelo,generica,original,premium,nota`; vacío = no se ofrece esa calidad). Es la **única fuente de precios de display de iPhone**: `pricing_fallback` la consulta primero (`cotizar_iphone_manual`) y ya no se aplican x3, piso ni escalera a iPhone. Si el modelo no está en la lista → técnico. Si el cliente dice solo "SE" → pregunta cuál SE. "iPhone SE 2022" funciona aunque el detector de modelo quite el "SE". Para cambiar un precio basta editar el CSV y subirlo (se recarga solo al cambiar el archivo). Ojo: `knowledge/*` está en `.gitignore`, así que se sube con `git add -f`.
Revisar en la lista: el 13 quedó más barato que el 12 en las tres calidades, y el premium del 16 Plus ($3,750) quedó debajo del del 16 ($3,900).

**Cotización de iPhone en 2 mensajes (3 nov, madrugada):** toda cotización de pantalla de iPhone se manda en dos mensajes de WhatsApp, con 2 s entre ellos:
1. **Precios con pros y contras de cada calidad, juntos para comparar.**
   - Genérica: "funciona bien para uso diario, pero…". En OLED (12 en adelante, X, XS, 11 Pro) dice "menos brillo, colores menos vivos y puede gastar más batería"; en LCD (XR, 11, SE, 8, 7, 6) solo dice "colores menos vivos".
   - Original: "colores, brillo y respuesta táctil como la de fábrica".
   - Premium: "lo más cercano a la de fábrica y no muestra el aviso de pieza desconocida".
   - El aviso de "pieza desconocida" se menciona solo del iPhone 11 en adelante.
2. **Valor del servicio.** Somos especialistas en Apple y lo atiende personal certificado. La pantalla es la pieza más cara después de la tarjeta madre. Incluye limpieza interna profesional, limpieza de bocinas, micrófonos, conectores y puerto de carga, garantía de 90 días y cambio el mismo día. Cierra con "¿Cuál opción te interesa?".
- **Nunca mencionar Face ID.** En un equipo mojado el cliente reclamó el Face ID después de cambiar la pantalla y lo tuvo que pagar el taller.
- **Mecánica:** el texto lleva el marcador `[[SIGUIENTE]]` (`agent/providers/base.py`: `partir_mensaje` / `unir_mensaje`).
  - WAHA y Whapi lo parten en varios envíos. Messenger e Instagram lo mandan en un solo mensaje.
  - El historial lo guarda sin el marcador.
  - El cargo a domicilio va en el mensaje 1, junto a los precios.
- **Archivos:** `agent/pricing.py` (`_formatear_iphone`, `_VALOR_SERVICIO_IPHONE`, `_IPHONE_LCD`), `agent/providers/*.py`, `agent/main.py` (`_para_historial`), `agent/filtro_domicilio.py`.
- **Pruebas:** `tests/test_precio_display_x3.py`.

**Fix 4 nov: iPhone solo con lista manual.**
- **Logs de producción:**
  - "Iphone 15 pro máx" con acento no encontraba el modelo y mandaba al técnico.
  - "iPhone XS" y "XR" no se detectaban como modelo.
  - "12 pro cambio" no se reconocía.
  - En producción quedó la versión sin explicación breve para los LCD.
- **Ahora:**
  - Hugo Shop queda bloqueado para iPhone por todos los caminos (`_resolver_match_hugo`, `obtener_cotizacion_display`, búsqueda sin marca).
  - El único origen es `knowledge/precios_iphone.csv`; si el modelo no está en la lista, se manda al técnico.
  - Nuevo parser `_clave_consulta_iphone` / `modelo_iphone_de_texto`:
    - quita acentos y palabras de más;
    - reconoce X, XR, XS, XS Max, SE 2020/2022 ("se me cayó" no cuenta como SE), "15pro max", "8+", "16 e" y "iphone 10" = X.
  - `brain._extraer_marca_modelo` usa ese parser cuando la marca es iPhone.

**Fix 4 nov: cita repetida en el grupo interno.**
- **Logs, caso Raúl, PS4, 3 nov:** Claude volvió a mandar `[[AGENDAR]]` un minuto después de confirmar. Se creó un segundo evento en Google Calendar con otro id. El aviso al grupo deduplicaba por id del evento, así que lo volvió a mandar.
- **Ahora, antes de agendar:** si ya hay una cita de ese teléfono en ±2 h (`cita_detector.existe_cita_cercana`), no se crea otro evento ni se vuelve a avisar.
- **Ahora, en `notificar_nueva_cita`:** también se deduplica por teléfono + día + hora (`slot:<tel10>:<fecha><hora>`), aunque el evento tenga otro id.
- **Prueba:** `tests/test_cita_duplicada.py`.
- **Pendiente:** borrar a mano en Google Calendar los eventos duplicados que ya existen (ej. Raúl, jueves 5 nov 10:30, hay 2).

Regreso a Whapi: ver `MIGRAR_A_WHAPI.md` (se puede hacer solo desde el celular).

---

## 5. Pendientes

1. ~~Actualizar el catálogo~~ — **hecho 3 nov**: `knowledge/hugo_shop.csv` se regeneró de `HUGO_SHOP_LISTA_2_Disponibles_23.OCT.26.pdf` (675 productos; 1 sin precio: Huawei NOVA Y70).
2. (Ya no aplica a iPhone: ahora manda la lista manual.) La lista del 23 oct no trae: iPhone 11 normal, 12 mini, 13 mini, 14 Plus, 16 Plus, 8 Plus ni 7 (el bot pregunta la versión o pasa al técnico). Faltan calidades en varios modelos (ej. 14 sin original, 17 Pro solo premium); se pueden completar con otro proveedor.
3. Matching: "Samsung A32 4G" y "Redmi Note 13 4G" vuelven a preguntar la variante aunque el cliente ya la dijo.
4. Evaluador: el caso `m03-identidad-bot` espera que el bot nunca admita ser asistente virtual; el prompt dice que sí lo admita si se lo preguntan. Falta decidir y alinear.
5. WAHA: probar envío de fotos y PDF (`nota:`) en Core; agregar alerta si la sesión se cae; decidir si se queda WAHA, se regresa a Whapi o se migra a la API oficial de Meta (desde el 1 oct 2026 Meta cobra los mensajes de servicio después de 1,000 gratis al mes; las conversaciones que vienen de anuncios Click-to-WhatsApp son gratis hasta 7 días).
6. Pendientes previos: Honor Magic 6 y Samsung S21 Ultra en catálogo (`BUGS_RESUELTOS_OCT2026.md`).
