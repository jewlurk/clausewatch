"""Word-level diff rendered as HTML. Brief §17.

The source is an uncontrolled PDF, so every token is HTML-escaped before it reaches
the output. The escaping happens on the token, never on the assembled string, so a
clause containing "<script>" cannot break out through the <ins>/<del> wrappers.
"""
from __future__ import annotations

import html
import re
from difflib import SequenceMatcher

_TOKEN_RE = re.compile(r"\S+|\s+")


def tokenise(text: str) -> list[str]:
    return _TOKEN_RE.findall(text)


def diff_html(old_body: str, new_body: str) -> str:
    """Return HTML with removals in <del> and additions in <ins>."""
    old_tokens = tokenise(old_body or "")
    new_tokens = tokenise(new_body or "")
    matcher = SequenceMatcher(a=old_tokens, b=new_tokens, autojunk=False)

    parts: list[str] = []
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        old_chunk = html.escape("".join(old_tokens[i1:i2]))
        new_chunk = html.escape("".join(new_tokens[j1:j2]))
        if tag == "equal":
            parts.append(new_chunk)
        elif tag == "delete":
            parts.append(f"<del>{old_chunk}</del>")
        elif tag == "insert":
            parts.append(f"<ins>{new_chunk}</ins>")
        else:  # replace
            parts.append(f"<del>{old_chunk}</del><ins>{new_chunk}</ins>")
    return "".join(parts)
