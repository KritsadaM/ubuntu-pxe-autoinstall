#!/usr/bin/env bash
# ==============================================================================
# Script: download_assets.sh
# Purpose: Download Ubuntu 24.04, 22.04, 20.04 ISOs and extract netboot kernels
# ==============================================================================

set -euo pipefail

DATA_DIR="./data"
ISO_DIR="$DATA_DIR/iso"
NETBOOT_DIR="$DATA_DIR/netboot"

mkdir -p "$ISO_DIR" "$NETBOOT_DIR/ubuntu-24.04" "$NETBOOT_DIR/ubuntu-22.04" "$NETBOOT_DIR/ubuntu-20.04"

echo "=========================================================="
echo " Ubuntu PXE Asset Downloader"
echo " Target ISO Directory:     $ISO_DIR"
echo " Target Netboot Directory: $NETBOOT_DIR"
echo "=========================================================="

# Check extraction tool (7z, bsdtar, or isoinfo)
EXTRACTOR=""
if command -v 7z &> /dev/null; then
    EXTRACTOR="7z"
elif command -v bsdtar &> /dev/null; then
    EXTRACTOR="bsdtar"
else
    echo "Warning: Neither '7z' nor 'bsdtar' found. Kernels will need to be extracted later or inside Docker container."
fi

download_and_extract() {
    local VER="$1"
    local ISO_URL="$2"
    local ISO_FILE="$3"
    local TARGET_DIR="$NETBOOT_DIR/$VER"
    local ISO_PATH="$ISO_DIR/$ISO_FILE"

    echo ""
    echo ">>> Processing $VER ($ISO_FILE)..."

    # Check if any matching ISO already exists for this version
    local EXISTING_ISO
    EXISTING_ISO=$(find "$ISO_DIR" -maxdepth 1 -name "${VER}*.iso" | head -n 1)

    if [ -n "$EXISTING_ISO" ]; then
        echo "Found existing ISO: $EXISTING_ISO (skipping download)"
        ISO_PATH="$EXISTING_ISO"
    else
        echo "Downloading $ISO_FILE from $ISO_URL..."
        curl -L --progress-bar -o "$ISO_PATH" "$ISO_URL"
    fi

    # Extract casper/vmlinuz and casper/initrd
    if [ -f "$TARGET_DIR/vmlinuz" ] && [ -f "$TARGET_DIR/initrd" ]; then
        echo "Netboot kernel and initrd already extracted in $TARGET_DIR (skipping extraction)"
    elif [ "$EXTRACTOR" = "7z" ]; then
        echo "Extracting vmlinuz and initrd using 7z..."
        7z e -y "$ISO_PATH" -o"$TARGET_DIR" casper/vmlinuz casper/initrd > /dev/null
        chmod 644 "$TARGET_DIR/vmlinuz" "$TARGET_DIR/initrd"
        echo "Extracted successfully to $TARGET_DIR"
    elif [ "$EXTRACTOR" = "bsdtar" ]; then
        echo "Extracting vmlinuz and initrd using bsdtar..."
        bsdtar -xf "$ISO_PATH" -C "$TARGET_DIR" --strip-components 1 casper/vmlinuz casper/initrd
        chmod 644 "$TARGET_DIR/vmlinuz" "$TARGET_DIR/initrd"
        echo "Extracted successfully to $TARGET_DIR"
    else
        echo "Skipping extraction (install 7zip / p7zip-full to extract automatically)"
    fi
}

# 1. Ubuntu 24.04 LTS (Noble Numbat)
download_and_extract "ubuntu-24.04" \
    "https://releases.ubuntu.com/24.04/ubuntu-24.04.4-live-server-amd64.iso" \
    "ubuntu-24.04-live-server-amd64.iso"

# 2. Ubuntu 22.04 LTS (Jammy Jellyfish)
download_and_extract "ubuntu-22.04" \
    "https://releases.ubuntu.com/22.04/ubuntu-22.04.5-live-server-amd64.iso" \
    "ubuntu-22.04-live-server-amd64.iso"

# 3. Ubuntu 20.04 LTS (Focal Fossa)
download_and_extract "ubuntu-20.04" \
    "https://releases.ubuntu.com/20.04/ubuntu-20.04.6-live-server-amd64.iso" \
    "ubuntu-20.04-live-server-amd64.iso"

echo ""
echo "=========================================================="
echo " All Ubuntu ISO assets and kernels processed!"
echo "=========================================================="
