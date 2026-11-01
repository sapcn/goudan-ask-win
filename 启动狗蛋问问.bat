@echo off
title 狗蛋问问
rem %~dp0 = 本 bat 所在目录（自适应任意安装路径）
cd /d %~dp0
python -m app.main
if errorlevel 1 pause
