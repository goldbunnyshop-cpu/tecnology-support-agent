import asyncio
import sys
sys.path.insert(0, '.')
from agent.memory import limpiar_todas_pausas

async def main():
    count = await limpiar_todas_pausas()
    print(f'✅ Pausas limpiadas: {count}')

asyncio.run(main())
