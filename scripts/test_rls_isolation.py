"""RLS isolation test (T22, brief §8 — mandatory).

Proves that one organisation cannot read or write another's data. The brief calls a
leak here company-ending, and it is the first thing a financial institution's vendor
review probes, so this is proven rather than reasoned about.

Method: create two real users, orgs, mappings and alerts, then query as each user with
Postgres actually enforcing the policies — `set local role authenticated` plus a JWT
claim, which is exactly how PostgREST executes a request. Reasoning about policy SQL
is not evidence; making the database answer is.

Everything runs inside one transaction that is always rolled back, so the test leaves
no rows behind even when it fails.
"""
from __future__ import annotations

import json
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "ingest"))

from db import connect

failures: list[str] = []


def check(condition: bool, description: str) -> None:
    print(f"  {'PASS' if condition else 'FAIL'}  {description}")
    if not condition:
        failures.append(description)


def as_user(cur, user_id: str) -> None:
    """Execute subsequent statements as that signed-in user, as PostgREST would."""
    cur.execute("set local role authenticated")
    claims = json.dumps({"sub": user_id, "role": "authenticated"})
    cur.execute("select set_config('request.jwt.claims', %s, true)", (claims,))


def as_owner(cur) -> None:
    cur.execute("reset role")


def main() -> int:
    conn = connect()
    conn.autocommit = False
    user_a, user_b = str(uuid.uuid4()), str(uuid.uuid4())

    try:
        with conn.cursor() as cur:
            # --- fixtures, created as owner ---
            for uid, email in ((user_a, "a@firm-a.test"), (user_b, "b@firm-b.test")):
                cur.execute(
                    "insert into auth.users (id, email, instance_id, aud, role) "
                    "values (%s, %s, '00000000-0000-0000-0000-000000000000', "
                    "'authenticated', 'authenticated')",
                    (uid, email),
                )
            cur.execute("insert into organisations (name) values ('Firm A') returning id")
            org_a = cur.fetchone()[0]
            cur.execute("insert into organisations (name) values ('Firm B') returning id")
            org_b = cur.fetchone()[0]
            cur.execute("insert into memberships (user_id, org_id) values (%s, %s)",
                        (user_a, org_a))
            cur.execute("insert into memberships (user_id, org_id) values (%s, %s)",
                        (user_b, org_b))

            cur.execute("select id from instruments order by id limit 1")
            instrument_id = cur.fetchone()[0]
            for org, ref in ((org_a, "A-SECRET-CONTROL"), (org_b, "B-SECRET-CONTROL")):
                cur.execute(
                    "insert into control_mappings (org_id, instrument_id, section_key, "
                    "internal_ref) values (%s, %s, '6.14', %s)",
                    (org, instrument_id, ref),
                )
            cur.execute("select id from deltas limit 1")
            delta_row = cur.fetchone()
            for org in (org_a, org_b):
                cur.execute("insert into alerts (org_id, delta_id) values (%s, %s)",
                            (org, delta_row[0]))

            print("\n--- control_mappings ---")
            as_user(cur, user_a)
            cur.execute("select internal_ref from control_mappings")
            visible = {r[0] for r in cur.fetchall()}
            check("A-SECRET-CONTROL" in visible, "A sees its own mapping")
            check("B-SECRET-CONTROL" not in visible, "A cannot see B's mapping")

            as_owner(cur)
            as_user(cur, user_b)
            cur.execute("select internal_ref from control_mappings")
            visible = {r[0] for r in cur.fetchall()}
            check("B-SECRET-CONTROL" in visible, "B sees its own mapping")
            check("A-SECRET-CONTROL" not in visible, "B cannot see A's mapping")

            print("\n--- alerts ---")
            as_owner(cur)
            as_user(cur, user_a)
            cur.execute("select org_id from alerts")
            orgs = {str(r[0]) for r in cur.fetchall()}
            check(str(org_a) in orgs, "A sees its own alerts")
            check(str(org_b) not in orgs, "A cannot see B's alerts")

            print("\n--- writes across the boundary ---")
            cur.execute(
                "update control_mappings set internal_ref = 'HIJACKED' "
                "where internal_ref = 'B-SECRET-CONTROL'"
            )
            check(cur.rowcount == 0, "A cannot update B's mapping")
            cur.execute("delete from control_mappings where internal_ref = 'B-SECRET-CONTROL'")
            check(cur.rowcount == 0, "A cannot delete B's mapping")
            cur.execute("delete from alerts where org_id = %s", (org_b,))
            check(cur.rowcount == 0, "A cannot delete B's alerts")

            print("\n--- corpus stays closed to signed-in users ---")
            cur.execute("select count(*) from sections")
            check(cur.fetchone()[0] == 0, "signed-in user cannot read sections")
            cur.execute("select count(*) from deltas")
            check(cur.fetchone()[0] == 0, "signed-in user cannot read deltas")

            print("\n--- organisations ---")
            cur.execute("select name from organisations")
            names = {r[0] for r in cur.fetchall()}
            check("Firm A" in names, "A sees its own organisation")
            check("Firm B" not in names, "A cannot see B's organisation")

            as_owner(cur)
    finally:
        conn.rollback()  # nothing this test created survives
        conn.close()

    print()
    if failures:
        print(f"ISOLATION FAILED — {len(failures)} check(s): {'; '.join(failures)}")
        return 1
    print("Tenant isolation holds: no cross-organisation read or write is possible.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
