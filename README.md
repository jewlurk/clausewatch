# Clausewatch

Clause-level change detection for Monetary Authority of Singapore (MAS) regulatory
instruments, mapped to a customer's own internal controls. See [CLAUDE.md](CLAUDE.md)
for the full build brief (business context, constraints, architecture, task backlog).

## Layout

| Path | What |
|---|---|
| `ingest/` | Python — crawler, PDF→sections parser, differ, LLM enrichment. Runs on GitHub Actions cron. |
| `api/` | TypeScript — Hono on Cloudflare Workers (read API). |
| `web/` | Cloudflare Pages — minimal static frontend + demo changelog. |
| `db/migrations/` | Numbered, forward-only SQL. The schema in CLAUDE.md §8 is the source of truth. |
| `.github/workflows/` | `test.yml` (on push), `crawl.yml` (daily cron). |
| `outreach/` | Sales prospect list (not code). |

## Dev setup (ingest)

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e "ingest[dev]"
cp .env.example .env      # fill secrets locally; .env is gitignored
pytest ingest             # CI runs this on every push
```

## Status

Stage 1 (ingest & parse) — scaffolding. The differ (Stage 2) is the product; nothing
downstream matters until it clears Gate G1 (<5% false positives on real MAS documents).

## Secrets — never commit

`SUPABASE_SECRET_KEY`, `DATABASE_URL` (with password), and all R2 keys go in
**GitHub Actions / Cloudflare secrets only**. The Supabase URL and publishable key are
public-safe and are the defaults in `.env.example`.
