# Nota de servicio en PDF (comando `nota:`)

Implementado: 11/10/2026. Estado: código listo en el repo; **pendiente de probar en producción** (ver "Pendientes").

## Qué hace

Desde el grupo interno (**Taller Interno TS**) se escribe un comando `nota:` con los datos del equipo. El bot:

1. Valida los datos y, si falta algo, **guarda lo capturado** y avisa qué falta (no hay que reescribir todo).
2. Genera un PDF con el mismo formato de la nota física (media carta, 140 x 216 mm), usando el **folio de la nota física**.
3. Envía el PDF al cliente por WhatsApp (Whapi) y una **copia al grupo** con el estado del envío.
4. Si el comando trae `pago:`, registra también la orden en el CRM (igual que el comando `nota:` anterior).

La **fecha nunca se pone sola**: si no viene `fecha:`, la nota no se genera.

## Cómo se usa

```
nota: folio: 11111 fecha: 12/10/26 cliente: Ricardo Alvarez telefono: 4455445544 marca: Samsung modelo: S23 Ultra falla: cambio de bateria costo: 2000
```

- Cada dato lleva su etiqueta con dos puntos. El **orden no importa**. Puede ir en una línea o una por renglón.
- **Obligatorios:** `folio`, `fecha`, `cliente`, `telefono`, `marca`, `modelo`, `costo` y `falla` (o `diagnostico`).
- Un número suelto al inicio se toma como folio si ya se puso `telefono:`; si no se puso `telefono:` y tiene 10+ dígitos, se toma como teléfono.
- Mayúsculas, acentos y espacios antes de los dos puntos no importan (`Teléfono :` funciona).
- Fecha: `DD/MM/AA` o `DD/MM/AAAA` (también con guiones).
- `cliente` y `marca` se capitalizan solo si vinieron todo en minúsculas o todo en mayúsculas (`ricardo alvarez` -> `Ricardo Alvarez`; `iPhone` y `DELL` se respetan).
- `saldo` se calcula solo: `costo - anticipo`.

### Campos opcionales (los de la nota física)

| Etiqueta | Alias | Valores / notas |
|---|---|---|
| `tipo` | `equipo` | Laptop, Celular... |
| `imei` | `serie` | texto libre |
| `domicilio` | `direccion` | texto libre |
| `hora` | | hora de entrada |
| `entrega` | | fecha y hora de entrega (texto libre) |
| `estimado` | | `mismo dia` o `sujeto` |
| `tiempo` | | tiempo para diagnosticar |
| `diagnostico` | | texto libre |
| `caracteristicas` | `caracteristica` | texto libre |
| `riesgos` | `riesgo` | texto libre |
| `danos` | `dano` | `roto`, `abollado`, `carcaza`, `estrellado` (varios separados por coma) o `ninguno`. Solo se marcan SÍ las que se escriban; con `ninguno` todas salen NO; sin `danos:` quedan en blanco |
| `chip` | `sim` | si/no u otro texto |
| `funda` | | si/no u otro texto |
| `accesorios` | `accesorio` | texto libre |
| `autorizo` | `autorizacion` | `firma`, `whatsapp` o ambos |
| `calidad` | | `premium`, `original` o `generica` |
| `estado` | | `prendido` o `apagado` |
| `anticipo` | | número; no puede ser mayor que el costo |
| `pago` | | `efectivo`, `tarjeta` o `transferencia`. Si se pone, la orden también se registra en el CRM |
| `refaccion` | | costo de la refacción (solo CRM, no sale en el PDF) |
| `costo` | `total` | número (acepta `$` y comas) |
| `telefono` | `tel`, `celular` | 10 dígitos |
| `cliente` | `nombre` | |

El campo `presupuesto:` **no existe** en el comando (en el PDF la casilla "Costo presupuesto SI/NO" queda sin marcar, como en la nota física sin llenar).

## Datos incompletos: borradores

Si falta o falla un dato, el bot responde algo como:

```
⚠️ Nota #11111 incompleta — guardé lo que ya mandaste.
✅ Guardado: folio, cliente, telefono, marca, modelo, falla, costo
❌ Falta: fecha: (DD/MM/AA)

Responde SOLO con lo que falta, por ejemplo:
nota: folio: 11111 fecha:
```

Se contesta solo con el folio y lo que falta (`nota: 11111 fecha: 12/10/26`) y se genera la nota.

Reglas (`agent/nota_parser.py`):

- Un valor inválido (ej. `pago: bitcoin`) se **descarta** del borrador y se pide de nuevo; lo demás se conserva.
- **Etiqueta mal escrita** (ej. `diagnosico:`): el bot sugiere la correcta y deja la línea lista con lo que se escribió. Nunca se mezcla en silencio con otro campo.
- Etiqueta escrita dos veces con valores distintos: se descarta y se pide una sola vez.
- El borrador se identifica por (chat, folio) o, si aún no hay folio, (chat, teléfono). **Un mensaje solo se une a un borrador con el mismo folio o teléfono**, para no mezclar datos de dos notas.
- Sin folio ni teléfono se guarda un borrador "sin ancla" que solo se completa con un mensaje que traiga únicamente `folio:` y/o `telefono:`.
- Mensaje sin folio ni teléfono habiendo notas pendientes: el bot pide el folio y lista las pendientes.
- Los borradores duran **6 horas** (`BORRADOR_TTL_SEG`) y viven **en memoria**: un deploy o reinicio en Railway los borra.
- `nota: cancelar 11111` borra el borrador de ese folio.

## Otros comandos del grupo relacionados

- `nota ayuda`: manda la guía completa con todos los campos opcionales.
- `menu`: incluye la sección "Nota de servicio en PDF" con las instrucciones y un ejemplo.
- `nota:` en el formato **viejo** posicional (`nota: 13054 5541576333 iPhone 13 pantalla 1200 tarjeta refaccion:500`) sigue funcionando: solo registra en el CRM, **sin PDF**. El bot decide el formato por la presencia de etiquetas.

## Envío al cliente

- Se envía como documento por Whapi (`POST /messages/document`, `media` en data URI base64) con el nombre `Nota_<folio>_TecnologySupport.pdf` y un texto corto (folio, equipo, total y, si hay anticipo, anticipo y saldo).
- Si el número del cliente está en **stop**, no se le envía; el grupo recibe la copia con el aviso.
- La copia al grupo siempre se manda e indica si el envío al cliente salió bien o falló.
- **Anti-duplicado:** el mismo (folio, teléfono, costo, anticipo) no se reenvía en 10 minutos.
- Se guarda en el historial del cliente una línea indicando que se envió la nota.

## CLABE y datos de pago

- La nota imprime la CLABE en el encabezado y en un recuadro destacado "Pago por transferencia" (CLABE, banco y titular).
- Los valores están en `agent/pdf_generator.py`: `CLABE_TS`, `BANCO_TS`, `TITULAR_TS`. **Si cambian, se editan ahí.**
- Antes de generar cualquier nota se valida el dígito verificador de la CLABE; si es inválido el PDF **no se genera**.
- El comando `clabe:` sigue leyendo la variable de entorno `CLABE_CUENTA` de Railway: **debe contener la misma CLABE** que `CLABE_TS`.

## Archivos del cambio

| Archivo | Cambio |
|---|---|
| `agent/nota_parser.py` | **Nuevo.** Parser, validación, borradores, textos de ayuda. Módulo puro (se prueba sin el bot) |
| `agent/commands.py` | Handler de `nota:` con etiquetas, `nota ayuda`, `nota: cancelar`, sección nueva en el menú |
| `agent/pdf_generator.py` | Render con Playwright/Chromium, casillas derivadas, CLABE y validación, `generar_pdf_async` |
| `agent/providers/whapi.py` | `enviar_documento_bytes()` |
| `templates/service_note.html` | Plantilla que replica la nota física |
| `templates/logo.png` | Logo (se incrusta en base64 al generar) |
| `Dockerfile` | `python -m playwright install --with-deps chromium` |
| `requirements.txt` | `playwright>=1.44.0` |

## Plantilla

- `templates/service_note.html` replica la nota física. Textos fijos (dirección, teléfonos, WhatsApp de atención, razón social, RFC, notas importantes, correo de facturación) están transcritos de la nota física: **se editan directamente en el HTML**.
- Los datos escritos por el usuario se escapan (`< > &`) antes de entrar al HTML. Los campos que no llegan quedan en blanco.
- Las casillas se dibujan con CSS (no dependen de fuentes del servidor).
- Se quitaron las líneas de firma del cliente y del técnico (un PDF por WhatsApp no se firma).
- Ajustar la altura de filas con cuidado: con textos largos la nota está al límite de **una página**. Verificar siempre que `pdfinfo` marque 1 página.

## Probar en local

```powershell
python -c "from agent.nota_parser import procesar_nota; print(procesar_nota('G', 'folio: 1 fecha: 12/10/26 cliente: Ana telefono: 5511223344 marca: LG modelo: K10 falla: no enciende costo: 500'))"
```

Para renderizar un PDF hace falta Playwright con Chromium (`pip install playwright` y `python -m playwright install chromium`).

## Pendientes y riesgos

- **Mensaje de respuestas rápidas de WhatsApp Business:** se quiere enviar al cliente, justo después del PDF, el texto de las respuestas rápidas actuales. **Falta el texto exacto** para implementarlo.
- **No probado en producción:** envío real por Whapi y build de Docker en Railway con Chromium (imagen más pesada; vigilar RAM en el plan Hobby al generar PDFs).
- **Confirmar la CLABE vigente:** la nota física impresa trae una CLABE distinta a la configurada en `CLABE_TS` (ambas pasan la validación del dígito verificador).
- Verificar que `CLABE_CUENTA` en Railway coincida con `CLABE_TS`.
- Los borradores no sobreviven a un reinicio. Si se vuelve un problema, moverlos a Postgres.
- El texto libre (falla, diagnóstico...) sale tal cual se escribe: errores de ortografía llegan al cliente.
