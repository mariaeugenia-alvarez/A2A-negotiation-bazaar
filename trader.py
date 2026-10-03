"""Offers made to us, judged every tick by bz/trade.py. SHADOW by default: it prints and logs what it would do and sends nothing.

    python3 trader.py                 # shadow: logs/trader.jsonl gets one line per new decision
    python3 trader.py --once          # one pass, then stop
    python3 trader.py --live          # ALSO accepts the best clear win each tick (one accept per tick). Ask first.

Only structure is read: what the offer gives and wants. The words around it never count.
"""
import argparse
import fcntl
import os
import sys
import time

from agent import connect
from bazaar_sdk import BazaarError
from bz import log, price
from bz.state import State
from bz.trade import judge


def venue_fees(b) -> dict:
    return {v["venue"]: (v.get("fee_bps", 0), v.get("fee_per_card", 0)) for v in b.venues().get("venues", [])}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--live", action="store_true", help="accept the best 'accept' decision each tick")
    ap.add_argument("--once", action="store_true")
    args = ap.parse_args()
    os.makedirs(log.LOG_DIR, exist_ok=True)
    lock = open(os.path.join(log.LOG_DIR, "trader.lock"), "w")
    try:  # a second trader on the same key could accept twice
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        sys.exit("another trader.py is already running (logs/trader.lock)")
    b = connect()
    st, fees, fees_at, seen = State(b), {}, -999, set()
    log.say(f"trader: {'LIVE' if args.live else 'shadow'}")
    while True:
        try:
            clock = b.clock()
            tick = clock["tick"]
            st.refresh()
            if tick - fees_at >= 20:
                fees, fees_at = venue_fees(b), tick
            valuer, by_ref, missing = price.from_state(st), st.by_ref(), st.missing()
            offers = (b.my_offers().get("offers") or [])
            decisions = []
            for o in offers:
                if o.get("to") != st.me["id"] or o.get("status") != "open":
                    continue
                d = judge(o, valuer, by_ref, st.cash, fees, missing, st.me["id"])
                decisions.append(d)
                key = (d["offer"], d["action"], d.get("surplus"))
                if key not in seen:
                    seen.add(key)
                    log.event("trader", tick=tick, expires=o.get("expires_tick"), live=args.live, **d)
                    log.say(f"[t{tick}] offer {d['offer']} from {d['maker']}: {d['action'].upper()} · {d['why']}")
            wins = sorted((d for d in decisions if d["action"] == "accept"), key=lambda d: -d["surplus"])
            if args.live and wins:
                w = wins[0]
                b.accept(w["offer"], assets=w["assets"] or None)
                log.event("trader_accept", tick=tick, **w)
                log.say(f"[t{tick}] ACCEPTED offer {w['offer']} (+{w['surplus']} P)")
            if args.once:
                log.say(f"{len(decisions)} offers addressed to us")
                return
            b.wait_tick()
        except BazaarError as e:
            log.say(f"trader: {e}")
            time.sleep(3)
        except Exception as e:  # never die on one odd offer
            log.say(f"trader: unexpected {type(e).__name__}: {e}")
            time.sleep(3)


if __name__ == "__main__":
    main()
