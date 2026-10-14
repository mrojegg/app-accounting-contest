#!/bin/zsh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
BUILD_ROOT="$PROJECT_ROOT/Build"
CACHE_KEY="$(printf '%s' "$SCRIPT_DIR" | shasum | awk '{print $1}')"
SCRATCH_PATH="$BUILD_ROOT/native_app/.build-local-$CACHE_KEY"
BUILD_DIR="$SCRATCH_PATH/release"
APP_NAME="Сортировка документов (конкурс)"
FINAL_BUNDLE_PATH="$BUILD_ROOT/$APP_NAME.app"
BUNDLE_PATH="$BUILD_ROOT/.$APP_NAME.building.app"
EXECUTABLE_NAME="SortingFilesNativeApp"
EXECUTABLE_PATH="$BUILD_DIR/$EXECUTABLE_NAME"
PDF_MERGER_EXECUTABLE_PATH="$BUILD_DIR/PDFMergeHelper"
INTERNAL_RUNTIME_DIR="$PROJECT_ROOT/Internal_DO_NOT_DELETE"
OCR_PACKAGE_DIR="$INTERNAL_RUNTIME_DIR/ocr/ocr_package"
OCR_BUILD_DIR="$BUILD_ROOT/ocr_package/.build-local/release"
OCR_EXECUTABLE_PATH="$OCR_BUILD_DIR/pdf_ocr_pkg"
ICON_PATH="$SCRIPT_DIR/Resources/AppIcon.icns"
ICON_SOURCE_PATH="$SCRIPT_DIR/Resources/AppIconSource.png"
ICON_SCRIPT_PATH="$SCRIPT_DIR/Resources/generate_icon.swift"
DEFAULT_RULES_PATH="$SCRIPT_DIR/Resources/DefaultRulesTemplate.md"
PUBLIC_RULES_PATH="$PROJECT_ROOT/Internal_DO_NOT_DELETE/project_rules/sorting_rules_clean.md"
PUBLIC_MANUAL_RULES_PATH="$PROJECT_ROOT/Internal_DO_NOT_DELETE/project_rules/manual_file_rules_clean.json"
CLANG_CACHE_DIR="$BUILD_ROOT/native_app/.build-local/clang-cache-$CACHE_KEY"
SWIFTPM_CACHE_DIR="$BUILD_ROOT/native_app/.build-local/swiftpm-cache-$CACHE_KEY"

mkdir -p "$CLANG_CACHE_DIR" "$SWIFTPM_CACHE_DIR"
mkdir -p "$BUILD_ROOT"

export CLANG_MODULE_CACHE_PATH="$CLANG_CACHE_DIR"
export SWIFTPM_MODULECACHE_OVERRIDE="$CLANG_CACHE_DIR"
export XDG_CACHE_HOME="$SWIFTPM_CACHE_DIR"
export SDKROOT="${SDKROOT:-$(xcrun --show-sdk-path)}"
: "${SORTING_PYTHON_HOME:?Set SORTING_PYTHON_HOME to a relocatable CPython distribution}"
if [[ ! -x "$SORTING_PYTHON_HOME/bin/python3" || ! -d "${SORTING_PYTHON_DEPS:-$BUILD_ROOT/python-runtime-deps}/pymupdf" ]]; then
  echo "Prepare standalone Python and requirements-macos.txt dependencies first" >&2
  exit 2
fi
if [[ -e "$BUNDLE_PATH" ]]; then
  echo "Another build or incomplete staging exists: $BUNDLE_PATH" >&2
  exit 2
fi
trap 'rm -rf "$BUNDLE_PATH"' EXIT

if [[ -f "$ICON_SOURCE_PATH" || -f "$ICON_SCRIPT_PATH" ]]; then
  ICON_TMP_DIR="$BUILD_ROOT/native_app/.icon-work"
  ICONSET_DIR="$ICON_TMP_DIR/AppIcon.iconset"
  ICON_MASTER="$ICON_TMP_DIR/AppIcon-1024.png"
  rm -rf "$ICON_TMP_DIR"
  mkdir -p "$ICONSET_DIR"
  if {
    if [[ -f "$ICON_SOURCE_PATH" ]]; then
      sips -z 1024 1024 "$ICON_SOURCE_PATH" --out "$ICON_MASTER" >/dev/null
    else
      swift "$ICON_SCRIPT_PATH" "$ICON_MASTER" 1024
    fi
  } \
    && sips -z 16 16 "$ICON_MASTER" --out "$ICONSET_DIR/icon_16x16.png" >/dev/null \
    && sips -z 32 32 "$ICON_MASTER" --out "$ICONSET_DIR/icon_16x16@2x.png" >/dev/null \
    && sips -z 32 32 "$ICON_MASTER" --out "$ICONSET_DIR/icon_32x32.png" >/dev/null \
    && sips -z 64 64 "$ICON_MASTER" --out "$ICONSET_DIR/icon_32x32@2x.png" >/dev/null \
    && sips -z 128 128 "$ICON_MASTER" --out "$ICONSET_DIR/icon_128x128.png" >/dev/null \
    && sips -z 256 256 "$ICON_MASTER" --out "$ICONSET_DIR/icon_128x128@2x.png" >/dev/null \
    && sips -z 256 256 "$ICON_MASTER" --out "$ICONSET_DIR/icon_256x256.png" >/dev/null \
    && sips -z 512 512 "$ICON_MASTER" --out "$ICONSET_DIR/icon_256x256@2x.png" >/dev/null \
    && sips -z 512 512 "$ICON_MASTER" --out "$ICONSET_DIR/icon_512x512.png" >/dev/null; then
    cp "$ICON_MASTER" "$ICONSET_DIR/icon_512x512@2x.png"
    if ! iconutil -c icns "$ICONSET_DIR" -o "$ICON_PATH"; then
      echo "Icon generation failed, continuing without app icon" >&2
    fi
  else
    echo "Icon preparation failed, continuing without app icon" >&2
  fi
fi

if [[ "${SKIP_BUILD:-0}" != "1" ]]; then
  swift build --disable-sandbox --build-system native -c release --scratch-path "$SCRATCH_PATH"
  (
    cd "$OCR_PACKAGE_DIR"
    swift build --disable-sandbox --build-system native -c release --scratch-path "$BUILD_ROOT/ocr_package/.build-local"
  )
fi

rm -rf "$BUNDLE_PATH"
mkdir -p "$BUNDLE_PATH/Contents/MacOS" "$BUNDLE_PATH/Contents/Resources"

cp "$EXECUTABLE_PATH" "$BUNDLE_PATH/Contents/MacOS/$EXECUTABLE_NAME"
chmod +x "$BUNDLE_PATH/Contents/MacOS/$EXECUTABLE_NAME"

if [[ -f "$ICON_PATH" ]]; then
  cp "$ICON_PATH" "$BUNDLE_PATH/Contents/Resources/AppIcon.icns"
fi

if [[ -f "$DEFAULT_RULES_PATH" ]]; then
  cp "$DEFAULT_RULES_PATH" "$BUNDLE_PATH/Contents/Resources/default_sorting_rules.md"
fi

RUNTIME_BUNDLE_ROOT="$BUNDLE_PATH/Contents/Resources/Internal_DO_NOT_DELETE"
mkdir -p \
  "$RUNTIME_BUNDLE_ROOT/scripts" \
  "$RUNTIME_BUNDLE_ROOT/project_rules" \
  "$RUNTIME_BUNDLE_ROOT/ocr/bin" \
  "$RUNTIME_BUNDLE_ROOT/pdf/bin"

cp -R "$INTERNAL_RUNTIME_DIR/scripts/." "$RUNTIME_BUNDLE_ROOT/scripts/"
cp -R "$INTERNAL_RUNTIME_DIR/project_rules/." "$RUNTIME_BUNDLE_ROOT/project_rules/"

"$SORTING_PYTHON_HOME/bin/python3" "$INTERNAL_RUNTIME_DIR/tools/prepare_python_runtime.py" \
  --source "$SORTING_PYTHON_HOME" \
  --dependencies "${SORTING_PYTHON_DEPS:-$BUILD_ROOT/python-runtime-deps}" \
  --output "$RUNTIME_BUNDLE_ROOT/python-runtime"

find "$RUNTIME_BUNDLE_ROOT" -name ".DS_Store" -delete
find "$RUNTIME_BUNDLE_ROOT" -name "__pycache__" -type d -prune -exec rm -rf {} +
find "$RUNTIME_BUNDLE_ROOT" -name "*.pyc" -delete
rm -f "$RUNTIME_BUNDLE_ROOT/scripts/fix_salary_offices.py"

if [[ -f "$PUBLIC_RULES_PATH" ]]; then
  cp "$PUBLIC_RULES_PATH" "$RUNTIME_BUNDLE_ROOT/project_rules/sorting_rules.md"
fi

if [[ -f "$PUBLIC_MANUAL_RULES_PATH" ]]; then
  cp "$PUBLIC_MANUAL_RULES_PATH" "$RUNTIME_BUNDLE_ROOT/project_rules/manual_file_rules.json"
fi

if [[ -x "$OCR_EXECUTABLE_PATH" ]]; then
  cp "$OCR_EXECUTABLE_PATH" "$RUNTIME_BUNDLE_ROOT/ocr/bin/pdf_ocr_pkg"
  chmod +x "$RUNTIME_BUNDLE_ROOT/ocr/bin/pdf_ocr_pkg"
fi

if [[ -x "$PDF_MERGER_EXECUTABLE_PATH" ]]; then
  cp "$PDF_MERGER_EXECUTABLE_PATH" "$RUNTIME_BUNDLE_ROOT/pdf/bin/pdf_merge_helper"
  chmod +x "$RUNTIME_BUNDLE_ROOT/pdf/bin/pdf_merge_helper"
fi

cat > "$BUNDLE_PATH/Contents/Info.plist" <<'PLIST'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleDevelopmentRegion</key>
    <string>ru</string>
    <key>CFBundleExecutable</key>
    <string>SortingFilesNativeApp</string>
    <key>CFBundleIdentifier</key>
    <string>local.codex.sortingfiles.contest</string>
    <key>CFBundleInfoDictionaryVersion</key>
    <string>6.0</string>
    <key>CFBundleIconFile</key>
    <string>AppIcon</string>
    <key>CFBundleName</key>
    <string>Сортировка документов (конкурс)</string>
    <key>CFBundlePackageType</key>
    <string>APPL</string>
    <key>CFBundleShortVersionString</key>
    <string>1.0</string>
    <key>CFBundleVersion</key>
    <string>1</string>
    <key>LSMinimumSystemVersion</key>
    <string>13.0</string>
    <key>NSHighResolutionCapable</key>
    <true/>
    <key>NSPrincipalClass</key>
    <string>NSApplication</string>
</dict>
</plist>
PLIST

touch "$BUNDLE_PATH/Contents/PkgInfo"
echo -n "APPL????" > "$BUNDLE_PATH/Contents/PkgInfo"

/usr/libexec/PlistBuddy -c "Set :CFBundleShortVersionString ${APP_VERSION:-1.2.0}" "$BUNDLE_PATH/Contents/Info.plist"
/usr/libexec/PlistBuddy -c "Set :CFBundleVersion ${APP_BUILD:-$(date -u +%Y%m%d%H%M)}" "$BUNDLE_PATH/Contents/Info.plist"
codesign --force --deep --sign - "$BUNDLE_PATH"
codesign --verify --deep --strict "$BUNDLE_PATH"
rm -rf "$FINAL_BUNDLE_PATH"
mv "$BUNDLE_PATH" "$FINAL_BUNDLE_PATH"

echo "$FINAL_BUNDLE_PATH"
