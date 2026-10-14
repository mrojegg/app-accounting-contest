#!/bin/zsh
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
INTERNAL_DIR="$ROOT_DIR/Internal_DO_NOT_DELETE"
APP_DIR="$INTERNAL_DIR/app_source/native_app"
BUILD_DIR="$ROOT_DIR/Build"
APP_BUNDLE="$BUILD_DIR/Сортировка документов.app"
DMG_BUNDLE="$ROOT_DIR/Dist/Сортировка документов.dmg"
: "${SORTING_PYTHON_HOME:?Set SORTING_PYTHON_HOME to a relocatable CPython distribution}"
PYTHON_DEPS="${SORTING_PYTHON_DEPS:-$BUILD_DIR/python-runtime-deps}"

echo "==> Tests"
(
  cd "$ROOT_DIR"
  PYTHONPATH="$BUILD_DIR/python-test-deps:$PYTHON_DEPS" "$SORTING_PYTHON_HOME/bin/python3" -B -m unittest discover -s 'Internal_DO_NOT_DELETE/tests' -p 'test_*.py'
)
(
  cd "$APP_DIR"
  swift test --scratch-path "$BUILD_DIR/native_app/.build-tests"
)

echo "==> App"
(
  cd "$APP_DIR"
  zsh ./build_app.sh
)

echo "==> Package"
(
  cd "$ROOT_DIR/Internal_DO_NOT_DELETE/tools"
  zsh ./package_dmg.sh >/dev/null
)

INSTALL_APP_PATH="${INSTALL_APP_PATH:-}"
if [[ -n "$INSTALL_APP_PATH" ]]; then
  echo "==> Install"
  if [[ "$INSTALL_APP_PATH" != /*.app || "$INSTALL_APP_PATH" == "$APP_BUNDLE" ]]; then
    echo "INSTALL_APP_PATH must be a separate absolute .app path" >&2
    exit 2
  fi
  codesign --verify --deep --strict "$APP_BUNDLE"
  STAGED_APP="${INSTALL_APP_PATH%.app}.staged.app"
  if [[ -e "$STAGED_APP" ]]; then
    echo "Staged app already exists: $STAGED_APP" >&2
    exit 2
  fi
  ditto "$APP_BUNDLE" "$STAGED_APP"
  codesign --verify --deep --strict "$STAGED_APP"
  rm -rf "$INSTALL_APP_PATH"
  mv "$STAGED_APP" "$INSTALL_APP_PATH"
  echo "Installed:"
  echo "$INSTALL_APP_PATH"
fi

echo
echo "Ready:"
echo "$APP_BUNDLE"
echo "$DMG_BUNDLE"
