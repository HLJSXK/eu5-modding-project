#!/bin/bash
# Build script for EU5 Goldberg Emulator tools
# Compiles for Windows, Linux, and macOS

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
echo "Building eu5-detector..."
echo "------------------------"

# Windows 64-bit
echo "Building for Windows (amd64)..."
GOOS=windows GOARCH=amd64 go build -ldflags="-s -w" -o "$BUILD_DIR/eu5-detector-windows-amd64.exe" ./cmd/eu5-detector

# Linux 64-bit
echo "Building for Linux (amd64)..."
GOOS=linux GOARCH=amd64 go build -ldflags="-s -w" -o "$BUILD_DIR/eu5-detector-linux-amd64" ./cmd/eu5-detector

# macOS 64-bit (Intel)
echo "Building for macOS (amd64)..."
GOOS=darwin GOARCH=amd64 go build -ldflags="-s -w" -o "$BUILD_DIR/eu5-detector-darwin-amd64" ./cmd/eu5-detector

# macOS ARM64 (Apple Silicon)
echo "Building for macOS (arm64)..."
GOOS=darwin GOARCH=arm64 go build -ldflags="-s -w" -o "$BUILD_DIR/eu5-detector-darwin-arm64" ./cmd/eu5-detector

echo ""
echo "Building eu5-deployer..."
echo "------------------------"

# Windows 64-bit
echo "Building for Windows (amd64)..."
GOOS=windows GOARCH=amd64 go build -ldflags="-s -w" -o "$BUILD_DIR/eu5-deployer-windows-amd64.exe" ./cmd/eu5-deployer

# Linux 64-bit
echo "Building for Linux (amd64)..."
GOOS=linux GOARCH=amd64 go build -ldflags="-s -w" -o "$BUILD_DIR/eu5-deployer-linux-amd64" ./cmd/eu5-deployer

# macOS 64-bit (Intel)
echo "Building for macOS (amd64)..."
GOOS=darwin GOARCH=amd64 go build -ldflags="-s -w" -o "$BUILD_DIR/eu5-deployer-darwin-amd64" ./cmd/eu5-deployer

# macOS ARM64 (Apple Silicon)
echo "Building for macOS (arm64)..."
GOOS=darwin GOARCH=arm64 go build -ldflags="-s -w" -o "$BUILD_DIR/eu5-deployer-darwin-arm64" ./cmd/eu5-deployer

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
