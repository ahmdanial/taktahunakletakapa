# taktahunakletakapa — Attack/Defense CTF toolkit

Automation for Attack/Defense (A/D) CTFs: run your exploits against every
opposing team on a loop, harvest flags, and submit them to the gameserver
automatically — while scripts on the defensive side help you back up services,
capture attacker traffic, and spot flags leaking off your box.

> A/D CTF: every team runs the same set of vulnerable services. You score by
> stealing flags from other teams' services (**attack**) and by keeping your
> own services patched and up (**defense/SLA**). Everything here assumes you
> are a participant in such an event and operating only against the event's
> own scoreboard and teams.

```
farm/        the exploit farm (attack loop + flag submitter)   — Python, stdlib
exploits/    your exploit scripts (templates included)
attack/      recon + manual flag scraping helpers
defense/     backup/restore, traffic capture, leak watch, firewall
config/      config.sample.yaml  (copy to config.yaml)
test/        local mocks + end-to-end self-test (make demo)
```

## Quickstart

```bash
make setup                 # installs pyyaml, copies config sample, chmods scripts
$EDITOR config/config.yaml # set team IPs, flag regex, submit protocol + token
make demo                  # optional: prove the pipeline works against local mocks
make run                   # start the full farm (attack + submit together)
```

`make demo` needs no CTF — it spins up a mock vulnerable service and mock
gameserver on localhost and runs a flag through the entire pipeline.

## Step-by-step walkthrough

Follow these in order the first time. Run everything from the repo root
(`taktahunakletakapa/`).

### Step 1 — Install and create your config

```bash
make setup
```

This installs PyYAML, copies `config/config.sample.yaml` to
`config/config.yaml` (only if it doesn't already exist), and marks all the
scripts executable. If you don't have `make`, do it by hand:

```bash
pip install -r requirements.txt
cp config/config.sample.yaml config/config.yaml
chmod +x exploits/* attack/*.sh attack/*.py defense/*.sh
```

### Step 2 — Prove it works (sanity check)

Before touching real settings, confirm the machinery runs:

```bash
make demo
```

Expect it to end with `DEMO PASS: 1 flag(s) accepted end-to-end`. If that
works, any later problem is in your config or exploit, not the farm.

### Step 3 — Edit the config for your event

Open `config/config.yaml` and set:

- **`teams`** — the IPs you attack. Either list them under `explicit:`, or use
  `ip_template: "10.60.{}.1"` + `range: [1,2,3,...]` to generate them.
- **`teams.skip`** — your own team IP and the gameserver/checker IP. Never
  attack these.
- **`flag_regex`** — the flag format for your CTF (the default matches 31
  chars + `=`). The organizers always publish this.
- **`submit`** — how flags are submitted:
  - `protocol: http` → set `url`, `method`, and usually `header_token` + `token`.
  - `protocol: tcp` → set `host`, `port`, and `hello` if a token line is needed.
  - `responses:` → the words the gameserver uses for accepted/duplicate/invalid.

Check what the farm parsed:

```bash
python3 -m farm teams        # prints your final target list + loaded exploits
```

### Step 4 — Write (or drop in) an exploit

An exploit is any executable file in `exploits/`. Copy a template and edit it:

```bash
cp exploits/example_sploit.py exploits/notes_sploit.py
$EDITOR exploits/notes_sploit.py     # set SERVICE_PORT + the actual attack
chmod +x exploits/notes_sploit.py
```

Rules your exploit must follow:
- It's called as `./exploits/notes_sploit.py <TARGET_IP>`.
- It prints any flags it finds to stdout (the farm scrapes them with
  `flag_regex`).
- It finishes quickly (well under `exploit_timeout` seconds).

Test it by hand against one target before trusting the farm with it:

```bash
./exploits/notes_sploit.py 10.60.2.1
```

To temporarily disable a broken exploit without deleting it, rename it to end
in `.disabled`.

### Step 5 — Do a single dry round

```bash
python3 -m farm once         # one attack round + one submit round, then exits
python3 -m farm stats        # how many flags were queued / accepted / rejected
```

Tip: set `submit.protocol: dummy` in the config first if you want to see which
flags *would* be submitted without actually sending them.

### Step 6 — Run the farm for the whole game

```bash
make run                     # = python3 -m farm run  (attack loop + submit loop)
```

Leave it running. It attacks every `run_every` seconds and submits every
`submit.interval` seconds. Watch another terminal with:

```bash
watch -n5 python3 -m farm stats
```

Stop it with `Ctrl-C`; the queue is saved in `farm.db`, so restarting never
loses or re-submits flags.

### Step 7 (optional) — Recon and manual flags

```bash
./attack/recon.sh                                   # open ports per team
curl -s http://10.60.2.1:5000/dump | ./attack/flagscan.py --enqueue --target 10.60.2.1
```

`flagscan.py --enqueue` pushes hand-collected flags into the same queue, so the
running farm submits them for you.

### Step 8 (optional) — Defense

On the box running your own services:

```bash
./defense/backup.sh save notes /srv/notes      # snapshot now; restore after a wipe
sudo ./defense/capture.sh 5000                 # record attacker traffic to a pcap
sudo ./defense/leakwatch.sh 5000               # alert when a flag leaves the wire
sudo CHECKERS="10.60.0.1" ./defense/firewall.sh block 10.60.2.1
```

See the **Defense helpers** section below for what each one is for.

## How the farm works

```
 exploits/*  ──run against──▶  every target team
      │                              │
      │   stdout scraped with flag_regex
      ▼                              ▼
  sqlite queue (farm.db)  ◀── de-duped, timestamped
      │
      │   submit loop, every submit.interval
      ▼
  gameserver (http | tcp)  ──▶ ACCEPTED / REJECTED / retry
```

- **An exploit** is any executable in `exploits/`. The farm runs it as
  `./exploit <TARGET_IP>` (also exporting `TARGET`, `HOST`, `FLAG_REGEX`) and
  scrapes anything matching `flag_regex` from its output. Language doesn't
  matter — see `exploits/example_sploit.py` and `.sh`. Park a broken one by
  renaming it to `*.disabled`.
- **The queue** (`farm.db`, SQLite/WAL) de-dupes flags and tracks status, so
  restarting the farm never loses or double-submits flags.
- **The submitter** batches queued flags to the gameserver. Transient failures
  (network errors, rate limits) keep flags queued; permanent responses
  (duplicate/own/invalid/expired) retire them. Response classification is
  config-driven (`submit.responses`) so you adapt to any gameserver's wording
  without touching code.

### Commands

```bash
python3 -m farm run      # attack + submit (what you run during the game)
python3 -m farm attack   # attack loop only (e.g. on a separate box)
python3 -m farm submit   # submit loop only
python3 -m farm once     # single round of each, then exit (great for testing)
python3 -m farm stats    # queue counts
python3 -m farm teams    # print expanded target list + loaded exploits
```

Every scalar in the config can be overridden by env var, e.g.
`FARM_SUBMIT__TOKEN=... FARM_RUN_EVERY=10 python3 -m farm run`.

### Submission protocols

Set `submit.protocol` in config:

- **`http`** — PUTs/POSTs a JSON array of flags; handles both a JSON array of
  `{flag,msg}` results and one-feedback-line-per-flag responses.
- **`tcp`** — line protocol: optional `hello` handshake, then one flag per
  line, reads one feedback line back.
- **`dummy`** — prints instead of submitting (dry runs).

If your event uses a different scheme, add a backend in `farm/protocols.py` —
each just implements `submit(flags) -> [(flag, status, response)]`.

## Attack helpers

```bash
./attack/recon.sh                         # open/closed service matrix per team
PORTS="22 80 5000" ./attack/recon.sh      # custom ports
curl -s http://10.60.2.1:5000/dump | ./attack/flagscan.py --enqueue --target 10.60.2.1
```

`flagscan.py` scrapes flags from any text and can push them straight into the
farm queue, so hand-run exploitation still rides the farm's submission.

## Defense helpers

```bash
# 1. Snapshot services the moment they're up; restore after an attacker wipes them.
./defense/backup.sh save notes /srv/notes
./defense/backup.sh restore notes

# 2. Record traffic to your services — attacker exploits land in your pcap.
sudo ./defense/capture.sh 5000 8080
#    ...then read the exploit back out and reuse it:
tcpdump -A -r pcaps/svc_*.pcap

# 3. Alert the instant a flag leaves your box.
sudo ./defense/leakwatch.sh 5000

# 4. Targeted firewalling (never blocks the checker).
sudo CHECKERS="10.60.0.1" ./defense/firewall.sh block 10.60.2.1
sudo ./defense/firewall.sh ratelimit 5000 20
sudo ./defense/firewall.sh reset
```

**Capturing attacker traffic is the highest-value defensive move**: once a rival
pops your service, their exploit is sitting in your pcap — read the flag out of
the response, find the request that caused it, and you've got a new sploit to
run against everyone.

## Notes & safety

- `config/config.yaml`, `farm.db`, and `pcaps/` are git-ignored — they hold
  your team token, live flags, and captured traffic. Don't commit them.
- Always list the gameserver/checker in `teams.skip` and in `CHECKERS` for the
  firewall. Blocking the checker tanks your SLA and costs more than any attacker.
- Use this only as a participant against your own CTF's scoreboard and teams.
```
