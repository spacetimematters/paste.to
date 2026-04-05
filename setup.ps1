# paste.to - One-Click Setup
# Run this in PowerShell: right-click setup.ps1 -> Run with PowerShell
# Or: powershell -ExecutionPolicy Bypass -File setup.ps1

Write-Host ""
Write-Host "  paste.to - YouTube Downloader Setup" -ForegroundColor White
Write-Host "  ====================================" -ForegroundColor DarkGray
Write-Host ""

# Check if Python is installed
$python = $null
foreach ($cmd in @("python", "py", "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe")) {
    try {
        $ver = & $cmd --version 2>&1
        if ($ver -match "Python 3") {
            $python = $cmd
            Write-Host "  [OK] Python found: $ver" -ForegroundColor Green
            break
        }
    } catch {}
}

if (-not $python) {
    Write-Host "  [!] Python not found. Installing now..." -ForegroundColor Yellow
    Write-Host ""

    $installer = "$env:TEMP\python-installer.exe"
    $url = "https://www.python.org/ftp/python/3.12.4/python-3.12.4-amd64.exe"

    Write-Host "  Downloading Python 3.12..." -ForegroundColor Gray
    try {
        [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
        Invoke-WebRequest -Uri $url -OutFile $installer -UseBasicParsing
    } catch {
        Write-Host "  [ERROR] Download failed: $_" -ForegroundColor Red
        Write-Host "  Please install Python manually from https://python.org" -ForegroundColor Yellow
        Read-Host "  Press Enter to exit"
        exit 1
    }

    Write-Host "  Installing Python (this takes ~1 minute)..." -ForegroundColor Gray
    Start-Process -FilePath $installer -ArgumentList "/quiet", "InstallAllUsers=0", "PrependPath=1", "Include_pip=1", "Include_tcltk=1" -Wait

    Remove-Item $installer -ErrorAction SilentlyContinue

    # Refresh PATH
    $env:PATH = "$env:LOCALAPPDATA\Programs\Python\Python312\;$env:LOCALAPPDATA\Programs\Python\Python312\Scripts\;$env:PATH"

    # Verify
    try {
        $ver = & python --version 2>&1
        $python = "python"
        Write-Host "  [OK] Python installed: $ver" -ForegroundColor Green
    } catch {
        Write-Host ""
        Write-Host "  [!] Python installed but shell needs to restart." -ForegroundColor Yellow
        Write-Host "  Close this window, reopen PowerShell, and run setup.ps1 again." -ForegroundColor Yellow
        Read-Host "  Press Enter to exit"
        exit 1
    }
}

Write-Host ""
Write-Host "  Installing dependencies..." -ForegroundColor Gray
& $python -m pip install --upgrade pip 2>&1 | Out-Null
& $python -m pip install customtkinter yt-dlp

if ($LASTEXITCODE -ne 0) {
    Write-Host "  [ERROR] Failed to install dependencies." -ForegroundColor Red
    Read-Host "  Press Enter to exit"
    exit 1
}

# Check for ffmpeg
$ffmpegFound = $false
try { ffmpeg -version 2>&1 | Out-Null; $ffmpegFound = $true } catch {}
if (-not $ffmpegFound) {
    Write-Host ""
    Write-Host "  Installing ffmpeg (needed for audio downloads)..." -ForegroundColor Gray
    try {
        winget install --id Gyan.FFmpeg --accept-package-agreements --accept-source-agreements 2>&1 | Out-Null
        Write-Host "  [OK] ffmpeg installed via winget" -ForegroundColor Green
    } catch {
        Write-Host "  [!] Could not auto-install ffmpeg. The app will download it on first use." -ForegroundColor Yellow
    }
} else {
    Write-Host "  [OK] ffmpeg found" -ForegroundColor Green
}

Write-Host ""
Write-Host "  [OK] Setup complete!" -ForegroundColor Green
Write-Host ""
Write-Host "  To run:       double-click run.bat" -ForegroundColor White
Write-Host "  Or in shell:  python app_desktop.py" -ForegroundColor White
Write-Host ""
Read-Host "  Press Enter to exit"
