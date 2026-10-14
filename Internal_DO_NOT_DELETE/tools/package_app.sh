#!/bin/zsh
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
BUILD_DIR="$ROOT_DIR/Build"
DIST_DIR="$ROOT_DIR/Dist"
APP_NAME="Сортировка документов.app"
APP_BUNDLE="$BUILD_DIR/$APP_NAME"
ZIP_PATH="$DIST_DIR/Сортировка документов.zip"

if [[ ! -d "$APP_BUNDLE" ]]; then
  (
    cd "$ROOT_DIR/Internal_DO_NOT_DELETE/app_source/native_app"
    zsh ./build_app.sh
  )
fi

mkdir -p "$DIST_DIR"
rm -f "$ZIP_PATH"
(
  cd "$BUILD_DIR"
  COPYFILE_DISABLE=1 zip -qry -X "$ZIP_PATH" "$APP_NAME"
)

echo "$ZIP_PATH"
