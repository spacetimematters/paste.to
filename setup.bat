@echo off
title paste.to - Setup
echo.
echo  paste.to - YouTube Downloader Setup
echo  ====================================
echo.

:: Check if Python is already installed
python --version >nul 2>&1
if %errorlevel% equ 0 (
    echo  [OK] Python is already installed.
    goto :install_deps
)

py --version >nul 2>&1
if %errorlevel% equ 0 (
    echo  [OK] Python is already installed.
    goto :install_deps_py
)

echo  [!] Python is not installed. Downloading now...
echo.

:: Download Python installer
set PYTHON_URL=https://www.python.org/ftp/python/3.12.4/python-3.12.4-amd64.exe
set INSTALLER=%TEMP%\python-installer.exe

echo  Downloading Python 3.12...
powershell -Command "Invoke-WebRequest -Uri '%PYTHON_URL%' -OutFile '%INSTALLER%'" 2>nul
if not exist "%INSTALLER%" (
    echo  [ERROR] Download failed. Please install Python manually from python.org
    pause
    exit /b 1
)

echo  Installing Python (this may take a minute)...
"%INSTALLER%" /quiet InstallAllUsers=0 PrependPath=1 Include_pip=1 Include_tcltk=1
if %errorlevel% neq 0 (
    echo  [ERROR] Install failed. Running interactive installer instead...
    "%INSTALLER%" PrependPath=1 Include_pip=1 Include_tcltk=1
)

del "%INSTALLER%" >nul 2>&1

:: Refresh PATH
set "PATH=%LOCALAPPDATA%\Programs\Python\Python312\;%LOCALAPPDATA%\Programs\Python\Python312\Scripts\;%PATH%"

python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo.
    echo  [!] Python installed but PATH not updated yet.
    echo  Please close this window, reopen it, and run setup.bat again.
    pause
    exit /b 1
)

:install_deps
echo.
echo  Installing dependencies...
python -m pip install --upgrade pip >nul 2>&1
python -m pip install customtkinter yt-dlp
if %errorlevel% neq 0 (
    echo  [ERROR] Failed to install dependencies.
    pause
    exit /b 1
)
goto :done

:install_deps_py
echo.
echo  Installing dependencies...
py -m pip install --upgrade pip >nul 2>&1
py -m pip install customtkinter yt-dlp
if %errorlevel% neq 0 (
    echo  [ERROR] Failed to install dependencies.
    pause
    exit /b 1
)
goto :done

:done
echo.
echo  [OK] Setup complete!
echo.
echo  To run:  double-click run.bat
echo  To build exe:  double-click build.bat
echo.
pause
