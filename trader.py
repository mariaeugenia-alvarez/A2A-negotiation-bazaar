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
    ap.add_argument("--no-boards", dest="boards", action="store_false", help="only offers made to us, not the public boards")
    args = ap.parse_args()
    os.makedirs(log.LOG_DIR, exist_ok=True)
    lock = open(os.path.join(log.LOG_DIR, "trader.lock"), "w")
    try:  # a second trader on the same key could accept twice
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        sys.exit("another trader.py is already running (logs/trader.lock)")
    b = connect()
    st, fees, fees_at, seen = State(b), {}, -999, set()
    active, boards_at = [], -999
    log.say(f"trader: {'LIVE' if args.live else 'shadow'}")
    while True:
        try:
            clock = b.clock()
            tick = clock["tick"]
            st.refresh()
            if tick - fees_at >= 20:
                fees, fees_at = venue_fees(b), tick
            valuer, by_ref, missing = price.from_state(st), st.by_ref(), st.missing()
            # offers made to us, then the public boards (the bulk of the deal flow): same rules for both
            todo = [(o, "to_us") for o in (b.my_offers().get("offers") or []) if o.get("to") == st.me["id"]]
            if args.boards:
                if tick - boards_at >= 10:  # which boards hold offers: look at all of them now and then
                    active = [v for v in fees if b.board(v).get("offers")]
                    boards_at = tick
                for v in active:
                    todo += [(o, "board") for o in b.board(v).get("offers") or [] if not o.get("to")]
            decisions = []
            for o, source in todo:
                if o.get("status") != "open":
                    continue
                d = judge(o, valuer, by_ref, st.cash, fees, missing, st.me["id"])
                decisions.append(d)
                key = (d["offer"], d["action"], d.get("surplus"))
                if key not in seen and (source == "to_us" or d["action"] in ("accept", "counter", "human")):
                    seen.add(key)
                    log.event("trader", tick=tick, expires=o.get("expires_tick"), live=args.live, source=source, **d)
                    if source == "to_us" or d["action"] in ("accept", "human"):
                        log.say(f"[t{tick}] {source} offer {d['offer']} on {d['venue']} from {d['maker']}: "
                                f"{d['action'].upper()} · {d['why']}")
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
