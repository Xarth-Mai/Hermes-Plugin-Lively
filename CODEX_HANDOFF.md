# Codex handoff · Hermes Lively v0.2

**Source branch**: `feat/lively-minimal-v02`
**Base**: `main` at `3ed24d0e8d7791c31d400a0da64be8eab46e3c7f`
**Goal**: review, repair, accept, merge, push and clean up this implementation. Do not assume that a static code review proves real platform delivery.

## Required outcome

- Preserve the deliberately small split: native Hermes Cron/Gateway handles scheduling and delivery, Lively `gate.py` handles a 23-minute stochastic gate and hard wake limits, Agent chooses final text or `[SILENT]`, `stickers.py` handles folder-local `metadata.json`.
- Native context flags: `attach_to_session=true`, `continuity=true`, `catch_up=false`, `failure_deliver=local`; task-level `wrap_response=off` when available. Do not modify Hermes upstream.
- Default wake behavior: 15% each eligible check, 5h minimum cooldown, 2 wakes/rolling 24h, 12 wakes/rolling 7d, 23:00–08:00 quiet hours (Profile local time). A silent wake consumes allowance. Tuning cannot raise the hard quotas.
- Installation stays opt-in: plugin installation must not automatically create/send Cron. `INSTALL.md` is the first-time Agent workflow; README shows both prompt and one-liner entries.
- No Weixin-specific hook, cross-channel duplicate state, custom sender or additional Agent. New gallery keeps earlier user images non-destructively.

## Suggested Codex review path

1. Fetch this branch and compare it with `main`; check all removals and modified tests. Preserve unrelated changes from other contributors.
2. Install dev requirements and run `python -m pytest -q`, `python -m ruff check .`, `python scripts/validate-assets.py` on 3.11–3.13 if possible.
3. Check the upstream-pinned contract via `python scripts/check-hermes.py --source /path/to/pinned/hermes-agent` and fix real mismatches in plugin code or docs. No runtime model or live sends in automated checks.
4. Audit gate atomicity, invalid input / clock handling, source path symlinks, no silent quota bypass, interrupted setup and old gallery migration. Check `cronjob_manage` relative script path and task-level `wrap_response` version support.
5. On an authorized sandbox Profile, test the real install and native Cron lifecycle (paused create → inspect → resume → pause), `continuity` / `attach_to_session`, text/media delivery and account/profile separation. Do not target a real user without consent.
6. Update `docs/validation.md` with tested outcomes. Remove any stale v0.1 references or invalid migration steps. After fixing, merge the verified branch to `main`, push, remove the finished branch and its obsolete artifacts. Preserve existing user data and unrelated Cron tasks.

## Known host limitation

Hermes pinned source parses invalid or failed script output as wake-allowed. `scripts/lively-gate.py` handles ordinary Python exceptions with `wakeAgent=false`, but script missing/interpreter launch failure can still wake the model. No Hermes patch is authorized. This makes a script gate a best-effort frequency control, not a strict safety guarantee against catastrophic host failure.

## Handoff checklist

- [ ] Unit tests and static checks verified
- [ ] Pinned Hermes Plugin Doctor / Cron contract verified
- [ ] `README.md` + `INSTALL.md` commands verified in clean Profile
- [ ] Legacy-gallery files retained and migrated safely
- [ ] Explicit recipient authorization and no duplicate Cron tasks
- [ ] Actual context continuity and media delivery checked or marked untested
- [ ] CI green and residual risks documented
- [ ] Fixes committed, branch merged to `main`, pushed, old branch cleaned
