@echo off
title Premium Remote Suite - Uninstaller
echo [*] Starting total removal of Remote Agent...
echo.

:: 1. Убиваем процессы
echo [+] Terminating active processes...
taskkill /F /IM ShellHost.exe /T >nul 2>&1
timeout /t 2 /nobreak >nul

:: 2. Удаляем автозагрузку из реестра
echo [+] Removing Registry persistence...
reg delete "HKCU\Software\Microsoft\Windows\CurrentVersion\Run" /v "Windows Update Component" /f >nul 2>&1

:: 3. Удаляем задачу из планировщика
echo [+] Removing Task Scheduler entry...
schtasks /delete /tn "MicrosoftWindowsHostUpdate" /f >nul 2>&1

:: 4. Удаляем файлы из AppData
echo [+] Deleting agent files from AppData...
if exist "%APPDATA%\Microsoft\Windows\Templates\ShellHost.exe" (
    del /f /q "%APPDATA%\Microsoft\Windows\Templates\ShellHost.exe"
)
if exist "%APPDATA%\Microsoft\Windows\Templates\shellhost.py" (
    del /f /q "%APPDATA%\Microsoft\Windows\Templates\shellhost.py"
)

echo.
echo [!] Agent has been completely removed from this system.
echo.
pause
