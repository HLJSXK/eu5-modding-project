@echo off
setlocal EnableExtensions EnableDelayedExpansion

REM Build/deploy script for stable/develop mods with optional COS upload.
REM Default deploy target:
REM   C:\Program Files (x86)\Steam\steamapps\common\Europa Universalis V\game\mod
REM
REM Optional upload destination (fixed object key):
REM   modsync/packages/stable.zip
REM
REM Usage examples:
REM   build.bat
REM   build.bat --upload-cos --cos-bucket your-bucket-1250000000 --cos-region ap-shanghai
REM   build.bat --upload-cos --cos-secret-id xxx --cos-secret-key yyy --cos-bucket bkt-1250000000 --cos-region ap-guangzhou
REM
REM Credential fallback order:
REM   1) --cos-secret-id / --cos-secret-key
REM   2) TENCENT_SECRET_ID / TENCENT_SECRET_KEY environment variables

set "REPO_ROOT=%~dp0"
set "SOURCE_DIR=%REPO_ROOT%src\stable"
set "SOURCE_DIR_DEVELOP=%REPO_ROOT%src\develop"
set "TARGET_ROOT=C:\Program Files (x86)\Steam\steamapps\common\Europa Universalis V\game\mod"
set "TARGET_DIR=%TARGET_ROOT%\stable"
set "TARGET_DIR_DEVELOP=%TARGET_ROOT%\develop"
set "BUILD_DIR=%REPO_ROOT%build"
set "ZIP_PATH=%BUILD_DIR%\stable.zip"

set "UPLOAD_COS=0"
set "COS_SECRET_ID="
set "COS_SECRET_KEY="
set "COS_BUCKET=%TENCENT_COS_BUCKET%"
set "COS_REGION=%TENCENT_COS_REGION%"

:parse_args
if "%~1"=="" goto args_done
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

if "%COS_SECRET_ID%"=="" if not "%TENCENT_SECRET_ID%"=="" set "COS_SECRET_ID=%TENCENT_SECRET_ID%"
if "%COS_SECRET_KEY%"=="" if not "%TENCENT_SECRET_KEY%"=="" set "COS_SECRET_KEY=%TENCENT_SECRET_KEY%"

REM Common Tencent Cloud env aliases
if "%COS_SECRET_ID%"=="" if not "%TENCENTCLOUD_SECRETID%"=="" set "COS_SECRET_ID=%TENCENTCLOUD_SECRETID%"
if "%COS_SECRET_KEY%"=="" if not "%TENCENTCLOUD_SECRETKEY%"=="" set "COS_SECRET_KEY=%TENCENTCLOUD_SECRETKEY%"
if "%COS_SECRET_ID%"=="" if not "%TENCENTCLOUD_SECRET_ID%"=="" set "COS_SECRET_ID=%TENCENTCLOUD_SECRET_ID%"
if "%COS_SECRET_KEY%"=="" if not "%TENCENTCLOUD_SECRET_KEY%"=="" set "COS_SECRET_KEY=%TENCENTCLOUD_SECRET_KEY%"

echo [INFO] Ensuring UTF-8 BOM on all .yml localization files...
powershell -NoProfile -ExecutionPolicy Bypass -File "%REPO_ROOT%scripts\ensure-utf8bom.ps1" -Path "%REPO_ROOT%src"
if errorlevel 1 (
    echo [ERROR] UTF-8 BOM fix step failed.
    exit /b 1
)

if not exist "%SOURCE_DIR%" (
    echo [ERROR] Source directory not found: "%SOURCE_DIR%"
    exit /b 1
)

if not exist "%SOURCE_DIR_DEVELOP%" (
    echo [ERROR] Source directory not found: "%SOURCE_DIR_DEVELOP%"
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

echo [INFO] Copying "%SOURCE_DIR%" to "%TARGET_DIR%"
robocopy "%SOURCE_DIR%" "%TARGET_DIR%" /E /R:2 /W:1 /NFL /NDL /NJH /NJS /NP >nul

REM Robocopy exit code: 0-7 success, 8+ failure
if errorlevel 8 (
    echo [ERROR] Copy failed. Robocopy exit code: %errorlevel%
    exit /b 1
)

if exist "%TARGET_DIR_DEVELOP%" (
    echo [INFO] Removing previous deployment: "%TARGET_DIR_DEVELOP%"
    rmdir /s /q "%TARGET_DIR_DEVELOP%"
    if errorlevel 1 (
        echo [ERROR] Failed to remove old develop target directory. Close EU5/Steam and retry.
        exit /b 1
    )
)

echo [INFO] Copying "%SOURCE_DIR_DEVELOP%" to "%TARGET_DIR_DEVELOP%"
robocopy "%SOURCE_DIR_DEVELOP%" "%TARGET_DIR_DEVELOP%" /E /R:2 /W:1 /NFL /NDL /NJH /NJS /NP >nul

if errorlevel 8 (
    echo [ERROR] Develop copy failed. Robocopy exit code: %errorlevel%
    exit /b 1
)

if not exist "%BUILD_DIR%" mkdir "%BUILD_DIR%"
if exist "%ZIP_PATH%" del /q "%ZIP_PATH%"

echo [INFO] Creating archive: "%ZIP_PATH%"
powershell -NoProfile -ExecutionPolicy Bypass -Command "Compress-Archive -Path '%SOURCE_DIR%\*' -DestinationPath '%ZIP_PATH%' -CompressionLevel Optimal"
if errorlevel 1 (
    echo [ERROR] Failed to create "%ZIP_PATH%".
    exit /b 1
)

echo [OK] Stable and develop mods deployed successfully.
echo [OK] Target: "%TARGET_DIR%"
echo [OK] Target: "%TARGET_DIR_DEVELOP%"
echo [OK] Archive: "%ZIP_PATH%"

if "%UPLOAD_COS%"=="0" exit /b 0

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

echo [INFO] Uploading "%ZIP_PATH%" to COS: modsync/packages/stable.zip
python "%REPO_ROOT%tools\upload_cos.py" --file "%ZIP_PATH%" --bucket "%COS_BUCKET%" --region "%COS_REGION%" --secret-id "%COS_SECRET_ID%" --secret-key "%COS_SECRET_KEY%" --key "modsync/packages/stable.zip"
if errorlevel 1 (
    echo [ERROR] COS upload failed.
    exit /b 1
)

echo [OK] COS upload completed: cos://%COS_BUCKET%/modsync/packages/stable.zip
exit /b 0

:usage
echo Usage:
echo   build.bat [--upload-cos] [--cos-secret-id ID] [--cos-secret-key KEY] [--cos-bucket BUCKET] [--cos-region REGION]
echo.
echo Notes:
echo   - If --upload-cos is omitted, script only deploys and creates stable.zip.
echo   - Credentials can come from TENCENT_SECRET_ID and TENCENT_SECRET_KEY.
echo   - Bucket/region can come from TENCENT_COS_BUCKET and TENCENT_COS_REGION.
exit /b 1
