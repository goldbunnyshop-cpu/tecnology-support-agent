# Sesión del 4 de noviembre de 2026 (madrugada)

Resumen de lo que se arregló hoy en el bot de WhatsApp de Tecnology Support.
Todo está subido a `main` en GitHub (commits `a5b4ee8` → `5bfa5f5`). Railway lo desplegó solo.
Pruebas: **74 pasando**. Las 9 de `test_pricing_sheets.py` ya fallaban antes y quedan excluidas.

> En la laptop, antes de editar algo: `git pull`

---

## 1. Pantallas de iPhone: solo la lista manual (`a5b4ee8`)

**Problema:** los logs de producción mostraban que no salía la lista manual de precios.
- "Iphone 15 pro **máx**": por el acento no encontraba el modelo y mandaba al técnico.
- "iPhone XS", "XR", "SE": el detector solo aceptaba modelos con número, así que caían a la IA sin precio.
- "Iphone 12 pro, cambio de…": tomaba "12 pro cambio" como el modelo.
- Hugo Shop todavía podía cotizar iPhone si la lista no se leía o si el cliente no decía la marca.
- En producción había quedado la versión sin explicación breve para XR, 11, SE y 8.

**Solución:**
- **Hugo Shop bloqueado para iPhone** en `_resolver_match_hugo`, `obtener_cotizacion_display` y la búsqueda sin marca. La única fuente es `knowledge/precios_iphone.csv`. Si el modelo no está en la lista o la lista no se lee, se manda al técnico. Nunca se inventa precio.
- **Nuevo detector de modelo** (`pricing._clave_consulta_iphone` / `modelo_iphone_de_texto`), que usa `brain._extraer_marca_modelo` cuando la marca es iPhone. Entiende:
  - "15 pro máx", "15pro max", "XS", "XS Max", "XR", "SE 2022", "8+", "16 e", "iphone 10" (= X), "tengo 2 iphone 11".
  - "SE" solo: pregunta si es SE 2020 o SE 2022.
  - "se me cayó" ya no se confunde con el SE.
- Regresó la explicación breve en los modelos LCD: genérica "colores menos vivos", original "como la de fábrica".

## 2. Confirmaciones de cita repetidas en el grupo interno (`c7294cc`)

**Problema:** caso Raúl, PS4. Claude volvió a mandar `[[AGENDAR]]` un minuto después de confirmar. Eso creó un segundo evento en Google Calendar con otro número de evento, y otro aviso al grupo. Con un mensaje más del cliente salía el tercero.

**Solución:**
- Antes de agendar, `cita_detector.existe_cita_cercana()` revisa si ese cliente ya tiene cita en un rango de ±2 horas. Si la tiene, no crea otro evento ni avisa otra vez.
- `notificar_nueva_cita` también evita duplicados por **teléfono + día + hora**, aunque el número de evento sea distinto.
- Prueba: `tests/test_cita_duplicada.py`.
- **Pendiente manual:** borrar en Google Calendar los eventos duplicados que ya existían (ej. Raúl, jueves 5 nov 10:30, tiene 2).

## 3. Seguimientos que respetan el plazo del cliente (`2908011`)

**Problema:** el calendario de seguimientos era fijo (2 h, 24 h, 72 h, 7 días). Si el cliente decía "el viernes les confirmo", el bot le escribía 2 horas después.

**Solución:**
- **`agent/espera_cliente.py`** detecta cuando el cliente pospone ("confirmo", "aviso", "paso", "lo llevo", "cuando me paguen"…) y el plazo que da:

  | El cliente dice (ejemplo: miércoles) | El bot vuelve a escribir |
  |---|---|
  | "el viernes les confirmo" | viernes 12:00 |
  | "el viernes en la tarde te aviso" | viernes 17:00 |
  | "mañana te digo" | jueves 12:00 |
  | "en 2 horas te confirmo" | 2 h 15 min después |
  | "la próxima semana paso" | lunes 12:00 |
  | "en dos semanas te escribo" | +14 días |
  | "el 20 de noviembre paso" | 20 nov 12:00 |
  | "cuando me paguen la quincena" | día siguiente a la quincena |
  | "a fin de mes lo llevo" | último día del mes |
  | "el mes que entra lo llevo" | día 2 del mes siguiente |
  | "lo platico y les aviso" (sin fecha) | 2 días después |

- **Tabla `leads`:** columnas nuevas `seguimiento_pausado_hasta` y `espera_texto`. Se crean solas al arrancar. No sale ningún seguimiento antes de esa fecha, y el día acordado sale ese mismo día.
- **Mensaje de seguimiento:** usa el contexto "como quedamos, te escribo hoy…".
- **Prompt:** cuando el cliente da un plazo, el bot lo acepta corto ("Perfecto, le escribo el viernes 😊") y no insiste.
- Si el cliente vuelve a escribir con una consulta nueva, se cancela la espera. Un "ok" o "gracias" no la cancela.
- Un "el lunes" sin una palabra como "confirmo" o "paso" no pausa nada, porque podría estar pidiendo cita.
- Prueba: `tests/test_espera_cliente.py`.

## 4. Venta e instalación de mejoras: memoria, SSD, RAM (`2688bea`, `86795a3`, `5bfa5f5`)

**Problema:** un cliente que cotizaba mantenimiento de PS5 pidió ampliar la memoria. El bot dijo que solo reparábamos y lo mandó a comprar a Mercado Libre o Amazon.

**Solución:**
- **Prompt, sección "Venta e instalación de mejoras":**
  - Sí vendemos e instalamos SSD M.2 para PS5, SSD para PS4, Xbox, laptop y PC, RAM y accesorios.
  - **Nunca** mandar al cliente a otra tienda.
  - Pregunta qué capacidad busca (1 TB o 2 TB).
  - **Precio:** no da cifra. Dice que el precio de la pieza es variable porque depende del tipo de cambio y que **en instantes le cotizamos**.
  - **Enfoque en confirmar la cita:** en el mismo mensaje pide día y hora. Si ya cotizaba otro servicio (ej. mantenimiento PS5 $1,400), ofrece hacer los dos en la misma visita y agenda aunque el precio de la pieza siga pendiente.
- **Fuera de horario (madrugada):** no promete "en instantes". Dice que el equipo técnico le manda la cotización cuando retoma: L–V desde 10:30 y S–D desde 11:30.
  - Hay doble protección: la regla en el prompt y `horario.ajustar_promesas`, que corrige el texto antes de enviarlo.
- **Aviso al grupo interno** (`agent/venta_upgrade.py`, `main._avisar_upgrade`):
  ```
  🛒 VENTA: AMPLIACIÓN / MEJORA
  📞 5215512345678 — wa.me/5215512345678
  📱 Equipo: PS5
  💬 Pidió: "y si le ponen un ssd de 2tb?"
  🔧 También cotiza: Mantenimiento (no perder este servicio)
  👨‍💼 Asesor: Sofia
  ➡️ Cotizar pieza + instalación (al tipo de cambio de hoy) y mandarle el precio YA…
  ```
  - Si llega fuera de horario, el aviso lo marca con 🌙.
  - Llega un solo aviso por cliente al día.
  - El bot **no se pausa**: sigue atendiendo.
- Prueba: `tests/test_venta_upgrade.py`.

---

## Costos al cierre (4 nov, 3:30 a.m.)

### Claude (API)
| Dato | Valor |
|---|---|
| Saldo | **USD 2.99**: alcanza para unos 2 días. **Recargar.** |
| Últimos 30 días | USD 42.53 (promedio USD 1.42 al día) |
| 1 nov / 2 nov / 3 nov | USD 3.06 / 1.67 / 1.75 |

- El prompt compacto lleva 1 día en producción. Para medir si bajó el gasto hay que comparar una semana completa.
- Lo que se agregó hoy no gasta tokens extra, porque es código propio.

### Railway (ciclo 20 oct – 20 nov)
| Dato | Valor |
|---|---|
| Uso | USD 2.92 de USD 5.00 incluidos (estimado de Railway: USD 5.03) |
| RAM | USD 2.85 (97% del total) |
| helpful-prosperity (bot) | USD 2.16 |
| lavish-alignment | USD 0.76: **borrar o pausar** |

- WAHA cuesta unos USD 0.22 al día. Deja de sumar cuando se regrese a Whapi y WAHA quede en 0 réplicas. Los pasos están en `MIGRAR_A_WHAPI.md`.

---

## Pendientes
1. **Recargar créditos de Claude.** Es urgente: el saldo dura unos 2 días.
2. Borrar o pausar el proyecto **lavish-alignment** en Railway.
3. Borrar en Google Calendar los eventos de cita duplicados que ya existían.
4. Pagar Whapi y seguir `MIGRAR_A_WHAPI.md`. Al terminar, poner WAHA en 0 réplicas.
5. Revisar en tu lista `knowledge/precios_iphone.csv`:
   - el iPhone 13 está más barato que el 12;
   - el premium del 16 Plus está más barato que el del 16.
6. Si aparecen frases de "le confirmo después" que el bot no entienda, agregarlas a `agent/espera_cliente.py`.

Más detalle técnico: `BITACORA_SEP_NOV_2026.md`.
