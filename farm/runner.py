"""Attack loop: run every exploit against every target, extract flags, queue them.

An "exploit" is any executable file in `exploits_dir`. The farm invokes it as:

    ./exploit <TARGET_IP>

and also sets these environment variables for convenience:

    TARGET / HOST   the target ip
    FLAG_REGEX      the configured flag regex

The exploit should print whatever it finds to stdout; any substring matching
the flag regex is harvested. Exploits are expected to be short-lived; one that
runs past `exploit_timeout` is killed. Hidden files and names ending in
`.disabled` are ignored, so you can park a broken sploit without deleting it.
"""
from __future__ import annotations

import concurrent.futures as cf
import os
import re
import stat
import subprocess
import sys
import time

from .config import Config
from .storage import Storage


def list_exploits(exploits_dir: str) -> list[str]:
    out: list[str] = []
    if not os.path.isdir(exploits_dir):
        return out
    for name in sorted(os.listdir(exploits_dir)):
        if name.startswith(".") or name.endswith(".disabled"):
            continue
        path = os.path.join(exploits_dir, name)
        if not os.path.isfile(path):
            continue
        st = os.stat(path)
        if st.st_mode & (stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH):
            out.append(path)
        else:
            print(f"[runner] skipping non-executable {path} (chmod +x to enable)",
                  file=sys.stderr)
    return out


def run_one(exploit: str, target: str, flag_re: re.Pattern, timeout: int
            ) -> tuple[str, str, list[str], str]:
    """Run one (exploit, target). Returns (exploit, target, flags, note)."""
    env = dict(os.environ, TARGET=target, HOST=target, FLAG_REGEX=flag_re.pattern)
    try:
        proc = subprocess.run(
            [exploit, target],
            capture_output=True, text=True, timeout=timeout, env=env,
        )
        output = proc.stdout + "\n" + proc.stderr
        note = "" if proc.returncode == 0 else f"rc={proc.returncode}"
    except subprocess.TimeoutExpired as exc:
        output = (exc.stdout or "") if isinstance(exc.stdout, str) else ""
        note = "timeout"
    except OSError as exc:
        return (exploit, target, [], f"spawn-error: {exc}")
    flags = flag_re.findall(output)
    return (exploit, target, flags, note)


def attack_round(cfg: Config, store: Storage, flag_re: re.Pattern) -> dict:
    exploits = list_exploits(cfg.exploits_dir)
    if not exploits:
        print(f"[runner] no executable exploits in {cfg.exploits_dir!r}",
              file=sys.stderr)
        return {"jobs": 0, "new_flags": 0}
    jobs = [(e, t) for e in exploits for t in cfg.teams]
    found: list[tuple[str, str, str]] = []
    stats = {"jobs": len(jobs), "new_flags": 0, "errors": 0}
    with cf.ThreadPoolExecutor(max_workers=cfg.max_parallel) as pool:
        futs = {
            pool.submit(run_one, e, t, flag_re, cfg.exploit_timeout): (e, t)
            for (e, t) in jobs
        }
        for fut in cf.as_completed(futs):
            exploit, target, flags, note = fut.result()
            name = os.path.basename(exploit)
            if note and note != "":
                stats["errors"] += 1
            if flags:
                for f in flags:
                    found.append((f, target, name))
                print(f"[runner] {name} -> {target}: {len(flags)} flag(s)"
                      f"{' (' + note + ')' if note else ''}")
            elif note:
                print(f"[runner] {name} -> {target}: {note}", file=sys.stderr)
    stats["new_flags"] = store.add_flags(found)
    return stats


def run_loop(cfg: Config, store: Storage, once: bool = False) -> None:
    flag_re = re.compile(cfg.flag_regex)
    print(f"[runner] {len(cfg.teams)} targets, flag /{cfg.flag_regex}/, "
          f"every {cfg.run_every}s")
    while True:
        start = time.time()
        try:
            s = attack_round(cfg, store, flag_re)
            print(f"[runner] round: {s['jobs']} jobs, "
                  f"{s['new_flags']} new flags, {s.get('errors',0)} errors")
        except Exception as exc:  # keep the farm alive through a bad round
            print(f"[runner] round failed: {exc}", file=sys.stderr)
        if once:
            return
        elapsed = time.time() - start
        time.sleep(max(0.0, cfg.run_every - elapsed))
