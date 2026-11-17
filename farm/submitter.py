"""Submit loop: pull queued flags, hand them to the backend, record results.

Runs independently of the runner so submission cadence (and rate limits) are
decoupled from exploit timing. Safe to run as its own process.
"""
from __future__ import annotations

import sys
import time

from . import protocols, storage
from .config import Config
from .storage import Storage


def submit_round(cfg: Config, store: Storage, backend) -> dict:
    sub = cfg.submit
    batch = store.take_queued(
        limit=int(sub.get("batch_size", 100)),
        max_age=float(cfg.flag_lifetime),
    )
    if not batch:
        return {"sent": 0, "accepted": 0, "rejected": 0, "requeued": 0}
    results = backend.submit(batch)
    counts = {"sent": len(batch), "accepted": 0, "rejected": 0, "requeued": 0}
    to_mark: list[tuple[str, str, str]] = []
    for flag, status, resp in results:
        if status == storage.ACCEPTED:
            counts["accepted"] += 1
        elif status == storage.REJECTED:
            counts["rejected"] += 1
        else:  # stays QUEUED
            counts["requeued"] += 1
            continue  # don't overwrite created_at ordering with an update
        to_mark.append((flag, status, resp))
    store.mark(to_mark)
    return counts


def run_loop(cfg: Config, store: Storage, once: bool = False) -> None:
    backend = protocols.make_backend(cfg.submit)
    interval = int(cfg.submit.get("interval", 10))
    proto = cfg.submit.get("protocol", "dummy")
    print(f"[submit] backend={proto}, every {interval}s, "
          f"batch={cfg.submit.get('batch_size', 100)}")
    while True:
        start = time.time()
        try:
            c = submit_round(cfg, store, backend)
            if c["sent"]:
                print(f"[submit] sent {c['sent']}: "
                      f"{c['accepted']} accepted, {c['rejected']} dead, "
                      f"{c['requeued']} requeued")
        except Exception as exc:
            print(f"[submit] round failed: {exc}", file=sys.stderr)
        if once:
            return
        time.sleep(max(0.0, interval - (time.time() - start)))
