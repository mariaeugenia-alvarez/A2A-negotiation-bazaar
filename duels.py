"""Duels agent: every decision comes from bz/duel.py (code decides), the words only carry it politely.

    python3 duels.py                         # plays every live duel until none is left (v2, approved by Thameur on Saturday)
    python3 duels.py --dry                   # prints the decisions, sends nothing
    python3 duels.py --duel-ticks 12         # Sunday: duels last 12 ticks
    python3 duels.py --policy v1             # FALLBACK: the Duels I logic
    Run it through the supervisor, on ONE machine only (Thameur's): python3 duels_watch.py

v2 (bz/duel.decide2, the waiting strategy approved by Thameur): tick 0 we send nothing; if the rival is still silent at
tick 1 we open at 0.75 x our limit (buyer) / 1.30 x (seller), then go quiet and re-read him. A self-conceder is left to
come to us; we take his best in-limit offer when he has not moved for 2 ticks, or at deadline - 2. A reciprocal rival
gets real steps, at most 2 counters, and we accept when one more round cannot beat the decay. Our limit is never
crossed. Days are sent with every offer; leaning toward our side is a hypothesis, his day asks are logged.
The rival's moves are measured in OUR TOTAL VALUE U = price surplus + w x day (read_bot): a rival who holds his price and
moves the day toward us is conceding; one who improves the price but moves the day against us is judged on the net.

SAFETY SWITCH (replaces the old 70 % rule): restart with --policy v1 only if
  1. at least 2 AVOIDABLE no-deals: the duel ended with no deal although the rival made at least one offer inside our
     limit with U >= 1 (silent rivals and rivals that never came inside our limit do not count), or
  2. this agent stops or crashes and duels_watch.py cannot restart it.
Check with:   python3 analyze_duels.py --since <first duel id of the session>   (prints the avoidable no-deals).

Texts: one per situation (opening, counter, last call), Spanish and English, short, always with the price and, when the
duel has days, the day. They never state our limit or our weight, and never say "last" or "final" except the last call.
Words never change a price or a day.
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

TEXTS = {  # (stage, has_day) -> text; {p} price, {d} day. Spanish / English.
    ("opening", True): "Rápido y justo: {p} P, día {d}. ¿Qué día de entrega te va mejor? / "
                       "Quick and fair: {p} P, day {d}. Which delivery day suits you best?",
    ("counter", True): "Parece que el día te importa: {p} P con día {d}. / It seems the day matters to you: {p} P, day {d}.",
    ("last_call", True): "Mi mejor oferta: {p} P, día {d}. / My best offer: {p} P, day {d}.",
    ("opening", False): "Rápido y justo: {p} P. / Quick and fair: {p} P.",
    ("counter", False): "Parece que cerrar rápido te importa: {p} P. / It seems closing fast matters to you: {p} P.",
    ("last_call", False): "Mi mejor oferta: {p} P. / My best offer: {p} P.",
}


def offer_text(stage: str, price: int, days=None) -> str:
    """The words for one offer. The price (and the day, when there is one) are always in the text."""
    return TEXTS[(stage if (stage, days is not None) in TEXTS else "counter", days is not None)].format(p=int(price), d=days)


def stage_of(a: dict) -> str:
    """v2 names the stage of each offer; v1 does not: its first offer is the opening, the rest are counters."""
    return a.get("stage") or ("opening" if not a.get("k") else "counter")


def arm_for(duel_id, arms: list) -> float:
    """Split test: each duel always gets the same arm (by its id), so the opening never changes mid-duel."""
    return arms[int(duel_id) % len(arms)]


def play(b, d: dict, tick: int, args) -> None:
    if args.policy == "v2":  # read the bot (doctrine approved 13:35): every decision, waits included, is logged
        arm = f"v2 {args.open2['buyer']}/{args.open2['seller']}"
        a = decide2({**d, "_start": d["deadline_tick"] - args.duel_ticks}, tick, open2=args.open2, days_sign=args.days_sign)
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
        b.duel_say(d["duel"], offer_text(stage_of(a), a["price"], None), price=a["price"])
    else:  # price and days side by side at the top level, as the rules show
        b.call("POST", f"/api/duels/{int(d['duel'])}/messages",
               {"text": offer_text(stage_of(a), a["price"], a["days"]), "price": int(a["price"]), "days": int(a["days"])})


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
                    help="v2 (default, approved): read the bot, bz/duel.decide2. v1: the Duels I logic, the fallback")
    ap.add_argument("--duel-ticks", type=int, default=16, help="duel length: 16 for Duels II, 12 on Sunday")
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
