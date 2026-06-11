# BIST-Scanner Build Script
# Builds a single Windows executable using PyInstaller

$ErrorActionPreference = "Stop"

Write-Host "=== BIST-Scanner Build ===" -ForegroundColor Cyan

# Ensure PyInstaller is installed
Write-Host "`n[1/3] Checking PyInstaller..." -ForegroundColor Yellow
try {
    $ver = python -m PyInstaller --version 2>$null
    Write-Host "  PyInstaller $ver found." -ForegroundColor Green
} catch {
    Write-Host "  Installing PyInstaller..." -ForegroundColor Yellow
    pip install pyinstaller
}

# Clean previous build
Write-Host "`n[2/3] Cleaning previous build artifacts..." -ForegroundColor Yellow
if (Test-Path "build") { Remove-Item -Recurse -Force "build" }
if (Test-Path "dist") { Remove-Item -Recurse -Force "dist" }

# Build
Write-Host "`n[3/3] Building executable..." -ForegroundColor Yellow
python -m PyInstaller bist-scanner.spec --noconfirm

if ($LASTEXITCODE -eq 0) {
    $exePath = "dist\BIST-Scanner.exe"
    if (Test-Path $exePath) {
        $size = (Get-Item $exePath).Length / 1MB
        Write-Host "`nBuild successful!" -ForegroundColor Green
        Write-Host "  Output: $exePath" -ForegroundColor Cyan
        Write-Host "  Size:   $([math]::Round($size, 1)) MB" -ForegroundColor Cyan
        Write-Host "`nTo run: double-click BIST-Scanner.exe" -ForegroundColor White
        Write-Host "  (bist.db will be created in the same folder on first run)" -ForegroundColor DarkGray
    }
} else {
    Write-Host "`nBuild failed. Check the output above for errors." -ForegroundColor Red
    exit 1
}
