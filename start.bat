@echo off
echo Vigzone AI - Setup ^& Launch Script
echo ======================================

where python >nul 2>nul
if %errorlevel% neq 0 (
    echo Python not found! Please install Python 3.10+
    exit /b 1
)

if not exist "venv" (
    echo Creating virtual environment...
    python -m venv venv
)

call venv\Scripts\activate.bat

echo Installing dependencies...
pip install --upgrade pip setuptools wheel >nul
pip install -r requirements.txt >nul
echo Dependencies installed.

if not exist ".env" (
    echo No .env file found. Creating one from .env.example...
    copy .env.example .env >nul
    echo Add your free Groq API key to .env before chatting: https://console.groq.com/keys
)

echo ======================================
echo Setup complete! Starting server...
echo ======================================
echo Web UI:    http://localhost:8000
echo API Docs:  http://localhost:8000/docs
echo Press Ctrl+C to stop the server

python app.py
