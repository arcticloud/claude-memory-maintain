#!/usr/bin/env python3
"""Phase 1+2 of memory compaction: archive + interleave. Mechanical, lossless, idempotent.

Phase 1 (archive): APPEND a dated snapshot of the current MEMORY.md to MEMORY-ARCHIVE.md.
Phase 2 (interleave): for every "- [...](file.md)" line in MEMORY.md, append that exact line
verbatim to the end of its target topic file (dedup by exact text) so recall brings back
updates that only ever lived in the index.

This script does NOT rewrite MEMORY.md itself and does NOT decide what to keep/archive —
that classification needs judgment (Phase 3) and is done by the agent, not this script.

Usage:
    python memory_compact.py --memory-dir <path> --stamp YYYY-MM-DD [--dry-run]

Invariants:
- Idempotent: re-running appends nothing new (dedup by exact line text already present in file).
- Archive is always appended to, never overwritten (a fresh dated "## Snapshot YYYY-MM-DD"
  section each run — this is the fix for a defect in an earlier prototype where a second
  compaction clobbered the first).
- Links containing "/" or "\\" (files outside the memory dir) are reported, not interleaved.
- Missing target files and non-UTF-8 files are reported, not fatal.
- Prints a JSON report at the end (counts: entries/appended/already/external/missing/errors) for
  Phase 3 to consume.

The header strings below (SNAPSHOT_HEADER_PREFIX, INTERLEAVE_HDR_PREFIX) are plain constants —
edit them if you want a different language or format; the dedup logic matches on exact text,
so changing them mid-project just starts a new lineage rather than breaking anything.
"""
import argparse
import json
import re
import sys
from pathlib import Path

LINK_RE = re.compile(r"\]\(([^()]+?\.md)\)")
INTERLEAVE_HDR_PREFIX = "## MEMORY.md index line as of compaction"


def bytes_len(s):
    return len(s.encode("utf-8"))


def compact(memory_dir: Path, stamp: str, dry_run: bool):
    idx_path = memory_dir / "MEMORY.md"
    arc_path = memory_dir / "MEMORY-ARCHIVE.md"

    if not idx_path.exists():
        return {"error": f"MEMORY.md not found in {memory_dir}"}

    text = idx_path.read_text(encoding="utf-8")

    stats = {"entries": 0, "appended": 0, "already": 0}
    external, missing, errors = [], [], []

    # Phase 1: append a dated snapshot to the archive (never overwrite)
    snapshot_header = f"## Snapshot {stamp}"
    already_archived = False
    if arc_path.exists():
        arc_existing = arc_path.read_text(encoding="utf-8")
        already_archived = snapshot_header in arc_existing
    else:
        arc_existing = "# Memory index archive (dated MEMORY.md snapshots)\n"

    if not already_archived:
        snapshot = (
            f"\n\n{snapshot_header}\n\n"
            "Verbatim copy of MEMORY.md at compaction time. Every line is also interleaved "
            "verbatim into the end of its topic file (see below).\n\n" + text.rstrip("\n") + "\n"
        )
        if not dry_run:
            with arc_path.open("a", encoding="utf-8", newline="\n") as f:
                f.write(snapshot)
    stats["archive_snapshot_appended"] = not already_archived

    # Phase 2: interleave each index line into its topic file
    interleave_hdr = f"{INTERLEAVE_HDR_PREFIX} {stamp} (verbatim; may contain updates not reflected above)"
    for line in text.splitlines():
        ls = line.strip()
        if not ls.startswith("- "):
            continue
        m = LINK_RE.search(ls)
        if not m:
            continue
        stats["entries"] += 1
        target = m.group(1)
        if "/" in target or "\\" in target:
            external.append(target)
            continue
        fp = memory_dir / target
        if not fp.exists():
            missing.append(target)
            continue
        try:
            body = fp.read_text(encoding="utf-8")
        except UnicodeDecodeError as e:
            errors.append({"target": target, "error": str(e)})
            continue
        if ls in body:
            stats["already"] += 1
            continue
        addition = body.rstrip("\n") + "\n\n---\n\n" + interleave_hdr + "\n\n" + ls + "\n"
        if not dry_run:
            try:
                fp.write_text(addition, encoding="utf-8", newline="\n")
            except OSError as e:
                errors.append({"target": target, "error": str(e)})
                continue
        stats["appended"] += 1

    stats["external"] = external
    stats["missing"] = missing
    stats["errors"] = errors
    stats["dry_run"] = dry_run
    return stats


def main():
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except AttributeError:
            pass

    ap = argparse.ArgumentParser()
    ap.add_argument("--memory-dir", required=True)
    ap.add_argument("--stamp", help="date stamp for this run, YYYY-MM-DD (required — pass explicitly, this script does not read the clock)", required=True)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    report = compact(Path(args.memory_dir), args.stamp, args.dry_run)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    sys.exit(1 if "error" in report else 0)


if __name__ == "__main__":
    main()
