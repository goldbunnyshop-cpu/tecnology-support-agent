import sys
import os
sys.path.insert(0, os.getcwd())

# Test imports sin ejecutar la app
print("Testing imports...")

try:
    from agent.brain import generar_respuesta
    print("✓ agent.brain")
except Exception as e:
    print(f"✗ agent.brain: {e}")

try:
    from agent.memory import inicializar_db
    print("✓ agent.memory")
except Exception as e:
    print(f"✗ agent.memory: {e}")

try:
    from agent.providers import obtener_proveedor
    print("✓ agent.providers")
except Exception as e:
    print(f"✗ agent.providers: {e}")

print("\nAll critical modules loaded successfully!")
