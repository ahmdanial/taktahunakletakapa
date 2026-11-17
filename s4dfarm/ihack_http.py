"""S4DFarm submit protocol for i-Hack AD CTF 2026.

Drop this in  <S4DFarm>/server/app/protocols/ihack_http.py  and set
SYSTEM_PROTOCOL = 'ihack_http' in config.py.

Submits like the briefing's example:
    PUT http://flag.i-hack.online/flags
    X-Team-Token: <token>
    Content-Type: application/json
    ["FLAG1=", "FLAG2=", ...]

The i-Hack gameserver "names" each outcome in the reply (accepted / your own /
too old / malformed / already paid / NOP). We don't know whether it answers
with a JSON array or plain text, so this handles BOTH: a JSON array of
{"flag":..., "msg":...} objects, or one feedback line per flag in request
order. Each reply is classified by substring (RESPONSES below).

After your FIRST real submission at 11:00, look at the exact words in the
dashboard's response column and adjust RESPONSES if anything lands in the wrong
bucket. A reply that matches nothing is kept QUEUED and retried.
"""
import logging

import requests

from models import FlagStatus, SubmitResult

logger = logging.getLogger(__name__)

TIMEOUT = 5

# Order matters: REJECTED is checked before ACCEPTED so a message like
# "invalid flag" can never match a stray "valid"/"ok" substring. Keep ACCEPTED
# tokens specific for the same reason.
RESPONSES = [
    (FlagStatus.REJECTED, [
        'your own', 'own flag', 'too old', 'expired', 'old',
        'already', 'paid', 'duplicate', 'nop', 'not active',
        'invalid', 'malformed', 'bad', 'wrong', 'no such',
        'not in database', 'unknown flag',
    ]),
    (FlagStatus.ACCEPTED, [
        'accepted', 'congrat', 'success',
    ]),
    (FlagStatus.QUEUED, [
        'timeout', 'try again', 'game not started', 'not started',
        'game over', 'is not up', 'rate', 'too many', 'limit',
    ]),
]


def _classify(message):
    low = (message or '').lower()
    for status, needles in RESPONSES:
        if any(n in low for n in needles):
            return status
    return FlagStatus.QUEUED  # unknown reply -> keep and retry next round


def submit_flags(flags, config):
    flag_strs = [item.flag for item in flags]
    try:
        r = requests.put(
            config['SYSTEM_URL'],
            headers={'X-Team-Token': config['SYSTEM_TOKEN']},
            json=flag_strs,
            timeout=TIMEOUT,
        )
    except requests.exceptions.RequestException as exc:
        logger.error('i-Hack submit request failed: %s', exc)
        for flag in flag_strs:
            yield SubmitResult(flag, FlagStatus.QUEUED, f'request error: {exc}')
        return

    # Shape 1: JSON array of {"flag": ..., "msg"/"status": ...}
    try:
        data = r.json()
    except ValueError:
        data = None

    if isinstance(data, list) and data and isinstance(data[0], dict):
        for item in data:
            flag = item.get('flag')
            if flag is None:
                continue
            msg = str(item.get('msg') or item.get('status')
                      or item.get('response') or item.get('result') or '')
            yield SubmitResult(flag, _classify(msg), msg)
        return

    # Shape 2: one feedback line per flag, in request order.
    lines = [ln for ln in r.text.splitlines() if ln.strip()]
    for i, flag in enumerate(flag_strs):
        msg = lines[i] if i < len(lines) else r.text.strip()
        yield SubmitResult(flag, _classify(msg), msg)
