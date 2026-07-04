---
name: memory-maintain
description: Use when saving or updating a persistent memory entry, when MEMORY.md exceeds its load budget, when an index entry has grown beyond one line, when memory looks truncated or old entries seem to have vanished at session start, or when asked to compact, audit, or clean up memory.
---

# Memory Maintain

## Overview

`MEMORY.md` is an index, loaded **whole, every session, with a hard byte budget** (~24KB) —
anything over budget is silently truncated, cutting the *oldest* entries first, which are
usually the standing rules and reference facts, not the noise. Topic files carry the actual
knowledge and come back via recall regardless of index size. **The only failure mode that
matters is writing detail into the index instead of the file** — everything else is cosmetic.

## When to use

- Saving any new memory, or updating an existing one
- `MEMORY.md` is near/over budget (~20KB, buffer under the ~24KB hard limit)
- An index line has grown past one line / ~400 bytes
- Entries seem to be missing at session start (silent truncation symptom)
- Asked to compact, audit, or clean up memory

## Rules for writing (every session, no exceptions)

1. New memory = topic file (good `description:` — that's the recall key) **+ one index line
   ≤ 400 bytes**: `- [Title (date)](file.md) — hook: when to read this.` See
   [reference/index-format.md](reference/index-format.md).
2. Updating a memory = edit the **topic file**. Never append new facts to the index line — only
   touch the index line if the hook itself changed.
3. Before creating a file, check whether an existing one already covers the topic. Update it.
4. Fixed section order (adapt names to your own convention if you like, but keep it fixed):
   `Who/What → Active → Rules (feedback) → Reference → Archive`. New active entries go at the
   top of "Active".

## Audit

```bash
python ~/.claude/skills/memory-maintain/scripts/memory_audit.py --memory-dir <path> [--budget 20480]
```

Read-only. Reports: index size vs budget, entry count, oversized lines (>400B), broken links,
duplicate targets, orphan topic files, and archive candidates (stale handoff/EOD by name+date,
or SUPERSEDED markers). Exit 0 = within budget, 1 = over (used by the `SessionStart` guard —
see [reference/automation-levels.md](reference/automation-levels.md)).

## Compaction — 3 phases, lossless

Compaction rewrites long-term memory. **Run only on explicit user confirmation**, unless the
user has granted standing permission (a `feedback` memory saying so).

1. **Archive** (`memory_compact.py`, phase 1): append a dated `## Snapshot YYYY-MM-DD` section to
   `MEMORY-ARCHIVE.md` with the current index verbatim. Always append, never overwrite — a
   second compaction must not erase the first snapshot.
2. **Interleave** (`memory_compact.py`, phase 2): every index line gets appended verbatim to the
   end of its topic file, under `## MEMORY.md index line as of compaction YYYY-MM-DD`, deduped
   by exact text. This is what brings index-only updates back through recall.

   ```bash
   python ~/.claude/skills/memory-maintain/scripts/memory_compact.py --memory-dir <path> --stamp YYYY-MM-DD [--dry-run]
   ```

3. **Rewrite the index** (agent does this — needs judgment, not scriptable):
   - Keep: open threads, entries from the last ~6 weeks, all `feedback_*`, live `reference_*`,
     locked decisions.
   - Drop from the index (file untouched — it's already archived+interleaved): closed
     handoff/EOD, superseded plans, finished phases.
   - Compress every remaining line to the format in step 1 above, keeping READ-FIRST hooks.
   - End with one pointer line to `MEMORY-ARCHIVE.md`.
   - Verify: re-run the audit — size ≤ budget, 0 broken links. Report to the user what moved
     where.

## Red flags — rationalizations that mean STOP

Verified against a real baseline run (no skill present) on a production `MEMORY.md` that had
grown to 160KB against a 20KB budget over months of real use: all of these occurred, with exact
byte counts, even though a proper topic file was also created/updated correctly each time.
Topic-file discipline alone doesn't save you — the index line fails independently and needs its
own discipline. Re-run with this skill present produced correct behavior on all 4 scenarios
(index lines 250B and under, budget flagged unprompted, no compaction without confirmation).

| Excuse | Reality |
| --- | --- |
| "The other entries in the index already look like this" | Baseline agent matched the style of pre-existing 1300+B lines and produced a 561B line, calling it "compact." Matching bloated neighbors perpetuates the bloat — the target format doesn't depend on what's already there. |
| "The index line should reflect the current state" / "so a future session sees the update without opening the file" | Baseline agent said this verbatim while growing index lines to 1397B and 2069B with facts that belonged in the topic file. If the index has to carry enough detail to skip the file, it has stopped being an index — the hook's job is to make you *open* the file, not replace it. |
| "This fact is important, details belong in the index" / "faster to just append the update to the index line" | Wrong either way: details go in the file (recall brings it back); an update living only in the index line is the first thing lost on the next truncation or compaction. |
| Silence on an already-oversized budget | Baseline agent added to a 160KB index (8x the 20KB budget) without remarking on it once. Budget-awareness doesn't happen by default — run the audit before writing, every time, not just when asked to compact. |
| "Compacting = losing information" / "I'll delete the outdated stuff" | This skill never deletes. The 3 phases are archive + interleave + move — nothing is ever removed, only relocated. |
| "I'll clean it up later" | If the budget's already exceeded, the tail is *already* invisible in every session right now. |
| "The user said 'fast', so skip the file / fatten the index line as a shortcut" | Speed pressure is not permission to skip the file, and it's not permission to cram detail into the index either — file + one short line, always both, one extra tool call. |
| Re-running compaction later | Must append a new dated snapshot to `MEMORY-ARCHIVE.md`, never overwrite it — a second compaction erasing the first snapshot was a real defect in an earlier prototype of this skill's script. |
