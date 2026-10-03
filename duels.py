"""Duels agent: every decision comes from bz/duel.py (code decides), the words only carry it politely.

    python3 duels.py                         # plays every live duel until none is left
    python3 duels.py --dry                   # prints the decisions, sends nothing
    python3 duels.py --rounds 3 --beta 2.0 --days-sign -1   # force: your_days_weight is a cost per day
"""
import argparse
import fcntl
import os
import sys
import time

from agent import connect
from bazaar_sdk import BazaarError
from bz import log
from bz.duel import OPEN2, OPEN_FRAC, decide, decide2

TEXTS = ["Thank you for meeting me. I can do {o}.", "I appreciate your move. {o} is where I can be.",
         "Let us close quickly: {o}.", "A real step towards you: {o}.", "I think {o} is fair for both of us."]


def offer_text(i: int, price: int, days) -> str:
    o = f"{price} P" + (f" with delivery on day {days}" if days is not None else "")
    return TEXTS[i % len(TEXTS)].format(o=o)


def arm_for(duel_id, arms: list) -> float:
    """Split test: each duel always gets the same arm (by its id), so the opening never changes mid-duel."""
    return arms[int(duel_id) % len(arms)]


def play(b, d: dict, tick: int, args) -> None:
    if args.policy == "v2":  # read the bot (doctrine approved 13:35): every decision, waits included, is logged
        arm = f"v2 {args.open2['buyer']}/{args.open2['seller']}"
        a = decide2(d, tick, open2=args.open2, days_sign=args.days_sign)
    else:
        arm = arm_for(d["duel"], args.arms)
        a = decide(d, tick, beta=args.beta, rounds_budget=args.rounds, days_sign=args.days_sign, open_frac=arm)
    log.event("duels", duel=d["duel"], tick=tick, role=d["role"], limit=d["your_limit"], rival=d.get("rival_offer"),
              arm=arm, policy=args.policy, **a)
    if a["action"] == "wait":
        return
    log.say(f"[duel {d['duel']}] {a['action']} {a.get('price', '')} {'' if a.get('days') is None else 'day ' + str(a['days'])}"
            f" · {a['why']} (his U {a.get('u_his')}, next step {a.get('next_step', a.get('exp_step'))}, "
            f"{a.get('left')} left, bot {a.get('kind', '-')}, days: {a.get('w_how')})")
    if args.dry:
        return
    if a["action"] == "accept":
        b.duel_accept(d["duel"])
    elif a["days"] is None:
        b.duel_say(d["duel"], offer_text(a["k"], a["price"], None), price=a["price"])
    else:  # price and days side by side at the top level, as the rules show
        b.call("POST", f"/api/duels/{int(d['duel'])}/messages",
               {"text": offer_text(a["k"], a["price"], a["days"]), "price": int(a["price"]), "days": int(a["days"])})


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--beta", type=float, default=2.0)
    ap.add_argument("--rounds", type=int, default=3, help="exchanges over which we concede to our reserve")
    ap.add_argument("--days-sign", type=int, default=None, choices=(1, -1),
                    help="force the sign of your_days_weight (default: read it from days_meaning, per duel)")
    ap.add_argument("--dry", action="store_true")
    ap.add_argument("--ab", default=None, metavar="A,B",
                    help="split test: opening shares to alternate by duel id, e.g. 0.45,0.25 (share of our limit we ask as "
                         f"surplus; default {OPEN_FRAC} for every duel). Score the result with analyze_duels.py")
    ap.add_argument("--policy", choices=("v1", "v2"), default="v2",
                    help="v2 (default): read the bot, bz/duel.decide2. v1: the Duels I logic, bz/duel.decide")
    ap.add_argument("--open", default=f"{OPEN2['buyer']},{OPEN2['seller']}", metavar="B,S",
                    help="v2 first offer as a share of our limit, buyer,seller (tests/sim_duel2.py)")
    args = ap.parse_args()
    args.arms = [float(x) for x in args.ab.split(",")] if args.ab else [OPEN_FRAC]
    ob, os_ = (float(x) for x in args.open.split(","))
    args.open2 = {"buyer": ob, "seller": os_}
    lock = open(os.path.join(log.LOG_DIR, "duels.lock"), "w")
    try:  # one agent per team: two would talk twice per tick in the same duel
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        sys.exit("another duels.py is already running (logs/duels.lock)")
    b = connect()
    shown = set()
    while True:
        try:
            tick = b.clock()["tick"]
            live = [d for d in b.duels().get("duels", []) if d["status"] == "live"]
            if not live:
                log.say("no live duels left")
                break
            for d in live:
                if d["duel"] not in shown:
                    shown.add(d["duel"])
                    log.say(f"[duel {d['duel']}] {d['role']} {d.get('item')} limit {d['your_limit']} issues {d.get('issues')} "
                            f"days_weight {d.get('your_days_weight')} ({d.get('days_meaning')}) deadline {d['deadline_tick']}")
                try:
                    play(b, d, tick, args)
                except BazaarError as e:
                    log.say(f"[duel {d['duel']}] refused: {e}")
                except Exception as e:  # one odd duel must not stop the others
                    log.say(f"[duel {d.get('duel')}] unexpected {type(e).__name__}: {e}")
            b.wait_tick()
        except Exception as e:  # network or server hiccup: never die mid-session
            log.say(f"duels: {type(e).__name__}: {e}, retrying")
            time.sleep(3)
    for d in b.duels(done=True).get("duels", []):
        log.say(f"[duel {d.get('duel')}] {d.get('role')} limit {d.get('your_limit')}: {d.get('status')} at {d.get('price')} "
                f"after {d.get('rounds')} rounds -> {d.get('result')}")


if __name__ == "__main__":
    main()
