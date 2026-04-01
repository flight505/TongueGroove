#!/bin/bash
# deploy.sh — Copy Tongue & Groove add-in to Fusion 360 AddIns directory.
# Run this from the project directory after making changes.
# Usage: bash deploy.sh

SRC="/Users/jesper/Projects/3Dprint/Tongue&Groove"
DST="/Users/jesper/Library/Application Support/Autodesk/Autodesk Fusion 360/API/AddIns/TongueGroove"

echo "Deploying Tongue & Groove → TongueGroove..."
mkdir -p "$DST"
cp "$SRC/Tongue&Groove.py"       "$DST/TongueGroove.py"   && echo "  ✓ TongueGroove.py"
cp "$SRC/Tongue&Groove.manifest"  "$DST/TongueGroove.manifest" && echo "  ✓ TongueGroove.manifest"
cp "$SRC/ScriptIcon.svg"          "$DST/ScriptIcon.svg"    && echo "  ✓ ScriptIcon.svg"
echo ""
echo "Done. Reload in Fusion 360: Shift+S → Add-Ins → TongueGroove → toggle off/on."
