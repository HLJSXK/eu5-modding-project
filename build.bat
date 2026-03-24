@echo off
setlocal

REM Simple build/deploy script for stable mod.
REM Default target: C:\Program Files (x86)\Steam\steamapps\common\Europa Universalis V\game\mod

set "REPO_ROOT=%~dp0"
set "SOURCE_DIR=%REPO_ROOT%src\stable"
set "TARGET_ROOT=C:\Program Files (x86)\Steam\steamapps\common\Europa Universalis V\game\mod"
set "TARGET_DIR=%TARGET_ROOT%\stable"

if not exist "%SOURCE_DIR%" (
    echo [ERROR] Source directory not found: "%SOURCE_DIR%"
    exit /b 1
)

if not exist "%TARGET_ROOT%" (
    echo [INFO] Target root not found. Creating: "%TARGET_ROOT%"
    mkdir "%TARGET_ROOT%"
    if errorlevel 1 (
        echo [ERROR] Failed to create target root. Try running as Administrator.
        exit /b 1
    )
)

if exist "%TARGET_DIR%" (
    echo [INFO] Removing previous deployment: "%TARGET_DIR%"
    rmdir /s /q "%TARGET_DIR%"
    if errorlevel 1 (
        echo [ERROR] Failed to remove old target directory. Close EU5/Steam and retry.
        exit /b 1
    )
)

echo [INFO] Copying "%SOURCE_DIR%" to "%TARGET_DIR%" ...
robocopy "%SOURCE_DIR%" "%TARGET_DIR%" /E /R:2 /W:1 /NFL /NDL /NJH /NJS /NP >nul

REM Robocopy exit code: 0-7 success, 8+ failure
if errorlevel 8 (
    echo [ERROR] Copy failed. Robocopy exit code: %errorlevel%
    exit /b 1
)

echo [OK] Stable mod deployed successfully.
echo [OK] Target: "%TARGET_DIR%"
exit /b 0
