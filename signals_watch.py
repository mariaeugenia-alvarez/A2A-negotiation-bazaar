"""Reads the public boards every tick and reports price drops (bz/signals.py). READ-ONLY: it never posts, accepts or cancels.

    python3 signals_watch.py            # runs until stopped; prints alerts, logs everything to logs/signals.jsonl

What it logs (logs/signals.jsonl), one line per new single-card ask: tick, venue, maker (a board pseudonym), card, price,
kind (new / drop / raise / same), the previous price, the drop size, drops in a row, and, for cards we still need,
whether we would take it (clears / near / gap / gain). Alerts on the screen and in logs/alerts.jsonl:
  DROP-TAKE  a dropped ask for a card we need that clears our rules NOW (trader.py --live-boards takes it if it runs)
  DROP-NEAR  a dropped ask within 25 % above the most we would pay (one more drop would clear it)
Why it exists: tests whether a price drop is a signal. Read the result later with:  python3 signals_watch.py --report
"""
import argparse
import json
import os
import sys
import time

from agent import connect
from bazaar_sdk import BazaarError
from bz import log
from bz.signals import AskTracker, assess
from bz.state import State
from bz.trade import fee_for

PATH = os.path.join(log.LOG_DIR, "signals.jsonl")


def report() -> None:
    rows = [json.loads(line) for line in open(PATH, encoding="utf-8")] if os.path.exists(PATH) else []
    by = {}
    for r in rows:
        by.setdefault(r["kind"], []).append(r)
    print(f"{len(rows)} asks seen:", {k: len(v) for k, v in by.items()})
    d = by.get("drop", [])
    if d:
        sizes = sorted(r["pct"] for r in d)
        print(f"drops: median {sizes[len(sizes) // 2]:.0%}, {sum(1 for r in d if r['drops_in_row'] >= 2)} in a staircase (2+ in a row)")
        need = [r for r in d if r.get("clears") is not None]
        print(f"drops on cards we need: {len(need)}, clearing our rules: {sum(1 for r in need if r['clears'])}, "
              f"near: {sum(1 for r in need if r.get('near'))}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--report", action="store_true")
    args = ap.parse_args()
    if args.report:
        return report()
    b = connect()
    st = State(b)
    tracker, fees, fees_at, active, active_at = AskTracker(), {}, -999, [], -999
    value_cache = {}
    log.say("signals_watch: read-only; logs/signals.jsonl")
    while True:
        try:
            tick = b.clock()["tick"]
            if tick - fees_at >= 20:
                fees = {v["venue"]: (v.get("fee_bps", 0), v.get("fee_per_card", 0)) for v in b.venues().get("venues", [])}
                fees_at = tick
                st.refresh()
                value_cache = {}
            if tick - active_at >= 10:
                active = [v for v in fees if b.board(v).get("offers")]
                active_at = tick
            asks = []
            for v in active:
                for o in b.board(v).get("offers") or []:
                    g, w = o.get("give") or {}, o.get("want") or {}
                    if len(g.get("assets") or []) == 1 and w.get("cash") and not g.get("cash") and not o.get("to") \
                            and (g["assets"][0].get("kind") == "card"):
                        asks.append({"id": o["id"], "maker": o.get("maker"), "ref": g["assets"][0]["ref"],
                                     "price": int(w["cash"]), "venue": v})
            needed = {r for refs in st.missing().values() for r in refs}
            for ev in tracker.update(tick, asks):
                if ev["ref"] in needed:
                    if ev["ref"] not in value_cache:
                        value_cache[ev["ref"]] = float(b.value(ev["ref"])["your_value"])
                    a = assess(ev, value_cache[ev["ref"]], fee_for(fees, ev["venue"], ev["price"], 1))
                    ev = {**ev, "value": value_cache[ev["ref"]], **a}
                log.event("signals", **ev)
                if ev["kind"] == "drop" and ev.get("clears"):
                    log.event("alerts", level="DROP-TAKE", text=f"{ev['ref']} ask {ev['last']} -> {ev['price']} on {ev['venue']}")
                    log.say(f"ALERT DROP-TAKE: {ev['ref']} ask {ev['last']} -> {ev['price']} ({ev['pct']:.0%}) on {ev['venue']}: "
                            f"clears our rules, gain +{ev['gain']}")
                elif ev["kind"] == "drop" and ev.get("near"):
                    log.say(f"ALERT DROP-NEAR: {ev['ref']} ask {ev['last']} -> {ev['price']} ({ev['pct']:.0%}) on {ev['venue']}: "
                            f"we would pay at most {ev['max_price']}")
            b.wait_tick()
        except BazaarError as e:
            log.say(f"signals_watch: {e}")
            time.sleep(3)
        except Exception as e:  # never die
            log.say(f"signals_watch: unexpected {type(e).__name__}: {e}")
            time.sleep(3)


if __name__ == "__main__":
    sys.exit(main())
