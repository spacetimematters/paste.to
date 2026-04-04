@echo off
:: Try common Python locations
set "PYPATH=%LOCALAPPDATA%\Programs\Python\Python312\python.exe"

python app_desktop.py 2>nul && goto :eof
py app_desktop.py 2>nul && goto :eof
"%PYPATH%" app_desktop.py 2>nul && goto :eof

echo.
echo  Python not found. Run setup first:
echo  Right-click setup.ps1 -^> Run with PowerShell
echo.
pause
