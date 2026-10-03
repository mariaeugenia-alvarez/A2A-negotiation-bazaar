"""bz/boards.BoardScanner: no burst, new boards noticed. python3 tests/test_boards.py"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from bz.boards import BoardScanner  # noqa: E402

VENUES = [f"v{i:02d}" for i in range(1, 22)] + ["rastro"]          # 22 boards, like Saturday


class Boards:
    def __init__(self, full):
        self.full, self.calls = set(full), []

    def read(self, v):
        self.calls.append(v)
        return [{"id": 1}] if v in self.full else []


checks = 0
b = Boards({"rastro", "v02", "v07"})
sc = BoardScanner(per_tick=4)
per_tick = []
for _ in range(8):
    b.calls = []
    out = sc.scan(b.read, VENUES)
    per_tick.append(len(b.calls))
    assert {"rastro", "v02", "v07"} <= set(sc.active) or _ < 6        # the three busy boards are found within 6 ticks
assert max(per_tick) <= 3 + 4, per_tick                                # 3 active + 4 probes, never 22 at once
assert sc.active == {"rastro", "v02", "v07"}, sc.active
checks += 3
# every tick afterwards: the 3 active boards plus 4 probes
b.calls = []
sc.scan(b.read, VENUES)
assert len(b.calls) == 7 and {"rastro", "v02", "v07"} <= set(b.calls); checks += 1
# a quiet board that gets an offer is noticed within ceil(19 / 4) = 5 ticks
b.full.add("v15")
for n in range(1, 8):
    sc.scan(b.read, VENUES)
    if "v15" in sc.active:
        break
assert "v15" in sc.active and n <= 5, n; checks += 1
# an active board that empties is dropped
b.full.discard("v02")
sc.scan(b.read, VENUES)
assert "v02" not in sc.active; checks += 1
# a venue that closes disappears from the set
sc.scan(b.read, [v for v in VENUES if v != "rastro"])
assert "rastro" not in sc.active; checks += 1
print(f"test_boards: {checks} checks passed")
