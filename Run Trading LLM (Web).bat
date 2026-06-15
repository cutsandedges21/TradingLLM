@echo off
title Trading LLM (Web)
cd /d "%~dp0"
echo ============================================
echo   Trading LLM  -  modern web terminal
echo   Opening http://127.0.0.1:8000 in your browser.
echo   Keep this window open; close it to quit.
echo ============================================
echo.
python app_web.py
echo.
echo Server stopped. If you saw an error above, read it, then:
pause
