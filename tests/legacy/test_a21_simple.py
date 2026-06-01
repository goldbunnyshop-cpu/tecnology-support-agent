import sys
import importlib

sys.path.insert(0, '.')

# Limpiar cache
for m in list(sys.modules.keys()):
    if 'agent' in m:
        del sys.modules[m]

# Recargar
from agent import pricing
importlib.reload(pricing)
from agent.pricing import buscar_productos_en_csv

# Test
prods = buscar_productos_en_csv('samsung', 'a21')
print(f"Total: {len(prods)}")
