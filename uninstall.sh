#!/usr/bin/env bash
# Uninstall Markdown Studio for the current user (no root required).
set -euo pipefail

app_dir="$HOME/.local/opt/markdown-studio"
bin_dir="$HOME/.local/bin"
apps_dir="${XDG_DATA_HOME:-$HOME/.local/share}/applications"
icons_dir="${XDG_DATA_HOME:-$HOME/.local/share}/icons/hicolor/scalable/apps"

# If Markdown Studio is still the default handler for Markdown, drop that
# association so the next editor installed can take over cleanly.
if command -v xdg-mime >/dev/null 2>&1; then
  if [ "$(xdg-mime query default text/markdown 2>/dev/null || true)" = "markdown-studio.desktop" ]; then
    mimeapps="${XDG_CONFIG_HOME:-$HOME/.config}/mimeapps.list"
    if [ -f "$mimeapps" ]; then
      python3 - "$mimeapps" <<'PY'
import re
import sys

path = sys.argv[1]
pattern = re.compile(r"^\s*text/markdown\s*=\s*markdown-studio\.desktop\s*;?\s*$")
with open(path, encoding="utf-8") as handle:
    lines = handle.readlines()
kept = [line for line in lines if not pattern.match(line)]
if kept != lines:
    with open(path, "w", encoding="utf-8") as handle:
        handle.writelines(kept)
PY
    fi
  fi
fi

rm -f "$bin_dir/markdown-studio"
rm -f "$apps_dir/markdown-studio.desktop"
rm -f "$icons_dir/markdown-studio.svg"
rm -rf "$app_dir"

command -v update-desktop-database >/dev/null 2>&1 && update-desktop-database "$apps_dir" >/dev/null 2>&1 || true
command -v gtk-update-icon-cache >/dev/null 2>&1 && gtk-update-icon-cache -f -t "${XDG_DATA_HOME:-$HOME/.local/share}/icons/hicolor" >/dev/null 2>&1 || true

echo "Markdown Studio uninstalled."
