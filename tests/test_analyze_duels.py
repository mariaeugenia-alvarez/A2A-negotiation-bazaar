"""analyze_duels.summarize and the arm split in duels.py. python3 tests/test_analyze_duels.py"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from analyze_duels import summarize  # noqa: E402

duels = [
    {"duel": 1, "status": "deal", "result": 20.0, "your_limit": 100, "rounds": 2},
    {"duel": 2, "status": "deal", "result": 30.0, "your_limit": 100, "rounds": 4},
    {"duel": 3, "status": "no_deal", "result": 0.0, "your_limit": 80, "rounds": 0},
    {"duel": 4, "status": "live", "result": None, "your_limit": 80, "rounds": 1},
    {"duel": 5, "status": "deal", "result": 10.0, "your_limit": 50, "rounds": 1},
]
s = summarize(duels, {1: 0.45, 2: 0.25, 3: 0.45, 4: 0.25, 5: 0.25})
assert s[0.45] == {"duels": 2, "deals": 1, "deal_rate": 0.5, "result_over_limit": 0.2, "mean_rounds": 2}, s
assert s[0.25]["duels"] == 2 and s[0.25]["deals"] == 2, s          # the live duel is not counted
assert s[0.25]["result_over_limit"] == 0.25, s                     # mean of 0.30 and 0.20
s = summarize(duels, {})
assert list(s) == [None] and s[None]["duels"] == 4, s              # no arm logged: one group

# duels.arm_for gives the same arm to the same duel, and alternates
os.environ.setdefault("BAZAAR_KEY", "x")
from duels import arm_for  # noqa: E402
arms = [0.45, 0.25]
assert [arm_for(i, arms) for i in (1, 2, 3, 4)] == [0.25, 0.45, 0.25, 0.45]
assert arm_for(7, arms) == arm_for(7, arms)
assert arm_for(9, [0.45]) == 0.45                                  # no split test: one arm for every duel
# ---- avoidable no-deals: the new safety-switch rule
from analyze_duels import avoidable_no_deals  # noqa: E402


def nd(i, role, limit, msgs, deadline=520, issues=("price",), w=None, meaning=None):
    return {"duel": i, "status": "no_deal", "role": role, "your_limit": limit, "deadline_tick": deadline, "issues": list(issues),
            "your_days_weight": w, "days_meaning": meaning, "messages": msgs}


def msg(t, who, p, day=None):
    return {"tick": t, "from": who, "price": p, "days": day}


# 2362 (Duels I): he offered 129 inside our buyer limit 148 and we never answered: AVOIDABLE
assert [a["duel"] for a in avoidable_no_deals([nd(2362, "buyer", 148, [msg(504, "R", 129)], 519)])] == [2362]
# 2485: seller cost 85, he climbed to 106 and we said nothing: AVOIDABLE
assert [a["duel"] for a in avoidable_no_deals([nd(2485, "seller", 85, [msg(526, "R", 53), msg(535, "R", 106)], 542)])] == [2485]
# a silent rival (2317) and a rival who never came inside our limit (2486 style) do NOT count
assert avoidable_no_deals([nd(2317, "buyer", 128, [], 525)]) == []
assert avoidable_no_deals([nd(9, "buyer", 100, [msg(500, "R", 160), msg(505, "R", 140)], 520)]) == []
# an offer in the last tick could not be answered
assert avoidable_no_deals([nd(8, "buyer", 100, [msg(519, "R", 90)], 520)]) == []
assert avoidable_no_deals([nd(8, "buyer", 100, [msg(518, "R", 90)], 520)])[0]["price"] == 90
# only no-deals count
assert avoidable_no_deals([{**nd(7, "buyer", 100, [msg(500, "R", 90)]), "status": "deal"}]) == []
# U matters: inside our limit but the day makes U < 1: not avoidable (buyer 100, a day costs 5: 98 on day 5 = 2 - 25)
assert avoidable_no_deals([nd(6, "buyer", 100, [msg(500, "R", 98, 5)], 520, ("price", "days"), 5, "each day costs you")]) == []
assert avoidable_no_deals([nd(6, "buyer", 100, [msg(500, "R", 98, 0)], 520, ("price", "days"), 5, "each day costs you")])[0]["u"] == 2.0
# the same offer with a day that HELPS us: U = 2 + 5 x 5 = 27: avoidable
assert avoidable_no_deals([nd(5, "buyer", 100, [msg(500, "R", 98, 5)], 520, ("price", "days"), 5, "your gain per day")])[0]["u"] == 27.0
print("test_analyze_duels: ok")
