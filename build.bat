@echo off
REM Build script for EU5 Sync UI package (Windows)
REM Builds sync-ui + goldberg_emulator only

echo ============================================================
echo Building EU5 Sync UI Package
echo ============================================================

REM Create build directory
if exist build rmdir /s /q build
mkdir build
mkdir build\eu5-tools-windows-amd64

echo.
echo Preparing icon resources...
set WINRES_VERSION=v0.3.1
set WINRES_BIN=

for /f %%i in ('go env GOPATH') do set GOPATH=%%i

if exist "%GOPATH%\bin\go-winres.exe" (
	set WINRES_BIN=%GOPATH%\bin\go-winres.exe
) else (
	echo go-winres not found locally, attempting install...
	go install github.com/tc-hib/go-winres@%WINRES_VERSION%
	if not errorlevel 1 if exist "%GOPATH%\bin\go-winres.exe" (
		set WINRES_BIN=%GOPATH%\bin\go-winres.exe
	)
)

if defined WINRES_BIN (
	go run .\tools\gen_sync_ui_icon.go -out build\sync-ui-icon.png
	"%WINRES_BIN%" simply --arch amd64 --icon build\sync-ui-icon.png --manifest gui --out cmd\eu5-sync-ui\rsrc --product-name "EU5 Sync UI" --file-description "EU5 Sync UI" --original-filename "eu5-sync-ui.exe"
	if errorlevel 1 (
		echo WARNING: icon embedding failed, continuing without icon resource.
	)
) else (
	echo WARNING: go-winres unavailable, install failed or offline, continuing without icon resource.
)

echo.
echo Building Windows binary (amd64)...
echo ---------------------------------
set GOOS=windows
set GOARCH=amd64
go build -ldflags="-H windowsgui -s -w" -o build\eu5-sync-ui-windows-amd64.exe .\cmd\eu5-sync-ui

echo.
echo Preparing package directory...
copy /y build\eu5-sync-ui-windows-amd64.exe build\eu5-tools-windows-amd64\eu5-sync-ui.exe >nul
xcopy /e /i /y goldberg_emulator build\eu5-tools-windows-amd64\goldberg_emulator >nul

del /q cmd\eu5-sync-ui\rsrc_windows_amd64.syso >nul 2>&1

echo Creating zip package...
powershell -NoProfile -Command "Compress-Archive -Path 'build/eu5-tools-windows-amd64/*' -DestinationPath 'build/eu5-tools-windows-amd64.zip' -Force"

echo.
echo ============================================================
echo Build completed successfully!
echo ============================================================
echo.
echo Output files:
dir /b build

echo.
echo Direct-use package:
echo   build\eu5-tools-windows-amd64.zip

pause
