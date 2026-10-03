"""Score observer for the experiments: it records our score numbers whenever one changes, with the tag of the
experiment running at that moment, and the leader's and the median's negotiating score (to tell a change of ours
from a drift of the whole field). Read-only.

    python3 observe.py                  # runs until stopped; appends to logs/score.jsonl
    python3 observe.py tag E1-duels-I   # sets the tag stored with every later line (python3 observe.py tag - clears it)
"""
import argparse
import json
import os
import statistics
import sys
import time

from agent import connect
from bazaar_sdk import BazaarError
from bz import log

TAG = os.path.join(log.LOG_DIR, "tag.txt")
FIELDS = ("score", "negotiating", "market", "neg_points", "duel_points", "ladder_points", "mm_points",
          "bench_efficiency", "bench_points", "rank")


def current_tag() -> str:
    try:
        return open(TAG, encoding="utf-8").read().strip()
    except OSError:
        return ""


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", nargs="?", choices=["tag"])
    ap.add_argument("value", nargs="?")
    ap.add_argument("--every", type=float, default=15.0, help="seconds between reads")
    args = ap.parse_args()
    os.makedirs(log.LOG_DIR, exist_ok=True)
    if args.cmd == "tag":
        open(TAG, "w", encoding="utf-8").write("" if args.value in (None, "-") else args.value)
        print("tag:", current_tag() or "(none)")
        return
    b = connect()
    last = None
    log.say("observer: appending to logs/score.jsonl")
    while True:
        try:
            me = b.me()
            s = me.get("score") or {}
            now = {k: s.get(k) for k in FIELDS}
            if now != last:
                neg = [t["negotiating"] for t in b.leaderboard().get("teams", []) if t.get("negotiating") is not None]
                row = {"tick": me.get("tick"), "tag": current_tag(), "cash": me.get("cash"), "deals": s.get("deals"),
                       "leader_neg": max(neg) if neg else None, "median_neg": statistics.median(neg) if neg else None, **now}
                log.event("score", **row)
                changed = {k: (last or {}).get(k, "-") for k in FIELDS if last is None or now[k] != last.get(k)}
                log.say(f"[t{row['tick']}] {row['tag'] or '-'}: " + ", ".join(f"{k} {changed[k]} -> {now[k]}" for k in changed))
                last = now
        except BazaarError as e:
            log.say(f"observer: {e}")
        except Exception as e:
            log.say(f"observer: unexpected {type(e).__name__}: {e}")
        time.sleep(args.every)


if __name__ == "__main__":
    sys.exit(main())
