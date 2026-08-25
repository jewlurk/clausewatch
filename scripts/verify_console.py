"""End-to-end verification of the customer console (web/app.html).

Every call app.html makes is replayed here against the live database with row level
security actually enforced — `set local role authenticated` plus a JWT claim, which is
how PostgREST executes a signed-in request. Reading the policy SQL is not evidence;
making the database answer is.

What this cannot cover: Supabase Auth's magic-link delivery. Everything after the link
is clicked is exercised below.

Runs inside one transaction that is always rolled back, so it leaves no rows behind
even when it fails.
"""
from __future__ import annotations

import json
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "ingest"))

from db import connect

failures: list[str] = []
notes: list[str] = []


def check(condition: bool, description: str, detail: str = "") -> None:
    print(f"  {'PASS' if condition else 'FAIL'}  {description}" + (f"  [{detail}]" if detail else ""))
    if not condition:
        failures.append(description)


def as_user(cur, user_id: str) -> None:
    cur.execute("set local role authenticated")
    cur.execute(
        "select set_config('request.jwt.claims', %s, true)",
        (json.dumps({"sub": user_id, "role": "authenticated"}),),
    )


def as_owner(cur) -> None:
    cur.execute("reset role")


def as_anon(cur) -> None:
    cur.execute("reset role")
    cur.execute("set local role anon")
    cur.execute("select set_config('request.jwt.claims', %s, true)",
                (json.dumps({"role": "anon"}),))


def main() -> int:
    conn = connect()
    conn.autocommit = False
    user_a = str(uuid.uuid4())
    user_b = str(uuid.uuid4())
    email_a = "verify-a@example.test"

    try:
        with conn.cursor() as cur:
            for uid, email in ((user_a, email_a), (user_b, "verify-b@example.test")):
                cur.execute(
                    "insert into auth.users (id, email, instance_id, aud, role) "
                    "values (%s, %s, '00000000-0000-0000-0000-000000000000',"
                    " 'authenticated', 'authenticated')",
                    (uid, email),
                )

            # ---------- 1. first sign-in: bootstrap_org ----------
            print("\n--- sign-in / org bootstrap (app.html start()) ---")
            as_user(cur, user_a)
            cur.execute("select bootstrap_org(%s)", (email_a.split("@")[1],))
            org_a = cur.fetchone()[0]
            check(org_a is not None, "bootstrap_org returns an org id", str(org_a))

            cur.execute("select bootstrap_org(%s)", (email_a.split("@")[1],))
            org_a2 = cur.fetchone()[0]
            check(org_a2 == org_a, "second call is idempotent (no duplicate org)")

            cur.execute("select name from organisations where id = %s", (org_a,))
            row = cur.fetchone()
            check(row is not None and row[0] == "example.test",
                  "org is named from the email domain", row[0] if row else "no row")

            as_owner(cur)
            cur.execute("select count(*) from usage_events where org_id = %s "
                        "and event_type = 'signup'", (org_a,))
            check(cur.fetchone()[0] == 1, "signup usage_event recorded")

            # ---------- 2. list_instruments ----------
            print("\n--- list_instruments (watchlist + mapping name resolution) ---")
            as_user(cur, user_a)
            cur.execute("select id, external_ref, title, change_count, version_count "
                        "from list_instruments()")
            instruments = cur.fetchall()
            check(len(instruments) >= 11, f"returns the corpus ({len(instruments)} instruments)")
            check(all(r[3] is not None and r[3] > 0 for r in instruments),
                  "every instrument reports a non-zero change_count")
            check(all(r[2] for r in instruments), "every instrument has a title")
            # app.html derives the watchlist subtitle as title.split(" - ").pop()
            no_dash = [r[1] for r in instruments if " - " not in (r[2] or "")]
            check(not no_dash,
                  "every title contains ' - ' so the watchlist subtitle is not the whole title",
                  ", ".join(no_dash) if no_dash else "")
            inst_by_ref = {r[1]: r[0] for r in instruments}
            n626 = inst_by_ref.get("Notice 626")
            check(n626 is not None, "Notice 626 present")

            # ---------- 3. empty state ----------
            print("\n--- changes view, before following anything ---")
            cur.execute("select count(*) from my_changes(200)")
            check(cur.fetchone()[0] == 0, "my_changes is empty for a new org (empty state shows)")

            # ---------- 4. watchlist follow ----------
            print("\n--- watchlist follow / unfollow ---")
            cur.execute("insert into watchlists (org_id, instrument_id) values (%s, %s)",
                        (org_a, n626))
            check(cur.rowcount == 1, "follow: insert into watchlists permitted by RLS")
            cur.execute("select count(*) from watchlists where org_id = %s", (org_a,))
            check(cur.fetchone()[0] == 1, "follow: row is visible back to the same user")

            cur.execute("select count(*) from my_changes(200)")
            watch_rows = cur.fetchone()[0]
            check(watch_rows > 0, f"changes view populates from the watchlist ({watch_rows} rows)")
            check(watch_rows <= 200, "row cap honoured")

            # ---------- 5. control mappings ----------
            print("\n--- control mappings (bulk paste, upsert, remove) ---")
            cur.execute(
                "insert into control_mappings (org_id, instrument_id, section_key, internal_ref)"
                " values (%s, %s, '6.14', 'AML-POL-4.2')"
                " on conflict (org_id, instrument_id, section_key, internal_ref) do nothing",
                (org_a, n626),
            )
            check(cur.rowcount == 1, "mapping insert permitted by RLS")
            cur.execute(
                "insert into control_mappings (org_id, instrument_id, section_key, internal_ref)"
                " values (%s, %s, '6.14', 'AML-POL-4.2')"
                " on conflict (org_id, instrument_id, section_key, internal_ref) do nothing",
                (org_a, n626),
            )
            check(cur.rowcount == 0, "re-pasting the same line does not duplicate (upsert works)")

            cur.execute("select internal_ref, section_key from control_mappings "
                        "where org_id = %s", (org_a,))
            check(cur.fetchall() == [("AML-POL-4.2", "6.14")], "mapping list reads back")

            cur.execute("select count(*) from my_changes(200) where internal_ref is not null")
            mapped = cur.fetchone()[0]
            check(mapped > 0, f"mapped clause appears tagged with the internal ref ({mapped} rows)")

            # duplicate-row check: watchlist AND mapping on the same delta
            cur.execute("select delta_id, count(*) from my_changes(500) "
                        "group by delta_id having count(*) > 1")
            dups = cur.fetchall()
            check(not dups, "no delta is listed twice when a clause is both watched and mapped",
                  f"{len(dups)} duplicated delta_ids" if dups else "")

            # ---------- 6. clause_keys (autocomplete) ----------
            print("\n--- clause_keys (mapping autocomplete) ---")
            cur.execute("select count(*) from clause_keys(%s)", (n626,))
            keys = cur.fetchone()[0]
            check(keys > 0, f"clause_keys returns the latest version's clause numbers ({keys})")

            # ---------- 7. org rename ----------
            print("\n--- account: rename organisation ---")
            cur.execute("update organisations set name = 'Renamed Firm' where id = %s", (org_a,))
            check(cur.rowcount == 1, "org rename permitted by RLS")

            # ---------- 8. usage events from the browser ----------
            print("\n--- usage events written by the browser client ---")
            for ev in ("login", "alert_viewed", "mapping_created"):
                cur.execute("insert into usage_events (org_id, event_type, metadata) "
                            "values (%s, %s, '{}'::jsonb)", (org_a, ev))
                check(cur.rowcount == 1, f"usage_event '{ev}' insert permitted by RLS")

            # ---------- 9. corpus stays closed ----------
            print("\n--- §11 guard: a signed-in user still cannot read the corpus ---")
            for tbl in ("sections", "deltas", "instruments", "instrument_versions"):
                cur.execute(f"select count(*) from {tbl}")
                check(cur.fetchone()[0] == 0, f"authenticated cannot select from {tbl}")

            cur.execute("select max(length(new_body)) from my_changes(500)")
            longest = cur.fetchone()[0]
            check(longest is None or longest <= 600,
                  "my_changes excerpt cap holds (<=600 chars)", str(longest))

            # ---------- 10. removals ----------
            print("\n--- remove mapping / unfollow ---")
            cur.execute("delete from control_mappings where org_id = %s", (org_a,))
            check(cur.rowcount == 1, "mapping removal works")
            cur.execute("delete from watchlists where org_id = %s and instrument_id = %s",
                        (org_a, n626))
            check(cur.rowcount == 1, "unfollow works")
            cur.execute("select count(*) from my_changes(200)")
            check(cur.fetchone()[0] == 0, "changes view empties again after unfollow")

            # ---------- 11. cross-org isolation on the console's own paths ----------
            print("\n--- isolation: user B cannot reach user A's console data ---")
            as_owner(cur)
            as_user(cur, user_b)
            cur.execute("select bootstrap_org('firm-b.test')")
            org_b = cur.fetchone()[0]
            check(org_b != org_a, "user B gets a different org")
            cur.execute("savepoint xorg")
            try:
                cur.execute("insert into watchlists (org_id, instrument_id) values (%s, %s)",
                            (org_a, n626))
                leaked = cur.rowcount == 1
            except Exception as exc:  # noqa: BLE001 — RLS refusing the write is the pass
                leaked = False
                _ = exc
            cur.execute("rollback to savepoint xorg")
            check(not leaked, "B cannot insert a watchlist row into A's org")

            cur.execute("update organisations set name = 'HIJACK' where id = %s", (org_a,))
            check(cur.rowcount == 0, "B cannot rename A's organisation")
            cur.execute("select count(*) from organisations where id = %s", (org_a,))
            check(cur.fetchone()[0] == 0, "B cannot see A's organisation")
            cur.execute("select count(*) from my_changes(200)")
            check(cur.fetchone()[0] == 0, "B's changes view does not show A's watched changes")

            # ---------- 12. anon is locked out of the console entirely ----------
            print("\n--- anon (the publishable key, which is public) ---")
            as_owner(cur)
            for fn, args in (("bootstrap_org", "'x'"), ("my_changes", "10"),
                             ("clause_keys", "1"), ("generate_alerts", "")):
                # Each probe is expected to raise, which aborts the transaction, so it
                # runs inside its own savepoint and the outer fixtures survive.
                cur.execute("savepoint probe")
                as_anon(cur)
                try:
                    cur.execute(f"select {fn}({args})")
                    allowed = True
                    message = "it was allowed"
                except Exception as exc:  # noqa: BLE001 — the refusal is the assertion
                    allowed = False
                    message = str(exc).strip().splitlines()[0]
                cur.execute("rollback to savepoint probe")
                as_owner(cur)
                check(not allowed and "permission denied" in message,
                      f"anon is refused {fn}()", message if allowed else "")

            # ---------- 13. alert generation (T26 prerequisite) ----------
            print("\n--- generate_alerts() idempotency (T26 depends on this) ---")
            as_owner(cur)
            # Give org A something to be alerted about: one mapped clause and one
            # followed instrument, which are the two alert routes T26 has to send.
            cur.execute(
                "insert into control_mappings (org_id, instrument_id, section_key, internal_ref)"
                " values (%s, %s, '6.14', 'AML-POL-4.2')", (org_a, n626))
            cur.execute("insert into watchlists (org_id, instrument_id) values (%s, %s)",
                        (org_a, n626))

            cur.execute("select count(*) from alerts where org_id = %s", (org_a,))
            check(cur.fetchone()[0] == 0, "no alerts for the org before generate_alerts()")

            cur.execute("select generate_alerts()")
            cur.execute("select count(*) from alerts where org_id = %s", (org_a,))
            first = cur.fetchone()[0]
            check(first > 0, f"generate_alerts() creates alerts for the org ({first})")
            cur.execute("select count(*) from alerts "
                        "where org_id = %s and mapping_id is not null", (org_a,))
            mapped_alerts = cur.fetchone()[0]
            check(mapped_alerts > 0,
                  f"mapped-control alerts created ({mapped_alerts}) — the T26 template that renews contracts")

            cur.execute("select generate_alerts()")
            cur.execute("select count(*) from alerts where org_id = %s", (org_a,))
            second = cur.fetchone()[0]
            check(second == first,
                  "running generate_alerts() twice creates no duplicate alerts",
                  f"after1={first} after2={second}")

    finally:
        conn.rollback()
        conn.close()

    print()
    for n in notes:
        print("NOTE:", n)
    if failures:
        print(f"\nCONSOLE VERIFICATION FAILED — {len(failures)} check(s):")
        for f in failures:
            print(f"  - {f}")
        return 1
    print("\nConsole verification passed: every path app.html uses works under RLS.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
