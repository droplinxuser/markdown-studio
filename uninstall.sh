#!/usr/bin/env bash
# Uninstall Markdown Studio for the current macOS user.
set -euo pipefail

APP="$HOME/Applications/Markdown Studio.app"
CLI="$HOME/.local/bin/markdown-studio"

rm -rf "$APP"
rm -f "$CLI"

if [ "${1:-}" = "--purge" ]; then
  rm -f "$HOME/Library/Preferences/com.github-com-markdownstudio.Markdown Studio.plist"
  rm -rf "$HOME/Library/Saved Application State/io.github.markdownstudio.MarkdownStudio.savedState"
  rm -rf "$HOME/Library/Caches/io.github.markdownstudio.MarkdownStudio"
  rm -rf "$HOME/Library/Application Support/Markdown Studio"
fi

echo "Markdown Studio uninstalled."
if [ "${1:-}" != "--purge" ]; then
  echo "Preferences were kept. Run ./uninstall.sh --purge to remove them too."
fi
