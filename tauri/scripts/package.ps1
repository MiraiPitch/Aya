# PowerShell script to package the Aya Voice Assistant Tauri app with Python

# Create a virtual environment for the Python package
Write-Host "Creating Python virtual environment..." -ForegroundColor Green
python -m venv .venv

# Activate the virtual environment
Write-Host "Activating virtual environment..." -ForegroundColor Green
& .\.venv\Scripts\Activate.ps1

# Install the Aya package and its dependencies
Write-Host "Installing Aya package and dependencies..." -ForegroundColor Green
pip install -e ..\python
pip install pyinstaller websockets

# Create a standalone Python executable
Write-Host "Creating standalone Python executable..." -ForegroundColor Green
pyinstaller --onefile ..\python\src\aya\tauri_bridge.py --name aya_bridge --hidden-import=websockets

# Copy the executable to the Tauri resources directory
Write-Host "Copying executable to Tauri resources..." -ForegroundColor Green
New-Item -ItemType Directory -Force -Path .\src-tauri\resources
Copy-Item .\dist\aya_bridge.exe .\src-tauri\resources\

# Update Tauri config to use the bundled executable
Write-Host "Updating Tauri configuration..." -ForegroundColor Green
$tauriConfig = Get-Content .\src-tauri\tauri.conf.json | ConvertFrom-Json
$tauriConfig.tauri.bundle.externalBin = @("resources/aya_bridge.exe")
$tauriConfig | ConvertTo-Json -Depth 10 | Set-Content .\src-tauri\tauri.conf.json

# Build the Tauri application
Write-Host "Building Tauri application..." -ForegroundColor Green
npm run build
npm run tauri build

Write-Host "Packaging complete!" -ForegroundColor Green
Write-Host "The packaged application can be found in: .\src-tauri\target\release\bundle" -ForegroundColor Cyan 