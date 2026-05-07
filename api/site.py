from http.server import BaseHTTPRequestHandler

import trackhanta


class handler(BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802
        html = trackhanta._build_html()
        html = html.replace("/assets/trackhanta-logo-white.png", "/api/logo")
        html = html.replace("/favicon-dark.png?v=1", "/api/favicon_png?v=1")
        html = html.replace("/favicon-dark.ico?v=1", "/api/favicon_ico?v=1")
        body = html.encode("utf-8")

        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
        self.send_header("Pragma", "no-cache")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)
