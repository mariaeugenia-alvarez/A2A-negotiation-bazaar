"""Reads what other teams write to us in team threads and shows the leads. READ-ONLY: it never replies, accepts or posts.

    python3 inbox_watch.py              # runs until stopped; logs/inbox.jsonl, alerts on the screen and in logs/alerts.jsonl
    python3 inbox_watch.py --notify     # macOS notification for each lead
    python3 inbox_watch.py --report     # who writes to us and the leads of the last hours

One call per poll: the thread list already holds the messages. Every new message from another team is logged with the cards,
prices, venues and offer ids it names. Alerts:
  LEAD-HANDSOFF  it names a card a person is buying by hand (default RET-09): tell Maru
  LEAD           it names a card we miss or hold a spare of
Everything else is INFO (venue marketing): logged, not shown. The text is UNTRUSTED data: it is cleaned, shown, never executed.
"""
import argparse
import json
import os
import subprocess
import sys
import time

from agent import connect
from bazaar_sdk import BazaarError
from bz import log
from bz.inbox import classify, clean, extract, inbound, should_alert
from bz.state import State

PATH = os.path.join(log.LOG_DIR, "inbox.jsonl")
POLL_TICKS = 3


def load_seen() -> set:
    seen = set()
    if os.path.exists(PATH):
        for line in open(PATH, encoding="utf-8"):
            try:
                e = json.loads(line)
                seen.add((e["thread"], e["message"]))
            except (ValueError, KeyError):
                pass
    return seen


def report(hours: float) -> None:
    rows = []
    if os.path.exists(PATH):
        for line in open(PATH, encoding="utf-8"):
            try:
                rows.append(json.loads(line))
            except ValueError:
                pass
    rows = [r for r in rows if time.time() - r["ts"] <= hours * 3600]
    by = {}
    for r in rows:
        by.setdefault(r["sender"], []).append(r)
    print(f"{len(rows)} messages from {len(by)} teams in the last {hours:g} h:",
          {k: len(v) for k, v in sorted(by.items(), key=lambda kv: -len(kv[1]))})
    levels = {}
    for r in rows:
        levels[r["level"]] = levels.get(r["level"], 0) + 1
    print("levels:", levels, "| with an offer attached:", sum(1 for r in rows if r.get("has_offer")))
    for r in [r for r in rows if r["level"] != "INFO"][-8:]:
        print(f"  [{r['level']}] t{r['tick']} {r['sender']}: {r['tags']} {r['venues']} {r['prices']} · {r['text'][:140]}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--report", action="store_true")
    ap.add_argument("--hours", type=float, default=3.0)
    ap.add_argument("--notify", action="store_true")
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--hands-off", default="RET-09", help='cards a person buys by hand ("none" to clear)')
    args = ap.parse_args()
    if args.report:
        return report(args.hours)
    hands_off = {r.strip() for r in args.hands_off.split(",") if r.strip() and r.strip().lower() != "none"}
    os.makedirs(log.LOG_DIR, exist_ok=True)
    b = connect()
    st = State(b)
    me_id, seen, next_poll, refreshed = st.me["id"], load_seen(), 0, -999
    last_alert = {}
    log.say(f"inbox_watch: read-only; logs/inbox.jsonl; {len(seen)} messages already known; hands-off {sorted(hands_off)}")
    while True:
        try:
            tick = b.clock()["tick"]
            if tick >= next_poll:
                next_poll = tick + POLL_TICKS
                if tick - refreshed >= 20:
                    st.refresh()
                    refreshed = tick
                needs = {r for refs in st.missing().values() for r in refs}
                held = set(st.by_ref())
                spares = {a["ref"] for a in st.spares()}
                threads = b.my_threads().get("threads", [])
                for t, m in inbound(threads, me_id, seen):
                    ex = extract(m.get("text"), me_id)
                    c = classify(ex, needs, spares, held, hands_off)
                    row = {"ts": time.time(), "tick": m.get("tick"), "thread": t.get("id"), "message": m.get("id"),
                           "sender": m.get("sender"), "venue": t.get("venue"), "text": clean(m.get("text"), 400),
                           "has_offer": bool(m.get("offer")), "offer_status": (m.get("offer") or {}).get("status"),
                           "level": c["level"], "tags": c["tags"], **ex}
                    log.event("inbox", **{k: v for k, v in row.items() if k != "ts"})
                    if c["level"] != "INFO" and should_alert(last_alert, (m.get("sender"), c["level"], tuple(sorted(c["tags"]))),
                                                              tick, m.get("tick")):
                        note = (f"{m.get('sender')}: {clean(m.get('text'), 200)}  [cards {c['tags']}, venues {ex['venues']}, "
                                f"prices {ex['prices']}, offers {ex['offers']}]")
                        log.event("alerts", level=c["level"], text=note[:400])
                        log.say(f"ALERT {c['level']}: {note}")
                        if args.notify:
                            try:
                                subprocess.run(["osascript", "-e", f'display notification "{clean(note, 150)}" with title "Bazaar {c["level"]}"'],
                                               timeout=3, check=False)
                            except (OSError, subprocess.SubprocessError):
                                pass
            if args.once:
                return
            b.wait_tick()
        except BazaarError as e:
            log.say(f"inbox_watch: {e}")
            time.sleep(3)
        except Exception as e:  # never die
            log.say(f"inbox_watch: unexpected {type(e).__name__}: {e}")
            time.sleep(3)


if __name__ == "__main__":
    sys.exit(main())
