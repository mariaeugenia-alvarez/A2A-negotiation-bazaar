"""Duel simulator: our bz/duel.decide against rivals like the ones seen in practice, measured as the server does
(value = our surplus x (1 - decay) ** rounds, no deal = 0).

    python3 tests/sim_duel.py
"""
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from bz.duel import decide, surplus  # noqa: E402


class Rival:
    """kind: 'recip' mirrors our step (x gain), 'boulware' barely moves until late, 'conceder' moves fast.
    Opens at open_frac beyond his own limit, accepts when our offer is within `accept_gap` of his next move."""
    def __init__(s, role, limit, kind, rng):
        s.role, s.limit, s.kind, s.rng = role, limit, kind, rng  # role: HIS role
        s.price = limit * (1.5 if role == "seller" else 0.5)
        s.k, s.last_ours = 0, None

    def good(s, p):  # our price inside his limit
        return p >= s.limit if s.role == "seller" else p <= s.limit

    def respond(s, ours, ticks_left, T):
        s.k += 1
        if s.good(ours) and abs(ours - s.price) <= max(2, 0.04 * s.limit):
            return "accept"
        room = abs(s.price - s.limit)
        if s.kind == "recip":
            step = abs(ours - s.last_ours) * s.rng.uniform(1.0, 2.0) if s.last_ours is not None else room * 0.1
        elif s.kind == "boulware":
            step = room * (0.05 if ticks_left > 3 else 0.5)
        else:
            step = room * 0.3
        step = min(room, max(1, step))
        s.price += -step if s.role == "seller" else step
        s.last_ours = ours
        if s.good(ours) and ((s.role == "seller" and ours >= s.price) or (s.role == "buyer" and ours <= s.price)):
            return "accept"
        return "offer"


def v0(d, tick):
    """The practice agent: Boulware beta 0.5 from 45 % away to our limit over the ticks left."""
    buy = d["role"] == "buyer"
    limit = d["your_limit"]
    start = limit * (0.55 if buy else 1.45)
    t0 = d["_t0"]
    T = max(1, d["deadline_tick"] - t0 - 1)
    frac = min(1.0, (tick - t0 + 1) / T) ** 2
    mine = round(start + frac * (limit - start))
    r = (d.get("rival_offer") or {}).get("price")
    if r is not None and (r <= limit if buy else r >= limit) and ((r <= mine if buy else r >= mine)
                                                                  or d["deadline_tick"] - tick <= 2):
        return {"action": "accept"}
    return {"action": "offer", "price": mine, "days": None}


def play(policy, role, limit, rival_limit, kind, seed, decay=0.06, ticks=16):
    rng = random.Random(seed)
    rv = Rival("seller" if role == "buyer" else "buyer", rival_limit, kind, rng)
    d = {"role": role, "your_limit": limit, "decay_per_round": decay, "issues": ["price"], "deadline_tick": ticks,
         "messages": [{"tick": 0, "from": "rival", "price": round(rv.price), "days": None}],
         "rival_offer": {"price": round(rv.price)}, "_t0": 0}
    rounds = 0
    for tick in range(ticks):
        a = policy(d, tick)
        if a["action"] == "accept":
            return surplus(role, limit, d["rival_offer"]["price"]) * (1 - decay) ** rounds, rounds
        if a["action"] == "wait":
            continue
        d["messages"].append({"tick": tick, "from": "you", "price": a["price"], "days": None})
        rounds += 1
        res = rv.respond(a["price"], ticks - tick, ticks)
        if res == "accept":
            return surplus(role, limit, a["price"]) * (1 - decay) ** rounds, rounds
        d["messages"].append({"tick": tick, "from": "rival", "price": round(rv.price), "days": None})
        d["rival_offer"] = {"price": round(rv.price)}
    return 0.0, rounds


if __name__ == "__main__":
    policies = {"v0": v0}
    for R in (3, 4, 6):
        for beta in (0.7, 1.0, 2.0):
            policies[f"v1 R={R} b={beta}"] = (lambda R, beta: lambda d, t: decide(d, t, beta=beta, rounds_budget=R))(R, beta)
    rng = random.Random(1)
    cases = []
    for i in range(400):
        role = rng.choice(["buyer", "seller"])
        limit = rng.randint(50, 180)
        pie = rng.uniform(0.05, 0.5) * limit
        rival_limit = limit - pie if role == "buyer" else limit + pie
        cases.append((role, limit, rival_limit, rng.choice(["recip", "recip", "boulware", "conceder"]), i, pie))
    print(f"{'policy':18} {'share of pie':>12} {'deal %':>7} {'rounds':>7}   by rival: recip / boulware / conceder")
    for name, pol in policies.items():
        tot, deals, rds, by = 0.0, 0, 0, {}
        for role, limit, rl, kind, seed, pie in cases:
            v, r = play(pol, role, limit, rl, kind, seed)
            share = v / pie
            tot += share
            deals += v > 0
            rds += r
            by.setdefault(kind, []).append(share)
        kinds = " / ".join(f"{sum(by[k]) / len(by[k]):.2f}" for k in ("recip", "boulware", "conceder"))
        print(f"{name:18} {tot / len(cases):12.2f} {100 * deals / len(cases):6.0f}% {rds / len(cases):7.1f}   {kinds}")
