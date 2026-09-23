import html
import re
from typing import Any

import sublime

from . import emmet_sublime as emmet
from . import syntax
from .config import get_user_css
from .utils import get_caret, go_to_pos

previews_by_buffer: dict[int, tuple[int, bool]] = {}
phantoms_by_buffer: dict[int, sublime.PhantomSet] = {}
phantom_key = "emmet_tag_preview"
max_preview_len = 100


def show_tag_preview(view: sublime.View, pt: int, text: str, dest: int) -> None:
    "Displays given tag preview at `pt` location"
    buffer_id = view.buffer_id()
    if buffer_id not in phantoms_by_buffer:
        phantom_set = sublime.PhantomSet(view, phantom_key)
        phantoms_by_buffer[buffer_id] = phantom_set
    else:
        phantom_set = phantoms_by_buffer[buffer_id]

    r = sublime.Region(pt, pt)

    def nav(href: str) -> None:
        go_to_pos(view, int(href))

    phantoms = [
        sublime.Phantom(r, phantom_content(text, dest), sublime.LAYOUT_INLINE, on_navigate=nav)
    ]
    phantom_set.update(phantoms)


def hide_tag_preview(view: sublime.View) -> None:
    "Hides tag preview in given view"
    buffer_id = view.buffer_id()

    if buffer_id in phantoms_by_buffer:
        del phantoms_by_buffer[buffer_id]
        view.erase_phantoms(phantom_key)


def reset_tag_preview(view: sublime.View) -> None:
    buffer_id = view.buffer_id()
    if buffer_id in previews_by_buffer:
        pt, visible = previews_by_buffer[buffer_id]
        if visible:
            previews_by_buffer[buffer_id] = (pt, False)


def phantom_content(content: str, dest: int) -> str:
    "Returns contents for phantom preview"
    return f"""
    <body id="emmet-preview-phantom">
        <style>
            body {{
                background-color: #1D9B45;
                color: #fff;
                border-radius: 3px;
                padding: 0px 3px;
                opacity: 0.2;
                font-size: 1rem;
            }}
            a {{
                text-decoration: none;
                color: #fff;
            }}
            {get_user_css()}
        </style>
        <div class="tag-preview"><a href="{dest:d}">{html.escape(content, False)}</a></div>
    </body>
    """


def allow_preview(view: sublime.View) -> bool:
    "Check if tag preview is allowed in given view"
    if not view.settings().get("is_widget") and emmet.get_settings("tag_preview"):
        size = syntax.typed_setting("tag_preview_size_limit", 0, int, float)
        return not size or view.size() <= size
    return False


def has_preview(view: sublime.View) -> bool:
    buffer_id = view.buffer_id()
    if buffer_id in previews_by_buffer:
        return previews_by_buffer[buffer_id][1]
    return False


def handle_selection_change(view: sublime.View) -> None:
    caret = get_caret(view)
    syntax_name = syntax.from_pos(view, caret)
    buffer_id = view.buffer_id()

    if (
        syntax.is_html(syntax_name)
        and not syntax.is_jsx(syntax_name)
        and may_be_in_close_tag(view, caret)
    ):
        ctx = emmet.get_tag_context(view, caret, syntax.is_xml(syntax_name))
        if (
            ctx
            and "close" in ctx
            and ctx["attributes"]
            and ctx["close"].contains(caret)
            and ctx["open"] not in view.visible_region()
        ):
            pos = ctx["close"].b

            # Do not display preview if user forcibly hides it with Esc key
            # for current location
            if buffer_id in previews_by_buffer:
                pt = previews_by_buffer[buffer_id][0]
                if pt == pos:
                    return

            preview = create_tag_preview(ctx)
            if len(preview) > max_preview_len:
                preview = f"{preview[0:max_preview_len]}..."
            show_tag_preview(view, pos, preview, ctx["open"].a)
            previews_by_buffer[buffer_id] = (pos, True)
            return

    hide_tag_preview(view)
    previews_by_buffer.pop(buffer_id, None)


CLOSE_TAG_LOOKBEHIND = 1024


def may_be_in_close_tag(view: sublime.View, caret: int) -> bool:
    """
    Cheap necessary condition for the preview: the caret is inside or at either
    edge of a closing tag `</name>`. Matching the tag means parsing the whole
    document, so skipping it for every other caret position saves that work on
    each caret move. When unsure, returns True (the full match decides).
    """
    start = max(0, caret - CLOSE_TAG_LOOKBEHIND)
    chunk = view.substr(sublime.Region(start, caret + 2))
    rel = caret - start
    if chunk.startswith("</", rel):
        return True  # caret right before `</`
    lt = chunk.rfind("<", 0, rel)
    if lt == -1:
        return start > 0  # the tag could start before the window
    # A close tag has no `>` before its end; the caret may sit right after it.
    return chunk.startswith("/", lt + 1) and ">" not in chunk[lt : rel - 1]


def create_tag_preview(ctx: Any) -> str:
    class_name = ""
    id_name = ""
    attrs = []
    for k, value in ctx["attributes"].items():
        if k == "class":
            # `or ""`: a valueless `<div class>` used to raise AttributeError here
            value = re.sub(r"\s+", ".", (value or "").strip())
            if value:
                class_name += f".{value}"
        elif k == "id":
            id_name += f"#{(value or '').strip()}"
        else:
            attrs.append(f'{k}="{value}"')

    attr_str = f"[{' '.join(attrs)}]" if attrs else ""
    return f"{ctx['name']}{id_name}{class_name}{attr_str}"
