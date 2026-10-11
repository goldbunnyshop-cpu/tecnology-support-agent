# agent/nota_parser.py — Comando "nota:" con etiquetas → datos para la nota de servicio en PDF
#
# Ejemplo:
#   nota: folio: 11111 fecha: 12/10/26 cliente: Ricardo Alvarez telefono: 4455445544
#         marca: Samsung modelo: S23 Ultra falla: cambio de bateria costo: 2000
#
# Reglas
#   - Cada dato lleva su etiqueta con dos puntos; el orden no importa.
#   - Obligatorios: folio, fecha, cliente, telefono, marca, modelo, costo y falla (o diagnostico).
#   - La FECHA nunca se pone sola: si no viene, la nota no se genera.
#   - Si algo falta o está mal, se GUARDA lo que sí llegó (borrador) y el bot avisa qué falta.
#     Se responde solo con lo que falta, repitiendo el folio (o el teléfono) para identificar la nota.
#   - Etiqueta mal escrita (ej. "diagnosico:") => aviso con sugerencia; nunca se mezcla con otro campo.
#   - Módulo puro (sin dependencias del bot) para poder probarlo solo.

import re
import time
import difflib
from datetime import datetime

_TRANS = str.maketrans("áéíóúüñÁÉÍÓÚÜÑ", "aeiouunAEIOUUN")  # misma longitud => mismas posiciones


def _plano(s) -> str:
    return (s or "").translate(_TRANS).lower()


# etiqueta canónica -> alias aceptados (sin acentos, minúsculas)
_ALIAS = {
    "folio":           ("folio",),
    "fecha":           ("fecha",),
    "cliente":         ("cliente", "nombre"),
    "telefono":        ("telefono", "tel", "celular"),
    "domicilio":       ("domicilio", "direccion"),
    "tipo":            ("tipo", "equipo"),
    "marca":           ("marca",),
    "modelo":          ("modelo",),
    "imei":            ("imei", "serie"),
    "hora":            ("hora",),
    "entrega":         ("entrega",),
    "estimado":        ("estimado",),
    "tiempo":          ("tiempo",),
    "falla":           ("falla",),
    "diagnostico":     ("diagnostico",),
    "caracteristicas": ("caracteristicas", "caracteristica"),
    "riesgos":         ("riesgos", "riesgo"),
    "danos":           ("danos", "dano"),
    "chip":            ("chip", "sim"),
    "funda":           ("funda",),
    "accesorios":      ("accesorios", "accesorio"),
    "autorizo":        ("autorizo", "autorizacion"),
    "calidad":         ("calidad",),
    "estado":          ("estado",),
    "costo":           ("costo", "total"),
    "anticipo":        ("anticipo",),
    "pago":            ("pago",),
    "refaccion":       ("refaccion",),  # costo de la refacción (ganancia en CRM); no sale en el PDF
}
_A2C = {alias: canon for canon, als in _ALIAS.items() for alias in als}
_RE_PALABRA = re.compile(r"(?<![a-z0-9])([a-z]{3,})\s*:(?!//)")  # cualquier "palabra:" (no URLs)

REQUERIDOS = ("folio", "fecha", "cliente", "telefono", "marca", "modelo", "costo")  # + falla o diagnostico
_ETIQ_FALTA = {
    "folio": "folio:", "fecha": "fecha: (DD/MM/AA)", "cliente": "cliente:", "telefono": "telefono: (10 dígitos)",
    "marca": "marca:", "modelo": "modelo:", "costo": "costo: (solo número)", "falla": "falla: (o diagnostico:)",
}
_ORDEN_MOSTRAR = ("folio", "fecha", "cliente", "telefono", "tipo", "marca", "modelo", "imei", "falla", "diagnostico",
                  "costo", "anticipo", "pago")

BORRADOR_TTL_SEG = 6 * 3600

AYUDA_NOTA_CORTA = (
    "*Cómo generar una nota de servicio (PDF):*\n"
    "Escribe en el grupo: nota: y cada dato con su etiqueta y dos puntos (el orden no importa).\n"
    "*Obligatorios:* folio, fecha, cliente, telefono, marca, modelo, costo y falla (o diagnostico)\n"
    "   _Ej: nota: folio: 11111 fecha: 12/10/26 cliente: Ricardo Alvarez telefono: 4455445544 "
    "marca: Samsung modelo: S23 Ultra falla: cambio de bateria costo: 2000_\n"
    "El bot crea el PDF con el folio de la nota física y lo envía al cliente + copia aquí.\n"
    "La fecha NUNCA se pone sola: escríbela tú (hoy, ayer o mañana).\n"
    "Si falta o falla un dato, el bot guarda lo demás y avisa qué falta: responde SOLO con eso "
    "(con el folio). Ej: nota: folio: 11111 fecha: 12/10/26"
)

AYUDA_NOTA_COMPLETA = (
    AYUDA_NOTA_CORTA + "\n\n"
    "*Campos opcionales* (los mismos de la nota física):\n"
    "tipo: (Laptop, Celular...) · imei: (o serie:) · domicilio: · hora: (hora de entrada) · "
    "entrega: (fecha y hora de entrega) · tiempo: (para diagnosticar) · estimado: mismo dia | sujeto · "
    "diagnostico: · caracteristicas: · riesgos: · "
    "danos: roto, abollado, carcaza, estrellado (o ninguno) · chip: · funda: · accesorios: · "
    "autorizo: firma | whatsapp · calidad: premium | original | generica · estado: prendido | apagado · "
    "anticipo: (el saldo se calcula solo) · pago: efectivo | tarjeta | transferencia · refaccion: (costo, solo CRM)\n\n"
    "*danos:* solo se marcan SÍ las piezas que escribas; con 'danos: ninguno' todas salen en NO.\n"
    "*pago:* si lo pones, la orden también se registra en el CRM.\n"
    "*nota: cancelar 11111* → borra un borrador incompleto (los borradores se guardan 6 horas)."
)


def es_nota_etiquetada(payload: str) -> bool:
    """True si el mensaje usa etiquetas (formato nuevo). 'refaccion:' solo no cuenta: existe en el formato viejo."""
    return any(m.group(1) != "refaccion" for m in _RE_PALABRA.finditer(_plano(payload)))


def fmt_dinero(n: float) -> str:
    return f"{n:,.0f}" if float(n).is_integer() else f"{n:,.2f}"


def _num(txt) -> float | None:
    limpio = re.sub(r"(?i)\b(mxn|pesos)\b|[\s$,]", "", txt or "")
    return float(limpio) if re.fullmatch(r"\d+(\.\d+)?", limpio) else None


def _si_no(v: str) -> str:
    p = _plano(v).strip()
    return "SÍ" if p == "si" else "NO" if p == "no" else v.strip()


def _nombre(n: str) -> str:
    """'ricardo alvarez' -> 'Ricardo Alvarez' (solo si vino todo en minúsculas o todo en mayúsculas)."""
    return n.title() if n and (n.islower() or n.isupper()) else n


def _marca(m: str) -> str:
    """'samsung' -> 'Samsung' ('DELL' o 'iPhone' se respetan)."""
    return m[:1].upper() + m[1:] if m and m.islower() else m


# ═════════════════════════════════════════════════════════════════════════════
# 1) Extraer campos del mensaje
# ═════════════════════════════════════════════════════════════════════════════

def extraer_campos(payload: str):
    """
    Retorna (campos, desconocidos, sueltos, repetidas)
      campos:       {canon: valor_crudo}
      desconocidos: [(palabra, valor)]   etiquetas que no existen (typos)
      sueltos:      [texto]              texto sin etiqueta al inicio que no es folio/teléfono
      repetidas:    {canon}              etiquetas escritas dos veces con valores distintos
    """
    texto = payload or ""
    plano = _plano(texto)
    toks = list(_RE_PALABRA.finditer(plano))
    campos: dict[str, str] = {}
    desconocidos: list[tuple[str, str]] = []
    sueltos: list[str] = []
    repetidas: set[str] = set()

    for i, m in enumerate(toks):
        fin = toks[i + 1].start() if i + 1 < len(toks) else len(texto)
        valor = texto[m.end():fin].strip()
        canon = _A2C.get(m.group(1))
        if canon is None:
            desconocidos.append((m.group(1), valor))
            continue
        if canon in campos and campos[canon] != valor:
            repetidas.add(canon)
        campos[canon] = valor

    # Dato suelto antes de la primera etiqueta: folio (si ya hay telefono:) o teléfono (10+ dígitos)
    lead = texto[: toks[0].start()].strip() if toks else texto.strip()
    if lead:
        digitos = re.sub(r"\D", "", lead)
        if not digitos or re.search(r"[^\d\s\-().+]", lead):
            sueltos.append(lead[:30])
        elif "telefono" not in campos and len(digitos) >= 10:
            campos["telefono"] = digitos
        elif "folio" not in campos:
            campos["folio"] = digitos
        else:
            sueltos.append(lead[:30])
    return campos, desconocidos, sueltos, repetidas


# ═════════════════════════════════════════════════════════════════════════════
# 2) Validar
# ═════════════════════════════════════════════════════════════════════════════

def validar(v: dict):
    """
    Retorna (datos | None, faltan, corregir, validos)
      faltan:   [canon]                  obligatorios que no llegaron
      corregir: [(canon, motivo)]        llegaron pero están mal (se descartan del borrador)
      validos:  {canon: valor_crudo}     lo que sí está bien (se guarda en el borrador)
    """
    corregir: list[tuple[str, str]] = []
    invalidos: set[str] = set()

    def malo(canon, motivo):
        corregir.append((canon, motivo))
        invalidos.add(canon)

    extra: dict = {}

    tel = re.sub(r"\D", "", v.get("telefono", ""))
    if "telefono" in v and len(tel) < 10:
        malo("telefono", "debe tener 10 dígitos")

    folio = re.sub(r"[^\w-]", "", v.get("folio", ""))
    if "folio" in v and not folio:
        malo("folio", "no es válido")

    total = _num(v.get("costo"))
    if "costo" in v and total is None:
        malo("costo", "solo número, ej. 2000")

    anticipo = 0.0
    if v.get("anticipo"):
        a = _num(v["anticipo"])
        if a is None:
            malo("anticipo", "solo número")
        elif total is not None and a > total:
            malo("anticipo", "es mayor que el costo")
        else:
            anticipo = a
    ref = 0.0
    if v.get("refaccion"):
        r = _num(v["refaccion"])
        if r is None:
            malo("refaccion", "solo número")
        else:
            ref = r

    fecha_fmt = ""
    if "fecha" in v:
        for fmt in ("%d/%m/%y", "%d/%m/%Y", "%d-%m-%y", "%d-%m-%Y"):
            try:
                fecha_fmt = datetime.strptime(v["fecha"].strip(), fmt).strftime("%d/%m/%Y")
                break
            except ValueError:
                continue
        if not fecha_fmt:
            malo("fecha", f"'{v['fecha'][:15]}' no es válida, usa DD/MM/AA")

    if "estimado" in v:
        e = _plano(v["estimado"])
        if "mismo" in e:
            extra["checked_mismo_dia"] = True
        elif "sujeto" in e or "diag" in e:
            extra["checked_sujeto_diag"] = True
        else:
            malo("estimado", "usa 'mismo dia' o 'sujeto'")

    if "autorizo" in v:
        a = _plano(v["autorizo"])
        firma, wa = "firma" in a, any(x in a for x in ("whats", "wasap", "wa"))
        if firma:
            extra["checked_aut_firma"] = True
        if wa:
            extra["checked_aut_whatsapp"] = True
        if not (firma or wa):
            malo("autorizo", "usa 'firma', 'whatsapp' o ambos")

    if "calidad" in v:
        c = _plano(v["calidad"])
        if "premium" in c:
            extra["calidad"] = "premium"
        elif c.startswith("original"):
            extra["calidad"] = "original"
        elif c.startswith(("generic", "econom")):
            extra["calidad"] = "generica"
        else:
            malo("calidad", "usa premium, original o generica")

    if "estado" in v:
        s = _plano(v["estado"])
        if s.startswith(("prend", "encend")):
            extra["estado"] = "prendido"
        elif s.startswith("apag"):
            extra["estado"] = "apagado"
        else:
            malo("estado", "usa prendido o apagado")

    forma_pago = ""
    if "pago" in v:
        fp = _plano(v["pago"]).strip()
        if fp.startswith("efect"):
            forma_pago = "efectivo"
        elif fp.startswith("tarj"):
            forma_pago = "tarjeta"
        elif fp.startswith("trans"):
            forma_pago = "transferencia"
        else:
            malo("pago", "usa efectivo, tarjeta o transferencia")

    if "danos" in v:
        piezas = ("roto", "abollado", "carcaza", "estrellado")
        toks = [t for t in re.split(r"[\s,;/]+", _plano(v["danos"])) if t and t not in ("y", "e", "doblada", "doblado")]
        malos = [t for t in toks if t not in piezas and t not in ("ninguno", "ninguna", "nada", "no", "sin")]
        if malos:
            malo("danos", f"'{malos[0]}' no es válido (roto, abollado, carcaza, estrellado o ninguno)")
        elif toks and all(t in ("ninguno", "ninguna", "nada", "no", "sin") for t in toks):
            for pz in piezas:
                extra[pz] = "NO"
        else:
            for t in toks:
                if t in piezas:
                    extra[t] = "SÍ"

    validos = {k: val for k, val in v.items() if k not in invalidos}

    faltan = [r for r in REQUERIDOS if r not in invalidos and not validos.get(r, "").strip()]
    if not (validos.get("falla", "").strip() or validos.get("diagnostico", "").strip()):
        if "falla" not in invalidos and "diagnostico" not in invalidos:
            faltan.append("falla")

    if faltan or corregir:
        return None, faltan, corregir, validos

    datos = {
        "phone":              tel,
        "folio":              folio,
        "fecha":              fecha_fmt,
        "cliente":            _nombre(v.get("cliente", "")),
        "domicilio":          v.get("domicilio", ""),
        "equipo_tipo":        v.get("tipo", ""),
        "marca":              _marca(v.get("marca", "")),
        "modelo":             v.get("modelo", ""),
        "imei":               v.get("imei", ""),
        "hora_entrada":       v.get("hora", ""),
        "fecha_entrega":      v.get("entrega", ""),
        "tiempo_diagnostico": v.get("tiempo", ""),
        "falla":              v.get("falla", ""),
        "diagnostico":        v.get("diagnostico", ""),
        "caracteristicas":    v.get("caracteristicas", ""),
        "riesgos":            v.get("riesgos", ""),
        "chip":               _si_no(v.get("chip", "")),
        "funda":              _si_no(v.get("funda", "")),
        "accesorios":         v.get("accesorios", ""),
        "forma_pago":         forma_pago,
        "total":              total,
        "anticipo":           anticipo,
        "refaccion":          ref,
    }
    datos.update(extra)
    return datos, [], [], validos


# ═════════════════════════════════════════════════════════════════════════════
# 3) Borradores: se guarda lo capturado y se pide solo lo que falta
# ═════════════════════════════════════════════════════════════════════════════
# Un borrador se identifica por (chat, folio) o, si aún no hay folio, por (chat, teléfono).
# Un mensaje solo se une a un borrador si trae el mismo folio/teléfono. Así los datos de una
# nota nunca se mezclan con los de otra.

_BORRADORES: dict[tuple, dict] = {}


def _limpiar(ahora: float):
    for k in [k for k, d in _BORRADORES.items() if ahora - d["t"] > BORRADOR_TTL_SEG]:
        _BORRADORES.pop(k, None)


def _tel10(campos: dict) -> str:
    return re.sub(r"\D", "", campos.get("telefono", ""))[-10:]


def _folio_norm(campos: dict) -> str:
    return re.sub(r"[^\w-]", "", campos.get("folio", ""))


def _clave(chat: str, campos: dict):
    f, t = _folio_norm(campos), _tel10(campos)
    if f:
        return (chat, "f:" + f)
    if len(t) == 10:
        return (chat, "t:" + t)
    return (chat, "sin")


def cancelar_borrador(chat: str, folio: str) -> bool:
    return _BORRADORES.pop((chat, "f:" + re.sub(r"[^\w-]", "", folio or "")), None) is not None


def borradores_pendientes(chat: str, ahora: float | None = None) -> list[str]:
    _limpiar(ahora if ahora is not None else time.time())
    return [k[1][2:] for k in _BORRADORES if k[0] == chat and k[1].startswith("f:")]


def _mensaje_incompleto(validos, faltan, corregir, desconocidos, sueltos, repetidas, guardado: bool) -> str:
    folio, tel = _folio_norm(validos), _tel10(validos)
    # Etiquetas mal escritas con sugerencia: lo que escribió Ulises ya cubre ese dato (solo falta corregir la etiqueta)
    sug_info = []
    for w, valor in desconocidos:
        sug = difflib.get_close_matches(w, list(_A2C), n=1, cutoff=0.6)
        sug_info.append((w, valor, _A2C[sug[0]] if sug else None))
    cubiertos = {c for _, _, c in sug_info if c}
    if cubiertos & {"falla", "diagnostico"}:
        cubiertos.add("falla")
    faltan = [k for k in faltan if k not in cubiertos]
    titulo = f"Nota #{folio}" if folio else (f"Nota del {tel}" if len(tel) == 10 else "Nota")
    lin = [f"⚠️ {titulo} incompleta" + (" — guardé lo que ya mandaste." if guardado else ".")]
    if guardado:
        ok = [k for k in _ORDEN_MOSTRAR if validos.get(k)]
        if ok:
            lin.append("✅ Guardado: " + ", ".join(ok))
    if faltan:
        lin.append("❌ Falta: " + ", ".join(_ETIQ_FALTA.get(k, k + ":") for k in faltan))
    for canon, motivo in corregir:
        lin.append(f"✏️ Corregir {canon}: {motivo}")
    for canon in sorted(repetidas):
        lin.append(f"✏️ '{canon}:' está escrita dos veces; envíala una sola vez")
    sugeridos = []
    for w, valor, canon in sug_info:
        if canon:
            lin.append(f"🔤 '{w}:' no existe, ¿quisiste decir '{canon}:'?")
            sugeridos.append(f"{canon}: {valor}".strip())
        else:
            lin.append(f"🔤 '{w}:' no es una etiqueta válida")
    for s_ in sueltos:
        lin.append(f"🔤 Texto sin etiqueta: '{s_}'")

    partes = []
    if folio:
        partes.append(f"folio: {folio}")
    elif len(tel) == 10:
        partes.append(f"telefono: {tel}")
    pendientes = list(faltan) + [c for c, _ in corregir] + sorted(repetidas)
    vistos = set()
    for k in pendientes:
        if k not in vistos:
            vistos.add(k)
            partes.append(f"{k}:")
    partes += sugeridos
    lin.append("")
    lin.append("Responde SOLO con lo que falta, por ejemplo:" if guardado else "Reenvía con lo que falta, por ejemplo:")
    lin.append("nota: " + " ".join(partes))
    if guardado:
        lin.append("(el borrador se guarda 6 horas)")
    return "\n".join(lin)


def procesar_nota(chat: str, payload: str, ahora: float | None = None) -> tuple[dict | None, str]:
    """
    Punto de entrada del comando 'nota:' con etiquetas.
    Retorna (datos, "")  si la nota está completa y válida, o (None, mensaje_para_el_grupo).
    """
    ahora = ahora if ahora is not None else time.time()
    _limpiar(ahora)
    nuevos, desconocidos, sueltos, repetidas = extraer_campos(payload)
    if not nuevos and not desconocidos:
        return None, "⚠️ No encontré ninguna etiqueta.\n\n" + AYUDA_NOTA_CORTA

    f, t = _folio_norm(nuevos), _tel10(nuevos)

    # Sin folio ni teléfono pero hay notas pendientes: pedir el folio (no adivinar a cuál pertenece)
    if not f and len(t) != 10:
        pend = [("#" + k[1][2:]) if k[1].startswith("f:") else ("tel " + k[1][2:])
                for k in _BORRADORES if k[0] == chat and k[1] != "sin"]
        if pend:
            return None, ("⚠️ No sé a qué nota pertenece. Notas pendientes: " + ", ".join(sorted(pend)) + "\n"
                          "Repite tu mensaje incluyendo el folio, ej:\nnota: folio: " + pend[0].lstrip("#")
                          + " " + " ".join(f"{k}: ..." for k in list(nuevos)[:3]) + "\n"
                          "(si es una nota nueva, escribe folio y telefono)")

    # ¿Hay un borrador al que pertenece este mensaje?
    base, usadas = {}, []
    candidatos = []
    if f:
        candidatos.append((chat, "f:" + f))
    if len(t) == 10:
        candidatos.append((chat, "t:" + t))
    for k in candidatos:
        if k in _BORRADORES:
            base.update(_BORRADORES[k]["campos"])
            usadas.append(k)
    # Borrador sin folio ni teléfono: solo se completa con un mensaje que traiga ÚNICAMENTE folio/teléfono
    k_sin = (chat, "sin")
    if k_sin in _BORRADORES and nuevos and set(nuevos) <= {"folio", "telefono"} and not base:
        base.update(_BORRADORES[k_sin]["campos"])
        usadas.append(k_sin)

    # Una etiqueta escrita dos veces se descarta (también del borrador): hay que reenviarla una sola vez
    combinado = {**base, **nuevos}
    for canon in repetidas:
        combinado.pop(canon, None)

    datos, faltan, corregir, validos = validar(combinado)

    if datos and not (desconocidos or sueltos or repetidas):
        for k in usadas:
            _BORRADORES.pop(k, None)
        return datos, ""

    # Incompleta: guardar lo que sí está bien
    for k in usadas:
        _BORRADORES.pop(k, None)
    guardado = bool(validos)
    if guardado:
        _BORRADORES[_clave(chat, validos)] = {"campos": validos, "t": ahora}
    return None, _mensaje_incompleto(validos, faltan, corregir, desconocidos, sueltos, repetidas, guardado)


def datos_para_pdf(datos: dict, cliente: str, telefono: str) -> dict:
    """Arma el diccionario que consume pdf_generator.generar_pdf()."""
    pdf = {k: val for k, val in datos.items() if k not in ("phone", "refaccion")}
    pdf["cliente"] = cliente
    pdf["telefono"] = telefono
    pdf["total"] = fmt_dinero(datos["total"])
    pdf["anticipo"] = fmt_dinero(datos["anticipo"])
    pdf["saldo"] = fmt_dinero(datos["total"] - datos["anticipo"])
    return pdf
