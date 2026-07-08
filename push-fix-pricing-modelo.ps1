# push-fix-pricing-modelo.ps1
# Sube SOLO el fix de extraccion de marca/modelo en agent/brain.py
# (corrige "Qjiero cotizar oppor reno 13" -> modelo quedaba como toda la frase
#  en vez de "reno 13"; mismo bug afectaba a Redmi Note 13 y similares)

Set-Location $PSScriptRoot

if (Test-Path ".git\index.lock") {
    Write-Host "Eliminando .git\index.lock residual..." -ForegroundColor Yellow
    Remove-Item ".git\index.lock" -Force
}

git status agent/brain.py

git add agent/brain.py

git commit -m "fix: extraccion de marca/modelo en pricing tolera typos y frases largas

- _extraer_marca_modelo ahora compara por TOKENS en vez de regex con
  limite de palabra (\b). Antes 'oppor' (typo de 'oppo') no calzaba con
  \boppo\b, y el modelo quedaba como la frase completa
  ('qjiero cotizar oppor reno 13') en vez de 'reno 13'.
- Se agrega tolerancia a typos de marca: token que EMPIEZA con el alias
  y tiene como maximo 2 caracteres extra (oppor~oppo, iphonee~iphone),
  solo para alias de 4+ letras (evita falsos positivos con lg/tcl/zte).
- _normalizar_consulta_pricing ahora tambien quita prefijos como
  'quiero/qiero/qjiero/quisiera/necesito/deseo cotizar/precio de un...'
  (antes solo 'me ayudas a cotizar'), asi 'qjiero cotizar' no contamina
  el modelo.
- Corrige tambien el caso pendiente de Redmi Note 13 (mismo bug)."

git push origin main

Write-Host ""
Write-Host "Listo. Prueba en WhatsApp con:" -ForegroundColor Green
Write-Host '  "Qjiero cotizar oppor reno 13" -> deberia buscar OPPO reno 13' -ForegroundColor Green
Write-Host '  "precio redmi note 13"        -> deberia buscar XIAOMI note 13' -ForegroundColor Green
