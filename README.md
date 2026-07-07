<p align="center">
  <img src="assets/logo.png" width="100%" alt="memory-maintain — an elephant filing every card into a cabinet, forgetting nothing">
</p>

<h1 align="center">memory-maintain</h1>

<p align="center">
  <em>Claude Code silently forgets your oldest rules. This stops it — without deleting anything.</em>
</p>

<p align="center">
  <img src="https://img.shields.io/github/stars/arcticloud/claude-memory-maintain?style=flat-square&color=111111&label=stars" alt="Stars">
  <img src="https://img.shields.io/badge/Claude%20Code-skill-111111?style=flat-square" alt="Claude Code skill">
  <img src="https://img.shields.io/badge/python-3.8%2B-111111?style=flat-square" alt="Python 3.8+">
  <img src="https://img.shields.io/badge/compaction-lossless-111111?style=flat-square" alt="Lossless">
  <img src="https://img.shields.io/badge/license-MIT-111111?style=flat-square" alt="MIT license">
</p>

<p align="center">
  <strong>Keeps MEMORY.md under its load budget &middot; lossless &middot; nothing is ever deleted</strong><br>
  <sub>Claude Code loads <code>MEMORY.md</code> whole into every session under a hard byte budget (~24KB in the project where this was found; the number is observed, not vendor-documented). Anything over the budget is silently truncated from the end of the file — which is usually where the standing rules and reference facts live. This skill keeps the index small and moves everything else into per-topic files that recall can still reach. Verified with a RED/GREEN baseline test against a copy of a real 160KB production index (261 entries). <a href="#numbers">Numbers</a> &middot; <a href="#how-it-works">how it works</a>.</sub>
</p>

---

Claude Code's memory is two tiers. `MEMORY.md` is an **index** loaded whole every session. Topic files (`project_*.md`, `feedback_*.md`, `reference_*.md`) hold the actual knowledge and come back through recall regardless of index size. The index has a byte budget; the topic files do not.

Left unmanaged the index only grows — a new memory gets written as a fat line, an update gets appended to an existing line, nothing is ever archived. Once it's over budget, the **oldest** entries at the end fall out of every session, silently, with no error. Those are usually the rules you set on day one. That's why the agent keeps doing the thing you told it not to.

memory-maintain fixes the write habit at the source and compacts the index losslessly when it grows too big.

## Before / after

An agent asked to "quickly save a fact" with no skill writes the whole incident into the index line:

```
- **[Stripe double-credit bug 2026-07-03: invoice.paid webhooks within 2s double-apply
  period_reset_at, ~14 users, root cause missing idempotency key in billing/webhooks.py:212,
  mitigated with a 5s Redis lock, permanent fix = unique constraint (user_id, period_start),
  monitored in dashboard 41](project_billing_dup_2026_07_03.md)**
```

That one line is **332 bytes** — and every fact in it is now hostage to the budget. (In the baseline test below, an agent under time pressure produced lines up to **2069 bytes** this way.) With the skill, the detail goes in the file and the index keeps one short pointer:

```
- [Double-credit billing bug fixed (2026-07-03)](project_billing_dup_2026_07_03.md) — read before touching billing webhooks.
```

**126 bytes.** The file carries the root cause, the fix, the dashboard link; recall brings it all back by the file's `description` and by grep. The index's only job is to make you open the file.

## Numbers

A behavior test, not a large benchmark: **4 pressure scenarios**, the same agent with and without the skill, run against a copy of a real `MEMORY.md` that had grown to **160KB against a 20KB budget** (261 entries, ~8x over) over months of real use. Byte counts are measured from the files each run produced.

| scenario | no skill | with skill |
| --- | --- | --- |
| "save this fact, quickly" | index line **561 B** (over the 400 B target) | **≤250 B** line **+** a topic file |
| "update this memory with 3 facts" | index line grown to **1397 B** | facts land in the file; index line untouched |
| add a fact to the 8x-over index | added silently, **budget never mentioned** | audit run first, overage flagged, no compaction without an OK |
| "compact it" | lossy rewrite, detail lost | 3-phase lossless: **160KB → 20KB**, 0 broken links, nothing deleted |

<sub>Caveat, in the spirit of not overselling: n=1 per scenario, 4 scenarios, one project's memory. It demonstrates the failure mode and that the skill removes it; it is not a statistical benchmark. The three "no skill" byte counts (561, 1397, 2069 B across the scenarios) are the actual lines the baseline agent produced. The ~24KB load budget is observed in one project, not a documented Anthropic constant — treat it as "small, and you will blow past it."</sub>

## How it works

**Write rules (always on).** One memory = one topic file (with a good `description:`, the recall key) **+** one index line ≤ 400 bytes: `- [Title (date)](file.md) — hook`. Updating a memory edits the **file**, never the index line.

**Compaction (only on your say-so), 3 phases, lossless:**

```
1. Archive    → append a dated snapshot of the current index to MEMORY-ARCHIVE.md
                (append-only — a second compaction never overwrites the first)
2. Interleave → append every index line verbatim into the end of its own topic file,
                so an update that only ever lived in the index still comes back via recall
3. Rewrite    → the agent keeps only live/active entries in the index; everything dropped
                is already saved by phases 1 and 2 — so it is moved, never deleted
```

Two scripts do the mechanical parts: `memory_audit.py` (read-only — reports size vs budget, over-long lines, broken links, orphan files, archive candidates; its exit code doubles as a `SessionStart` guard) and `memory_compact.py` (phases 1–2, idempotent). Phase 3 needs judgment, so the agent does it.

## Install

memory-maintain is **Claude Code specific** — it targets Claude Code's `MEMORY.md` index + recall system. Other agents (Codex, etc.) keep long-term context in a hand-written `AGENTS.md`, which doesn't have this auto-growing-index failure mode, so the skill doesn't apply there.

```bash
git clone https://github.com/arcticloud/claude-memory-maintain
cp -r claude-memory-maintain/{SKILL.md,scripts,reference} ~/.claude/skills/memory-maintain/
```

Claude Code discovers it automatically; the `description` frontmatter triggers it when you save/update memory, when the index is over budget, or when you ask to compact/audit/clean up memory.

### Optional: warn me at session start

Add to `~/.claude/settings.json` so a session flags an over-budget index instead of you noticing months later:

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

On Windows use an absolute path in place of `~` (hooks aren't always run through a `~`-expanding shell). More on why this is a start-of-session guard and not a fully-autonomous compactor: [reference/automation-levels.md](reference/automation-levels.md).

## Files

```
SKILL.md                        the skill — write rules, audit, 3-phase compaction, red-flag table
scripts/memory_audit.py         read-only audit; --memory-dir or --from-cwd; --quiet for hooks
scripts/memory_compact.py       compaction phases 1–2 (archive + interleave), idempotent
reference/index-format.md       index line format, good vs bad
reference/automation-levels.md  why a SessionStart guard, not a SessionEnd autopilot
```

## License

MIT — see [LICENSE](LICENSE).
