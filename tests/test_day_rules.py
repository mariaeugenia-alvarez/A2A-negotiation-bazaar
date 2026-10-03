"""Duels III day rules (bz/duel.py decide2 day_rules): best_open, hold, lc_ours.

  1. day_rules OFF is exactly the Duels II code (tests/duel_d2_frozen.py, a copy of bz/duel.py as it played Duels II)
  2. the hard rules hold with the rules ON: price never outside our limit, every offer worth >= 1 to us, days 0..10
  3. each rule does what it says: opening at our best day, no day move in a counter, last call keeps our day
"""
import importlib.util
import os
import random
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
from bz.duel import DAY_RULES_D3, _u, decide2, inside  # noqa: E402

spec = importlib.util.spec_from_file_location("d2", os.path.join(HERE, "tests", "duel_d2_frozen.py"))
d2 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(d2)

MEANING = {1: "each delivery day adds this much cash to your side", -1: "each delivery day costs you this much cash"}


def random_duel(r, two=True):
    role = r.choice(["buyer", "seller"])
    L = r.randint(20, 220)
    sign = r.choice([1, -1])
    wv = round(r.uniform(0.1, 8), 2)
    ms, t = [], 100
    for k in range(r.randint(0, 6)):
        if r.random() < 0.5:
            ms.append({"tick": t + k, "from": "you", "price": int(L * r.uniform(0.6, 1.4)), "days": r.randint(0, 10) if two else None})
        ms.append({"tick": t + k, "from": "Rival", "price": int(L * r.uniform(0.5, 1.7)), "days": r.randint(0, 10) if two else None})
    ro = {"price": ms[-1]["price"], "days": ms[-1]["days"]} if ms and ms[-1]["from"] != "you" else None
    d = {"duel": 1, "role": role, "your_limit": L, "issues": ["price", "days"] if two else ["price"],
         "your_days_weight": wv if two else None, "days_meaning": MEANING[sign] if two else None, "decay_per_round": 0.1,
         "deadline_tick": 112, "messages": ms, "rival_offer": ro, "_start": 100}
    return d, r.randint(min(100 + len(ms), 111), 111), sign * wv if two else 0.0


def check(name, ok):
    assert ok, name
    check.n += 1


check.n = 0


def test_off_is_duels_ii():
    r = random.Random(1)
    for i in range(6000):
        d, t, _ = random_duel(r, two=i % 3 != 0)
        a, b = decide2(d, t), d2.decide2(d, t)
        check(f"off == Duels II code (duel {i})", a == b)


def test_hard_rules_on():
    r = random.Random(2)
    offers = 0
    for i in range(8000):
        d, t, w = random_duel(r)
        a = decide2(d, t, day_rules=DAY_RULES_D3)
        if a["action"] == "offer":
            offers += 1
            L, role = float(d["your_limit"]), d["role"]
            check("price inside our limit", inside(role, L, a["price"]))
            check("offer worth >= 1 to us", _u(role, L, w, a["price"], a["days"]) >= 1 - 1e-9)
            check("day 0..10", 0 <= a["days"] <= 10)
        if a["action"] == "accept":
            ro = d["rival_offer"]
            check("accept inside our limit and worth >= 1", ro and inside(d["role"], float(d["your_limit"]), ro["price"])
                  and _u(d["role"], float(d["your_limit"]), w, ro["price"], ro["days"]) >= 1 - 1e-9)
    check("enough offers tested", offers > 1500)


def test_each_rule():
    r = random.Random(3)
    seen = {"opening": 0, "counter": 0, "last_call": 0}
    for i in range(20000):
        d, t, w = random_duel(r)
        a = decide2(d, t, day_rules=DAY_RULES_D3)
        if a["action"] != "offer":
            continue
        ours = [m for m in d["messages"] if m["from"] == "you"]
        st = a.get("stage")
        seen[st] = seen.get(st, 0) + 1
        if st == "opening":
            check("opening at our best day", a["days"] == (10 if w > 0 else 0) or
                  _u(d["role"], float(d["your_limit"]), w, a["price"], 10 if w > 0 else 0) < 1)
        if st == "counter":
            check("counter keeps our day", a["days"] == ours[-1]["days"] or
                  _u(d["role"], float(d["your_limit"]), w, a["price"], ours[-1]["days"]) < 1)
        if st == "last_call":
            check("last call keeps our day when it is worth >= 1 there", a["days"] == ours[-1]["days"] or
                  _u(d["role"], float(d["your_limit"]), w, a["price"], ours[-1]["days"]) < 1)
    check("each stage tested", all(v > 50 for v in seen.values()))


def test_fixed_examples():
    # buyer, limit 100, a day costs 2: we opened 65 at day 0 (best_open), he asks 140 at day 10 -> the counter keeps day 0
    d = {"duel": 1, "role": "buyer", "your_limit": 100, "issues": ["price", "days"], "your_days_weight": 2.0,
         "days_meaning": MEANING[-1], "decay_per_round": 0.1, "deadline_tick": 112, "_start": 100,
         "messages": [{"tick": 101, "from": "you", "price": 75, "days": 0}, {"tick": 102, "from": "Rival", "price": 140, "days": 10}],
         "rival_offer": {"price": 140, "days": 10}}
    a = decide2(d, 103, day_rules=DAY_RULES_D3)
    check("example counter: offer", a["action"] == "offer")
    check("example counter: day kept at 0", a["days"] == 0)
    check("example counter: price conceded toward him", 75 < a["price"] <= 100)
    b = decide2(d, 103)
    check("example counter: Duels II code moves the day", b["action"] == "offer" and b["days"] != 0)
    # opening: seller, a day adds value -> day 10
    e = {**d, "role": "seller", "days_meaning": MEANING[1], "messages": [], "rival_offer": None}
    o = decide2(e, 101, day_rules=DAY_RULES_D3)
    check("example opening: seller opens at day 10", o["action"] == "offer" and o["days"] == 10)


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
    print(f"test_day_rules: {check.n} checks passed")
