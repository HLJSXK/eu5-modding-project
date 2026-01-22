@echo off
REM Build script for EU5 Goldberg Emulator tools (Windows)
REM Compiles for Windows, Linux, and macOS

echo ============================================================
echo Building EU5 Goldberg Emulator Tools
echo ============================================================

REM Create build directory
if exist build rmdir /s /q build
mkdir build

echo.
echo Building eu5-detector...
echo ------------------------

echo Building for Windows (amd64)...
set GOOS=windows
set GOARCH=amd64
go build -ldflags="-s -w" -o build\eu5-detector-windows-amd64.exe .\cmd\eu5-detector

echo Building for Linux (amd64)...
set GOOS=linux
set GOARCH=amd64
go build -ldflags="-s -w" -o build\eu5-detector-linux-amd64 .\cmd\eu5-detector

echo Building for macOS (amd64)...
set GOOS=darwin
set GOARCH=amd64
go build -ldflags="-s -w" -o build\eu5-detector-darwin-amd64 .\cmd\eu5-detector

echo Building for macOS (arm64)...
set GOOS=darwin
set GOARCH=arm64
go build -ldflags="-s -w" -o build\eu5-detector-darwin-arm64 .\cmd\eu5-detector

echo.
echo Building eu5-deployer...
echo ------------------------

echo Building for Windows (amd64)...
set GOOS=windows
set GOARCH=amd64
go build -ldflags="-s -w" -o build\eu5-deployer-windows-amd64.exe .\cmd\eu5-deployer

echo Building for Linux (amd64)...
set GOOS=linux
set GOARCH=amd64
go build -ldflags="-s -w" -o build\eu5-deployer-linux-amd64 .\cmd\eu5-deployer

echo Building for macOS (amd64)...
set GOOS=darwin
set GOARCH=amd64
go build -ldflags="-s -w" -o build\eu5-deployer-darwin-amd64 .\cmd\eu5-deployer

echo Building for macOS (arm64)...
set GOOS=darwin
set GOARCH=arm64
go build -ldflags="-s -w" -o build\eu5-deployer-darwin-arm64 .\cmd\eu5-deployer

echo.
echo ============================================================
echo Build completed successfully!
echo ============================================================
echo.
echo Output files:
dir /b build

pause
