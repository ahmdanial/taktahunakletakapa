# S4DFarm overlay for i-Hack AD CTF 2026

Ready-to-paste config + submit protocol for running
[S4DFarm](https://github.com/C4T-BuT-S4D/S4DFarm) at this event, instead of (or
alongside) the farm in this repo. S4DFarm gives you a web dashboard and lets
several teammates run exploit clients against one shared server.

Two files:

| File | Copy it to |
|---|---|
| `config.py` | `<S4DFarm>/server/app/config.py` |
| `ihack_http.py` | `<S4DFarm>/server/app/protocols/ihack_http.py` |

## Apply

```bash
git clone https://github.com/C4T-BuT-S4D/S4DFarm
cp s4dfarm/config.py       S4DFarm/server/app/config.py
cp s4dfarm/ihack_http.py   S4DFarm/server/app/protocols/ihack_http.py

cd S4DFarm
export IHACK_TOKEN=<your-submit-token>      # your submit token (not in git)
export SERVER_PASSWORD=pick-a-password   # web dashboard login
docker compose up --build -d             # dashboard on http://localhost:5000
```

The config already has: 29 targets (`10.80.1.2`–`10.80.30.2` minus your team 3),
flag format `[A-Z0-9]{31}=`, the i-Hack submit URL + `X-Team-Token` header, and
`FLAG_LIFETIME = 600s` (S4DFarm's default is too short for i-Hack).

## Run exploits

Same exploit contract as this repo — executable, team host as `argv[1]`, prints
flags to stdout, has a shebang. Your `exploits/ihack_template.py` copies work
unchanged. From the pwnbox, one client per service:

```bash
cd S4DFarm/client
./start_sploit.py --server-url http://localhost:5000 --server-pass "$SERVER_PASSWORD" \
    --attack-period 120 --pool-size 30 -e /path/to/exploits/carsim.py
```

- `--attack-period 120` → one wave per 120s round
- `--pool-size 30` → hit all 29 teams at once
- `-e` → endless

## After the first real submission (11:00)

Open the dashboard, find a submitted flag, and read the gameserver's exact reply
text. If any outcome landed in the wrong column, edit the `RESPONSES` lists at
the top of `ihack_http.py` to match the real words, then
`docker compose restart`. The protocol already covers accepted / your-own /
too-old / malformed / already-paid / NOP, and handles both JSON and plain-text
replies — this is just fine-tuning.

> The real submit token lives only in the `IHACK_TOKEN` env var, never in these
> committed files.
