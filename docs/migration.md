# From Lively v0.1 to v0.2

v0.2 removes Weixin-specific authorization hooks, complex binding hashes and the old `lively_contact` tool. Its new `lively_schedule` prepares a stable per-Profile gate script, while Hermes native Cron owns the schedule, destination and enable/disable state.

1. Before updating, list Cron tasks and **pause the exact old `lively-proactive` job(s)**. Confirm there is no in-flight run. Do not blindly delete other Cron tasks.
2. Install/update the plugin and reload it in a new session. Confirm the two new tools are available.
3. The user must explicitly authorize a new private delivery destination. Legacy Weixin bindings do not migrate automatically.
4. Call `lively_schedule(action="prepare")`, then create one paused native Cron with `script=lively-gate.py`, `schedule=23m`, `continuity=true`, `attach_to_session=true`, `catch_up=false` and verified delivery settings; inspect and resume only after validation.
5. Old personal `gallery/manifest.json` entries are copied into `gallery/legacy/metadata.json` on first gallery access. Existing image files and the old manifest stay intact. Native folder metadata can be edited independently.
6. Old `data.db` and legacy preflight scripts are preserved, not silently deleted. Remove a legacy script only after verifying no Cron task references it and after confirming the rollback path is no longer needed.

On failure, pause the new task and keep the prior data untouched. The old 30m Cron remains paused until the user deliberately switches back.

`config.json` is newly created with v0.2 defaults; old occasional/regular/clingy values do not map automatically. For profile-wide `cron.wrap_response`, avoid unrequested global changes. Older Hermes versions without per-job wrapping require the user's explicit decision.
