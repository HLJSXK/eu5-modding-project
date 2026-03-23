#!/bin/bash
# Build script for EU5 Sync UI package
# Builds sync-ui + goldberg_emulator only

set -e

echo "============================================================"
echo "Building EU5 Sync UI Package"
echo "============================================================"

# Create build directory
BUILD_DIR="build"
rm -rf "$BUILD_DIR"
mkdir -p "$BUILD_DIR"

echo ""
echo "Preparing icon resources..."
WINRES_VERSION="v0.3.1"
WINRES_BIN="$(go env GOPATH)/bin/go-winres"

if [ ! -x "$WINRES_BIN" ]; then
	echo "go-winres not found locally, attempting install..."
	if ! go install "github.com/tc-hib/go-winres@${WINRES_VERSION}"; then
		echo "WARNING: go-winres install failed (possibly offline). Continuing without icon resource."
		WINRES_BIN=""
	fi
fi

if [ -n "$WINRES_BIN" ] && [ -x "$WINRES_BIN" ]; then
	go run ./tools/gen_sync_ui_icon.go -out "$BUILD_DIR/sync-ui-icon.png"
	if ! "$WINRES_BIN" simply --arch amd64 --icon "$BUILD_DIR/sync-ui-icon.png" --manifest gui --out cmd/eu5-sync-ui/rsrc --product-name "EU5 Sync UI" --file-description "EU5 Sync UI" --original-filename "eu5-sync-ui.exe"; then
		echo "WARNING: icon embedding failed. Continuing without icon resource."
	fi
fi

echo ""
echo "Building Windows binary (amd64)..."
echo "---------------------------------"
GOOS=windows GOARCH=amd64 go build -ldflags="-H windowsgui -s -w" -o "$BUILD_DIR/eu5-sync-ui-windows-amd64.exe" ./cmd/eu5-sync-ui

echo ""
echo "Preparing package directory..."
PACKAGE_DIR="$BUILD_DIR/eu5-tools-windows-amd64"
mkdir -p "$PACKAGE_DIR"
cp "$BUILD_DIR/eu5-sync-ui-windows-amd64.exe" "$PACKAGE_DIR/eu5-sync-ui.exe"
cp -R goldberg_emulator "$PACKAGE_DIR/goldberg_emulator"

rm -f cmd/eu5-sync-ui/rsrc_windows_amd64.syso

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
echo "Package: $BUILD_DIR/eu5-tools-windows-amd64.zip"
