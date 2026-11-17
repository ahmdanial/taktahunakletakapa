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
