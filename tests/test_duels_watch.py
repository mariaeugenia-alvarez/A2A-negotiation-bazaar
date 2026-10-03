"""duels_watch.waiting_on_us on the Duels I silences. python3 tests/test_duels_watch.py"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("BAZAAR_KEY", "x")
from duels_watch import waiting_on_us  # noqa: E402


def duel(i, msgs, deadline=535, status="live"):
    return {"duel": i, "status": status, "deadline_tick": deadline, "messages": msgs}


def m(t, who, p):
    return {"tick": t, "from": who, "price": p}


# 2362: the rival offered 129 (inside our 148) at tick 504 and we never answered
assert waiting_on_us([duel(2362, [m(503, "you", 80), m(504, "R", 129)], 519)], 507, 3) == [2362]
assert waiting_on_us([duel(2362, [m(503, "you", 80), m(504, "R", 129)], 519)], 505, 3) == []    # not yet 3 ticks
# our offer stands: we wait for the rival, not a silence of ours
assert waiting_on_us([duel(1, [m(503, "R", 129), m(504, "you", 110)], 519)], 515, 3) == []
# 2317: nobody spoke since the duel opened (deadline - 16)
assert waiting_on_us([duel(2317, [], 525)], 512, 3) == [2317]
# finished duels never count
assert waiting_on_us([duel(9, [], 525, status="deal")], 540, 3) == []
# v2 waits on purpose (self-conceder): a decision logged for the duel within `silent` ticks means the agent is alive
assert waiting_on_us([duel(2485, [m(526, "R", 53), m(529, "R", 70)], 542)], 533, 3, {2485: 532}) == []
assert waiting_on_us([duel(2485, [m(526, "R", 53), m(529, "R", 70)], 542)], 533, 3, {2485: 529}) == [2485]
print("test_duels_watch: ok")
