#!/usr/bin/env bash
# Build a self-contained Markdown Studio.app for macOS.
#
# Nothing is installed system-wide. A standalone Python runtime and the Python
# wheels live inside the app bundle; this script only writes to .build/ and
# dist/ in the project folder.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BUILD="$ROOT/.build"
RUNTIME="$BUILD/python"
DIST="$ROOT/dist"
APP="$DIST/Markdown Studio.app"
PY_VERSION="3.12.16"
PY_RELEASE="20261026"

case "$(uname -m)" in
  arm64) PY_ASSET="aarch64" ;;
  x86_64) PY_ASSET="x86_64" ;;
  *) echo "Unsupported architecture: $(uname -m)" >&2; exit 1 ;;
esac

say() { printf '%s\n' "$*"; }

ensure_runtime() {
  if [ ! -x "$RUNTIME/bin/python3" ]; then
    say "Downloading the self-contained Python runtime…"
    mkdir -p "$BUILD"
    local url="https://github.com/astral-sh/python-build-standalone/releases/download/${PY_RELEASE}/cpython-${PY_VERSION}%2B${PY_RELEASE}-${PY_ASSET}-apple-darwin-install_only_stripped.tar.gz"
    curl -L --fail --retry 3 "$url" -o "$BUILD/python.tar.gz"
    tar -xzf "$BUILD/python.tar.gz" -C "$BUILD"
    rm -f "$BUILD/python.tar.gz"
  fi

  "$RUNTIME/bin/python3" -m pip install --quiet --upgrade pip wheel
  "$RUNTIME/bin/python3" -m pip install --quiet -r "$ROOT/requirements.txt"
  "$RUNTIME/bin/python3" - <<'PY'
import PySide6, markdown_it, pygments, linkify_it
print("runtime ready:", PySide6.__version__)
PY
}

make_icon() {
  say "Rendering the application icon…"
  rm -rf "$BUILD/icon.iconset"
  mkdir -p "$BUILD/icon.iconset"
  "$RUNTIME/bin/python3" - "$ROOT" <<'PY'
import os
import sys
from PySide6.QtCore import Qt
from PySide6.QtGui import QImage, QPainter
from PySide6.QtSvg import QSvgRenderer

root = sys.argv[1]
renderer = QSvgRenderer(os.path.join(root, "markdown-studio.svg"))
image = QImage(1024, 1024, QImage.Format.Format_ARGB32)
image.fill(Qt.GlobalColor.transparent)
painter = QPainter(image)
painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
renderer.render(painter)
painter.end()
image.save(os.path.join(root, ".build", "icon-1024.png"))
PY

  local base="$BUILD/icon-1024.png"
  local set="$BUILD/icon.iconset"
  sips -z 16 16 "$base" --out "$set/icon_16x16.png" >/dev/null
  sips -z 32 32 "$base" --out "$set/icon_16x16@2x.png" >/dev/null
  sips -z 32 32 "$base" --out "$set/icon_32x32.png" >/dev/null
  sips -z 64 64 "$base" --out "$set/icon_32x32@2x.png" >/dev/null
  sips -z 128 128 "$base" --out "$set/icon_128x128.png" >/dev/null
  sips -z 256 256 "$base" --out "$set/icon_128x128@2x.png" >/dev/null
  sips -z 256 256 "$base" --out "$set/icon_256x256.png" >/dev/null
  sips -z 512 512 "$base" --out "$set/icon_256x256@2x.png" >/dev/null
  sips -z 512 512 "$base" --out "$set/icon_512x512.png" >/dev/null
  cp "$base" "$set/icon_512x512@2x.png"
  iconutil -c icns "$set" -o "$BUILD/MarkdownStudio.icns"
}

trim_runtime() {
  local res="$APP/Contents/Resources/runtime"
  local site="$res/lib/python3.12/site-packages"
  local py="$res/lib/python3.12"

  say "Trimming unused runtime pieces…"
  rm -rf "$py/test" "$py/idlelib" "$py/tkinter" "$py/turtledemo" \
         "$py/ensurepip" "$py/venv" "$py/lib2to3"
  rm -rf "$site/pip" "$site/setuptools" "$site/wheel" "$site/pkg_resources"
  rm -rf "$site/PySide6/Qt/qml" "$site/PySide6/Qt/translations" \
         "$site/PySide6/Qt/metatypes" "$site/PySide6/Qt/libexec" \
         "$site/PySide6/Qt/lib/cmake" "$site/PySide6/Qt/lib/pkgconfig"
  rm -rf "$site/PySide6/include" "$site/PySide6/typesystems" \
         "$site/PySide6/scripts" "$site/PySide6/support"
  rm -rf "$site/PySide6/Assistant.app" "$site/PySide6/Designer.app" \
         "$site/PySide6/Linguist.app" "$site/PySide6/qmlls" \
         "$site/PySide6/qmlformat" "$site/PySide6/lupdate" \
         "$site/PySide6/lrelease" "$site/PySide6/designer"
  find "$site/PySide6" -name '*.pyi' -delete 2>/dev/null || true

  # Only the Python Qt modules this app can import are needed.
  local module
  for module in "$site"/PySide6/Qt*.abi3.so; do
    [ -e "$module" ] || continue
    case "$(basename "$module")" in
      QtCore.abi3.so|QtGui.abi3.so|QtWidgets.abi3.so|QtNetwork.abi3.so|\
      QtWebChannel.abi3.so|QtWebEngineCore.abi3.so|QtWebEngineWidgets.abi3.so|\
      QtSvg.abi3.so|QtSvgWidgets.abi3.so|QtOpenGL.abi3.so|\
      QtOpenGLWidgets.abi3.so|QtPrintSupport.abi3.so|QtQml.abi3.so|\
      QtQmlCore.abi3.so|QtQmlMeta.abi3.so|QtQmlNetwork.abi3.so|\
      QtQuick.abi3.so|QtQuickWidgets.abi3.so|QtPositioning.abi3.so|\
      QtConcurrent.abi3.so|QtXml.abi3.so|QtDBus.abi3.so)
        ;;
      *) rm -f "$module" ;;
    esac
  done

  local lib="$site/PySide6/Qt/lib"
  (
    cd "$lib"
    # Opt-in frameworks only; everything else here belongs to features this
    # editor does not use (3D, charts, multimedia, QML controls, …).
    rm -rf Qt3D* QtCharts* QtDataVisualization* QtGraphs* QtDesigner* \
           QtHelp* QtSql* QtTest* QtMultimedia* QtPdf* QtQuick3D* \
           QtWebView* QtBluetooth* QtNfc* QtRemoteObjects* QtSensors* \
           QtSerialPort* QtTextToSpeech* QtLocation* QtHttpServer* \
           QtLabs* QtQuickControls2* QtQuickDialogs2* QtQuickTimeline* \
           QtQuickParticles* QtQuickTest* QtQmlCompiler* \
           QtQmlDesignSupport* QtNetworkAuth*

    # Chromium ships two names for each FFmpeg library. Keep one file and
    # point the compatibility name at it.
    local pair base real
    for pair in libavcodec.63 libavformat.63 libavutil.61 libswresample.7 libswscale.10; do
      real="$(ls ${pair}.*.dylib 2>/dev/null | grep -v "^${pair}\.dylib$" | head -1 || true)"
      if [ -n "$real" ]; then
        rm -f "${pair}.dylib"
        ln -s "$(basename "$real")" "${pair}.dylib"
      fi
    done

    local engine="QtWebEngineCore.framework"
    if [ -d "$engine/Versions/A/Resources" ]; then
      rm -f "$engine/Versions/A/Resources/qtwebengine_devtools_resources.pak"
      find "$engine/Versions/A/Resources/qtwebengine_locales" -type f \
        ! -name 'en-US.pak' ! -name 'en-GB.pak' -delete 2>/dev/null || true
    fi
    if [ -d "$engine/Resources" ]; then
      rm -f "$engine/Resources/qtwebengine_devtools_resources.pak"
      find "$engine/Resources/qtwebengine_locales" -type f \
        ! -name 'en-US.pak' ! -name 'en-GB.pak' -delete 2>/dev/null || true
    fi
  )
}

write_plist() {
  cat > "$APP/Contents/Info.plist" <<'PLIST'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleName</key>
  <string>Markdown Studio</string>
  <key>CFBundleDisplayName</key>
  <string>Markdown Studio</string>
  <key>CFBundleIdentifier</key>
  <string>io.github.markdownstudio.MarkdownStudio</string>
  <key>CFBundleExecutable</key>
  <string>Markdown Studio</string>
  <key>CFBundlePackageType</key>
  <string>APPL</string>
  <key>CFBundleSignature</key>
  <string>????</string>
  <key>CFBundleVersion</key>
  <string>2.0</string>
  <key>CFBundleShortVersionString</key>
  <string>2.0</string>
  <key>CFBundleIconFile</key>
  <string>MarkdownStudio</string>
  <key>CFBundleDevelopmentRegion</key>
  <string>en</string>
  <key>LSMinimumSystemVersion</key>
  <string>14.0</string>
  <key>LSApplicationCategoryType</key>
  <string>public.app-category.productivity</string>
  <key>NSHighResolutionCapable</key>
  <true/>
  <key>NSSupportsAutomaticGraphicsSwitching</key>
  <true/>
  <key>NSRequiresAquaSystemAppearance</key>
  <false/>
  <key>NSSupportsSuddenTermination</key>
  <true/>
  <key>LSMultipleInstancesProhibited</key>
  <true/>
  <key>NSHumanReadableCopyright</key>
  <string>Copyright © 2026 Markdown Studio. MIT License.</string>
  <key>CFBundleDocumentTypes</key>
  <array>
    <dict>
      <key>CFBundleTypeName</key>
      <string>Markdown Document</string>
      <key>CFBundleTypeRole</key>
      <string>Editor</string>
      <key>LSHandlerRank</key>
      <string>Default</string>
      <key>LSItemContentTypes</key>
      <array>
        <string>net.daringfireball.markdown</string>
      </array>
      <key>CFBundleTypeExtensions</key>
      <array>
        <string>md</string>
        <string>markdown</string>
        <string>mdown</string>
        <string>mkd</string>
      </array>
    </dict>
    <dict>
      <key>CFBundleTypeName</key>
      <string>Plain Text Document</string>
      <key>CFBundleTypeRole</key>
      <string>Editor</string>
      <key>LSHandlerRank</key>
      <string>Alternate</string>
      <key>LSItemContentTypes</key>
      <array>
        <string>public.plain-text</string>
      </array>
      <key>CFBundleTypeExtensions</key>
      <array>
        <string>txt</string>
      </array>
    </dict>
  </array>
  <key>UTImportedTypeDeclarations</key>
  <array>
    <dict>
      <key>UTTypeIdentifier</key>
      <string>net.daringfireball.markdown</string>
      <key>UTTypeDescription</key>
      <string>Markdown Document</string>
      <key>UTTypeConformsTo</key>
      <array>
        <string>public.plain-text</string>
      </array>
      <key>UTTypeTagSpecification</key>
      <dict>
        <key>public.filename-extension</key>
        <array>
          <string>md</string>
          <string>markdown</string>
          <string>mdown</string>
          <string>mkd</string>
        </array>
        <key>public.mime-type</key>
        <string>text/markdown</string>
      </dict>
    </dict>
  </array>
</dict>
</plist>
PLIST
}

build_app() {
  ensure_runtime
  make_icon

  say "Assembling Markdown Studio.app…"
  rm -rf "$APP"
  mkdir -p "$APP/Contents/MacOS" "$APP/Contents/Resources"

  ditto "$RUNTIME" "$APP/Contents/Resources/runtime"
  cp "$ROOT/app.py" "$APP/Contents/Resources/app.py"
  cp "$ROOT/markdown-studio.svg" "$APP/Contents/Resources/markdown-studio.svg"
  cp "$ROOT/LICENSE" "$APP/Contents/Resources/LICENSE"
  cp "$BUILD/MarkdownStudio.icns" "$APP/Contents/Resources/MarkdownStudio.icns"
  ditto "$ROOT/assets" "$APP/Contents/Resources/assets"

  cat > "$APP/Contents/MacOS/Markdown Studio" <<'LAUNCHER'
#!/bin/bash
DIR="$(cd "$(dirname "$0")" && pwd)"
export PYTHONNOUSERSITE=1
exec "$DIR/../Resources/runtime/bin/python3" "$DIR/../Resources/app.py" "$@"
LAUNCHER
  chmod +x "$APP/Contents/MacOS/Markdown Studio"

  write_plist
  trim_runtime
  xattr -cr "$APP" 2>/dev/null || true

  say ""
  say "Built: $APP"
  say "Size:  $(du -sh "$APP" | cut -f1)"
  say ""
  say "Run it with:"
  say "  open \"$APP\""
}

build_app
