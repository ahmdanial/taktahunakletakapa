#!/usr/bin/env bash
# leakwatch.sh — tail live traffic and alert the instant a flag leaves your box.
#
# Runs tcpdump in ASCII mode and greps every packet for the flag format. When a
# flag appears in OUTBOUND traffic on a service port, someone is exfiltrating
# it right now — the surrounding packets show you exactly how. Pair with
# capture.sh (which keeps the full pcap) for after-the-fact analysis.
#
# Usage:
#   sudo ./defense/leakwatch.sh 5000
#   sudo FLAG_REGEX='[A-Z0-9]{31}=' ./defense/leakwatch.sh 5000 8080
set -euo pipefail

if [[ "$#" -lt 1 ]]; then
    sed -n '2,12p' "$0"; exit 2
fi

FLAG_REGEX="${FLAG_REGEX:-[A-Z0-9]{31}=}"
IFACE="${IFACE:-any}"

command -v tcpdump >/dev/null || { echo "need tcpdump" >&2; exit 1; }

filter="tcp and ("
first=1
for p in "$@"; do
    if [[ $first -eq 1 ]]; then filter+="port $p"; first=0
    else filter+=" or port $p"; fi
done
filter+=")"

echo "watching [$filter] for /$FLAG_REGEX/ — Ctrl-C to stop" >&2

# -l line-buffered, -A ascii. We print a red-ish marker line per hit with a
# timestamp so you can correlate against the live scoreboard.
stdbuf -oL tcpdump -i "$IFACE" -n -A -s 0 -l "$filter" 2>/dev/null \
    | grep --line-buffered -Eo "$FLAG_REGEX" \
    | while read -r flag; do
        printf '[%s] FLAG SEEN ON WIRE: %s\n' "$(date +%H:%M:%S)" "$flag"
    done
