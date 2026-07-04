# MEMORY.md index line format

One line per memory, under ~150 characters / 400 bytes. Non-ASCII text (Cyrillic, CJK, etc.)
runs more bytes per character than ASCII — e.g. Cyrillic is ~2 bytes/char, so a 150-character
Russian line is already ~300 bytes. Leave headroom, don't max it out.

```
- [Title (date)](topic_file.md) — hook: when to read this.
```

- `[Title (date)]` — short, scannable title. Date only if it matters for recency judgment.
- `(topic_file.md)` — the recall key. Local filename only, no path.
- ` — hook: ...` — one clause: when a future session should open this file. Not a summary of
  its contents. Detail lives in the file; recall brings the file back by its `description:` and
  by grep hits inside it. The index line's only job is to make you *want* to open the file.

## Good vs bad

**Bad — details crammed into the index line (fat line, breaks the budget, and updates written
here get silently dropped on the next compaction/truncation):**

```
- **[Billing bug 2026-07-03: invoice.paid webhooks arriving within 2s double-apply
  period_reset_at, ~14 users affected 2026-06-28..2026-07-02, root cause missing idempotency
  key in billing/webhooks.py:212, mitigated with a 5s Redis lock, deployed 14:20 UTC,
  permanent fix = unique constraint (user_id, period_start), monitored in dashboard id 41]
  (project_billing_dup_credit_2026_07_03.md)**
```

**Good — one line, everything else in the file:**

```
- [Double-credit billing bug fixed (2026-07-03)](project_billing_dup_credit_2026_07_03.md) — read before touching billing webhooks or period_reset_at.
```

## Updating an existing memory

Never append new facts to the index line. Open the topic file, add the new facts there (with a
**Why:**/**How to apply:** line if it's a feedback/project memory), and only touch the index
line if the *hook itself* changed (e.g. it's no longer "READ FIRST" because the issue is closed).

## Fixed section order

```
Who/What → Active → Rules (feedback) → Reference → Archive
```

(Any fixed order works — this is just an example. What matters is that it's fixed, so new
entries have one obvious place to go and old ones aren't scattered.)

New active entries go at the top of "Active". The "Archive" section ends with a single pointer
line to `MEMORY-ARCHIVE.md` — never a growing list of closed items (those move to the archive
file itself, per-topic-file interleaving brings their detail back via recall).
