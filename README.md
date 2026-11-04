# Markdown Studio

A small, fast Markdown editor for macOS. The window is split in half: a
toolbar-driven editor on the left and a live preview on the right.

![Markdown Studio](docs/screenshot.png)

## Features

- Split view: Markdown editor with a formatting toolbar, live preview beside it.
- Tabs for multiple open files, with a close button on every tab. Open several
  files at once from the file chooser, the command line, Finder, or by dragging
  them onto the window.
- Automatic saving of named files while you type, plus a save-on-close pass so
  an accidental close does not lose changes.
- Spelling and grammar review through LanguageTool (online; optional and only
  runs when you choose **Tools → Check Spelling & Grammar**). Suspected words
  are underlined in the editor, and applying one suggestion refreshes the
  review in place instead of closing it.
- Live preview with GitHub-style typography, tables, task lists, syntax
  highlighting (Pygments) and local/remote images.
- Toolbar for bold, italic, strikethrough, inline code, headings, quotes, lists,
  task lists, links, images, tables, code blocks and horizontal rules. The
  toolbar uses native SF Symbols, so it sits comfortably beside the rest of
  macOS.
- Keyboard shortcuts for everything you do often, using the standard macOS
  Command and Control conventions.
- Undo/redo with sensible grouping.
- Open, save, save-as and export to a standalone HTML file.
- Drag a `.md` file onto the window to open it.
- Automatic light/dark appearance for the whole window and preview, following
  the macOS appearance setting.
- Responsive layout: the toolbar collapses into an overflow menu when the
  window is narrow, tabs scroll when needed, and the editor/preview split stays
  proportional as the window resizes.
- Scroll position is mirrored from the editor to the preview.
- Word, character and line counts, plus cursor position.

## Requirements

- macOS 14 or later (Apple silicon or Intel).
- Nothing else. The app bundle carries its own Python and Qt runtime, so it does
  not install Homebrew packages, Python packages, or anything else into the
  system.

## Install

```bash
./install.sh
```

This builds `dist/Markdown Studio.app` if needed, copies it to
`~/Applications/Markdown Studio.app`, registers it with Launch Services, and
adds a small `markdown-studio` command in `~/.local/bin` (add that folder to
your `PATH` if you want the command everywhere).

To make Markdown Studio the default Markdown editor, select a `.md` file in
Finder, choose **File → Get Info**, pick **Markdown Studio** under **Open
with**, then click **Change All**.

## Uninstall

```bash
./uninstall.sh            # remove the app and command
./uninstall.sh --purge    # also remove preferences, caches and session data
```

## Run

```bash
open -a "$HOME/Applications/Markdown Studio.app"   # welcome document
markdown-studio notes.md                           # open a file
markdown-studio a.md b.md                          # several files in tabs
open "dist/Markdown Studio.app"                    # run the built bundle directly
```

## Shortcuts

| Action | Shortcut |
| --- | --- |
| New / Open / Save / Save As | `⌘N` / `⌘O` / `⌘S` / `⇧⌘S` |
| Close tab | `⌘W` |
| Next / previous tab | `⌃⇥` / `⌃⇧⇥` |
| Export as HTML | `⇧⌘E` |
| Check spelling & grammar | `⇧⌘G` |
| Undo / Redo | `⌘Z` / `⇧⌘Z` |
| Bold / Italic / Strikethrough | `⌘B` / `⌘I` / `⇧⌘X` |
| Inline code / Code block | `⌘E` / `⇧⌘C` |
| Link / Image | `⌘K` / `⇧⌘I` |
| Heading 1 / 2 / 3 | `⌘1` / `⌘2` / `⌘3` |
| Bulleted / Numbered / Task list | `⇧⌘8` / `⇧⌘7` (task via toolbar) |
| Block quote | `⇧⌘9` |
| Toggle preview | `⇧⌘P` |
| Full screen | `⌃⌘F` or `F11` |
| Quit | `⌘Q` |

## Notes

- Raw HTML in a document is escaped, not executed.
- Clicking an `http(s)` link opens it in your browser; clicking a link to a local
  Markdown file opens that file in the editor.
- Relative image paths resolve against the document's folder.
- The preview is rendered by Qt WebEngine with a small GitHub-flavoured
  stylesheet; code blocks are highlighted by Pygments.
- Saves are atomic: the document is written to a temporary file and renamed
  into place, so a crash or power loss cannot leave a truncated file.
- Named files are auto-saved after a short pause in typing. Untitled documents
  still ask where to save when you close them.
- Spelling and grammar checks send the document text to
  `api.languagetool.org` only when you run the check. Set
  `MARKDOWN_STUDIO_GRAMMAR_URL` and `MARKDOWN_STUDIO_GRAMMAR_LANGUAGE` to use a
  self-hosted LanguageTool server or another language.
- Light/dark mode follows the macOS appearance, and the preview and editor
  update with it immediately.
- The app is self-contained. Its runtime lives inside
  `Markdown Studio.app/Contents/Resources/runtime`; deleting the app removes
  all of it.

## Building

```bash
./build_macos.sh
```

The build script downloads a standalone CPython runtime into `.build/`, installs
the Python wheels into that private runtime, copies what the app needs into
`dist/Markdown Studio.app`, and trims the Qt modules the editor does not use.
Nothing is installed system-wide. `install.sh` calls this automatically.

## Files

| File | Purpose |
| --- | --- |
| `app.py` | the whole application |
| `markdown-studio.svg` | application icon source |
| `assets/toolbar/` | SF Symbol toolbar icons |
| `assets/generate-icons.js` | regenerates the toolbar icons on macOS |
| `requirements.txt` | pinned Python dependencies for the private runtime |
| `build_macos.sh` | builds the self-contained `.app` |
| `install.sh` | per-user installer |
| `uninstall.sh` | per-user uninstaller |
