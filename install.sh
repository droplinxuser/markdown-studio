#!/usr/bin/env bash
# Install Markdown Studio for the current user (no root required).
set -euo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
app_dir="$HOME/.local/opt/markdown-studio"
bin_dir="$HOME/.local/bin"
apps_dir="${XDG_DATA_HOME:-$HOME/.local/share}/applications"
icons_dir="${XDG_DATA_HOME:-$HOME/.local/share}/icons/hicolor/scalable/apps"

mkdir -p "$app_dir" "$bin_dir" "$apps_dir" "$icons_dir"
cp "$here/app.py" "$app_dir/app.py"
cp "$here/markdown-studio.svg" "$app_dir/markdown-studio.svg"
cp "$here/markdown-studio.svg" "$icons_dir/markdown-studio.svg"

cat > "$bin_dir/markdown-studio" <<LAUNCHER
#!/usr/bin/env bash
exec /usr/bin/python3 "$app_dir/app.py" "\$@"
LAUNCHER
chmod +x "$bin_dir/markdown-studio"

sed "s|@EXEC@|$bin_dir/markdown-studio|g" "$here/markdown-studio.desktop" \
  > "$apps_dir/markdown-studio.desktop"

command -v update-desktop-database >/dev/null 2>&1 && update-desktop-database "$apps_dir" >/dev/null 2>&1 || true
command -v gtk-update-icon-cache >/dev/null 2>&1 && gtk-update-icon-cache -f -t "${XDG_DATA_HOME:-$HOME/.local/share}/icons/hicolor" >/dev/null 2>&1 || true

echo "Markdown Studio installed."
echo "  launch:  markdown-studio [file.md]"
echo "  menu:    search for \"Markdown Studio\""
