"""The reviewer's failing inputs for bz/duel.decide, as checks. python3 tests/test_duel.py"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from bz.duel import decide, surplus  # noqa: E402


def duel(role, limit, msgs, rival=None, issues=("price",), w=None, meaning=None, deadline=150, decay=0.06):
    return {"role": role, "your_limit": limit, "issues": list(issues), "your_days_weight": w, "days_meaning": meaning,
            "deadline_tick": deadline, "decay_per_round": decay, "messages": msgs, "rival_offer": rival}


def m(tick, who, price, days=None):
    return {"tick": tick, "from": who, "price": price, "days": days}


def ok(a, d):
    """Every offer and accept is inside our limit on price alone, a valid price and day."""
    if a["action"] == "offer":
        assert a["price"] >= 1 and surplus(d["role"], d["your_limit"], a["price"]) >= 0, a
        if "days" in d["issues"]:
            assert a["days"] is not None and 0 <= a["days"] <= 10, a
    if a["action"] == "accept":
        assert surplus(d["role"], d["your_limit"], d["rival_offer"]["price"]) >= 0, a


checks = 0
# 1. his first offer, barely inside our limit, is not accepted on the spot
d = duel("buyer", 129, [m(120, "R", 128)], {"price": 128}, deadline=140)
a = decide(d, 121); ok(a, d); assert a["action"] == "offer", a; checks += 1
d = duel("buyer", 129, [m(120, "R", 103)], {"price": 103}, deadline=140)
a = decide(d, 121); ok(a, d); assert a["action"] == "offer", a; checks += 1
# 2. two issues: no price below 1
d = duel("buyer", 50, [m(1, "R", 90, 2), m(2, "R", 80, 0)], {"price": 80, "days": 0}, ("price", "days"), 4,
         "your gain per day of delivery", deadline=20)
a = decide(d, 3); ok(a, d); checks += 1
# 3. two issues: never offer or accept a price past our limit, whatever the days
d = duel("seller", 20, [m(1, "R", 5, 10)], {"price": 5, "days": 10}, ("price", "days"), 6, "gain per day", deadline=3)
a = decide(d, 2); ok(a, d); assert a["action"] != "accept", a; checks += 1
d = duel("seller", 20, [m(1, "R", 5, 10)], {"price": 5, "days": 10}, ("price", "days"), 5, "gain per day", deadline=132)
a = decide(d, 131); ok(a, d); assert a["action"] != "accept", a; checks += 1
# 4. the sign of the days weight comes from days_meaning; unreadable -> days count for nothing
d = duel("buyer", 129, [m(1, "R", 125, 10)], {"price": 125, "days": 10}, ("price", "days"), 2,
         "each day of delay costs you this much", deadline=10)
a = decide(d, 9); assert a["w"] == -2.0, a; assert a["action"] != "accept" or a["u_his"] >= 1, a; checks += 1
a = decide(duel("buyer", 129, [], None, ("price", "days"), 2, "???"), 1); assert a["w"] == 0.0, a; checks += 1
# 5. same-tick answer: we do not talk twice in a row while he has not replied
d = duel("buyer", 129, [m(120, "R", 110), m(120, "you", 71)], {"price": 110}, deadline=140)
a = decide(d, 121); assert a["action"] == "wait", a; checks += 1
# 8. silent rival: no concessions without his replies, a last offer near the deadline
d = duel("seller", 84, [m(120, "you", 122)], None, deadline=132)
a = decide(d, 125); assert a["action"] == "wait", a; checks += 1
a = decide(d, 130); ok(a, d); assert a["action"] == "offer" and a["price"] < 122, a; checks += 1
# a real exchange still concedes and closes
d = duel("buyer", 129, [m(120, "R", 129), m(121, "you", 71), m(121, "R", 114), m(122, "you", 95), m(122, "R", 103)],
         {"price": 103}, deadline=132)
a = decide(d, 123); ok(a, d); checks += 1
print(f"{checks} checks passed; last decision: {a['action']} {a.get('price')} ({a['why']})")
# duel 143 (practice): he moved 1 after our opening, before any step of ours -> do not accept 13 of a big room
d = duel("buyer", 138, [m(144, "R", 126), m(144, "you", 76), m(145, "R", 125)], {"price": 125}, deadline=156)
a = decide(d, 145); assert a["action"] == "offer", a
# after real steps that he answers with tiny steps, taking his offer is right
d = duel("buyer", 138, [m(1, "R", 126), m(1, "you", 76), m(2, "R", 125), m(2, "you", 100), m(3, "R", 124),
                        m(3, "you", 110), m(4, "R", 123.5)], {"price": 123}, deadline=156)
a = decide(d, 4); assert a["action"] == "accept", a
print("reciprocity checks passed")
