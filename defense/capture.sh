#!/usr/bin/env bash
# capture.sh — record traffic to your services so you can reverse-engineer the
# exploits being used against you and replay them against everyone else.
#
# This is the single highest-value defensive move in A/D: the moment someone
# pops your service, their exploit traffic is in your pcap. Read the flag out
# of a response, find the request that triggered it, and you have a sploit.
#
# Usage:
#   sudo ./defense/capture.sh 5000                 # capture port 5000
#   sudo ./defense/capture.sh 5000 8080            # multiple ports
#   ROTATE=300 sudo ./defense/capture.sh 5000      # rotate files every 5 min
#   OUTDIR=/data/pcaps sudo ./defense/capture.sh 5000
#
# Needs tcpdump + root. Files land in $OUTDIR as svc_<ts>_NN.pcap.
set -euo pipefail

if [[ "$#" -lt 1 ]]; then
    sed -n '2,15p' "$0"; exit 2
fi

OUTDIR="${OUTDIR:-./pcaps}"
ROTATE="${ROTATE:-600}"        # seconds per file
IFACE="${IFACE:-any}"
mkdir -p "$OUTDIR"

if ! command -v tcpdump >/dev/null; then
    echo "tcpdump not found. Install it (apt-get install -y tcpdump)." >&2
    exit 1
fi

# Build a BPF filter: tcp and (port A or port B ...)
filter="tcp and ("
first=1
for p in "$@"; do
    [[ "$p" =~ ^[0-9]+$ ]] || { echo "bad port: $p" >&2; exit 2; }
    if [[ $first -eq 1 ]]; then filter+="port $p"; first=0
    else filter+=" or port $p"; fi
done
filter+=")"

ts="$(date +%Y%m%d-%H%M%S)"
echo "capturing [$filter] on $IFACE -> $OUTDIR/svc_${ts}_NN.pcap (rotate ${ROTATE}s)"
echo "Ctrl-C to stop. Inspect later with:  tcpdump -A -r <file>"

exec tcpdump -i "$IFACE" -n -s 0 -G "$ROTATE" \
    -w "$OUTDIR/svc_${ts}_%02d.pcap" "$filter"
