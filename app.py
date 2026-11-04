#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Markdown Studio — a small, fast Markdown editor for macOS.

Layout: toolbar + tabs above the editor, live preview beside it.
Renderer: markdown-it-py + Pygments. Preview: Qt WebEngine (WebKit-derived).
Framework: PySide6 (Qt 6).

Dependencies: PySide6, markdown-it-py, pygments.
"""

import html
import http.client
import json
import os
import re
import socket
import ssl
import subprocess
import sys
import tempfile
import threading
import urllib.parse

from PySide6.QtCore import (
    QCoreApplication,
    QEvent,
    QObject,
    QPoint,
    QSettings,
    QSize,
    Qt,
    QTimer,
    QUrl,
    Signal,
)
from PySide6.QtGui import (
    QAction,
    QColor,
    QDesktopServices,
    QFont,
    QFontDatabase,
    QGuiApplication,
    QIcon,
    QKeySequence,
    QPainter,
    QPalette,
    QPen,
    QPixmap,
    QTextCharFormat,
    QTextCursor,
)
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QDialog,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QProxyStyle,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSplitter,
    QStackedWidget,
    QStatusBar,
    QStyle,
    QTabBar,
    QTextBrowser,
    QTextEdit,
    QToolBar,
    QToolButton,
    QVBoxLayout,
    QWidget,
)
from PySide6.QtWebEngineCore import QWebEnginePage, QWebEngineSettings
from PySide6.QtWebEngineWidgets import QWebEngineView

from markdown_it import MarkdownIt
from pygments import highlight as pygments_highlight
from pygments.formatters import HtmlFormatter
from pygments.lexers import get_lexer_by_name
from pygments.util import ClassNotFound

# Qt WebEngine requires this attribute before the QApplication is created.
QCoreApplication.setAttribute(
    Qt.ApplicationAttribute.AA_ShareOpenGLContexts, True
)

APP_ID = "io.github.markdownstudio.MarkdownStudio"
APP_NAME = "Markdown Studio"
APP_VERSION = "2.0"
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ICON_PATH = os.path.join(BASE_DIR, "markdown-studio.svg")
TOOLBAR_ICON_DIR = os.path.join(BASE_DIR, "assets", "toolbar")
MARKDOWN_EXTENSIONS = (".md", ".markdown", ".mdown", ".mkd", ".txt")
TOOLBAR_LABELS = {
    "new": "New",
    "open": "Open",
    "save": "Save",
    "undo": "Undo",
    "redo": "Redo",
    "bold": "Bold",
    "italic": "Italic",
    "strike": "Strikethrough",
    "code": "Inline Code",
    "ul": "Bulleted List",
    "ol": "Numbered List",
    "task": "Task List",
    "quote": "Block Quote",
    "link": "Link",
    "image": "Image",
    "table": "Table",
    "codeblock": "Code Block",
    "hr": "Horizontal Rule",
    "preview": "Preview",
}

# LanguageTool provides free spelling and grammar checks. QuillBot does not
# offer a public API without a paid account, so LanguageTool is the default.
GRAMMAR_URL = os.environ.get(
    "MARKDOWN_STUDIO_GRAMMAR_URL", "https://api.languagetool.org/v2/check"
)
GRAMMAR_LANGUAGE = os.environ.get("MARKDOWN_STUDIO_GRAMMAR_LANGUAGE", "en-US")
GRAMMAR_MAX_CHARS = 19000


class _IPv4HTTPConnection(http.client.HTTPConnection):
    """HTTPConnection that skips unreachable IPv6 addresses (fast fallback)."""

    def connect(self):
        try:
            infos = socket.getaddrinfo(
                self.host, self.port, socket.AF_INET, socket.SOCK_STREAM
            )
        except socket.gaierror:
            return super().connect()
        last_error = None
        for family, socktype, proto, _canon, address in infos:
            sock = socket.socket(family, socktype, proto)
            sock.settimeout(self.timeout)
            try:
                sock.connect(address)
            except OSError as error:
                last_error = error
                sock.close()
                continue
            self.sock = sock
            return
        raise last_error or OSError("Could not connect to %s" % self.host)


class _IPv4HTTPSConnection(_IPv4HTTPConnection, http.client.HTTPSConnection):
    def connect(self):
        super().connect()
        context = self._context or ssl.create_default_context()
        self.sock = context.wrap_socket(self.sock, server_hostname=self.host)


WELCOME = """# Welcome to Markdown Studio

A quiet place to write Markdown, with a live preview that updates as you type.

## The basics

- Write on the left, watch the result on the right.
- Use the **toolbar** above the editor, or the keyboard shortcuts, to format.
- Press **⌘S** to save and **⌘O** to open a file. Open several files
  at once and switch between them with the tabs at the top.
- Press **⌘N** for a new tab, **⌘W** to close one, and **⌃⇥**
  to move between tabs.
- Files with a name are saved automatically as you type.
- Use **Tools → Check Spelling & Grammar** for a spelling and grammar review.
- Drag a `.md` file onto the window to open it.

> Good writing is clear thinking made visible.

## Try the formatting

Select some text and press **⌘B** for bold, **⌘I** for italic, or
**⌘K** to turn it into a link. Headings are **⌘1**, **⌘2** and **⌘3**.

```python
def greet(name):
    return f"Hello, {name}!"

print(greet("writer"))
```

| Shortcut | Action        |
| -------- | ------------- |
| ⌘B       | Bold          |
| ⌘I       | Italic        |
| ⌘K       | Insert link   |
| ⌘E       | Inline code   |

- [x] Open the app
- [ ] Write something worth keeping
- [ ] Export it as HTML
"""

PREVIEW_CSS = r"""
body {
  margin: 0;
  font-family: -apple-system, BlinkMacSystemFont, "SF Pro Text",
               "Helvetica Neue", Arial, sans-serif;
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
  font-family: "SF Mono", Menlo, Monaco, "Courier New", monospace;
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
  font-family: "SF Mono", Menlo, Monaco, monospace;
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

APP_CSS = r"""
QToolBar {
  background: palette(window);
  border: none;
  border-bottom: 1px solid rgba(127, 127, 127, 0.18);
  spacing: 1px;
  padding: 3px 8px;
}
#tabStrip {
  background: palette(window);
  border-bottom: 1px solid rgba(127, 127, 127, 0.18);
}
QTabBar::tab { min-width: 104px; }
QToolButton#newTab {
  border: none;
  background: transparent;
  padding: 0;
}
QToolButton#newTab:hover {
  background: rgba(127, 127, 127, 0.16);
  border-radius: 5px;
}
QSplitter::handle {
  background: transparent;
  border-left: 1px solid rgba(127, 127, 127, 0.24);
}
QSplitter::handle:hover { background: rgba(127, 127, 127, 0.10); }
QStatusBar {
  border-top: 1px solid rgba(127, 127, 127, 0.18);
  background: palette(window);
}
QStatusBar QLabel {
  color: palette(mid);
  font-size: 11px;
  padding: 0 2px;
}
QScrollArea#grammarScroll { border: none; background: palette(window); }
QWidget#grammarContent { background: palette(window); }
QFrame#issueCard {
  border: 1px solid rgba(127, 127, 127, 0.28);
  border-radius: 10px;
  background: palette(alternate-base);
}
QLabel#grammarCount { font-size: 15px; }
QLabel#grammarDetail { color: palette(mid); }
QLabel#grammarContext { color: palette(mid); }
"""

# ---------------------------------------------------------------- markdown ---

_md = MarkdownIt(
    "commonmark",
    {"html": False, "linkify": True, "typographer": True, "breaks": False},
)
_md.enable(["table", "strikethrough", "linkify", "replacements", "smartquotes"])

_TASK_RE = re.compile(r"<li>\s*\[([ xX])\](?:\s+|(?=</li>))")


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


def _base_url_for(folder):
    folder = os.path.abspath(os.path.expanduser(folder or os.path.expanduser("~")))
    if not folder.endswith(os.sep):
        folder += os.sep
    return QUrl.fromLocalFile(folder)


def _shortcut_text(widget, shortcuts):
    if not shortcuts:
        return ""
    return shortcuts[0].toString(QKeySequence.SequenceFormat.NativeText)


def _dialog_error(parent, message):
    QMessageBox.critical(parent, "Something went wrong", message)


def _dialog_info(parent, message, title="Markdown Studio"):
    QMessageBox.information(parent, title, message)


def _dialog_replace(parent, path):
    """Ask before a Save/Export overwrites a path we appended an extension to."""
    box = QMessageBox(parent)
    box.setIcon(QMessageBox.Icon.Question)
    box.setWindowTitle("Replace existing file?")
    box.setText("“%s” already exists." % os.path.basename(path))
    box.setInformativeText("Do you want to replace it?")
    box.setStandardButtons(QMessageBox.StandardButton.Cancel)
    replace = box.addButton("Replace", QMessageBox.ButtonRole.DestructiveRole)
    box.setDefaultButton(QMessageBox.StandardButton.Cancel)
    box.exec()
    return box.clickedButton() is replace


def _set_widget_font(widget, point_size=None, bold=False, italic=False, mono=False):
    if widget is None:
        return
    font = widget.font()
    if mono:
        font = QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont)
        if not font.family():
            font = QFont("Menlo")
        if point_size:
            font.setPointSize(point_size)
    elif point_size:
        font.setPointSize(point_size)
    if bold:
        font.setBold(True)
    if italic:
        font.setItalic(True)
    widget.setFont(font)


class LeftAlignedTabStyle(QProxyStyle):
    """Keep native macOS tab painting, but start tabs at the leading edge."""

    def styleHint(self, hint, option=None, widget=None, returnData=None):
        if hint == QStyle.StyleHint.SH_TabBar_Alignment:
            return int(Qt.AlignmentFlag.AlignLeft.value)
        return super().styleHint(hint, option, widget, returnData)


class GrammarCard(QFrame):
    """A rounded issue card that follows the current light/dark palette."""

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        background = self.palette().color(QPalette.ColorRole.AlternateBase)
        border = self.palette().color(QPalette.ColorRole.Mid)
        border.setAlpha(90)
        painter.setBrush(background)
        painter.setPen(QPen(border, 1))
        painter.drawRoundedRect(self.rect().adjusted(0, 0, -1, -1), 10, 10)
        painter.end()


class MarkdownEditor(QPlainTextEdit):
    """Plain-text editor that forwards dropped Markdown files to the window."""

    def __init__(self, window):
        super().__init__()
        self.window_ref = window

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            return
        super().dragEnterEvent(event)

    def dropEvent(self, event):
        paths = self.window_ref.paths_from_mime(event.mimeData())
        if paths:
            event.acceptProposedAction()
            self.window_ref.open_paths(paths)
            return
        super().dropEvent(event)


class Document:
    """One open file: its editor, path, saved text and view state."""

    def __init__(self, window, text, path=None, label=None, base_dir=None):
        self.editor = MarkdownEditor(window)
        self.editor.setPlainText(text)
        self.editor.setPlaceholderText("Start writing Markdown…")
        self.editor.setTabChangesFocus(False)
        self.editor.setFrameShape(QFrame.Shape.NoFrame)
        self.editor.setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth)
        self.editor.setViewportMargins(26, 20, 26, 40)
        self.editor.document().setModified(False)
        font = QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont)
        if not font.family():
            font = QFont("Menlo")
        font.setPointSize(13)
        self.editor.setFont(font)
        self.editor.setTabStopDistance(
            self.editor.fontMetrics().horizontalAdvance(" ") * 4
        )

        self.path = path
        self.label = label
        self.saved_text = text
        self.scroll_ratio = 0.0
        self.grammar_matches = []
        folder = os.path.dirname(path) if path else (base_dir or os.path.expanduser("~"))
        self.base_dir = folder

    @property
    def display_name(self):
        if self.path:
            return os.path.basename(self.path)
        return self.label or "Untitled"

    def is_modified(self):
        return self.editor.document().isModified()

    def text(self):
        return self.editor.toPlainText()


# --------------------------------------------------------------- qwebengine ---

class PreviewPage(QWebEnginePage):
    def __init__(self, window, parent=None):
        super().__init__(parent)
        self.window_ref = window

    def acceptNavigationRequest(self, url, nav_type, is_main_frame):
        if is_main_frame and nav_type == QWebEnginePage.NavigationType.NavigationTypeLinkClicked:
            scheme = url.scheme().lower()
            if scheme in ("http", "https", "mailto"):
                QDesktopServices.openUrl(url)
                return False
            if scheme == "file":
                local = url.toLocalFile()
                if local and os.path.isdir(local):
                    # An in-page anchor resolves against the base folder.
                    return True
                if local and os.path.isfile(local):
                    if local.lower().endswith(MARKDOWN_EXTENSIONS):
                        QTimer.singleShot(
                            0, lambda path=local: self.window_ref.open_paths([path])
                        )
                    else:
                        QDesktopServices.openUrl(url)
                    return False
            return False
        return super().acceptNavigationRequest(url, nav_type, is_main_frame)


class GrammarBridge(QObject):
    finished = Signal(object, str, str, object, object, object)


# ------------------------------------------------------------------ window ---

class MarkdownWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setMinimumSize(640, 420)
        self.resize(1400, 880)
        self.setWindowTitle(APP_NAME)
        self.setWindowIcon(QIcon(ICON_PATH))
        self.setAcceptDrops(True)

        self._loading = False
        self._switching_document = False
        self._syncing_tabs = False
        self._preview_ready = False
        self._preview_generation = 0
        self._shutting_down = False
        self._last_dir = os.path.expanduser("~")
        self._autosave_enabled = True
        self._paned_ratio = 0.5
        self._recent = []
        self._icon_actions = {}
        self._grammar_checking = False
        self._grammar_dialog = None
        self._grammar_doc = None
        self._grammar_text = ""
        self._grammar_matches = []
        self._grammar_list_layout = None
        self._grammar_count = None
        self._grammar_detail = None
        self._grammar_fix_button = None

        self.docs = []
        self.doc = None

        self._settings = QSettings()
        self._load_preferences()

        self._build_actions()
        self._build_menu()
        self._build_toolbar()
        self._build_central_widget()
        self._build_statusbar()

        self._preview_timer = QTimer(self)
        self._preview_timer.setSingleShot(True)
        self._preview_timer.setInterval(140)
        self._preview_timer.timeout.connect(self._push_content)

        self._scroll_timer = QTimer(self)
        self._scroll_timer.setSingleShot(True)
        self._scroll_timer.setInterval(45)
        self._scroll_timer.timeout.connect(self._flush_scroll)

        self._autosave_timer = QTimer(self)
        self._autosave_timer.setSingleShot(True)
        self._autosave_timer.setInterval(1200)
        self._autosave_timer.timeout.connect(self._flush_autosave)

        self._grammar_bridge = GrammarBridge(self)
        self._grammar_bridge.finished.connect(self._show_grammar_results)

        self._build_preview()
        self._restore_window_state()
        self._sync_theme()
        self._refresh_recent_menu()

        try:
            QGuiApplication.styleHints().colorSchemeChanged.connect(
                self._on_system_theme_changed
            )
        except AttributeError:
            pass

        self._new_document(WELCOME, None, label="Welcome")
        self._apply_wrap_to_all()
        self._set_preview_visible(self._preview_visible, initial=True)
        self._update_header()
        QTimer.singleShot(0, self._apply_split_ratio)

    # ---------------------------------------------------------- preferences ---

    def _load_preferences(self):
        settings = self._settings
        value = settings.value("files/lastDir", "")
        if value and os.path.isdir(str(value)):
            self._last_dir = str(value)
        self._autosave_enabled = self._setting_bool("edit/autosave", True)
        self._wrap_enabled = self._setting_bool("view/wrap", True)
        self._preview_visible = self._setting_bool("view/preview", True)
        try:
            ratio = float(settings.value("preview/ratio", 0.5))
        except (TypeError, ValueError):
            ratio = 0.5
        self._paned_ratio = min(0.9, max(0.1, ratio))
        recent = settings.value("files/recent", [])
        if isinstance(recent, str):
            recent = [recent] if recent else []
        elif recent is None:
            recent = []
        self._recent = [str(path) for path in recent][:10]

    def _setting_bool(self, key, default):
        value = self._settings.value(key, default)
        if isinstance(value, bool):
            return value
        return str(value).lower() not in ("false", "0", "no", "")

    def _save_preferences(self):
        settings = self._settings
        settings.setValue("window/geometry", self.saveGeometry())
        settings.setValue("window/state", self.saveState())
        settings.setValue("splitter/state", self.splitter.saveState())
        settings.setValue("preview/ratio", self._paned_ratio)
        settings.setValue("view/preview", self._preview_visible)
        settings.setValue("view/wrap", self._wrap_enabled)
        settings.setValue("edit/autosave", self._autosave_enabled)
        settings.setValue("files/lastDir", self._last_dir)
        settings.setValue("files/recent", self._recent)
        settings.sync()

    def _restore_window_state(self):
        geometry = self._settings.value("window/geometry")
        if geometry:
            self.restoreGeometry(geometry)
        state = self._settings.value("window/state")
        if state:
            self.restoreState(state)
        splitter_state = self._settings.value("splitter/state")
        if splitter_state:
            self.splitter.restoreState(splitter_state)
            sizes = self.splitter.sizes()
            total = sum(sizes)
            if total > 0 and sizes[0] > 0:
                self._paned_ratio = min(0.9, max(0.1, sizes[0] / total))

    # -------------------------------------------------------------- actions ---

    def _build_actions(self):
        self.act = {}

        def action(key, text, slot, shortcuts=None, checkable=False, checked=False):
            act = QAction(text, self)
            if shortcuts:
                act.setShortcuts([QKeySequence(item) for item in shortcuts])
            act.setCheckable(checkable)
            if checkable:
                act.setChecked(checked)
            if not checkable:
                act.triggered.connect(slot)
            self.act[key] = act
            return act

        action("new", "New Tab", self._on_new, ["Ctrl+N"])
        action("open", "Open…", self._on_open, ["Ctrl+O"])
        action("save", "Save", self._on_save, ["Ctrl+S"])
        action("save_as", "Save As…", self._on_save_as, ["Ctrl+Shift+S"])
        action("close", "Close Tab", self._on_close, ["Ctrl+W"])
        action("export", "Export as HTML…", self._on_export, ["Ctrl+Shift+E"])
        action("grammar", "Check Spelling & Grammar…", self._on_check_grammar, ["Ctrl+Shift+G"])
        action("undo", "Undo", lambda: self._editor().undo(), ["Ctrl+Z"])
        action("redo", "Redo", lambda: self._editor().redo(), ["Ctrl+Shift+Z", "Ctrl+Y"])
        action("cut", "Cut", lambda: self._editor().cut(), ["Ctrl+X"])
        action("copy", "Copy", lambda: self._editor().copy(), ["Ctrl+C"])
        action("paste", "Paste", lambda: self._editor().paste(), ["Ctrl+V"])
        action("select_all", "Select All", lambda: self._editor().selectAll(), ["Ctrl+A"])

        action("bold", "Bold", lambda: self._wrap("**", "**", "bold text"), ["Ctrl+B"])
        action("italic", "Italic", lambda: self._wrap("*", "*", "italic text"), ["Ctrl+I"])
        action("strike", "Strikethrough", lambda: self._wrap("~~", "~~", "struck text"), ["Ctrl+Shift+X"])
        action("code", "Inline Code", lambda: self._wrap("`", "`", "code"), ["Ctrl+E"])
        action("link", "Link…", self._insert_link, ["Ctrl+K"])
        action("image", "Image…", self._insert_image, ["Ctrl+Shift+I"])
        action("h1", "Heading 1", lambda: self._heading(1), ["Ctrl+1"])
        action("h2", "Heading 2", lambda: self._heading(2), ["Ctrl+2"])
        action("h3", "Heading 3", lambda: self._heading(3), ["Ctrl+3"])
        action("quote", "Block Quote", self._toggle_quote, ["Ctrl+Shift+9"])
        action("ul", "Bulleted List", lambda: self._toggle_list(False), ["Ctrl+Shift+8"])
        action("ol", "Numbered List", lambda: self._toggle_list(True), ["Ctrl+Shift+7"])
        action("task", "Task List", self._toggle_task)
        action("table", "Insert Table", self._insert_table)
        action("codeblock", "Code Block", self._insert_code_block, ["Ctrl+Shift+C"])
        action("hr", "Horizontal Rule", lambda: self._insert_block("\n\n---\n"))
        action("next_tab", "Next Tab", lambda: self._cycle_tab(1), ["Meta+Tab", "Meta+PageDown"])
        action("prev_tab", "Previous Tab", lambda: self._cycle_tab(-1), ["Meta+Shift+Tab", "Meta+PageUp"])
        action("fullscreen", "Enter Full Screen", self._toggle_fullscreen, ["F11", "Ctrl+Meta+F"])
        action("shortcuts", "Keyboard Shortcuts", self._show_shortcuts)
        action("minimize", "Minimize", self.showMinimized, ["Ctrl+M"])
        action("zoom", "Zoom", self._toggle_zoom)

        preview = action("preview", "Show Preview", self._on_preview_action, checkable=True, checked=self._preview_visible)
        preview.toggled.connect(self._on_preview_toggled)

        wrap = action("wrap", "Word Wrap", self._on_wrap_toggled, checkable=True, checked=self._wrap_enabled)
        wrap.toggled.connect(self._on_wrap_toggled)

        autosave = action("autosave", "Auto-save", self._on_autosave_toggled, checkable=True, checked=self._autosave_enabled)
        autosave.toggled.connect(self._on_autosave_toggled)

        quit_action = action("quit", "Quit Markdown Studio", self.close, ["Ctrl+Q"])
        quit_action.setMenuRole(QAction.MenuRole.QuitRole)

        about_action = action("about", "About Markdown Studio", self._show_about)
        about_action.setMenuRole(QAction.MenuRole.AboutRole)

        for key, act in self.act.items():
            if act.shortcuts():
                hint = _shortcut_text(self, act.shortcuts())
                base = act.text().replace("&", "").replace("…", "")
                act.setToolTip("%s (%s)" % (base, hint))
                act.setStatusTip(act.toolTip())
            else:
                act.setToolTip(act.text().replace("&", ""))
                act.setStatusTip(act.toolTip())

        self.act["wrap"].setToolTip("Wrap long lines")
        self.act["autosave"].setToolTip("Save named files while you type")
        self.act["preview"].setToolTip("Show or hide the preview")

    def _build_menu(self):
        menubar = self.menuBar()
        if hasattr(menubar, "setNativeMenuBar"):
            menubar.setNativeMenuBar(True)

        file_menu = menubar.addMenu("File")
        file_menu.addAction(self.act["new"])
        file_menu.addAction(self.act["open"])
        self.recent_menu = file_menu.addMenu("Open Recent")
        file_menu.addSeparator()
        file_menu.addAction(self.act["save"])
        file_menu.addAction(self.act["save_as"])
        file_menu.addAction(self.act["export"])
        file_menu.addSeparator()
        file_menu.addAction(self.act["close"])
        file_menu.addSeparator()
        file_menu.addAction(self.act["quit"])

        edit_menu = menubar.addMenu("Edit")
        edit_menu.addAction(self.act["undo"])
        edit_menu.addAction(self.act["redo"])
        edit_menu.addSeparator()
        edit_menu.addAction(self.act["cut"])
        edit_menu.addAction(self.act["copy"])
        edit_menu.addAction(self.act["paste"])
        edit_menu.addAction(self.act["select_all"])

        format_menu = menubar.addMenu("Format")
        for key in ("bold", "italic", "strike", "code"):
            format_menu.addAction(self.act[key])
        format_menu.addSeparator()
        for key in ("h1", "h2", "h3"):
            format_menu.addAction(self.act[key])
        format_menu.addSeparator()
        for key in ("quote", "ul", "ol", "task"):
            format_menu.addAction(self.act[key])
        format_menu.addSeparator()
        format_menu.addAction(self.act["link"])
        format_menu.addAction(self.act["image"])
        format_menu.addSeparator()
        format_menu.addAction(self.act["table"])
        format_menu.addAction(self.act["codeblock"])
        format_menu.addAction(self.act["hr"])

        view_menu = menubar.addMenu("View")
        view_menu.addAction(self.act["next_tab"])
        view_menu.addAction(self.act["prev_tab"])
        view_menu.addSeparator()
        view_menu.addAction(self.act["preview"])
        view_menu.addAction(self.act["wrap"])
        view_menu.addSeparator()
        view_menu.addAction(self.act["fullscreen"])

        tools_menu = menubar.addMenu("Tools")
        tools_menu.addAction(self.act["grammar"])
        tools_menu.addSeparator()
        tools_menu.addAction(self.act["autosave"])

        window_menu = menubar.addMenu("Window")
        window_menu.addAction(self.act["minimize"])
        window_menu.addAction(self.act["zoom"])
        window_menu.addSeparator()
        window_menu.addAction(self.act["fullscreen"])

        help_menu = menubar.addMenu("Help")
        help_menu.addAction(self.act["shortcuts"])
        help_menu.addAction(self.act["about"])

    def _toolbar_icon(self, key):
        path = os.path.join(TOOLBAR_ICON_DIR, key + ".png")
        pixmap = QPixmap(path)
        if pixmap.isNull():
            return QIcon()
        tinted = QPixmap(pixmap.size())
        tinted.fill(Qt.GlobalColor.transparent)
        painter = QPainter(tinted)
        painter.drawPixmap(0, 0, pixmap)
        painter.setCompositionMode(
            QPainter.CompositionMode.CompositionMode_SourceIn
        )
        painter.fillRect(tinted.rect(), self.palette().color(QPalette.ColorRole.ButtonText))
        painter.end()
        return QIcon(tinted)

    def _refresh_toolbar_icons(self):
        for action, key in self._icon_actions.items():
            action.setIcon(self._toolbar_icon(key))
        if hasattr(self, "new_tab_button"):
            self.new_tab_button.setIcon(self._toolbar_icon("plus"))
            self.new_tab_button.setIconSize(QSize(14, 14))

    def _build_toolbar(self):
        self.toolbar = QToolBar("Format", self)
        self.toolbar.setObjectName("FormatToolbar")
        self.toolbar.setMovable(False)
        self.toolbar.setFloatable(False)
        self.toolbar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
        self.toolbar.setIconSize(QSize(18, 18))
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, self.toolbar)

        def icon_tool(key, slot, tip):
            act = QAction(TOOLBAR_LABELS.get(key, key.title()), self)
            act.setToolTip(tip)
            act.triggered.connect(slot)
            self.toolbar.addAction(act)
            self._icon_actions[act] = key
            act.setIcon(self._toolbar_icon(key))
            return act

        def text_tool(label, slot, tip):
            act = QAction(label, self)
            act.setToolTip(tip)
            act.triggered.connect(slot)
            self.toolbar.addAction(act)
            button = self.toolbar.widgetForAction(act)
            if button is not None:
                button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
                _set_widget_font(button, 10, bold=True)
            return act

        icon_tool("new", self._on_new, "New tab (%s)" % _shortcut_text(self, self.act["new"].shortcuts()))
        icon_tool("open", self._on_open, "Open… (%s)" % _shortcut_text(self, self.act["open"].shortcuts()))
        icon_tool("save", self._on_save, "Save (%s)" % _shortcut_text(self, self.act["save"].shortcuts()))
        self.toolbar.addSeparator()
        icon_tool("undo", lambda: self._editor().undo(), "Undo (%s)" % _shortcut_text(self, self.act["undo"].shortcuts()))
        icon_tool("redo", lambda: self._editor().redo(), "Redo (%s)" % _shortcut_text(self, self.act["redo"].shortcuts()))
        self.toolbar.addSeparator()
        icon_tool("bold", lambda: self._wrap("**", "**", "bold text"), "Bold (%s)" % _shortcut_text(self, self.act["bold"].shortcuts()))
        icon_tool("italic", lambda: self._wrap("*", "*", "italic text"), "Italic (%s)" % _shortcut_text(self, self.act["italic"].shortcuts()))
        icon_tool("strike", lambda: self._wrap("~~", "~~", "struck text"), "Strikethrough (%s)" % _shortcut_text(self, self.act["strike"].shortcuts()))
        icon_tool("code", lambda: self._wrap("`", "`", "code"), "Inline code (%s)" % _shortcut_text(self, self.act["code"].shortcuts()))
        self.toolbar.addSeparator()
        text_tool("H1", lambda: self._heading(1), "Heading 1 (%s)" % _shortcut_text(self, self.act["h1"].shortcuts()))
        text_tool("H2", lambda: self._heading(2), "Heading 2 (%s)" % _shortcut_text(self, self.act["h2"].shortcuts()))
        text_tool("H3", lambda: self._heading(3), "Heading 3 (%s)" % _shortcut_text(self, self.act["h3"].shortcuts()))
        self.toolbar.addSeparator()
        icon_tool("ul", lambda: self._toggle_list(False), "Bulleted list (%s)" % _shortcut_text(self, self.act["ul"].shortcuts()))
        icon_tool("ol", lambda: self._toggle_list(True), "Numbered list (%s)" % _shortcut_text(self, self.act["ol"].shortcuts()))
        icon_tool("task", self._toggle_task, "Task list")
        icon_tool("quote", self._toggle_quote, "Block quote (%s)" % _shortcut_text(self, self.act["quote"].shortcuts()))
        self.toolbar.addSeparator()
        icon_tool("link", self._insert_link, "Link (%s)" % _shortcut_text(self, self.act["link"].shortcuts()))
        icon_tool("image", self._insert_image, "Image (%s)" % _shortcut_text(self, self.act["image"].shortcuts()))
        self.toolbar.addSeparator()
        icon_tool("table", self._insert_table, "Insert table")
        icon_tool("codeblock", self._insert_code_block, "Code block (%s)" % _shortcut_text(self, self.act["codeblock"].shortcuts()))
        icon_tool("hr", lambda: self._insert_block("\n\n---\n"), "Horizontal rule")

        spacer = QWidget(self)
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.toolbar.addWidget(spacer)

        self.preview_button_action = QAction("Preview", self)
        self.preview_button_action.setCheckable(True)
        self.preview_button_action.setChecked(self._preview_visible)
        self.preview_button_action.setToolTip("Show or hide the preview")
        self.preview_button_action.toggled.connect(self._on_preview_button_toggled)
        self.toolbar.addAction(self.preview_button_action)
        self._icon_actions[self.preview_button_action] = "preview"
        self.preview_button_action.setIcon(self._toolbar_icon("preview"))
        preview_button = self.toolbar.widgetForAction(self.preview_button_action)
        if preview_button is not None:
            preview_button.setToolButtonStyle(
                Qt.ToolButtonStyle.ToolButtonTextBesideIcon
            )
            _set_widget_font(preview_button, 11)

    def _build_central_widget(self):
        central = QWidget(self)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        tab_strip = QFrame(central)
        tab_strip.setObjectName("tabStrip")
        tab_strip.setAutoFillBackground(True)
        tab_strip.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        tab_layout = QHBoxLayout(tab_strip)
        tab_layout.setContentsMargins(8, 0, 8, 0)
        tab_layout.setSpacing(4)

        self.tabs = QTabBar(tab_strip)
        self.tabs.setStyle(LeftAlignedTabStyle(QApplication.style()))
        self.tabs.setDocumentMode(True)
        self.tabs.setDrawBase(False)
        self.tabs.setExpanding(False)
        self.tabs.setMovable(True)
        self.tabs.setTabsClosable(True)
        self.tabs.setUsesScrollButtons(True)
        self.tabs.setElideMode(Qt.TextElideMode.ElideRight)
        self.tabs.setMinimumHeight(35)
        self.tabs.currentChanged.connect(self._on_tab_changed)
        self.tabs.tabCloseRequested.connect(self._on_tab_close_requested)
        self.tabs.tabMoved.connect(self._on_tab_moved)
        tab_layout.addWidget(self.tabs, 1)

        self.new_tab_button = QToolButton(tab_strip)
        self.new_tab_button.setObjectName("newTab")
        self.new_tab_button.setAutoRaise(True)
        self.new_tab_button.setToolTip("New tab (%s)" % _shortcut_text(self, self.act["new"].shortcuts()))
        self.new_tab_button.setFixedSize(28, 26)
        self.new_tab_button.setIconSize(QSize(14, 14))
        self.new_tab_button.clicked.connect(self._on_new)
        tab_layout.addWidget(self.new_tab_button, 0, Qt.AlignmentFlag.AlignVCenter)

        layout.addWidget(tab_strip, 0)

        self.stack = QStackedWidget(central)
        self.stack.setMinimumWidth(260)

        self.preview = QWebEngineView(central)
        self.preview.setMinimumWidth(240)
        self.preview.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.preview.setContextMenuPolicy(Qt.ContextMenuPolicy.NoContextMenu)

        self.splitter = QSplitter(Qt.Orientation.Horizontal, central)
        self.splitter.setChildrenCollapsible(False)
        self.splitter.setHandleWidth(5)
        self.splitter.addWidget(self.stack)
        self.splitter.addWidget(self.preview)
        self.splitter.setStretchFactor(0, 1)
        self.splitter.setStretchFactor(1, 1)
        self.splitter.setSizes([700, 700])
        self.splitter.splitterMoved.connect(self._on_splitter_moved)

        layout.addWidget(self.splitter, 1)
        self.setCentralWidget(central)

    def _build_statusbar(self):
        bar = QStatusBar(self)
        bar.setSizeGripEnabled(False)
        self.setStatusBar(bar)

        self.stats_label = QLabel("0 words")
        self.state_label = QLabel("Not saved")
        self.cursor_label = QLabel("Ln 1, Col 1")
        self.encoding_label = QLabel("UTF-8")

        bar.addWidget(self.stats_label, 1)
        for label in (self.state_label, QLabel("·"), self.cursor_label, QLabel("·"), self.encoding_label):
            bar.addPermanentWidget(label)

    def _build_preview(self):
        self.preview_page = PreviewPage(self, self.preview)
        self.preview.setPage(self.preview_page)
        settings = self.preview.settings()
        settings.setAttribute(QWebEngineSettings.WebAttribute.JavascriptEnabled, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.JavascriptCanOpenWindows, False)
        settings.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessFileUrls, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.PluginsEnabled, False)
        settings.setAttribute(QWebEngineSettings.WebAttribute.FullScreenSupportEnabled, False)
        self.preview.loadFinished.connect(self._on_preview_load)
        self._load_preview_shell()

    # --------------------------------------------------------------- theme ---

    def _is_system_dark(self):
        override = os.environ.get("MARKDOWN_STUDIO_THEME", "").lower()
        if override in ("dark", "light"):
            return override == "dark"
        try:
            scheme = QGuiApplication.styleHints().colorScheme()
            if scheme == Qt.ColorScheme.Dark:
                return True
            if scheme == Qt.ColorScheme.Light:
                return False
        except AttributeError:
            pass
        try:
            result = subprocess.run(
                ["defaults", "read", "-g", "AppleInterfaceStyle"],
                capture_output=True,
                text=True,
                timeout=2,
            )
            return "dark" in result.stdout.lower()
        except Exception:
            return False

    def _grammar_colors(self):
        if self._is_system_dark():
            return QColor("#ff7b72"), QColor(255, 123, 114, 42)
        return QColor("#d1242f"), QColor(209, 36, 47, 28)

    def _sync_theme(self):
        dark = self._is_system_dark()
        self.preview_page.setBackgroundColor(QColor("#0d1117") if dark else QColor("#ffffff"))
        if self._preview_ready:
            self._run_js("window.setTheme(%s);" % ("true" if dark else "false"))
        self._refresh_toolbar_icons()
        self._reapply_grammar_highlights()

    def _on_system_theme_changed(self, *_args):
        self._sync_theme()

    def _apply_theme_to_preview(self):
        self._sync_theme()

    # ------------------------------------------------------------- preview ---

    def _document_base_url(self, doc=None):
        doc = doc or self.doc
        folder = doc.base_dir if doc else self._last_dir
        return _base_url_for(folder)

    def _load_preview_shell(self):
        if self.doc is not None:
            folder = self.doc.base_dir
        else:
            folder = self._last_dir
        self._preview_ready = False
        self._preview_generation += 1
        self.preview.setHtml(build_preview_shell(), _base_url_for(folder))

    def _on_preview_load(self, ok):
        if not ok:
            return
        self._preview_ready = True
        self._sync_theme()
        self._push_content()
        if self.doc is not None and self._preview_ready:
            self._run_js("window.setScrollRatio(%f);" % self.doc.scroll_ratio)

    def _run_js(self, script):
        if not self._preview_ready:
            return
        try:
            self.preview.page().runJavaScript(script)
        except RuntimeError:
            pass

    def _push_content(self):
        if not self._preview_ready or self.doc is None:
            return
        markup = render_markdown(self.doc.text())
        payload = json.dumps(markup).replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")
        self._run_js(
            "window.setTheme(%s);window.setContent(%s);"
            % ("true" if self._is_system_dark() else "false", payload)
        )

    def _schedule_preview(self):
        self._preview_timer.start()

    def _on_editor_scroll(self, doc):
        if self._switching_document or doc is not self.doc:
            return
        bar = doc.editor.verticalScrollBar()
        span = bar.maximum() - bar.minimum()
        doc.scroll_ratio = (bar.value() - bar.minimum()) / span if span > 0 else 0.0
        if not self._preview_ready:
            return
        if not self._scroll_timer.isActive():
            self._scroll_timer.start()

    def _flush_scroll(self):
        if not self._preview_ready or self.doc is None:
            return
        self._run_js("window.setScrollRatio(%f);" % self.doc.scroll_ratio)

    def _on_splitter_moved(self, _pos, _index):
        if self._preview_visible:
            sizes = self.splitter.sizes()
            total = sum(sizes)
            if total > 0:
                ratio = sizes[0] / total
                if 0.1 <= ratio <= 0.9:
                    self._paned_ratio = ratio

    def _apply_split_ratio(self):
        if not self._preview_visible:
            return
        total = sum(self.splitter.sizes())
        if total <= 0:
            total = self.splitter.width()
        if total > 0:
            left = int(total * self._paned_ratio)
            self.splitter.setSizes([left, total - left])

    def _set_preview_visible(self, show, initial=False):
        self._preview_visible = bool(show)
        self.preview.setVisible(self._preview_visible)
        if self.act["preview"].isChecked() != self._preview_visible:
            self.act["preview"].blockSignals(True)
            self.act["preview"].setChecked(self._preview_visible)
            self.act["preview"].blockSignals(False)
        if self.preview_button_action.isChecked() != self._preview_visible:
            self.preview_button_action.blockSignals(True)
            self.preview_button_action.setChecked(self._preview_visible)
            self.preview_button_action.blockSignals(False)
        if self._preview_visible:
            QTimer.singleShot(0, self._apply_split_ratio)
        elif not initial:
            self._settings.setValue("preview/ratio", self._paned_ratio)

    def _on_preview_action(self, _checked=False):
        self._set_preview_visible(self.act["preview"].isChecked())

    def _on_preview_toggled(self, checked):
        self._set_preview_visible(checked)

    def _on_preview_button_toggled(self, checked):
        self._set_preview_visible(checked)

    # ---------------------------------------------------------- text utils ---

    def _editor(self):
        return self.doc.editor if self.doc is not None else None

    def _get_text(self):
        return self.doc.text() if self.doc is not None else ""

    def _begin_edit(self):
        cursor = self._editor().textCursor()
        cursor.beginEditBlock()
        return cursor

    def _end_edit(self, cursor):
        cursor.endEditBlock()
        self._editor().setTextCursor(cursor)

    def _is_wrapped(self, start, end, left, right):
        text = self._get_text()
        return (
            start >= len(left)
            and text[start - len(left) : start] == left
            and text[end : end + len(right)] == right
        )

    def _wrap(self, left, right, placeholder):
        editor = self._editor()
        if editor is None:
            return
        cursor = editor.textCursor()
        doc = editor.document()
        text = editor.toPlainText()
        cursor.beginEditBlock()
        try:
            if cursor.hasSelection():
                s, e = cursor.selectionStart(), cursor.selectionEnd()
                selected = text[s:e]
                if (
                    len(selected) > len(left) + len(right)
                    and selected.startswith(left)
                    and selected.endswith(right)
                ):
                    inner = selected[len(left) : len(selected) - len(right)]
                    cursor.setPosition(s)
                    cursor.setPosition(e, QTextCursor.MoveMode.KeepAnchor)
                    cursor.insertText(inner)
                    cursor.setPosition(s)
                    cursor.setPosition(s + len(inner), QTextCursor.MoveMode.KeepAnchor)
                elif self._is_wrapped(s, e, left, right):
                    cursor.setPosition(e + len(right))
                    cursor.setPosition(e, QTextCursor.MoveMode.KeepAnchor)
                    cursor.removeSelectedText()
                    cursor.setPosition(s)
                    cursor.setPosition(s - len(left), QTextCursor.MoveMode.KeepAnchor)
                    cursor.removeSelectedText()
                    cursor.setPosition(e - len(left) - len(right))
                else:
                    cursor.setPosition(e)
                    cursor.insertText(right)
                    cursor.setPosition(s)
                    cursor.insertText(left)
                    cursor.setPosition(s + len(left))
                    cursor.setPosition(e + len(left), QTextCursor.MoveMode.KeepAnchor)
            else:
                position = cursor.position()
                cursor.insertText(left + placeholder + right)
                cursor.setPosition(position + len(left))
                cursor.setPosition(
                    position + len(left) + len(placeholder),
                    QTextCursor.MoveMode.KeepAnchor,
                )
        finally:
            cursor.endEditBlock()
        editor.setTextCursor(cursor)
        editor.setFocus()

    def _insert_link(self):
        editor = self._editor()
        if editor is None:
            return
        cursor = editor.textCursor()
        if cursor.hasSelection():
            s, e = cursor.selectionStart(), cursor.selectionEnd()
            cursor.beginEditBlock()
            cursor.setPosition(e)
            cursor.insertText("](url)")
            cursor.setPosition(s)
            cursor.insertText("[")
            cursor.setPosition(e + 3)
            cursor.setPosition(e + 6, QTextCursor.MoveMode.KeepAnchor)
            cursor.endEditBlock()
            editor.setTextCursor(cursor)
        else:
            self._wrap("[", "](url)", "link text")
        editor.setFocus()

    def _insert_image(self):
        self._wrap("![", "](image.png)", "alt text")
        self._editor().setFocus()

    def _selected_lines(self):
        editor = self._editor()
        cursor = editor.textCursor()
        doc = editor.document()
        if cursor.hasSelection():
            first_block = doc.findBlock(cursor.selectionStart())
            last_block = doc.findBlock(cursor.selectionEnd())
            first = first_block.blockNumber()
            last = last_block.blockNumber()
            if cursor.selectionEnd() == last_block.position() and last > first:
                last -= 1
        else:
            first = last = cursor.block().blockNumber()
        return first, last

    def _transform_lines(self, transform):
        editor = self._editor()
        if editor is None:
            return
        doc = editor.document()
        first, last = self._selected_lines()
        cursor = editor.textCursor()
        had_selection = cursor.hasSelection()
        lines = []
        for number in range(first, last + 1):
            block = doc.findBlockByNumber(number)
            lines.append(block.text())
        new_lines = transform(lines)
        new_text = "\n".join(new_lines)
        start_block = doc.findBlockByNumber(first)
        end_block = doc.findBlockByNumber(last)
        start_pos = start_block.position()
        end_pos = end_block.position() + max(0, end_block.length() - 1)

        cursor.beginEditBlock()
        try:
            cursor.setPosition(start_pos)
            cursor.setPosition(end_pos, QTextCursor.MoveMode.KeepAnchor)
            cursor.insertText(new_text)
        finally:
            cursor.endEditBlock()
        if had_selection:
            cursor.setPosition(start_pos)
            cursor.setPosition(start_pos + len(new_text), QTextCursor.MoveMode.KeepAnchor)
        else:
            cursor.setPosition(start_pos + len(new_text))
        editor.setTextCursor(cursor)
        editor.ensureCursorVisible()
        editor.setFocus()

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
        editor = self._editor()
        if editor is None:
            return
        cursor = editor.textCursor()
        position = cursor.position()
        prefix = "\n\n" if cursor.positionInBlock() > 0 else ""
        cursor.beginEditBlock()
        cursor.insertText(prefix + text)
        if select_text and select_text in text:
            offset = position + len(prefix) + text.index(select_text)
            cursor.setPosition(offset)
            cursor.setPosition(offset + len(select_text), QTextCursor.MoveMode.KeepAnchor)
        else:
            cursor.setPosition(position + len(prefix) + len(text))
        cursor.endEditBlock()
        editor.setTextCursor(cursor)
        editor.setFocus()

    def _insert_table(self):
        self._insert_block(
            "| Column 1 | Column 2 |\n"
            "| -------- | -------- |\n"
            "| Cell 1   | Cell 2   |",
            select_text="Column 1",
        )

    def _insert_code_block(self):
        editor = self._editor()
        if editor is None:
            return
        cursor = editor.textCursor()
        cursor.beginEditBlock()
        if cursor.hasSelection():
            selected = cursor.selectedText().replace("\u2029", "\n")
            cursor.removeSelectedText()
            block = "```\n" + selected + "\n```"
            cursor.insertText(block)
            cursor.setPosition(cursor.position())
        else:
            position = cursor.position()
            prefix = "\n\n" if cursor.positionInBlock() > 0 else ""
            cursor.insertText(prefix + "```\n\n```")
            cursor.setPosition(position + len(prefix) + 4)
        cursor.endEditBlock()
        editor.setTextCursor(cursor)
        editor.setFocus()

    # --------------------------------------------------------------- files ---

    def _make_document(self, text, path=None, label=None):
        doc = Document(self, text, path, label, self._last_dir)
        editor = doc.editor
        editor.textChanged.connect(lambda d=doc: self._on_text_changed(d))
        editor.cursorPositionChanged.connect(lambda d=doc: self._on_cursor_changed(d))
        editor.document().modificationChanged.connect(
            lambda _modified, d=doc: self._on_modification_changed(d)
        )
        editor.verticalScrollBar().valueChanged.connect(
            lambda _value, d=doc: self._on_editor_scroll(d)
        )
        self.docs.append(doc)
        self.stack.addWidget(editor)
        self._syncing_tabs = True
        index = self.tabs.addTab(doc.display_name)
        self.tabs.setTabToolTip(index, doc.path or "Not saved yet")
        self._syncing_tabs = False
        return doc

    def _new_document(self, text="", path=None, label=None):
        doc = self._make_document(text, path, label)
        self._select_document(doc)
        return doc

    def _on_tab_changed(self, index):
        if self._syncing_tabs:
            return
        if 0 <= index < len(self.docs):
            self._select_document(self.docs[index])

    def _on_tab_close_requested(self, index):
        if 0 <= index < len(self.docs):
            self._close_document(self.docs[index])

    def _on_tab_moved(self, source, destination):
        if self._syncing_tabs:
            return
        if 0 <= source < len(self.docs) and 0 <= destination < len(self.docs):
            doc = self.docs.pop(source)
            self.docs.insert(destination, doc)
            self._update_tabs()

    def _select_document(self, doc):
        if doc not in self.docs:
            return
        if doc is self.doc:
            doc.editor.setFocus()
            return
        self._flush_pending_autosave()
        self._store_active_view_state()
        target_ratio = doc.scroll_ratio
        self._switching_document = True
        self.doc = doc
        if doc.path:
            self._last_dir = os.path.dirname(doc.path)
        self.stack.setCurrentWidget(doc.editor)
        self._syncing_tabs = True
        self.tabs.setCurrentIndex(self.docs.index(doc))
        self._syncing_tabs = False
        self.tabs.setTabToolTip(self.docs.index(doc), doc.path or "Not saved yet")
        self._update_header()
        self._update_stats()
        self._update_cursor()
        self._reset_preview()
        QTimer.singleShot(0, lambda d=doc, r=target_ratio: self._restore_editor_scroll(d, r))
        doc.editor.setFocus()

    def _store_active_view_state(self):
        if self.doc is None:
            return
        bar = self.doc.editor.verticalScrollBar()
        span = bar.maximum() - bar.minimum()
        self.doc.scroll_ratio = (bar.value() - bar.minimum()) / span if span > 0 else 0.0

    def _restore_editor_scroll(self, doc, ratio):
        if doc is not self.doc:
            return
        bar = doc.editor.verticalScrollBar()
        span = bar.maximum() - bar.minimum()
        if span > 0:
            bar.setValue(int(ratio * span))
        doc.scroll_ratio = ratio
        self._switching_document = False
        self._flush_scroll()

    def _close_document(self, doc):
        if doc not in self.docs:
            return
        if doc is not self.doc:
            self._select_document(doc)
        self._flush_pending_autosave()
        if not self._maybe_save(doc):
            return
        if self._grammar_doc is doc and self._grammar_dialog is not None:
            self._close_grammar_dialog(self._grammar_dialog)
        index = self.docs.index(doc)
        self.docs.remove(doc)
        self._syncing_tabs = True
        self.tabs.removeTab(index)
        self._syncing_tabs = False
        self.stack.removeWidget(doc.editor)
        doc.editor.deleteLater()
        if not self.docs:
            self.doc = None
            self._new_document("", None)
            return
        self.doc = None
        self._select_document(self.docs[min(index, len(self.docs) - 1)])

    def _on_close(self, *_args):
        if self.doc is not None:
            self._close_document(self.doc)

    def _cycle_tab(self, step):
        if len(self.docs) < 2 or self.doc is None:
            return
        index = (self.docs.index(self.doc) + step) % len(self.docs)
        self._select_document(self.docs[index])

    def _load_text(self, doc, text, path):
        self._cancel_pending_autosave()
        self._loading = True
        doc.editor.setPlainText(text)
        doc.editor.moveCursor(QTextCursor.MoveOperation.Start)
        doc.editor.document().setModified(False)
        self._loading = False
        self._clear_grammar_highlights(doc)
        doc.path = path
        doc.label = None
        if path:
            self._last_dir = os.path.dirname(path)
        doc.base_dir = os.path.dirname(path) if path else self._last_dir
        doc.saved_text = text
        doc.scroll_ratio = 0.0
        self._update_header()
        self._update_stats()
        self._update_cursor()
        QTimer.singleShot(0, lambda: doc.editor.verticalScrollBar().setValue(0))
        self._reset_preview()
        self._schedule_preview()

    def _open_path(self, path):
        path = os.path.realpath(os.path.abspath(os.path.expanduser(path)))
        for doc in self.docs:
            if doc.path and os.path.realpath(doc.path) == path:
                self._select_document(doc)
                return
        try:
            with open(path, "r", encoding="utf-8-sig", errors="replace") as handle:
                text = handle.read()
        except OSError as error:
            _dialog_error(self, "Could not open %s\n\n%s" % (path, error))
            return
        current = self.doc
        if (
            current is not None
            and current.path is None
            and not current.is_modified()
        ):
            self._load_text(current, text, path)
        else:
            self._new_document(text, path)
        self._remember_recent(path)

    def open_paths(self, paths):
        for path in paths:
            if path and os.path.isfile(path):
                self._open_path(path)

    def paths_from_mime(self, mime):
        paths = []
        if not mime.hasUrls():
            return paths
        for url in mime.urls():
            if not url.isLocalFile():
                continue
            path = url.toLocalFile()
            if path and os.path.isfile(path):
                paths.append(path)
        return paths

    def _on_open(self, *_args):
        paths, _filter = QFileDialog.getOpenFileNames(
            self,
            "Open Markdown File",
            self._last_dir,
            "Markdown files (*.md *.markdown *.mdown *.mkd *.txt);;All files (*)",
        )
        if paths:
            self._last_dir = os.path.dirname(paths[-1])
            for path in paths:
                self._open_path(path)
        self._editor().setFocus()

    def _on_new(self, *_args):
        self._new_document("", None)
        self._editor().setFocus()

    def _on_save(self, *_args):
        self._save()

    def _on_save_as(self, *_args):
        self._save(save_as=True)

    def _save(self, save_as=False, doc=None):
        doc = doc or self.doc
        if doc is None:
            return False
        self._cancel_pending_autosave()
        path = doc.path
        if path is None or save_as:
            path = self._choose_save(doc)
            if not path:
                return False
            if not os.path.splitext(path)[1] and not os.path.isfile(path):
                candidate = path + ".md"
                if os.path.isfile(candidate) and not _dialog_replace(self, candidate):
                    return False
                path = candidate
        text = doc.text()
        try:
            _atomic_write(path, text)
        except OSError as error:
            _dialog_error(self, "Could not save %s\n\n%s" % (path, error))
            return False
        previous_dir = doc.base_dir
        doc.path = path
        doc.label = None
        doc.base_dir = os.path.dirname(path)
        doc.saved_text = text
        doc.editor.document().setModified(False)
        if doc is self.doc:
            self._last_dir = os.path.dirname(path)
            if previous_dir != doc.base_dir:
                self._reset_preview()
            self._update_header()
            self.state_label.setText("Saved")
        self._update_tabs()
        self._remember_recent(path)
        return True

    # ------------------------------------------------------------ autosave ---

    def _schedule_autosave(self):
        if self._autosave_enabled:
            self._autosave_timer.start()

    def _cancel_pending_autosave(self):
        self._autosave_timer.stop()

    def _flush_pending_autosave(self):
        if self._autosave_timer.isActive():
            self._cancel_pending_autosave()
            if self.doc is not None and self.doc.path:
                self._autosave_document(self.doc)

    def _flush_autosave(self):
        if self.doc is None or not self._autosave_enabled:
            return
        if self.doc.path and self.doc.is_modified():
            self._autosave_document(self.doc)

    def _autosave_document(self, doc):
        if not doc.path or not doc.is_modified():
            return True
        text = doc.text()
        try:
            _atomic_write(doc.path, text)
        except OSError:
            if doc is self.doc:
                self.state_label.setText("Auto-save failed")
            return False
        doc.saved_text = text
        doc.editor.document().setModified(False)
        if doc is self.doc:
            self._update_header()
            self.state_label.setText("Auto-saved")
        self._update_tabs()
        return True

    def _autosave_all(self):
        for doc in self.docs:
            if doc.path and doc.is_modified():
                self._autosave_document(doc)

    def _on_autosave_toggled(self, checked):
        self._autosave_enabled = bool(checked)
        if self._autosave_enabled:
            self._schedule_autosave()
        else:
            self._cancel_pending_autosave()

    # ------------------------------------------------- spelling & grammar ---

    def _on_check_grammar(self, *_args):
        if self._grammar_dialog is not None:
            self._grammar_dialog.show()
            self._grammar_dialog.raise_()
            self._grammar_dialog.activateWindow()
            return
        if self._grammar_checking or self.doc is None:
            return
        text = self.doc.text()
        if not text.strip():
            _dialog_info(self, "There is no text to check.", "Nothing to check")
            return
        self._clear_grammar_highlights(self.doc)
        checked = text[:GRAMMAR_MAX_CHARS]
        self._grammar_checking = True
        self.state_label.setText("Checking spelling & grammar…")
        worker = threading.Thread(
            target=self._grammar_worker,
            args=(self.doc, text, checked),
            daemon=True,
        )
        worker.start()

    def _post_grammar(self, payload):
        parsed = urllib.parse.urlparse(GRAMMAR_URL)
        path = parsed.path or "/"
        if parsed.query:
            path += "?" + parsed.query
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
        if parsed.scheme not in ("http", "https") or not parsed.hostname:
            raise OSError("Unsupported grammar checker URL: %s" % GRAMMAR_URL)
        if parsed.scheme == "https":
            connection = _IPv4HTTPSConnection(parsed.hostname, port, timeout=20)
        else:
            connection = _IPv4HTTPConnection(parsed.hostname, port, timeout=20)
        try:
            connection.request(
                "POST",
                path,
                body=payload,
                headers={
                    "User-Agent": "MarkdownStudio/%s" % APP_VERSION,
                    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
                    "Accept": "application/json",
                },
            )
            response = connection.getresponse()
            raw = response.read()
            if response.status >= 400:
                raise OSError("Grammar service returned HTTP %s" % response.status)
        finally:
            connection.close()
        return json.loads(raw.decode("utf-8"))

    def _grammar_worker(self, doc, text, checked, dialog=None):
        data = None
        error = None
        try:
            payload = urllib.parse.urlencode(
                {"text": checked, "language": GRAMMAR_LANGUAGE}
            ).encode("utf-8")
            data = self._post_grammar(payload)
        except Exception as error_object:  # network, TLS, JSON, rate limit…
            error = str(error_object) or error_object.__class__.__name__
        self._grammar_bridge.finished.emit(doc, text, checked, data, error, dialog)

    def _show_grammar_results(self, doc, text, checked, data, error, dialog=None):
        if self._shutting_down:
            return
        self._grammar_checking = False
        if doc not in self.docs:
            if dialog is not None:
                self._close_grammar_dialog(dialog)
            return
        if dialog is not None and dialog is not self._grammar_dialog:
            return
        if doc.text() != text:
            # The document changed while the request was in flight. Showing
            # the old offsets would highlight the wrong words, so discard the
            # result and re-check an open review.
            if doc is self.doc:
                self._update_header()
            if dialog is not None and dialog is self._grammar_dialog:
                self._refresh_grammar_dialog(doc, dialog)
            return
        if doc is self.doc:
            self._update_header()
        if dialog is not None:
            if error:
                self._set_grammar_status(
                    "Check failed", "Could not reach the grammar service: %s" % error
                )
                self._clear_grammar_rows()
                return
            matches = data.get("matches", []) if data else []
            matches = [dict(match) for match in matches]
            self._normalise_grammar_offsets(checked, matches)
            self._render_grammar_matches(doc, checked, matches, text)
            return
        if error:
            _dialog_error(
                self,
                "Could not reach the spelling and grammar service.\n\n"
                "Check your internet connection and try again.\n\n%s" % error,
            )
            return
        matches = data.get("matches", []) if data else []
        matches = [dict(match) for match in matches]
        self._normalise_grammar_offsets(checked, matches)
        if not matches:
            _dialog_info(
                self,
                "No spelling or grammar issues were found.",
                "Spelling & Grammar",
            )
            return
        self._build_grammar_dialog(doc, text, checked, matches)

    def _set_grammar_status(self, count, detail):
        if self._grammar_count is not None:
            self._grammar_count.setText("<b>%s</b>" % html.escape(count))
        if self._grammar_detail is not None:
            self._grammar_detail.setText(detail)

    def _clear_grammar_rows(self):
        if self._grammar_list_layout is None:
            return
        while self._grammar_list_layout.count():
            item = self._grammar_list_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()
        if self._grammar_fix_button is not None:
            self._grammar_fix_button.setEnabled(False)

    def _render_grammar_matches(self, doc, checked, matches, full_text):
        self._grammar_matches = matches
        self._grammar_text = full_text
        self._grammar_doc = doc
        if self._grammar_list_layout is None:
            return
        self._clear_grammar_rows()
        self._highlight_grammar_issues(doc, matches)
        if matches:
            self._set_grammar_status(
                "%d issue%s found"
                % (len(matches), "" if len(matches) == 1 else "s"),
                self._grammar_detail_text(len(full_text), len(checked)),
            )
        else:
            self._set_grammar_status(
                "No issues found",
                self._grammar_detail_text(len(full_text), len(checked)),
            )
            label = QLabel("No spelling or grammar issues were found.")
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            label.setContentsMargins(20, 30, 20, 30)
            self._grammar_list_layout.addWidget(label)
        for match in matches:
            self._grammar_list_layout.addWidget(
                self._build_issue_row(doc, checked, full_text, match)
            )
        self._grammar_list_layout.addStretch(1)
        if self._grammar_fix_button is not None:
            self._grammar_fix_button.setEnabled(
                any(match.get("replacements") for match in matches)
            )

    def _grammar_detail_text(self, text_length, checked_length):
        host = urllib.parse.urlparse(GRAMMAR_URL).netloc or GRAMMAR_URL
        detail = "Checked with LanguageTool. Text is sent to %s." % host
        if text_length > checked_length:
            detail += " Only the first %s characters were checked." % format(
                checked_length, ","
            )
        return detail

    def _build_grammar_dialog(self, doc, text, checked, matches):
        dialog = QDialog(self)
        dialog.setWindowTitle("Spelling & Grammar")
        dialog.resize(820, 600)
        dialog.setModal(False)
        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(16, 14, 16, 10)
        layout.setSpacing(10)

        self._grammar_count = QLabel(dialog)
        self._grammar_count.setObjectName("grammarCount")
        self._grammar_count.setTextFormat(Qt.TextFormat.RichText)
        self._grammar_count.setAlignment(Qt.AlignmentFlag.AlignLeft)
        self._grammar_detail = QLabel(dialog)
        self._grammar_detail.setObjectName("grammarDetail")
        self._grammar_detail.setWordWrap(True)
        self._grammar_detail.setAlignment(Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(self._grammar_count)
        layout.addWidget(self._grammar_detail)

        scroller = QScrollArea(dialog)
        scroller.setObjectName("grammarScroll")
        scroller.setFrameShape(QFrame.Shape.NoFrame)
        scroller.setWidgetResizable(True)
        scroller.viewport().setAutoFillBackground(True)
        scroller.viewport().setBackgroundRole(QPalette.ColorRole.Window)
        content = QWidget(scroller)
        content.setObjectName("grammarContent")
        content.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        content.setAutoFillBackground(True)
        content.setBackgroundRole(QPalette.ColorRole.Window)
        self._grammar_list_layout = QVBoxLayout(content)
        self._grammar_list_layout.setContentsMargins(10, 8, 10, 8)
        self._grammar_list_layout.setSpacing(8)
        scroller.setWidget(content)
        layout.addWidget(scroller, 1)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        close_button = QPushButton("Close", dialog)
        close_button.clicked.connect(lambda: self._close_grammar_dialog(dialog))
        self._grammar_fix_button = QPushButton("Fix All", dialog)
        self._grammar_fix_button.setDefault(True)
        self._grammar_fix_button.clicked.connect(
            lambda: self._apply_all_grammar_fixes(
                self._grammar_doc, self._grammar_text, list(self._grammar_matches), dialog
            )
        )
        buttons.addWidget(close_button)
        buttons.addWidget(self._grammar_fix_button)
        layout.addLayout(buttons)

        self._grammar_dialog = dialog
        self._grammar_doc = doc
        dialog.finished.connect(lambda _result, d=dialog: self._on_grammar_dialog_finished(d))
        self._render_grammar_matches(doc, checked, matches, text)
        dialog.show()
        dialog.raise_()
        dialog.activateWindow()

    def _refresh_grammar_dialog(self, doc, dialog):
        if dialog is None or dialog is not self._grammar_dialog:
            return
        if doc not in self.docs:
            self._close_grammar_dialog(dialog)
            return
        self._grammar_doc = doc
        text = doc.text()
        if not text.strip():
            self._render_grammar_matches(doc, "", [], text)
            return
        checked = text[:GRAMMAR_MAX_CHARS]
        self._grammar_checking = True
        if doc is self.doc:
            self.state_label.setText("Checking spelling & grammar…")
        self._set_grammar_status("Checking…", "Re-checking after applying a fix…")
        self._clear_grammar_rows()
        worker = threading.Thread(
            target=self._grammar_worker,
            args=(doc, text, checked, dialog),
            daemon=True,
        )
        worker.start()

    def _build_issue_row(self, doc, text, full_text, match):
        card = GrammarCard()
        card.setObjectName("issueCard")
        card.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(4)

        message = QLabel()
        message.setTextFormat(Qt.TextFormat.RichText)
        message.setText("<b>%s</b>" % html.escape(match.get("message", "Issue")))
        message.setWordWrap(True)
        message.setAlignment(Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(message)

        context = QLabel()
        context.setObjectName("grammarContext")
        context.setTextFormat(Qt.TextFormat.RichText)
        context.setText(self._issue_markup(text, match))
        context.setWordWrap(True)
        context.setAlignment(Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(context)

        replacements = [
            item.get("value", "")
            for item in (match.get("replacements") or [])
            if item.get("value")
        ]
        controls = QHBoxLayout()
        controls.setContentsMargins(0, 4, 0, 0)
        if replacements:
            combo = QComboBox()
            for value in replacements[:10]:
                combo.addItem(value)
            combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            apply = QPushButton("Apply")
            apply.setDefault(False)
            apply.clicked.connect(
                lambda _checked=False, c=combo: self._apply_grammar_fix(
                    doc, full_text, match, c.currentText()
                )
            )
            controls.addWidget(combo, 1)
            controls.addWidget(apply, 0)
        else:
            note = QLabel("No automatic suggestion")
            note.setObjectName("grammarDetail")
            controls.addWidget(note, 1)
        layout.addLayout(controls)
        return card

    def _clear_grammar_highlights(self, doc):
        if doc is None:
            return
        doc.grammar_matches = []
        doc.editor.setExtraSelections([])

    def _highlight_grammar_issues(self, doc, matches):
        doc.grammar_matches = list(matches)
        self._apply_grammar_highlights(doc)

    def _apply_grammar_highlights(self, doc):
        selections = []
        if not doc.grammar_matches:
            doc.editor.setExtraSelections(selections)
            return
        underline, background = self._grammar_colors()
        length = doc.editor.document().characterCount()
        for match in doc.grammar_matches:
            try:
                offset = int(match.get("qt_offset", -1))
                span = int(match.get("qt_length", 0))
            except (TypeError, ValueError):
                continue
            if offset < 0 or span <= 0 or offset + span > length:
                continue
            selection = QTextEdit.ExtraSelection()
            cursor = QTextCursor(doc.editor.document())
            cursor.setPosition(offset)
            cursor.setPosition(offset + span, QTextCursor.MoveMode.KeepAnchor)
            fmt = QTextCharFormat()
            fmt.setUnderlineStyle(QTextCharFormat.UnderlineStyle.SpellCheckUnderline)
            fmt.setUnderlineColor(underline)
            fmt.setBackground(background)
            selection.format = fmt
            selection.cursor = cursor
            selections.append(selection)
        doc.editor.setExtraSelections(selections)

    def _reapply_grammar_highlights(self):
        for doc in self.docs:
            if doc.grammar_matches:
                self._apply_grammar_highlights(doc)

    def _normalise_grammar_offsets(self, text, matches):
        """LanguageTool counts UTF-16 units. Keep both Qt and Python offsets."""
        for match in matches:
            try:
                start = int(match.get("offset", 0))
                length = int(match.get("length", 0))
            except (TypeError, ValueError):
                continue
            start_index = self._utf16_to_index(text, start)
            end_index = self._utf16_to_index(text, start + length)
            match["qt_offset"] = max(0, start)
            match["qt_length"] = max(0, length)
            match["offset"] = start_index
            match["length"] = max(0, end_index - start_index)

    def _utf16_to_index(self, text, units):
        if units <= 0:
            return 0
        count = 0
        for index, char in enumerate(text):
            if count >= units:
                return index
            count += 2 if ord(char) > 0xFFFF else 1
        return len(text)

    def _issue_markup(self, text, match):
        try:
            offset = max(0, int(match.get("offset", 0)))
            length = max(0, int(match.get("length", 0)))
        except (TypeError, ValueError):
            offset, length = 0, 0
        offset = min(offset, len(text))
        length = min(length, len(text) - offset)
        start = max(0, offset - 42)
        end = min(len(text), offset + length + 42)
        prefix = text[start:offset].replace("\n", " ")
        issue = text[offset : offset + length].replace("\n", " ")
        suffix = text[offset + length : end].replace("\n", " ")
        return "<small>%s%s<b>%s</b>%s%s</small>" % (
            "…" if start > 0 else "",
            html.escape(prefix),
            html.escape(issue),
            html.escape(suffix),
            "…" if end < len(text) else "",
        )

    def _apply_grammar_fix(self, doc, expected_text, match, replacement):
        if not replacement:
            return
        dialog = self._grammar_dialog
        if doc not in self.docs:
            self._close_grammar_dialog(dialog)
            return
        if doc.text() != expected_text:
            self._refresh_grammar_dialog(doc, dialog)
            return
        try:
            qt_offset = int(match.get("qt_offset", -1))
            qt_length = int(match.get("qt_length", 0))
        except (TypeError, ValueError):
            qt_offset, qt_length = -1, 0
        if qt_offset < 0:
            self._refresh_grammar_dialog(doc, dialog)
            return
        self._select_document(doc)
        editor = doc.editor
        cursor = editor.textCursor()
        cursor.beginEditBlock()
        cursor.setPosition(qt_offset)
        cursor.setPosition(qt_offset + qt_length, QTextCursor.MoveMode.KeepAnchor)
        cursor.insertText(replacement)
        cursor.endEditBlock()
        editor.setTextCursor(cursor)
        if dialog is not None and dialog is self._grammar_dialog:
            self._refresh_grammar_dialog(doc, dialog)

    def _apply_all_grammar_fixes(self, doc, expected_text, matches, dialog):
        if dialog is None or dialog is not self._grammar_dialog:
            return
        if doc not in self.docs:
            self._close_grammar_dialog(dialog)
            return
        if doc.text() != expected_text:
            self._refresh_grammar_dialog(doc, dialog)
            return
        fixes = []
        for match in matches:
            replacements = match.get("replacements") or []
            if not replacements:
                continue
            try:
                offset = int(match.get("offset", -1))
                length = int(match.get("length", 0))
                qt_offset = int(match.get("qt_offset", -1))
                qt_length = int(match.get("qt_length", 0))
            except (TypeError, ValueError):
                continue
            if offset < 0 or offset + length > len(expected_text):
                continue
            fixes.append(
                (offset, length, qt_offset, qt_length, replacements[0].get("value", ""))
            )
        if not fixes:
            return
        fixes.sort(key=lambda item: item[0])
        filtered = []
        boundary = -1
        for fix in fixes:
            if fix[0] >= boundary:
                filtered.append(fix)
                boundary = fix[0] + fix[1]
        filtered.sort(key=lambda item: item[2], reverse=True)
        self._select_document(doc)
        editor = doc.editor
        cursor = editor.textCursor()
        cursor.beginEditBlock()
        for _offset, _length, qt_offset, qt_length, replacement in filtered:
            cursor.setPosition(qt_offset)
            cursor.setPosition(qt_offset + qt_length, QTextCursor.MoveMode.KeepAnchor)
            cursor.insertText(replacement)
        cursor.endEditBlock()
        editor.setTextCursor(cursor)
        self._refresh_grammar_dialog(doc, dialog)

    def _close_grammar_dialog(self, dialog):
        if dialog is None:
            return
        if self._grammar_dialog is dialog:
            self._grammar_dialog = None
            self._grammar_list_layout = None
            self._grammar_count = None
            self._grammar_detail = None
            self._grammar_fix_button = None
            self._grammar_doc = None
            self._grammar_text = ""
            self._grammar_matches = []
        dialog.close()
        dialog.deleteLater()

    def _on_grammar_dialog_finished(self, dialog):
        if self._grammar_dialog is dialog:
            self._grammar_dialog = None
            self._grammar_list_layout = None
            self._grammar_count = None
            self._grammar_detail = None
            self._grammar_fix_button = None
            self._grammar_doc = None
            self._grammar_text = ""
            self._grammar_matches = []
        dialog.deleteLater()

    # ----------------------------------------------------------- export ---

    def _on_export(self, *_args):
        doc = self.doc
        if doc is None:
            return
        path = self._choose_export(doc)
        if not path:
            return
        if not os.path.splitext(path)[1] and not os.path.isfile(path):
            candidate = path + ".html"
            if os.path.isfile(candidate) and not _dialog_replace(self, candidate):
                return
            path = candidate
        name = os.path.basename(doc.path) if doc.path else (doc.label or "Untitled")
        document = build_export_html(os.path.splitext(name)[0], doc.text())
        try:
            _atomic_write(path, document)
        except OSError as error:
            _dialog_error(self, "Could not export %s\n\n%s" % (path, error))

    # ----------------------------------------------------------- dialogs ---

    def _choose_open(self):
        paths, _filter = QFileDialog.getOpenFileNames(
            self,
            "Open Markdown File",
            self._last_dir,
            "Markdown files (*.md *.markdown *.mdown *.mkd *.txt);;All files (*)",
        )
        if paths:
            self._last_dir = os.path.dirname(paths[-1])
        return paths

    def _choose_save(self, doc=None):
        doc = doc or self.doc
        path = doc.path if doc is not None else None
        if path:
            start = path
        else:
            start = os.path.join(self._last_dir, "untitled.md")
        chosen, _filter = QFileDialog.getSaveFileName(
            self,
            "Save Markdown File",
            start,
            "Markdown files (*.md *.markdown *.mdown *.mkd *.txt);;All files (*)",
        )
        if chosen:
            self._last_dir = os.path.dirname(chosen)
        return chosen or None

    def _choose_export(self, doc=None):
        doc = doc or self.doc
        path = doc.path if doc is not None else None
        base = os.path.splitext(os.path.basename(path))[0] if path else "untitled"
        start = os.path.join(self._last_dir, base + ".html")
        chosen, _filter = QFileDialog.getSaveFileName(
            self,
            "Export as HTML",
            start,
            "HTML files (*.html);;All files (*)",
        )
        if chosen:
            self._last_dir = os.path.dirname(chosen)
        return chosen or None

    def _maybe_save(self, doc=None):
        doc = doc or self.doc
        if doc is None or not doc.is_modified():
            return True
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Warning)
        box.setWindowTitle("Save changes?")
        box.setText("“%s” has unsaved changes." % doc.display_name)
        box.setInformativeText(
            "Your changes will be lost if you don’t save them."
        )
        box.setStandardButtons(
            QMessageBox.StandardButton.Save
            | QMessageBox.StandardButton.Discard
            | QMessageBox.StandardButton.Cancel
        )
        box.setDefaultButton(QMessageBox.StandardButton.Save)
        response = box.exec()
        if response == QMessageBox.StandardButton.Save:
            return self._save(doc=doc)
        return response == QMessageBox.StandardButton.Discard

    # -------------------------------------------------------------- status ---

    def _on_text_changed(self, doc):
        if self._loading or doc is not self.doc:
            return
        self._clear_grammar_highlights(doc)
        self._update_stats()
        self._update_header()
        self._schedule_preview()
        self._schedule_autosave()

    def _on_cursor_changed(self, doc):
        if doc is self.doc:
            self._update_cursor()

    def _on_modification_changed(self, doc):
        if self._loading:
            return
        if doc is self.doc:
            self._update_header()
        else:
            self._update_tabs()

    def _update_header(self):
        if self.doc is None:
            return
        doc = self.doc
        name = doc.display_name
        modified = doc.is_modified()
        self.setWindowTitle("%s[*] — %s" % (name, APP_NAME))
        self.setWindowModified(modified)
        self.setWindowFilePath(doc.path or "")
        if modified:
            self.state_label.setText("Edited")
        elif doc.path:
            self.state_label.setText("Saved")
        else:
            self.state_label.setText("Not saved")
        self._update_tabs()

    def _update_tabs(self):
        for index, doc in enumerate(self.docs):
            if index >= self.tabs.count():
                break
            name = doc.display_name
            if doc.is_modified():
                name = "• " + name
            self.tabs.setTabText(index, name)
            self.tabs.setTabToolTip(index, doc.path or "Not saved yet")

    def _update_stats(self):
        if self.doc is None:
            return
        text = self.doc.text()
        words = len(text.split())
        characters = len(text)
        lines = text.count("\n") + 1 if text else 1
        word_label = "word" if words == 1 else "words"
        line_label = "line" if lines == 1 else "lines"
        self.stats_label.setText(
            "%s %s · %s characters · %s %s"
            % (
                format(words, ","),
                word_label,
                format(characters, ","),
                format(lines, ","),
                line_label,
            )
        )

    def _update_cursor(self):
        if self.doc is None:
            return
        cursor = self.doc.editor.textCursor()
        self.cursor_label.setText(
            "Ln %s, Col %s"
            % (format(cursor.blockNumber() + 1, ","), format(cursor.positionInBlock() + 1, ","))
        )

    # --------------------------------------------------------------- misc ---

    def _reset_preview(self):
        self._preview_ready = False
        self._load_preview_shell()

    def _apply_wrap_to_all(self):
        mode = (
            QPlainTextEdit.LineWrapMode.WidgetWidth
            if self._wrap_enabled
            else QPlainTextEdit.LineWrapMode.NoWrap
        )
        for doc in self.docs:
            doc.editor.setLineWrapMode(mode)

    def _on_wrap_toggled(self, checked):
        self._wrap_enabled = bool(checked)
        self._apply_wrap_to_all()
        self._settings.setValue("view/wrap", self._wrap_enabled)

    def _toggle_fullscreen(self, *_args):
        if self.isFullScreen():
            self.showNormal()
            self.act["fullscreen"].setText("Enter Full Screen")
        else:
            self.showFullScreen()
            self.act["fullscreen"].setText("Leave Full Screen")

    def _toggle_zoom(self, *_args):
        if self.isMaximized():
            self.showNormal()
        else:
            self.showMaximized()

    def _remember_recent(self, path):
        path = os.path.realpath(os.path.abspath(path))
        self._recent = [item for item in self._recent if os.path.realpath(item) != path]
        self._recent.insert(0, path)
        self._recent = self._recent[:10]
        self._refresh_recent_menu()
        self._settings.setValue("files/recent", self._recent)

    def _refresh_recent_menu(self):
        if not hasattr(self, "recent_menu"):
            return
        self.recent_menu.clear()
        existing = [path for path in self._recent if os.path.isfile(path)]
        if not existing:
            empty = self.recent_menu.addAction("No Recent Files")
            empty.setEnabled(False)
            return
        for path in existing:
            label = os.path.basename(path)
            action = self.recent_menu.addAction(label)
            action.setToolTip(path)
            action.triggered.connect(
                lambda _checked=False, p=path: self._open_path(p)
            )
        self.recent_menu.addSeparator()
        clear = self.recent_menu.addAction("Clear Menu")
        clear.triggered.connect(self._clear_recent)

    def _clear_recent(self):
        self._recent = []
        self._settings.setValue("files/recent", [])
        self._refresh_recent_menu()

    def _show_about(self, *_args):
        _dialog_info(
            self,
            "%s %s\n\n"
            "A small, fast Markdown editor with tabs and a live preview.\n"
            "Write on the left, see the result on the right.\n\n"
            "Built with Python, Qt and Qt WebEngine.\n"
            "Licensed under the MIT License."
            % (APP_NAME, APP_VERSION),
            "About Markdown Studio",
        )

    def _show_shortcuts(self, *_args):
        dialog = QDialog(self)
        dialog.setWindowTitle("Keyboard Shortcuts")
        dialog.resize(560, 540)
        layout = QVBoxLayout(dialog)
        browser = QTextBrowser(dialog)
        browser.setOpenExternalLinks(False)
        browser.setHtml(
            """
            <style>
              body { font-family: -apple-system, "SF Pro Text", sans-serif; font-size: 13px; }
              h3 { margin-top: 18px; margin-bottom: 6px; }
              td { padding: 3px 14px 3px 0; }
              td.key { font-family: "SF Mono", Menlo, monospace; white-space: nowrap; }
              td.action { }
            </style>
            <h3>Editing</h3>
            <table>
              <tr><td class="key">⌘B</td><td class="action">Bold</td></tr>
              <tr><td class="key">⌘I</td><td class="action">Italic</td></tr>
              <tr><td class="key">⇧⌘X</td><td class="action">Strikethrough</td></tr>
              <tr><td class="key">⌘E</td><td class="action">Inline code</td></tr>
              <tr><td class="key">⌘K</td><td class="action">Link</td></tr>
              <tr><td class="key">⇧⌘I</td><td class="action">Image</td></tr>
              <tr><td class="key">⌘1 / ⌘2 / ⌘3</td><td class="action">Heading 1 / 2 / 3</td></tr>
              <tr><td class="key">⇧⌘8 / ⇧⌘7</td><td class="action">Bulleted / numbered list</td></tr>
              <tr><td class="key">⇧⌘9</td><td class="action">Block quote</td></tr>
              <tr><td class="key">⇧⌘C</td><td class="action">Code block</td></tr>
              <tr><td class="key">⌘Z / ⇧⌘Z</td><td class="action">Undo / redo</td></tr>
            </table>
            <h3>Files</h3>
            <table>
              <tr><td class="key">⌘N</td><td class="action">New tab</td></tr>
              <tr><td class="key">⌘O</td><td class="action">Open</td></tr>
              <tr><td class="key">⌘S</td><td class="action">Save</td></tr>
              <tr><td class="key">⇧⌘S</td><td class="action">Save As</td></tr>
              <tr><td class="key">⌘W</td><td class="action">Close tab</td></tr>
              <tr><td class="key">⌃⇥ / ⌃⇧⇥</td><td class="action">Next / previous tab</td></tr>
              <tr><td class="key">⇧⌘E</td><td class="action">Export as HTML</td></tr>
            </table>
            <h3>Tools</h3>
            <table>
              <tr><td class="key">⇧⌘G</td><td class="action">Check spelling &amp; grammar</td></tr>
            </table>
            <h3>View</h3>
            <table>
              <tr><td class="key">⇧⌘P</td><td class="action">Show / hide preview</td></tr>
              <tr><td class="key">⌃⌘F</td><td class="action">Enter / leave full screen</td></tr>
              <tr><td class="key">F11</td><td class="action">Enter / leave full screen</td></tr>
            </table>
            """
        )
        layout.addWidget(browser)
        close = QPushButton("Close", dialog)
        close.clicked.connect(dialog.accept)
        row = QHBoxLayout()
        row.addStretch(1)
        row.addWidget(close)
        layout.addLayout(row)
        dialog.exec()

    # ------------------------------------------------------------- events ---

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            return
        super().dragEnterEvent(event)

    def dropEvent(self, event):
        paths = self.paths_from_mime(event.mimeData())
        if paths:
            event.acceptProposedAction()
            self.open_paths(paths)
            return
        super().dropEvent(event)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape and self.isFullScreen():
            self.showNormal()
            self.act["fullscreen"].setText("Enter Full Screen")
            return
        super().keyPressEvent(event)

    def closeEvent(self, event):
        self._flush_pending_autosave()
        self._autosave_all()
        for doc in list(self.docs):
            if doc.is_modified():
                self._select_document(doc)
                if not self._maybe_save(doc):
                    event.ignore()
                    return
        if self.doc is not None:
            self._store_active_view_state()
        self._save_preferences()
        self._shutting_down = True
        event.accept()


# -------------------------------------------------------------------- app ---

class MarkdownApplication(QApplication):
    openFiles = Signal(list)

    def __init__(self, argv):
        super().__init__(argv)
        self.window = None
        self._pending_paths = []

    def event(self, event):
        if event.type() == QEvent.Type.FileOpen:
            path = event.file()
            if path:
                if self.window is not None:
                    self.window.open_paths([path])
                else:
                    self._pending_paths.append(path)
            return True
        return super().event(event)

    def attach_window(self, window):
        self.window = window
        pending, self._pending_paths = self._pending_paths, []
        if pending:
            window.open_paths(pending)


def main(argv=None):
    argv = list(sys.argv if argv is None else argv)
    QCoreApplication.setAttribute(
        Qt.ApplicationAttribute.AA_ShareOpenGLContexts, True
    )
    app = MarkdownApplication(argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationDisplayName(APP_NAME)
    app.setApplicationVersion(APP_VERSION)
    app.setOrganizationName("Markdown Studio")
    app.setOrganizationDomain("github.com/markdownstudio")
    app.setDesktopFileName(APP_ID)
    app.setWindowIcon(QIcon(ICON_PATH))
    app.setStyleSheet(APP_CSS)
    app.setQuitOnLastWindowClosed(True)

    window = MarkdownWindow()
    app.attach_window(window)
    window.show()

    paths = [
        arg
        for arg in argv[1:]
        if not arg.startswith("-") and os.path.isfile(os.path.expanduser(arg))
    ]
    if paths:
        window.open_paths(paths)
    window.raise_()
    window.activateWindow()
    if window.doc is not None:
        window.doc.editor.setFocus()
    code = app.exec()
    try:
        sys.stdout.flush()
        sys.stderr.flush()
    except Exception:
        pass
    # Qt WebEngine and PySide can crash while destroying widgets during
    # Python finalization after the event loop has already finished.  All
    # settings and files have been saved by closeEvent, so exit directly.
    os._exit(code)


if __name__ == "__main__":
    sys.exit(main())
