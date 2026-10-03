"""bz/duel.decide2 (read the bot): hard rules on random cases, and the Duels I situations. python3 tests/test_duel2.py"""
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from bz.duel import decide2, inside, read_bot  # noqa: E402


def duel(role, limit, msgs, rival=None, deadline=520, decay=0.08, issues=("price",), w=None, meaning=None):
    return {"role": role, "your_limit": limit, "messages": msgs, "rival_offer": rival, "deadline_tick": deadline,
            "decay_per_round": decay, "issues": list(issues), "your_days_weight": w, "days_meaning": meaning}


def m(t, who, p, days=None):
    return {"tick": t, "from": who, "price": p, "days": days}


checks = 0
# 1. hard rules on random duels: never an offer past our limit, never accept outside it, days 0-10, price >= 1
rng = random.Random(7)
for seed in range(4000):
    role = rng.choice(["buyer", "seller"])
    limit = rng.randint(20, 200)
    two = rng.random() < 0.4
    msgs, t = [], 500
    for _ in range(rng.randint(0, 7)):
        who = rng.choice(["R", "R", "you"])
        msgs.append(m(t, who, round(limit * rng.uniform(0.4, 1.6)), rng.randint(0, 10) if two else None))
        t += rng.choice([0, 1, 1, 2])
    his = [x for x in msgs if x["from"] != "you"]
    rival = {"price": his[-1]["price"], "days": his[-1]["days"]} if his else None
    d = duel(role, limit, msgs, rival, deadline=t + rng.randint(0, 14), issues=("price", "days") if two else ("price",),
             w=rng.uniform(0.2, 2) if two else None, meaning=rng.choice(["gain per day", "cost per day"]))
    a = decide2(d, t)
    if a["action"] == "offer":
        assert inside(role, limit, a["price"]) and a["price"] >= 1, (a, d)
        assert not two or (a["days"] is not None and 0 <= a["days"] <= 10), (a, d)
    if a["action"] == "accept":
        assert rival and inside(role, limit, rival["price"]), (a, d)
checks += 1

# 2. 2362 (Duels I, unanswered): buyer limit 148, he offered 149 then 129 after our 80. Inside with a good surplus
#    after our counter: accept (Duels I said nothing for 15 ticks and got 0).
d = duel("buyer", 148, [m(502, "R", 149), m(503, "you", 80), m(504, "R", 129)], {"price": 129, "days": None}, deadline=519)
a = decide2(d, 506)
assert a["action"] == "accept", a; checks += 1
# 3. 2485 (unanswered): seller cost 85, he climbs alone 53, 54, 55 ... while we are silent: stay silent, he comes to us
d = duel("seller", 85, [m(526, "R", 53), m(527, "R", 58), m(528, "R", 64), m(529, "R", 70)], {"price": 70, "days": None},
         deadline=542)
a = decide2(d, 530)
assert a["action"] == "wait" and "self-conceder" in a["why"] and read_bot(d)["kind"] == "self", a; checks += 1
#    ... and once he is inside and his steps stop, take it
d = duel("seller", 85, [m(526, "R", 53), m(528, "R", 90), m(530, "R", 106), m(531, "R", 106)], {"price": 106, "days": None},
         deadline=542)
a = decide2(d, 534)
assert a["action"] == "accept", a; checks += 1
# 4. 2317 (silence on both sides): we open, at 0.75 of our buyer limit
d = duel("buyer", 128, [], None, deadline=525)
a = decide2(d, 512)
assert a["action"] == "offer" and a["price"] == 96, a; checks += 1
#    a rival who has said nothing by tick 1-2 never makes us wait: some never open (2317, 2380, 2381 scored 0)
for t_now in (501, 502):
    a = decide2(duel("seller", 60, [], None, deadline=516), t_now)
    assert a["action"] == "offer" and a["price"] == 78, a
checks += 1
# 5. 2549: he opens inside with a big surplus (125 vs our cost 92): watch his first moves, then counter once
d = duel("seller", 92, [m(569, "R", 125)], {"price": 125, "days": None}, deadline=585)
assert decide2(d, 570)["action"] == "wait"
a = decide2(d, 572)
assert a["action"] == "offer" and a["price"] >= 126, a; checks += 2
# 6. an in-limit offer with fewer than 3 ticks left is always taken
d = duel("buyer", 100, [m(500, "R", 140), m(501, "you", 75), m(502, "R", 99)], {"price": 99, "days": None}, deadline=505)
assert decide2(d, 503)["action"] == "accept"; checks += 1
# 7. a hard bot that never comes inside: two real counters, then no deal is fine
d = duel("buyer", 100, [m(500, "R", 160), m(501, "you", 75), m(502, "R", 159), m(503, "you", 89), m(504, "R", 159)],
         {"price": 159, "days": None}, deadline=520)
a = decide2(d, 505)
assert a["action"] == "wait" and read_bot(d)["kind"] == "hard", a; checks += 1
# 8. two issues: always a day with a price; the day leans toward our side but is not forced to 0 or 10
d = duel("buyer", 100, [m(500, "R", 160, 4)], {"price": 160, "days": 4}, deadline=520, issues=("price", "days"), w=1.0,
         meaning="your gain per day of delivery")
a = decide2(d, 503)
assert a["action"] == "offer" and a["days"] == 8, a; checks += 1   # opening day: halfway between 5 and our end (10), half up
# 9. approved by Thameur: tick 0 we send nothing even if he is silent; from tick 1 we open
assert decide2(duel("seller", 60, [], None, deadline=516), 500)["action"] == "wait"      # start = 516 - 16 = 500
assert decide2({**duel("seller", 60, [], None, deadline=512), "_start": 500}, 500)["action"] == "wait"   # Sunday, 12 ticks
assert decide2({**duel("seller", 60, [], None, deadline=512), "_start": 500}, 501)["action"] == "offer"
checks += 3
# 10. a self-conceder inside our limit who has not moved for 2 ticks: take it now (no need to wait for deadline - 2)
d = duel("buyer", 100, [m(500, "R", 140), m(501, "R", 120), m(502, "R", 95)], {"price": 95, "days": None}, deadline=516)
assert decide2(d, 503)["action"] == "wait"                                              # moved last tick: let him come
assert decide2(d, 504)["action"] == "accept"                                            # 2 ticks without a move
checks += 2
# 11. our opening to a silent rival is not a counter: a reciprocal rival still gets 2 real counters after it
d = duel("buyer", 100, [m(501, "you", 75), m(502, "R", 150), m(503, "you", 85), m(504, "R", 140)], {"price": 140, "days": None},
         deadline=516)
a = decide2(d, 505)
assert a["action"] == "offer" and a["counters"] == 1, a; checks += 1
# ================= read_bot in OUR TOTAL VALUE U = price surplus + w * day (approved for Duels II) =================
from bz.duel import _toward_us, surplus  # noqa: E402


def two(role, limit, msgs, w, meaning, rival, deadline=520):
    return duel(role, limit, msgs, rival, deadline=deadline, issues=("price", "days"), w=abs(w), meaning=meaning)


COST = "each day of delay costs you this much"
# (a) price fixed, the day moves our way: he is conceding. Buyer, limit 120, a day costs us 2 P (w = -2).
d = two("buyer", 120, [m(500, "R", 100, 8), m(501, "R", 100, 6)], -2, COST, {"price": 100, "days": 6})
b = read_bot(d)
assert b["solo"] == [4.0] and b["solo_price"] == [0.0] and b["kind"] == "self", b          # dU = -2 x (6 - 8) = +4
a_ = decide2(d, 502)
assert a_["action"] == "wait" and "self-conceder" in a_["why"], a_; checks += 2
# the same duel read by price only would see no concession at all (this is the bug being fixed)
d0 = duel("buyer", 120, [m(500, "R", 100), m(501, "R", 100)], {"price": 100, "days": None})
assert read_bot(d0)["kind"] == "new"; checks += 1
# (b) price better but the day worse and net U down: NOT conceding. 100/day 6 -> 95/day 9: dU = +5 - 6 = -1
d = two("buyer", 120, [m(500, "R", 100, 6), m(501, "R", 95, 9)], -2, COST, {"price": 95, "days": 9})
b = read_bot(d)
assert b["solo"] == [-1.0] and b["solo_price"] == [5.0] and b["kind"] != "self", b
assert "self-conceder" not in decide2(d, 502)["why"]; checks += 2
# ... and with a day that helps us as much as the price, the net is positive: conceding
d = two("buyer", 120, [m(500, "R", 100, 6), m(501, "R", 95, 4)], -2, COST, {"price": 95, "days": 4})
assert read_bot(d)["solo"] == [9.0] and read_bot(d)["kind"] == "self"; checks += 1
# a seller with a gain per day: a later day is worth more to us (w = +3): his day 2 -> 5 at a fixed price is +9
d = two("seller", 60, [m(500, "R", 70, 2), m(501, "R", 70, 5)], 3, "your gain per day of delivery", {"price": 70, "days": 5})
assert read_bot(d)["solo"] == [9.0] and read_bot(d)["kind"] == "self"; checks += 1
# his answers to OUR offers are measured in U too: day moves toward us after our offer = a real answer (reciprocal)
d = two("buyer", 120, [m(500, "R", 100, 8), m(501, "you", 80, 5), m(502, "R", 100, 4)], -2, COST, {"price": 100, "days": 4})
b = read_bot(d)
assert b["answered"] == [8.0] and b["solo"] == [] and b["kind"] == "recip", b; checks += 1
# a message without a day keeps his last day
d = two("buyer", 120, [m(500, "R", 100, 6), {"tick": 501, "from": "R", "price": 96, "days": None}], -2, COST, {"price": 96, "days": None})
assert read_bot(d)["solo"] == [4.0], read_bot(d); checks += 1
# (e) price still OUTSIDE our limit and only the day moves: waiting would never give an acceptable offer, so we speak
d = two("buyer", 100, [m(500, "R", 130, 8), m(501, "R", 130, 5)], -2, COST, {"price": 130, "days": 5})
assert read_bot(d)["kind"] == "self" and read_bot(d)["solo"] == [6.0]
a_ = decide2(d, 502)
assert a_["action"] == "offer" and a_["price"] <= 100, a_; checks += 2
# (f) price inside our limit but U < 1 because of the day, and the day keeps moving our way: wait for U to reach 1
d = two("buyer", 100, [m(500, "R", 98, 5), m(501, "R", 98, 4)], -5, COST, {"price": 98, "days": 4})
a_ = decide2(d, 502)
assert a_["action"] == "wait" and "self-conceder" in a_["why"], a_; checks += 1

# (c) price-only behaviour is EXACTLY what it was: a copy of the previous read_bot must agree on thousands of random duels,
#     for price-only duels and for two-issue duels whose days do not count (w = 0)
def old_read_bot(d):
    role, msgs = d["role"], [x for x in d.get("messages") or [] if x.get("price") is not None]
    solo, answered, prev, ours_since = [], [], None, False
    for x in msgs:
        if x.get("from") == "you":
            ours_since = True
            continue
        if prev is not None:
            (answered if ours_since else solo).append(_toward_us(role, prev, x["price"]))
        prev, ours_since = x["price"], False
    if solo and max(solo) > 0 and (not answered or len(solo) >= len(answered)):
        kind = "self"
    elif answered and max(answered) >= max(2.0, 0.02 * float(d["your_limit"])):
        kind = "recip"
    elif answered:
        kind = "hard"
    else:
        kind = "new"
    return {"kind": kind, "solo": solo, "answered": answered}


rng2 = random.Random(21)
for seed in range(3000):
    role = rng2.choice(["buyer", "seller"])
    limit = rng2.randint(20, 200)
    with_days = rng2.random() < 0.5
    msgs, t0 = [], 500
    for _ in range(rng2.randint(0, 9)):
        msgs.append(m(t0, rng2.choice(["R", "R", "you"]), round(limit * rng2.uniform(0.4, 1.6)), rng2.randint(0, 10) if with_days else None))
        t0 += rng2.choice([0, 1, 1, 2])
    dd = duel(role, limit, msgs, None, issues=("price", "days") if with_days else ("price",), w=0.0 if with_days else None,
              meaning="???" if with_days else None)           # unreadable meaning: days count for nothing (w = 0)
    new, old = read_bot(dd), old_read_bot(dd)
    assert (new["kind"], new["solo"], new["answered"]) == (old["kind"], old["solo"], old["answered"]), (dd, new, old)
    assert new["solo"] == new["solo_price"] and new["answered"] == new["answered_price"], (dd, new)
checks += 1

# (d) the hard rules on 4,000 more random two-issue duels, signed weights both ways, days on every message
rng3 = random.Random(33)
crossed = 0
for seed in range(4000):
    role = rng3.choice(["buyer", "seller"])
    limit = rng3.randint(20, 200)
    msgs, t0 = [], 500
    for _ in range(rng3.randint(0, 8)):
        msgs.append(m(t0, rng3.choice(["R", "R", "you"]), round(limit * rng3.uniform(0.4, 1.6)), rng3.randint(0, 10)))
        t0 += rng3.choice([0, 1, 1, 2])
    his_ = [x for x in msgs if x["from"] != "you"]
    rival = {"price": his_[-1]["price"], "days": his_[-1]["days"]} if his_ else None
    w_ = rng3.uniform(0.2, 3.0)
    dd = duel(role, limit, msgs, rival, deadline=t0 + rng3.randint(0, 14), issues=("price", "days"), w=w_,
              meaning=rng3.choice(["your gain per day", "each day of delay costs you", "gain and cost"]))
    a_ = decide2(dd, t0)
    if a_["action"] == "offer":
        crossed += not (inside(role, limit, a_["price"]) and a_["price"] >= 1 and 0 <= a_["days"] <= 10)
    if a_["action"] == "accept":
        crossed += not (rival and inside(role, limit, rival["price"]))
assert crossed == 0, crossed; checks += 1
# the last call never retreats (found with the fake duel server: we offered 100 = our limit, then "best offer 97")
d = duel("buyer", 100, [m(500, "R", 150), m(501, "you", 75), m(502, "R", 145), m(503, "you", 100), m(504, "R", 140)],
         {"price": 140, "days": None}, deadline=516)
a_ = decide2(d, 513)                                    # 3 ticks left, counters used, he is still outside: no last call below 100
assert a_["action"] == "wait" or (a_["action"] == "offer" and a_["price"] >= 100), a_
d = duel("buyer", 100, [m(500, "R", 150), m(501, "you", 60), m(502, "R", 145), m(503, "you", 70), m(504, "R", 140)],
         {"price": 140, "days": None}, deadline=516)
a_ = decide2(d, 513)                                    # our last offer 70: a last call at 97 is a real step up
assert a_["action"] == "offer" and a_["price"] == 97 and a_["stage"] == "last_call", a_
d = duel("seller", 60, [m(500, "R", 30), m(501, "you", 90), m(502, "R", 35), m(503, "you", 60), m(504, "R", 40)],
         {"price": 40, "days": None}, deadline=516)
a_ = decide2(d, 513)                                    # a seller already at the cost 60: a "best offer" of 62 would be worse for him
assert a_["action"] == "wait", a_
d = duel("seller", 60, [m(500, "R", 30), m(501, "you", 100), m(502, "R", 35), m(503, "you", 90), m(504, "R", 40)],
         {"price": 40, "days": None}, deadline=516)
a_ = decide2(d, 513)                                    # our last offer 90: a last call at 62 is a real step toward him
assert a_["action"] == "offer" and a_["price"] == 62 and a_["stage"] == "last_call", a_
checks += 4
# ================= PACKAGES: every two-issue offer is (price, day) built from a target U (approved for Duels II) =================
import importlib.util  # noqa: E402
from bz.duel import last_call_day, opening_day, package_counter  # noqa: E402

spec = importlib.util.spec_from_file_location("duel_v2_frozen", os.path.join(os.path.dirname(os.path.abspath(__file__)), "duel_v2_frozen.py"))
frozen = importlib.util.module_from_spec(spec)
spec.loader.exec_module(frozen)          # the exact decide2 of commit 9bdbd9c, before packages

# (d) price-only duels: the full answer is IDENTICAL to the frozen code on 3,000 random duels
rng4 = random.Random(44)
for seed in range(3000):
    role = rng4.choice(["buyer", "seller"])
    limit = rng4.randint(20, 200)
    msgs, t0 = [], 500
    for _ in range(rng4.randint(0, 9)):
        msgs.append(m(t0, rng4.choice(["R", "R", "you"]), round(limit * rng4.uniform(0.4, 1.6))))
        t0 += rng4.choice([0, 1, 1, 2])
    his_ = [x for x in msgs if x["from"] != "you"]
    rival = {"price": his_[-1]["price"], "days": None} if his_ else None
    dd = duel(role, limit, msgs, rival, deadline=t0 + rng4.randint(0, 14), decay=rng4.choice([0.06, 0.08, 0.1]))
    assert decide2(dd, t0) == frozen.decide2(dd, t0), (dd, decide2(dd, t0), frozen.decide2(dd, t0))
checks += 1

# (f) the opening day is halfway between 5 and our preferred end: 8 when a day gains us, 3 when it costs (half up); w = 0: his day or 5
assert opening_day(2.0, None) == 8 and opening_day(-2.0, None) == 3 and opening_day(0.0, None) == 5 and opening_day(0.0, 9) == 9
assert opening_day(2.0, 1) == 8 and opening_day(-2.0, 9) == 3          # with w != 0 his day does not move our opening
d = two("buyer", 100, [], -2, COST, None, deadline=516)
a_ = decide2(d, 501)
assert a_["action"] == "offer" and a_["stage"] == "opening" and a_["price"] == 75 and a_["days"] == 3, a_; checks += 3

# (e) w = 0 (days do not count to us): every day moved toward him costs 1 P. Buyer, limit 100, our last offer 80 on day 2, he asks day 8.
p = package_counter("buyer", 100, 0.0, (80, 2), (120, 8))
assert p and p["day"] == 5 and p["moved"] == 3 and p["charge"] == 3, p     # halfway 2 -> 5: three days, 3 P
assert p["p0"] - p["price"] == 3, p                                          # 96 at the unchanged day, 93 with the move
p = package_counter("seller", 60, 0.0, (90, 2), (30, 8))
assert p["day"] == 5 and p["price"] - p["p0"] == 3, p; checks += 3

# a move that HELPS us is no concession: no premium, no giving back, and U ends above the target (w>0: later days gain us value)
p = package_counter("seller", 60, 3.0, (110, 2), (70, 8))                   # he asks day 8, we like later days (+3 per day)
assert p["helps"] is True and p["charge"] == 0 and p["day"] == 5 and p["price"] == p["p0"], p
assert p["u"] > p["u_t"], p                                                  # we keep the day gain
# a move that HURTS us (w>0, he asks an earlier day) is paid: c = max(|w|, 1) = 3 P per day
p = package_counter("seller", 60, 3.0, (110, 8), (70, 2))
assert p["helps"] is False and p["day"] == 5 and p["moved"] == 3 and p["charge"] == 9 and p["price"] - p["p0"] == 9, p; checks += 4

# (a)(b) properties on 20,000 random package situations
rng5 = random.Random(55)
n_pkg = n_helps = n_hurt = n_none = 0
for seed in range(20000):
    role = rng5.choice(["buyer", "seller"])
    limit = rng5.randint(20, 200)
    w = rng5.choice([-1, 1]) * rng5.choice([0.0, 0.3, 0.8, 1.0, 1.7, 3.0, 5.0])
    ld = rng5.randint(0, 10)
    lp = round(limit * (rng5.uniform(0.5, 0.95) if role == "buyer" else rng5.uniform(1.05, 1.6)))
    hasher = rng5.random() < 0.85
    if hasher:
        hp = round(limit * rng5.uniform(0.6, 1.7))
        hd = rng5.choice([None, rng5.randint(0, 10), rng5.randint(0, 10)])
        his = (hp, hd)
    else:
        his = None
    pk = package_counter(role, limit, w, (lp, ld), his)
    if pk is None:
        n_none += 1
        continue
    n_pkg += 1
    u_last = surplus(role, limit, lp) + w * ld
    c = max(abs(w), 1.0)
    # the limit is never crossed, the day is a real day, the price is a real price
    assert inside(role, limit, pk["price"]) and pk["price"] >= 1 and 0 <= pk["day"] <= 10, (pk, role, limit)
    # the day moves only toward the day he asked, never past halfway, and not at all if he asked none
    if his is None or his[1] is None:
        assert pk["day"] == ld, pk
    else:
        half = int(ld + 0.5 * (his[1] - ld) + 0.5)
        lo, hi = min(ld, half), max(ld, half)
        assert lo <= pk["day"] <= hi, (pk, ld, his)
    sign = w * (pk["day"] - ld)
    if pk["moved"] > 0 and sign <= 0:      # (a) a conceding or neutral move: >= c P per day in OUR favour vs the unchanged-day package
        n_hurt += 1
        gain_for_us = (pk["p0"] - pk["price"]) if role == "buyer" else (pk["price"] - pk["p0"])
        assert gain_for_us >= c * pk["moved"] - 1e-9, (pk, c)              # whole premium, no rounding slack
    if pk["moved"] > 0 and sign > 0:       # a helping move never lowers our price against the unchanged-day package
        n_helps += 1
        worse = (pk["price"] > pk["p0"]) if role == "buyer" else (pk["price"] < pk["p0"])
        assert not worse, pk
    u = pk["u"]
    if not pk["helps"]:                    # (b) U never rises against us ...
        assert u <= u_last + 1e-6, (pk, u_last)
    if his is not None:                    # ... and never drops below his last offer's U
        u_his = surplus(role, limit, his[0]) + w * (his[1] if his[1] is not None else ld)
        assert u >= u_his - 1e-6, (pk, u_his)
        assert (pk["price"] < his[0]) if role == "buyer" else (pk["price"] > his[0]), (pk, his)   # never at or beyond his price
assert n_pkg > 8000 and n_hurt > 1500 and n_helps > 500, (n_pkg, n_hurt, n_helps, n_none); checks += 2

# (b) chains: opening, then up to 3 counters against a rival who concedes; the U of our offers does not rise (unless a day helps us)
rng6 = random.Random(66)
chains = 0
for seed in range(2000):
    role = rng6.choice(["buyer", "seller"])
    limit = rng6.randint(40, 180)
    w = rng6.choice([-1, 1]) * rng6.choice([0.5, 1.0, 2.0, 4.0])
    meaning = "your gain per day" if w > 0 else COST
    msgs = [m(500, "R", round(limit * (1.4 if role == "buyer" else 0.6)), rng6.randint(0, 10))]
    last_u = None
    for step_i in range(4):
        tick_ = 503 + 2 * step_i
        rp = msgs[-1]["price"] + (-1 if role == "buyer" else 1) * rng6.randint(0, 6)
        dd = duel(role, limit, msgs, {"price": msgs[-1]["price"], "days": msgs[-1]["days"]}, deadline=530, issues=("price", "days"),
                  w=abs(w), meaning=meaning)
        a_ = decide2(dd, tick_)
        if a_["action"] != "offer":
            break
        assert inside(role, limit, a_["price"]) and 0 <= a_["days"] <= 10, a_
        u_now = surplus(role, limit, a_["price"]) + w * a_["days"]
        if last_u is not None and "pkg" in a_ and not a_["pkg"]["helps"]:
            assert u_now <= last_u + 1e-6, (a_, u_now, last_u)
        last_u = u_now
        msgs.append({"tick": tick_, "from": "you", "price": a_["price"], "days": a_["days"]})
        msgs.append({"tick": tick_ + 1, "from": "R", "price": rp, "days": rng6.randint(0, 10)})
        chains += 1
assert chains > 1500, chains; checks += 1                       # 2000 chains x up to 4 offers

# (g) the last call: U >= 1 and inside the limit; his day if it fits, else the nearest day that does
for w_ in (2.0, -2.0):
    meaning = "your gain per day" if w_ > 0 else COST
    d = duel("buyer", 100, [m(500, "R", 150, 4), m(501, "you", 75, 5), m(503, "you", 90, 5), m(504, "R", 140, 4)],
             {"price": 140, "days": 4}, deadline=516, issues=("price", "days"), w=abs(w_), meaning=meaning)
    a_ = decide2(d, 513)
    assert a_["action"] == "offer" and a_["stage"] == "last_call", a_
    assert inside("buyer", 100, a_["price"]) and surplus("buyer", 100, a_["price"]) + w_ * a_["days"] >= 1 and 0 <= a_["days"] <= 10, a_
    assert a_["days"] == (4 if w_ > 0 else 1), a_                  # w>0: his day 4 fits; w<0: U >= 1 needs day <= 1, the nearest to 4
assert last_call_day("seller", 60, 1.0, 63, 7, 5) == 7 and last_call_day("buyer", 100, -3.0, 97, 9, 2) == 0   # 3 - 3d >= 1 -> d = 0
assert last_call_day("buyer", 100, -5.0, 99, None, None) == 0                                              # margin 1: only day 0 gives U >= 1
assert last_call_day("buyer", 100, -5.0, 99, 6, 6) == 0 and last_call_day("buyer", 100, -9.0, 100, 3, 3) is None   # surplus 0: no day fits
checks += 3
# ================= HARD RULE: every offer we send has U >= 1 (price surplus + w x day), on top of price inside the limit =================
from bz.duel import U_FLOOR, days_weight, fix_day_for_u  # noqa: E402

# the blocker case (found in verification): buyer L=100, a day costs 2, we opened 75/day 3, he asks 140/day 8 then 130/day 8.
# The package used to be 95 P / day 6 with U = 5 - 12 = -7. Now: an offer with U >= 1, or a wait.
d = two("buyer", 100, [m(500, "R", 140, 8), m(501, "you", 75, 3), m(502, "R", 130, 8)], -2, COST, {"price": 130, "days": 8}, deadline=530)
a_ = decide2(d, 503)
assert a_["action"] == "offer" and surplus("buyer", 100, a_["price"]) - 2 * a_["days"] >= 1 and a_["price"] <= 100, a_
assert (a_["price"], a_["days"]) == (87, 6), a_      # u_t is floored at 1: the biggest concession we can make is U = 1
checks += 1

# fix_day_for_u: toward our last day first, then toward our preferred end; nothing fits: None
assert fix_day_for_u("buyer", 100, -2.0, 99, 6, 3) == 0          # surplus 1: only day 0 leaves U >= 1; path 6 -> 3 -> 0
assert fix_day_for_u("buyer", 100, -2.0, 90, 8, 3) == 4          # surplus 10: U = 10 - 2d >= 1 -> d <= 4; the first day on the path 8 -> 3
assert fix_day_for_u("buyer", 100, 0.0, 100, 5, 5) is None       # w = 0: days do not count and the surplus is 0
assert fix_day_for_u("seller", 60, 3.0, 61, 2, 5) == 2           # already U = 1 + 6 >= 1: kept
checks += 4

# the opening with a large weight: day 3 at 75 P would be U = 25 - 30 = -5; the day moves toward our side until U >= 1
d = two("buyer", 100, [], -10, COST, None, deadline=516)
a_ = decide2(d, 501)
assert a_["action"] == "offer" and 25 - 10 * a_["days"] >= 1 and a_["days"] == 2, a_; checks += 1

# the 20,000 random packages: 0 with U < 1 (re-run with the same generator as above, counting)
rng7 = random.Random(55)
bad = n = 0
for seed in range(20000):
    role = rng7.choice(["buyer", "seller"])
    limit = rng7.randint(20, 200)
    w = rng7.choice([-1, 1]) * rng7.choice([0.0, 0.3, 0.8, 1.0, 1.7, 3.0, 5.0])
    ld = rng7.randint(0, 10)
    lp = round(limit * (rng7.uniform(0.5, 0.95) if role == "buyer" else rng7.uniform(1.05, 1.6)))
    his = (round(limit * rng7.uniform(0.6, 1.7)), rng7.choice([None, rng7.randint(0, 10), rng7.randint(0, 10)])) if rng7.random() < 0.85 else None
    pk = package_counter(role, limit, w, (lp, ld), his)
    if pk:
        n += 1
        bad += (surplus(role, limit, pk["price"]) + w * pk["day"]) < U_FLOOR - 1e-9
assert n > 8000 and bad == 0, (n, bad); checks += 1

# the 4,000 random two-issue duels: every offer (opening, counter, last call, fallback) has U >= 1; nothing crosses the limit
rng8 = random.Random(77)
offers = low = 0
for seed in range(4000):
    role = rng8.choice(["buyer", "seller"])
    limit = rng8.randint(20, 200)
    msgs, t0 = [], 500
    for _ in range(rng8.randint(0, 8)):
        msgs.append(m(t0, rng8.choice(["R", "R", "you"]), round(limit * rng8.uniform(0.4, 1.6)), rng8.randint(0, 10)))
        t0 += rng8.choice([0, 1, 1, 2])
    his_ = [x for x in msgs if x["from"] != "you"]
    rival = {"price": his_[-1]["price"], "days": his_[-1]["days"]} if his_ else None
    dd = duel(role, limit, msgs, rival, deadline=t0 + rng8.randint(0, 14), issues=("price", "days"), w=rng8.uniform(0.2, 6.0),
              meaning=rng8.choice(["your gain per day", "each day of delay costs you"]))
    a_ = decide2(dd, t0)
    if a_["action"] == "offer":
        offers += 1
        w_signed = days_weight(dd)[0]
        low += (surplus(role, limit, a_["price"]) + w_signed * a_["days"]) < U_FLOOR - 1e-9
        assert inside(role, limit, a_["price"]) and 0 <= a_["days"] <= 10, a_
assert offers > 800 and low == 0, (offers, low); checks += 1

# the 2,000 chains of successive offers (same generator as the earlier chain test): every offer has U >= 1
rng9 = random.Random(66)
chains = low = 0
for seed in range(2000):
    role = rng9.choice(["buyer", "seller"])
    limit = rng9.randint(40, 180)
    w = rng9.choice([-1, 1]) * rng9.choice([0.5, 1.0, 2.0, 4.0, 8.0])
    meaning = "your gain per day" if w > 0 else COST
    msgs = [m(500, "R", round(limit * (1.4 if role == "buyer" else 0.6)), rng9.randint(0, 10))]
    for step_i in range(4):
        tick_ = 503 + 2 * step_i
        dd = duel(role, limit, msgs, {"price": msgs[-1]["price"], "days": msgs[-1]["days"]}, deadline=530, issues=("price", "days"),
                  w=abs(w), meaning=meaning)
        a_ = decide2(dd, tick_)
        if a_["action"] != "offer":
            break
        chains += 1
        low += (surplus(role, limit, a_["price"]) + w * a_["days"]) < U_FLOOR - 1e-9
        msgs.append({"tick": tick_, "from": "you", "price": a_["price"], "days": a_["days"]})
        msgs.append({"tick": tick_ + 1, "from": "R", "price": msgs[-2]["price"] + (-1 if role == "buyer" else 1) * rng9.randint(0, 6),
                     "days": rng9.randint(0, 10)})
assert chains > 1500 and low == 0, (chains, low); checks += 1

# the last call keeps U >= 1 (already enforced by last_call_day): 3 more random scans
for seed in range(2000):
    w_ = rng9.choice([-1, 1]) * rng9.choice([0.3, 1.0, 2.0, 5.0, 9.0])
    limit = rng9.randint(20, 200)
    p = limit - max(1, round(0.03 * limit))
    dy = last_call_day("buyer", limit, w_, p, rng9.choice([None, rng9.randint(0, 10)]), rng9.choice([None, rng9.randint(0, 10)]))
    assert dy is None or (0 <= dy <= 10 and surplus("buyer", limit, p) + w_ * dy >= U_FLOOR - 1e-9)
checks += 1
# ================= days_meaning: the EXACT sentences of the Duels II duels (a hotfix: 'adds' was read as unread, w = 0) =================
SELL_MEANING = "each delivery day adds this much cash to your side"      # sell duels: a later day GAINS us value
BUY_MEANING = "each delivery day costs you this much cash"               # buy duels: a later day COSTS us value
w_sell, how_sell = days_weight({"issues": ["price", "days"], "your_days_weight": 3.0, "days_meaning": SELL_MEANING})
w_buy, how_buy = days_weight({"issues": ["price", "days"], "your_days_weight": 3.0, "days_meaning": BUY_MEANING})
assert (w_sell, how_sell) == (3.0, "gain per day"), (w_sell, how_sell)
assert (w_buy, how_buy) == (-3.0, "cost per day"), (w_buy, how_buy)
# through decide2 (what the agent logs as w and w_how), seller and buyer, and the old sentences still read the same way
for role, meaning, w_exp, how_exp in (("seller", SELL_MEANING, 3.0, "gain per day"), ("buyer", BUY_MEANING, -3.0, "cost per day"),
                                      ("seller", "your gain per day of delivery", 3.0, "gain per day"),
                                      ("buyer", "each day of delay costs you this much", -3.0, "cost per day")):
    dd = duel(role, 100, [m(500, "R", 140 if role == "buyer" else 60, 5)], {"price": 140 if role == "buyer" else 60, "days": 5},
              deadline=520, issues=("price", "days"), w=3.0, meaning=meaning)
    a_ = decide2(dd, 503)
    assert (a_["w"], a_["w_how"]) == (w_exp, how_exp), (role, meaning, a_["w"], a_["w_how"])
# an unreadable sentence still counts days for nothing (w = 0), and never crashes
assert days_weight({"issues": ["price", "days"], "your_days_weight": 3.0, "days_meaning": "???"})[0] == 0.0
checks += 4
print(f"test_duel2: {checks} checks passed (4000 random duels for the hard rules, 3000 regression duels, 4000 random two-issue duels)")

