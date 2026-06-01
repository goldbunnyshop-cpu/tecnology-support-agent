# importar_chats.py — Script de importación de chats existentes
# Uso: python importar_chats.py

import asyncio
import sys
import os

sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def barra_progreso(actual: int, total: int, info: str):
    pct = int(actual / total * 40)
    barra = "█" * pct + "░" * (40 - pct)
    print(f"\r  [{barra}] {actual}/{total}  {info[:35]:<35}", end="", flush=True)


async def main():
    print()
    print("=" * 60)
    print("   Tecnology Support — Importador de Chats WhatsApp")
    print("=" * 60)
    print()
    print("  Conectando con Whapi.cloud y analizando conversaciones...")
    print("  Claude clasificará cada chat en el funnel automáticamente.")
    print()

    from agent.import_chats import importar_todos_los_chats
    from agent.reports import generar_reporte_excel

    try:
        resumen = await importar_todos_los_chats(callback_progreso=barra_progreso)
        print()
        print()
        print("  ✓ Importación completada")
        print()
        print(f"  Total chats analizados : {resumen['total_chats']}")
        print(f"  Clientes importados    : {resumen['importados']}")
        print(f"  No eran clientes       : {resumen['omitidos_no_clientes']}")
        print(f"  Ya estaban en sistema  : {resumen['ya_en_sistema']}")
        print()

        if resumen["importados"] > 0:
            print("  Generando reporte Excel con los resultados...")
            ruta = await generar_reporte_excel()
            print(f"  ✓ Reporte guardado en: {ruta}")
            print()
            print("  Abre el archivo para ver tus leads clasificados por etapa.")
        else:
            print("  No se encontraron clientes nuevos para importar.")

    except Exception as e:
        print(f"\n  ERROR: {e}")
        print("  Verifica que WHAPI_TOKEN esté configurado en tu .env")

    print()
    print("=" * 60)
    print()


if __name__ == "__main__":
    asyncio.run(main())
