"""T26 email alerts.

The rules that must not regress: the mapped-control template wins when a mapping is
involved, no clause text leaves the building, every change links to MAS, and nothing
that reads as legal advice can be sent.
"""
from __future__ import annotations

import json
from datetime import date

import httpx
import pytest

from notify import Alert, Digest, ResendClient, ResendError, render_digest
from notify.templates import PrescriptiveEmail, render_watchlist


def make_alert(**over) -> Alert:
    base = {
        "alert_id": 1,
        "instrument_ref": "Notice 626",
        "instrument_title": "Prevention of Money Laundering - Banks",
        "source_url": "https://www.mas.gov.sg/regulation/notices/notice-626",
        "section_key": "6.14",
        "op": "MODIFIED",
        "severity": 4,
        "revision_date": date(2025, 6, 30),
        "effective_date": date(2025, 7, 1),
        "internal_ref": None,
        "ai_summary": "Screening threshold changed from SGD 20,000 to SGD 5,000.",
        "obligation_change": True,
    }
    base.update(over)
    return Alert(**base)


def digest_of(*alerts) -> Digest:
    return Digest(recipient="mlro@firm.com.sg", org_name="Firm", alerts=alerts)


def test_mapped_template_used_when_a_control_is_affected():
    subject, html = render_digest(digest_of(make_alert(internal_ref="AML-POL-4.2")))
    assert "AML-POL-4.2" in subject
    assert "Notice 626" in subject and "6.14" in subject
    assert "one of your controls" in html


def test_watchlist_template_used_when_nothing_is_mapped():
    subject, html = render_digest(digest_of(make_alert()))
    assert "Notice 626" in subject
    assert "Instruments you follow" in html
    assert "control mapped to it yet" in html


def test_mapped_alerts_lead_and_watchlist_hits_ride_along():
    _, html = render_digest(digest_of(
        make_alert(alert_id=1, internal_ref="AML-POL-4.2"),
        make_alert(alert_id=2, section_key="8.1"),
    ))
    assert html.index("Your controls") < html.index("Also on your watchlist")


def test_every_change_carries_the_official_mas_link():
    _, html = render_digest(digest_of(make_alert(internal_ref="AML-POL-4.2")))
    assert 'href="https://www.mas.gov.sg/regulation/notices/notice-626"' in html


def test_clause_text_is_never_in_the_email():
    """§11: the email carries the summary and the clause number, not the clause."""
    alert = make_alert(ai_summary="Threshold changed.")
    _, html = render_digest(digest_of(alert))
    assert not hasattr(alert, "new_body")
    assert "Threshold changed." in html


def test_dates_are_described_not_interpreted():
    _, html = render_digest(digest_of(make_alert()))
    assert "revised 30 June 2025" in html
    assert "effective 1 July 2025" in html


def test_an_effective_date_equal_to_the_revision_date_is_not_repeated():
    _, html = render_digest(digest_of(
        make_alert(effective_date=date(2025, 6, 30))))
    assert html.count("30 June 2025") == 1


def test_renumbering_without_a_summary_still_says_something_useful():
    _, html = render_digest(digest_of(
        make_alert(op="RENUMBERED", ai_summary=None, obligation_change=False)))
    assert "The clause number changed; the wording did not." in html


def test_prescriptive_language_is_refused():
    with pytest.raises(PrescriptiveEmail):
        render_digest(digest_of(
            make_alert(ai_summary="You must update your onboarding policy.")))


def test_pdf_text_is_escaped():
    _, html = render_digest(digest_of(
        make_alert(internal_ref='<b>REF</b>', ai_summary='<script>alert("x")</script> & more')))
    assert "<script>" not in html
    assert "&lt;script&gt;" in html
    assert "&lt;b&gt;REF&lt;/b&gt;" in html


def test_the_em_dash_is_an_entity_not_literal_text():
    """The site shipped literal "&larr;" once. Not twice."""
    _, html = render_digest(digest_of(make_alert(internal_ref="AML-POL-4.2")))
    assert "&amp;mdash;" not in html
    assert "AML-POL-4.2 &mdash; Notice 626 6.14" in html


def test_empty_digest_is_an_error_not_an_empty_email():
    with pytest.raises(ValueError):
        render_digest(digest_of())


def test_subject_pluralises_across_several_instruments():
    subject, _ = render_watchlist(digest_of(
        make_alert(alert_id=1),
        make_alert(alert_id=2, instrument_ref="PSN01"),
    ))
    assert subject == "2 clause changes across 2 instruments you follow"


# ---------- transport ----------

def test_resend_posts_the_documented_shape():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["auth"] = request.headers["authorization"]
        seen["body"] = json.loads(request.read())
        return httpx.Response(200, json={"id": "msg_123"})

    client = ResendClient(api_key="re_test", sender="Clausewatch <alerts@example.sg>",
                          transport=httpx.MockTransport(handler))
    assert client.send(to="a@b.sg", subject="s", html="<p>h</p>") == "msg_123"
    assert seen["url"] == "https://api.resend.com/emails"
    assert seen["auth"] == "Bearer re_test"
    assert seen["body"] == {
        "from": "Clausewatch <alerts@example.sg>", "to": ["a@b.sg"],
        "subject": "s", "html": "<p>h</p>",
    }


def test_resend_surfaces_the_api_message_on_failure():
    """An unverified sending domain and a bad key are both 4xx; the body distinguishes."""
    transport = httpx.MockTransport(
        lambda r: httpx.Response(403, json={"message": "The domain is not verified."}))
    client = ResendClient(api_key="re_test", sender="x@y.sg", transport=transport)
    with pytest.raises(ResendError, match="not verified"):
        client.send(to="a@b.sg", subject="s", html="<p>h</p>")


def test_unconfigured_client_refuses_rather_than_guessing():
    client = ResendClient(api_key="", sender="")
    assert not client.configured
    with pytest.raises(ResendError, match="ALERT_FROM"):
        client.send(to="a@b.sg", subject="s", html="<p>h</p>")
