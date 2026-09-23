import io
import os.path
import re
import struct
from typing import Any

import sublime

from ..emmet.action_utils import get_open_tag
from . import emmet_sublime as emmet
from . import syntax, utils


def update_image_size(view: sublime.View, edit: sublime.Edit) -> None:
    caret = utils.get_caret(view)
    syntax_name = syntax.from_pos(view, caret)

    if syntax.is_html(syntax_name):
        update_image_size_html(view, edit, caret)
    elif syntax.is_css(syntax_name):
        update_image_size_css(view, edit, caret)


def update_image_size_html(view: sublime.View, edit: sublime.Edit, pos: int) -> None:
    "Updates image size in HTML context"
    tag: Any = get_open_tag(utils.get_content(view), pos)
    if tag and tag.name.lower() == "img" and tag.attributes:
        attrs = {a.name.lower(): a for a in tag.attributes}

        if "src" in attrs and attrs["src"].value:
            src = utils.attribute_value(attrs["src"])
            size = read_image_size(view, src)
            if size:
                patch_html_size(attrs, view, edit, size[0], size[1])
            else:
                print(f'Unable to determine size of "{src}": file is either unsupported or invalid')


def update_image_size_css(view: sublime.View, edit: sublime.Edit, pos: int) -> None:
    "Updates image size in CSS context"
    section = emmet.css_section(utils.get_content(view), pos, True)
    # Store all properties in lookup table and find matching URL
    props: dict[str, Any] = {}
    src = None
    context_prop = None

    if section:
        for p in section.properties:
            props[view.substr(p.name)] = p

            # If value matches caret location, find url(...) token for it
            if pos in p.value:
                context_prop = p
                src = get_css_url(view, p, pos)

    if src:
        size = read_image_size(view, src)
        if size:
            patch_css_size(view, edit, props, size[0], size[1], context_prop)
        else:
            print(f'Unable to determine size of "{src}": file is either unsupported or invalid')


def get_css_url(view: sublime.View, css_prop: Any, pos: int) -> str | None:
    for v in css_prop.value_tokens:
        m = re.match(r'url\([\'"]?(.+?)[\'"]?\)', view.substr(v)) if pos in v else None
        if m:
            return m.group(1)
    return None


def get_dpi(file_path: str) -> float:
    "Detects file DPI from given file path"
    name = os.path.splitext(file_path)[0]

    # If file name contains DPI suffix like `@2x`, use it to scale down image size
    m = re.search(r"@(\d+(?:\.\d+))x$", name)
    return (m and float(m.group(1))) or 1


def read_image_size(view: sublime.View, src: str) -> tuple[int, int] | None:
    "Reads image size of given file, if possible"
    abs_file = None
    if utils.is_url(src):
        abs_file = src
    elif file_name := view.file_name():
        abs_file = utils.locate_file(file_name, src)

    if abs_file:
        file_name = os.path.basename(abs_file)
        ext = os.path.splitext(file_name)[1]
        chunk = 2048 if ext.lower() in (".svg", ".jpg", ".jpeg") else 100
        data = utils.read_file(abs_file, chunk)
        size = get_size(data)
        if size:
            dpi = get_dpi(src)
            return round(size[0] / dpi), round(size[1] / dpi)
    else:
        print(f'Unable to locate file for "{src}" url')
    return None


def patch_html_size(
    attrs: dict[str, Any], view: sublime.View, edit: sublime.Edit, w: int, h: int
) -> None:
    "Updates image size of HTML tag"
    width = str(w)
    height = str(h)
    width_attr = attrs.get("width")
    height_attr = attrs.get("height")

    if width_attr and height_attr:
        # We have both attributes, patch them
        wr = utils.attribute_region(width_attr)
        hr = utils.attribute_region(height_attr)
        if wr.begin() < hr.begin():
            view.replace(edit, hr, utils.patch_attribute(height_attr, height))
            view.replace(edit, wr, utils.patch_attribute(width_attr, width))
        else:
            view.replace(edit, wr, utils.patch_attribute(width_attr, width))
            view.replace(edit, hr, utils.patch_attribute(height_attr, height))
    elif width_attr or height_attr:
        # Use existing attribute and replace it with patched variations
        attr: Any = width_attr or height_attr
        data = (
            f"{utils.patch_attribute(attr, width, 'width')} "
            f"{utils.patch_attribute(attr, height, 'height')}"
        )
        view.replace(edit, utils.attribute_region(attr), data)
    elif "src" in attrs:
        # At least 'src' attribute should be available
        attr = attrs["src"]
        pos = attr.value_end if attr.value is not None else attr.name_end
        data = (
            f" {utils.patch_attribute(attr, width, 'width')} "
            f"{utils.patch_attribute(attr, height, 'height')}"
        )
        view.insert(edit, pos, data)


def patch_css_size(
    view: sublime.View,
    edit: sublime.Edit,
    props: dict[str, Any],
    w: int,
    h: int,
    context_prop: Any,
) -> None:
    width = f"{w:d}px"
    height = f"{h:d}px"
    width_prop = props.get("width")
    height_prop = props.get("height")

    if width_prop and height_prop:
        # We have both properties, patch them
        if width_prop.before < height_prop.before:
            view.replace(edit, height_prop.value, height)
            view.replace(edit, width_prop.value, width)
        else:
            view.replace(edit, width_prop.value, width)
            view.replace(edit, height_prop.value, height)
    elif width_prop or height_prop:
        # Use existing attribute and replace it with patched variations
        prop: Any = width_prop or height_prop
        data = utils.patch_property(view, prop, width, "width") + utils.patch_property(
            view, prop, height, "height"
        )
        view.replace(edit, sublime.Region(prop.before, prop.after), data)
    elif context_prop:
        # Append to source property
        data = utils.patch_property(view, context_prop, width, "width") + utils.patch_property(
            view, context_prop, height, "height"
        )
        view.insert(edit, context_prop.after, data)


def get_size(data: bytes) -> tuple[int, int] | None:
    """
    Returns size of given image fragment, if possible.
    Based on image_size script by Paulo Scardine: https://github.com/scardine/image_size
    """
    size = len(data)
    if size >= 10 and data[:6] in (b"GIF87a", b"GIF89a"):
        # GIFs
        w, h = struct.unpack("<HH", data[6:10])
        return int(w), int(h)

    if size >= 24 and data.startswith(b"\211PNG\r\n\032\n") and data[12:16] == b"IHDR":
        # PNGs
        w, h = struct.unpack(">LL", data[16:24])
        return int(w), int(h)

    if size >= 16 and data.startswith(b"\211PNG\r\n\032\n"):
        # older PNGs
        w, h = struct.unpack(">LL", data[8:16])
        return int(w), int(h)

    if size >= 30 and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        # WebP
        webp_type = data[12:16]
        if webp_type == b"VP8 ":  # Lossy WebP (old)
            w, h = struct.unpack("<HH", data[26:30])
        elif webp_type == b"VP8L":  # Lossless WebP
            bits = struct.unpack("<I", data[21:25])[0]
            w = int(bits & 0x3FFF) + 1
            h = int((bits >> 14) & 0x3FFF) + 1
        elif webp_type == b"VP8X":  # Extended WebP
            w = int((data[26] << 16) | (data[25] << 8) | data[24]) + 1
            h = int((data[29] << 16) | (data[28] << 8) | data[27]) + 1
        else:
            w = 0
            h = 0
        return w, h

    if b"<svg" in data:
        # SVG
        start = data.index(b"<svg")
        end = data.index(b">", start)
        svg = str(data[start : end + 1], "utf8")
        w = re.search(r'width=["\'](\d+)', svg)
        h = re.search(r'height=["\'](\d+)', svg)
        return int(w.group(1) if w else 0), int(h.group(1) if h else 0)

    if size >= 2 and data.startswith(b"\377\330"):
        # JPEG
        with io.BytesIO(data) as inp:
            inp.seek(0)
            inp.read(2)
            b = inp.read(1)
            while b and ord(b) != 0xDA:
                while ord(b) != 0xFF:
                    b = inp.read(1)
                while ord(b) == 0xFF:
                    b = inp.read(1)
                if 0xC0 <= ord(b) <= 0xC3:
                    inp.read(3)
                    h, w = struct.unpack(">HH", inp.read(4))
                    return int(w), int(h)
                inp.read(int(struct.unpack(">H", inp.read(2))[0]) - 2)
                b = inp.read(1)

        return 0, 0
    return None
