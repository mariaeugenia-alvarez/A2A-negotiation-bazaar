"""Dashboard of our games against every dealer, the duels, and what we can see of the other teams.

    python3 dashboard.py              # builds logs/dashboard.html and opens it in the browser
    python3 dashboard.py --no-open    # only builds it
    python3 dashboard.py --offline    # no network: only what is already in logs/
    python3 dashboard.py --json       # prints the data instead of the page (to debug)

It only reads (the game's public pages, and our own data if BAZAAR_KEY is set) and writes under logs/.
Run it again to refresh. Run feed_logger.py next to it to keep the other teams' history: the public feed only holds
the last ~500 events.
"""
import argparse
import json
import os
import subprocess
import sys

from bz import dash, log

HERE = os.path.dirname(os.path.abspath(__file__))
TEMPLATE = os.path.join(HERE, "dashboard", "template.html")
OUT = os.path.join(log.LOG_DIR, "dashboard.html")


def render(data: dict) -> str:
    blob = json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    return open(TEMPLATE, encoding="utf-8").read().replace("/*__DATA__*/null", blob)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--offline", action="store_true")
    ap.add_argument("--no-key", action="store_true", help="do not use our key: only public data and the logs")
    ap.add_argument("--no-open", action="store_true")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--out", default=OUT)
    args = ap.parse_args()
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
