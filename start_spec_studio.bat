@echo off
cd /d "%~dp0"
python spec_studio.py || py spec_studio.py
echo.
pause