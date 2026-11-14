# v0.2 validation status

## Mai acceptance run — 2026-11-15 (Asia/Shanghai)

**Release gate: BLOCKED. PR #1 must remain open; do not install or enable a production proactive job on the strength of these checks.** This run was performed directly by Mai, with no delegated agent. The repository was cloned cleanly into `/ssk/Hermes-Plugin-Lively`; remote and branch were checked before changes. The complete `CODEX_HANDOFF.md` was read. Git, not the supplied ZIP, was the implementation authority.

### Verified in this run

- PR head initially `112c4d6f7151fe2f20e501a311ae8508a9cc31b5`; base branch `main`. GitHub API reported all eight existing check runs successful (unit 3.11/3.12/3.13 and pinned Hermes contract, duplicated push/PR runs). These are evidence for that remote head only, **not** for the subsequent local fixes.
- Python **3.14.10** on the actual host: **19 unit tests passed**. Final command: `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python3 -m pytest -q`. Disabling unrelated system pytest plugins avoids a host pytest-asyncio configuration warning; these tests are synchronous. Python 3.11–3.13 were not installed locally or rerun locally.
- Ruff passed using an isolated temporary venv; system Python did not have Ruff. Four folder-local PNG assets validated, 40,340 bytes total. `git diff --check` passed.
- Checked out the exact upstream Hermes SHA `bfe20f5586b3a26259f71669ad49ac85bd173f10` outside the plugin repository. `python3 scripts/check-hermes.py --source <checkout>` passed Doctor, plugin validation, registration/Skills/prompt assertions, native Cron and script fail-closed tests. A system-site-packages venv at the pinned checkout's `venv/` was required by that host's script-interpreter discovery; the first attempt without it failed and was not counted as a pass. No Hermes source was edited.
- Actual installed-host `hermes plugins doctor /ssk/Hermes-Plugin-Lively --ci` passed runtime discovery, manifest parsing, import and registration: plugin 0.2.0, two tools, zero hooks. This isolated Doctor result is **not** proof that the running Gateway loaded the plugin.
- Actual installed-host CLI lifecycle in a disposable `HERMES_HOME`, with no Gateway and `deliver=local`: paused create → read back disabled state → resume → read back enabled state → pause → read back disabled state → remove and verify absence. Schedule 23m, `context_from=["self"]` (continuity), `catch_up=false`, `failure_deliver=local`. This local-only CLI lifecycle did not exercise chat attachment; the pinned contract separately exercised `attach_to_session=true`.
- Current source routing was read from this execution job and independently checked with Discord GET channel: channel type 1 (DM), no guild, sole recipient is the explicitly authorized Lzz account. No test messages or media were sent: installation was already blocked, so waking the sleeping user would not complete end-to-end acceptance.
- Existing default-profile Cron was enumerated. No Lively proactive job existed; unrelated jobs were not changed. No other profile was operated on and no Gateway was restarted.

### Repairs and review

Regression tests were observed failing before the corresponding repairs:

1. Legacy migration resolved an image path before inspecting symlinks. A symlink pointing to a regular file inside `images/` was accepted. Reject source symlinks and symlink ancestors before resolution.
2. Legacy migration checked a personal-gallery root symlink only after migration had already written outside the intended gallery. Reject a symlinked personal root/ancestor before migration starts.
3. Gallery removal checked the immediate folder but not a symlinked personal-gallery root. Strengthen the shared image-path check to reject ancestor symlinks before metadata deletion/unlink.
4. An oversized legacy image could be copied and the migration completion marker written before later enumeration rejected its size. Check the 10 MiB bound before copying and marking completion.

An additional interruption/retry test verifies that a simulated metadata-write failure preserves original image/manifest bytes, does not mark migration completed, and permits a successful retry. The original concurrency tests verify one atomic SQLite claim across concurrent evaluations, rolling 24h/7d limits, silent-wake accounting, one-off overrides and default/custom quiet hours. Defaults remain 23m / 15% / 5h / 2 per rolling 24h / 12 per rolling 7d / 23:00–08:00. Soft tuning cannot modify hard-quota keys. SQLite `BEGIN IMMEDIATE` serializes claims. Configuration JSON and SQLite preferences are separate stores, not a cross-file crash-atomic transaction; interrupted soft tuning is not guaranteed all-or-nothing across both. Profile directories remain a trusted-owner boundary; path checks do not claim descriptor-relative protection against an adversary concurrently replacing parent directories.

The v0.1 code/removals and migration format were compared against remote main. Original assets/manifest/data.db are not deleted by the new migration. No old authorization is inherited. The architecture remains native Cron/Gateway + gate + Agent decision + local folder metadata; no custom sender, upstream patch, or extra agent was introduced.

### Blocking evidence

**1. Native installation cannot enable the plugin on this packaged host.**

In a clean disposable `HERMES_HOME`, the actual native installer cloned the exact local review commit through `file:///ssk/Hermes-Plugin-Lively --ref 2c69582f5970d1a0eb41ed0abd0c055d3eaf48b9 --enable`. This is a local-source installation test, not a claim that the README's remote one-liner was verified. Files installed, but enable was refused:

```text
Enable 'lively' refused: [Errno 2] No such file or directory:
'/usr/lib/python3.14/site-packages/uv.lock'
config.yaml and the active environment are unchanged.
The plugin stays installed but disabled.
```

The command returned process exit code 0 despite the refusal, so automation must inspect the actual enabled state, not just exit status. This matches the packaged-host managed dependency environment/publication limitation. It is a host integration blocker, not a passing deployment. No manual config enable, fake lockfile, alternate Hermes tree, source patch, or Gateway restart was used to route around it. The disposable installed tree was subsequently removed with the other test artifacts. A restart alone is not an established fix for a missing lockfile.

**2. The prescribed GitHub PAT cannot write this repository.**

Using `/root/.config/hermes/github.env`, pushing the local fix returned HTTP 403 (`Permission ... denied to Xarth-Mai`). A GitHub git-ref write probe also returned HTTP 403, `Resource not accessible by personal access token`; no probe branch was created. Read-only repository identity permissions reported `push=true`, which describes the account and does not prove this token's effective write permission. Credentials were not printed or substituted. Therefore no fixed-head CI run, remote merge, or branch cleanup can be claimed. Fixes and this record are committed locally for recovery.

### Not accepted / production state

- No real native Cron text/media delivery, target-chat transcript attachment, recurring output continuity, GIF behavior, or user-side rendering/continued conversation was exercised. Safe routing was verified, but no send occurred. A second platform was outside this run's authorization.
- The installed host has only profile-wide `cron.wrap_response` in its actual delivery implementation; no per-job field is exposed by `create_job`. No global wrapping setting was changed. Preserve existing wrapping until the owner separately authorizes a profile-wide change or a compatible host exposes a per-job option.
- `attach_to_session=true` and `continuity=true` are distinct: target chat attachment versus previous meaningful Cron output. Passing their offline contract does not prove a user's actual resumed chat experience.
- No production default-profile plugin installation or proactive task was created/enabled. No forced wake or quiet-hours override was used.
- PR remains unmerged and the feature branch must remain for recovery. Cleanup is limited to this run's disposable sandbox, isolated tooling and upstream contract checkout; user data, original handoff ZIP, source repository, and other Cron are retained.
- After resolving host installation and token permission blockers, rerun checks on the exact fixed remote head, verify CI, perform the authorized bounded native delivery/context tests, and only then consider merge and production installation. User-visible rendering and natural follow-up experience still need the user's later confirmation, never an invented automated pass.

### Residual native-host boundary

Pinned Hermes can treat a missing/interpreter-failed/invalid-output gate script as wake-allowed. The script catches ordinary Python exceptions and returns `{"wakeAgent":false}`, but cannot enforce hard quotas if the host never executes it. No upstream patch is authorized; these controls are not an absolute safety boundary against catastrophic host failure.

## Follow-up after explicit SSH authorization — 2026-11-15

- Pushed the local fixes and initial acceptance record through the existing GitHub SSH identity, without changing global Git configuration or credentials. Remote feature head was read back as `dda7de153d3f714c8041c9babce69eaff5fb46b4`.
- All eight push/PR check runs for that head passed: Python 3.11/3.12/3.13 and pinned Hermes contract. The earlier PAT write failure is no longer a push blocker; that token itself was not changed.
- Investigated the installed **python-hermes-agent 0.23.0-1**, rather than assuming the older `/ssk/python-hermes-agent` working tree describes the running package. The wrapper already sets `HERMES_INSTALL_ROOT=/usr/share/hermes-agent`; the stamp there declares `updateMechanism=external`.
- The native plugin admission calls `pm.client.sync_venv` for every candidate selection. `pm.paths.repo_root()` nevertheless resolves from the installed module to `/usr/lib/python3.14/site-packages`; `Venv.expected_stamp()` reads that root's `uv.lock`, and `Venv.apply()` builds a managed dependency generation from that source root. The package contains `pm/uv.lock` (PM's own runtime lock), not the missing core project lock. Those locks are not interchangeable.
- Thus merely adding a placeholder, copying PM's lock to the core path, or changing the asset-root environment does not repair admission. Even a genuine core lock by itself would not establish that replacing a distro-managed dependency environment is supported. No such workaround, source patch, manual enablement, or Gateway restart was performed.
- Remaining boundary: repair the externally managed host's native plugin admission/packaging contract before production installation and real delivery acceptance. This is outside Lively's implementation; the existing no-Hermes-source-change constraint remains in force. PR remains unmerged and production remains disabled.

## Earlier handoff results (historical only)

The original handoff reported 14 tests on Python 3.13.5 and green [Actions run 43631122552](https://github.com/Xarth-Mai/Hermes-Plugin-Lively/actions/runs/43631122552). Those results do not replace the current run or establish real delivery.
