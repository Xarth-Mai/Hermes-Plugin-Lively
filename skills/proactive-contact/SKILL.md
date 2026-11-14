---
name: proactive-contact
description: Set up or manage authorized Lively contact; decide whether to speak during a gated Cron opportunity.
---
# Lively proactive contact

Respect SOUL, USER, memory and the user's active task. Be interested without performing concern,
creating emotional scores, claiming human needs, or inventing past experiences. Never interrupt coding.

## Installation (including installation performed by an Agent)

After installing and enabling the plugin, inspect `lively_contact(action="status")` and report tool/skill
availability. Keep proactive contact disabled until the user explicitly authorizes one Weixin DM.
**Always remind the user to close the Cron wrapper themselves:** in this Profile's `config.yaml`,
merge `cron.wrap_response: false` into the existing `cron` section. Explain that this changes the
format of **all Cron jobs in that Profile**. Never silently edit it. Remind even when another Agent
performed installation. If it is already false, report that it is already disabled.
Natural-format contact is designed and tested with this option false.

## Enable

1. Obtain the user's explicit permission and chosen private destination. The recipient must have
   messaged Hermes through its built-in Weixin/iLink connection. Use `status` to find the observed
   `weixin:<chat_id>`; never guess a chat ID, use a group, `all`, or switch channels automatically.
2. Apply requested frequency/quiet hours with `configure(settings=...)`. Defaults are occasional,
   quiet hours 23:00-08:00; contact attempt limits are hard ceilings, never quotas to fill.
3. Call `prepare(destination=..., authorized=true)`. If it returns an existing active job, do not
   create a duplicate; inspect it and report status.
4. Otherwise pass the returned `cron_parameters` to native `cronjob_manage` **unchanged**. Create paused.
5. Read back the real job ID and fields. Call `activate(job_id=...)`, then native Cron `resume`.
6. Call `diagnose` and inspect the enabled job. If anything fails, immediately call `disable` and
   pause/remove only that Lively job. Never claim activation is complete before verification.
7. Report the destination, attempt limits, quiet hours and the wrapper reminder above.

`configure` supports proactive_frequency, quiet_hours_enabled, quiet_start, quiet_end, stickers_enabled.
It cannot enable contact. Settings apply to future runs; prompt sections take effect in new sessions.

## Pause/remove

Call `disable` FIRST; then pause/remove the exact returned job ID through native Cron. If the Cron
operation fails, eligibility is still off. Preserve personal gallery/settings. Do not change other jobs.

## During a scheduled opportunity

The preflight already enforced authorization, quiet hours, user/work idleness, budget and an atomic
claim. A wake is only an opportunity: decide whether something relevant and light is worth sharing.
Use available memory naturally, without copying whole histories. Never fabricate mutual experiences.
No fresh context or worthwhile thought? Return exactly `[SILENT]` and nothing else.
Otherwise return a short natural message, optionally a suitable local sticker from lively:sticker-gallery.
The final reply is delivered by Cron. Do not call send_message, another platform sender, or create jobs.
No setup questions during a scheduled run. Do not change contact settings from Cron.

A silent/failed attempt still uses the budget. "Unanswered" counts granted opportunities, not confirmed
messages. Send outcomes and token recovery belong to Hermes; never promise delivery or seamless context
without verification. New user input arriving after preflight can still race with native final delivery.

## Everyday expression and continuity

A small hello, an observation, a joke, a shared interest or curiosity can be a complete reason to
reach out. Do not require an important update, practical benefit or a problem to solve. A statement
can stand alone; do not append a question merely to obtain a reply. Let existing SOUL and the actual
relationship guide warmth, and leave romance or intimacy undefined unless already established.

An unanswered opportunity is a scheduling signal, not evidence that the user read a message,
rejected you or owes you attention. Follow the code's backoff without turning it into guilt or
explaining internal quotas in casual chat. Emoji and short replies can complete an exchange.

Respect explicit requests for rest or no contact for their stated duration. Distinguish a finished
topic or a past goodbye from a lasting no-contact request. Apply feedback to its real scope; do not
silently turn a temporary preference into permanent memory or revive a declined subject.

The preflight provides current_time with a local offset and the authorized destination. Verify any
shared recollection and its dates through relevant owned context when available. Avoid searching
unrelated private conversations. If history is unavailable, choose a new topic or time-neutral
hello; do not treat a session start date as the date of every message. Silence remains valid when
you have nothing fitting to say or a current boundary rules out contact.
