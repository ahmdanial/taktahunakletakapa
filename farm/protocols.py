"""Flag-submission backends.

Every backend implements submit(flags) -> list[(flag, status, response)] where
status is one of storage.{ACCEPTED, REJECTED, QUEUED}. QUEUED means "transient
failure, try again later" (e.g. network error, rate limit); the flag stays in
the queue. The classification of gameserver responses is driven entirely by the
`responses:` substrings in config, so you adapt to a new CTF without code.
"""
from __future__ import annotations

import json
import socket
import urllib.error
import urllib.request
from typing import Callable

from . import storage

Result = tuple[str, str, str]  # (flag, status, response)


def _classifier(responses: dict) -> Callable[[str], str]:
    """Build a function mapping a gameserver response string -> farm status."""
    accepted = [s.lower() for s in responses.get("accepted", ["accepted"])]
    duplicate = [s.lower() for s in responses.get("duplicate", [])]
    nop = [s.lower() for s in responses.get("nop", [])]
    invalid = [s.lower() for s in responses.get("invalid", [])]
    error = [s.lower() for s in responses.get("error", [])]

    def classify(resp: str) -> str:
        low = (resp or "").lower()
        if any(s in low for s in accepted):
            return storage.ACCEPTED
        # permanently dead responses -> don't retry
        if any(s in low for s in duplicate + nop + invalid):
            return storage.REJECTED
        # transient -> keep for next round
        if any(s in low for s in error):
            return storage.QUEUED
        # Unknown response: be conservative, retry once more.
        return storage.QUEUED

    return classify


class DummyBackend:
    """Prints flags instead of submitting. Useful for dry runs / testing."""

    def __init__(self, submit_cfg: dict):
        self.classify = _classifier(submit_cfg.get("responses", {}))

    def submit(self, flags: list[str]) -> list[Result]:
        out: list[Result] = []
        for f in flags:
            print(f"[dummy] would submit {f}")
            out.append((f, storage.ACCEPTED, "dummy accepted"))
        return out


class HttpBackend:
    """Submit a JSON array of flags to an HTTP endpoint.

    Expects the gameserver to reply with either:
      * a JSON array of {"flag": ..., "msg"/"status": ...} objects, or
      * one plain-text line of feedback per flag (in request order).
    Both shapes are common; we handle both.
    """

    def __init__(self, submit_cfg: dict):
        self.url = submit_cfg["url"]
        self.method = submit_cfg.get("method", "PUT").upper()
        self.token = submit_cfg.get("token")
        self.header_token = submit_cfg.get("header_token")
        self.timeout = int(submit_cfg.get("http_timeout", 15))
        self.classify = _classifier(submit_cfg.get("responses", {}))

    def submit(self, flags: list[str]) -> list[Result]:
        body = json.dumps(flags).encode()
        headers = {"Content-Type": "application/json"}
        if self.header_token and self.token:
            headers[self.header_token] = str(self.token)
        req = urllib.request.Request(
            self.url, data=body, headers=headers, method=self.method
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                raw = resp.read().decode("utf-8", "replace")
        except (urllib.error.URLError, socket.timeout, OSError) as exc:
            # Transient: keep every flag queued for the next round.
            return [(f, storage.QUEUED, f"net-error: {exc}") for f in flags]
        return self._parse(flags, raw)

    def _parse(self, flags: list[str], raw: str) -> list[Result]:
        # Try JSON array of result objects first.
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            data = None
        results: list[Result] = []
        if isinstance(data, list) and data and isinstance(data[0], dict):
            by_flag = {}
            for item in data:
                fl = item.get("flag")
                msg = str(item.get("msg") or item.get("status") or item.get("response") or "")
                if fl:
                    by_flag[fl] = msg
            for f in flags:
                msg = by_flag.get(f, "no response")
                results.append((f, self.classify(msg), msg))
            return results
        # Otherwise treat as one feedback line per flag (order preserved).
        lines = [ln for ln in raw.splitlines() if ln.strip()]
        for i, f in enumerate(flags):
            msg = lines[i] if i < len(lines) else raw.strip()
            results.append((f, self.classify(msg), msg))
        return results


class TcpBackend:
    """Submit flags over a line-oriented TCP protocol (one flag per line).

    After connecting we optionally send a `hello` line (token/handshake), then
    send each flag followed by '\\n' and read one feedback line back.
    """

    def __init__(self, submit_cfg: dict):
        self.host = submit_cfg["host"]
        self.port = int(submit_cfg["port"])
        self.hello = submit_cfg.get("hello", "")
        self.timeout = int(submit_cfg.get("tcp_timeout", 15))
        self.classify = _classifier(submit_cfg.get("responses", {}))

    def submit(self, flags: list[str]) -> list[Result]:
        try:
            sock = socket.create_connection((self.host, self.port), self.timeout)
        except OSError as exc:
            return [(f, storage.QUEUED, f"net-error: {exc}") for f in flags]
        results: list[Result] = []
        try:
            sock.settimeout(self.timeout)
            reader = sock.makefile("r", encoding="utf-8", errors="replace")
            writer = sock.makefile("w", encoding="utf-8")
            if self.hello:
                writer.write(self.hello + "\n")
                writer.flush()
                # Drain any greeting / prompt lines without blocking forever.
                _drain_greeting(reader)
            for f in flags:
                writer.write(f + "\n")
                writer.flush()
                line = reader.readline()
                if not line:  # connection dropped mid-batch
                    results.append((f, storage.QUEUED, "connection closed"))
                    # Remaining flags also go back to the queue.
                    idx = flags.index(f) + 1
                    results.extend(
                        (g, storage.QUEUED, "connection closed") for g in flags[idx:]
                    )
                    break
                msg = line.strip()
                results.append((f, self.classify(msg), msg))
        finally:
            sock.close()
        return results


def _drain_greeting(reader, max_lines: int = 5) -> None:
    import select
    for _ in range(max_lines):
        r, _, _ = select.select([reader.fileno()], [], [], 0.2)
        if not r:
            return
        if not reader.readline():
            return


def make_backend(submit_cfg: dict):
    proto = (submit_cfg.get("protocol") or "dummy").lower()
    if proto == "http":
        return HttpBackend(submit_cfg)
    if proto == "tcp":
        return TcpBackend(submit_cfg)
    if proto == "dummy":
        return DummyBackend(submit_cfg)
    raise SystemExit(f"Unknown submit protocol: {proto!r} (use http/tcp/dummy)")
