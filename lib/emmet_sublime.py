import re
from collections.abc import Sequence
from typing import Any, NotRequired, TypedDict

import sublime

from .. import emmet as _emmet
from ..emmet import Config
from ..emmet import action_utils as _action_utils
from ..emmet import css_matcher as _css_matcher
from ..emmet import html_matcher as _html_matcher
from ..emmet import math_expression as _math
from ..emmet.action_utils import CSSSection, SelectItemModel
from ..emmet.extract_abbreviation import ExtractedAbbreviation
from . import syntax
from .config import get_settings
from .utils import to_region

# The vendored py-emmet annotations are loose (e.g. `config: dict` where a Config is
# passed, `-> MatchedTag` where None is returned), so its entry points are used untyped.
expand_abbreviation: Any = _emmet.expand
extract: Any = _emmet.extract
match: Any = _html_matcher.match
balanced_inward: Any = _html_matcher.balanced_inward
balanced_outward: Any = _html_matcher.balanced_outward
css_balanced_inward: Any = _css_matcher.balanced_inward
css_balanced_outward: Any = _css_matcher.balanced_outward
get_css_section: Any = _action_utils.get_css_section
select_item_css: Any = _action_utils.select_item_css
select_item_html: Any = _action_utils.select_item_html
evaluate: Any = _math.evaluate
extract_math: Any = _math.extract


class TagContext(TypedDict):
    name: str
    attributes: dict[str, str | None]
    open: sublime.Region
    close: NotRequired[sublime.Region]


class MathResult(TypedDict):
    start: int
    end: int
    result: float
    snippet: str


def escape_text(text: str, **kwargs: Any) -> str:
    "Escapes all `$` in plain text for snippet output"
    return re.sub(r"\$", "\\$", text)


def expand(abbr: str, config: Config | dict[str, Any]) -> str:
    return expand_abbreviation(abbr, config, get_settings("config"))


def balance(code: str, pos: int, direction: str, xml: bool = False) -> list[Any]:
    "Returns list of tags for balancing for given code"
    options = {"xml": xml}
    if direction == "inward":
        return balanced_inward(code, pos, options)
    return balanced_outward(code, pos, options)


def balance_css(code: str, pos: int, direction: str) -> list[Sequence[int]]:
    "Returns list of selector/property ranges for balancing for given code"
    if direction == "inward":
        return css_balanced_inward(code, pos)
    return css_balanced_outward(code, pos)


def select_item(
    code: str, pos: int, is_css: bool = False, is_previous: bool = False
) -> SelectItemModel | None:
    "Returns model for selecting next/previous item"
    if is_css:
        model = select_item_css(code, pos, is_previous)
    else:
        model = select_item_html(code, pos, is_previous)
    if model:
        model.ranges = [to_region(r) for r in model.ranges]
    return model


def css_section(code: str, pos: int, properties: bool = False) -> CSSSection | None:
    "Find enclosing CSS section and returns its ranges with (optionally) parsed properties"
    section = get_css_section(code, pos, properties)
    if section and section.properties:
        # Convert property ranges to Sublime Regions
        for p in section.properties:
            p.name = to_region(p.name)
            p.value = to_region(p.value)
            p.value_tokens = [to_region(v) for v in p.value_tokens]

    return section


def evaluate_math(code: str, pos: int, options: dict[str, Any] | None = None) -> MathResult | None:
    "Finds and evaluates math expression at given position in line"
    expr = extract_math(code, pos, options)
    if expr:
        start, end = expr
        try:
            result = evaluate(code[start:end])
        # py-emmet raises plain Exception (and ZeroDivisionError) for invalid input
        except Exception:  # noqa: BLE001
            return None
        return {
            "start": start,
            "end": end,
            "result": result,
            "snippet": f"{result:.4f}".rstrip("0").rstrip("."),
        }
    return None


def get_tag_context(view: sublime.View, pt: int, xml: bool | None = None) -> TagContext | None:
    "Returns matched HTML/XML tag for given point in view"
    content = view.substr(sublime.Region(0, view.size()))

    if xml is None:
        # Autodetect XML dialect
        xml = syntax.is_xml(syntax.from_pos(view, pt))

    matched_tag = match(content, pt, {"xml": xml})
    if not matched_tag:
        return None

    ctx: TagContext = {
        "name": matched_tag.name,
        "attributes": {},
        "open": to_region(matched_tag.open),
    }

    if matched_tag.close:
        ctx["close"] = to_region(matched_tag.close)

    for attr in matched_tag.attributes:
        value = attr.value
        # unquote value
        if value and (value[0] == '"' or value[0] == "'"):
            value = value.strip(value[0])
        ctx["attributes"][attr.name] = value

    return ctx


def extract_abbreviation(
    view: sublime.View, loc: int | sublime.Region | Sequence[int], config: Config
) -> ExtractedAbbreviation | None:
    """
    Extracts abbreviation from given location in view. Locations could be either
    `int` (a character location in view) or `list`/`tuple`/`sublime.Region`.
    """
    look_ahead = config.type != "stylesheet"
    is_jsx = syntax.is_jsx(config.syntax)
    prefix = get_jsx_prefix() if is_jsx else None

    if isinstance(loc, (list, tuple)):
        loc = to_region(loc)

    if isinstance(loc, int):
        # Character location is passed, extract from line
        pt = loc
        region = view.line(pt)

        # https://github.com/emmetio/sublime-text-plugin/issues/185
        # Handle edge case when abbreviation is extracted in JSX attribute.
        # For example: `<A child={<B|}>`, when extracting abbreviation from
        # | position, it will return `{<B}`, which is perfectly valid abbreviation.
        # However, expected abbreviation is `<B`
        if is_jsx and view.match_selector(pt, "meta.tag.attributes"):
            value_region = view.expand_to_scope(pt, "source.js.embedded")
            if value_region:
                region = value_region
    elif isinstance(loc, sublime.Region):
        # Extract from given range
        pt = loc.end()
        region = loc
    else:
        return None

    text = view.substr(region)
    begin = region.begin()
    abbr_pos = pt - begin

    abbr_data = extract(
        text,
        abbr_pos,
        {
            "type": config.type,
            # No look-ahead for stylesheets: they do not support brackets syntax
            # and enabled look-ahead produces false matches
            "lookAhead": look_ahead,
            "prefix": prefix,
        },
    )

    if not abbr_data and look_ahead:
        # Try without lookAhead option: useful for abbreviations inside
        # string literals
        abbr_data = extract(
            text, abbr_pos, {"type": config.type, "lookAhead": False, "prefix": prefix}
        )

    if abbr_data:
        # https://github.com/emmetio/sublime-text-plugin/issues/185
        # Validate that extracted abbreviation starts with prefix
        if prefix and text[abbr_data.location - len(prefix) : abbr_data.location] != prefix:
            return None

        abbr_data.start += begin
        abbr_data.end += begin
        abbr_data.location += begin
        return abbr_data

    return None


def get_jsx_prefix() -> str:
    "Returns prefix for capturing JSX abbreviations"
    prefix = get_settings("jsx_prefix")
    if prefix is True:
        prefix = "<"
    return prefix if isinstance(prefix, str) else ""
