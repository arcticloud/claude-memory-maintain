# memory-maintain

A Claude Code skill that keeps `MEMORY.md` (Claude's persistent cross-session memory index)
under its load budget — without ever deleting anything.

## The problem

Claude Code's memory system is two-tiered: `MEMORY.md` is an index loaded **whole, every
session**, with a hard byte budget (~24KB). Topic files hold the actual knowledge and come back
through recall regardless of index size. Anything over budget in the index gets **silently
truncated** — and it truncates the *oldest* entries first, which tend to be standing rules and
reference facts, not noise.

Left unmanaged, an index degrades one habit at a time:

1. A new memory gets written as a fat index line (500–3000 bytes) instead of "one line + a file."
2. An update gets appended to an existing index line instead of edited into its topic file.
3. Nobody ever archives anything, so the index only grows.
4. The budget gets blown, and now the tail of the index — the old standing rules — is invisible
   in every future session, silently.

## What this skill does

- **Enforces a one-line-per-memory index format** (`- [Title](file.md) — hook`, ≤400 bytes) so
  detail lives in the file, not the index.
- **Read-only audit** (`memory_audit.py`) — reports index size vs. budget, oversized lines,
  broken links, duplicates, orphan files, and archive candidates. Exit code doubles as a
  `SessionStart` hook guard.
- **Lossless 3-phase compaction** (`memory_compact.py` for phases 1–2, judgment-based phase 3):
  archive the current index as a dated snapshot (append-only, never overwritten), interleave
  every index line verbatim into the end of its topic file (so nothing written only in the index
  is ever lost), then rewrite the index to just the active/standing entries.
- **Never deletes anything.** Every byte that leaves the index either moves to a topic file or to
  the archive.

## Why you'd trust this one

Most "agent skill" repos ship a plausible-sounding `SKILL.md` and no evidence it changes
behavior. This one was built by the [writing-skills](https://github.com/obra/superpowers)
TDD-for-documentation method: no skill gets written before you've watched an agent fail without
it.

**RED (baseline, no skill, against a real production index that had grown to 160KB against a
20KB budget over months of real use):**

| Scenario | What happened |
|---|---|
| "Save this fact, quickly, don't overthink it" | New index line: **561 bytes** (over the 400B cap) — the agent called it "compact," matching the style of already-bloated neighboring lines |
| "Update this existing memory with 3 new facts" | Topic file updated correctly, but the index line was rewritten to **1397 bytes** — "the index line should reflect the current state" |
| Index already 8x over budget, "add one more fact" | Appended anyway. Budget overage **never mentioned once** |

**GREEN (same 3 scenarios, skill present):** new index lines **250 bytes and under**; updates
land only in the topic file; the agent runs the audit unprompted and reports the pre-existing
budget overage instead of staying silent; compaction is proposed, never run without confirmation.

Full methodology, byte counts, and the red-flag rationalization table (with the exact
excuses the baseline agent used, verbatim) are in [SKILL.md](SKILL.md).

## Install

```bash
cp -r memory-maintain-skill/{SKILL.md,scripts,reference} ~/.claude/skills/memory-maintain/
```

Claude Code picks it up automatically — the skill's `description` frontmatter is what triggers
it (saving/updating memory, index over budget, asked to compact/audit/clean up memory).

### Optional: SessionStart guard

Add this to `~/.claude/settings.json` to get a heads-up at the start of every session when a
project's `MEMORY.md` is over budget:

```json
{
  "hooks": {
    "SessionStart": [{
      "hooks": [{
        "type": "command",
        "command": "python ~/.claude/skills/memory-maintain/scripts/memory_audit.py --from-cwd --quiet"
      }]
    }]
  }
}
```

See [reference/automation-levels.md](reference/automation-levels.md) for why this is a guard
(L1) rather than a fully autonomous `SessionEnd` compactor (L3, and why that's a bad default).

## Files

```
SKILL.md                     the skill itself — rules, audit, compaction, red flags
scripts/memory_audit.py      read-only audit, --memory-dir or --from-cwd, --quiet for hooks
scripts/memory_compact.py    phases 1+2 of compaction (archive + interleave), idempotent
reference/index-format.md    index line format, good vs. bad examples
reference/automation-levels.md   why SessionStart guard, not SessionEnd autopilot
```

## License

MIT — see [LICENSE](LICENSE).
