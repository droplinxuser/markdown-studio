#!/usr/bin/env bash
# Uninstall Markdown Studio for the current user (no root required).
set -euo pipefail

app_dir="$HOME/.local/opt/markdown-studio"
bin_dir="$HOME/.local/bin"
apps_dir="${XDG_DATA_HOME:-$HOME/.local/share}/applications"
icons_dir="${XDG_DATA_HOME:-$HOME/.local/share}/icons/hicolor/scalable/apps"

# Drop Markdown Studio from the Markdown handler lists, preserving any other
# handlers that share a line, so the next editor installed can take over
# cleanly and no dangling association is left behind.
mimeapps="${XDG_CONFIG_HOME:-$HOME/.config}/mimeapps.list"
if [ -f "$mimeapps" ]; then
  python3 - "$mimeapps" <<'PY'
import re
import sys

path = sys.argv[1]
pattern = re.compile(r"^(\s*text/markdown\s*=\s*)(.*)$")
with open(path, encoding="utf-8") as handle:
    lines = handle.readlines()
out = []
changed = False
for line in lines:
    match = pattern.match(line)
    if not match:
        out.append(line)
        continue
    handlers = [item.strip() for item in match.group(2).split(";") if item.strip()]
    kept = [item for item in handlers if item != "markdown-studio.desktop"]
    if kept == handlers:
        out.append(line)
        continue
    changed = True
    if kept:
        out.append(match.group(1) + ";".join(kept) + ";\n")
if changed:
    with open(path, "w", encoding="utf-8") as handle:
        handle.writelines(out)
PY
fi

rm -f "$bin_dir/markdown-studio"
rm -f "$apps_dir/markdown-studio.desktop"
rm -f "$icons_dir/markdown-studio.svg"
rm -rf "$app_dir"

command -v update-desktop-database >/dev/null 2>&1 && update-desktop-database "$apps_dir" >/dev/null 2>&1 || true
command -v gtk-update-icon-cache >/dev/null 2>&1 && gtk-update-icon-cache -f -t "${XDG_DATA_HOME:-$HOME/.local/share}/icons/hicolor" >/dev/null 2>&1 || true

echo "Markdown Studio uninstalled."
