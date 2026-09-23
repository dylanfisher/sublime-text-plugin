import html
import re

from ..emmet.html_matcher import ElementType, get_attributes, scan

re_tag_end = re.compile(r"\s*\/?>$")


def highlight(code: str) -> str:
    chunks = []
    offset = [0]

    def cb(name: str, elem_type: int, start: int, end: int) -> None:
        if offset[0] != start:
            chunks.append(escape(code[offset[0] : start]))
        offset[0] = end

        if elem_type == ElementType.Close:
            chunks.append(
                f'<span class="tag close">&lt;/<span class="tag-name">{name}</span>&gt;</span>'
            )
        else:
            chunks.append(f'<span class="tag open">&lt;<span class="tag-name">{name}</span>')
            for attr in get_attributes(code, start, end, name):
                chunks.append(' <span class="attr">')
                chunks.append(f'<span class="attr-name">{attr.name}</span>')
                if attr.value is not None:
                    chunks.append(f'=<span class="attr-value">{attr.value}</span>')
                chunks.append("</span>")

            tag_end = re_tag_end.search(code[start:end])
            if tag_end:
                chunks.append(escape(tag_end.group(0)))
            chunks.append("</span>")

    scan(code, cb)
    chunks.append(escape(code[offset[0] :]))

    return "".join(chunks)


def styles() -> str:
    return """
    .dark .tag { color: #77c7b4; }
    .dark .attr-name { color: #8fd260; }
    .dark .attr-value { color: #ff6e61; }

    .light .tag { color: #0046aa; }
    .light .attr-name { color: #017ab7; }
    .light .attr-value { color: #017ab7; }
    """


def escape(code: str) -> str:
    return html.escape(code, False)
