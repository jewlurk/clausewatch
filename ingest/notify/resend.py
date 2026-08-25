"""Resend transport (T26).

Verified against resend.com on 26 August 2026:

* Send: ``POST https://api.resend.com/emails``, ``Authorization: Bearer <key>``,
  JSON body with ``from``, ``to``, ``subject`` and ``html``.
* Free tier: **100 emails/day**, 3,000/month, 3 domains, 30-day retention.
* "You must add and verify at least one domain to send emails with Resend."
  There is no send path that skips owning a domain — see ``docs/STATE.md``.

The daily cap below defaults under the free-tier limit rather than at it, so a
mis-scoped query cannot spend the day's whole allowance before anyone notices.
"""
from __future__ import annotations

import os

import httpx

API = "https://api.resend.com/emails"

# Free tier is 100/day. Stop at 90 so a bug costs a warning, not the day's quota.
DAILY_CAP = int(os.environ.get("ALERT_DAILY_CAP", "90"))


class ResendError(RuntimeError):
    pass


class ResendClient:
    def __init__(
        self,
        api_key: str | None = None,
        sender: str | None = None,
        timeout: float = 30.0,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.api_key = api_key or os.environ.get("RESEND_API_KEY", "")
        self.sender = sender or os.environ.get("ALERT_FROM", "")
        self._client = httpx.Client(timeout=timeout, transport=transport)

    @property
    def configured(self) -> bool:
        return bool(self.api_key and self.sender)

    def send(self, *, to: str, subject: str, html: str) -> str:
        if not self.configured:
            raise ResendError("RESEND_API_KEY and ALERT_FROM must both be set")
        response = self._client.post(
            API,
            headers={"Authorization": f"Bearer {self.api_key}"},
            json={"from": self.sender, "to": [to], "subject": subject, "html": html},
        )
        if response.status_code >= 400:
            # Resend's message is the useful part: an unverified sending domain and a
            # bad key fail the same way from the caller's side otherwise.
            raise ResendError(f"HTTP {response.status_code}: {response.text[:400]}")
        return response.json().get("id", "")

    def close(self) -> None:
        self._client.close()
