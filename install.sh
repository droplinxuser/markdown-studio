#!/usr/bin/env bash
# Install Markdown Studio for the current macOS user (no root, no system packages).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SRC="$ROOT/dist/Markdown Studio.app"
DEST="$HOME/Applications/Markdown Studio.app"
LSREGISTER="/System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister"

needs_build=0
if [ ! -d "$SRC" ]; then
  needs_build=1
else
  for file in "$ROOT/app.py" "$ROOT/requirements.txt" "$ROOT/build_macos.sh" \
              "$ROOT/markdown-studio.svg"; do
    if [ "$file" -nt "$SRC" ]; then
      needs_build=1
      break
    fi
  done
  if [ -d "$ROOT/assets/toolbar" ] && [ "$ROOT/assets/toolbar" -nt "$SRC" ]; then
    needs_build=1
  fi
fi

if [ "$needs_build" = "1" ]; then
  "$ROOT/build_macos.sh"
fi

echo "Installing to $DEST"
mkdir -p "$HOME/Applications"
rm -rf "$DEST"
ditto "$SRC" "$DEST"
xattr -cr "$DEST" 2>/dev/null || true

if [ -x "$LSREGISTER" ]; then
  "$LSREGISTER" -f "$DEST" >/dev/null 2>&1 || true
fi

# A tiny command-line launcher. It uses Launch Services so files open in the
# already-running app instead of starting a second copy.
mkdir -p "$HOME/.local/bin"
cat > "$HOME/.local/bin/markdown-studio" <<LAUNCHER
#!/bin/bash
exec open -a "$DEST" "\$@"
LAUNCHER
chmod +x "$HOME/.local/bin/markdown-studio"

echo ""
echo "Markdown Studio installed."
echo "  app:      $DEST"
echo "  launch:   open -a \"$DEST\""
echo "  CLI:      $HOME/.local/bin/markdown-studio [file.md]"
echo ""
echo "To make it the default Markdown editor, select a .md file in Finder,"
echo "choose File > Get Info > Open With > Markdown Studio, then Change All."
