"""Ground truth from MAS's own tracked-changes PDF.

MAS states: coloured + struck-through = deletion, coloured + underlined = insertion.
So a clause containing red characters is a clause MAS changed. Extracting the tracked
document twice — once with every character, once with red characters omitted — and
comparing per clause yields MAS's own changed-clause list, independent of our differ.
"""
import sys
from pathlib import Path

from pdfminer.high_level import extract_pages
from pdfminer.layout import LAParams, LTChar, LTTextContainer

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "ingest"))
from parse.sections import parse_sections

RED = (1.0, 0.0, 0.0)


def extract(path, skip_red=False):
    out = []
    for page in extract_pages(path, laparams=LAParams(boxes_flow=None)):
        for element in page:
            if not isinstance(element, LTTextContainer):
                continue
            for line in element:
                if not hasattr(line, "__iter__"):
                    continue
                buf = []
                for ch in line:
                    if isinstance(ch, LTChar):
                        colour = getattr(ch.graphicstate, "ncolor", None)
                        is_red = (
                            isinstance(colour, tuple) and tuple(round(c, 2) for c in colour) == RED
                        )
                        if skip_red and is_red:
                            continue
                        buf.append(ch.get_text())
                    else:
                        buf.append(getattr(ch, "get_text", lambda: "")())
                if buf:
                    out.append("".join(buf))
    return "\n".join(out)


def changed_clauses(path):
    full = {s.section_key: s.body for s in parse_sections(extract(path))}
    black = {s.section_key: s.body for s in parse_sections(extract(path, skip_red=True))}
    changed = set()
    for key, body in full.items():
        if key not in black or black[key] != body:
            changed.add(key)
    return changed, set(full)


if __name__ == "__main__":
    fixtures = Path(__file__).resolve().parent.parent / "ingest" / "tests" / "fixtures"
    changed, all_keys = changed_clauses(fixtures / "626_2025_tracked.pdf")
    print(f"clauses in tracked doc: {len(all_keys)}")
    print(f"MAS-marked changed clauses: {len(changed)}")
    print(sorted(changed))
