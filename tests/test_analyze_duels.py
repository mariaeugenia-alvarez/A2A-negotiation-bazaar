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
print("test_analyze_duels: ok")
