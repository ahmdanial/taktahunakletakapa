#!/usr/bin/env python3
"""A mock 'vulnerable' service that just serves flags, for testing the farm.

Run:  python3 test/mock_service.py 5000
Then an exploit that GETs http://127.0.0.1:5000/ will scrape the flags.
"""
import random
import string
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer


def gen_flag() -> str:
    return "".join(random.choices(string.ascii_uppercase + string.digits, k=31)) + "="


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802
        flags = "\n".join(gen_flag() for _ in range(random.randint(1, 3)))
        body = f"<html><body>notes:\n{flags}\n</body></html>".encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a):  # quiet
        pass


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 5000
    print(f"mock service on :{port}")
    HTTPServer(("0.0.0.0", port), Handler).serve_forever()
