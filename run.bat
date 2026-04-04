@echo off
:: Try python first, then py
python app_desktop.py 2>nul
if %errorlevel% neq 0 (
    py app_desktop.py 2>nul
)
if %errorlevel% neq 0 (
    echo Python not found. Run setup.bat first.
    pause
)
