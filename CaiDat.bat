@echo off
chcp 65001 >nul
cd /d "%~dp0"
title Cai dat DCR - DragonCloud_reading
powershell -ExecutionPolicy Bypass -File "%~dp0CaiDat.ps1"
