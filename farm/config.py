"""Configuration loading for the farm.

Loads YAML if PyYAML is installed, otherwise falls back to JSON. Any scalar
setting can be overridden from the environment with a FARM_ prefix, e.g.
FARM_RUN_EVERY=10 or FARM_SUBMIT__URL=http://... (double underscore descends
into nested keys).
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Any

try:
    import yaml  # type: ignore
    _HAVE_YAML = True
except ImportError:  # pragma: no cover - yaml is optional
    _HAVE_YAML = False


def _load_raw(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as fh:
        text = fh.read()
    if _HAVE_YAML:
        return yaml.safe_load(text) or {}
    # Best-effort JSON fallback so the farm still runs without PyYAML.
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise SystemExit(
            f"Cannot parse {path}: PyYAML is not installed and the file is not "
            f"valid JSON ({exc}). Install pyyaml or provide JSON config."
        )


def _apply_env_overrides(cfg: dict, prefix: str = "FARM_") -> None:
    """FARM_SUBMIT__INTERVAL=5 -> cfg['submit']['interval'] = 5 (typed)."""
    for key, val in os.environ.items():
        if not key.startswith(prefix):
            continue
        path = key[len(prefix):].lower().split("__")
        node = cfg
        for part in path[:-1]:
            node = node.setdefault(part, {})
            if not isinstance(node, dict):
                break
        else:
            node[path[-1]] = _coerce(val)


def _coerce(val: str) -> Any:
    low = val.lower()
    if low in ("true", "false"):
        return low == "true"
    try:
        return int(val)
    except ValueError:
        pass
    try:
        return float(val)
    except ValueError:
        return val


def expand_teams(block: dict) -> list[str]:
    """Build the final target list from explicit entries and/or a template."""
    teams: list[str] = []
    teams.extend(block.get("explicit") or [])
    template = block.get("ip_template")
    rng = block.get("range") or []
    if template:
        for i in rng:
            teams.append(template.replace("{}", str(i)))
    skip = set(block.get("skip") or [])
    # De-duplicate while preserving order, drop skipped hosts.
    seen: set[str] = set()
    out: list[str] = []
    for t in teams:
        if t in skip or t in seen:
            continue
        seen.add(t)
        out.append(t)
    return out


@dataclass
class Config:
    teams: list[str]
    flag_regex: str
    flag_lifetime: int
    exploits_dir: str
    run_every: int
    exploit_timeout: int
    max_parallel: int
    submit: dict
    db_path: str
    raw: dict = field(repr=False, default_factory=dict)

    @classmethod
    def load(cls, path: str) -> "Config":
        raw = _load_raw(path)
        _apply_env_overrides(raw)
        return cls(
            teams=expand_teams(raw.get("teams") or {}),
            flag_regex=raw.get("flag_regex", r"[A-Z0-9]{31}="),
            flag_lifetime=int(raw.get("flag_lifetime", 300)),
            exploits_dir=raw.get("exploits_dir", "exploits"),
            run_every=int(raw.get("run_every", 30)),
            exploit_timeout=int(raw.get("exploit_timeout", 25)),
            max_parallel=int(raw.get("max_parallel", 16)),
            submit=raw.get("submit") or {},
            db_path=raw.get("db_path", "farm.db"),
            raw=raw,
        )
