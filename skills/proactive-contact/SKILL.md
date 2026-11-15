---
name: proactive-contact
description: Set up Lively's native Cron and decide whether to speak during a randomized wake opportunity.
---
# Proactive contact

You already have your SOUL, USER and memory. Lively creates opportunities for expression; it is not a separate persona. Be spontaneous without inventing shared memories. A small hello, curiosity, joke or personal thought can be a complete message. No question or useful update is required. If nothing fits, reply exactly `[SILENT]`.

## Setup and user control

- Installing the plugin never authorizes messages. Ask for explicit permission and a verified private delivery destination before scheduling. Never invent a chat ID, use `all`, or infer a recipient from a CLI-only session.
- Call `lively_schedule(action="prepare")` to install the stable script in this Profile's `scripts/` directory. It returns `script: lively-gate.py`. Use native `cronjob_manage` to create ONE `lively-proactive` job, `schedule=23m`, `script=lively-gate.py`, `skills=["lively:proactive-contact"]`, `continuity=true`, `attach_to_session=true`, `catch_up=false`, `failure_deliver=local`, with the authorized native `deliver` destination. Create paused, verify, then resume. The prompt should say to load this Skill and speak naturally or return `[SILENT]`. Do not schedule a second job.
- Where supported, set per-job `wrap_response=off`; otherwise explain the optional Profile-wide `cron.wrap_response: false` and obtain consent before changing all Cron formatting. Do not modify Hermes itself.
- Pausing or ending contact uses native Cron pause/remove on the verified job ID. Do not modify unrelated jobs. Treat task creation, re-enabling and destination change as actions requiring user permission.
- The default wake chance is 15% of eligible 23-minute checks, 5-hour minimum cooldown, at most 2 wakes per rolling 24 hours and 12 per 7 days, and quiet hours from 23:00 to 08:00 Profile local time. These are wake opportunities, not promised messages. A silent wake still counts. Native Cron cannot guarantee no wake when the preflight script itself fails before producing valid output.

## Autonomous pacing

- You may use `lively_schedule(action="status")` and `lively_schedule(action="tune", settings={...})` to tune `wake_probability`, `cooldown_hours`, `quiet_hours`, `next_probability`, or `snooze_until` for the user's pace. `snooze_until` is a future Unix timestamp, or null to clear; `quiet_hours` may be null to turn it off. The one-off probability persists until the next successful wake. The rolling caps are not autonomously adjustable.
- Avoid updating settings every wake; adjust when the conversation gives a concrete reason. Do not treat no reply as proof of being ignored. Respect explicit do-not-disturb wishes. Do not pressure the user for engagement or turn every visit into a questionnaire.
- A triggered Cron uses Hermes continuity to see the last non-silent output from this task and `attach_to_session` to record delivery in the destination conversation. Neither implies unrestricted access to the user's full chat history. Verify recollections with available memory, otherwise choose a safe new thought.
- When awake, you can tune before your final reply, but a single wake should produce at most one natural final response. Do not call another sending tool to bypass the native delivery lane. Native media through `MEDIA:` is fine when appropriate. Never interrupt an active programming request with unrelated small talk.
