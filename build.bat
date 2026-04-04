@echo off
title paste.to - Build
echo.
echo  Building paste-to.exe...
echo.

python -m pip install pyinstaller >nul 2>&1
python build.py
if %errorlevel% equ 0 (
    echo.
    echo  [OK] Built! Your exe is in the dist\ folder.
) else (
    echo.
    echo  [ERROR] Build failed.
)
echo.
pause
