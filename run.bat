@echo off
title TIRE-MES 4.0 - Industrial Manufacturing Execution System
color 0B

echo ===============================================================================
echo     TIRE-MES 4.0 - HE THONG DIEU HANH SAN XUAT NHA MAY LOP XE
echo     Kien Truc MES Engineer 10 Nam Kinh Nghiem - Chuan ISA-95 Level 3
echo ===============================================================================
echo.

echo [1/3] Kiem tra moi truong Python...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [LOI] Khong tim thay Python tren he thong! Vui long cai dat Python 3.10 tro len.
    pause
    exit /b
)

echo [2/3] Khoi dong Database & Server MES...
echo [3/3] Dang mo trinh duyet tai: http://localhost:8000
start http://localhost:8000

echo.
echo ===============================================================================
echo   MES Application dang chay tai: http://localhost:8000
echo   Tai lieu API Swagger tai:      http://localhost:8000/docs
echo   Nhan Ctrl+C de dung may chu.
echo ===============================================================================
echo.

python main.py
pause
