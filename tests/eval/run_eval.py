#!/usr/bin/env python3
# tests/eval/run_eval.py — Orquestador de evaluación de calidad del agente
# Generado por AgentKit — framework de evaluación

"""
Corre el set de pruebas contra el agente ACTUAL y produce un reporte
multidimensional, estratificado por complejidad.

Método (skill context-engineering:evaluation):
  1. Para cada caso: monta historial real, inyecta contexto de fecha si aplica,
     y llama generar_respuesta() — el MISMO punto de entrada que usa producción.
  2. Gate determinista (judge.evaluar_deterministico): si falla una regla
     aplicable, el caso REPRUEBA pase lo que pase el juez.
  3. Juez-LLM (Opus) para dimensiones subjetivas (solo casos conversacionales;
     los casos de motor de pricing se evalúan solo con reglas deterministas).
  4. Agrega: por dimensión, por estrato de complejidad, tasa de gate, score global.

Uso:
  python tests/eval/run_eval.py            # corre todo
  python tests/eval/run_eval.py --solo s01-saludo,m03-identidad-bot
Salida:
  - resumen ASCII en consola
  - reporte completo en tests/eval/reporte.json
"""

import asyncio
import sys
import os
import json
import argparse
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from dotenv import load_dotenv
load_dotenv()

# Consola Windows (cp1252) no codifica acentos/emojis del juez — forzar UTF-8 tolerante.
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from agent.brain import generar_respuesta, cargar_config_prompts
from agent.memory import inicializar_db
from tests.eval.dataset import DATASET, HECHOS_NEGOCIO
from tests.eval import judge

ZONA_CDMX = ZoneInfo("America/Mexico_City")
RUTA_REPORTE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "reporte.json")

_DIAS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
_MESES = {1: "enero", 2: "febrero", 3: "marzo", 4: "abril", 5: "mayo", 6: "junio",
          7: "julio", 8: "agosto", 9: "septiembre", 10: "octubre", 11: "noviembre", 12: "diciembre"}


def _ctx_fecha():
    """Replica el bloque de fecha/hora CDMX que main.py inyecta en producción."""
    hoy = datetime.now(ZONA_CDMX)
    man = hoy + timedelta(days=1)
    return (
        f"══ FECHA Y HORA ACTUAL — CDMX ══\n"
        f"Hoy: {_DIAS[hoy.weekday()]} {hoy.day} de {_MESES[hoy.month]} {hoy.year} · {hoy.strftime('%H:%M')}\n"
        f"Mañana: {_DIAS[man.weekday()]} {man.day} de {_MESES[man.month]}\n"
        f"NUNCA le preguntes al cliente qué día o fecha es — ya la tienes.\n"
        f"════════════════════════════════════════════════════"
    )


async def correr_caso(caso: dict, personalidades: dict) -> dict:
    contexto = _ctx_fecha() if caso.get("inyectar_fecha") else ""
    try:
        respuesta = await generar_respuesta(
            caso["mensaje"], caso["historial"], asesor=caso["asesor"], contexto_cliente=contexto
        )
    except Exception as e:
        respuesta = f"[ERROR AL GENERAR: {e}]"

    det = judge.evaluar_deterministico(respuesta, caso)

    dims = None
    score = None
    aprobado = det["paso"]
    # Solo casos conversacionales (ruta Claude) pasan por el juez subjetivo.
    if caso["ruta_esperada"] == "claude":
        personalidad = personalidades.get(caso["asesor"], "")
        dims = await judge.evaluar_con_juez(respuesta, caso, HECHOS_NEGOCIO, personalidad)
        score = judge.score_ponderado(dims)
        min_dim = min(dims[k] for k in judge.PESOS)
        aprobado = (
            det["paso"]
            and score >= judge.UMBRAL_APROBACION
            and min_dim >= judge.UMBRAL_MIN_DIMENSION
        )
    else:
        # pricing: aprueba si pasa el gate determinista
        score = 1.0 if det["paso"] else 0.0

    return {
        "id": caso["id"],
        "complejidad": caso["complejidad"],
        "caso_uso": caso["caso_uso"],
        "asesor": caso["asesor"],
        "ruta_esperada": caso["ruta_esperada"],
        "mensaje": caso["mensaje"],
        "respuesta": respuesta,
        "deterministico": det,
        "dimensiones": dims,
        "score": score,
        "aprobado": aprobado,
    }


def _media(xs):
    xs = [x for x in xs if x is not None]
    return round(sum(xs) / len(xs), 3) if xs else None


def agregar(resultados: list) -> dict:
    estratos = {}
    for r in resultados:
        estratos.setdefault(r["complejidad"], []).append(r)

    por_estrato = {}
    orden = ["simple", "medium", "complex", "very_complex"]
    for c in orden:
        if c not in estratos:
            continue
        grupo = estratos[c]
        por_estrato[c] = {
            "n": len(grupo),
            "aprobados": sum(1 for r in grupo if r["aprobado"]),
            "tasa_aprobacion": round(sum(1 for r in grupo if r["aprobado"]) / len(grupo), 3),
            "score_medio": _media([r["score"] for r in grupo]),
        }

    conversacionales = [r for r in resultados if r["dimensiones"]]
    por_dimension = {}
    for k in judge.PESOS:
        por_dimension[k] = _media([r["dimensiones"][k] for r in conversacionales])

    gate_total = sum(1 for r in resultados if r["deterministico"]["paso"])
    return {
        "n_total": len(resultados),
        "aprobados_total": sum(1 for r in resultados if r["aprobado"]),
        "tasa_aprobacion_global": round(sum(1 for r in resultados if r["aprobado"]) / len(resultados), 3),
        "gate_determinista_paso": gate_total,
        "gate_determinista_tasa": round(gate_total / len(resultados), 3),
        "score_medio_global": _media([r["score"] for r in resultados]),
        "por_estrato": por_estrato,
        "por_dimension": por_dimension,
    }


def imprimir_resumen(agg: dict, resultados: list):
    def p(s=""):
        print(s)

    p()
    p("=" * 64)
    p("   REPORTE DE EVALUACION — Tecnology Support (agente actual)")
    p("=" * 64)
    p(f"Casos: {agg['n_total']}  |  Aprobados: {agg['aprobados_total']}  "
      f"|  Tasa global: {agg['tasa_aprobacion_global']*100:.0f}%")
    p(f"Gate determinista: {agg['gate_determinista_paso']}/{agg['n_total']} "
      f"({agg['gate_determinista_tasa']*100:.0f}%)  |  Score medio: {agg['score_medio_global']}")

    p()
    p("-- Por dimension (juez-LLM, solo casos conversacionales) " + "-" * 8)
    for k, v in agg["por_dimension"].items():
        barra = "#" * int((v or 0) * 20)
        p(f"  {k:<20} {v if v is not None else 'n/a':<6} |{barra}")

    p()
    p("-- Por estrato de complejidad " + "-" * 33)
    for c, v in agg["por_estrato"].items():
        p(f"  {c:<14} n={v['n']:<3} aprob={v['aprobados']}/{v['n']:<3} "
          f"tasa={v['tasa_aprobacion']*100:.0f}%  score={v['score_medio']}")

    p()
    p("-- Casos REPROBADOS " + "-" * 44)
    reprobados = [r for r in resultados if not r["aprobado"]]
    if not reprobados:
        p("  (ninguno)")
    for r in reprobados:
        fallas = ", ".join(f"{f['regla']}({f['evidencia']})" for f in r["deterministico"]["fallas"])
        p(f"  [{r['id']}] {r['complejidad']}/{r['caso_uso']}  score={r['score']}")
        if fallas:
            p(f"      gate: {fallas}")
        if r["dimensiones"]:
            dims = r["dimensiones"]
            bajas = {k: dims[k] for k in judge.PESOS if dims[k] < judge.UMBRAL_MIN_DIMENSION}
            if bajas:
                p(f"      dims bajas: {bajas}")
            p(f"      juez: {dims['razonamiento']}")

    p()
    p("=" * 64)
    p(f"Reporte completo: {RUTA_REPORTE}")
    p("=" * 64)
    p()


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--solo", type=str, default="", help="ids separados por coma")
    args = parser.parse_args()

    await inicializar_db()

    config = cargar_config_prompts()
    asesores = config.get("asesores", {})
    personalidades = {k: v.get("personalidad", "") for k, v in asesores.items()}

    casos = DATASET
    if args.solo:
        ids = {x.strip() for x in args.solo.split(",")}
        casos = [c for c in DATASET if c["id"] in ids]

    print(f"\nCorriendo {len(casos)} casos contra el agente actual "
          f"(modelo agente: claude-sonnet-4-6 | juez: {judge.MODELO_JUEZ})...\n")

    resultados = []
    for i, caso in enumerate(casos, 1):
        print(f"  [{i}/{len(casos)}] {caso['id']} ...", flush=True)
        resultados.append(await correr_caso(caso, personalidades))

    agg = agregar(resultados)

    reporte = {
        "generado": datetime.now(ZONA_CDMX).isoformat(),
        "modelo_agente": "claude-sonnet-4-6",
        "modelo_juez": judge.MODELO_JUEZ,
        "pesos": judge.PESOS,
        "umbral_aprobacion": judge.UMBRAL_APROBACION,
        "umbral_min_dimension": judge.UMBRAL_MIN_DIMENSION,
        "agregado": agg,
        "resultados": resultados,
    }
    with open(RUTA_REPORTE, "w", encoding="utf-8") as f:
        json.dump(reporte, f, ensure_ascii=False, indent=2)

    imprimir_resumen(agg, resultados)


if __name__ == "__main__":
    asyncio.run(main())
