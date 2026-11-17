#!/usr/bin/env bash
# firewall.sh — targeted iptables helpers for defense.
#
# WARNING: never block the gameserver/checker, or your service SLA tanks and
# you lose more points than any attacker could take. This script keeps a
# whitelist of checker IPs that are always allowed.
#
# Common defensive uses:
#   * block a specific attacker IP that isn't the checker
#   * rate-limit new connections to a service to blunt exploit farms
#   * drop packets whose payload contains your flag format (crude DLP)
#
# Usage:
#   sudo CHECKERS="10.60.0.1" ./defense/firewall.sh block 10.60.2.1
#   sudo ./defense/firewall.sh unblock 10.60.2.1
#   sudo ./defense/firewall.sh ratelimit 5000 20     # 20 new conn/min/ip
#   sudo ./defense/firewall.sh dlp 5000              # drop outbound flags
#   sudo ./defense/firewall.sh list
#   sudo ./defense/firewall.sh reset                 # flush rules we added
#
# All rules go in a dedicated chain (ADCTF) so `reset` never touches other
# rules on the box.
set -euo pipefail

CHAIN="ADCTF"
CHECKERS="${CHECKERS:-}"            # space-separated IPs to always allow
FLAG_REGEX_HEX="${FLAG_REGEX_HEX:-}"  # optional; see dlp note below

need_root() { [[ "$(id -u)" -eq 0 ]] || { echo "run as root" >&2; exit 1; }; }
need_root
command -v iptables >/dev/null || { echo "iptables not found" >&2; exit 1; }

ensure_chain() {
    iptables -nL "$CHAIN" >/dev/null 2>&1 || iptables -N "$CHAIN"
    # Hook our chain into INPUT once.
    iptables -C INPUT -j "$CHAIN" 2>/dev/null || iptables -I INPUT 1 -j "$CHAIN"
    # Always-allow checkers at the top of our chain.
    for c in $CHECKERS; do
        iptables -C "$CHAIN" -s "$c" -j RETURN 2>/dev/null \
            || iptables -I "$CHAIN" 1 -s "$c" -j RETURN
    done
}

cmd="${1:-}"; shift || true
case "$cmd" in
    block)
        ip="${1:?need ip}"; ensure_chain
        for c in $CHECKERS; do
            [[ "$ip" == "$c" ]] && { echo "refusing to block checker $ip" >&2; exit 1; }
        done
        iptables -A "$CHAIN" -s "$ip" -j DROP
        echo "blocked $ip"
        ;;
    unblock)
        ip="${1:?need ip}"
        iptables -D "$CHAIN" -s "$ip" -j DROP 2>/dev/null && echo "unblocked $ip" \
            || echo "no such rule"
        ;;
    ratelimit)
        port="${1:?need port}"; rate="${2:-30}"; ensure_chain
        # Allow checkers (already RETURN'd above), then rate-limit the rest.
        iptables -A "$CHAIN" -p tcp --dport "$port" --syn \
            -m hashlimit --hashlimit-name "svc$port" \
            --hashlimit-above "${rate}/min" --hashlimit-mode srcip \
            -j DROP
        echo "rate-limited new connections to :$port at ${rate}/min/ip"
        ;;
    dlp)
        port="${1:?need port}"; ensure_chain
        # Crude outbound flag filter using the string match module. This blocks
        # packets whose ASCII payload contains an '=' preceded by the flag body;
        # tune the --string to a fixed, known substring of your flag if possible.
        # NOTE: regex isn't supported by the string module — use an exact token.
        token="${DLP_TOKEN:-}"
        if [[ -z "$token" ]]; then
            echo "set DLP_TOKEN to a fixed substring present in every flag" >&2
            echo "(the kernel string match can't do regex)" >&2
            exit 2
        fi
        iptables -I OUTPUT -p tcp --sport "$port" \
            -m string --string "$token" --algo bm -j DROP
        echo "dropping outbound :$port packets containing '$token'"
        ;;
    list)
        echo "== $CHAIN =="; iptables -nL "$CHAIN" --line-numbers 2>/dev/null || echo "(none)"
        echo "== OUTPUT (dlp) =="; iptables -nL OUTPUT --line-numbers | grep -i string || true
        ;;
    reset)
        iptables -D INPUT -j "$CHAIN" 2>/dev/null || true
        iptables -F "$CHAIN" 2>/dev/null || true
        iptables -X "$CHAIN" 2>/dev/null || true
        # Remove any dlp rules we added to OUTPUT.
        while iptables -D OUTPUT -m string 2>/dev/null; do :; done || true
        echo "flushed $CHAIN"
        ;;
    *) sed -n '2,20p' "$0"; exit 2 ;;
esac
