@echo off
echo [+] Starting Premium Remote Suite Installation...
echo.
cd %~dp0
echo [1/2] Installing Node.js dependencies...
call npm install express socket.io ejs multer node-fetch
echo.
echo [2/3] Checking Python environment...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [!] WARNING: Python not found in PATH!
) else (
    echo [+] Python is ready. Installing packages...
    pip install pynput pycryptodome pypiwin32 mss opencv-python numpy pyinstaller
)
echo.
echo [+] Installation Complete!
echo.
echo To start the server: node server.js
echo To start the agent:  python agent.py
pause
