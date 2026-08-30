"""IRAS source adapter (T33) — proving the source abstraction holds.

The point of a second adapter is to show that adding a regulator is a new adapter and
nothing else: the parser, the differ, the storage, the schema all stay untouched. This
one adapts IRAS e-Tax Guides, and it is deliberately a *different shape* from MAS, which
is what makes it a real test of the SourceAdapter seam rather than a copy:

  * MAS: one landing page per instrument, linking that instrument's version history.
    `discover` returns many versions of ONE instrument.
  * IRAS: one catalogue page listing many distinct guides, each a single current PDF.
    `discover` returns ONE version each of MANY instruments.

The DocumentRef contract absorbs both without change: each guide is emitted as its own
ref, keyed by its title. Two IRAS facts the MAS adapter never had to handle are carried
through here — the publication date is in the listing markup (MAS's dates come from the
PDF), and each guide has a duplicate download link inside a hidden modal, which is
deduped.

FETCH-LAYER CAVEAT — read before wiring this to a live crawl. Verified 30 Aug 2026:
IRAS's e-Tax Guides page renders its list client-side; a plain HTTP GET returns the app
shell with zero PDF links. The same is true of SGX and CEA. MAS's per-notice pages are
legacy static HTML, which is why PoliteClient (no JS) suffices there. So IRAS integration
needs a JavaScript-capable fetch step feeding rendered HTML into this adapter. That is a
crawler concern, orthogonal to the adapter — and it is exactly the boundary T33 set out
to find. This adapter parses the rendered markup and is tested against a real captured
sample; the JS fetch layer is the remaining integration work, not a flaw in the seam.
"""
from __future__ import annotations

import re
from html.parser import HTMLParser
from urllib.parse import urljoin, urlsplit, urlunsplit

from .base import DocumentRef

BASE_URL = "https://www.iras.gov.sg"

# The title carries a trailing "(PDF, 728.33 KB)" hint that is not part of the name.
_SIZE_HINT = re.compile(r"\s*\(PDF,[^)]*\)\s*$", re.IGNORECASE)


def _canonical(url: str) -> str:
    """Absolute URL with the ?sfvrsn cache-buster dropped, so the same guide dedups.

    IRAS appends ?sfvrsn=<hash>_<n> to every asset; the same document appears with and
    without it. Keying dedup on the path, not the link, mirrors MasAdapter._canonical.
    """
    parts = urlsplit(urljoin(BASE_URL, url))
    return urlunsplit((parts.scheme, parts.netloc, parts.path, "", ""))


class _EtaxListingParser(HTMLParser):
    """Collect (title, date, pdf_url) for each .eyd-article-item on the listing.

    Each guide is one <article class="eyd-article-item">. Inside it, the first <h2> is
    the title and the first .pdf link is the download. The article also contains a
    hidden modal that repeats both — capturing only the FIRST of each within an article
    ignores the duplicate.
    """

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.items: list[tuple[str, str | None, str]] = []
        self._depth = 0            # tag depth inside the current article, 0 = outside
        self._in_title = False
        self._in_date = False
        self._title: list[str] = []
        self._date: str | None = None
        self._url: str | None = None

    def _reset_item(self) -> None:
        self._title, self._date, self._url = [], None, None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        a = dict(attrs)
        classes = (a.get("class") or "").split()

        if tag == "article" and "eyd-article-item" in classes:
            self._depth = 1
            self._reset_item()
            return
        if self._depth == 0:
            return
        self._depth += 1

        # First <h2> holds the title; ignore any later one (the modal's copy).
        if tag == "h2" and not self._title:
            self._in_title = True
        elif tag == "span" and "eyd-article-item__meta--date" in classes:
            self._in_date = True
        elif tag == "a" and self._url is None:
            href = a.get("href") or ""
            if ".pdf" in href.lower():
                self._url = _canonical(href)

    def handle_data(self, data: str) -> None:
        if self._in_title:
            self._title.append(data)
        elif self._in_date:
            self._date = (self._date or "") + data

    def handle_endtag(self, tag: str) -> None:
        if self._depth == 0:
            return
        if tag == "h2":
            self._in_title = False
        elif tag == "span":
            self._in_date = False

        self._depth -= 1
        if self._depth == 0:  # closed the article
            title = _SIZE_HINT.sub("", " ".join("".join(self._title).split())).strip()
            if title and self._url:
                self.items.append((title, (self._date or "").strip() or None, self._url))
            self._reset_item()


class IrasAdapter:
    code = "IRAS"

    def discover(self, html: str, instrument_ref: str | None = None) -> list[DocumentRef]:
        """Every e-Tax guide linked on the rendered listing page.

        `instrument_ref` is accepted for interface parity with MasAdapter but ignored:
        an IRAS listing is a catalogue of many instruments, so each guide's own title
        becomes its ref. Deduped by canonical URL — the per-guide modal repeats the link.
        """
        parser = _EtaxListingParser()
        parser.feed(html)

        seen: set[str] = set()
        refs: list[DocumentRef] = []
        for title, date, url in parser.items:
            if url in seen:
                continue
            seen.add(url)
            label = f"{title} ({date})" if date else title
            refs.append(DocumentRef(url=url, label=label, instrument_ref=title))
        return refs
