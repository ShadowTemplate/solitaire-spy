"""Local-only sideboard-guide dashboard.

    python -m solitaire_spy.sideboard.server [--dir resources] [--deck NAME] [--port 8766]

The deck lists (every *.txt in --dir that has a sideboard; main-only lists are ignored) are
selectable in the UI; the default is team_geddon (--deck picks another, else the first listed). The
matchup rankings live in resources/sideboard/matchups.json (see bootstrap.py) and are
rewritten whenever the ranking is re-ordered in the dashboard. Binds to 127.0.0.1 only.
"""
import argparse
import json
import mimetypes
import os
import re
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parents[2]
STATIC = Path(__file__).parent / "static"
MATCHUPS = ROOT / "resources" / "sideboard" / "matchups.json"
DECK_DIR = ROOT / "resources"
DEFAULT_DECK = "team_geddon"  # selected on load when it is available (else the first eligible list)
BASES = ("sheet", "optional", "inferred", "untouchable", "implied")


def load_decklist(path):
    """Parse `N Card Name` lines into {'main': [...], 'sideboard': [...]} (each [{name, count}]).

    The sideboard starts at a "Sideboard" marker or, as in MTGO/Arena exports, after a blank line
    that follows the main deck. Split cards ("Fang Dragon // Forktail Sweep") keep their first face.
    """
    sections = {"main": {}, "sideboard": {}}
    current = "main"
    for raw in Path(path).read_text().splitlines():
        line = raw.strip()
        if not line:
            if sections["main"]:
                current = "sideboard"
            continue
        if line.startswith("#"):
            continue
        if re.match(r"(?i)^(sideboard|sb:)", line):
            current = "sideboard"
            continue
        m = re.match(r"^(\d+)x?\s+(.+)$", line)
        if not m:
            raise ValueError(f"Cannot parse deck line: {raw!r}")
        name = m.group(2).split("//")[0].strip()
        sections[current][name] = sections[current].get(name, 0) + int(m.group(1))
    return {k: [{"name": n, "count": c} for n, c in v.items()] for k, v in sections.items()}


def validate_matchups(doc, previous):
    """Reject anything that is not a re-ordering/edit of the existing structure."""
    if not isinstance(doc, dict) or not isinstance(doc.get("matchups"), list):
        raise ValueError("Expected an object with a 'matchups' list")
    if [m.get("id") for m in doc["matchups"]] != [m["id"] for m in previous["matchups"]]:
        raise ValueError("Matchups cannot be added, removed or re-ordered through the API")
    for m in doc["matchups"]:
        target = m.get("target")
        if not isinstance(target, dict) or not all(isinstance(v, int) and 0 <= v <= 60 for v in target.values()):
            raise ValueError(f"{m['id']}: 'target' must map cards to copies")
        for side in ("in", "out"):
            cards = [e.get("card") for e in m[side]]
            if len(set(cards)) != len(cards) or not all(isinstance(c, str) and c for c in cards):
                raise ValueError(f"{m['id']}.{side}: cards must be unique non-empty names")
            for e in m[side]:
                if not isinstance(e.get("copies"), int) or not 0 <= e["copies"] <= 60:
                    raise ValueError(f"{m['id']}.{side}.{e['card']}: bad copies")
                if e.get("basis") not in BASES:
                    raise ValueError(f"{m['id']}.{side}.{e['card']}: bad basis")


class App:
    def __init__(self, deck_dir=DECK_DIR, preferred=None, matchups_path=MATCHUPS):
        self.deck_dir = Path(deck_dir).resolve()
        self.preferred = preferred
        self.matchups_path = Path(matchups_path)
        self.lock = threading.Lock()

    def deck_names(self):
        """Only complete lists (main + sideboard); main-only lists have nothing to side in from."""
        names = []
        for path in sorted(self.deck_dir.glob("*.txt")):
            try:
                if load_decklist(path)["sideboard"]:
                    names.append(path.stem)
            except ValueError:
                pass  # not a deck list
        if self.preferred in names:
            names.remove(self.preferred)
            names.insert(0, self.preferred)
        return names

    @property
    def default(self):
        names = self.deck_names()
        if not names:
            raise ValueError(f"No deck list with a sideboard found in {self.deck_dir}")
        return names[0]

    def deck(self, name=None):
        name = name or self.default
        if name not in self.deck_names():
            raise ValueError(f"Unknown deck {name!r}")
        return {"name": name, **load_decklist(self.deck_dir / f"{name}.txt")}

    def matchups(self):
        with self.lock:
            return json.loads(self.matchups_path.read_text())

    def save_matchups(self, doc):
        with self.lock:
            validate_matchups(doc, json.loads(self.matchups_path.read_text()))
            tmp = self.matchups_path.with_suffix(".tmp")
            tmp.write_text(json.dumps(doc, indent=1, ensure_ascii=False) + "\n")
            os.replace(tmp, self.matchups_path)


def make_handler(app):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):
            pass

        def _send(self, status, body, ctype="application/json"):
            if not isinstance(body, bytes):
                body = json.dumps(body).encode()
            self.send_response(status)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def _file(self, base, rel):
            path = (base / rel).resolve()
            if base.resolve() not in path.parents or not path.is_file():
                return self._send(404, {"error": "not found"})
            self._send(200, path.read_bytes(), mimetypes.guess_type(path.name)[0] or "application/octet-stream")

        def _guard(self, fn):
            try:
                fn()
            except (ValueError, KeyError, TypeError, AttributeError, json.JSONDecodeError) as e:
                self._send(400, {"error": str(e)})

        def do_GET(self):
            url = urlparse(self.path)
            if url.path == "/api/decks":
                return self._send(200, {"decks": app.deck_names(), "default": app.default})
            if url.path == "/api/deck":
                return self._guard(lambda: self._send(200, app.deck(parse_qs(url.query).get("name", [None])[0])))
            if url.path == "/api/matchups":
                return self._send(200, app.matchups())
            return self._file(STATIC, "index.html" if url.path == "/" else url.path.lstrip("/"))

        def do_PUT(self):
            if urlparse(self.path).path != "/api/matchups":
                return self._send(404, {"error": "not found"})

            def run():
                app.save_matchups(json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0)))))
                self._send(200, {"ok": True})

            self._guard(run)

    return Handler


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dir", default=str(DECK_DIR), help="folder holding the deck lists (*.txt)")
    ap.add_argument("--deck", default=DEFAULT_DECK, help="name of the deck list selected by default (without .txt)")
    ap.add_argument("--port", type=int, default=8766)
    args = ap.parse_args()
    app = App(args.dir, args.deck)
    app.deck()
    app.matchups()  # fail fast if missing: run `python -m solitaire_spy.sideboard.bootstrap`
    server = ThreadingHTTPServer(("127.0.0.1", args.port), make_handler(app))
    print(f"Sideboard dashboard ({len(app.deck_names())} deck lists from {app.deck_dir}): http://127.0.0.1:{args.port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
