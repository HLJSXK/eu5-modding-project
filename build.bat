@echo off
setlocal EnableExtensions EnableDelayedExpansion

REM Build/deploy script for mod targets with optional COS upload.
REM Deployment mirrors files into the existing target root so EU5 debug hot reload
REM can keep watching the same directory handle.
REM Default deploy target:
REM   C:\Program Files (x86)\Steam\steamapps\common\Europa Universalis V\game\mod
REM
REM Target archives:
REM   build\stable.zip
REM   build\sol_standalone.zip
REM
REM Optional upload destinations:
REM   modsync/packages/stable.zip
REM   modsync/packages/sol_standalone.zip
REM
REM Usage examples:
REM   build.bat
REM   build.bat sol_standalone
REM   build.bat --target sol_standalone
REM   build.bat --all
REM   build.bat all --upload-cos --cos-bucket your-bucket-1250000000 --cos-region ap-shanghai
REM
REM Credential fallback order:
REM   1) --cos-secret-id / --cos-secret-key
REM   2) TENCENT_SECRET_ID / TENCENT_SECRET_KEY environment variables

set "REPO_ROOT=%~dp0"
set "TARGET_ROOT=C:\Program Files (x86)\Steam\steamapps\common\Europa Universalis V\game\mod"
set "BUILD_DIR=%REPO_ROOT%build"
set "TARGET_SELECTION=stable"

set "UPLOAD_COS=0"
set "COS_SECRET_ID="
set "COS_SECRET_KEY="
set "COS_BUCKET=%TENCENT_COS_BUCKET%"
set "COS_REGION=%TENCENT_COS_REGION%"

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
if /I "%~1"=="--upload-cos" (
    set "UPLOAD_COS=1"
    shift
    goto parse_args
)
if /I "%~1"=="--cos-secret-id" (
    if "%~2"=="" goto arg_error
    set "COS_SECRET_ID=%~2"
    shift
    shift
    goto parse_args
)
if /I "%~1"=="--cos-secret-key" (
    if "%~2"=="" goto arg_error
    set "COS_SECRET_KEY=%~2"
    shift
    shift
    goto parse_args
)
if /I "%~1"=="--cos-bucket" (
    if "%~2"=="" goto arg_error
    set "COS_BUCKET=%~2"
    shift
    shift
    goto parse_args
)
if /I "%~1"=="--cos-region" (
    if "%~2"=="" goto arg_error
    set "COS_REGION=%~2"
    shift
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
) else if /I "%TARGET_SELECTION%"=="all" (
    set "BUILD_TARGETS=stable sol_standalone"
) else (
    echo [ERROR] Unknown target: %TARGET_SELECTION%
    goto usage
)

for %%T in (%BUILD_TARGETS%) do (
    if /I "%%~T"=="sol_standalone" (
        echo [INFO] Regenerating SOL standalone location_window.gui...
        python "%REPO_ROOT%scripts\generate_sol_location_window.py"
        if errorlevel 1 exit /b 1
    )
)

if "%COS_SECRET_ID%"=="" if not "%TENCENT_SECRET_ID%"=="" set "COS_SECRET_ID=%TENCENT_SECRET_ID%"
if "%COS_SECRET_KEY%"=="" if not "%TENCENT_SECRET_KEY%"=="" set "COS_SECRET_KEY=%TENCENT_SECRET_KEY%"

REM Common Tencent Cloud env aliases
if "%COS_SECRET_ID%"=="" if not "%TENCENTCLOUD_SECRETID%"=="" set "COS_SECRET_ID=%TENCENTCLOUD_SECRETID%"
if "%COS_SECRET_KEY%"=="" if not "%TENCENTCLOUD_SECRETKEY%"=="" set "COS_SECRET_KEY=%TENCENTCLOUD_SECRETKEY%"
if "%COS_SECRET_ID%"=="" if not "%TENCENTCLOUD_SECRET_ID%"=="" set "COS_SECRET_ID=%TENCENTCLOUD_SECRET_ID%"
if "%COS_SECRET_KEY%"=="" if not "%TENCENTCLOUD_SECRET_KEY%"=="" set "COS_SECRET_KEY=%TENCENTCLOUD_SECRET_KEY%"

echo [INFO] Running static validator on changed files...
set "PYTHONUTF8=1"
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

if "%UPLOAD_COS%"=="1" (
    call :prepare_cos_upload
    if errorlevel 1 exit /b 1
)

for %%T in (%BUILD_TARGETS%) do (
    call :deploy_target "%%~T"
    if errorlevel 1 exit /b 1

    if "%UPLOAD_COS%"=="1" (
        call :upload_target "%%~T"
        if errorlevel 1 exit /b 1
    )
)

echo [OK] Build completed for: %BUILD_TARGETS%
exit /b 0

:deploy_target
setlocal
set "TARGET_NAME=%~1"
set "SOURCE_DIR=%REPO_ROOT%src\%TARGET_NAME%"
set "TARGET_DIR=%TARGET_ROOT%\%TARGET_NAME%"
set "ZIP_PATH=%BUILD_DIR%\%TARGET_NAME%.zip"

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

if not exist "%BUILD_DIR%" mkdir "%BUILD_DIR%"
if exist "%ZIP_PATH%" del /q "%ZIP_PATH%"

echo [INFO] Creating archive: "%ZIP_PATH%"
powershell -NoProfile -ExecutionPolicy Bypass -Command "Compress-Archive -Path '%SOURCE_DIR%\*' -DestinationPath '%ZIP_PATH%' -CompressionLevel Optimal"
if errorlevel 1 (
    echo [ERROR] Failed to create "%ZIP_PATH%".
    exit /b 1
)

echo [OK] %TARGET_NAME% deployed successfully.
echo [OK] Target: "%TARGET_DIR%"
echo [OK] Archive: "%ZIP_PATH%"
endlocal
exit /b 0

:prepare_cos_upload
if "%COS_SECRET_ID%"=="" (
    echo [ERROR] COS upload requested but secret id is missing.
    echo         Use --cos-secret-id or set one of:
    echo         TENCENT_SECRET_ID / TENCENTCLOUD_SECRETID / TENCENTCLOUD_SECRET_ID
    exit /b 1
)

if "%COS_SECRET_KEY%"=="" (
    echo [ERROR] COS upload requested but secret key is missing.
    echo         Use --cos-secret-key or set one of:
    echo         TENCENT_SECRET_KEY / TENCENTCLOUD_SECRETKEY / TENCENTCLOUD_SECRET_KEY
    exit /b 1
)

if "%COS_BUCKET%"=="" (
    echo [ERROR] COS upload requested but bucket is missing.
    echo         Use --cos-bucket or set TENCENT_COS_BUCKET.
    exit /b 1
)

if "%COS_REGION%"=="" (
    echo [ERROR] COS upload requested but region is missing.
    echo         Use --cos-region or set TENCENT_COS_REGION.
    exit /b 1
)

where python >nul 2>nul
if errorlevel 1 (
    echo [ERROR] Python not found in PATH. Required for COS upload.
    exit /b 1
)

python -c "import qcloud_cos" >nul 2>nul
if errorlevel 1 (
    echo [INFO] Installing Tencent COS SDK for Python: cos-python-sdk-v5
    python -m pip install --user cos-python-sdk-v5
    if errorlevel 1 (
        echo [ERROR] Failed to install cos-python-sdk-v5.
        exit /b 1
    )
)
exit /b 0

:upload_target
setlocal
set "TARGET_NAME=%~1"
set "ZIP_PATH=%BUILD_DIR%\%TARGET_NAME%.zip"
set "COS_KEY=modsync/packages/%TARGET_NAME%.zip"

echo [INFO] Uploading "%ZIP_PATH%" to COS: %COS_KEY%
python "%REPO_ROOT%tools\upload_cos.py" --file "%ZIP_PATH%" --bucket "%COS_BUCKET%" --region "%COS_REGION%" --secret-id "%COS_SECRET_ID%" --secret-key "%COS_SECRET_KEY%" --key "%COS_KEY%"
if errorlevel 1 (
    echo [ERROR] COS upload failed for %TARGET_NAME%.
    exit /b 1
)

echo [OK] COS upload completed: cos://%COS_BUCKET%/%COS_KEY%
endlocal
exit /b 0

:usage
echo Usage:
echo   build.bat [stable^|sol_standalone^|all] [--target TARGET] [--all] [--upload-cos] [--cos-secret-id ID] [--cos-secret-key KEY] [--cos-bucket BUCKET] [--cos-region REGION]
echo.
echo Targets:
echo   stable          Build and deploy src\stable to mod\stable and build\stable.zip.
echo   sol_standalone  Build and deploy src\sol_standalone to mod\sol_standalone and build\sol_standalone.zip.
echo   all             Build and deploy both targets.
echo.
echo Notes:
echo   - If no target is provided, script builds stable.
echo   - If --upload-cos is omitted, script only deploys and creates zip archives.
echo   - Credentials can come from TENCENT_SECRET_ID and TENCENT_SECRET_KEY.
echo   - Bucket/region can come from TENCENT_COS_BUCKET and TENCENT_COS_REGION.
exit /b 1
