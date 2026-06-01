#!/usr/bin/env python3
"""Script para agregar la función buscar_modelo_sin_marca al archivo pricing.py"""

nueva_funcion = '''

async def buscar_modelo_sin_marca(modelo: str) -> str:
    """Busqueda por modelo sin marca explícita."""
    if not modelo or len(modelo.strip()) < 2:
        return _mensaje_no_disponible("No especificado", "modelo desconocido")

    productos = cargar_csv_hugo()
    if not productos:
        logger.warning("[PRICING] CSV vacio en busqueda sin marca")
        return _mensaje_no_disponible("No especificado", modelo)

    modelo_lower = modelo.lower().strip()
    for marca_alias in ALIAS_MARCAS:
        modelo_lower = re.sub(rf'\\b{re.escape(marca_alias)}\\b', '', modelo_lower).strip()

    if not modelo_lower:
        return _mensaje_no_disponible("No especificado", modelo)

    tokens = modelo_lower.split()
    matches_por_marca = defaultdict(list)

    for p in productos:
        marca = p.get('MARCA', '')
        if not marca:
            continue
        pares = normalizar_modelo_descripcion(p['DESCRIPCION'], marca)
        for base, variante in pares:
            if not base:
                continue
            base_lower = base.lower()
            if tokens and tokens[0] == base_lower:
                matches_por_marca[marca].append((p, [variante]))
                break

    if not matches_por_marca:
        logger.warning(f"[PRICING] Sin productos para '{modelo}' sin marca")
        return _mensaje_no_disponible("No especificado", modelo)

    if len(matches_por_marca) == 1:
        marca = list(matches_por_marca.keys())[0]
        productos_encontrados = [p for p, _ in matches_por_marca[marca]]
        logger.info(f"[PRICING] Busqueda sin marca: '{modelo}' -> {marca}")
        return _formatear_cotizacion(marca, modelo, productos_encontrados)

    marcas_str = ", ".join(sorted(matches_por_marca.keys()))
    cuerpo = (
        f"Encontre displays para {modelo.upper()} en: {marcas_str}. "
        f"De cual marca es tu dispositivo?"
    )
    return f"INFORMACION PARA EL CLIENTE:\\n\\n{cuerpo}"

'''

# Leer el archivo original
with open('agent/pricing.py', 'r', encoding='utf-8') as f:
    contenido = f.read()

# Encontrar el lugar donde insertar (antes de "async def inicializar_cotizador")
marker = "async def inicializar_cotizador():"
if marker not in contenido:
    print(f"ERROR: Marker no encontrado: {marker}")
    exit(1)

# Insertar la nueva función
indice = contenido.find(marker)
contenido_nuevo = contenido[:indice] + nueva_funcion + "\n" + contenido[indice:]

# Escribir el archivo
with open('agent/pricing.py', 'w', encoding='utf-8') as f:
    f.write(contenido_nuevo)

print("✓ Función agregada exitosamente")
print(f"Total líneas: {len(contenido_nuevo.splitlines())}")
