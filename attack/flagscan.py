#!/usr/bin/env python3
"""flagscan.py — scrape flags from arbitrary text/responses and (optionally)
push them straight into the farm queue.

Handy for one-off exploitation from the shell: pipe anything through it and it
pulls out flags, de-dupes them, and can enqueue them so the submit loop sends
them. This lets you exploit by hand and still ride the farm's submission.

Examples:
    curl -s http://10.60.2.1:5000/dump | ./attack/flagscan.py
    ./attack/flagscan.py --enqueue --target 10.60.2.1 --exploit manual < loot.txt
    ./attack/flagscan.py -r '[A-Z0-9]{31}=' somefile.txt
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

# Make `farm` importable whether run from repo root or the attack/ dir.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def main() -> int:
    ap = argparse.ArgumentParser(description="scrape flags from text")
    ap.add_argument("files", nargs="*", help="files to scan (default: stdin)")
    ap.add_argument("-r", "--regex", default=r"[A-Z0-9]{31}=",
                    help="flag regex (default matches common 31+'=' format)")
    ap.add_argument("--enqueue", action="store_true",
                    help="insert found flags into the farm queue")
    ap.add_argument("-c", "--config", default="config/config.yaml")
    ap.add_argument("--target", default="manual", help="target tag for enqueue")
    ap.add_argument("--exploit", default="flagscan", help="exploit tag for enqueue")
    args = ap.parse_args()

    flag_re = re.compile(args.regex)
    texts: list[str] = []
    if args.files:
        for f in args.files:
            try:
                texts.append(Path(f).read_text(errors="replace"))
            except OSError as exc:
                print(f"flagscan: {f}: {exc}", file=sys.stderr)
    else:
        texts.append(sys.stdin.read())

    seen: list[str] = []
    seen_set: set[str] = set()
    for t in texts:
        for m in flag_re.findall(t):
            if m not in seen_set:
                seen_set.add(m)
                seen.append(m)

    for flag in seen:
        print(flag)

    if args.enqueue and seen:
        from farm.config import Config
        from farm.storage import Storage
        cfg = Config.load(args.config)
        store = Storage(cfg.db_path)
        n = store.add_flags((f, args.target, args.exploit) for f in seen)
        print(f"flagscan: enqueued {n} new flag(s) "
              f"({len(seen) - n} already known)", file=sys.stderr)

    return 0 if seen else 1  # exit 1 = nothing found (useful in pipelines)


if __name__ == "__main__":
    raise SystemExit(main())
