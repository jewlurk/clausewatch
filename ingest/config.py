"""Central config loaded from environment (see .env.example).

Secrets are read from the environment only — never hardcoded. In CI/prod they come
from GitHub Actions / Cloudflare secrets; locally from a gitignored .env.
"""
from __future__ import annotations

import os
from dataclasses import dataclass

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:  # dotenv is a dev convenience; prod injects real env vars
    pass


@dataclass(frozen=True)
class Config:
    supabase_url: str
    database_url: str | None
    crawler_user_agent: str
    crawler_min_interval_seconds: float

    @classmethod
    def from_env(cls) -> Config:
        return cls(
            supabase_url=os.environ.get("SUPABASE_URL", ""),
            database_url=os.environ.get("DATABASE_URL"),
            crawler_user_agent=os.environ.get(
                "CRAWLER_USER_AGENT", "clausewatch/0.1"
            ),
            crawler_min_interval_seconds=float(
                os.environ.get("CRAWLER_MIN_INTERVAL_SECONDS", "2")
            ),
        )
