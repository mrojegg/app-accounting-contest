#!/bin/zsh
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
BUILD_DIR="$ROOT_DIR/Build"
DIST_DIR="$ROOT_DIR/Dist"
APP_NAME="Сортировка документов.app"
APP_BUNDLE="$BUILD_DIR/$APP_NAME"
DMG_PATH="$DIST_DIR/Сортировка документов.dmg"
OCR_HELPER="$APP_BUNDLE/Contents/Resources/Internal_DO_NOT_DELETE/ocr/bin/pdf_ocr_pkg"
APP_EXECUTABLE="$APP_BUNDLE/Contents/MacOS/SortingFilesNativeApp"

: "${APPLE_SIGN_IDENTITY:?Set APPLE_SIGN_IDENTITY to your Developer ID Application identity}"
: "${APPLE_NOTARY_PROFILE:?Set APPLE_NOTARY_PROFILE to your notarytool keychain profile name}"

if [[ ! -d "$APP_BUNDLE" ]]; then
  echo "App bundle not found: $APP_BUNDLE" >&2
  exit 1
fi

if [[ ! -f "$DMG_PATH" ]]; then
  echo "DMG not found: $DMG_PATH" >&2
  exit 1
fi

echo "==> Sign nested binaries"
if [[ -x "$OCR_HELPER" ]]; then
  codesign --force --timestamp --options runtime --sign "$APPLE_SIGN_IDENTITY" "$OCR_HELPER"
fi

if [[ -x "$APP_EXECUTABLE" ]]; then
  codesign --force --timestamp --options runtime --sign "$APPLE_SIGN_IDENTITY" "$APP_EXECUTABLE"
fi

echo "==> Sign app bundle"
codesign --force --deep --timestamp --options runtime --sign "$APPLE_SIGN_IDENTITY" "$APP_BUNDLE"
codesign --verify --deep --strict --verbose=2 "$APP_BUNDLE"

echo "==> Repackage dmg"
(
  cd "$ROOT_DIR/Internal_DO_NOT_DELETE/tools"
  zsh ./package_dmg.sh >/dev/null
)

echo "==> Sign dmg"
codesign --force --timestamp --sign "$APPLE_SIGN_IDENTITY" "$DMG_PATH"
codesign --verify --verbose=2 "$DMG_PATH"

echo "==> Notarize dmg"
xcrun notarytool submit "$DMG_PATH" --keychain-profile "$APPLE_NOTARY_PROFILE" --wait

echo "==> Staple"
xcrun stapler staple "$APP_BUNDLE"
xcrun stapler staple "$DMG_PATH"

echo "==> Gatekeeper check"
spctl -a -vv --type execute "$APP_BUNDLE"

echo
echo "Notarized artifacts:"
echo "$APP_BUNDLE"
echo "$DMG_PATH"
