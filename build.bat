@echo off
REM Build script for EU5 Goldberg Emulator tools (Windows)
REM Compiles Windows release package only

echo ============================================================
echo Building EU5 Goldberg Emulator Tools
echo ============================================================

REM Create build directory
if exist build rmdir /s /q build
mkdir build
mkdir build\eu5-tools-windows-amd64

echo.
echo Building Windows binaries (amd64)...
echo -----------------------------------
set GOOS=windows
set GOARCH=amd64
go build -ldflags="-s -w" -o build\eu5-detector-windows-amd64.exe .\cmd\eu5-detector
go build -ldflags="-s -w" -o build\eu5-deployer-windows-amd64.exe .\cmd\eu5-deployer
go build -ldflags="-s -w" -o build\eu5-modsync-windows-amd64.exe .\cmd\eu5-modsync

echo.
echo Preparing package directory...
copy /y build\eu5-deployer-windows-amd64.exe build\eu5-tools-windows-amd64\eu5-deployer.exe >nul
copy /y build\eu5-detector-windows-amd64.exe build\eu5-tools-windows-amd64\eu5-detector.exe >nul
copy /y build\eu5-modsync-windows-amd64.exe build\eu5-tools-windows-amd64\eu5-modsync.exe >nul
xcopy /e /i /y goldberg_emulator build\eu5-tools-windows-amd64\goldberg_emulator >nul

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
