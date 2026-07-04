#!/usr/bin/env python3
"""Read-only audit of a Claude Code memory directory. Never writes anything.

Usage:
    python memory_audit.py --memory-dir <path> [--budget 20480] [--quiet]
    python memory_audit.py --from-cwd [--budget 20480] [--quiet]

Exit code: 0 if MEMORY.md is within budget, 1 if it exceeds budget (for hook use).
"""
import argparse
import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

LINE_RE = re.compile(r"^- .*\]\(([^()]+?\.md)\)")
MAX_LINE_BYTES = 400
STALE_WEEKS = 6
ARCHIVE_NAME_HINTS = ("handoff", "eod", "session")
SUPERSEDED_MARKERS = ("SUPERSEDED", "устарело", "УСТАРЕЛО")
DATE_RE = re.compile(r"(20\d{2})[-_](\d{2})[-_](\d{2})")


def slug_from_cwd():
    cwd = os.getcwd()
    return re.sub(r"[:\\/.]", "-", cwd)


def resolve_memory_dir(args):
    if args.memory_dir:
        return Path(args.memory_dir)
    if args.from_cwd:
        slug = slug_from_cwd()
        return Path.home() / ".claude" / "projects" / slug / "memory"
    raise SystemExit("need --memory-dir or --from-cwd")


def bytes_len(s):
    return len(s.encode("utf-8"))


def extract_date(name):
    m = DATE_RE.search(name)
    if not m:
        return None
    try:
        return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)), tzinfo=timezone.utc)
    except ValueError:
        return None


def audit(memory_dir: Path, budget: int):
    idx_path = memory_dir / "MEMORY.md"
    if not idx_path.exists():
        return {"error": f"MEMORY.md not found in {memory_dir}"}

    text = idx_path.read_text(encoding="utf-8")
    size = bytes_len(text)
    lines = [l for l in text.splitlines() if l.strip().startswith("- ")]

    line_sizes = [(l, bytes_len(l)) for l in lines]
    top10 = sorted(line_sizes, key=lambda t: -t[1])[:10]
    oversized = [l for l, n in line_sizes if n > MAX_LINE_BYTES]

    targets_by_line = []
    dupes = {}
    broken_links = []
    referenced_files = set()
    for l in lines:
        m = LINE_RE.match(l.strip())
        if not m:
            continue
        target = m.group(1)
        if "/" in target or "\\" in target:
            continue  # external path, not a local topic file
        referenced_files.add(target)
        dupes.setdefault(target, []).append(l)
        fp = memory_dir / target
        if not fp.exists():
            broken_links.append({"line": l.strip(), "target": target})

    duplicate_targets = {t: ls for t, ls in dupes.items() if len(ls) > 1}

    existing_files = {
        p.name for p in memory_dir.glob("*.md")
        if p.name not in ("MEMORY.md", "MEMORY-ARCHIVE.md")
    }
    orphan_files = sorted(existing_files - referenced_files)

    now = datetime.now(timezone.utc)
    stale_cutoff = now - timedelta(weeks=STALE_WEEKS)
    archive_candidates = []
    for l in lines:
        ls = l.strip()
        lower = ls.lower()
        name_hint = any(h in lower for h in ARCHIVE_NAME_HINTS)
        marker_hit = any(mk in ls for mk in SUPERSEDED_MARKERS)
        d = extract_date(ls)
        stale = d is not None and d < stale_cutoff
        if (name_hint and stale) or marker_hit:
            archive_candidates.append({
                "line": ls,
                "reason": "superseded-marker" if marker_hit else "stale-handoff",
                "date": d.strftime("%Y-%m-%d") if d else None,
            })

    return {
        "memory_dir": str(memory_dir),
        "budget_bytes": budget,
        "index_size_bytes": size,
        "over_budget": size > budget,
        "entry_count": len(lines),
        "top10_by_bytes": [{"bytes": n, "line": l[:120]} for l, n in top10],
        "oversized_lines_over_400b": [{"bytes": bytes_len(l), "line": l[:160]} for l in oversized],
        "broken_links": broken_links,
        "duplicate_targets": {t: [l[:120] for l in ls] for t, ls in duplicate_targets.items()},
        "orphan_files": orphan_files,
        "archive_candidates": archive_candidates,
    }


def render_human(report):
    if "error" in report:
        return report["error"]
    lines = []
    status = "OVER BUDGET" if report["over_budget"] else "within budget"
    lines.append(
        f"MEMORY.md: {report['index_size_bytes']} bytes / {report['budget_bytes']} budget "
        f"({status}), {report['entry_count']} entries"
    )
    if report["oversized_lines_over_400b"]:
        lines.append(f"\n{len(report['oversized_lines_over_400b'])} line(s) over {MAX_LINE_BYTES}B (fat index lines):")
        for item in report["oversized_lines_over_400b"][:10]:
            lines.append(f"  [{item['bytes']}B] {item['line']}")
    if report["broken_links"]:
        lines.append(f"\n{len(report['broken_links'])} broken link(s):")
        for item in report["broken_links"]:
            lines.append(f"  -> {item['target']}: {item['line'][:100]}")
    if report["duplicate_targets"]:
        lines.append(f"\n{len(report['duplicate_targets'])} file(s) with multiple index lines pointing at them:")
        for t, ls in report["duplicate_targets"].items():
            lines.append(f"  {t}: {len(ls)} lines")
    if report["orphan_files"]:
        lines.append(f"\n{len(report['orphan_files'])} orphan topic file(s) (not referenced in index):")
        for f in report["orphan_files"][:15]:
            lines.append(f"  {f}")
    if report["archive_candidates"]:
        lines.append(f"\n{len(report['archive_candidates'])} archive candidate(s) (stale handoff/EOD or superseded):")
        for c in report["archive_candidates"][:15]:
            lines.append(f"  [{c['reason']}] {c['line'][:100]}")
    lines.append("\nTop 10 lines by size:")
    for item in report["top10_by_bytes"]:
        lines.append(f"  [{item['bytes']}B] {item['line']}")
    return "\n".join(lines)


def main():
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except AttributeError:
            pass

    ap = argparse.ArgumentParser()
    ap.add_argument("--memory-dir")
    ap.add_argument("--from-cwd", action="store_true")
    ap.add_argument("--budget", type=int, default=20480)
    ap.add_argument("--quiet", action="store_true", help="print nothing when within budget; used by hooks")
    args = ap.parse_args()

    memory_dir = resolve_memory_dir(args)
    report = audit(memory_dir, args.budget)

    if "error" in report:
        if not args.quiet:
            print(report["error"], file=sys.stderr)
        sys.exit(0)  # nothing to audit is not a failure

    if args.quiet:
        if report["over_budget"]:
            print(
                f"MEMORY.md index is {report['index_size_bytes']}B, over the {report['budget_bytes']}B budget "
                f"({report['entry_count']} entries). Run /memory-maintain to compact it (3-phase: "
                f"archive -> interleave into topic files -> rewrite index)."
            )
        sys.exit(1 if report["over_budget"] else 0)

    print(render_human(report))
    print("\n--- JSON ---")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    sys.exit(1 if report["over_budget"] else 0)


if __name__ == "__main__":
    main()
