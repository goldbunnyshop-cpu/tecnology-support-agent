# Script para importar citas sin emojis (PowerShell compatible)
$url = "https://tecnology-support-agent-production.up.railway.app/api/calendar/importar-de-texto"

$citas = @(
    "NUEVA CITA AGENDADA
Jose Luis Gil Miranda | PS5
Sabado 9 de mayo, 11:30 a.m. | Sobrecalentamiento, se apaga sola
Asesor: Sofia",

    "NUEVA CITA AGENDADA
Andres | PS5
Sabado 16 de mayo, 11:00 a.m. | Consola se apaga despues de 30 minutos jugando
Asesor: Valentina",

    "NUEVA CITA AGENDADA
Emmanuel | PS5
Sabado 9 de mayo, 12:00 p.m. | Puerto HDMI con falso contacto
Asesor: Camila",

    "NUEVA CITA AGENDADA
Francisco Gonzalez | PS3
Jueves 14 de mayo, 7:30 p.m. | Charola no jala los discos, consola desarmada
Asesor: Sofia",

    "NUEVA CITA AGENDADA
Gonz | Xbox Series S
Sabado 9 de mayo, 12:30 p.m. | Mantenimiento por sobrecalentamiento
Asesor: Sofia",

    "NUEVA CITA AGENDADA
Augusto | PS4
Sabado 9 de mayo, 5:30 p.m. | Mantenimiento
Asesor: Valentina",

    "NUEVA CITA AGENDADA
Raul Del Prado Flores | Xbox Series X
Sabado 16 de mayo, 11:30 a.m. | Mantenimiento
Asesor: Valentina",

    "NUEVA CITA AGENDADA
Jose Antonio | PS5 con lector de discos
Sabado 16 de mayo, 1:30 p.m. | Bandeja de discos danada, soportes rotos
Asesor: Valentina",

    "NUEVA CITA AGENDADA
Pablo | PS5
Sabado 16 de mayo, 11:30 a.m. | Se calienta y se apaga sola
Asesor: Sofia",

    "NUEVA CITA AGENDADA
Eric Soto Rodriguez | Xbox 360 (x2) + Moto Z
Jueves 14 de mayo, 11:00 a.m. | Xbox 360 con falla de 4 anillos, Moto Z cambio de pantalla
Asesor: Sofia",

    "NUEVA CITA AGENDADA
Israel | Nintendo Switch
Sabado 16 de mayo, 11:30 a.m. | Drift en palancas y botones sin respuesta
Asesor: Sofia",

    "NUEVA CITA AGENDADA
Jose Juan Campos Medina | PS4 Fat, PS3 Fat, Xbox 360
Domingo 17 de mayo, 12:00 p.m. | Mantenimiento - limpieza profunda y cambio de pasta termica
Asesor: Camila",

    "NUEVA CITA AGENDADA
Carlos Tengo | iPhone 14
Sabado 16 de mayo, 2:00 p.m. | Centro de carga danado
Asesor: Sofia",

    "NUEVA CITA AGENDADA
Jaime Escamilla | Xbox Series X Digital
Miercoles 13 de mayo, 10:30 a.m. | Puerto Ethernet con falso positivo
Asesor: Camila",

    "NUEVA CITA AGENDADA
Irving Sanchez | Xbox One
Viernes 15 de mayo, 5:00 p.m. | No enciende, no se ve el LED de power
Asesor: Sofia",

    "NUEVA CITA AGENDADA
David | PS5
Sabado 16 de mayo, 2:45 p.m. | Se calienta mucho, ya fue limpiada pero persiste
Asesor: Valentina",

    "NUEVA CITA AGENDADA
Diego Gutierrez | Sony PS Vita PCH-1000
Sabado 16 de mayo, 12:00 p.m. | Fallo en joystick analogico y gatillo
Asesor: Daniela"
)

Write-Host "================================" -ForegroundColor Cyan
Write-Host "  IMPORTADOR DE CITAS" -ForegroundColor Cyan
Write-Host "================================" -ForegroundColor Cyan
Write-Host "Total de citas a importar: $($citas.Count)" -ForegroundColor Yellow
Write-Host ""

$body = @{mensajes = $citas} | ConvertTo-Json -Depth 10

Write-Host "Enviando citas al servidor..." -ForegroundColor Cyan

try {
    $response = Invoke-WebRequest -Uri $url -Method POST `
        -Headers @{"Content-Type"="application/json"} `
        -Body $body `
        -UseBasicParsing

    $result = $response.Content | ConvertFrom-Json

    Write-Host ""
    Write-Host "RESULTADO:" -ForegroundColor Green
    Write-Host "================================" -ForegroundColor Green
    Write-Host "Importadas: $($result.importadas)" -ForegroundColor Green
    Write-Host "Ya existentes: $($result.ya_existentes)" -ForegroundColor Yellow
    Write-Host "Errores: $($result.errores)" -ForegroundColor Red
    Write-Host "Total procesadas: $($result.total_encontradas)" -ForegroundColor Cyan
    Write-Host "================================" -ForegroundColor Green

    if ($result.errores -gt 0) {
        Write-Host ""
        Write-Host "Detalles de errores:" -ForegroundColor Red
        $result.detalles | Where-Object {$_.estado -eq "error"} | ForEach-Object {
            Write-Host "  ERROR #$($_.numero): $($_.razon)" -ForegroundColor Red
        }
    }

} catch {
    Write-Host "ERROR en la solicitud:" -ForegroundColor Red
    Write-Host $_.Exception.Message -ForegroundColor Red
}

Write-Host ""
Write-Host "Proceso completado." -ForegroundColor Gray
