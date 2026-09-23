"""Shared helpers for the Emmet UnitTesting suite (not a test module)."""

from typing import Any

import sublime
import sublime_plugin
from unittesting import ViewTestCase

from ..lib import abbreviation

HTML = "Packages/HTML/HTML.sublime-syntax"
XML = "Packages/XML/XML.sublime-syntax"
CSS = "Packages/CSS/CSS.sublime-syntax"
JSX = "Packages/JavaScript/JSX.sublime-syntax"
PYTHON = "Packages/Python/Python.sublime-syntax"
TEXT = "Packages/Text/Plain text.tmLanguage"

_sp: Any = sublime_plugin
PKG = __name__.split(".")[0]
EVENTS = (
    "on_modified",
    "on_modified_async",
    "on_selection_modified",
    "on_selection_modified_async",
    "on_activated",
    "on_text_command",
    "on_post_text_command",
    "on_query_completions",
    "on_query_context",
)


def emmet_listener(cls_name: str, extra: list[Any] = ()) -> Any:  # type: ignore[assignment]
    """The registered instance of one of Emmet's EventListener classes."""
    candidates = [o for objs in _sp.all_callbacks.values() for o in objs] + list(extra)
    for obj in candidates:
        if type(obj).__name__ == cls_name and type(obj).__module__.startswith(PKG + "."):
            return obj
    raise LookupError(cls_name)


def user_settings() -> dict[str, Any]:
    try:
        value = sublime.decode_value(sublime.load_resource("Packages/User/Emmet.sublime-settings"))
    except OSError, ValueError:  # no user file (e.g. in CI)
        return {}
    return value if isinstance(value, dict) else {}


class EmmetTestCase(ViewTestCase):
    """Output-panel view with a given syntax. Emmet's real listeners are detached
    while a test runs, so only the calls a test makes touch Emmet state."""

    syntax = HTML
    view_settings = {  # noqa: RUF012 - same shape as UnitTesting's class attribute
        "detect_indentation": False,
        "translate_tabs_to_spaces": False,
        "tab_size": 4,
        "word_wrap": False,
        "auto_match_enabled": False,
        "auto_indent": False,
        "auto_complete": False,
    }
    emmet_settings: dict[str, Any] = {}  # noqa: RUF012 - read-only per class
    # Every Emmet setting a test may change; all are restored in tearDown (never saved).
    TOUCHED = (
        "auto_mark",
        "abbreviation_preview",
        "tab_expand",
        "auto_id_class",
        "multicursor_tab",
        "tag_preview",
        "tag_preview_size_limit",
        "jsx_prefix",
        "known_snippets_only",
        "toggle_comment",
        "max_data_url",
        "syntax_scopes",
        "abbreviation_scopes",
        "config",
        "wrap_size_preview",
        "marker_scope",
        "telemetry",
    )

    def setUp(self) -> None:
        self._detached: list[tuple[list[Any], Any]] = []
        for event in EVENTS:
            lst = _sp.all_callbacks.get(event, [])
            for obj in list(lst):
                if type(obj).__module__.startswith(PKG + "."):
                    lst.remove(obj)
                    self._detached.append((lst, obj))
        self.settings = sublime.load_settings("Emmet.sublime-settings")
        self._saved = {k: self.settings.get(k) for k in (*self.TOUCHED, *self.emmet_settings)}
        for k, v in self.emmet_settings.items():
            self.settings.set(k, v)
        self.view.assign_syntax(self.syntax)

    def tearDown(self) -> None:
        abbreviation.dispose_editor(self.view)
        # Put back exactly what the user's file says; erase the rest so the package
        # default shows through again. Never save_settings (the User folder syncs).
        user = user_settings()
        for k in self._saved:
            if k in user:
                self.settings.set(k, user[k])
            else:
                self.settings.erase(k)
        for lst, obj in self._detached:
            if obj not in lst:
                lst.append(obj)

    # helpers

    def set_text(self, text: str) -> None:
        """Set content. `|` marks carets (removed from the text)."""
        self.view.set_read_only(False)
        self.view.run_command("select_all")
        self.view.run_command("right_delete")
        carets = []
        clean = ""
        for ch in text:
            if ch == "|":
                carets.append(len(clean))
            else:
                clean += ch
        self.view.run_command("append", {"characters": clean, "force": True})
        sel = self.view.sel()
        sel.clear()
        for c in carets:
            sel.add(c)

    def text(self) -> str:
        return self.view.substr(sublime.Region(0, self.view.size()))

    def text_with_carets(self) -> str:
        """Content with `|` at every empty selection and `[...]` around selections."""
        text = self.text()
        marks: list[tuple[int, str]] = []
        for r in self.view.sel():
            if r.empty():
                marks.append((r.a, "|"))
            else:
                marks += [(r.begin(), "["), (r.end(), "]")]
        for pt, mark in sorted(marks, reverse=True):
            text = text[:pt] + mark + text[pt:]
        return text

    def select(self, *regions: tuple[int, int] | int) -> None:
        sel = self.view.sel()
        sel.clear()
        for r in regions:
            sel.add(sublime.Region(*r) if isinstance(r, tuple) else sublime.Region(r))

    def regions(self) -> list[tuple[int, int]]:
        return [(r.begin(), r.end()) for r in self.view.sel()]

    def listener(self, cls_name: str) -> Any:
        return emmet_listener(cls_name, [obj for _, obj in self._detached])

    def cmd(self, name: str, args: dict[str, Any] | None = None) -> None:
        self.view.run_command(name, args or {})
