# ============================================================================
# Lyric Scroller - one-shot build (generate -> compile -> upload)
# ----------------------------------------------------------------------------
# Usage:
#   .\build.ps1                          # default lrc\fangxia.lrc, auto port
#   .\build.ps1 -Lrc "lrc\my.lrc"        # pick a lyric file
#   .\build.ps1 -Port COM6               # force a COM port
#   .\build.ps1 -NoUpload                # generate + compile only
# ============================================================================
param(
    [string]$Lrc = "lrc\fangxia.lrc",
    [string]$Port = "",
    [switch]$NoUpload
)

$ErrorActionPreference = "Stop"
$Root   = Split-Path -Parent $MyInvocation.MyCommand.Path
$Tools  = Join-Path $Root "tools"
$Sketch = Join-Path $Root "lyric_scroller"

# ---- locate Python ----
function Get-Python {
    if (Get-Command python -ErrorAction SilentlyContinue) { return "python" }
    $bundled = Get-ChildItem "$env:USERPROFILE\.dsh\dsh-runtimes\*\dependencies\python\python.exe" `
        -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($bundled) { return $bundled.FullName }
    throw "Python not found: install Python and add it to PATH"
}

# ---- locate arduino-cli ----
$Cli = $null
if (Get-Command arduino-cli -ErrorAction SilentlyContinue) { $Cli = "arduino-cli" }
else {
    foreach ($p in @(
        "D:\Program Files (x86)\ardiuno\Arduino IDE\resources\app\lib\backend\resources\arduino-cli.exe",
        "C:\Program Files\Arduino IDE\resources\app\lib\backend\resources\arduino-cli.exe",
        "C:\Program Files (x86)\Arduino IDE\resources\app\lib\backend\resources\arduino-cli.exe"
    )) { if (Test-Path $p) { $Cli = $p; break } }
}
if (-not $Cli) { throw "arduino-cli not found: install Arduino IDE or add arduino-cli to PATH" }

$Python = Get-Python
$LrcAbs = Join-Path $Root $Lrc

# ---- Arduino data dirs (override via env) ----
if (-not $env:ARDUINO_DIRECTORIES_DATA) { $env:ARDUINO_DIRECTORIES_DATA = "E:\Arduino IDE\ArduinoData" }
if (-not $env:ARDUINO_DIRECTORIES_USER) { $env:ARDUINO_DIRECTORIES_USER = "D:\Desktop\Arduino" }

# ---- port ----
if (-not $Port) {
    $ports = [System.IO.Ports.SerialPort]::GetPortNames()
    if (-not $ports) { throw "No serial port found: plug in the UNO USB cable" }
    $Port = $ports | Sort-Object { [int]([regex]::Match($_, '\d+').Value) } | Select-Object -Last 1
}

Write-Host "== Lyric Scroller build ==" -ForegroundColor Cyan
Write-Host "  Python      : $Python"
Write-Host "  arduino-cli : $Cli"
Write-Host "  LRC         : $Lrc"
Write-Host "  Port        : $Port"
Write-Host "  Data dir    : $env:ARDUINO_DIRECTORIES_DATA"

# ---- 0. ensure font present (auto-download, GNU Unifont) ----
$Font = Join-Path $Tools "unifont-18.0.01.hex.gz"
if (-not (Test-Path $Font)) {
    Write-Host ""
    Write-Host "[0/3] Downloading Unifont font ..." -ForegroundColor Yellow
    curl.exe -sSL --ssl-no-revoke -o $Font `
        "https://unifoundry.com/pub/unifont/unifont-18.0.01/font-builds/unifont-18.0.01.hex.gz"
    if (-not (Test-Path $Font) -or (Get-Item $Font).Length -lt 1000) {
        throw "font download failed"
    }
}

# ---- 1. generate data ----
Write-Host ""
Write-Host "[1/3] Generate lyric data (lrc2data.py) ..." -ForegroundColor Yellow
& $Python -B (Join-Path $Tools "lrc2data.py") $LrcAbs
if ($LASTEXITCODE -ne 0) { throw "lrc2data failed" }

# ---- 2. compile ----
Write-Host ""
Write-Host "[2/3] Compile ..." -ForegroundColor Yellow
$Build = Join-Path $env:TEMP "lyric_scroller_build"
Remove-Item $Build -Recurse -Force -ErrorAction SilentlyContinue
& $Cli compile --fqbn arduino:avr:uno --output-dir $Build $Sketch
if ($LASTEXITCODE -ne 0) { throw "compile failed" }

# ---- 3. upload ----
if ($NoUpload) {
    Write-Host ""
    Write-Host "Upload skipped (-NoUpload)" -ForegroundColor DarkYellow
} else {
    Write-Host ""
    Write-Host "[3/3] Upload to $Port ..." -ForegroundColor Yellow
    & $Cli upload -p $Port --fqbn arduino:avr:uno --input-dir $Build $Sketch
    if ($LASTEXITCODE -ne 0) { throw "upload failed: check port $Port (busy? board unplugged?)" }
}

Remove-Item $Build -Recurse -Force -ErrorAction SilentlyContinue
Write-Host ""
Write-Host "Done." -ForegroundColor Green
