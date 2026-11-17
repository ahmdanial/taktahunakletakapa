#!/usr/bin/env bash
# backup.sh — snapshot and restore your vulnerable services.
#
# The FIRST thing to do when a service goes live: take a pristine backup. When
# an attacker wipes or tampers with your service, restore it in seconds. Keeps
# timestamped tarballs so you can roll back to any known-good point.
#
# Usage:
#   ./defense/backup.sh save  <name> <path> [path...]   # snapshot paths
#   ./defense/backup.sh list  [name]                     # list snapshots
#   ./defense/backup.sh restore <name> [timestamp]       # restore (latest if omitted)
#
# Example:
#   ./defense/backup.sh save notes /srv/notes
#   ./defense/backup.sh restore notes
set -euo pipefail

STORE="${BACKUP_STORE:-./.backups}"
mkdir -p "$STORE"

usage() { sed -n '2,15p' "$0"; exit "${1:-0}"; }

cmd="${1:-}"; shift || true
case "$cmd" in
    save)
        name="${1:?need a name}"; shift
        [[ "$#" -ge 1 ]] || { echo "need at least one path" >&2; exit 2; }
        ts="$(date +%Y%m%d-%H%M%S)"
        out="$STORE/${name}_${ts}.tar.gz"
        tar czf "$out" "$@"
        # Keep a convenient "latest" pointer.
        ln -sf "$(basename "$out")" "$STORE/${name}_latest.tar.gz"
        echo "saved $out ($(du -h "$out" | cut -f1))"
        ;;
    list)
        name="${1:-}"
        ls -1t "$STORE"/${name:+${name}_}*.tar.gz 2>/dev/null \
            | grep -v '_latest.tar.gz$' || echo "(no snapshots)"
        ;;
    restore)
        name="${1:?need a name}"; ts="${2:-}"
        if [[ -n "$ts" ]]; then
            src="$STORE/${name}_${ts}.tar.gz"
        else
            src="$STORE/${name}_latest.tar.gz"
        fi
        [[ -e "$src" ]] || { echo "no such snapshot: $src" >&2; exit 1; }
        echo "restoring from $(readlink -f "$src")"
        # Extract to / by default because paths in the tar are absolute-safe
        # only if you saved absolute paths. Restore relative to root.
        tar xzf "$src" -C / 2>/dev/null || tar xzf "$src"
        echo "restored $name"
        ;;
    ""|-h|--help) usage 0 ;;
    *) echo "unknown command: $cmd" >&2; usage 2 ;;
esac
