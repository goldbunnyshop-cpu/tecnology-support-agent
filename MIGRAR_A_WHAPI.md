# Regresar de WAHA a Whapi — guía desde el celular

> Todo se hace desde el navegador del celular: Whapi y Railway. No hace falta la laptop ni tocar código.
> El código ya soporta los dos proveedores; se cambia con **una variable**.

---

## Antes de empezar

| Dato | Valor |
|---|---|
| Proyecto Railway | `helpful-prosperity` → entorno `production` |
| Servicio del bot | `tecnology-support-agent` |
| Servicio WAHA | `waha` (`waha-production-d22d.up.railway.app`) |
| URL del webhook | `https://tecnology-support-agent-production.up.railway.app/webhook` |
| Variable que cambia | `WHATSAPP_PROVIDER` (`waha` → `whapi`) |
| Token de Whapi | `WHAPI_TOKEN` ya está guardado en el bot (no se borró) |

**Importante:** nunca dejes WAHA y Whapi conectados al mismo tiempo. Los dos mandan el mensaje al bot y el cliente recibe **respuestas dobles**.

**Problema del QR:** no puedes escanear un QR que se muestra en el mismo celular. Opciones:
- Abrir el panel de Whapi en otra pantalla (tablet, otro celular, una PC del local) y escanear con tu celular.
- O usar la opción **"Vincular con número de teléfono"** (código de 8 letras) si Whapi la muestra. En WhatsApp: Dispositivos vinculados → Vincular dispositivo → "Vincular con número de teléfono".

---

## Paso a paso (unos 10 minutos)

### 1. Pagar Whapi
panel.whapi.cloud → tu canal → pagar el plan. Confirma que el canal aparezca activo (aunque diga "desconectado").

### 2. Apagar WAHA en WhatsApp
En tu celular: **WhatsApp → ⋮ → Dispositivos vinculados** → toca el dispositivo de WAHA → **Cerrar sesión**.
Desde aquí el bot deja de contestar hasta el paso 4. Hazlo en un horario tranquilo.

### 3. Vincular Whapi
panel.whapi.cloud → tu canal → escanea el QR (o usa el código de vinculación). Espera a que diga **Connected / Authorized**.

Revisa en el canal → **Settings → Webhooks**:
- URL: `https://tecnology-support-agent-production.up.railway.app/webhook`
- Modo: `POST` (method/body)
- Eventos: `messages` (POST) activado. Si estaban también `chats` o `statuses`, déjalos como estaban antes.
- Guardar.

### 4. Cambiar el proveedor en Railway
railway.com → `helpful-prosperity` → servicio **tecnology-support-agent** → **Variables**:
- `WHATSAPP_PROVIDER` = `whapi`
- Comprueba que exista `WHAPI_TOKEN`. Si Whapi te dio un token nuevo, pégalo aquí.
- **No borres** `WAHA_URL`, `WAHA_API_KEY` ni `WAHA_SESSION`. No estorban y sirven si algún día hay que regresar a WAHA.

Railway muestra el botón **Deploy / Apply changes** → tócalo. Espera a que el despliegue diga **Active** (1–2 min).

### 5. Probar
Desde otro número escribe al WhatsApp del taller, por ejemplo: "precio display iphone 13".
- Debe contestar **una sola vez**.
- En Railway → bot → **Deployments → View logs** debes ver `Mensaje de ...` y la respuesta, sin errores `[WAHA]`.
- Manda también un mensaje al grupo interno y comprueba que le lleguen al grupo las alertas de citas.

### 6. Apagar WAHA en Railway (deja de cobrar RAM)
Hazlo solo cuando el paso 5 funcione.
Servicio **waha** → **Settings** → baja hasta el final → **Remove service from all regions** / pon **0 réplicas** (según lo que muestre Railway).
- Con 0 réplicas se conserva el volumen (`waha-volume`) por si quieres regresar. El volumen cobra muy poco (disco, no RAM).
- Si ya no lo vas a usar: **Delete service** borra también el volumen.

Ahorro: unos **$0.20 USD diarios** (WAHA usa unos 650 MB de RAM).

---

## Qué cambia al regresar a Whapi

| Tema | WAHA | Whapi |
|---|---|---|
| Atribución de anuncios (saber si el cliente viene de un anuncio Click-to-WhatsApp) | No llega | **Regresa** (`fuente = anuncio`) |
| Envío de fotos / PDF (`nota:`) | Limitado en WAHA Core | Funciona |
| Filtro de estados (`status@broadcast`) | Necesario, ya está | Whapi no los manda; el filtro queda en `waha.py`, sin efecto |
| Prefijo 521 en números de 10 dígitos | Lo arregla `waha.py` | Whapi lo completa solo |
| Costo | ~$6 USD/mes de RAM en Railway | 650 MXN/mes (≈ $35 USD) |

No hace falta cambiar código: `agent/providers/__init__.py` elige el proveedor según `WHATSAPP_PROVIDER`.

---

## Si algo sale mal

| Síntoma | Causa probable | Arreglo |
|---|---|---|
| El bot no contesta nada | Falta guardar el webhook en Whapi, o el despliegue no terminó | Revisa el paso 3 (URL exacta, con `/webhook`) y el paso 4 (Deploy en Active) |
| Logs `401` / `Unauthorized` de Whapi | Token viejo | Copia el token del canal en Whapi y pégalo en `WHAPI_TOKEN`; vuelve a desplegar |
| Contesta doble | WAHA sigue vinculado | Paso 2: cierra la sesión de WAHA en Dispositivos vinculados, y paso 6 |
| Quieres volver a WAHA de emergencia | — | `WHATSAPP_PROVIDER=waha`, enciende el servicio waha (1 réplica), entra a `https://waha-production-d22d.up.railway.app/dashboard` y escanea el QR de la sesión `default` |

---

## Contexto
- Fecha de esta guía: 3 nov 2026. Desde el 2 nov el bot corre en WAHA porque Whapi se suspendió por falta de pago.
- Detalle de la migración a WAHA y de todos los cambios: `BITACORA_SEP_NOV_2026.md`.
