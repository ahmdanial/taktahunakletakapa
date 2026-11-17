#!/usr/bin/env python3
"""A mock flag-submission server (HTTP), for testing the submitter.

Accepts PUT/POST of a JSON array of flags, returns a JSON array of
{"flag":..., "msg":...}. Remembers flags so resubmits come back as duplicates.

Run:  python3 test/mock_gameserver.py 8080
Point config submit.url at http://127.0.0.1:8080/flags
"""
import json
import re
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer

FLAG_RE = re.compile(r"[A-Z0-9]{31}=")
SEEN: set[str] = set()


class Handler(BaseHTTPRequestHandler):
    def _handle(self):
        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length).decode("utf-8", "replace")
        try:
            flags = json.loads(raw)
            assert isinstance(flags, list)
        except Exception:
            self.send_response(400)
            self.end_headers()
            self.wfile.write(b'[]')
            return
        out = []
        for f in flags:
            if not FLAG_RE.fullmatch(str(f)):
                msg = "invalid: bad format"
            elif f in SEEN:
                msg = "duplicate: already submitted"
            else:
                SEEN.add(f)
                msg = "accepted"
            out.append({"flag": f, "msg": msg})
        body = json.dumps(out).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    do_PUT = _handle
    do_POST = _handle

    def log_message(self, *a):
        pass


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8080
    print(f"mock gameserver on :{port} (PUT/POST /flags)")
    HTTPServer(("0.0.0.0", port), Handler).serve_forever()
