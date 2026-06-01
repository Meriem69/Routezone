Write-Host "=== ARRET PROPRE ROUTEZONE ===" -ForegroundColor Cyan

Write-Host "`n[1/4] Arret Docker..." -ForegroundColor Yellow
docker-compose down

Write-Host "`n[2/4] Verification conteneurs restants..." -ForegroundColor Yellow
docker ps

Write-Host "`n[3/4] Verification ports 8000/8001/8501..." -ForegroundColor Yellow
$listening = netstat -ano | Select-String "LISTENING" | Select-String ":8000 |:8001 |:8501 "
if ($listening) {
    Write-Host "ATTENTION : processus zombies actifs sur ces ports :" -ForegroundColor Red
    Write-Host $listening
    Write-Host "Tape : taskkill /PID <numero> /F pour les tuer" -ForegroundColor Red
} else {
    Write-Host "Aucun processus zombie. TIME_WAIT et SYN_SENT sont normaux." -ForegroundColor Green
}

Write-Host "`n[4/4] Desactivation venv..." -ForegroundColor Yellow
deactivate 2>$null

Write-Host "`n=== ARRET TERMINE ===" -ForegroundColor Green
Write-Host "Tu peux fermer VS Code." -ForegroundColor Cyan
