# Automation levels

The skill itself cannot run "after every session" — skills only execute inside a live session.
Automation is hooks in `settings.json`, executed by the harness, not the model. Four levels,
enable top-down:

| Level | Mechanism | What it does | Status |
|---|---|---|---|
| L0 | This skill's write rules | Every new memory is written correctly at the source (one index line + file) | core, always on |
| L1 | `SessionStart` hook → `memory_audit.py --quiet` | Deterministic guard: injects "index over budget, run /memory-maintain" when MEMORY.md > budget | recommended |
| L2 | `/memory-maintain` (manual or triggered by L1) | Audit + 3-phase compaction, with confirmation | core |
| L3 | `SessionEnd` hook → headless `claude -p "/memory-maintain --auto"` | Fully autonomous, runs after every session | opt-in, off by default |

## L1 hook (SessionStart)

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

On Windows, use an absolute path instead of `~` (e.g. `%USERPROFILE%/.claude/skills/...` or the
literal `C:/Users/<you>/.claude/skills/...`), since hook commands aren't always run through a
shell that expands `~`.

`--from-cwd` derives the memory directory from the current working directory using the same
slug transform Claude Code uses for project paths (replace `[:\\/.]` with `-`).

## Why L3 is off by default

- Cost: a headless run after every single session, whether or not memory actually needs it.
- Races: two parallel sessions in the same project both writing `MEMORY.md` — needs a lock file.
- Silent edits: long-term memory gets rewritten with no human eyes on the diff.

Memory degrades by kilobytes per week, not per session — an `L1` guard at the start of the
*next* session catches it before it does damage. There's no practical need for `L3` unless `L1`'s
signal is being systematically ignored. If enabling `L3` anyway, scope `--auto` to a safe subset
only: reformatting fat lines (>400B → tail moved to topic file) without re-classifying sections,
behind a lock file, with a run log in `memory/maintenance-log.md`.
