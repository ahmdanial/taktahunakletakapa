"""Command-line entrypoint for the farm.

Usage:
    python -m farm run      [-c config.yaml]   # attack + submit (full farm)
    python -m farm attack   [-c config.yaml]   # attack loop only
    python -m farm submit   [-c config.yaml]   # submit loop only
    python -m farm once     [-c config.yaml]   # one attack round + one submit
    python -m farm stats    [-c config.yaml]   # print queue counts and exit
    python -m farm teams    [-c config.yaml]   # print expanded target list
"""
from __future__ import annotations

import argparse
import sys
import threading

from .config import Config
from .runner import list_exploits, run_loop as run_attack
from .storage import Storage
from .submitter import run_loop as run_submit


def _load(args) -> tuple[Config, Storage]:
    cfg = Config.load(args.config)
    return cfg, Storage(cfg.db_path)


def cmd_run(args) -> int:
    cfg, store = _load(args)
    t = threading.Thread(target=run_submit, args=(cfg, store), daemon=True)
    t.start()
    try:
        run_attack(cfg, store)          # blocks; submit runs in background
    except KeyboardInterrupt:
        print("\n[farm] stopping")
    return 0


def cmd_attack(args) -> int:
    cfg, store = _load(args)
    try:
        run_attack(cfg, store)
    except KeyboardInterrupt:
        print("\n[farm] stopping")
    return 0


def cmd_submit(args) -> int:
    cfg, store = _load(args)
    try:
        run_submit(cfg, store)
    except KeyboardInterrupt:
        print("\n[farm] stopping")
    return 0


def cmd_once(args) -> int:
    cfg, store = _load(args)
    run_attack(cfg, store, once=True)
    run_submit(cfg, store, once=True)
    print("[farm] stats:", store.stats())
    return 0


def cmd_stats(args) -> int:
    cfg, store = _load(args)
    stats = store.stats()
    total = sum(stats.values())
    print(f"queue @ {cfg.db_path}  (total {total})")
    for k in ("QUEUED", "ACCEPTED", "REJECTED", "SKIPPED"):
        print(f"  {k:<9} {stats.get(k, 0)}")
    return 0


def cmd_teams(args) -> int:
    cfg, _ = _load(args)
    print(f"# {len(cfg.teams)} targets")
    for t in cfg.teams:
        print(t)
    exs = list_exploits(cfg.exploits_dir)
    print(f"# {len(exs)} exploit(s): "
          + ", ".join(e.rsplit('/', 1)[-1] for e in exs), file=sys.stderr)
    return 0


def main(argv: list[str] | None = None) -> int:
    # -c is accepted both before and after the subcommand.
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("-c", "--config", default="config/config.yaml",
                        help="path to config (default: config/config.yaml)")
    parser = argparse.ArgumentParser(prog="farm", parents=[common],
                                     description="A/D CTF exploit farm")
    sub = parser.add_subparsers(dest="cmd", required=True)
    for name in ("run", "attack", "submit", "once", "stats", "teams"):
        sub.add_parser(name, parents=[common])
    args = parser.parse_args(argv)
    return {
        "run": cmd_run, "attack": cmd_attack, "submit": cmd_submit,
        "once": cmd_once, "stats": cmd_stats, "teams": cmd_teams,
    }[args.cmd](args)


if __name__ == "__main__":
    raise SystemExit(main())
