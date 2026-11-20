# Sediakan folder kerja untuk skill caption (word-behind-head).
# Semua dipasang DALAM folder ini sahaja: venv, model, fon.
# Guna:  powershell -ExecutionPolicy Bypass -File setup.ps1 -Dir "D:\Video\projek\caption"
param([string]$Dir = (Get-Location).Path)

$ErrorActionPreference = "Stop"
Set-Location $Dir

if (-not (Get-Command ffmpeg -ErrorAction SilentlyContinue)) {
    Write-Host "ffmpeg tiada. Pasang: winget install Gyan.FFmpeg"; exit 1
}

if (-not (Test-Path ".venv")) { python -m venv .venv }
$py = Join-Path $Dir ".venv\Scripts\python.exe"
& $py -m pip install --upgrade pip -q
& $py -m pip install -q faster-whisper "rembg[cpu]" pillow numpy

New-Item -ItemType Directory -Force fonts, models\rembg, models\hf, models\whisper | Out-Null
$fonts = @{
    "fonts\Anton-Regular.ttf"      = "https://github.com/google/fonts/raw/main/ofl/anton/Anton-Regular.ttf"
    "fonts\Inter-Variable.ttf"     ="https://github.com/google/fonts/raw/main/ofl/inter/Inter%5Bopsz,wght%5D.ttf"
}
foreach ($k in $fonts.Keys) {
    if (-not (Test-Path -LiteralPath $k)) { Invoke-WebRequest $fonts[$k] -OutFile $k }
}
Write-Host "Siap. Python: $py"
Write-Host "Model (cut-out ~1 GB, whisper ~0.5 GB) dimuat turun kali pertama skrip dijalankan."
