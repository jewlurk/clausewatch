"""Source adapter interface.

One adapter per regulator. Keeping this narrow is what lets T33 add a second
regulator (ACRA/SGX) without touching the parser or differ.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@dataclass(frozen=True)
class DocumentRef:
    """A candidate document discovered on a regulator page."""

    url: str  # absolute
    label: str  # anchor text as published, e.g. "Notice 626 (Amendment) 2022"
    instrument_ref: str  # 'Notice 626'
    is_pdf: bool = True


@runtime_checkable
class SourceAdapter(Protocol):
    code: str  # regulator code, matches regulators.code

    def discover(self, landing_url: str, instrument_ref: str) -> list[DocumentRef]:
        """Return every document version linked from an instrument's landing page."""
        ...
