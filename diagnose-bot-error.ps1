# diagnose-bot-error.ps1
# Diagnostica el error de ModuleNotFoundError: No module named 'bot'

Write-Host "=====================================================" -ForegroundColor Cyan
Write-Host "  Diagnostico: ModuleNotFoundError 'bot'" -ForegroundColor Cyan
Write-Host "=====================================================" -ForegroundColor Cyan
Write-Host ""

# 1. Buscar cualquier import de 'bot'
Write-Host "[1] Buscando imports de 'bot'..." -ForegroundColor Yellow
$imports = Select-String -Path "agent\*.py" -Pattern "from bot|import bot" -ErrorAction SilentlyContinue
if ($imports) {
    Write-Host "  ENCONTRADO:" -ForegroundColor Red
    $imports | ForEach-Object { Write-Host "    $_" }
} else {
    Write-Host "  No encontrado (OK)" -ForegroundColor Green
}
Write-Host ""

# 2. Verificar estructura de directorios
Write-Host "[2] Estructura de directorios:" -ForegroundColor Yellow
Get-ChildItem -Path "agent" -Directory | ForEach-Object { Write-Host "    📁 $($_.Name)" }
Write-Host ""

# 3. Verificar __init__.py
Write-Host "[3] Verificando __init__.py:" -ForegroundColor Yellow
if (Test-Path "agent\__init__.py") {
    $content = Get-Content "agent\__init__.py"
    if ($content) {
        Write-Host "    Contenido:" -ForegroundColor Cyan
        $content | ForEach-Object { Write-Host "      $_" }
    } else {
        Write-Host "    Vacío (OK)" -ForegroundColor Green
    }
} else {
    Write-Host "    NO EXISTE - crear ahora" -ForegroundColor Red
    "" | Out-File -FilePath "agent\__init__.py" -Encoding utf8
    Write-Host "    ✓ Creado" -ForegroundColor Green
}
Write-Host ""

# 4. Test local de import
Write-Host "[4] Probando import local:" -ForegroundColor Yellow
$pythonTest = @"
import sys
sys.path.insert(0, '.')
try:
    from agent.main import app
    print('✓ Import exitoso: agent.main.app')
except ModuleNotFoundError as e:
    print(f'✗ Error: {e}')
except Exception as e:
    print(f'✗ Otro error: {e}')
"@

$pythonTest | python -c "import sys; sys.stdin = sys.stdin" -InputObject $_  2>&1

Write-Host ""
Write-Host "[5] Recomendaciones:" -ForegroundColor Cyan
Write-Host "  • Si el test paso: El problema esta en Railway (PYTHONPATH)"
Write-Host "  • Si fallo: El archivo tiene un import circular o invalido"
Write-Host ""
Write-Host "Cuando hagas push a Railway, usa:" -ForegroundColor Magenta
Write-Host "  git push origin main -f"
Write-Host ""
