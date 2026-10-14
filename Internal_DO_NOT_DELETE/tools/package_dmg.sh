#!/bin/zsh
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
BUILD_DIR="$ROOT_DIR/Build"
DIST_DIR="$ROOT_DIR/Dist"
APP_NAME="Сортировка документов (конкурс).app"
APP_BUNDLE="$BUILD_DIR/$APP_NAME"
DMG_PATH="$DIST_DIR/Сортировка документов (конкурс).dmg"
STAGING_DIR="$DIST_DIR/.dmg-staging"

if [[ ! -d "$APP_BUNDLE" ]]; then
  (
    cd "$ROOT_DIR/Internal_DO_NOT_DELETE/app_source/native_app"
    zsh ./build_app.sh
  )
fi

mkdir -p "$DIST_DIR"
rm -rf "$STAGING_DIR"
mkdir -p "$STAGING_DIR"
cp -R "$APP_BUNDLE" "$STAGING_DIR/"
ln -s /Applications "$STAGING_DIR/Applications"
rm -f "$DMG_PATH"

hdiutil create \
  -volname "Сортировка документов" \
  -srcfolder "$STAGING_DIR" \
  -ov \
  -format UDZO \
  "$DMG_PATH" >/dev/null

rm -rf "$STAGING_DIR"

echo "$DMG_PATH"
