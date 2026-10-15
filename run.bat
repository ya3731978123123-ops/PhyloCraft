@echo off
title PhyloCraft - Visual Evolutionary Biology Workbench
echo ========================================================
echo   Starting PhyloCraft (Visual Evolutionary Biology Suite)
echo ========================================================
echo.

python main.py
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [Error] Application closed with an error code: %ERRORLEVEL%
    pause
)
