"""bz/signals: price-drop detection and what a drop is worth to us. python3 tests/test_signals.py"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from bz.signals import AskTracker, assess  # noqa: E402


def ask(i, p, maker="m1", ref="LAV-04", venue="rastro"):
    return {"id": i, "maker": maker, "ref": ref, "price": p, "venue": venue}


checks = 0
t = AskTracker()
assert t.update(100, [ask(1, 12)])[0]["kind"] == "new"
e = t.update(110, [ask(2, 10)])[0]
assert e["kind"] == "drop" and e["last"] == 12 and e["pct"] == 0.167 and e["drops_in_row"] == 1, e
e = t.update(120, [ask(3, 9)])[0]
assert e["kind"] == "drop" and e["drops_in_row"] == 2, e                       # a staircase: 12 -> 10 -> 9
assert t.update(125, [ask(4, 9)])[0]["kind"] == "same"
assert t.update(130, [ask(5, 11)])[0]["kind"] == "raise"
assert t.update(131, [ask(5, 11)]) == []                                       # an offer already seen is not a new signal
checks += 6
# another maker, another card, and the memory window
t = AskTracker(memory=80)
t.update(100, [ask(1, 12, maker="m1"), ask(2, 12, maker="m2"), ask(3, 12, ref="LAV-05")])
assert [e["kind"] for e in t.update(110, [ask(4, 10, maker="m2")])] == ["drop"]   # m2 only
assert t.update(110, [ask(5, 10, maker="m3")])[0]["kind"] == "new"                # unrelated maker
assert t.update(300, [ask(6, 8, maker="m1")])[0]["kind"] == "new"                 # 200 ticks later: forgotten
checks += 3
# what a drop is worth: LAV-04 is worth 16 to us. At El Rastro we pay the fee (2 P on a 9 P ask).
a = assess({"price": 9}, 16.0, 2)
assert a["clears"] and a["max_price"] == 12 and a["gain"] == 5.0, a
a = assess({"price": 13}, 16.0, 2)
assert not a["clears"] and a["near"] and a["gap"] == 1, a                      # one small drop from clearing
a = assess({"price": 20}, 16.0, 2)
assert not a["clears"] and not a["near"], a
a = assess({"price": 20}, 27.5, 0)                                             # SAL-06 on a 0 % venue: 27.5 - 2.75 margin
assert a["clears"] and a["max_price"] == 24, a
checks += 4
print(f"test_signals: {checks} checks passed")
