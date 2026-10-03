"""trader_review.analyze/render on synthetic logs: every proposal rule fires on its own evidence. python3 tests/test_trader_review.py"""
import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import trader_review as R  # noqa: E402

NOW = 1_000_000.0


def write(d, name, rows):
    with open(os.path.join(d, name + ".jsonl"), "w") as f:
        for x in rows:
            f.write(json.dumps(x) + "\n")


def make(**k):
    d = tempfile.mkdtemp()
    json.dump({"ts": NOW - 10, "live": True, "acting": True, "stopped": False, "budget": 40, "cash": 50}, open(os.path.join(d, "trader.heartbeat"), "w"))
    for name, rows in k.items():
        write(d, name, rows)
    return d


def ts(n):
    return NOW - n * 60


checks = 0
# 1. a healthy quiet trader: no proposal except "nothing to improve"
d = make(score=[{"ts": ts(100), "rank": 10, "score": 20, "cash": 120, "negotiating": 10, "median_neg": 12, "leader_neg": 20},
                {"ts": ts(1), "rank": 9, "score": 22, "cash": 118, "negotiating": 11, "median_neg": 12.2, "leader_neg": 20.4}])
rep = R.analyze(d, NOW, 2)
assert [p[1] for p in rep["proposals"]] == ["Nothing to improve: no clear win appeared in this window."], rep["proposals"]
txt = R.render(rep)
assert "Rank 10 -> 9" in txt and "Negotiating: ours +1.00, field median +0.20, leader +0.40" in txt, txt; checks += 2
# 2. no heartbeat and a pause file: the first two proposals, in that order
d = make()
os.remove(os.path.join(d, "trader.heartbeat"))
open(os.path.join(d, "trader.pause"), "w").write("neg_points fell\n")
p = R.analyze(d, NOW, 2)["proposals"]
assert p[0][1].startswith("The trader is not running") and p[1][1].startswith("The trader is paused: neg_points fell"), p; checks += 1
# 3. an old heartbeat counts as not running
d = make()
json.dump({"ts": NOW - 400}, open(os.path.join(d, "trader.heartbeat"), "w"))
assert R.analyze(d, NOW, 2)["proposals"][0][1].startswith("The trader is not running"); checks += 1
# 4. clear wins blocked by the budget: propose a higher budget, with the evidence
d = make(trader_blocked=[{"ts": ts(5), "offer": 1, "reason": "budget", "surplus": 4.0, "cost": 9, "venue": "rastro"},
                         {"ts": ts(4), "offer": 2, "reason": "budget", "surplus": 5.0, "cost": 11, "venue": "v02"},
                         {"ts": ts(3), "offer": 2, "reason": "budget", "surplus": 5.0, "cost": 11, "venue": "v02"}])   # a repeat: counted once
rep = R.analyze(d, NOW, 2)
assert rep["blocked"]["budget"]["n"] == 2 and rep["blocked"]["budget"]["surplus"] == 9.0, rep["blocked"]
top = rep["proposals"][0]
assert "Raise the board budget" in top[1] and "2 clear wins blocked" in top[2] and "+9.0 P" in top[2], top; checks += 2
# 5. counters: 5 sent, none accepted. Bids: 8 posted, none filled. Cash under 30 P most of the time.
d = make(trader_counter=[{"ts": ts(i)} for i in range(5)], trader_outcome=[{"ts": ts(i), "outcome": "expired"} for i in range(5)],
         quotes=[{"ts": ts(i), "event": "posted", "side": "bid", "offer": i, "ratio": 0.8} for i in range(8)],
         score=[{"ts": ts(100 - i), "cash": 20, "rank": 15, "score": 20} for i in range(10)])
txt = [p[1] for p in R.analyze(d, NOW, 2)["proposals"]]
assert "Stop sending counters." in txt and any(t.startswith("Standing bids never fill") for t in txt) and any(t.startswith("Cash is the limit") for t in txt), txt; checks += 1
# 6. accepts that settle worse than planned
acc = [{"ts": ts(i), "offer": i, "surplus": 5.0, "cash_out": 9, "fee": 2} for i in range(1, 4)]
setl = [{"ts": ts(i), "offer": i, "found": True, "planned_gain": 5.0, "realized_gain": 2.0} for i in range(1, 4)]
d = make(trader_accept=acc, trader_settlement=setl)
rep = R.analyze(d, NOW, 2)
assert rep["accepts"]["n"] == 3 and rep["accepts"]["cost"] == 33 and rep["accepts"]["realized"] == 6.0
assert any(p[1].startswith("Accepts settle worse than planned") for p in rep["proposals"]); checks += 2
# 7. the window cuts old rows; at most 3 proposals; fills by price/book bucket
d = make(trader_counter=[{"ts": NOW - 10 * 3600}] * 9, quotes=[{"ts": ts(30), "event": "posted", "side": "bid", "offer": 7, "ratio": 0.85},
                                                                   {"ts": ts(20), "event": "filled", "side": "bid", "offer": 7}])
rep = R.analyze(d, NOW, 2)
assert rep["counters"]["sent"] == 0 and rep["quotes"]["by_ratio"] == {"0.8-1.0": [1, 1]} and len(rep["proposals"]) <= 3, rep; checks += 3
print(f"test_trader_review: {checks} checks passed")
