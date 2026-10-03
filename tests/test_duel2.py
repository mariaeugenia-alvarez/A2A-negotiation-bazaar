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
print(f"test_duel2: {checks} checks passed (4000 random duels for the hard rules)")
