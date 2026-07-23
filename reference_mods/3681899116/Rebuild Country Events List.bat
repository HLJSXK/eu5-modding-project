@echo off
setlocal

set "MOD_ROOT=%~dp0"
set "SCRIPT_PATH=%MOD_ROOT%tools\rebuild_with_installed_mods.ps1"

if not exist "%SCRIPT_PATH%" goto missing_script

powershell -NoProfile -ExecutionPolicy Bypass -File "%SCRIPT_PATH%"
set "EXIT_CODE=%ERRORLEVEL%"

echo.
if not "%EXIT_CODE%"=="0" (
    echo Rebuild failed.
) else (
    echo Rebuild finished successfully.
)
echo.
pause
exit /b %EXIT_CODE%

:missing_script
echo Could not find: "%SCRIPT_PATH%"
echo.
echo This build does not include the rebuild tools.
echo.
pause
exit /b 1
