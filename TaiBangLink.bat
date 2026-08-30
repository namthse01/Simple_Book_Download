@echo off
chcp 65001 >nul
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
cd /d "%~dp0"
title TaiTruyen - dong lenh
if "%~1"=="" (
  set /p LINK=Dan link trang truyen roi Enter:
) else (
  set LINK=%~1
)
python app.py --url "%LINK%"
pause
