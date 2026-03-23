#!/bin/bash
# Build script for EU5 Goldberg Emulator tools
# Compiles Windows release package only

set -e

echo "============================================================"
echo "Building EU5 Goldberg Emulator Tools"
echo "============================================================"

# Create build directory
BUILD_DIR="build"
rm -rf "$BUILD_DIR"
mkdir -p "$BUILD_DIR"

# Version info
VERSION="1.0.0"
BUILD_TIME=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

echo ""
echo "Building Windows binaries (amd64)..."
echo "-----------------------------------"
GOOS=windows GOARCH=amd64 go build -ldflags="-s -w" -o "$BUILD_DIR/eu5-detector-windows-amd64.exe" ./cmd/eu5-detector
GOOS=windows GOARCH=amd64 go build -ldflags="-s -w" -o "$BUILD_DIR/eu5-deployer-windows-amd64.exe" ./cmd/eu5-deployer
GOOS=windows GOARCH=amd64 go build -ldflags="-s -w" -o "$BUILD_DIR/eu5-modsync-windows-amd64.exe" ./cmd/eu5-modsync

echo ""
echo "Preparing package directory..."
PACKAGE_DIR="$BUILD_DIR/eu5-tools-windows-amd64"
mkdir -p "$PACKAGE_DIR"
cp "$BUILD_DIR/eu5-deployer-windows-amd64.exe" "$PACKAGE_DIR/eu5-deployer.exe"
cp "$BUILD_DIR/eu5-detector-windows-amd64.exe" "$PACKAGE_DIR/eu5-detector.exe"
cp "$BUILD_DIR/eu5-modsync-windows-amd64.exe" "$PACKAGE_DIR/eu5-modsync.exe"
cp -R goldberg_emulator "$PACKAGE_DIR/goldberg_emulator"

echo "Creating zip package..."
(cd "$BUILD_DIR" && zip -r -q "eu5-tools-windows-amd64.zip" "eu5-tools-windows-amd64")

echo ""
echo "============================================================"
echo "Build completed successfully!"
echo "============================================================"
echo ""
echo "Output files:"
ls -lh "$BUILD_DIR"

echo ""
echo "Build info:"
echo "  Version: $VERSION"
echo "  Build time: $BUILD_TIME"
echo "  Package: $BUILD_DIR/eu5-tools-windows-amd64.zip"
