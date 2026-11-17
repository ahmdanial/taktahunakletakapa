# ============================================================================
# S4DFarm server config, pre-filled for i-Hack AD CTF 2026.
#
# Overlay file — copy it over your S4DFarm clone:
#   cp s4dfarm/config.py        <S4DFarm>/server/app/config.py
#   cp s4dfarm/ihack_http.py    <S4DFarm>/server/app/protocols/ihack_http.py
# then from <S4DFarm>:  docker compose up --build -d   (web UI on :5000)
#
# Secrets are read from the environment so this file is safe to commit. Before
# starting the server, export them on the pwnbox:
#   export IHACK_TOKEN=<your-submit-token>
#   export SERVER_PASSWORD=<pick-a-dashboard-password>
# ============================================================================
import os

CONFIG = {
    # 30 teams at 10.80.N.2, minus our own (team 3) — never attack yourself.
    # NOP is not on the 1..30 grid, so it is already excluded.
    'TEAMS': {f'team{i}': f'10.80.{i}.2' for i in range(1, 31) if i != 3},

    # i-Hack flags: 31 uppercase alphanumerics + '='.
    'FLAG_FORMAT': r'[A-Z0-9]{31}=',

    # Submission: PUT http://flag.i-hack.online/flags with X-Team-Token header
    # and a JSON array body — handled by the bundled ihack_http protocol.
    'SYSTEM_PROTOCOL': 'ihack_http',
    'SYSTEM_URL': 'http://flag.i-hack.online/flags',
    'SYSTEM_TOKEN': os.getenv('IHACK_TOKEN') or 'PUT_YOUR_SUBMIT_TOKEN_HERE',

    # A flag lives 5 rounds x 120s = 600s. (S4DFarm's default is 5*60 — too
    # short for i-Hack, so we override it, or valid flags get dropped early.)
    'FLAG_LIFETIME': 5 * 120,

    # Submit at most SUBMIT_FLAG_LIMIT flags every SUBMIT_PERIOD seconds.
    'SUBMIT_FLAG_LIMIT': 100,
    'SUBMIT_PERIOD': 2,

    # Web dashboard login. Change via the SERVER_PASSWORD env var.
    'SERVER_PASSWORD': os.getenv('SERVER_PASSWORD') or 'change-me',

    'TIMEZONE': 'Asia/Singapore',
    'DEBUG': os.getenv('DEBUG') == '1',
}
