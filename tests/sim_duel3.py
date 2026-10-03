"""Day-aware duel simulator, calibrated on the 68 duels of Duels II (Saturday): price AND delivery day.

    python3 tests/sim_duel3.py              # validate on Duels II, then compare the A1-A5 variants on Duels II settings
    python3 tests/sim_duel3.py 0.10 12      # compare the variants on Sunday settings (decay 10 %, 12 ticks)

Our side: the 68 real Duels II scenarios (role, our limit, our signed day weight, read from logs/duels/).
Rival model, every number measured on Duels II (logs/duels/, logs/duels.jsonl):
  - silent the whole duel: 6 of 68
  - speaks first at tick 0 in about half of the duels where he speaks (33 of 62); otherwise he answers our opening
  - first day asked: OUR worst end in 44 of 56, day 5 in 6 of 56, another day otherwise
  - never changes his day in 39 of 56 duels ("fixed"); the 17 "traders" move it toward us for 1 to 4.5 P per day
  - price behaviour per kind as in tests/sim_duel2.py (self / recip / hard), with the Duels II kind mix
  - he accepts our package when it is inside his price limit and worth at least his own next offer TO HIM, at his day
    weight. Fixed rivals weigh a day lightly (they accepted our day 5+ days from theirs in 17 of 27 accepted packages)
Validation: the code that played Duels II (bz/duel.decide2 as it is) must reproduce Duels II before any variant is
compared. The calibration constants below were fitted on that, and only on that.
Variants are wrappers here; bz/duel.py is not changed.
"""
import collections
import copy
import glob
import json
import os
import random
import statistics as st
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
from bz.duel import _u, decide2, package_counter, surplus  # noqa: E402

# ---------------------------------------------------------------- calibration (fitted on Duels II, see validate())
P_SILENT = 6 / 68          # rival never speaks
P_FIRST = 33 / 62          # rival speaks first, among rivals who speak
P_TRADER = 17 / 56         # rival moves his day at some point
P_OPPOSITE = 44 / 56       # rival asks our worst end
P_FIVE = 6 / 56            # rival asks day 5
KIND_MIX = {"self": 0.30, "recip": 0.58, "hard": 0.12}   # fitted: Duels II classes self 18 / recip 25 / hard 3
STEP = {"self": (0.85, 6.0), "recip": (0.25, 9.0), "hard": (0.10, 1.5)}  # (p of a solo move per tick, answer step)
PIE = (0.30, 0.80)         # fitted: rival limit = ours -/+ PIE x our limit
FIXED_W = (0.0, 1.0)       # fitted: a fixed rival's day weight (P per day), uniform
TRADER_W = (1.0, 4.5)      # measured: the price traders asked per day moved
P_DAY_MOVE = 0.90          # fitted: a trader moves his day when he answers us
END_ACCEPT = 3             # measured: 9 of the 27 offers of ours he accepted were sent with 2-3 ticks left: near the
                           # deadline he takes any package inside his price limit that is worth >= 0 to him (no deal = 0)
P_INSIDE = 0.60            # fitted: he opens inside our price limit
MEANING = {1: "each delivery day adds this much cash to your side", -1: "each delivery day costs you this much cash"}


def real_scenarios():
    out = []
    for f in sorted(glob.glob(os.path.join(HERE, "logs", "duels", "*.json"))):
        d = json.load(open(f))
        if d.get("session", 0) < 3 or d.get("status") not in ("deal", "no_deal") or not d.get("your_days_weight"):
            continue
        sign = 1 if "adds" in (d.get("days_meaning") or "") else -1
        out.append({"id": d["duel"], "role": d["role"], "limit": float(d["your_limit"]), "w": sign * float(d["your_days_weight"])})
    return out


class Rival:
    def __init__(s, sc, rng):
        s.rng = rng
        role = sc["role"]
        s.role = "seller" if role == "buyer" else "buyer"
        L = sc["limit"]
        pie = rng.uniform(*PIE) * L
        s.limit = L - pie if role == "buyer" else L + pie          # his price limit
        s.kind = rng.choices(list(KIND_MIX), weights=list(KIND_MIX.values()))[0]
        s.p_solo, s.step = STEP[s.kind]
        s.silent = rng.random() < P_SILENT
        s.first = rng.random() < P_FIRST
        our_best = 10 if sc["w"] > 0 else 0
        r = rng.random()
        s.day = (10 - our_best) if r < P_OPPOSITE else 5 if r < P_OPPOSITE + P_FIVE else rng.randint(0, 10)
        s.pref = s.day                                               # his good end
        s.trader = rng.random() < P_TRADER
        s.wd = rng.uniform(*(TRADER_W if s.trader else FIXED_W))    # what one day toward HIS end is worth to him
        if rng.random() < P_INSIDE:  # opens inside our limit, else 5-50 % beyond it
            s.price = s.limit + (L - s.limit) * rng.uniform(0.3, 0.9)
        else:
            s.price = L * (rng.uniform(1.05, 1.5) if s.role == "seller" else rng.uniform(0.5, 0.95))
        s.price = max(s.price, s.limit) if s.role == "seller" else min(s.price, s.limit)
        s.moved_days = 0

    def his_u(s, price, day):
        ps = (price - s.limit) if s.role == "seller" else (s.limit - price)
        return ps - s.wd * abs(day - s.pref)

    def move_price(s, size):
        s.price = max(s.limit, s.price - size) if s.role == "seller" else min(s.limit, s.price + size)

    def answer(s, price, day, left=99):
        nxt = s.price - s.step if s.role == "seller" else s.price + s.step
        inside = price >= s.limit if s.role == "seller" else price <= s.limit
        if inside and s.his_u(price, day) >= s.his_u(nxt, s.day) - 1e-9:
            return "accept"
        if inside and left <= END_ACCEPT and s.his_u(price, day) >= 0:
            return "accept"
        if s.trader and s.day != day and s.rng.random() < P_DAY_MOVE:   # a trader gives days, and takes price back
            k = min(abs(s.day - day), s.rng.randint(3, 10))
            s.day += k if day > s.day else -k
            back = s.wd * k
            s.price = s.price + back if s.role == "seller" else s.price - back
            s.moved_days += k
        else:
            s.move_price(s.step * s.rng.uniform(0.5, 1.5))
        return "offer"


def play(policy, sc, seed, decay, ticks):
    """One duel. Returns a dict: result, deal, rounds, final day, his first day, who closed, our day moves and his replies."""
    rng = random.Random(seed)
    rv = Rival(sc, rng)
    role, L, w = sc["role"], sc["limit"], sc["w"]
    d = {"duel": 1, "role": role, "your_limit": L, "decay_per_round": decay, "issues": ["price", "days"], "deadline_tick": ticks,
         "your_days_weight": abs(w), "days_meaning": MEANING[1 if w > 0 else -1], "messages": [], "rival_offer": None, "_start": 0}
    his_first = rv.day
    rec = {"rounds": 0, "deal": False, "result": 0.0, "his_first": his_first, "by": None, "day": None, "our_moves": 0, "replied": 0}

    def his_msg(tick):
        p, dd = round(rv.price), rv.day
        d["messages"].append({"tick": tick, "from": "rival", "price": p, "days": dd})
        d["rival_offer"] = {"price": p, "days": dd}

    if not rv.silent and rv.first:
        his_msg(0)
    pending, last_ours_day, move_tick = None, None, None
    for tick in range(0, ticks):
        if pending is not None and not rv.silent:   # he answers our offer of last tick: a round
            rec["rounds"] += 1
            day_before = rv.day
            if rv.answer(*pending, left=ticks - tick) == "accept":
                u = _u(role, L, w, pending[0], pending[1])
                rec.update(deal=True, result=u * (1 - decay) ** rec["rounds"], by="ours", day=pending[1])
                return rec
            if move_tick is not None:
                rec["replied"] += rv.day != day_before
                move_tick = None
            his_msg(tick)
            pending = None
        elif not rv.silent and d["rival_offer"] is not None and rng.random() < rv.p_solo:  # he concedes alone: no round
            rv.move_price(4.2 * rng.uniform(0.3, 1.7))
            if round(rv.price) != d["rival_offer"]["price"]:
                his_msg(tick)
        if tick == 0:
            continue
        a = policy(d, tick)
        if a["action"] == "accept" and d["rival_offer"] is not None:
            p, dd = d["rival_offer"]["price"], d["rival_offer"]["days"]
            u = _u(role, L, w, p, dd)
            rec.update(deal=True, result=u * (1 - decay) ** rec["rounds"], by="his", day=dd)
            return rec
        if a["action"] == "offer":
            if last_ours_day is not None and a["days"] != last_ours_day:
                rec["our_moves"] += 1
                move_tick = tick
            last_ours_day = a["days"]
            d["messages"].append({"tick": tick, "from": "you", "price": a["price"], "days": a["days"]})
            pending = (a["price"], a["days"])
    return rec


def run(policy, scs, decay, ticks, reps):
    rows = []
    for i, sc in enumerate(scs):
        for k in range(reps):
            r = play(policy, sc, 1000 * i + k, decay, ticks)
            r["role"] = sc["role"]
            rows.append(r)
    deals = [r for r in rows if r["deal"]]
    m = lambda xs: st.mean(xs) if xs else 0.0
    return {"deal_rate": len(deals) / len(rows), "per_deal": m([r["result"] for r in deals]),
            "per_duel": m([r["result"] for r in rows]),
            "buyer": m([r["result"] for r in deals if r["role"] == "buyer"]), "seller": m([r["result"] for r in deals if r["role"] == "seller"]),
            "his_day": m([r["day"] == r["his_first"] for r in deals]), "by_ours": m([r["by"] == "ours" for r in deals]),
            "rounds": m([r["rounds"] for r in deals]),
            "reply": sum(r["replied"] for r in rows) / max(1, sum(r["our_moves"] for r in rows)),
            "negative": sum(r["result"] < 0 for r in rows)}


REAL = {"deal_rate": 60 / 68, "per_deal": 18.4, "per_duel": 1103.4 / 68, "buyer": 12.5, "seller": 24.3, "his_day": 29 / 60,
        "by_ours": 27 / 60, "rounds": 1.4, "reply": 8 / 25, "negative": 0}


# ---------------------------------------------------------------- the variants (wrappers; bz/duel.py unchanged)

def best_day(w):
    return 10 if w > 0 else 0


def wrap(open2=None, a1=False, a2=False, a3=False):
    """decide2 plus: A5 open2 = first offer share; A1 open with our best day (same price, so bolder); A2 never move our
    day toward his before he moved his toward ours; A3 'mirror': move ours by at most the days he moved toward ours."""
    def pol(d, tick):
        a = decide2(d, tick, open2=open2)
        if a["action"] != "offer":
            return a
        w = a["w"]
        if w == 0:
            return a
        ours = [m for m in d["messages"] if m["from"] == "you"]
        his = [m for m in d["messages"] if m["from"] != "you"]
        if a1 and a.get("stage") == "opening":
            return {**a, "days": best_day(w)}
        if (a2 or a3) and a.get("stage") == "counter" and ours and his:
            last = (ours[-1]["price"], ours[-1]["days"])
            pref = best_day(w)
            # how many days he moved toward our best end since his first offer
            his_move = max(0, abs(his[0]["days"] - pref) - abs(his[-1]["days"] - pref))
            our_given = abs(last[1] - ours[0]["days"])
            allowed = (his_move - our_given) if a3 else (10 if his_move > 0 else 0)
            if abs(a["days"] - last[1]) > max(0, allowed):
                # allowed day toward his: at most `allowed` more days; price from the package rule at that day
                hd = his[-1]["days"]
                k = max(0, allowed)
                tgt = last[1] + (k if hd > last[1] else -k) if hd != last[1] else last[1]
                pk = package_counter(d["role"], float(d["your_limit"]), w, last, (his[-1]["price"], tgt))
                if pk is None:
                    return {"action": "wait", "why": "A2/A3: no price-only step fits", **{k_: v for k_, v in a.items() if k_ not in ("action", "why", "price", "days")}}
                return {**a, "price": pk["price"], "days": pk["day"]}
        return a
    return pol


def validate(reps=30):
    scs = real_scenarios()
    sim = run(wrap(), scs, 0.08, 16, reps)
    print(f"VALIDATION on the {len(scs)} real Duels II scenarios x {reps} rivals each (code as played, decay 8 %, 16 ticks)")
    print(f"{'measure':34} {'Duels II (real)':>16} {'simulator':>10}")
    names = {"deal_rate": "deal rate", "per_deal": "points per deal", "per_duel": "points per duel", "buyer": "  per deal when we buy",
             "seller": "  per deal when we sell", "his_day": "deals on HIS first day", "by_ours": "deals = he took OUR package",
             "rounds": "rounds per deal", "reply": "he moved his day after ours", "negative": "deals with U < 0"}
    for k, n in names.items():
        fmt = (lambda x: f"{x:.0%}") if k in ("deal_rate", "his_day", "by_ours", "reply") else (lambda x: f"{x:.1f}")
        print(f"{n:34} {fmt(REAL[k]):>16} {fmt(sim[k]):>10}")
    return sim


def compare(decay, ticks, reps=30):
    scs = real_scenarios()
    variants = {
        "now (as played in Duels II)": wrap(),
        "A5 first offer 0.65 / 1.50": wrap(open2={"buyer": 0.65, "seller": 1.50}),
        "A5 first offer 0.65 / 1.40": wrap(open2={"buyer": 0.65, "seller": 1.40}),
        "A1 open with our best day": wrap(a1=True),
        "A2 no day move before his": wrap(a2=True),
        "A3 mirror his day moves": wrap(a3=True),
        "A1 + A3": wrap(a1=True, a3=True),
        "A1 + A3 + A5 (0.65/1.50)": wrap(open2={"buyer": 0.65, "seller": 1.50}, a1=True, a3=True),
        "A1 + A2 + A5 (0.65/1.50)": wrap(open2={"buyer": 0.65, "seller": 1.50}, a1=True, a2=True),
    }
    print(f"\nCOMPARISON, decay {decay:.0%}, {ticks} ticks, {len(scs)} scenarios x {reps} rivals. Points per DUEL is the number that counts")
    print(f"{'variant':32} {'pts/duel':>9} {'deals':>6} {'pts/deal':>9} {'buy':>6} {'sell':>6} {'rounds':>7} {'U<0':>4}")
    base = None
    for n, pol in variants.items():
        r = run(pol, scs, decay, ticks, reps)
        base = base or r["per_duel"]
        print(f"{n:32} {r['per_duel']:9.2f} {r['deal_rate']:6.0%} {r['per_deal']:9.1f} {r['buyer']:6.1f} {r['seller']:6.1f} {r['rounds']:7.1f} {r['negative']:4d}"
              f"   ({(r['per_duel'] / base - 1):+.0%})")


if __name__ == "__main__":
    decay = float(sys.argv[1]) if len(sys.argv) > 1 else 0.08
    ticks = int(sys.argv[2]) if len(sys.argv) > 2 else 16
    validate()
    compare(decay, ticks)
