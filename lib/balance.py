import sublime

from . import emmet_sublime as emmet
from . import syntax
from .utils import get_content, to_region


def push_range(items: list[sublime.Region], region: sublime.Region) -> None:
    last = items[-1] if items else None
    if not last or (last != region and region):
        items.append(region)


def get_regions(
    view: sublime.View, pt: int, syntax_name: str, direction: str = "outward"
) -> list[sublime.Region]:
    "Returns regions for balancing"
    content = get_content(view)

    if syntax.is_css(syntax_name):
        regions = emmet.balance_css(content, pt, direction)
        return [to_region(r) for r in regions]

    result: list[sublime.Region] = []
    tags = emmet.balance(content, pt, direction, syntax.is_xml(syntax_name))

    for tag in tags:
        if tag.close:
            # Inner range
            push_range(result, sublime.Region(tag.open[1], tag.close[0]))
            # Outer range
            push_range(result, sublime.Region(tag.open[0], tag.close[1]))
        else:
            push_range(result, sublime.Region(tag.open[0], tag.open[1]))

    result.sort(key=lambda v: v.begin(), reverse=direction == "outward")
    return result


def balance_inward(view: sublime.View, syntax_name: str) -> list[sublime.Region]:
    "Returns inward balanced ranges from current view's selection"
    result = []

    for sel in view.sel():
        regions = get_regions(view, sel.begin(), syntax_name, "inward")

        # Try to find range which equals to selection: we should pick leftmost
        ix = -1
        for i, r in enumerate(regions):
            if r == sel:
                ix = i
                break

        target_region = sel

        if ix < len(regions) - 1:
            target_region = regions[ix + 1]
        elif ix == -1:
            # No match found, pick closest region
            for r in regions:
                if sel in r:
                    target_region = r
                    break

        result.append(target_region)

    return result


def balance_outward(view: sublime.View, syntax_name: str) -> list[sublime.Region]:
    "Returns outward balanced ranges from current view's selection"
    result = []

    for sel in view.sel():
        regions = get_regions(view, sel.begin(), syntax_name, "outward")
        target_region = sel
        for r in regions:
            if sel in r and r.end() > sel.end():
                target_region = r
                break

        result.append(target_region)

    return result
