"""Duels: a BOA agent in code. Bidding = Boulware curve over the ticks left, Acceptance = take the rival's offer when
it is inside our limit and at least as good as our next counter (or the deadline is near). The words only ask nicely.

    python3 duels.py            # plays every live duel until none is left
    python3 duels.py --beta 0.5 --dry
"""
import argparse
import time

from agent import connect
from bazaar_sdk import BazaarError
from bz import log

OPEN_FRAC = 0.45  # buyer opens at limit*(1-OPEN_FRAC), seller at limit*(1+OPEN_FRAC)
TEXTS = ["Thank you for meeting me. I can offer {p} P.", "I appreciate your move. {p} P is where I can be.",
         "Let us close quickly: {p} P.", "A step towards you: {p} P.", "I think {p} P is fair for both of us."]


def boulware(start: float, limit: float, t: float, T: float, beta: float) -> int:
    frac = min(1.0, max(0.0, t / max(1.0, T))) ** (1 / beta)
    return round(start + frac * (limit - start))


def play(b, d: dict, tick: int, beta: float, dry: bool, first_tick: dict) -> None:
    buy = d["role"] == "buyer"
    limit = d["your_limit"]
    start = limit * (1 - OPEN_FRAC) if buy else limit * (1 + OPEN_FRAC)
    t0 = first_tick.setdefault(d["duel"], tick)
    T = max(1, d["deadline_tick"] - t0 - 1)  # leave the last tick for a deadline accept
    left = d["deadline_tick"] - tick
    mine = boulware(start, limit, tick - t0 + 1, T, beta)
    rival = (d.get("rival_offer") or {}).get("price")
    inside = rival is not None and (rival <= limit if buy else rival >= limit)
    better_than_next = rival is not None and (rival <= mine if buy else rival >= mine)
    log.event("duels", duel=d["duel"], tick=tick, role=d["role"], limit=limit, rival=rival, mine=mine, left=left)
    if inside and (better_than_next or left <= 2):
        log.say(f"[duel {d['duel']}] {d['role']} limit {limit}: accept rival {rival} (next counter {mine}, {left} left)")
        if not dry:
            b.duel_accept(d["duel"])
        return
    if (d.get("your_offer") or {}).get("price") == mine:
        mine += 1 if buy else -1  # never the same price twice
        if (mine > limit) if buy else (mine < limit):
            return
    log.say(f"[duel {d['duel']}] {d['role']} limit {limit}: rival {rival} -> we offer {mine} ({left} ticks left)")
    if not dry:
        b.duel_say(d["duel"], TEXTS[(tick - t0) % len(TEXTS)].format(p=mine), price=mine)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--beta", type=float, default=0.5)
    ap.add_argument("--dry", action="store_true")
    args = ap.parse_args()
    b = connect()
    first_tick: dict = {}
    while True:
        try:
            tick = b.clock()["tick"]
            live = [d for d in b.duels().get("duels", []) if d["status"] == "live"]
            if not live:
                log.say("no live duels left")
                break
            for d in live:
                if "days" in (d.get("issues") or []):
                    log.say(f"[duel {d['duel']}] multi-issue (days) not supported yet: skipped")
                    continue
                try:
                    play(b, d, tick, args.beta, args.dry, first_tick)
                except BazaarError as e:
                    log.say(f"[duel {d['duel']}] refused: {e}")
            b.wait_tick()
        except BazaarError as e:
            log.say(f"duels: {e}, retrying")
            time.sleep(3)
    for d in b.duels(done=True).get("duels", []):
        log.say(f"[duel {d['duel']}] {d['role']} limit {d['your_limit']}: {d.get('result')} at {d.get('price')}")


if __name__ == "__main__":
    main()
