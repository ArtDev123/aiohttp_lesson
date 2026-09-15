@echo off
REM Обёртка для PowerShell-скрипта. Двойной клик или:
REM   scripts\init_postgres.bat
powershell -ExecutionPolicy Bypass -File "%~dp0init_postgres.ps1"
if errorlevel 1 pause
