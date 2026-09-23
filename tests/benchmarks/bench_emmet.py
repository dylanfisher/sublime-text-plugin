"""Emmet benchmarks. Runs inside Sublime Text (see harness.py).

$SCRATCH/tools/st-run.sh tests/benchmarks/bench_emmet.py --timeout 180 \
    -- --case type_first --size 10k --out before-type_first-10k.json

One case at one fixture size per call (see main()); tests/benchmarks/run_all.sh
runs them all and merges the JSON.

Listener rows call the listener objects directly. Emmet's real listeners are
detached while the fixtures are edited, so only the timed call touches Emmet
state. Commands run through view.run_command. The user's merged
Emmet.sublime-settings apply, except where a row says otherwise; settings are
changed in memory only and restored afterwards (never saved).
"""

import runpy
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

import sublime
import sublime_plugin

H = runpy.run_path(str(Path(__file__).with_name("harness.py")))
PKG = "Emmet"
_sp: Any = sublime_plugin

HTML = "Packages/HTML/HTML.sublime-syntax"
CSS = "Packages/CSS/CSS.sublime-syntax"
JSX = "Packages/JavaScript/JSX.sublime-syntax"
PYTHON = "Packages/Python/Python.sublime-syntax"

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


def html_text(lines: int) -> str:
    """Deterministic HTML page with about `lines` lines. Every 6th line is blank."""
    out = ["<!DOCTYPE html>", "<html>", "<head>", "  <title>Bench</title>", "</head>", "<body>"]
    i = 0
    while len(out) < lines - 2:
        out += [
            f'  <div class="item item-{i}" id="id{i}" data-n="{i}">',
            f'    <p>Paragraph {i} with <a href="/x/{i}">a link</a> and <span>text</span></p>',
            "    <ul><li>one</li><li>two</li></ul>",
            f'    <img src="img{i}.png" alt="">',
            "    ",
            "  </div>",
        ]
        i += 1
    out += ["</body>", "</html>"]
    return "\n".join(out) + "\n"


def css_text(lines: int) -> str:
    """CSS fixture with a `.bench {}` block (blank line inside) in the middle."""
    body = H["fixture_text"](lines - 3, "css").splitlines()
    mid = len(body) // 2
    return "\n".join([*body[:mid], ".bench {", "  ", "}", *body[mid:]]) + "\n"


def jsx_text(lines: int) -> str:
    out = ["import React from 'react';", ""]
    i = 0
    while len(out) < lines:
        out += [
            f"function Item{i}(props) {{",
            f"  const value{i} = props.items.map((x) => x * {i});",
            "  return (",
            f'    <div className="item-{i}">',
            "      ",
            "    </div>",
            "  );",
            "}",
        ]
        i += 1
    return "\n".join(out) + "\n"


def modules() -> dict[str, Any]:
    return {
        "abbr": sys.modules[f"{PKG}.lib.abbreviation"],
        "main": sys.modules[f"{PKG}.main"],
    }


def emmet_listeners(view: sublime.View, event: str) -> list[Callable[..., Any]]:
    """Bound callables of Emmet's listeners for `event`, taking (view, *args)."""
    calls: list[Callable[..., Any]] = [
        getattr(obj, event) for obj in H["event_listeners"](event, f"{PKG}.")
    ]
    for obj in H["view_listeners"](view, f"{PKG}."):
        if hasattr(obj, event):
            method = getattr(obj, event)
            calls.append(lambda _view, *a, m=method: m(*a))
    return calls


class Detached:
    """Remove Emmet's EventListeners/ViewEventListeners from dispatch (not from memory)."""

    def __init__(self, views: list[sublime.View]) -> None:
        self.views = views
        self.saved: list[tuple[list[Any], Any]] = []

    def __enter__(self) -> Detached:
        lists = [_sp.all_callbacks.get(e, []) for e in EVENTS]
        lists += [_sp.view_event_listeners.get(v.view_id, []) for v in self.views]
        for lst in lists:
            for obj in list(lst):
                if type(obj).__module__.startswith(f"{PKG}."):
                    lst.remove(obj)
                    self.saved.append((lst, obj))
        return self

    def __exit__(self, *exc: object) -> None:
        for lst, obj in self.saved:
            if obj not in lst:
                lst.append(obj)


def blank_line(view: sublime.View, row: int) -> sublime.Region:
    return view.line(view.text_point(row, 0))


def find_row(view: sublime.View, needle: str, after_row: int = 0) -> int:
    r = view.find(needle, view.text_point(after_row, 0), sublime.FindFlags.LITERAL)
    return view.rowcol(r.begin())[0]


def set_line(view: sublime.View, row: int, text: str) -> int:
    """Replace line `row` with `text`, caret at its end. Returns the caret."""
    line = blank_line(view, row)
    view.sel().clear()
    view.sel().add(line)
    view.run_command("insert", {"characters": text})
    return view.sel()[0].b


def caret(view: sublime.View, pt: int) -> None:
    view.sel().clear()
    view.sel().add(pt)


def arg(name: str, default: str | None = None) -> str | None:
    return sys.argv[sys.argv.index(name) + 1] if name in sys.argv else default


# --runs/--warmup override the harness defaults (20/3) for dry runs only.
RUN_KW: dict[str, int] = {}
if arg("--runs"):
    RUN_KW["runs"] = int(arg("--runs") or 20)
if arg("--warmup"):
    RUN_KW["warmup"] = int(arg("--warmup") or 3)


class Ctx:
    """One fixture view plus the Emmet modules, for one case at one size."""

    def __init__(self, bench: Any, window: sublime.Window, kind: str, size: str) -> None:
        self.bench = bench
        n = H["SIZES"][size]
        text, syntax = {
            "html": (html_text, HTML),
            "css": (css_text, CSS),
            "jsx": (jsx_text, JSX),
            "python": (lambda n: H["fixture_text"](n), PYTHON),
        }[kind]
        self.view = H["scratch_view"](window, text(n), syntax)
        self.view.settings().set("auto_match_enabled", False)
        self.view.settings().set("auto_indent", False)
        self.abbr = modules()["abbr"]
        self.label = f"{kind} {size}"
        # Resolve listeners now: Detached() hides them from all_callbacks later.
        self.calls = {e: emmet_listeners(self.view, e) for e in EVENTS}
        self.objs = {e: H["event_listeners"](e, f"{PKG}.") for e in EVENTS}

    def time(self, name: str, fn: Callable[[Any], Any], setup: Callable[[], Any]) -> None:
        self.bench.time(f"{name} ({self.label})", fn, setup=setup, **RUN_KW)

    def reset(self, pos: int) -> None:
        self.abbr.stop_tracking(self.view, {"force": True})
        self.abbr.set_last_pos(self.view, pos - 1)

    def typed(self, row: int, text: str) -> Callable[[], sublime.View]:
        """Setup: line `row` now holds `text` (last char just typed), no tracker."""

        def setup() -> sublime.View:
            self.reset(set_line(self.view, row, text))
            return self.view

        return setup

    def at(self, pt: int) -> Callable[[], sublime.View]:
        return lambda: (caret(self.view, pt), self.view)[1]

    def listeners(self, event: str) -> Callable[[Any], Any]:
        calls = self.calls[event]
        return lambda v: [f(v) for f in calls]

    def mid_blank_row(self, needle: str = "    \n") -> int:
        return find_row(self.view, needle, self.view.rowcol(self.view.size())[0] // 2)


def case_type_first(c: Ctx) -> None:
    kind = c.label.split()[0]
    row, text = {
        "html": (c.mid_blank_row(), "    u"),
        "css": (c.mid_blank_row(".bench {") + 1, "  p"),
        "jsx": (c.mid_blank_row("      \n"), "      <d"),
        "python": (c.mid_blank_row(), "    u"),
    }[kind]
    c.time("on_modified: type 1st abbr char", c.listeners("on_modified"), c.typed(row, text))


def case_type_second(c: Ctx) -> None:
    row = c.mid_blank_row()
    on_mod = c.calls["on_modified"]

    def setup() -> sublime.View:
        c.reset(set_line(c.view, row, "    u"))
        for f in on_mod:
            f(c.view)
        c.view.run_command("insert", {"characters": "l"})
        return c.view

    c.time("on_modified: type 2nd abbr char", c.listeners("on_modified"), setup)


def case_type_in_tag(c: Ctx) -> None:
    row = c.mid_blank_row() - 1  # the <img ...> line

    def setup() -> sublime.View:
        pos = blank_line(c.view, row).begin() + 9
        caret(c.view, pos)
        c.view.run_command("insert", {"characters": "x"})
        c.reset(pos + 1)
        return c.view

    c.time("on_modified: type inside a tag", c.listeners("on_modified"), setup)


def case_move(c: Ctx) -> None:
    pt = c.view.text_point(c.mid_blank_row() - 3, 8)
    c.time("on_selection_modified: move caret", c.listeners("on_selection_modified"), c.at(pt))


def case_move_in_abbr(c: Ctx) -> None:
    row = c.mid_blank_row()

    def setup() -> sublime.View:
        pos = set_line(c.view, row, "    ul>li")
        c.reset(pos)
        c.abbr.suggest_abbreviation_tracker(c.view, pos)
        caret(c.view, pos - 1)
        return c.view

    c.time("on_selection_modified: caret in abbr", c.listeners("on_selection_modified"), setup)


def case_completions(c: Ctx) -> None:
    row = c.mid_blank_row()
    qc = c.calls["on_query_completions"]
    objs = c.objs["on_query_completions"]

    def setup() -> Any:
        pos = set_line(c.view, row, "    ul>li")
        c.reset(pos)
        for obj in objs:
            obj.pending_completions_request = True
        return pos

    c.time(
        "on_query_completions: after ul>li",
        lambda pos: [f(c.view, "li", [pos]) for f in qc],
        setup,
    )


def case_tab_context(c: Ctx) -> None:
    row = c.mid_blank_row()
    qx = c.calls["on_query_context"]
    keys = ("emmet_abbreviation", "emmet_activation_scope", "emmet_multicursor_tab_expand")
    c.time(
        "on_query_context: Tab key contexts",
        lambda v: [f(v, k, 0, True, False) for f in qx for k in keys],
        c.typed(row, "    ul>li"),
    )


def case_activated(c: Ctx) -> None:
    c.time("on_activated", c.listeners("on_activated"), lambda: c.view)


def _tag_preview(c: Ctx, name: str, pt: int) -> None:
    settings = sublime.load_settings("Emmet.sublime-settings")
    old = (settings.get("tag_preview"), settings.get("tag_preview_size_limit"))
    settings.set("tag_preview", True)
    settings.set("tag_preview_size_limit", 0)
    try:
        c.time(name, c.listeners("on_selection_modified_async"), c.at(pt))
    finally:
        settings.set("tag_preview", old[0])
        settings.set("tag_preview_size_limit", old[1])
        c.view.erase_phantoms("emmet_tag_preview")


def case_tag_preview_text(c: Ctx) -> None:
    _tag_preview(c, "tag preview on: caret in text", c.view.text_point(c.mid_blank_row() - 4, 8))


def case_tag_preview_close(c: Ctx) -> None:
    pt = c.view.find("</div>", c.view.text_point(c.mid_blank_row(), 0), sublime.FindFlags.LITERAL)
    _tag_preview(c, "tag preview on: caret in close tag", pt.begin() + 3)


def case_cmd_expand(c: Ctx) -> None:
    css = c.label.startswith("css")
    row = c.mid_blank_row(".bench {") + 1 if css else c.mid_blank_row()
    c.time(
        f"cmd emmet_expand_abbreviation {'p10' if css else 'ul>li*3'}",
        lambda v: v.run_command("emmet_expand_abbreviation"),
        c.typed(row, "  p10" if css else "    ul>li*3"),
    )


def case_cmd_balance(c: Ctx) -> None:
    pt = c.view.find("<p>Paragraph", c.view.text_point(c.mid_blank_row(), 0)).begin() + 8
    c.time(
        "cmd emmet_balance outward",
        lambda v: v.run_command("emmet_balance", {"direction": "outward"}),
        c.at(pt),
    )


def _div_pt(c: Ctx) -> int:
    return c.view.find("<div class", c.view.text_point(c.mid_blank_row(), 0)).begin() + 2


def case_cmd_tag_pair(c: Ctx) -> None:
    c.time(
        "cmd emmet_go_to_tag_pair",
        lambda v: v.run_command("emmet_go_to_tag_pair"),
        c.at(_div_pt(c)),
    )


def case_cmd_rename(c: Ctx) -> None:
    c.time("cmd emmet_rename_tag", lambda v: v.run_command("emmet_rename_tag"), c.at(_div_pt(c)))


def case_reference(c: Ctx) -> None:
    c.time(
        "reference: 1x native move by characters",
        lambda v: v.run_command("move", {"by": "characters", "forward": True}),
        c.at(1000),
    )


# case name -> (fixture kind, function)
CASES: dict[str, tuple[str, Callable[[Ctx], None]]] = {
    "type_first": ("html", case_type_first),
    "type_first_css": ("css", case_type_first),
    "type_first_jsx": ("jsx", case_type_first),
    "type_first_python": ("python", case_type_first),
    "type_second": ("html", case_type_second),
    "type_in_tag": ("html", case_type_in_tag),
    "move": ("html", case_move),
    "move_python": ("python", case_move),
    "move_in_abbr": ("html", case_move_in_abbr),
    "completions": ("html", case_completions),
    "tab_context": ("html", case_tab_context),
    "activated": ("html", case_activated),
    "tag_preview_text": ("html", case_tag_preview_text),
    "tag_preview_close": ("html", case_tag_preview_close),
    "cmd_expand": ("html", case_cmd_expand),
    "cmd_expand_css": ("css", case_cmd_expand),
    "cmd_balance": ("html", case_cmd_balance),
    "cmd_tag_pair": ("html", case_cmd_tag_pair),
    "cmd_rename": ("html", case_cmd_rename),
    "reference": ("html", case_reference),
}


def main(window: sublime.Window) -> None:
    """One case at one size per call: -- --case NAME --size small|10k|100k --out FILE.

    `--case load` times the plugin reload instead. Every call stays well under a
    minute so the editor is never blocked for long (see PERFORMANCE.md).
    """
    bench = H["Bench"](PKG)
    case = arg("--case") or "load"
    if case == "load":
        bench.reload_time(f"{PKG}.main", **RUN_KW)
        bench.save()
        return
    kind, fn = CASES[case]
    ctx = Ctx(bench, window, kind, arg("--size") or "small")
    try:
        with Detached([ctx.view]):
            fn(ctx)
    finally:
        ctx.abbr.dispose_editor(ctx.view)
        H["close_views"](ctx.view)
    bench.save()


if __name__ == "__main__":
    main(globals()["AGENT_WINDOW"])  # injected by st-run.sh / agent_run_script
