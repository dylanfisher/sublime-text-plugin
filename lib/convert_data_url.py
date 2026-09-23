import base64
import os
import os.path
import re
from typing import Any

import sublime

from ..emmet.action_utils import get_open_tag
from ..emmet.html_matcher import AttributeToken
from . import emmet_sublime as emmet
from . import syntax, utils

URLSAFE_TO_STANDARD = str.maketrans("-_", "+/")

mime_types = {
    ".gif": "image/gif",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".svg": "image/svg+xml",
    ".webp": "image/webp",
}


def convert_html(view: sublime.View, edit: sublime.Edit, pos: int) -> None:
    "Convert to/from data:URL for HTML context"
    # Upstream called a non-existent `emmet.tag()`, so this always raised AttributeError.
    tag: Any = get_open_tag(utils.get_content(view), pos)

    if tag and tag.name.lower() == "img" and tag.attributes:
        src_attr = next((a for a in tag.attributes if a.name == "src"), None)

        # Get region of attribute value
        region = src_attr and attr_value_region(src_attr)

        if region:
            toggle_url(view, edit, region)


def convert_css(view: sublime.View, edit: sublime.Edit, pos: int) -> None:
    "Convert to/from data:URL for CSS context"
    section = emmet.css_section(utils.get_content(view), pos, True)

    if not section:
        return

    # Find value token with `url(...)` value under caret
    for p in section.properties:
        # If value matches caret location, find url(...) token for it
        if pos in p.value:
            token = get_url_region(view, p, pos)
            if token:
                toggle_url(view, edit, token)
            break


def toggle_url(view: sublime.View, edit: sublime.Edit, region: sublime.Region) -> None:
    "Toggles URL state for given region: either convert it to data:URL or store as file"
    src = view.substr(region)

    if src.startswith("data:"):

        def on_done(text: str) -> None:
            convert_from_data_url(view, region, text)

        window = view.window() or sublime.active_window()
        window.show_input_panel("Enter file name", f"image{get_ext(src)}", on_done, None, None)
    else:
        convert_to_data_url(view, edit, region)


def convert_to_data_url(view: sublime.View, edit: sublime.Edit, region: sublime.Region) -> None:
    max_size = syntax.typed_setting("max_data_url", 0, int, float)
    src = view.substr(region)
    abs_file = None
    file_name = view.file_name()

    if utils.is_url(src):
        abs_file = src
    elif file_name:
        abs_file = utils.locate_file(file_name, src)
        if abs_file and max_size and os.path.getsize(abs_file) > max_size:
            status(
                f"{abs_file} is larger than {max_size} bytes; "
                'increase the "max_data_url" setting to convert it'
            )
            return
    else:
        status("save the file first: image paths are resolved relative to it")
        return

    if not abs_file:
        status(f"can't find {src}")
        return

    try:
        # Read one byte past the limit so an oversized remote file is detected
        # without downloading all of it.
        data = utils.read_file(abs_file, int(max_size) + 1 if max_size else -1)
    except (OSError, ValueError) as err:  # URLError/HTTPError/timeouts are OSErrors
        status(f"can't read {abs_file}: {err}")
        return

    if data and (not max_size or len(data) <= max_size):
        ext = os.path.splitext(abs_file)[1]
        if ext in mime_types:
            # Standard base64 (RFC 2397 data: URLs); upstream used the URL-safe
            # alphabet (`-`/`_`), which browsers reject in data: URLs.
            encoded = base64.b64encode(data).decode("ascii")
            new_src = f"data:{mime_types[ext]};base64,{encoded}"
            view.replace(edit, region, new_src)


def convert_from_data_url(view: sublime.View, region: sublime.Region, dest: str) -> None:
    src = view.substr(region)
    m = re.match(r"^data\:.+?;base64,(.+)", src)
    if not m:
        return

    file_name = view.file_name()
    if not file_name:
        status("save the file first: the image is written next to it")
        return
    if not dest.strip():
        return

    base_dir = os.path.dirname(file_name)
    abs_dest = utils.create_path(base_dir, dest)
    file_url = os.path.relpath(abs_dest, base_dir).replace("\\", "/")

    # Accept both base64 alphabets (upstream wrote URL-safe data), ignore
    # whitespace, but reject anything else instead of silently dropping it.
    payload = re.sub(r"\s+", "", m.group(1)).translate(URLSAFE_TO_STANDARD)
    try:
        data = base64.b64decode(payload, validate=True)
    except ValueError as err:  # binascii.Error
        status(f"invalid base64 data: {err}")
        return

    if os.path.exists(abs_dest) and not sublime.ok_cancel_dialog(
        f"{abs_dest} already exists.\n\nReplace it with the image from the data: URL?",
        "Replace",
    ):
        return

    try:
        os.makedirs(os.path.dirname(abs_dest), exist_ok=True)
        with open(abs_dest, "wb") as fd:
            fd.write(data)
    except OSError as err:
        status(f"can't write {abs_dest}: {err}")
        return

    view.run_command(
        "convert_data_url_replace", {"region": [region.begin(), region.end()], "text": file_url}
    )


def status(message: str) -> None:
    "Report a failure of this command in the status bar and the console"
    print(f"Emmet: Convert data:URL: {message}")
    sublime.status_message(f"Emmet: {message}")


def attr_value_region(attr: AttributeToken) -> sublime.Region | None:
    "Returns clean (unquoted) value region of given attribute"
    if attr.value is not None:
        start = attr.value_start
        end = attr.value_end
        if utils.is_quoted(attr.value):
            start += 1
            end -= 1
        return sublime.Region(start, end)
    return None


def get_url_region(view: sublime.View, css_prop: Any, pos: int) -> sublime.Region | None:
    "Returns region of matched `url()` token from given value"
    for v in css_prop.value_tokens:
        m = re.match(r'url\([\'"]?(.+?)[\'"]?\)', view.substr(v)) if pos in v else None
        if m:
            return sublime.Region(v.begin() + m.start(1), v.begin() + m.end(1))
    return None


def get_ext(data_url: str) -> str:
    "Returns suggested extension from given data:URL string"
    m = re.match(r"data:(.+?);", data_url)
    if m:
        for key, value in mime_types.items():
            if value == m.group(1):
                return key
    return ".jpg"
