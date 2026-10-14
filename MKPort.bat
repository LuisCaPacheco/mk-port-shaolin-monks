@echo off
rem MK Port — doble clic alternativo (si no quieres usar MKPort.exe)
cd /d "%~dp0"
py -3 mkport.py
if errorlevel 1 pause
