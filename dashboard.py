"""Dashboard of our games against every dealer, the duels, and what we can see of the other teams.

    python3 dashboard.py              # builds logs/dashboard.html and opens it in the browser
    python3 dashboard.py --no-open    # only builds it
    python3 dashboard.py --offline    # no network: only what is already in logs/
    python3 dashboard.py --serve      # keeps running: serves the page on http://127.0.0.1:8765 and refreshes it by itself
    python3 dashboard.py --serve --every 20 --port 9000
    python3 dashboard.py --json       # prints the data instead of the page (to debug)

It only reads (the game's public pages, and our own data if BAZAAR_KEY is set) and writes under logs/.
Run it again to refresh. Run feed_logger.py next to it to keep the other teams' history: the public feed only holds
the last ~500 events.
"""
import argparse
import hashlib
import json
import os
import signal
import socket
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from bz import dash, log

HERE = os.path.dirname(os.path.abspath(__file__))
TEMPLATE = os.path.join(HERE, "dashboard", "template.html")
OUT = os.path.join(log.LOG_DIR, "dashboard.html")


def render(data: dict) -> str:
    blob = json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    return open(TEMPLATE, encoding="utf-8").read().replace("/*__DATA__*/null", blob)


def stamp(data: dict) -> dict:
    """A short fingerprint of everything but the build time: the page redraws only when it changes."""
    body = {k: v for k, v in data.items() if k not in ("built", "rev", "live")}
    data["rev"] = hashlib.sha1(json.dumps(body, sort_keys=True, default=str).encode()).hexdigest()[:12]
    return data


JOURNAL = os.path.join(log.LOG_DIR, "dashboard_server.log")


def journal(msg: str) -> None:
    """One line per start, stop and failure of --serve, so that 'why did it stop?' has an answer next time."""
    os.makedirs(log.LOG_DIR, exist_ok=True)
    with open(JOURNAL, "a", encoding="utf-8") as f:
        f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} pid {os.getpid()} {msg}\n")


def free_port(first: int) -> int:
    """The wanted port, or the next free one: a second copy must not crash because the first still holds it."""
    for port in range(first, first + 10):
        with socket.socket() as s:
            if s.connect_ex(("127.0.0.1", port)) != 0:
                return port
    return first


def serve(args) -> None:
    """Rebuild the data every few seconds in the background and serve it. Local only: the data holds private values."""
    box = {"data": None}
    lock = threading.Lock()
    started = time.strftime("%H:%M:%S")
    args.port = free_port(args.port)

    def refresh() -> None:
        data = stamp(dash.build(offline=args.offline, key=not args.no_key))
        data["live"] = {"every": max(3, min(args.every, 10)), "refresh": args.every, "pid": os.getpid(), "since": started}
        with lock:
            box["data"] = data

    refresh()

    def loop() -> None:
        while True:
            time.sleep(args.every)
            try:
                refresh()
            except BaseException as e:  # a bad moment of the network must not stop the dashboard
                journal(f"refresh failed: {type(e).__name__}: {e}")
                log.say(f"dashboard: no se pudo refrescar ({type(e).__name__}: {e}), sigo con los datos anteriores")

    threading.Thread(target=loop, daemon=True).start()

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            with lock:
                data = box["data"]
            path = self.path.split("?")[0]
            if path in ("/", "/index.html", "/dashboard.html"):
                body, kind = render(data).encode("utf-8"), "text/html; charset=utf-8"
            elif path == "/data.json":
                body, kind = json.dumps(data, ensure_ascii=False, separators=(",", ":")).encode("utf-8"), "application/json"
            else:
                self.send_error(404)
                return
            self.send_response(200)
            self.send_header("Content-Type", kind)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *a) -> None:
            pass

    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)  # 127.0.0.1: only this computer can read it
    url = f"http://127.0.0.1:{args.port}/"
    log.say(f"dashboard: {url} (se actualiza solo cada {args.every} s; Ctrl+C para parar)")
    journal(f"started on {url}")

    def stopped_by(signum, _frame):  # someone ran kill, or the terminal window was closed
        name = signal.Signals(signum).name
        journal(f"stopped by {name} ({'terminal closed' if name == 'SIGHUP' else 'kill or stop request'})")
        raise SystemExit(0)

    for sig in (signal.SIGTERM, signal.SIGHUP):
        signal.signal(sig, stopped_by)
    if not args.no_open and sys.platform == "darwin":
        subprocess.run(["open", url], check=False)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        journal("stopped by Ctrl+C")
    except SystemExit:
        raise
    except BaseException as e:
        journal(f"crashed: {type(e).__name__}: {e}")
        raise


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--offline", action="store_true")
    ap.add_argument("--no-key", action="store_true", help="do not use our key: only public data and the logs")
    ap.add_argument("--no-open", action="store_true")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--out", default=OUT)
    ap.add_argument("--serve", action="store_true", help="stay running and refresh the page by itself")
    ap.add_argument("--every", type=int, default=20, help="seconds between refreshes with --serve")
    ap.add_argument("--port", type=int, default=8765)
    args = ap.parse_args()
    if args.serve:
        serve(args)
        return
    data = dash.build(offline=args.offline, key=not args.no_key)
    if args.json:
        print(json.dumps(data, ensure_ascii=False, indent=1))
        return
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        f.write(render(data))
    log.say(f"dashboard: {args.out} ({len(data['ours'])} hilos nuestros, {len(data['others'])} de otros equipos, "
            f"{len(data['duels'])} duelos)")
    if data.get("errors"):
        log.say(f"dashboard: no se pudo leer: {', '.join(data['errors'])}")
    if not args.no_open and sys.platform == "darwin":
        subprocess.run(["open", args.out], check=False)


if __name__ == "__main__":
    main()
