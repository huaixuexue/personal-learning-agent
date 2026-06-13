$ErrorActionPreference = "Stop"

python -m pip install -r requirements-desktop.txt

pyinstaller `
  --noconfirm `
  --windowed `
  --onefile `
  --name "PersonalLearningAgent" `
  --icon "assets/app_icon.ico" `
  --add-data "assets;assets" `
  desktop_app.py

Write-Host ""
Write-Host "Build complete: dist\PersonalLearningAgent.exe"
Write-Host "Local data folder: $env:LOCALAPPDATA\PersonalLearningAgent\data\users"
