from http.server import BaseHTTPRequestHandler

import trackhanta


class handler(BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802
        if not trackhanta.FAVICON_DARK_PATH.is_file():
            body = b"Favicon ICO not found"
            self.send_response(404)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        body = trackhanta.FAVICON_DARK_PATH.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", "image/x-icon")
        self.send_header("Cache-Control", "public, max-age=3600")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)
