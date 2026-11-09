"""Local-only keep/mulligan dashboard.

    python -m solitaire_spy.mulligan.server [--deck resources/stock_main_no_initiative.txt]  (default deck; every *.txt next to it is selectable) [--port 8765]

Binds to 127.0.0.1 only. Rules and tags are persisted next to the deck under
resources/mulligan/<deck-stem>.rules.json / .tags.json.
"""
import argparse
import json
import mimetypes
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

from solitaire_spy.mulligan import model

ROOT = Path(__file__).resolve().parents[2]
STATIC = Path(__file__).parent / "static"
IMAGES = ROOT / "resources" / "images"
DATA_DIR = ROOT / "resources" / "mulligan"
DEFAULT_DECK = ROOT / "resources" / "stock_main_no_initiative.txt"


class DeckContext:
    """Everything the dashboard needs for one deck list: hands, tags and rules."""

    def __init__(self, deck_path):
        self.deck_path = Path(deck_path)
        self.deck = model.load_decklist(self.deck_path)
        self.space = model.HandSpace(self.deck)
        stem = self.deck_path.stem
        self.rules_path = DATA_DIR / f"{stem}.rules.json"
        self.tags_path = DATA_DIR / f"{stem}.tags.json"
        self.tags = model.load_tags(self.tags_path, self.space)
        self.rules = (json.loads(self.rules_path.read_text())
                      if self.rules_path.exists() else [])
        self.lock = threading.Lock()

    def state(self):
        return {
            "deck_name": self.deck_path.stem,
            "deck": [{"name": n, "count": c} for n, c in self.deck],
            "deck_size": self.space.deck_size,
            "tags": self.tags,
            "rules": self.rules,
            "sizes": list(model.HAND_SIZES),
            "modes": list(model.MODES),
        }

    def save_rules(self, rules):
        model.validate_rules(rules)
        with self.lock:
            self.rules = rules
            model.save_json(self.rules_path, rules)

    def save_tags(self, tags):
        clean = {}
        for tag, cards in tags.items():
            if not tag.replace("_", "").isalnum():
                raise ValueError(f"Bad tag name {tag!r} (letters, digits, underscore)")
            clean[tag] = [c for c in cards if c in self.space.index]
        with self.lock:
            self.tags = clean
            model.save_json(self.tags_path, clean)


class App:
    """Registry of the deck lists in resources/*.txt, loaded lazily."""

    def __init__(self, default_deck):
        self.deck_dir = Path(default_deck).resolve().parent
        self.default = Path(default_deck).stem
        self.contexts = {}
        self.lock = threading.Lock()

    def deck_names(self):
        names = sorted(p.stem for p in self.deck_dir.glob("*.txt"))
        return [self.default] + [n for n in names if n != self.default] if self.default in names else names

    def get(self, name=None):
        name = name or self.default
        if name not in self.deck_names():
            raise ValueError(f"Unknown deck {name!r}")
        with self.lock:
            if name not in self.contexts:
                self.contexts[name] = DeckContext(self.deck_dir / f"{name}.txt")
            return self.contexts[name]


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

        def _body(self):
            return json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")

        def _file(self, base, rel):
            path = (base / rel).resolve()
            if base.resolve() not in path.parents or not path.is_file():
                return self._send(404, {"error": "not found"})
            ctype = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
            self._send(200, path.read_bytes(), ctype)

        @staticmethod
        def _image(name):
            # deck lists differ in capitalisation ("Lead The Stampede"); match files case-insensitively
            wanted = (name + ".jpg").lower()
            return next((p.name for p in IMAGES.glob("*.jpg") if p.name.lower() == wanted), name + ".jpg")

        def _guard(self, fn):
            try:
                fn()
            except (ValueError, KeyError, TypeError, json.JSONDecodeError) as e:
                self._send(400, {"error": str(e)})

        def do_GET(self):
            url = urlparse(self.path)
            if url.path == "/api/decks":
                return self._send(200, {"decks": app.deck_names(), "default": app.default})
            if url.path == "/api/state":
                return self._guard(lambda: self._send(200, app.get(parse_qs(url.query).get("deck", [None])[0]).state()))
            if url.path.startswith("/img/"):
                return self._file(IMAGES, self._image(unquote(url.path[5:])))
            rel = "index.html" if url.path == "/" else url.path.lstrip("/")
            return self._file(STATIC, rel)

        def do_POST(self):
            url = urlparse(self.path)

            def run():
                body = self._body()
                ctx = app.get(body.get("deck"))
                rules = body.get("rules", ctx.rules)
                tags = body.get("tags", ctx.tags)
                model.validate_rules(rules)
                if url.path == "/api/summary":
                    return self._send(200, model.summarize(ctx.space, tags, rules))
                if url.path == "/api/hands":
                    return self._send(200, model.query_hands(
                        ctx.space, tags, rules, int(body["size"]), body["mode"],
                        body.get("filter", "undecided"), body.get("has", []),
                        int(body.get("offset", 0)), min(int(body.get("limit", 50)), 500)))
                self._send(404, {"error": "not found"})

            self._guard(run)

        def do_PUT(self):
            url = urlparse(self.path)

            def run():
                body = self._body()
                ctx = app.get(body.get("deck"))
                if url.path == "/api/rules":
                    ctx.save_rules(body["rules"])
                elif url.path == "/api/tags":
                    ctx.save_tags(body["tags"])
                else:
                    return self._send(404, {"error": "not found"})
                self._send(200, {"ok": True})

            self._guard(run)

    return Handler


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--deck", default=str(DEFAULT_DECK))
    ap.add_argument("--port", type=int, default=8765)
    args = ap.parse_args()
    app = App(args.deck)
    app.get()  # load the default deck eagerly so startup errors show immediately
    server = ThreadingHTTPServer(("127.0.0.1", args.port), make_handler(app))
    print(f"Keep/mull dashboard for {Path(args.deck).name} (+ other decks in its folder): http://127.0.0.1:{args.port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
