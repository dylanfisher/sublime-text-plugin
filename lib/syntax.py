import re
from typing import Any, TypedDict

import sublime

__doc__ = "Syntax-related methods"

markup_syntaxes = ["html", "xml", "xsl", "jsx", "haml", "jade", "pug", "slim"]
stylesheet_syntaxes = ["css", "scss", "sass", "less", "sss", "stylus", "postcss"]
xml_syntaxes = ["xml", "xsl", "jsx"]
html_syntaxes = ["html"]

# NB: avoid circular reference for `emmet_sublime` module,
# create own settings instance
settings: sublime.Settings | None = None


class SyntaxInfo(TypedDict):
    syntax: str
    type: str


def get_settings(key: str, default: Any = None) -> Any:
    "Returns value of given Emmet setting"
    global settings

    if settings is None:
        settings = sublime.load_settings("Emmet.sublime-settings")

    return settings.get(key, default)


_type_warned: set[str] = set()


def typed_setting(key: str, default: Any, *types: type) -> Any:
    """
    Value of setting `key` if it is one of `types`, else `default`. A wrong type
    (e.g. a string where a number is expected) is reported once in the console
    instead of raising inside a listener on every keystroke. `bool` does not count
    as a number here.
    """
    value = get_settings(key, default)
    if isinstance(value, types) and not (isinstance(value, bool) and bool not in types):
        return value
    if value is not None and key not in _type_warned:
        _type_warned.add(key)
        expected = " or ".join(t.__name__ for t in types)
        print(f'Emmet: ignoring setting "{key}": expected {expected}, got {value!r}')
    return default


def selector_list(key: str) -> list[str]:
    "Setting `key` as a list of scope selectors (non-string items are dropped)"
    value = typed_setting(key, [], list)
    return [sel for sel in value if isinstance(sel, str)]


def info(view: sublime.View, pt: int, fallback: str | None = None) -> SyntaxInfo | None:
    """
    Returns Emmet syntax info for given location in view.
    Syntax info is an abbreviation type (either 'markup' or 'stylesheet') and syntax
    name, which is used to apply syntax-specific options for output.

    By default, if given location doesn’t match any known context, this method
    returns `None`, but if `fallback` argument is provided, it returns data for
    given fallback syntax
    """
    syntax = from_pos(view, pt) or fallback
    if syntax:
        return {"syntax": syntax, "type": get_type(syntax)}
    return None


def doc_syntax(view: sublime.View) -> str:
    "Returns current document syntax"
    syntax = str(view.settings().get("syntax", "") or "")
    syntax = re.split(r"[\\\/]", syntax)[-1]
    if "." in syntax:
        syntax = syntax.split(".")[0]
    return syntax.lower()


def from_pos(view: sublime.View, pt: int) -> str | None:
    "Returns Emmet syntax for given location in view"
    scopes = typed_setting("syntax_scopes", {}, dict)
    for name, sel in scopes.items():
        if isinstance(sel, str) and view.match_selector(pt, sel):
            return name

    return None


def get_type(syntax: str | None) -> str:
    "Returns type of Emmet abbreviation for given syntax"
    return "stylesheet" if syntax in stylesheet_syntaxes else "markup"


def is_xml(syntax: str | None) -> bool:
    "Check if given syntax is XML dialect"
    return syntax in xml_syntaxes


def is_html(syntax: str | None) -> bool:
    "Check if given syntax is HTML dialect (including XML)"
    return syntax in html_syntaxes or is_xml(syntax)


def is_supported(syntax: str | None) -> bool:
    "Check if given syntax name is supported by Emmet"
    return syntax in markup_syntaxes or syntax in stylesheet_syntaxes


def is_css(syntax: str | None) -> bool:
    """
    Check if given syntax is a CSS dialect. Note that it’s not the same as stylesheet
    syntax: for example, SASS is a stylesheet but not CSS dialect (but SCSS is)
    """
    return syntax in ("css", "scss", "less")


def is_jsx(syntax: str | None) -> bool:
    "Check if given syntax is JSX"
    return syntax == "jsx"


def is_inline(view: sublime.View, pt: int) -> bool:
    "Check if abbreviation in given location must be expanded as single line"
    return matches_selector(view, pt, selector_list("inline_scopes"))


def in_activation_scope(view: sublime.View, pt: int) -> bool:
    """
    Check if given location in view can be used for abbreviation marker activation.
    Note that this method implies that caret is in Emmet-supported syntax
    """
    if matches_selector(view, pt, selector_list("ignore_scopes")):
        return False

    if matches_selector(view, pt, selector_list("abbreviation_scopes")):
        return True

    # Handle edge case for HTML syntax:
    # <div>a|</div>
    # in this example, ST returns `punctuation.definition.tag.begin.html`
    # scope, even if caret is actually not in tag. Add some custom checks here
    return bool(
        view.match_selector(pt, "(text.html | text.xml) meta.tag punctuation.definition.tag.begin")
        and view.substr(pt) == "<"
    )


def matches_selector(view: sublime.View, pt: int, selectors: list[str]) -> bool:
    "Check if given location in view one of the given selectors"
    return any(view.match_selector(pt, sel) for sel in selectors)
