# Reporte de cambios — Evaluación de calidad y fix del router de pricing

**Fecha y hora:** 2026-05-31, 15:09 (CDMX)
**Autor:** Christian + Claude Code
**Commit:** `2547c3d` — *fix: router de pricing solo intercepta consultas de display reales*
**Estado del deploy:** ✅ Pusheado a `main` → Railway redeployando a producción.

---

## 1. Qué se hizo

Se evaluó la **calidad actual** del agente de WhatsApp (Tecnology Support) con un framework
de evaluación nuevo, se detectó un bug sistémico de enrutamiento y se corrigió.

### 1.1 Framework de evaluación (nuevo) — `tests/eval/`
| Archivo | Qué hace |
|---|---|
| `dataset.py` | 52 casos de prueba estratificados por complejidad (simple/medium/complex/very_complex) |
| `judge.py` | Validación determinista (reglas del contrato) + juez-LLM con `claude-opus-4-8` |
| `run_eval.py` | Orquestador → genera `tests/eval/reporte.json` |

**Cómo correrlo:**
```bash
python tests/eval/run_eval.py            # corre los 52 casos
python tests/eval/run_eval.py --solo id1,id2   # corre casos específicos
```

### 1.2 Fix del router de pricing — `agent/brain.py`
El motor de cotización de pantallas se disparaba ante **cualquier** marca+modelo o palabra de
precio, desviando consultas que **no son de display** y respondiendo con el guion de cotización
de pantalla fuera de lugar.

**Casos que estaban fallando:**
| Cliente preguntaba | Respondía (mal) |
|---|---|
| "precio del **mantenimiento** de Switch" ($500) | guion de cotización de display |
| "¿el **diagnóstico** tiene costo?" ($200) | guion de cotización de display |
| "cambiar la **batería** de iPhone 12" | pedía variante de display |
| "cambio de **centro de carga**" | pedía variante de display |

**Corrección aplicada en `_intentar_respuesta_pricing_contextual`:**
- `_PATRON_NO_DISPLAY` → mantenimiento, diagnóstico, batería, centro de carga, consola, control,
  software, etc. ahora los atiende **Claude** (precio fijo de consola, invitar al módulo, Situación 5).
- `_PATRON_DISPLAY` → solo dispara con términos inequívocos de pantalla (`display`, `pantalla`,
  `mica`, `cristal`, `gorilla`). Se excluyeron `touch`/`táctil` porque generaban falsos positivos
  en quejas conversacionales (ej: "el touch muerto").

---

## 2. Resultados (antes → después)

| Métrica | Pre-fix | **Post-fix** |
|---|---|---|
| Tasa de aprobación (52 casos) | 77 % | **90 %** |
| Score medio ponderado | 0.82 | **0.91** |
| Correctitud factual | 0.82 | **0.94** |
| Cumple el caso de uso | 0.75 | **0.85** |
| Casos reprobados | 12 | **5** |

**Por complejidad (post-fix):** simple 100 % · medium 88 % · complex 92 % · very_complex 80 %.

> Nota: el primer baseline con solo 18 casos daba 89 % (inflado). El set real de 52 casos
> reveló el problema sistémico y dio la señal correcta.

---

## 3. Pendientes (NO son del router — son ajustes de prompt)

Quedaron documentados; el framework ya permite medir antes/después de tocarlos:

1. **Situación 5 para modelos viejos/consola** (`v04`) — Claude aplica el guion genérico de
   celulares en vez del protocolo de captura de datos de contacto.
2. **Rigidez del "pide nombre primero"** (`m11`) — atropella preguntas directas del cliente
   (ej: "¿cómo llego en metro?" → responde pidiendo el nombre).
3. **Presión de cierre tras 2 intentos** (`v02`) — el modelo no cuenta los intentos previos del
   historial y vuelve a insistir.
4. **Fuga del bloque interno** (`c12`) — el agente filtró `══ DISPONIBILIDAD REAL ══` al cliente.
   Ya lo detecta el gate determinista (`no_filtra_disponibilidad`).

---

## 4. Archivos tocados en este commit

```
agent/brain.py          (fix del router)
tests/eval/dataset.py   (nuevo)
tests/eval/judge.py     (nuevo)
tests/eval/run_eval.py  (nuevo)
tests/eval/__init__.py  (nuevo)
tests/eval/.gitignore   (nuevo)
```

*Generado el 2026-05-31 15:09 (CDMX).*
