"""Ground truth from MAS's own tracked-changes PDF.

MAS states: coloured + struck-through = deletion, coloured + underlined = insertion.
So a clause containing red characters is a clause MAS changed. The document is
extracted twice — once with every character, once with red characters omitted — and
compared per section. Sections that differ are the ones MAS marked.

This mirrors parse_pdf's font split so footnotes are covered too: footnotes carry real
amendments (cross-references renumbered from 11A.x to 11.x in the June 2025 round), and
an oracle that only knew about clauses scored every one of those as a false positive.
"""
from __future__ import annotations

import sys
from pathlib import Path

from pdfminer.high_level import extract_pages
from pdfminer.layout import LAParams, LTChar, LTTextContainer

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "ingest"))

from parse.sections import (
    FOOTNOTE_SIZE_RATIO,
    parse_footnotes,
    parse_sections,
)

RED = (1.0, 0.0, 0.0)


def _is_red(ch: LTChar) -> bool:
    colour = getattr(ch.graphicstate, "ncolor", None)
    return isinstance(colour, tuple) and tuple(round(c, 2) for c in colour) == RED


def split_tracked(path, skip_red: bool = False) -> tuple[str, str]:
    """Return (body text, footnote text), optionally omitting MAS's red markup."""
    pages = list(extract_pages(str(path), laparams=LAParams(boxes_flow=None)))

    sizes: dict[float, int] = {}
    for page in pages:
        for element in page:
            if not isinstance(element, LTTextContainer):
                continue
            for line in element:
                if not hasattr(line, "__iter__"):
                    continue
                for ch in line:
                    if isinstance(ch, LTChar) and ch.get_text().strip():
                        size = round(ch.size, 1)
                        sizes[size] = sizes.get(size, 0) + 1
    if not sizes:
        return "", ""
    floor = max(sizes, key=lambda s: sizes[s]) * FOOTNOTE_SIZE_RATIO

    body: list[str] = []
    footnotes: list[str] = []
    for page in pages:
        for element in page:
            if not isinstance(element, LTTextContainer):
                continue
            for line in element:
                if not hasattr(line, "__iter__"):
                    continue
                big, small = [], []
                for ch in line:
                    if not isinstance(ch, LTChar):
                        continue
                    if skip_red and _is_red(ch):
                        continue
                    (big if ch.size >= floor else small).append(ch.get_text())
                if "".join(big).strip():
                    body.append("".join(big).rstrip("\n"))
                if "".join(small).strip():
                    footnotes.append("".join(small).rstrip("\n"))
    return "\n".join(body), "\n".join(footnotes)


def _sections(path, skip_red: bool) -> dict[str, str]:
    body_text, footnote_text = split_tracked(path, skip_red=skip_red)
    out = {s.section_key: s.body for s in parse_sections(body_text)}
    out.update({s.section_key: s.body for s in parse_footnotes(footnote_text)})
    return out


def changed_clauses(path) -> tuple[set[str], set[str]]:
    """(sections MAS marked as changed, all sections in the tracked document)."""
    full = _sections(path, skip_red=False)
    black = _sections(path, skip_red=True)
    changed = {key for key, body in full.items() if black.get(key) != body}
    return changed, set(full)


if __name__ == "__main__":
    fixtures = Path(__file__).resolve().parent.parent / "ingest" / "tests" / "fixtures"
    changed, all_keys = changed_clauses(fixtures / "626_2025_tracked.pdf")
    print(f"sections in tracked doc: {len(all_keys)}")
    print(f"MAS-marked changed sections: {len(changed)}")
    print(sorted(changed))
