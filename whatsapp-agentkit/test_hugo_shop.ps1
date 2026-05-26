# Test Hugo Shop - Script PowerShell (Sin emojis)
# Ejecutar en PowerShell: .\test_hugo_shop.ps1
# ESTRUCTURA: CÓDIGO | DESCRIPCIÓN | CALIDAD | COLOR | PRECIO_1 | PRECIO_2

Write-Host ""
Write-Host "====================================================================" -ForegroundColor Cyan
Write-Host "   TEST HUGO SHOP - Consulta de precios de displays" -ForegroundColor Cyan
Write-Host "====================================================================" -ForegroundColor Cyan
Write-Host ""

# Leer .env
$env_path = Join-Path (Get-Location) ".env"
if (-not (Test-Path $env_path)) {
    Write-Host "[ERROR] No se encontro .env" -ForegroundColor Red
    exit
}

Write-Host "[INFO] Leyendo .env..." -ForegroundColor Yellow
$env_content = Get-Content $env_path

# Extraer HUGO_SHOP_SHEET_ID
$sheet_id = $null
foreach ($line in $env_content) {
    if ($line -match "^HUGO_SHOP_SHEET_ID=(.+)$") {
        $sheet_id = $matches[1]
        break
    }
}

if (-not $sheet_id) {
    Write-Host "[ERROR] HUGO_SHOP_SHEET_ID no encontrado en .env" -ForegroundColor Red
    exit
}

Write-Host "[OK] Sheet ID encontrado: $($sheet_id.Substring(0, 20))..." -ForegroundColor Green
Write-Host ""

# Construir URL de descarga CSV
$csv_url = "https://docs.google.com/spreadsheets/d/$sheet_id/export?format=csv"
Write-Host "[INFO] Descargando datos desde Google Sheets..." -ForegroundColor Yellow

try {
    $response = Invoke-WebRequest -Uri $csv_url -TimeoutSec 10
    $csv_content = $response.Content
} catch {
    Write-Host "[ERROR] Error descargando hoja: $_" -ForegroundColor Red
    exit
}

Write-Host "[OK] Descarga completada" -ForegroundColor Green
Write-Host ""

# Parsear CSV
$lineas = $csv_content -split "`n"
Write-Host "ESTRUCTURA DE LA HOJA HUGO SHOP:" -ForegroundColor Cyan
Write-Host ""

# Mostrar primeras líneas (estructura)
Write-Host "Primeras 10 filas:" -ForegroundColor Yellow
$mostradas = 0
foreach ($linea in $lineas) {
    if ($mostradas -ge 10) { break }
    if ([string]::IsNullOrWhiteSpace($linea)) { continue }

    Write-Host "  $linea" -ForegroundColor Gray
    $mostradas++
}

Write-Host ""
Write-Host "====================================================================" -ForegroundColor Cyan
Write-Host "   PRUEBA DE BUSQUEDA" -ForegroundColor Cyan
Write-Host "====================================================================" -ForegroundColor Cyan
Write-Host ""

# Función para detectar multiplicador según calidad
# REGLA: UNICAMENTE AMOLED = x3, TODO lo demás = x4
function Get-Multiplicador ($calidad) {
    $calidad_lower = $calidad.ToLower()

    if ($calidad_lower -match "amoled") {
        return 3
    }
    else {
        return 4  # TODO lo demás (incluyendo OLED, ORIG, INCELL, etc.)
    }
}

# Casos de prueba (ajustar con modelos que existan en tu hoja)
$casos = @(
    @{ marca = "alcatel"; modelo = "5024" },
    @{ marca = "cubot"; modelo = "kingkong" },
    @{ marca = "samsung"; modelo = "s24" }
)

Write-Host "Buscando modelos en Hugo Shop..." -ForegroundColor Yellow
Write-Host "Nota: Ajusta los nombres de marca/modelo según los que aparecen en la hoja" -ForegroundColor Yellow
Write-Host ""

$marca_actual = ""

foreach ($caso in $casos) {
    $marca = $caso.marca.ToLower()
    $modelo = $caso.modelo.ToLower()
    $encontrado = $false

    Write-Host "[BUSCA] $($caso.marca.ToUpper()) $($caso.modelo)" -ForegroundColor Cyan

    foreach ($linea in $lineas) {
        if ([string]::IsNullOrWhiteSpace($linea)) { continue }

        # Parsear línea CSV (manejar comillas)
        $partes = @()
        foreach ($part in ($linea -split ',')) {
            $partes += $part.Trim().Trim('"')
        }

        if ($partes.Count -lt 2) { continue }

        $col_a = $partes[0].Trim().ToLower()
        $col_b = if ($partes.Count -gt 1) { $partes[1].Trim().ToLower() } else { "" }
        $col_c = if ($partes.Count -gt 2) { $partes[2].Trim().ToLower() } else { "" }
        $col_d = if ($partes.Count -gt 3) { $partes[3].Trim() } else { "" }
        $col_e = if ($partes.Count -gt 4) { $partes[4].Trim() } else { "" }

        # Detectar si es encabezado de marca (A tiene valor, B está vacío)
        if ($col_a -and -not $col_b) {
            $marca_actual = $col_a
            continue
        }

        # Saltar si B está vacío
        if (-not $col_b) { continue }

        # Buscar coincidencia: marca actual + modelo en B
        if ($marca_actual -eq $marca -and $col_b -match [regex]::Escape($modelo)) {
            try {
                $precio_str = $col_e -replace '\$|,', ''
                $precio_base = [float]$precio_str
                $multiplicador = Get-Multiplicador $col_c
                $precio_final = [int]($precio_base * $multiplicador)

                Write-Host "   [OK] Encontrado: $col_b" -ForegroundColor Green
                Write-Host "        Calidad: $col_c | Color: $col_d" -ForegroundColor Green
                Write-Host "        Precio Base: `$$precio_base × $multiplicador = `$$precio_final MXN" -ForegroundColor Green
                Write-Host ""

                $encontrado = $true
                break
            } catch {
                # Continuar si hay error
            }
        }
    }

    if (-not $encontrado) {
        Write-Host "   [NO ENCONTRADO] $($caso.marca) $($caso.modelo) no está en el catálogo" -ForegroundColor Yellow
        Write-Host ""
    }
}

Write-Host "====================================================================" -ForegroundColor Cyan
Write-Host "   TEST COMPLETADO" -ForegroundColor Cyan
Write-Host "====================================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "[NOTA] Si ves precios calculados, Hugo Shop esta funcionando." -ForegroundColor Green
Write-Host "[NOTA] Si ves 'NO ENCONTRADO', revisa el nombre exacto en la hoja." -ForegroundColor Yellow
Write-Host ""
