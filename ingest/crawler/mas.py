"""MAS source adapter.

Verified 2026-08-25 against the live site: an instrument's landing page links its
full published version history as PDFs, not just the current version. Notice 626's
page carried 16 PDFs spanning 2014-2025. This is why backfill (T14) needs no archive
scraping — the history is on the page.

URL shapes are NOT stable across eras (three distinct /-/media/ prefixes seen for the
same instrument), so we discover links by parsing the page rather than templating URLs.
"""
from __future__ import annotations

from html.parser import HTMLParser
from urllib.parse import urljoin, urlsplit, urlunsplit

from .base import DocumentRef

BASE_URL = "https://www.mas.gov.sg"


class _PdfLinkParser(HTMLParser):
    """Collect (href, anchor text) for every .pdf link."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.links: list[tuple[str, str]] = []
        self._href: str | None = None
        self._text: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag != "a":
            return
        href = dict(attrs).get("href") or ""
        if ".pdf" in href.lower():
            self._href = href
            self._text = []

    def handle_data(self, data: str) -> None:
        if self._href is not None:
            self._text.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "a" and self._href is not None:
            label = " ".join("".join(self._text).split())
            self.links.append((self._href, label))
            self._href = None
            self._text = []


def _canonical(url: str) -> str:
    """Absolute URL with the Sitecore cache-busting query dropped.

    MAS appends ?sc_lang=&hash= to some links; the same document appears with and
    without it. Dropping the query keeps dedup keyed on the document, not the link.
    """
    absolute = urljoin(BASE_URL, url)
    parts = urlsplit(absolute)
    return urlunsplit((parts.scheme, parts.netloc, parts.path, "", ""))


class MasAdapter:
    code = "MAS"

    def discover(self, html: str, instrument_ref: str) -> list[DocumentRef]:
        """Extract every distinct PDF version linked from a landing page.

        Takes page HTML (not a URL) so discovery is pure and testable offline; the
        caller owns fetching via PoliteClient.
        """
        parser = _PdfLinkParser()
        parser.feed(html)

        seen: set[str] = set()
        refs: list[DocumentRef] = []
        for href, label in parser.links:
            url = _canonical(href)
            if url in seen:
                continue
            seen.add(url)
            refs.append(DocumentRef(url=url, label=label, instrument_ref=instrument_ref))
        return refs
