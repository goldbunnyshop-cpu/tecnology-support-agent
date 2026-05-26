# 🔧 Setup: Meta Inbox (Messenger + Instagram DMs)

> Integra tu bot con **Facebook Messenger** e **Instagram Direct Messages** en una sola aplicación.

---

## 📋 Requisitos previos

- ✅ Cuenta de Facebook Business
- ✅ Página de Facebook (o crear una)
- ✅ Cuenta de Instagram de Negocios (linkedada a la página)
- ✅ Acceso como Admin en ambas

---

## 🚀 Paso 1: Crear o configurar App de Facebook

### 1.1 Ve a Facebook Developers
- Abre: https://developers.facebook.com/apps
- Click en **"Create App"** (si es la primera vez)
- Elige tipo: **Business**
- Nombre: `AgentKit Meta Inbox`
- Click **Create**

### 1.2 Agregar productos a la app
En el dashboard de tu app:
1. Click en **+ Add Product**
2. Busca **Messenger** → Click **Set Up**
3. Busca **Instagram Graph API** → Click **Set Up**
4. (Opcional) Busca **Webhooks** → Click **Set Up** (para testing local)

---

## 🔑 Paso 2: Obtener Access Token

### 2.1 Generar Token Permanente
En tu app → **Tools → Token Tool**:
1. Selecciona tu **Página de Facebook**
2. Copia el token (empieza con `EAA...`)
3. Este es tu `META_ACCESS_TOKEN`

**⚠️ Guárdalo en `.env` - NUNCA públicamente**

---

## 📱 Paso 3: Obtener IDs de Página e Instagram

### 3.1 Facebook Page ID
En tu app → **Settings → Basic**:
- Busca **App ID** y **App Secret**
- Ve a tu página: https://www.facebook.com/TU_PAGINA
- En la URL o click derecho → "View Page Info" → el ID numérico es tu **PAGE_ID**

### 3.2 Instagram Account ID
En tu app → **Instagram Graph API**:
1. Click en **Get Started**
2. Selecciona tu **Instagram Account** (linkedada a la página)
3. Copia el **Instagram Business Account ID**

---

## 🔌 Paso 4: Configurar Webhook

En tu app → **Messenger → Settings**:

1. **Callback URL**: `https://tu-railway-app.up.railway.app/webhook`
2. **Verify Token**: Inventa uno (ej: `mi-agente-2024`)
   - Guárdalo en `.env` como `META_VERIFY_TOKEN`
3. **Subscribe to Webhook Events**: Marca:
   - ✅ `messages`
   - ✅ `messaging_postbacks`
   - ✅ `messaging_optins`
4. Click **Verify and Save**

### Instagram DMs
En tu app → **Instagram Graph API → Webhooks**:
- Misma URL
- Mismo Verify Token
- Eventos: `messages`

---

## 🔐 Paso 5: Actualizar `.env`

```env
# Cambiar el proveedor
WHATSAPP_PROVIDER=meta_inbox

# Meta Inbox
META_ACCESS_TOKEN=EAA...  # Token permanente de tu página
META_VERIFY_TOKEN=mi-agente-2024  # El que inventaste en webhook
META_PAGE_IDS=123456789  # Tu Facebook Page ID
META_IG_ACCOUNT_IDS=987654321  # Tu Instagram Account ID

# Si quieres mantener ambos:
# WHATSAPP_PROVIDER=whapi  # Para WhatsApp
# O
# WHATSAPP_PROVIDER=meta_inbox  # Para Messenger + Instagram
```

---

## ✅ Paso 6: Testing

### Local (antes de deployar)
```bash
python tests/test_local.py
# Escribe mensajes como si fueras un cliente
```

### En Railway
```bash
# 1. Push a GitHub
git add -A
git commit -m "feat: meta inbox messenger + instagram"
git push origin main

# 2. Railway redeploy automático (5-10 min)

# 3. Prueba en Messenger
# Ve a tu página → Click en "Inbox" → escribe un test

# 4. Prueba en Instagram
# Abre tu Instagram Business → DMs → escribe un test
```

---

## 📊 Cómo funciona el bot multi-canal

Cuando habilitas `WHATSAPP_PROVIDER=meta_inbox`:

```
Cliente escribe en Messenger
    ↓
Webhook de Meta → /webhook
    ↓
ProveedorMetaInbox normaliza a MensajeEntrante (canal="messenger")
    ↓
Brain genera respuesta (sistema de dispositivos, asesor, etc.)
    ↓
ProveedorMetaInbox envía por Messenger (mismo ID del usuario)

---

Cliente escribe en Instagram DM
    ↓
Webhook de Meta → /webhook
    ↓
ProveedorMetaInbox normaliza a MensajeEntrante (canal="instagram")
    ↓
Brain genera respuesta
    ↓
ProveedorMetaInbox envía por Instagram (mismo ID del usuario)
```

**La BD es la misma** — el cliente `123456789` en Messenger es el mismo registro en Instagram si usa el mismo ID.

---

## 🔧 Troubleshooting

### "Callback URL doesn't match"
- Verifica que Meta está recibiendo el `challenge` en GET `/webhook`
- Asegúrate que `META_VERIFY_TOKEN` en `.env` coincide con el de Meta

### "Invalid Access Token"
- El token expiró → regenera uno en Meta
- Está revocado → pide nuevos permisos en Meta App Roles

### No llegan mensajes
- Verifica que tu app tiene permisos para Messenger e Instagram
- En Meta → **Settings → Roles** → asegúrate de tener permisos suficientes
- En Meta → **Messenger → Settings → Subscriptions** → verifica que `messages` está chequeado

### Mensaje no se envía
- El ID del usuario es incorrecto (Instagram vs Messenger usan IDs diferentes)
- Token sin permisos de envío → regenera token con permisos `pages_manage_metadata`

---

## 📞 URLs útiles

- **Facebook Developers**: https://developers.facebook.com/
- **Messenger Platform Docs**: https://developers.facebook.com/docs/messenger-platform
- **Instagram Graph API**: https://developers.facebook.com/docs/instagram-api
- **Tu página**: https://www.facebook.com/TU_PAGINA/inbox
- **Tu Instagram**: https://www.instagram.com/direct/

---

## ⚡ Pro Tips

1. **Mantén ambos canales**: Puedes cambiar `WHATSAPP_PROVIDER` en `.env` sin reescribir código
   ```env
   WHATSAPP_PROVIDER=whapi        # Hoy: WhatsApp
   WHATSAPP_PROVIDER=meta_inbox   # Mañana: Messenger + Instagram
   ```

2. **Rastrear canal en logs**: El bot logea `[META-INBOX] Messenger:` o `[META-INBOX] Instagram:` para ver de dónde vino

3. **Responder diferente por canal** (futuro): Podrías agregar lógica en `brain.py` para cambiar tono según `mensaje.canal`

4. **Webhook único**: Messenger e Instagram DMs usan el MISMO webhook en `/webhook` — Meta diferencia por tipo de evento

---

## ✨ Resumen

| Configuración | Valor |
|---|---|
| WHATSAPP_PROVIDER | `meta_inbox` |
| META_ACCESS_TOKEN | Tu token permanente (EAA...) |
| META_VERIFY_TOKEN | Lo que inventaste (ej: `mi-agente-2024`) |
| META_PAGE_IDS | Tu Facebook Page ID (123456789) |
| META_IG_ACCOUNT_IDS | Tu Instagram Account ID (987654321) |
| Webhook URL | `https://tu-app.up.railway.app/webhook` |
| Webhook Events | `messages` (ambos canales) |

**¡Listo! El bot ahora responde en Messenger e Instagram DMs.** 🚀

