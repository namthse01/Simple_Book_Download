@echo off
chcp 65001 >nul
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
cd /d "%~dp0"
title TaiTruyen - tren trinh duyet
python app.py --web
if errorlevel 1 pause
