# Validation status

This page summarizes the current release evidence and known limits. Historical review notes and machine-specific logs remain in Git history, not in the user-facing documentation.

## Automated checks

The v0.2.1 mainline at commit `6b13051` passed [GitHub Actions run 43696516887](https://github.com/Xarth-Mai/Hermes-Plugin-Lively/actions/runs/43696516887) on 2026-11-15:

- Unit tests, Ruff and bundled-asset validation on Python 3.11, 3.12 and 3.13
- Plugin Doctor, skill registration and native Cron contract checks against pinned Hermes source `bfe20f5586b3a26259f71669ad49ac85bd173f10`

See [Actions](https://github.com/Xarth-Mai/Hermes-Plugin-Lively/actions) for the status of newer commits. The pinned contract is a compatibility test, not a guarantee across every installed Hermes version.

## Host-specific verification

The previous deployment report records native installation and tool discovery on two profiles, plus shared-gallery lookup of 293 imported personal images. Those personal images are not part of this repository. These observations are environment-specific, not automated release tests.

The report did **not** establish end-to-end proactive text/media delivery, user-visible GIF rendering, chat transcript attachment or recurring contextual continuity on a real destination. These remain unverified; they must not be described as passed.

## Operating boundaries

- Installation does not grant permission to schedule or send messages. Verify the actual private destination, create the native Cron paused, inspect it, then resume only with explicit authorization.
- `attach_to_session` and `continuity` serve different purposes and must be evaluated separately.
- The script returns `wakeAgent=false` on ordinary handled failures. Some Hermes versions can still wake the model when the script cannot start or emits invalid output; the plugin does not patch Hermes.
- Existing user galleries, Cron tasks, profile settings and private records must be preserved during upgrade or uninstall unless the owner explicitly authorizes removal.

For setup and recovery instructions, see [INSTALL.md](../INSTALL.md) and [migration.md](migration.md).
