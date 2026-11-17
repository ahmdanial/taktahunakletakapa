#!/usr/bin/env bash
# demo.sh — end-to-end self-test with no real CTF.
#
# Spins up a mock vulnerable service and a mock gameserver on localhost, points
# a throwaway config at them, runs one attack+submit round, and checks that
# flags were scraped, queued, submitted and accepted. Exercises the whole farm.
set -uo pipefail
cd "$(dirname "$0")/.."

SVC_PORT=15000
GS_PORT=18080
TMPCFG="$(mktemp /tmp/farm-demo-XXXX.yaml)"
DB="$(mktemp /tmp/farm-demo-XXXX.db)"
pids=()

cleanup() {
    for p in "${pids[@]:-}"; do kill "$p" 2>/dev/null || true; done
    rm -f "$TMPCFG" "$DB" "$DB-wal" "$DB-shm"
}
trap cleanup EXIT

echo "== starting mocks =="
python3 test/mock_service.py "$SVC_PORT" & pids+=($!)
python3 test/mock_gameserver.py "$GS_PORT" & pids+=($!)
sleep 1

cat > "$TMPCFG" <<EOF
teams:
  explicit: ["127.0.0.1"]
flag_regex: "[A-Z0-9]{31}="
flag_lifetime: 300
exploits_dir: "exploits"
run_every: 5
exploit_timeout: 10
max_parallel: 4
submit:
  protocol: "http"
  interval: 5
  batch_size: 100
  url: "http://127.0.0.1:${GS_PORT}/flags"
  method: "PUT"
  responses:
    accepted: ["accepted"]
    duplicate: ["duplicate", "already"]
    invalid: ["invalid"]
db_path: "${DB}"
EOF

# Point the example exploit at the mock service port via env (it reads argv[1]
# for host; the port is hardcoded to 5000, so use a tiny inline exploit here).
INLINE_EXPLOIT="$(mktemp /tmp/farm-demo-sploit-XXXX.py)"
cat > "$INLINE_EXPLOIT" <<EOF
#!/usr/bin/env python3
import os,re,sys,urllib.request
host=sys.argv[1]
r=re.compile(os.environ.get("FLAG_REGEX","[A-Z0-9]{31}="))
with urllib.request.urlopen(f"http://{host}:${SVC_PORT}/",timeout=5) as resp:
    print("\n".join(r.findall(resp.read().decode())))
EOF
chmod +x "$INLINE_EXPLOIT"
# Temporarily place it in exploits/ under a demo name.
DEMO_SPLOIT="exploits/_demo_sploit.py"
cp "$INLINE_EXPLOIT" "$DEMO_SPLOIT"; chmod +x "$DEMO_SPLOIT"
trap 'rm -f "$DEMO_SPLOIT" "$INLINE_EXPLOIT"; cleanup' EXIT

echo "== teams =="
python3 -m farm teams -c "$TMPCFG"

echo "== one attack round =="
python3 -m farm attack -c "$TMPCFG" &
APID=$!; pids+=($APID)
sleep 3; kill $APID 2>/dev/null || true

echo "== stats after attack =="
python3 -m farm stats -c "$TMPCFG"

echo "== one submit round =="
python3 -m farm submit -c "$TMPCFG" &
SPID=$!; pids+=($SPID)
sleep 3; kill $SPID 2>/dev/null || true

echo "== final stats =="
OUT="$(python3 -m farm stats -c "$TMPCFG")"
echo "$OUT"

ACCEPTED="$(echo "$OUT" | awk '/ACCEPTED/{print $2}')"
if [[ "${ACCEPTED:-0}" -ge 1 ]]; then
    echo "DEMO PASS: $ACCEPTED flag(s) accepted end-to-end"
    exit 0
else
    echo "DEMO FAIL: no flags accepted" >&2
    exit 1
fi
