"""Loopback-only, read-only HTTP interface. No third-party assets or services."""
from __future__ import annotations

from http.server import BaseHTTPRequestHandler, HTTPServer
import json
from pathlib import Path
import mimetypes
from urllib.parse import parse_qs, urlsplit, unquote

from .index import Explorer, MODULE


WEB = Path(__file__).resolve().parent / "web"
DOCS = MODULE / "reversing/docs"


def serve(database: Path, port: int, open_browser: bool = False) -> None:
    explorer = Explorer(database)

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format: str, *args: object) -> None:
            if args and str(args[1:2]) not in {"('200',)", "('304',)"}:
                super().log_message(format, *args)

        def send(self, payload: bytes, mime: str = "application/json; charset=utf-8", status: int = 200) -> None:
            self.send_response(status)
            self.send_header("Content-Type", mime)
            self.send_header("Content-Length", str(len(payload)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; frame-ancestors 'none'; object-src 'none'")
            self.end_headers()
            self.wfile.write(payload)

        def do_GET(self) -> None:
            if self.headers.get("Host", "").split(":")[0] not in {"127.0.0.1", "localhost"}:
                self.send(b'{"error":"loopback Host required"}', status=403)
                return
            request = urlsplit(self.path)
            values = parse_qs(request.query)

            def text(key: str, default: str = "") -> str:
                return values.get(key, [default])[0]

            def number(key: str, default: int, minimum: int = 0, maximum: int = 1000000000) -> int:
                return min(maximum, max(minimum, int(text(key, str(default)))))

            options = {"view": text("view", "member"), "cross": text("cross") == "1", "language": text("language", "auto")}
            try:
                path = request.path
                if path == "/api/summary":
                    result = explorer.summary()
                    result["levels"] = [dict(row) for row in explorer.db.execute("SELECT level,COUNT(*) AS count FROM files GROUP BY level ORDER BY level")]
                    result["formats"] = [dict(row) for row in explorer.db.execute("SELECT format,COUNT(*) AS count FROM files GROUP BY format ORDER BY format")]
                    result["statuses"] = [dict(row) for row in explorer.db.execute("SELECT status,COUNT(*) AS count FROM files GROUP BY status ORDER BY COUNT(*) DESC LIMIT 50")]
                elif path == "/api/files":
                    result = explorer.search(text("level"), text("q"), text("view", "member"), text("format"),
                                             number("offset", 0), number("limit", 80, 1, 200), text("shared") == "1")
                elif path == "/api/file":
                    file_id = number("id", 0)
                    result = explorer.identifiers(file_id, number("offset", 0), number("limit", 60, 1, 200), **options)
                    result["provenance"] = [dict(row) for row in explorer.db.execute("SELECT * FROM edges WHERE source=? OR target=? LIMIT 200", (file_id, file_id))]
                elif path == "/api/graph":
                    result = explorer.graph(number("id", 0), number("depth", 1, 1, 3), number("maximum", 160, 20, 500), text("incoming") == "1", **options)
                elif path == "/api/words":
                    result = explorer.words(number("id", 0), number("offset", 0), number("limit", 64, 1, 128),
                                            1 if text("unaligned") == "1" else 4, **options)
                elif path == "/api/copies":
                    file = explorer.file(number("id", 0))
                    result = {"copies": [dict(row) for row in explorer.db.execute("SELECT * FROM files WHERE sha256=? AND sha256<>'' ORDER BY level,path LIMIT 200", (file["sha256"],))]}
                elif path == "/api/catalog":
                    from .catalog import catalog
                    result = catalog()
                elif path.startswith("/docs/"):
                    self.static(DOCS, unquote(path[6:]))
                    return
                else:
                    self.static(WEB, "index.html" if path == "/" else unquote(path[1:]))
                    return
                self.send(json.dumps(result, ensure_ascii=True).encode())
            except (ValueError, KeyError, OSError, IndexError) as exc:
                self.send(json.dumps({"error": str(exc)}).encode(), status=400)

        def static(self, root: Path, name: str) -> None:
            target = (root / name).resolve()
            if not target.is_relative_to(root.resolve()) or not target.is_file() or target.suffix.lower() not in {".html", ".css", ".js"}:
                self.send(b'{"error":"not found"}', status=404)
                return
            mime = {".js": "text/javascript", ".css": "text/css", ".html": "text/html"}[target.suffix.lower()]
            self.send(target.read_bytes(), mime + "; charset=utf-8")

    server = HTTPServer(("127.0.0.1", port), Handler)
    print(f"File connections: http://127.0.0.1:{server.server_port}/", flush=True)
    print("Read-only input access. Press Ctrl+C to stop.", flush=True)
    if open_browser:
        import webbrowser
        webbrowser.open(f"http://127.0.0.1:{server.server_port}/")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        explorer.db.close()
