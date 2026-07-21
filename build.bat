@echo off
setlocal EnableExtensions EnableDelayedExpansion

REM Build/deploy script for mod targets.
REM Deployment mirrors files into the existing target root so EU5 debug hot reload
REM can keep watching the same directory handle.
REM Default deploy target:
REM   C:\Program Files (x86)\Steam\steamapps\common\Europa Universalis V\game\mod
REM
REM Usage examples:
REM   build.bat
REM   build.bat sol_standalone
REM   build.bat sol_pp_compatibility_submod
REM   build.bat --target sol_standalone
REM   build.bat --all

set "REPO_ROOT=%~dp0"
set "TARGET_ROOT=C:\Program Files (x86)\Steam\steamapps\common\Europa Universalis V\game\mod"
set "TARGET_SELECTION=all"

:parse_args
if "%~1"=="" goto args_done
if /I "%~1"=="stable" (
    set "TARGET_SELECTION=stable"
    shift
    goto parse_args
)
if /I "%~1"=="sol_standalone" (
    set "TARGET_SELECTION=sol_standalone"
    shift
    goto parse_args
)
if /I "%~1"=="sol_pp_compatibility_submod" (
    set "TARGET_SELECTION=sol_pp_compatibility_submod"
    shift
    goto parse_args
)
if /I "%~1"=="all" (
    set "TARGET_SELECTION=all"
    shift
    goto parse_args
)
if /I "%~1"=="--target" (
    if "%~2"=="" goto arg_error
    set "TARGET_SELECTION=%~2"
    shift
    shift
    goto parse_args
)
if /I "%~1"=="--all" (
    set "TARGET_SELECTION=all"
    shift
    goto parse_args
)
if /I "%~1"=="--help" goto usage
if /I "%~1"=="-h" goto usage

echo [ERROR] Unknown argument: %~1
goto usage

:arg_error
echo [ERROR] Missing value for argument: %~1
goto usage

:args_done

if /I "%TARGET_SELECTION%"=="stable" (
    set "BUILD_TARGETS=stable"
) else if /I "%TARGET_SELECTION%"=="sol_standalone" (
    set "BUILD_TARGETS=sol_standalone"
) else if /I "%TARGET_SELECTION%"=="sol_pp_compatibility_submod" (
    set "BUILD_TARGETS=sol_pp_compatibility_submod"
) else if /I "%TARGET_SELECTION%"=="all" (
    set "BUILD_TARGETS=stable sol_standalone sol_pp_compatibility_submod"
) else (
    echo [ERROR] Unknown target: %TARGET_SELECTION%
    goto usage
)

set "PYTHONUTF8=1"

echo [INFO] Regenerating SOL generated sources...
python "%REPO_ROOT%scripts\gen_sol_chain.py" --target "%TARGET_SELECTION%"
if errorlevel 1 exit /b 1

echo [INFO] Running static validator on changed files...
set "VALIDATE_OUT=%TEMP%\sol_validate_out.txt"
python "%REPO_ROOT%scripts\validate.py" --changed > "!VALIDATE_OUT!" 2>&1
set "VALIDATE_RC=!errorlevel!"
type "!VALIDATE_OUT!"
del "!VALIDATE_OUT!" 2>nul
if !VALIDATE_RC! neq 0 (
    echo [ERROR] Validation failed. Fix the issues above before deploying.
    exit /b 1
)

echo [INFO] Ensuring UTF-8 BOM on all .yml and .txt files under src...
powershell -NoProfile -ExecutionPolicy Bypass -File "%REPO_ROOT%scripts\ensure-utf8bom.ps1" -Path "%REPO_ROOT%src"
if errorlevel 1 (
    echo [ERROR] UTF-8 BOM fix step failed.
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

for %%T in (%BUILD_TARGETS%) do (
    call :deploy_target "%%~T"
    if errorlevel 1 exit /b 1
)

echo [OK] Build completed for: %BUILD_TARGETS%
exit /b 0

:deploy_target
setlocal
set "TARGET_NAME=%~1"
set "SOURCE_DIR=%REPO_ROOT%src\%TARGET_NAME%"
set "TARGET_DIR=%TARGET_ROOT%\%TARGET_NAME%"

if not exist "%SOURCE_DIR%" (
    echo [ERROR] Source directory not found: "%SOURCE_DIR%"
    exit /b 1
)

echo [INFO] Mirroring "%SOURCE_DIR%" to "%TARGET_DIR%"
robocopy "%SOURCE_DIR%" "%TARGET_DIR%" /MIR /R:2 /W:1 /NFL /NDL /NJH /NJS /NP
set "ROBOCOPY_RC=!errorlevel!"

REM Robocopy exit code: 0-7 success, 8+ failure
if !ROBOCOPY_RC! GEQ 8 (
    echo [ERROR] Copy failed for %TARGET_NAME%. Robocopy exit code: !ROBOCOPY_RC!
    exit /b 1
)
cmd /c "exit /b 0"

echo [OK] %TARGET_NAME% deployed successfully.
echo [OK] Target: "%TARGET_DIR%"
endlocal
exit /b 0

:usage
echo Usage:
echo   build.bat [stable^|sol_standalone^|sol_pp_compatibility_submod^|all] [--target TARGET] [--all]
echo.
echo Targets:
echo   stable          Build and deploy src\stable to mod\stable.
echo   sol_standalone  Build and deploy src\sol_standalone to mod\sol_standalone.
echo   sol_pp_compatibility_submod  Build and deploy the SOL-PP compatibility submod.
echo   all             Build and deploy all targets.
echo.
echo Notes:
echo   - If no target is provided, script builds and deploys all targets.
echo   - The script only deploys selected targets.
echo   - The script does not create repository build\ archives.
exit /b 1
