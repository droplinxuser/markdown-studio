#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Markdown Studio — a small, fast Markdown editor for the Linux desktop.

Layout: toolbar + editor on the left, live preview on the right.
Renderer: markdown-it-py + Pygments. Preview: WebKitGTK.

Dependencies (all shipped with Ubuntu): python3-gi, gir1.2-gtk-3.0,
gir1.2-handy-1, gir1.2-webkit2-4.1, python3-markdown-it, python3-pygments.
"""

import html
import json
import os
import re
import sys
import tempfile

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
gi.require_version("Handy", "1")
gi.require_version("WebKit2", "4.1")

from gi.repository import Gdk, GdkPixbuf, Gio, GLib, Gtk, Handy, Pango, WebKit2

from markdown_it import MarkdownIt
from pygments import highlight as pygments_highlight
from pygments.formatters import HtmlFormatter
from pygments.lexers import get_lexer_by_name
from pygments.util import ClassNotFound

APP_ID = "io.github.markdownstudio.MarkdownStudio"
APP_NAME = "Markdown Studio"
APP_VERSION = "1.0"
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ICON_PATH = os.path.join(BASE_DIR, "markdown-studio.svg")

WELCOME = """# Welcome to Markdown Studio

A quiet place to write Markdown, with a live preview that updates as you type.

## The basics

- Write on the left, watch the result on the right.
- Use the **toolbar** above the editor, or the keyboard shortcuts, to format.
- Press **Ctrl+S** to save and **Ctrl+O** to open a file.
- Drag a `.md` file onto the window to open it.

> Good writing is clear thinking made visible.

## Try the formatting

Select some text and press **Ctrl+B** for bold, **Ctrl+I** for italic, or
**Ctrl+K** to turn it into a link. Headings are **Ctrl+1**, **Ctrl+2** and
**Ctrl+3**.

```python
def greet(name):
    return f"Hello, {name}!"

print(greet("writer"))
```

| Shortcut | Action        |
| -------- | ------------- |
| Ctrl+B   | Bold          |
| Ctrl+I   | Italic        |
| Ctrl+K   | Insert link   |
| Ctrl+E   | Inline code   |

- [x] Open the app
- [ ] Write something worth keeping
- [ ] Export it as HTML
"""

PREVIEW_CSS = r"""
body {
  margin: 0;
  font-family: "Ubuntu", "Cantarell", "Inter", system-ui, sans-serif;
  font-size: 16px;
  line-height: 1.65;
  -webkit-font-smoothing: antialiased;
}
body.theme-light {
  --bg: #ffffff;
  --fg: #1f2328;
  --muted: #5b6570;
  --border: #d8dee4;
  --accent: #0969da;
  --code-bg: #f6f8fa;
  --inline-bg: rgba(129, 139, 152, 0.14);
  --stripe: rgba(0, 0, 0, 0.025);
  --selection: #b6d7ff;
  --scrollbar: #c6ced8;
  --mark: #fff3b8;
  background: var(--bg);
  color: var(--fg);
}
body.theme-dark {
  --bg: #0d1117;
  --fg: #e6edf3;
  --muted: #9198a1;
  --border: #30363d;
  --accent: #4c9aff;
  --code-bg: #151b23;
  --inline-bg: rgba(110, 118, 129, 0.28);
  --stripe: rgba(255, 255, 255, 0.025);
  --selection: #264f78;
  --scrollbar: #3d444d;
  --mark: #4b3f00;
  background: var(--bg);
  color: var(--fg);
}
* { box-sizing: border-box; }
article {
  max-width: 860px;
  margin: 0 auto;
  padding: 42px 48px 160px;
  overflow-wrap: break-word;
}
article > :first-child { margin-top: 0; }
h1, h2, h3, h4, h5, h6 {
  margin: 1.7em 0 0.65em;
  font-weight: 600;
  line-height: 1.3;
  letter-spacing: -0.012em;
}
h1 { font-size: 2em; padding-bottom: 0.3em; border-bottom: 1px solid var(--border); }
h2 { font-size: 1.5em; padding-bottom: 0.25em; border-bottom: 1px solid var(--border); }
h3 { font-size: 1.22em; }
h4 { font-size: 1.05em; }
h5 { font-size: 0.95em; }
h6 { font-size: 0.9em; color: var(--muted); }
p, ul, ol, dl, blockquote, table, pre, details { margin: 0 0 1.05em; }
a { color: var(--accent); text-decoration: none; }
a:hover { text-decoration: underline; }
strong { font-weight: 600; }
ul, ol { padding-left: 1.65em; }
li > ul, li > ol { margin: 0.3em 0 0.3em; }
li + li { margin-top: 0.25em; }
li.task-item { list-style: none; margin-left: -1.45em; }
li.task-item input {
  margin: 0 0.55em 0 0;
  width: 0.95em;
  height: 0.95em;
  vertical-align: -0.08em;
  accent-color: var(--accent);
}
blockquote {
  margin-left: 0;
  padding: 0.15em 0 0.15em 1.15em;
  border-left: 3px solid var(--border);
  color: var(--muted);
}
blockquote > :last-child { margin-bottom: 0; }
code {
  font-family: "Ubuntu Mono", "JetBrains Mono", "DejaVu Sans Mono", monospace;
  font-size: 0.875em;
  background: var(--inline-bg);
  padding: 0.18em 0.38em;
  border-radius: 5px;
}
pre {
  background: var(--code-bg);
  border: 1px solid var(--border);
  border-radius: 9px;
  padding: 15px 18px;
  overflow: auto;
  line-height: 1.5;
}
pre.highlight { background: var(--code-bg); border: 1px solid var(--border); }
pre code {
  background: none;
  padding: 0;
  border-radius: 0;
  font-size: 0.855em;
}
table {
  border-collapse: collapse;
  display: block;
  width: max-content;
  max-width: 100%;
  overflow: auto;
}
th, td { border: 1px solid var(--border); padding: 7px 14px; }
th { font-weight: 600; background: var(--code-bg); text-align: left; }
tr:nth-child(2n) td { background: var(--stripe); }
img { max-width: 100%; height: auto; border-radius: 7px; }
hr { height: 1px; border: 0; background: var(--border); margin: 2em 0; }
kbd {
  font-family: "Ubuntu Mono", "DejaVu Sans Mono", monospace;
  font-size: 0.8em;
  padding: 0.12em 0.45em;
  border: 1px solid var(--border);
  border-bottom-width: 2px;
  border-radius: 5px;
  background: var(--code-bg);
}
mark { background: var(--mark); color: inherit; border-radius: 3px; padding: 0 0.15em; }
del { color: var(--muted); }
::selection { background: var(--selection); }
::-webkit-scrollbar { width: 11px; height: 11px; }
::-webkit-scrollbar-thumb {
  background: var(--scrollbar);
  border: 3px solid var(--bg);
  border-radius: 7px;
}
::-webkit-scrollbar-track { background: transparent; }
@media print {
  article { padding: 0; max-width: none; }
  pre, table { page-break-inside: avoid; }
}
"""

PREVIEW_JS = r"""
function setContent(markup) {
  document.getElementById('content').innerHTML = markup;
}
function setTheme(dark) {
  document.body.className = dark ? 'theme-dark' : 'theme-light';
}
function setScrollRatio(ratio) {
  var max = document.documentElement.scrollHeight - window.innerHeight;
  window.scrollTo(0, Math.max(0, Math.min(1, ratio)) * max);
}
"""

# ---------------------------------------------------------------- markdown ---

_md = MarkdownIt(
    "commonmark",
    {"html": False, "linkify": True, "typographer": True, "breaks": False},
)
_md.enable(["table", "strikethrough", "linkify"])

_TASK_RE = re.compile(r"<li>\s*\[([ xX])\]\s+")


def _highlight_code(code, lang, _attrs):
    lexer = None
    if lang:
        try:
            lexer = get_lexer_by_name(lang, stripall=False)
        except ClassNotFound:
            lexer = None
    if lexer is None:
        body = html.escape(code)
    else:
        body = pygments_highlight(code, lexer, HtmlFormatter(nowrap=True))
    return '<pre class="highlight"><code>%s</code></pre>' % body


_md.options["highlight"] = _highlight_code


def render_markdown(text):
    """Render Markdown to a safe HTML fragment (raw HTML is escaped)."""
    out = _md.render(text)
    return _TASK_RE.sub(
        lambda m: '<li class="task-item"><input type="checkbox" disabled%s> '
        % (" checked" if m.group(1).lower() == "x" else ""),
        out,
    )


def _pygments_css(style, prefix):
    return HtmlFormatter(style=style, nowrap=True).get_style_defs(prefix)


def _style_block():
    return (
        _pygments_css("friendly", "body.theme-light .highlight")
        + "\n"
        + _pygments_css("github-dark", "body.theme-dark .highlight")
        + "\n"
        + PREVIEW_CSS
    )


def build_preview_shell():
    return (
        "<!DOCTYPE html><html><head><meta charset=\"utf-8\">"
        "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">"
        "<style>" + _style_block() + "</style></head>"
        "<body class=\"theme-light\"><article id=\"content\"></article>"
        "<script>" + PREVIEW_JS + "</script></body></html>"
    )


def build_export_html(title, text):
    body = render_markdown(text)
    return (
        "<!DOCTYPE html><html><head><meta charset=\"utf-8\">"
        "<title>%s</title><style>%s</style></head>"
        "<body class=\"theme-light\"><article>%s</article></body></html>"
        % (html.escape(title), _style_block(), body)
    )


# ------------------------------------------------------------------- gtk -----

APP_CSS = b"""
.formatbar {
  background: @theme_bg_color;
  border-bottom: 1px solid alpha(@theme_fg_color, 0.10);
}
.formatbar flowboxchild { padding: 0; }
button.tool {
  min-height: 26px;
  min-width: 22px;
  padding: 3px 5px;
  border-radius: 6px;
  border: none;
  background: transparent;
  box-shadow: none;
  color: alpha(@theme_fg_color, 0.86);
}
button.tool:hover {
  background: alpha(@theme_fg_color, 0.09);
  color: @theme_fg_color;
}
button.tool:active, button.tool:checked {
  background: alpha(@theme_selected_bg_color, 0.22);
  color: @theme_selected_bg_color;
}
button.hlabel {
  font-weight: 700;
  font-size: 11px;
  padding: 4px 7px;
  letter-spacing: 0.02em;
}
button.glyph {
  font-size: 13px;
  font-weight: 600;
  padding: 3px 6px;
}
button.glyph.mono {
  font-family: "Ubuntu Mono", "DejaVu Sans Mono", monospace;
  font-size: 11px;
  font-weight: 600;
  letter-spacing: -0.04em;
}
.editor-view {
  font-family: "Ubuntu Mono", "JetBrains Mono", "DejaVu Sans Mono", monospace;
  font-size: 14px;
  background: @theme_base_color;
}
.statusbar {
  border-top: 1px solid alpha(@theme_fg_color, 0.10);
  background: @theme_bg_color;
}
.statusbar label {
  font-size: 11px;
  color: alpha(@theme_fg_color, 0.62);
}
paned > separator {
  min-width: 1px;
  min-height: 1px;
  background: alpha(@theme_fg_color, 0.12);
}
paned > separator:hover { background: alpha(@theme_fg_color, 0.22); }
headerbar .title-label { font-weight: 700; font-size: 14px; }
headerbar .subtitle-label { font-size: 10.5px; color: alpha(@theme_fg_color, 0.6); }
"""


def _atomic_write(path, text):
    """Write ``text`` to ``path`` without risking a half-written file.

    The data is written to a temporary file in the same directory, flushed to
    disk, and renamed over the target.  A crash or power loss mid-write leaves
    the previous version intact.  Existing file permissions (and ownership,
    where permitted) are preserved.
    """
    target = os.path.realpath(path)
    directory = os.path.dirname(target) or "."
    try:
        info = os.stat(target)
    except FileNotFoundError:
        info = None
    if info is not None and not os.access(target, os.W_OK):
        raise PermissionError("Permission denied: %s" % path)
    fd, tmp = tempfile.mkstemp(prefix=".markdown-studio-", dir=directory)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        if info is not None:
            os.chmod(tmp, info.st_mode & 0o777)
            try:
                os.chown(tmp, info.st_uid, info.st_gid)
            except OSError:
                pass
        else:
            current_umask = os.umask(0)
            os.umask(current_umask)
            os.chmod(tmp, 0o666 & ~current_umask)
        os.replace(tmp, target)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
    # Best effort: make the rename itself durable.
    try:
        dir_fd = os.open(directory, os.O_RDONLY)
        try:
            os.fsync(dir_fd)
        finally:
            os.close(dir_fd)
    except OSError:
        pass


def _dialog_error(parent, message):
    dialog = Gtk.MessageDialog(
        transient_for=parent,
        modal=True,
        message_type=Gtk.MessageType.ERROR,
        buttons=Gtk.ButtonsType.CLOSE,
        text="Something went wrong",
    )
    dialog.format_secondary_text(message)
    dialog.run()
    dialog.destroy()


class MarkdownWindow(Gtk.ApplicationWindow):
    def __init__(self, application):
        super().__init__(application=application)
        self.set_default_size(1400, 880)
        self.set_size_request(760, 500)
        self.set_title(APP_NAME)
        if os.path.exists(ICON_PATH):
            try:
                self.set_icon_from_file(ICON_PATH)
            except GLib.Error:
                pass

        self.file_path = None
        self._loading = False
        self._last_dir = os.path.expanduser("~")
        self._preview_ready = False
        self._preview_timeout = 0
        self._scroll_timeout = 0
        self._base_uri = GLib.filename_to_uri(self._last_dir, None) + "/"
        self._first_map = True
        self._undo_stack = []
        self._redo_stack = []
        self._applying_history = False
        self._history_text = ""
        self._history_cursor = 0
        self._saved_text = ""
        self._group_start = 0

        self._build_actions()
        self._build_header()
        self._build_body()
        self._build_statusbar()
        self._build_menu()

        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        root.pack_start(self.paned, True, True, 0)
        root.pack_start(self.statusbar, False, False, 0)
        self.add(root)

        self.style_manager = Handy.StyleManager.get_default()
        self.style_manager.connect("notify::dark", self._on_theme_changed)

        self.buffer = self.textview.get_buffer()
        self.buffer.connect("changed", self._on_buffer_changed)
        self.buffer.connect("mark-set", lambda *a: self._update_cursor())
        self.buffer.connect("notify::modified", lambda *a: self._update_header())

        self.connect("map-event", self._on_first_map)
        self.connect("delete-event", self._on_delete_event)
        self.connect("drag-data-received", self._on_drag_data)
        self.connect("key-press-event", self._on_key_press)

        self.drag_dest_set(
            Gtk.DestDefaults.ALL,
            [Gtk.TargetEntry.new("text/uri-list", 0, 0)],
            Gdk.DragAction.COPY,
        )

        self._load_text(WELCOME, None)
        self._update_header()
        self._update_stats()
        self._update_cursor()
        self.show_all()
        self.textview.grab_focus()

    # ------------------------------------------------------------- chrome ---

    def _build_header(self):
        self.header = Handy.HeaderBar()
        self.header.set_show_close_button(True)
        self.header.set_has_subtitle(False)

        title_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        title_box.set_valign(Gtk.Align.CENTER)
        self.title_label = Gtk.Label(label="Untitled")
        self.title_label.set_ellipsize(Pango.EllipsizeMode.END)
        self.title_label.set_max_width_chars(48)
        self.title_label.get_style_context().add_class("title-label")
        self.subtitle_label = Gtk.Label(label="")
        self.subtitle_label.set_ellipsize(Pango.EllipsizeMode.END)
        self.subtitle_label.set_max_width_chars(64)
        self.subtitle_label.get_style_context().add_class("subtitle-label")
        title_box.pack_start(self.title_label, False, False, 0)
        title_box.pack_start(self.subtitle_label, False, False, 0)
        self.header.set_custom_title(title_box)

        for icon, action, tip in (
            ("document-new-symbolic", "win.new", "New document (Ctrl+N)"),
            ("document-open-symbolic", "win.open", "Open… (Ctrl+O)"),
            ("document-save-symbolic", "win.save", "Save (Ctrl+S)"),
        ):
            button = Gtk.Button.new_from_icon_name(icon, Gtk.IconSize.BUTTON)
            button.set_relief(Gtk.ReliefStyle.NONE)
            button.set_tooltip_text(tip)
            button.set_action_name(action)
            button.set_focus_on_click(False)
            self.header.pack_start(button)

        self.header.pack_start(Gtk.Separator(orientation=Gtk.Orientation.VERTICAL))
        for icon, action, tip in (
            ("edit-undo-symbolic", "win.undo", "Undo (Ctrl+Z)"),
            ("edit-redo-symbolic", "win.redo", "Redo (Ctrl+Shift+Z)"),
        ):
            button = Gtk.Button.new_from_icon_name(icon, Gtk.IconSize.BUTTON)
            button.set_relief(Gtk.ReliefStyle.NONE)
            button.set_tooltip_text(tip)
            button.set_action_name(action)
            button.set_focus_on_click(False)
            self.header.pack_start(button)

        self.menu_button = Gtk.MenuButton()
        self.menu_button.set_image(
            Gtk.Image.new_from_icon_name("open-menu-symbolic", Gtk.IconSize.BUTTON)
        )
        self.menu_button.set_relief(Gtk.ReliefStyle.NONE)
        self.menu_button.set_tooltip_text("Menu")
        self.menu_button.set_focus_on_click(False)
        self.header.pack_end(self.menu_button)
        self.set_titlebar(self.header)

    def _tool_button(self, icon=None, label=None, action=None, tip=None):
        if icon:
            button = Gtk.Button.new_from_icon_name(icon, Gtk.IconSize.BUTTON)
        else:
            button = Gtk.Button(label=label)
            button.get_style_context().add_class("hlabel")
        button.set_relief(Gtk.ReliefStyle.NONE)
        button.set_focus_on_click(False)
        button.set_can_focus(False)
        button.get_style_context().add_class("tool")
        if action:
            button.set_action_name(action)
        if tip:
            button.set_tooltip_text(tip)
        return button

    def _glyph_button(self, text, action=None, tip=None, mono=False):
        button = Gtk.Button(label=text)
        button.set_relief(Gtk.ReliefStyle.NONE)
        button.set_focus_on_click(False)
        button.set_can_focus(False)
        context = button.get_style_context()
        context.add_class("tool")
        context.add_class("glyph")
        if mono:
            context.add_class("mono")
        if action:
            button.set_action_name(action)
        if tip:
            button.set_tooltip_text(tip)
        return button

    def _build_body(self):
        bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        bar.get_style_context().add_class("formatbar")

        flow = Gtk.FlowBox()
        flow.set_orientation(Gtk.Orientation.HORIZONTAL)
        flow.set_selection_mode(Gtk.SelectionMode.NONE)
        flow.set_homogeneous(False)
        flow.set_max_children_per_line(5)
        flow.set_column_spacing(10)
        flow.set_row_spacing(2)
        flow.set_margin_start(9)
        flow.set_margin_end(4)
        flow.set_margin_top(4)
        flow.set_margin_bottom(4)
        flow.set_valign(Gtk.Align.CENTER)
        flow.set_hexpand(True)

        groups = [
            [
                self._tool_button("format-text-bold-symbolic", action="win.bold", tip="Bold (Ctrl+B)"),
                self._tool_button("format-text-italic-symbolic", action="win.italic", tip="Italic (Ctrl+I)"),
                self._tool_button(
                    "format-text-strikethrough-symbolic",
                    action="win.strike",
                    tip="Strikethrough (Ctrl+Shift+X)",
                ),
                self._glyph_button("</>", action="win.code", tip="Inline code (Ctrl+E)", mono=True),
            ],
            [
                self._tool_button(label="H1", action="win.h1", tip="Heading 1 (Ctrl+1)"),
                self._tool_button(label="H2", action="win.h2", tip="Heading 2 (Ctrl+2)"),
                self._tool_button(label="H3", action="win.h3", tip="Heading 3 (Ctrl+3)"),
            ],
            [
                self._tool_button("view-list-symbolic", action="win.ul", tip="Bulleted list (Ctrl+Shift+8)"),
                self._tool_button("view-list-ordered-symbolic", action="win.ol", tip="Numbered list (Ctrl+Shift+7)"),
                self._tool_button("checkbox-checked-symbolic", action="win.task", tip="Task list"),
                self._glyph_button("“", action="win.quote", tip="Block quote (Ctrl+Shift+9)"),
            ],
            [
                self._tool_button("insert-link-symbolic", action="win.link", tip="Link (Ctrl+K)"),
                self._tool_button("insert-image-symbolic", action="win.image", tip="Image (Ctrl+Shift+I)"),
            ],
            [
                self._tool_button("view-grid-symbolic", action="win.table", tip="Insert table"),
                self._tool_button("utilities-terminal-symbolic", action="win.codeblock", tip="Code block (Ctrl+Shift+C)"),
                self._glyph_button("—", action="win.hr", tip="Horizontal rule"),
            ],
        ]
        for group in groups:
            box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=1)
            for button in group:
                box.pack_start(button, False, False, 0)
            flow.add(box)

        self.preview_toggle = Gtk.ToggleButton()
        self.preview_toggle.set_image(
            Gtk.Image.new_from_icon_name("view-reveal-symbolic", Gtk.IconSize.BUTTON)
        )
        self.preview_toggle.set_relief(Gtk.ReliefStyle.NONE)
        self.preview_toggle.set_active(True)
        self.preview_toggle.set_tooltip_text("Show / hide preview (Ctrl+Shift+P)")
        self.preview_toggle.set_focus_on_click(False)
        self.preview_toggle.set_can_focus(False)
        self.preview_toggle.set_valign(Gtk.Align.CENTER)
        self.preview_toggle.set_margin_end(7)
        self.preview_toggle.get_style_context().add_class("tool")
        self.preview_toggle.connect("toggled", self._on_preview_button)

        bar.pack_start(flow, True, True, 0)
        bar.pack_end(self.preview_toggle, False, False, 0)
        self.formatbar = bar
        self.toolbar_flow = flow

        editor_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)

        self.textview = Gtk.TextView()
        self.textview.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        self.textview.set_left_margin(26)
        self.textview.set_right_margin(26)
        self.textview.set_top_margin(20)
        self.textview.set_bottom_margin(40)
        self.textview.set_pixels_above_lines(1)
        self.textview.set_pixels_below_lines(1)
        self.textview.set_accepts_tab(True)
        self.textview.get_style_context().add_class("editor-view")

        self.editor_scroll = Gtk.ScrolledWindow()
        self.editor_scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        self.editor_scroll.set_overlay_scrolling(True)
        self.editor_scroll.add(self.textview)

        editor_box.pack_start(bar, False, False, 0)
        editor_box.pack_start(self.editor_scroll, True, True, 0)
        self.editor_box = editor_box

        settings = WebKit2.Settings()
        settings.set_enable_javascript(True)
        settings.set_enable_developer_extras(False)
        settings.set_enable_page_cache(False)
        settings.set_allow_file_access_from_file_urls(True)
        settings.set_allow_universal_access_from_file_urls(False)

        self.webview = WebKit2.WebView()
        self.webview.set_settings(settings)
        self.webview.connect("load-changed", self._on_preview_load)
        self.webview.connect("decide-policy", self._on_decide_policy)

        self.paned = Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL)
        self.paned.pack1(editor_box, resize=True, shrink=False)
        self.paned.pack2(self.webview, resize=True, shrink=False)
        self.paned.set_position(700)

        self.editor_scroll.get_vadjustment().connect("value-changed", self._on_editor_scroll)

    def _build_statusbar(self):
        self.statusbar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self.statusbar.get_style_context().add_class("statusbar")
        self.statusbar.set_margin_start(14)
        self.statusbar.set_margin_end(14)
        self.statusbar.set_margin_top(5)
        self.statusbar.set_margin_bottom(5)

        self.stats_label = Gtk.Label(label="0 words")
        self.cursor_label = Gtk.Label(label="Ln 1, Col 1")
        self.encoding_label = Gtk.Label(label="UTF-8")
        self.state_label = Gtk.Label(label="Not saved")

        self.statusbar.pack_start(self.stats_label, False, False, 0)
        self.statusbar.pack_end(self.encoding_label, False, False, 0)
        self.statusbar.pack_end(Gtk.Label(label="·"), False, False, 0)
        self.statusbar.pack_end(self.cursor_label, False, False, 0)
        self.statusbar.pack_end(Gtk.Label(label="·"), False, False, 0)
        self.statusbar.pack_end(self.state_label, False, False, 0)

    def _build_menu(self):
        menu = Gio.Menu()
        menu.append("New", "win.new")
        menu.append("Open…", "win.open")
        menu.append("Save", "win.save")
        menu.append("Save As…", "win.save_as")
        menu.append("Export as HTML…", "win.export")

        view = Gio.Menu()
        view.append("Toggle Preview", "win.preview")
        view.append("Word Wrap", "win.wrap")
        view.append("Fullscreen", "win.fullscreen")
        menu.append_section(None, view)

        help_section = Gio.Menu()
        help_section.append("Keyboard Shortcuts", "win.shortcuts")
        help_section.append("About Markdown Studio", "app.about")
        help_section.append("Quit", "app.quit")
        menu.append_section(None, help_section)

        self.menu_button.set_menu_model(menu)

    # ------------------------------------------------------------ actions ---

    def _add_action(self, name, callback, state=None):
        if state is None:
            action = Gio.SimpleAction.new(name, None)
            action.connect("activate", callback)
        else:
            action = Gio.SimpleAction.new_stateful(
                name, None, GLib.Variant.new_boolean(state)
            )
            action.connect("change-state", callback)
        self.add_action(action)
        return action

    def _build_actions(self):
        self._add_action("new", self._on_new)
        self._add_action("open", self._on_open)
        self._add_action("save", self._on_save)
        self._add_action("save_as", self._on_save_as)
        self._add_action("export", self._on_export)
        self._add_action("undo", lambda *a: self._undo())
        self._add_action("redo", lambda *a: self._redo())
        self._add_action("bold", lambda *a: self._wrap("**", "**", "bold text"))
        self._add_action("italic", lambda *a: self._wrap("*", "*", "italic text"))
        self._add_action("strike", lambda *a: self._wrap("~~", "~~", "struck text"))
        self._add_action("code", lambda *a: self._wrap("`", "`", "code"))
        self._add_action("link", lambda *a: self._insert_link())
        self._add_action("image", lambda *a: self._insert_image())
        self._add_action("h1", lambda *a: self._heading(1))
        self._add_action("h2", lambda *a: self._heading(2))
        self._add_action("h3", lambda *a: self._heading(3))
        self._add_action("quote", lambda *a: self._toggle_quote())
        self._add_action("ul", lambda *a: self._toggle_list(ordered=False))
        self._add_action("ol", lambda *a: self._toggle_list(ordered=True))
        self._add_action("task", lambda *a: self._toggle_task())
        self._add_action("table", lambda *a: self._insert_table())
        self._add_action("codeblock", lambda *a: self._insert_code_block())
        self._add_action("hr", lambda *a: self._insert_block("\n\n---\n"))
        self._preview_action = self._add_action(
            "preview", self._on_preview_toggled, state=True
        )
        self._preview_action.connect("notify::state", self._sync_preview_toggle)
        self._add_action("wrap", self._on_wrap_toggled, state=True)
        self._add_action("fullscreen", self._on_fullscreen)
        self._add_action("shortcuts", self._on_shortcuts)

    # ------------------------------------------------------------- preview ---

    def _init_preview(self):
        self.webview.load_html(build_preview_shell(), self._base_uri)
        return False

    def _on_preview_load(self, webview, event):
        if event == WebKit2.LoadEvent.FINISHED:
            self._preview_ready = True
            self._push_content()
            self._apply_theme_to_preview()

    def _push_content(self):
        if not self._preview_ready:
            return
        text = self._get_text()
        js = "window.setTheme(%s);window.setContent(%s);" % (
            "true" if self.style_manager.get_dark() else "false",
            json.dumps(render_markdown(text)),
        )
        self._run_js(js)

    def _run_js(self, script):
        self.webview.evaluate_javascript(
            script, len(script), None, None, None, None, None
        )

    def _schedule_preview(self):
        if self._preview_timeout:
            GLib.source_remove(self._preview_timeout)
        self._preview_timeout = GLib.timeout_add(140, self._flush_preview)

    def _flush_preview(self):
        self._preview_timeout = 0
        self._push_content()
        return False

    def _apply_theme_to_preview(self):
        dark = self.style_manager.get_dark()
        self.webview.set_background_color(
            Gdk.RGBA(0.051, 0.067, 0.090, 1) if dark else Gdk.RGBA(1, 1, 1, 1)
        )
        if self._preview_ready:
            self._run_js("window.setTheme(%s);" % ("true" if dark else "false"))

    def _on_theme_changed(self, *_args):
        self._apply_theme_to_preview()

    def _on_editor_scroll(self, adjustment):
        if not self._preview_ready or self._scroll_timeout:
            return
        self._scroll_timeout = GLib.timeout_add(45, self._flush_scroll, adjustment)

    def _flush_scroll(self, adjustment):
        self._scroll_timeout = 0
        if not self._preview_ready:
            return False
        span = adjustment.get_upper() - adjustment.get_page_size()
        ratio = adjustment.get_value() / span if span > 0 else 0.0
        self._run_js("window.setScrollRatio(%f);" % ratio)
        return False

    def _on_decide_policy(self, webview, decision, decision_type):
        if decision_type != WebKit2.PolicyDecisionType.NAVIGATION_ACTION:
            return False
        action = decision.get_navigation_action()
        if action.get_navigation_type() == WebKit2.NavigationType.LINK_CLICKED:
            uri = action.get_request().get_uri() or ""
            if uri.startswith("file://"):
                local = GLib.filename_from_uri(uri.rsplit("#", 1)[0])[0]
                if os.path.isfile(local) and local.lower().endswith(
                    (".md", ".markdown", ".mdown", ".mkd", ".txt")
                ):
                    decision.ignore()
                    self._open_path(local)
                    return True
            if uri.startswith(("http://", "https://", "mailto:")):
                decision.ignore()
                Gtk.show_uri_on_window(self, uri, Gtk.get_current_event_time())
                return True
        return False

    def _on_preview_toggled(self, action, value):
        action.set_state(value)
        self._set_preview_visible(value.get_boolean())

    def _on_preview_button(self, button):
        active = button.get_active()
        if self._preview_action.get_state().get_boolean() != active:
            self._preview_action.set_state(GLib.Variant.new_boolean(active))
            self._set_preview_visible(active)

    def _sync_preview_toggle(self, action, _pspec=None):
        if not hasattr(self, "preview_toggle"):
            return
        active = action.get_state().get_boolean()
        if self.preview_toggle.get_active() != active:
            self.preview_toggle.set_active(active)

    def _set_preview_visible(self, show):
        self.webview.set_visible(show)
        if show:
            GLib.idle_add(self._center_paned_once)

    def _center_paned_once(self):
        width = self.paned.get_allocated_width()
        if width > 0:
            self.paned.set_position(width // 2)
        return False

    def _on_wrap_toggled(self, action, value):
        action.set_state(value)
        wrap = value.get_boolean()
        self.textview.set_wrap_mode(
            Gtk.WrapMode.WORD_CHAR if wrap else Gtk.WrapMode.NONE
        )

    def _on_fullscreen(self, *_args):
        window = self.get_window()
        if window and window.get_state() & Gdk.WindowState.FULLSCREEN:
            self.unfullscreen()
        else:
            self.fullscreen()

    # ---------------------------------------------------------- text utils ---

    def _get_text(self):
        start, end = self.buffer.get_bounds()
        return self.buffer.get_text(start, end, True)

    def _is_wrapped(self, start, end, left, right):
        text = self._get_text()
        return (
            start >= len(left)
            and text[start - len(left) : start] == left
            and text[end : end + len(right)] == right
        )

    def _wrap(self, left, right, placeholder):
        buffer = self.buffer
        buffer.begin_user_action()
        if buffer.get_has_selection():
            start, end = buffer.get_selection_bounds()
            s, e = start.get_offset(), end.get_offset()
            selected = buffer.get_text(start, end, True)
            if (
                len(selected) > len(left) + len(right)
                and selected.startswith(left)
                and selected.endswith(right)
            ):
                inner = selected[len(left) : len(selected) - len(right)]
                buffer.delete(start, end)
                buffer.insert(buffer.get_iter_at_offset(s), inner)
                buffer.select_range(
                    buffer.get_iter_at_offset(s),
                    buffer.get_iter_at_offset(s + len(inner)),
                )
            elif self._is_wrapped(s, e, left, right):
                buffer.delete(
                    buffer.get_iter_at_offset(e), buffer.get_iter_at_offset(e + len(right))
                )
                buffer.delete(
                    buffer.get_iter_at_offset(s - len(left)),
                    buffer.get_iter_at_offset(s),
                )
                buffer.place_cursor(buffer.get_iter_at_offset(e - len(left) - len(right)))
            else:
                buffer.insert(buffer.get_iter_at_offset(e), right)
                buffer.insert(buffer.get_iter_at_offset(s), left)
                buffer.select_range(
                    buffer.get_iter_at_offset(s + len(left)),
                    buffer.get_iter_at_offset(e + len(left)),
                )
        else:
            position = buffer.get_iter_at_mark(buffer.get_insert()).get_offset()
            buffer.insert(buffer.get_iter_at_offset(position), left + placeholder + right)
            buffer.select_range(
                buffer.get_iter_at_offset(position + len(left)),
                buffer.get_iter_at_offset(position + len(left) + len(placeholder)),
            )
        buffer.end_user_action()
        self.textview.grab_focus()

    def _insert_link(self):
        buffer = self.buffer
        if buffer.get_has_selection():
            start, end = buffer.get_selection_bounds()
            s, e = start.get_offset(), end.get_offset()
            buffer.begin_user_action()
            buffer.insert(buffer.get_iter_at_offset(e), "](url)")
            buffer.insert(buffer.get_iter_at_offset(s), "[")
            buffer.select_range(
                buffer.get_iter_at_offset(e + 3), buffer.get_iter_at_offset(e + 6)
            )
            buffer.end_user_action()
        else:
            self._wrap("[", "](url)", "link text")
        self.textview.grab_focus()

    def _insert_image(self):
        self._wrap("![", "](image.png)", "alt text")
        self.textview.grab_focus()

    def _selected_lines(self):
        buffer = self.buffer
        if buffer.get_has_selection():
            start, end = buffer.get_selection_bounds()
            first, last = start.get_line(), end.get_line()
            if end.get_line_offset() == 0 and last > first:
                last -= 1
        else:
            first = last = buffer.get_iter_at_mark(buffer.get_insert()).get_line()
        return first, last

    def _transform_lines(self, transform):
        """Apply transform(list_of_lines) -> new list to the selected lines."""
        buffer = self.buffer
        first, last = self._selected_lines()
        had_selection = buffer.get_has_selection()
        buffer.begin_user_action()
        lines = []
        for line in range(first, last + 1):
            start = buffer.get_iter_at_line(line)
            end = start.copy()
            end.forward_to_line_end()
            lines.append(buffer.get_text(start, end, True))
        new_lines = transform(lines)
        for line in range(last, first - 1, -1):
            start = buffer.get_iter_at_line(line)
            end = start.copy()
            end.forward_to_line_end()
            buffer.delete(start, end)
            buffer.insert(buffer.get_iter_at_line(line), new_lines[line - first])
        if had_selection:
            end_iter = buffer.get_iter_at_line(last)
            end_iter.forward_to_line_end()
            buffer.select_range(buffer.get_iter_at_line(first), end_iter)
        else:
            end = buffer.get_iter_at_line(last)
            end.forward_to_line_end()
            buffer.place_cursor(end)
        buffer.end_user_action()
        self.textview.scroll_to_mark(buffer.get_insert(), 0.1, False, 0, 0)
        self.textview.grab_focus()

    _PREFIX_RE = re.compile(
        r"^(?:#{1,6}\s+|>\s?|[-*+]\s+(?:\[[ xX]\]\s+)?|\d+[.)]\s+)"
    )

    def _strip_prefix(self, text):
        return self._PREFIX_RE.sub("", text, count=1)

    def _heading(self, level):
        marker = "#" * level + " "

        def transform(lines):
            if all(line.startswith(marker) for line in lines):
                return [self._strip_prefix(line) for line in lines]
            return [marker + self._strip_prefix(line) for line in lines]

        self._transform_lines(transform)

    def _toggle_quote(self):
        def transform(lines):
            quoted = [line.startswith(">") for line in lines]
            if all(quoted):
                return [re.sub(r"^>\s?", "", line, count=1) for line in lines]
            return [
                line if is_quoted else ("> " + line)
                for line, is_quoted in zip(lines, quoted)
            ]

        self._transform_lines(transform)

    def _toggle_list(self, ordered):
        marker_re = (
            re.compile(r"^\s*\d+[.)]\s+")
            if ordered
            else re.compile(r"^\s*[-*+]\s+(?!\[[ xX]\])")
        )

        def transform(lines):
            if all(marker_re.match(line) for line in lines):
                return [line[marker_re.match(line).end():] for line in lines]
            result = []
            for index, line in enumerate(lines):
                marker = "%d. " % (index + 1) if ordered else "- "
                result.append(marker + self._strip_prefix(line))
            return result

        self._transform_lines(transform)

    def _toggle_task(self):
        task_re = re.compile(r"^\s*[-*+]\s+\[[ xX]\]\s+")

        def transform(lines):
            if all(task_re.match(line) for line in lines):
                return [task_re.sub("", line, count=1) for line in lines]
            return ["- [ ] " + self._strip_prefix(line) for line in lines]

        self._transform_lines(transform)

    def _insert_block(self, text, select_text=None):
        buffer = self.buffer
        buffer.begin_user_action()
        insert_at = buffer.get_iter_at_mark(buffer.get_insert())
        position = insert_at.get_offset()
        prefix = "\n\n" if insert_at.get_line_offset() > 0 else ""
        buffer.insert(insert_at, prefix + text)
        if select_text and select_text in text:
            offset = position + len(prefix) + text.index(select_text)
            buffer.select_range(
                buffer.get_iter_at_offset(offset),
                buffer.get_iter_at_offset(offset + len(select_text)),
            )
        else:
            buffer.place_cursor(buffer.get_iter_at_offset(position + len(prefix) + len(text)))
        buffer.end_user_action()
        self.textview.grab_focus()

    def _insert_table(self):
        self._insert_block(
            "| Column 1 | Column 2 |\n"
            "| -------- | -------- |\n"
            "| Cell 1   | Cell 2   |",
            select_text="Column 1",
        )

    def _insert_code_block(self):
        buffer = self.buffer
        if buffer.get_has_selection():
            start, end = buffer.get_selection_bounds()
            s, e = start.get_offset(), end.get_offset()
            selected = buffer.get_text(start, end, True)
            buffer.begin_user_action()
            buffer.delete(start, end)
            block = "```\n" + selected + "\n```"
            buffer.insert(buffer.get_iter_at_offset(s), block)
            buffer.place_cursor(buffer.get_iter_at_offset(s + len(block)))
            buffer.end_user_action()
            self.textview.grab_focus()
            return
        buffer.begin_user_action()
        insert_at = buffer.get_iter_at_mark(buffer.get_insert())
        position = insert_at.get_offset()
        prefix = "\n\n" if insert_at.get_line_offset() > 0 else ""
        buffer.insert(insert_at, prefix + "```\n\n```")
        buffer.place_cursor(buffer.get_iter_at_offset(position + len(prefix) + 4))
        buffer.end_user_action()
        self.textview.grab_focus()

    def _undo(self):
        if not self._undo_stack:
            return
        self._redo_stack.append((self._history_text, self._history_cursor))
        text, cursor = self._undo_stack.pop()
        self._group_start = 0
        self._apply_history(text, cursor)

    def _redo(self):
        if not self._redo_stack:
            return
        self._undo_stack.append((self._history_text, self._history_cursor))
        text, cursor = self._redo_stack.pop()
        self._group_start = 0
        self._apply_history(text, cursor)

    def _apply_history(self, text, cursor):
        self._applying_history = True
        self.buffer.set_text(text)
        cursor = max(0, min(cursor, self.buffer.get_char_count()))
        self.buffer.place_cursor(self.buffer.get_iter_at_offset(cursor))
        self._applying_history = False
        self._history_text = text
        self._history_cursor = cursor
        self.buffer.set_modified(text != self._saved_text)
        self._update_stats()
        self._update_header()
        self._schedule_preview()
        self.textview.scroll_to_mark(self.buffer.get_insert(), 0.15, False, 0, 0)
        self.textview.grab_focus()

    # --------------------------------------------------------------- files ---

    def _load_text(self, text, path):
        self._loading = True
        self.buffer.set_text(text)
        self.buffer.place_cursor(self.buffer.get_start_iter())
        self.file_path = path
        if path:
            self._last_dir = os.path.dirname(path)
        self._base_uri = GLib.filename_to_uri(
            os.path.dirname(path) if path else self._last_dir, None
        ) + "/"
        self._loading = False
        self._saved_text = text
        self._history_text = text
        self._history_cursor = 0
        self._undo_stack.clear()
        self._redo_stack.clear()
        self._group_start = 0
        self.buffer.set_modified(False)
        self._preview_ready = False
        GLib.idle_add(self._init_preview)
        self._update_header()
        self._update_stats()
        self._update_cursor()
        self.textview.scroll_to_iter(self.buffer.get_start_iter(), 0.0, False, 0, 0)
        self._schedule_preview()

    def load_path(self, path):
        path = os.path.abspath(os.path.expanduser(path))
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as handle:
                text = handle.read()
        except OSError as error:
            _dialog_error(self, "Could not open %s\n\n%s" % (path, error))
            return
        self._load_text(text, path)

    def _open_path(self, path):
        if not self._maybe_save():
            return
        self.load_path(path)

    def _on_open(self, *_args):
        if not self._maybe_save():
            return
        path = self._choose_open()
        if path:
            self.load_path(path)

    def _on_new(self, *_args):
        if not self._maybe_save():
            return
        self._load_text("", None)
        self.textview.grab_focus()

    def _on_save(self, *_args):
        self._save()

    def _on_save_as(self, *_args):
        self._save(save_as=True)

    def _save(self, save_as=False):
        path = self.file_path
        if path is None or save_as:
            path = self._choose_save()
            if not path:
                return False
            if not os.path.splitext(path)[1]:
                path += ".md"
        text = self._get_text()
        try:
            _atomic_write(path, text)
        except OSError as error:
            _dialog_error(self, "Could not save %s\n\n%s" % (path, error))
            return False
        previous_dir = os.path.dirname(self.file_path) if self.file_path else None
        self.file_path = path
        self._last_dir = os.path.dirname(path)
        self._base_uri = GLib.filename_to_uri(self._last_dir, None) + "/"
        if previous_dir != self._last_dir:
            self._preview_ready = False
            GLib.idle_add(self._init_preview)
        self.buffer.set_modified(False)
        self._saved_text = text
        self._update_header()
        self.state_label.set_text("Saved")
        return True

    def _on_export(self, *_args):
        path = self._choose_export()
        if not path:
            return
        if not os.path.splitext(path)[1]:
            path += ".html"
        name = os.path.basename(self.file_path) if self.file_path else "Untitled"
        document = build_export_html(os.path.splitext(name)[0], self._get_text())
        try:
            _atomic_write(path, document)
        except OSError as error:
            _dialog_error(self, "Could not export %s\n\n%s" % (path, error))

    def _choose_open(self):
        dialog = Gtk.FileChooserDialog(
            title="Open Markdown File",
            transient_for=self,
            action=Gtk.FileChooserAction.OPEN,
            use_header_bar=True,
        )
        dialog.add_buttons(
            "Cancel", Gtk.ResponseType.CANCEL, "Open", Gtk.ResponseType.ACCEPT
        )
        dialog.set_default_response(Gtk.ResponseType.ACCEPT)
        dialog.set_current_folder(self._last_dir)

        markdown_filter = Gtk.FileFilter()
        markdown_filter.set_name("Markdown files")
        for pattern in ("*.md", "*.markdown", "*.mdown", "*.mkd", "*.txt"):
            markdown_filter.add_pattern(pattern)
        dialog.add_filter(markdown_filter)

        all_filter = Gtk.FileFilter()
        all_filter.set_name("All files")
        all_filter.add_pattern("*")
        dialog.add_filter(all_filter)

        response = dialog.run()
        path = dialog.get_filename() if response == Gtk.ResponseType.ACCEPT else None
        dialog.destroy()
        if path:
            self._last_dir = os.path.dirname(path)
        return path

    def _choose_save(self):
        dialog = Gtk.FileChooserDialog(
            title="Save Markdown File",
            transient_for=self,
            action=Gtk.FileChooserAction.SAVE,
            use_header_bar=True,
        )
        dialog.add_buttons(
            "Cancel", Gtk.ResponseType.CANCEL, "Save", Gtk.ResponseType.ACCEPT
        )
        dialog.set_default_response(Gtk.ResponseType.ACCEPT)
        dialog.set_do_overwrite_confirmation(True)
        dialog.set_current_folder(self._last_dir)
        if self.file_path:
            dialog.set_filename(self.file_path)
            dialog.set_current_name(os.path.basename(self.file_path))
        else:
            dialog.set_current_name("untitled.md")

        filter_md = Gtk.FileFilter()
        filter_md.set_name("Markdown files")
        for pattern in ("*.md", "*.markdown", "*.txt"):
            filter_md.add_pattern(pattern)
        dialog.add_filter(filter_md)

        response = dialog.run()
        path = dialog.get_filename() if response == Gtk.ResponseType.ACCEPT else None
        dialog.destroy()
        if path:
            self._last_dir = os.path.dirname(path)
        return path

    def _choose_export(self):
        dialog = Gtk.FileChooserDialog(
            title="Export as HTML",
            transient_for=self,
            action=Gtk.FileChooserAction.SAVE,
            use_header_bar=True,
        )
        dialog.add_buttons(
            "Cancel", Gtk.ResponseType.CANCEL, "Export", Gtk.ResponseType.ACCEPT
        )
        dialog.set_default_response(Gtk.ResponseType.ACCEPT)
        dialog.set_do_overwrite_confirmation(True)
        dialog.set_current_folder(self._last_dir)
        base = (
            os.path.splitext(os.path.basename(self.file_path))[0]
            if self.file_path
            else "untitled"
        )
        dialog.set_current_name(base + ".html")

        filter_html = Gtk.FileFilter()
        filter_html.set_name("HTML files")
        filter_html.add_pattern("*.html")
        dialog.add_filter(filter_html)

        response = dialog.run()
        path = dialog.get_filename() if response == Gtk.ResponseType.ACCEPT else None
        dialog.destroy()
        if path:
            self._last_dir = os.path.dirname(path)
        return path

    def _maybe_save(self):
        if not self.buffer.get_modified():
            return True
        dialog = Gtk.MessageDialog(
            transient_for=self,
            modal=True,
            message_type=Gtk.MessageType.QUESTION,
            buttons=Gtk.ButtonsType.NONE,
            text="Save changes?",
        )
        dialog.format_secondary_text(
            "“%s” has unsaved changes. Your changes will be lost if you don't save them."
            % (os.path.basename(self.file_path) if self.file_path else "Untitled")
        )
        dialog.add_button("Cancel", Gtk.ResponseType.CANCEL)
        dialog.add_button("Discard", Gtk.ResponseType.NO)
        dialog.add_button("Save", Gtk.ResponseType.YES)
        dialog.set_default_response(Gtk.ResponseType.YES)
        discard = dialog.get_widget_for_response(Gtk.ResponseType.NO)
        if discard:
            discard.get_style_context().add_class("destructive-action")
        response = dialog.run()
        dialog.destroy()
        if response == Gtk.ResponseType.YES:
            return self._save()
        return response == Gtk.ResponseType.NO

    def _on_delete_event(self, *_args):
        return not self._maybe_save()

    # -------------------------------------------------------------- status ---

    def _on_buffer_changed(self, *_args):
        if self._loading:
            return
        current = self._get_text()
        if not self._applying_history and current != self._history_text:
            now = GLib.get_monotonic_time()
            if not self._undo_stack or now - self._group_start > 1_200_000:
                self._undo_stack.append((self._history_text, self._history_cursor))
                del self._undo_stack[:-80]
                while (
                    sum(len(entry[0]) for entry in self._undo_stack) > 8_000_000
                    and len(self._undo_stack) > 1
                ):
                    self._undo_stack.pop(0)
                self._redo_stack.clear()
            self._group_start = now
            self._history_text = current
            self._history_cursor = self.buffer.get_iter_at_mark(
                self.buffer.get_insert()
            ).get_offset()
            self.buffer.set_modified(current != self._saved_text)
        self._update_stats()
        self._update_header()
        self._schedule_preview()

    def _update_header(self):
        name = os.path.basename(self.file_path) if self.file_path else "Untitled"
        modified = self.buffer.get_modified()
        self.title_label.set_text(name)
        self.set_title("%s — %s" % (name, APP_NAME))
        if self.file_path:
            location = os.path.dirname(self.file_path).replace(os.path.expanduser("~"), "~", 1)
            subtitle = ("Edited · " if modified else "") + location
        else:
            subtitle = "Edited" if modified else "Not saved yet"
        self.subtitle_label.set_text(subtitle)
        if modified:
            self.state_label.set_text("Edited")
        elif self.file_path:
            self.state_label.set_text("Saved")
        else:
            self.state_label.set_text("Not saved")

    def _update_stats(self):
        text = self._get_text()
        words = len(text.split())
        characters = len(text)
        lines = text.count("\n") + 1 if text else 1
        word_label = "word" if words == 1 else "words"
        line_label = "line" if lines == 1 else "lines"
        self.stats_label.set_text(
            "%s %s · %s characters · %s %s"
            % (format(words, ","), word_label, format(characters, ","), format(lines, ","), line_label)
        )

    def _update_cursor(self):
        iterator = self.buffer.get_iter_at_mark(self.buffer.get_insert())
        self.cursor_label.set_text(
            "Ln %s, Col %s" % (format(iterator.get_line() + 1, ","), iterator.get_line_offset() + 1)
        )

    # --------------------------------------------------------------- misc ----

    def _on_first_map(self, *_args):
        if not self._first_map:
            return False
        self._first_map = False
        width = self.paned.get_allocated_width()
        if width > 0:
            self.paned.set_position(width // 2)
        return False

    def _on_key_press(self, _widget, event):
        if event.keyval == Gdk.KEY_Escape and self.get_window().get_state() & Gdk.WindowState.FULLSCREEN:
            self.unfullscreen()
            return True
        return False

    def _on_drag_data(self, _widget, _context, _x, _y, data, _info, _time):
        uris = data.get_uris()
        if not uris:
            return
        path = GLib.filename_from_uri(uris[0])[0]
        if os.path.isfile(path):
            self._open_path(path)

    def _on_shortcuts(self, *_args):
        dialog = Gtk.MessageDialog(
            transient_for=self,
            modal=True,
            message_type=Gtk.MessageType.INFO,
            buttons=Gtk.ButtonsType.CLOSE,
            text="Keyboard Shortcuts",
        )
        dialog.format_secondary_text(
            "Editing\n"
            "  Ctrl+B  Bold          Ctrl+I  Italic\n"
            "  Ctrl+E  Inline code   Ctrl+K  Link\n"
            "  Ctrl+1/2/3  Headings  Ctrl+Shift+C  Code block\n"
            "  Ctrl+Shift+8/7  Lists Ctrl+Shift+9  Quote\n"
            "  Ctrl+Z / Ctrl+Shift+Z  Undo / Redo\n\n"
            "Files\n"
            "  Ctrl+N  New           Ctrl+O  Open\n"
            "  Ctrl+S  Save          Ctrl+Shift+S  Save As\n"
            "  Ctrl+Shift+E  Export as HTML\n\n"
            "View\n"
            "  Ctrl+Shift+P  Toggle preview     F11  Fullscreen\n"
            "  Ctrl+Q  Quit"
        )
        dialog.run()
        dialog.destroy()


class MarkdownStudio(Gtk.Application):
    def __init__(self):
        super().__init__(
            application_id=APP_ID, flags=Gio.ApplicationFlags.HANDLES_OPEN
        )
        self.window = None

    def do_startup(self):
        Gtk.Application.do_startup(self)
        GLib.set_application_name(APP_NAME)
        GLib.set_prgname("markdown-studio")

        provider = Gtk.CssProvider()
        provider.load_from_data(APP_CSS)
        Gtk.StyleContext.add_provider_for_screen(
            Gdk.Screen.get_default(),
            provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
        )

        quit_action = Gio.SimpleAction.new("quit", None)
        quit_action.connect("activate", self._on_quit)
        self.add_action(quit_action)

        about_action = Gio.SimpleAction.new("about", None)
        about_action.connect("activate", self._on_about)
        self.add_action(about_action)

        accels = {
            "win.new": ["<Control>n"],
            "win.open": ["<Control>o"],
            "win.save": ["<Control>s"],
            "win.save_as": ["<Control><Shift>s"],
            "win.export": ["<Control><Shift>e"],
            "win.undo": ["<Control>z"],
            "win.redo": ["<Control><Shift>z", "<Control>y"],
            "win.bold": ["<Control>b"],
            "win.italic": ["<Control>i"],
            "win.strike": ["<Control><Shift>x"],
            "win.code": ["<Control>e"],
            "win.link": ["<Control>k"],
            "win.image": ["<Control><Shift>i"],
            "win.h1": ["<Control>1"],
            "win.h2": ["<Control>2"],
            "win.h3": ["<Control>3"],
            "win.quote": ["<Control><Shift>9"],
            "win.ul": ["<Control><Shift>8"],
            "win.ol": ["<Control><Shift>7"],
            "win.table": [],
            "win.codeblock": ["<Control><Shift>c"],
            "win.preview": ["<Control><Shift>p"],
            "win.wrap": [],
            "win.fullscreen": ["F11"],
            "win.shortcuts": [],
            "app.quit": ["<Control>q"],
            "app.about": [],
        }
        for action, shortcuts in accels.items():
            if shortcuts:
                self.set_accels_for_action(action, shortcuts)

    def do_activate(self):
        if self.window is None:
            self.window = MarkdownWindow(application=self)
        self.window.present()

    def do_open(self, files, _n_files, _hint):
        if self.window is None:
            self.window = MarkdownWindow(application=self)
        self.window.present()
        if files:
            path = files[0].get_path()
            if path:
                self.window._open_path(path)

    def _on_quit(self, *_args):
        for window in list(self.get_windows()):
            window.close()
            if window in self.get_windows():
                return
        if not self.get_windows():
            self.quit()

    def _on_about(self, *_args):
        window = self.window or self.get_active_window()
        dialog = Gtk.AboutDialog(transient_for=window, modal=True)
        dialog.set_program_name(APP_NAME)
        dialog.set_version(APP_VERSION)
        dialog.set_comments(
            "A small, fast Markdown editor with a live preview.\n"
            "Write on the left, see the result on the right."
        )
        dialog.set_license_type(Gtk.License.MIT_X11)
        if os.path.exists(ICON_PATH):
            try:
                dialog.set_logo(
                    GdkPixbuf.Pixbuf.new_from_file_at_scale(ICON_PATH, 128, 128, True)
                )
            except GLib.Error:
                pass
        dialog.run()
        dialog.destroy()


def main():
    app = MarkdownStudio()
    return app.run(sys.argv)


if __name__ == "__main__":
    sys.exit(main())
