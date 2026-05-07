from http.server import BaseHTTPRequestHandler
import json
from datetime import datetime, timezone

import trackhanta


class handler(BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802
        payload = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "cases": trackhanta.CASES,
            "incidents": trackhanta.INCIDENTS,
        }
        body = json.dumps(payload).encode("utf-8")

        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
        self.send_header("Pragma", "no-cache")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)
