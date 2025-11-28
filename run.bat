@echo off
echo Starting QR Code Generator PC Tool...
echo.
python run.py
if errorlevel 1 (
    echo.
    echo Error occurred. Please check if Python is installed and all dependencies are installed.
    echo.
    echo To install dependencies, run:
    echo pip install -r requirements.txt
    echo.
    pause
)

