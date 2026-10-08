"""Weboberfläche: python -m icd_agent.web  →  http://localhost:8000"""

from __future__ import annotations

import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import anthropic

from .agent import KodierFehler, kodieren
from .catalog import katalog_laden

INDEX = Path(__file__).resolve().parent / "static" / "index.html"
KATALOG = katalog_laden()


class Handler(BaseHTTPRequestHandler):
    def _json(self, status: int, daten: dict) -> None:
        body = json.dumps(daten, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        if self.path == "/api/status":
            self._json(200, {"katalog": KATALOG.quelle if KATALOG else None, "anzahl": len(KATALOG) if KATALOG else 0})
            return
        if self.path not in ("/", "/index.html"):
            self.send_error(404)
            return
        body = INDEX.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self) -> None:
        if self.path != "/api/kodieren":
            self.send_error(404)
            return
        try:
            laenge = int(self.headers.get("Content-Length", 0))
            text = json.loads(self.rfile.read(laenge) or b"{}").get("text", "")
            self._json(200, kodieren(text, KATALOG))
        except KodierFehler as e:
            self._json(400, {"fehler": str(e)})
        except anthropic.AuthenticationError:
            self._json(500, {"fehler": "Kein gültiger ANTHROPIC_API_KEY gesetzt."})
        except anthropic.APIError as e:
            self._json(502, {"fehler": f"Fehler bei der Claude-API: {e}"})
        except Exception as e:  # noqa: BLE001 – Browser soll immer eine lesbare Meldung bekommen
            self._json(500, {"fehler": f"Interner Fehler: {e}"})


def main() -> None:
    host = os.environ.get("HOST", "127.0.0.1")
    port = int(os.environ.get("PORT", "8000"))
    print(f"ICD-Assistent läuft auf http://{host}:{port}")
    print(f"Katalog: {KATALOG.quelle} ({len(KATALOG)} Codes)" if KATALOG else "Kein Katalog geladen – Codes ungeprüft.")
    ThreadingHTTPServer((host, port), Handler).serve_forever()


if __name__ == "__main__":
    main()
