# tests/eval/judge.py — Validación determinista + juez-LLM
# Generado por AgentKit — framework de evaluación de calidad del agente

"""
Dos capas de evaluación, en orden:

1) GATE DETERMINISTA (regex/conteo) — comprueba el contrato de comportamiento
   que NO admite interpretación: idioma mexicano, no revelar bot, decir "módulo",
   no negar fines de semana, no filtrar mensajes internos, precios correctos, etc.
   Si una regla aplicable falla, el caso REPRUEBA aunque el juez lo califique alto
   (una respuesta inválida no se "lava" con una nota subjetiva favorable).

2) JUEZ-LLM (Opus, tier distinto al agente Sonnet) — califica dimensiones
   subjetivas 0.0–1.0: correctitud factual, cumplimiento del caso, tono/personalidad,
   naturalidad. Devuelve razonamiento + score estructurado por dimensión.
"""

import os
import re
import json
import logging
from anthropic import AsyncAnthropic

logger = logging.getLogger("agentkit.eval")
client = AsyncAnthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

MODELO_JUEZ = "claude-opus-4-8"  # distinto al agente (claude-sonnet-4-6)

# ════════════════════ CAPA 1 — REGLAS DETERMINISTAS ════════════════════
# Cada regla: (texto_respuesta) -> (paso: bool, evidencia: str)

_ARGENTINISMOS = re.compile(
    r"\b(vos|boludo|quilombo|tenés|querés|podés|vení|acordate|fijate|cómo andás|che)\b", re.I
)
_REVELA_BOT = re.compile(
    r"\b(openai|chatgpt|anthropic|claude|python|fastapi|machine learning|chatbot|"
    r"inteligencia artificial|modelo de lenguaje|soy un bot|soy una ia|soy una inteligencia)\b",
    re.I,
)
_TALLER = re.compile(r"\b(taller|tienda|sucursal|local)\b", re.I)
_NIEGA_FINDE = re.compile(
    r"(no\s+(trabajamos|abrimos|atendemos|laboramos)[^.\n]{0,30}"
    r"(s[áa]bado|domingo|fin(es)?\s+de\s+semana))"
    r"|(cerrad[oa]s?[^.\n]{0,20}(s[áa]bado|domingo|fin(es)?\s+de\s+semana))",
    re.I,
)
_FILTRA_SISTEMA = re.compile(
    r"(no tengo acceso|el sistema no (ha )?inyect|el contexto no incluye|"
    r"confírmame la fecha exacta|necesito que me confirmes la fecha|qué día es hoy|"
    r"qué fecha es hoy)",
    re.I,
)
_PIDE_NOMBRE = re.compile(
    r"(con qui[eé]n tengo el gusto|me (puede |podr[íi]a )?(decir|dar) su nombre|"
    r"¿c[oó]mo se llama|cu[áa]l es su nombre|me regala su nombre|me dice su nombre)",
    re.I,
)
_HACE_PREGUNTA = re.compile(r"\?")
_ENCABEZADO_INTERNO = re.compile(r"INFORMACION PARA EL CLIENTE", re.I)
_LINK_MAPS = re.compile(r"maps\.app\.goo\.gl", re.I)
# Precio MXN de refacción: $ seguido de número de 3-4 cifras (con coma opcional)
_PRECIO_MXN = re.compile(r"\$\s?\d{1,2}[.,]?\d{3}\b")


def _ok(ev=""):
    return (True, ev)


def _fail(ev):
    return (False, ev)


def regla_idioma_mexicano(t):
    m = _ARGENTINISMOS.search(t)
    return _fail(f"argentinismo: '{m.group(0)}'") if m else _ok()


def regla_no_revela_bot(t):
    m = _REVELA_BOT.search(t)
    return _fail(f"revela tecnología/bot: '{m.group(0)}'") if m else _ok()


def regla_no_taller(t):
    m = _TALLER.search(t)
    return _fail(f"usa palabra prohibida: '{m.group(0)}'") if m else _ok()


def regla_no_niega_finde(t):
    m = _NIEGA_FINDE.search(t)
    return _fail(f"niega fines de semana: '{m.group(0)}'") if m else _ok()


def regla_no_filtra_sistema(t):
    m = _FILTRA_SISTEMA.search(t)
    return _fail(f"filtra mensaje interno: '{m.group(0)}'") if m else _ok()


def regla_no_filtra_disponibilidad(t):
    # El agente NUNCA debe echar al cliente el bloque interno de contexto.
    m = re.search(r"══.*?══|DISPONIBILIDAD REAL|FECHA Y HORA ACTUAL|Slots disponibles", t, re.I)
    return _fail(f"filtra bloque interno: '{m.group(0)[:40]}'") if m else _ok()


def regla_no_pide_fecha_hoy(t):
    # subconjunto de filtra_sistema enfocado en preguntar la fecha
    m = re.search(r"(qué día es hoy|qué fecha es hoy|me confirma.{0,15}fecha)", t, re.I)
    return _fail(f"pregunta la fecha al cliente: '{m.group(0)}'") if m else _ok()


def regla_no_repite_pedir_nombre(t):
    m = _PIDE_NOMBRE.search(t)
    return _fail(f"vuelve a pedir el nombre: '{m.group(0)}'") if m else _ok()


def regla_hace_pregunta(t):
    return _ok() if _HACE_PREGUNTA.search(t) else _fail("no cierra con pregunta/CTA")


def regla_menciona_la_comer(t):
    return _ok() if re.search(r"la comer|fuentes brotantes|metrob", t, re.I) else _fail(
        "no menciona La Comer / Fuentes Brotantes"
    )


def regla_precio_ps5_correcto(t):
    return _ok() if re.search(r"1[.,]?300", t) else _fail("no da el precio correcto de PS5 ($1,300)")


def regla_respuesta_no_vacia(t):
    return _ok() if t and len(t.strip()) >= 10 else _fail("respuesta vacía o demasiado corta")


def regla_sin_encabezado_interno(t):
    m = _ENCABEZADO_INTERNO.search(t)
    return _fail("filtró encabezado interno de pricing") if m else _ok()


def regla_pide_resena(t):
    return _ok() if _LINK_MAPS.search(t) else _fail("no comparte el link de reseña/maps")


def regla_no_presiona_excesivo(t):
    # señal burda: más de 1 signo de exclamación de urgencia + "aparto/agendar/hoy mismo" repetido
    urgencia = len(re.findall(r"(se (llena|agota)|hoy mismo|últim|apúr|no se le agot)", t, re.I))
    return _fail("presión de cierre excesiva tras 2 intentos") if urgencia >= 2 else _ok()


REGLAS = {
    "idioma_mexicano": regla_idioma_mexicano,
    "no_revela_bot": regla_no_revela_bot,
    "no_taller": regla_no_taller,
    "no_niega_finde": regla_no_niega_finde,
    "no_filtra_sistema": regla_no_filtra_sistema,
    "no_filtra_disponibilidad": regla_no_filtra_disponibilidad,
    "no_pide_fecha_hoy": regla_no_pide_fecha_hoy,
    "no_repite_pedir_nombre": regla_no_repite_pedir_nombre,
    "hace_pregunta": regla_hace_pregunta,
    "menciona_la_comer": regla_menciona_la_comer,
    "precio_ps5_correcto": regla_precio_ps5_correcto,
    "respuesta_no_vacia": regla_respuesta_no_vacia,
    "sin_encabezado_interno": regla_sin_encabezado_interno,
    "pide_resena": regla_pide_resena,
    "no_presiona_excesivo": regla_no_presiona_excesivo,
}


def evaluar_deterministico(respuesta: str, caso: dict) -> dict:
    """Aplica las reglas deterministas declaradas en el caso + la regla global de
    'no exponer precio de refacción' cuando aplica."""
    resultados = []
    for nombre in caso.get("checks", []):
        fn = REGLAS.get(nombre)
        if not fn:
            resultados.append({"regla": nombre, "paso": False, "evidencia": "REGLA DESCONOCIDA"})
            continue
        paso, ev = fn(respuesta)
        resultados.append({"regla": nombre, "paso": paso, "evidencia": ev})

    # Regla global: precio de refacción/software prohibido para este caso
    if caso.get("precio_refaccion_prohibido"):
        m = _PRECIO_MXN.search(respuesta)
        # excepción: precio de consola/diagnóstico no aplica aquí porque estos casos
        # no son de consola; cualquier $###/$#,### se considera precio de refacción.
        paso = m is None
        resultados.append({
            "regla": "precio_refaccion_prohibido",
            "paso": paso,
            "evidencia": f"expuso precio: '{m.group(0)}'" if m else "",
        })

    paso_global = all(r["paso"] for r in resultados)
    fallas = [r for r in resultados if not r["paso"]]
    return {"paso": paso_global, "reglas": resultados, "fallas": fallas}


# ════════════════════ CAPA 2 — JUEZ-LLM ════════════════════

_PROMPT_JUEZ = """Eres un evaluador experto de calidad de un agente de atención a clientes por WhatsApp para un módulo de reparación de tecnología en México llamado "Tecnology Support".

Tu trabajo es calificar la RESPUESTA DEL AGENTE de forma estricta y objetiva. Evalúa el RESULTADO (¿es una buena respuesta para este cliente en este punto de la conversación?), NO si siguió pasos exactos — hay varias formas válidas de responder bien.

## Hechos de negocio (única fuente de verdad — todo lo demás es invención)
{hechos}

## Contexto de la conversación
Asesor (personalidad esperada): {asesor} — {personalidad}
Caso evaluado: {caso_uso} ({complejidad})
Qué debería lograr una respuesta excelente:
{criterio}

## Historial previo
{historial}

## Mensaje del cliente bajo prueba
{mensaje}

## Respuesta del agente (a evaluar)
{respuesta}

## Califica cada dimensión de 0.0 a 1.0
- correctitud: ¿Los datos son correctos según los hechos de negocio? ¿No inventa nada? (0 = inventa datos falsos / contradice hechos; 1 = todo correcto)
- cumple_caso: ¿La respuesta avanza el caso de uso y logra lo que debía lograr? (0 = ignora o falla el objetivo; 1 = lo cumple completamente)
- tono_personalidad: ¿Coincide con la personalidad del asesor y suena cálido/humano mexicano? (0 = robótico o tono equivocado; 1 = perfecto)
- naturalidad: ¿Suena a persona real, sin frases prohibidas ("estimado cliente", "en qué puedo asistirle"), arranque natural, longitud adecuada (3-4 líneas)? (0 = robótico/genérico; 1 = muy natural)

Devuelve SOLO un objeto JSON válido, sin texto adicional, con esta forma exacta:
{{"correctitud": 0.0, "cumple_caso": 0.0, "tono_personalidad": 0.0, "naturalidad": 0.0, "razonamiento": "1-2 frases explicando la nota más baja"}}"""


def _formatear_historial(historial):
    if not historial:
        return "(sin historial — primer mensaje)"
    lineas = []
    for m in historial:
        quien = "Cliente" if m["role"] == "user" else "Agente"
        lineas.append(f"{quien}: {m['content']}")
    return "\n".join(lineas)


async def evaluar_con_juez(respuesta: str, caso: dict, hechos: str, personalidad: str) -> dict:
    prompt = _PROMPT_JUEZ.format(
        hechos=hechos.strip(),
        asesor=caso["asesor"],
        personalidad=personalidad,
        caso_uso=caso["caso_uso"],
        complejidad=caso["complejidad"],
        criterio=caso["criterio"],
        historial=_formatear_historial(caso["historial"]),
        mensaje=caso["mensaje"],
        respuesta=respuesta,
    )
    try:
        r = await client.messages.create(
            model=MODELO_JUEZ,
            max_tokens=600,
            messages=[{"role": "user", "content": prompt}],
        )
        texto = r.content[0].text.strip()
        # extraer el primer bloque JSON
        inicio = texto.find("{")
        fin = texto.rfind("}")
        data = json.loads(texto[inicio:fin + 1])
        return {
            "correctitud": float(data.get("correctitud", 0)),
            "cumple_caso": float(data.get("cumple_caso", 0)),
            "tono_personalidad": float(data.get("tono_personalidad", 0)),
            "naturalidad": float(data.get("naturalidad", 0)),
            "razonamiento": data.get("razonamiento", ""),
        }
    except Exception as e:
        logger.error(f"[JUEZ] Error evaluando {caso['id']}: {e}")
        return {
            "correctitud": 0.0, "cumple_caso": 0.0, "tono_personalidad": 0.0,
            "naturalidad": 0.0, "razonamiento": f"ERROR DEL JUEZ: {e}",
        }


# Pesos por dimensión (ajustados al caso de uso: atención a clientes que vende citas)
PESOS = {
    "correctitud": 0.35,        # dar datos falsos rompe la confianza
    "cumple_caso": 0.30,        # debe avanzar la venta/soporte
    "tono_personalidad": 0.15,
    "naturalidad": 0.20,        # sonar humano es central a esta marca
}
UMBRAL_APROBACION = 0.70       # general; 0.90 sería alto riesgo
UMBRAL_MIN_DIMENSION = 0.50    # ninguna dimensión puede caer bajo esto


def score_ponderado(dims: dict) -> float:
    return round(sum(dims[k] * PESOS[k] for k in PESOS), 4)
