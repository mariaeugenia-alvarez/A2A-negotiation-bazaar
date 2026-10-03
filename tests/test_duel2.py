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
assert a["action"] == "offer" and a["days"] == 7, a; checks += 1
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
print(f"test_duel2: {checks} checks passed (4000 random duels for the hard rules, 3000 regression duels, 4000 random two-issue duels)")

