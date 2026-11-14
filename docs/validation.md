# v0.2 validation status

Implementation branch: `feat/lively-minimal-v02`. This document records the checks performed while preparing the Codex handoff. Source tests and contract checks are automated; real sending and media rendering require a user's live Hermes Profile and consent.

## Automated checks

Local verification on Python 3.13.5: **14 unit tests passed**, asset validator passed, and Python source compilation passed. `ruff` and the pinned Hermes checkout were not available in this runtime, so those results are **not yet verified**.

- Python 3.11+ unit tests: initial defaults, probability overrides, cross-midnight quiet hours, rolling 24-hour / 7-day limits, concurrent claims, invalid state, stable script preparation, folder metadata, import/removal, path validation, parallel import and non-destructive legacy-gallery migration.
- Asset verification: original PNG assets and their corresponding folder metadata.
- Pinned Hermes host contract: plugin registration, tool/Skill exposure, Cron creation, script gate behavior and continuity options. Run via `python scripts/check-hermes.py --source /path/to/hermes-agent` at the pinned source SHA `bfe20f5586b3a26259f71669ad49ac85bd173f10`.

Do not mark CI, live deployment, or real delivery as passed merely because the above entry points exist. Check actual CI output and report verified results separately.

## Live acceptance still required

- Install into a clean Profile with the one-line command and verify tools, Skills and new-session prompt.
- Explicit private-target authorization, exactly one Cron, stable script path and pause/resume lifecycle.
- `attach_to_session` and `continuity` produce the intended chat and recurring-task history on a real platform.
- Confirm task-level `wrap_response` behavior on current Hermes, or document the global-setting tradeoff on older Hermes.
- Confirm image delivery and GIF behavior in at least two supported channels where available.
- Confirm pause/uninstall and Gateway restart behavior without surprise new messages; document the host script-failure fail-open edge.
- Confirm real Profile data and gallery remain intact during v0.1 → v0.2 migration.
