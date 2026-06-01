$token = "ghp_8lNPXquFqUFX8OX0"
$repo = "https://$token@github.com/goldbunnyshop-cpu/tecnology-support-agent.git"

Write-Host "Configurando git..." -ForegroundColor Cyan
git config user.email "goldbunnyshop@gmail.com"
git config user.name "Christian"

Write-Host "Agregando cambios..." -ForegroundColor Cyan
git add agent/main.py

Write-Host "Haciendo commit..." -ForegroundColor Cyan
git commit -m "fix: patrones de extracción sin emojis específicos para importar citas"

Write-Host "Haciendo push a main..." -ForegroundColor Cyan
git push $repo main

Write-Host "Listo!" -ForegroundColor Green
