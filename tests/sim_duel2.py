"""Duel simulator calibrated on Duels I (61 duels measured by the dashboard session): compares bz/duel.decide (v1)
with bz/duel.decide2 (read the bot) and tunes the opening. Value = our surplus x (1 - decay) ** rounds, no deal = 0,
and a round counts only when the rival answers one of OUR offers (his solo messages cost nothing).

    python3 tests/sim_duel2.py            # Duels II settings: decay 0.08, 16 ticks
    python3 tests/sim_duel2.py 0.10 12    # Sunday settings

Rival model (assumptions, from the measurements):
  - opens inside our limit in ~45 % of duels (Duels I: 12/25 buying, 9/25 selling)
  - when we are silent, concedes alone with probability p_solo per tick, ~4.2 P a step (Duels I: 89/104, +4.2 P)
  - answers each of our offers the next tick: ~6.0 P step (reciprocal), ~1 P (hard); never past his own limit
  - accepts our offer when it is inside his limit and at least as good for him as his next own price
  - types: self (p_solo 0.85), recip (p_solo 0.5), hard (p_solo 0.15, tiny steps). Mixes are varied below.
"""
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from bz.duel import decide, decide2, surplus  # noqa: E402

TYPES = {"self": (0.85, 6.0), "recip": (0.5, 6.0), "hard": (0.15, 1.0)}


class Rival:
    def __init__(s, role, limit, our_limit, kind, rng):
        s.role, s.limit, s.kind, s.rng = role, limit, kind, rng  # role: HIS role; limit: HIS limit
        s.p_solo, s.step = TYPES[kind]
        if rng.random() < 0.45:  # opens inside our limit: between his limit and ours
            s.price = limit + (our_limit - limit) * rng.uniform(0.3, 0.9)
        else:  # outside: 5-50 % beyond our limit
            s.price = our_limit * (rng.uniform(1.05, 1.5) if role == "seller" else rng.uniform(0.5, 0.95))
        if (role == "seller" and s.price < limit) or (role == "buyer" and s.price > limit):
            s.price = limit

    def move(s, size):
        if s.role == "seller":
            s.price = max(s.limit, s.price - size)
        else:
            s.price = min(s.limit, s.price + size)

    def ok_for_him(s, p):
        return p >= s.limit if s.role == "seller" else p <= s.limit

    def answer(s, ours):
        nxt = s.price - s.step if s.role == "seller" else s.price + s.step
        if s.ok_for_him(ours) and ((s.role == "seller" and ours >= nxt) or (s.role == "buyer" and ours <= nxt)):
            return "accept"
        s.move(s.step * s.rng.uniform(0.5, 1.5))
        return "offer"


def play(policy, role, limit, rival_limit, kind, seed, decay, ticks):
    rng = random.Random(seed)
    rv = Rival("seller" if role == "buyer" else "buyer", rival_limit, limit, kind, rng)
    d = {"role": role, "your_limit": limit, "decay_per_round": decay, "issues": ["price"], "deadline_tick": ticks,
         "messages": [{"tick": 0, "from": "rival", "price": round(rv.price), "days": None}],
         "rival_offer": {"price": round(rv.price), "days": None}}
    rounds, pending = 0, None
    for tick in range(1, ticks):
        if pending is not None:  # he answers our offer of last tick: that is a round
            rounds += 1
            if rv.answer(pending) == "accept":
                return surplus(role, limit, pending) * (1 - decay) ** rounds, rounds
            d["messages"].append({"tick": tick, "from": "rival", "price": round(rv.price), "days": None})
            d["rival_offer"] = {"price": round(rv.price), "days": None}
            pending = None
        elif rng.random() < rv.p_solo:  # he moves alone while we are silent: no round
            rv.move(4.2 * rng.uniform(0.3, 1.7))
            if round(rv.price) != d["rival_offer"]["price"]:
                d["messages"].append({"tick": tick, "from": "rival", "price": round(rv.price), "days": None})
                d["rival_offer"] = {"price": round(rv.price), "days": None}
        a = policy(d, tick)
        if a["action"] == "accept":
            return surplus(role, limit, d["rival_offer"]["price"]) * (1 - decay) ** rounds, rounds
        if a["action"] == "offer":
            d["messages"].append({"tick": tick, "from": "you", "price": a["price"], "days": None})
            pending = a["price"]
    return 0.0, rounds


def cases(n, mix, seed=1):
    rng = random.Random(seed)
    out = []
    for i in range(n):
        role = rng.choice(["buyer", "seller"])
        limit = rng.randint(40, 180)
        pie = rng.uniform(0.05, 0.45) * limit
        rival_limit = limit - pie if role == "buyer" else limit + pie
        kind = rng.choices(list(mix), weights=list(mix.values()))[0]
        out.append((role, limit, rival_limit, kind, i, pie))
    return out


def score(policy, cs, decay, ticks):
    tot, deals, rds = 0.0, 0, 0
    for role, limit, rl, kind, seed, pie in cs:
        v, r = play(policy, role, limit, rl, kind, seed, decay, ticks)
        tot += v / pie
        deals += v > 0
        rds += r
    return tot / len(cs), deals / len(cs), rds / len(cs)


if __name__ == "__main__":
    decay = float(sys.argv[1]) if len(sys.argv) > 1 else 0.08
    ticks = int(sys.argv[2]) if len(sys.argv) > 2 else 16
    mixes = {"measured (self 60/recip 30/hard 10)": {"self": .6, "recip": .3, "hard": .1},
             "more reciprocal (30/50/20)": {"self": .3, "recip": .5, "hard": .2},
             "harder (20/40/40)": {"self": .2, "recip": .4, "hard": .4}}
    policies = {"v1 decide, open 0.45 (Duels I)": lambda d, t: decide(d, t),
                "v1 decide, open 0.25": lambda d, t: decide(d, t, open_frac=0.25)}
    for b in (0.65, 0.70, 0.75, 0.80, 0.85):
        for s_ in (1.20, 1.25, 1.30, 1.35):
            policies[f"v2 open buyer {b:.2f} / seller {s_:.2f}"] = (lambda b, s_: lambda d, t: decide2(d, t, open2={"buyer": b, "seller": s_}))(b, s_)
    print(f"decay {decay}, {ticks} ticks, 600 duels per mix. Columns: share of the pie / deal rate / rounds")
    results = {}
    for mname, mix in mixes.items():
        cs = cases(600, mix)
        for pname, pol in policies.items():
            results.setdefault(pname, []).append(score(pol, cs, decay, ticks))
    print(f"{'policy':38} " + "   ".join(f"{m[:24]:>24}" for m in mixes))
    for pname, rs in sorted(results.items(), key=lambda kv: -kv[1][0][0]):
        print(f"{pname:38} " + "   ".join(f"{a:.3f} / {d_:.0%} / {r:.1f}".rjust(24) for a, d_, r in rs))
