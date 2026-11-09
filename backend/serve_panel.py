#!/usr/bin/env python3
"""Sirve el panel y hace proxy de /api hacia el backend FastAPI.

Así el navegador habla con un único origen (http://127.0.0.1:5500) y no
depende de CORS ni de que el puerto 8000 sea accesible desde el navegador.
"""

from __future__ import annotations

import http.client
import json
import sys
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

PANEL_DIR = Path(__file__).resolve().parent.parent
BACKEND_HOST = "127.0.0.1"
BACKEND_PORT = 8000

_HOP_BY_HOP = {"connection", "keep-alive", "proxy-authenticate", "proxy-authorization",
               "te", "trailers", "transfer-encoding", "upgrade"}


class PanelHandler(SimpleHTTPRequestHandler):
    server_version = "PanelDev/1.0"

    def end_headers(self) -> None:
        self.send_header("Cache-Control", "no-store, max-age=0")
        super().end_headers()

    def _is_api(self) -> bool:
        return self.path.startswith("/api/")

    def _proxy(self) -> None:
        length = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(length) if length else None

        headers = {
            key: value
            for key, value in self.headers.items()
            if key.lower() not in _HOP_BY_HOP | {"host", "content-length"}
        }

        connection = http.client.HTTPConnection(BACKEND_HOST, BACKEND_PORT, timeout=180)
        try:
            connection.request(self.command, self.path, body=body, headers=headers)
            response = connection.getresponse()
            payload = response.read()

            self.send_response(response.status, response.reason)
            for key, value in response.getheaders():
                if key.lower() not in _HOP_BY_HOP | {"content-length"}:
                    self.send_header(key, value)
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            if self.command != "HEAD":
                self.wfile.write(payload)
        except Exception as exc:  # noqa: BLE001 - queremos devolver el detalle al panel
            message = json.dumps(
                {"detail": f"No se pudo conectar con el backend 127.0.0.1:{BACKEND_PORT}: {exc}"}
            ).encode()
            self.send_response(502)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(message)))
            self.end_headers()
            self.wfile.write(message)
        finally:
            connection.close()

    def do_GET(self) -> None:  # noqa: N802 - API de BaseHTTPRequestHandler
        if self._is_api():
            self._proxy()
        else:
            super().do_GET()

    def do_HEAD(self) -> None:  # noqa: N802
        if self._is_api():
            self._proxy()
        else:
            super().do_HEAD()

    def do_POST(self) -> None:  # noqa: N802
        if self._is_api():
            self._proxy()
        else:
            self.send_error(501, "Método no soportado para archivos estáticos")

    def do_PUT(self) -> None:  # noqa: N802
        if self._is_api():
            self._proxy()
        else:
            self.send_error(501, "Método no soportado para archivos estáticos")

    def do_PATCH(self) -> None:  # noqa: N802
        if self._is_api():
            self._proxy()
        else:
            self.send_error(501, "Método no soportado para archivos estáticos")

    def do_DELETE(self) -> None:  # noqa: N802
        if self._is_api():
            self._proxy()
        else:
            self.send_error(501, "Método no soportado para archivos estáticos")

    def do_OPTIONS(self) -> None:  # noqa: N802
        if self._is_api():
            self._proxy()
        else:
            self.send_error(501, "Método no soportado para archivos estáticos")


def main() -> None:
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 5500
    handler = partial(PanelHandler, directory=str(PANEL_DIR))
    server = ThreadingHTTPServer(("127.0.0.1", port), handler)
    print(
        f"Panel en http://127.0.0.1:{port} "
        f"(/api -> http://{BACKEND_HOST}:{BACKEND_PORT})",
        flush=True,
    )
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
