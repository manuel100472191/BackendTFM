from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread
from typing import Callable


def start_health_server(port: int, ready: Callable[[], bool]) -> ThreadingHTTPServer:
    class HealthHandler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            if self.path not in {"/health", "/ready"}:
                self.send_response(404)
                self.end_headers()
                return

            is_ready = ready()
            body = b'{"status":"ready"}' if is_ready else b'{"status":"not_ready"}'
            self.send_response(200 if is_ready else 503)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format: str, *args: object) -> None:
            return

    server = ThreadingHTTPServer(("0.0.0.0", port), HealthHandler)
    thread = Thread(target=server.serve_forever, name="health-server", daemon=True)
    thread.start()
    return server
