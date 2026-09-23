import re
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any

import sublime
import sublime_plugin

from ..emmet.abbreviation import parse as markup_parse
from ..emmet.config import Config
from ..emmet.css_abbreviation import parse as stylesheet_parse
from . import emmet_sublime as emmet
from . import syntax, utils
from .config import get_config
from .context import get_html_context

re_indent = re.compile(r"^\s+")


@dataclass
class WrapEntry:
    "A region to wrap and the Emmet config for it (unpacks as `region, config`)"

    region: sublime.Region
    config: Config

    def __iter__(self) -> Iterator[Any]:
        yield self.region
        yield self.config


class WrapAbbreviationInputHandler(sublime_plugin.TextInputHandler):
    def __init__(
        self,
        view: sublime.View,
        wrap_entries: list[WrapEntry],
        initial_abbr: str | None = None,
        preview: bool = False,
    ) -> None:
        self.view = view
        self.wrap_entries = wrap_entries
        self.instant_preview = preview
        self.initial_abbr = initial_abbr

    def placeholder(self) -> str:
        return "Enter abbreviation"

    def initial_text(self) -> str:
        return self.initial_abbr or ""

    def validate(self, text: str, event: Any = None) -> bool:
        try:
            config = self.wrap_entries[0].config if self.wrap_entries else None
            if config and config.type == "stylesheet":
                stylesheet_parse(text, config)
            else:
                markup_parse(text, config)
            return True
        # The parsers signal invalid input with their own exception types.
        except Exception:  # noqa: BLE001
            return False

    def cancel(self) -> None:
        undo_preview(self.view)

    def confirm(self, text: str, event: Any = None) -> None:
        undo_preview(self.view)

    def preview(self, text: str) -> str | sublime.Html:
        abbr = text.strip()
        snippet = None

        undo_preview(self.view)

        if abbr:
            try:
                preview_items = []
                for region, config in self.wrap_entries:
                    result = emmet.expand(abbr, config)
                    if self.instant_preview:
                        preview_items.append((region.begin(), region.end(), result))

                if preview_items:
                    self.view.run_command(
                        "emmet_wrap_with_abbreviation_preview", {"items": preview_items}
                    )
            except Exception:  # noqa: BLE001 - see validate()
                snippet = '<div class="error">Invalid abbreviation</div>'

        if snippet:
            return sublime.Html(popup_content(snippet))

        return ""  # no preview (Sublime treats "" and None the same)


def in_range(region: sublime.Region, pt: int) -> bool:
    return region.begin() < pt < region.end()


def get_content(view: sublime.View, region: sublime.Region, lines: bool = False) -> Any:
    "Returns contents of given region, properly de-indented"
    base_line = view.substr(view.line(region.begin()))
    m = re_indent.match(base_line)
    indent = m.group(0) if m else ""
    src_lines = view.substr(region).splitlines()
    dest_lines = []

    for line in src_lines:
        if dest_lines and line.startswith(indent):
            line = line[len(indent) :]
        dest_lines.append(utils.escape_snippet(line))

    return dest_lines if lines else "\n".join(dest_lines)


def popup_content(content: str) -> str:
    return f"""
    <body>
        <style>
            body {{ font-size: 0.8rem; }}
            .error {{ color: red }}
        </style>
        <div>{content}</div>
    </body>
    """


def get_wrap_region(view: sublime.View, sel: sublime.Region, config: Config) -> sublime.Region:
    "Returns region to wrap with abbreviation"
    if sel.empty():
        # No selection means user wants to wrap current tag container
        pt = sel.begin()
        ctx = emmet.get_tag_context(view, pt)
        if ctx:
            # Check how given point relates to matched tag:
            # if it's in either open or close tag, we should wrap tag itself,
            # otherwise we should wrap its contents
            open_tag = ctx["open"]
            close_tag = ctx.get("close")

            if in_range(open_tag, pt) or (close_tag and in_range(close_tag, pt)):
                return sublime.Region(
                    open_tag.begin(), close_tag.end() if close_tag else open_tag.end()
                )

            if close_tag:
                r = sublime.Region(open_tag.end(), close_tag.begin())
                next_region = utils.narrow_to_non_space(view, r)

                # On the right side of tag contents, we should skip new lines only
                # and trim spaces at the end of line
                padding = view.substr(sublime.Region(next_region.end(), r.end()))
                ix = padding.find("\n")
                end = next_region.end() + ix if ix != -1 else r.end()
                return sublime.Region(next_region.begin(), end)

    return utils.narrow_to_non_space(view, sel, utils.NON_SPACE_LEFT)


def undo_preview(view: sublime.View) -> None:
    last_command = view.command_history(0, True)[0]
    if last_command == "emmet_wrap_with_abbreviation_preview":
        view.run_command("undo")


def get_wrap_config(view: sublime.View, pos: int) -> Config:
    syntax_name = syntax.doc_syntax(view)
    config = get_config(view, pos)
    config.syntax = syntax_name
    config.type = "markup"
    if syntax.is_html(syntax_name):
        config.context = get_html_context(view, pos)

    return config
