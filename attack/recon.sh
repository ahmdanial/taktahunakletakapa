#!/usr/bin/env bash
# recon.sh — quick service enumeration across all target teams.
#
# Reads the target list from the farm ("python -m farm teams") or from a file,
# then probes a set of ports on each. Prints an open/closed matrix so you can
# see which services are up on which team at a glance.
#
# Usage:
#   ./attack/recon.sh                       # targets from farm config
#   ./attack/recon.sh -f hosts.txt          # targets from a file (one ip/line)
#   PORTS="22 80 5000 8080" ./attack/recon.sh
#
# Pure bash + /dev/tcp, so it needs no nmap. For deep scans use nmap directly.
set -uo pipefail

PORTS="${PORTS:-22 80 443 5000 8080 1337 31337 3000 9000}"
TIMEOUT="${TIMEOUT:-1}"
CONFIG="${CONFIG:-config/config.yaml}"
HOSTS_FILE=""

while getopts "f:c:p:h" opt; do
    case "$opt" in
        f) HOSTS_FILE="$OPTARG" ;;
        c) CONFIG="$OPTARG" ;;
        p) PORTS="$OPTARG" ;;
        h) sed -n '2,13p' "$0"; exit 0 ;;
        *) exit 2 ;;
    esac
done

get_targets() {
    if [[ -n "$HOSTS_FILE" ]]; then
        grep -vE '^\s*(#|$)' "$HOSTS_FILE"
    else
        python3 -m farm teams -c "$CONFIG" 2>/dev/null | grep -vE '^\s*#'
    fi
}

probe() {  # host port -> echoes "open"/"-"
    local host="$1" port="$2"
    if timeout "$TIMEOUT" bash -c "exec 3<>/dev/tcp/${host}/${port}" 2>/dev/null; then
        printf 'open'
    else
        printf '  - '
    fi
}

mapfile -t TARGETS < <(get_targets)
if [[ "${#TARGETS[@]}" -eq 0 ]]; then
    echo "no targets (check $CONFIG or -f file)" >&2
    exit 1
fi

# Header
printf '%-18s' "HOST"
for p in $PORTS; do printf '%6s' "$p"; done
echo

for host in "${TARGETS[@]}"; do
    printf '%-18s' "$host"
    for p in $PORTS; do
        printf '%6s' "$(probe "$host" "$p")"
    done
    echo
done
