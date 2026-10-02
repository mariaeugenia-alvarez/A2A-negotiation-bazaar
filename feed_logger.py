"""Keep every public event: the feed only holds the last 500 (about 20 ticks), so we poll it and append new ones.

    python3 feed_logger.py            # runs until stopped; appends to logs/feed.jsonl
    python3 feed_logger.py --every 30

Every team's haggles with the dealers are in it (offers included), which is how we learn their limits for free.
"""
import argparse
import json
import os
import time

from agent import connect
from bazaar_sdk import BazaarError
from bz import log

PATH = os.path.join(log.LOG_DIR, "feed.jsonl")


def last_seen() -> int:
    """Highest event id already stored, so a restart neither repeats nor skips."""
    if not os.path.exists(PATH):
        return 0
    last = 0
    with open(PATH, encoding="utf-8") as f:
        for line in f:
            try:
                last = max(last, json.loads(line)["id"])
            except (ValueError, KeyError):
                pass
    return last


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--every", type=float, default=60.0, help="seconds between polls (keep it under ~15 ticks)")
    args = ap.parse_args()
    b = connect()
    seen = last_seen()
    os.makedirs(log.LOG_DIR, exist_ok=True)
    log.say(f"feed logger: appending to {PATH}, last stored event {seen}")
    while True:
        try:
            events = b.feed(limit=500).get("events") or []
            new = sorted((e for e in events if e["id"] > seen), key=lambda e: e["id"])
            if new and seen and events and min(e["id"] for e in events) > seen + 1 and len(events) >= 500:
                log.say(f"feed logger: possible gap after event {seen} (polling too slowly?)")
            if new:
                with open(PATH, "a", encoding="utf-8") as f:
                    for e in new:
                        f.write(json.dumps(e, ensure_ascii=False) + "\n")
                seen = new[-1]["id"]
                log.say(f"feed logger: +{len(new)} events (tick {new[-1]['tick']}, last id {seen})")
        except BazaarError as e:
            log.say(f"feed logger: {e}, retrying")
        except Exception as e:  # never die: a lost hour of feed cannot be recovered
            log.say(f"feed logger: unexpected {type(e).__name__}: {e}")
        time.sleep(args.every)


if __name__ == "__main__":
    main()
