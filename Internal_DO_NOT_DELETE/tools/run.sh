#!/bin/zsh
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
APP_BUNDLE="$ROOT_DIR/Build/Сортировка документов.app"
APP_EXEC="$APP_BUNDLE/Contents/MacOS/SortingFilesNativeApp"

if [[ ! -x "$APP_EXEC" ]]; then
  zsh "$ROOT_DIR/Internal_DO_NOT_DELETE/tools/build.sh"
fi

if command -v open >/dev/null 2>&1; then
  open "$APP_BUNDLE"
else
  "$APP_EXEC"
fi
