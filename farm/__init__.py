"""Lightweight Attack/Defense CTF exploit farm.

Modules:
    config     - load/normalise YAML (or JSON) configuration
    storage    - sqlite-backed flag queue with dedup and status tracking
    protocols  - pluggable flag-submission backends (http / tcp / dummy)
    runner     - the attack loop: run every exploit against every target
    submitter  - the submit loop: batch flags to the gameserver
    cli        - command-line entrypoint
"""

__version__ = "1.0.0"
