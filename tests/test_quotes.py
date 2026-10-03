"""bz/quotes and bz/guard on Saturday's real numbers. python3 tests/test_quotes.py"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from bz.guard import Guard  # noqa: E402
from bz.quotes import ask_price, bid_price, plan  # noqa: E402

BOOK = {"common": 10, "uncommon": 25, "rare": 70}
checks = 0

# prices: our real values at tick 561 (affinity RET 1.3, SAL 1.1, MAL 0.9)
assert bid_price(13.0, 10, "common") == 8                 # RET-02: market 0.8 of book, +5 for us
assert bid_price(27.5, 25, "uncommon") == 20              # SAL-06
assert bid_price(27.5, 25, "uncommon", best_other=22) == 23   # outbid another team, still under 27.5 - 2.75
assert bid_price(27.5, 25, "uncommon", best_other=30) == 24   # never above value - margin
assert bid_price(77.0, 70, "rare") == 68                  # SAL-09: rares trade near book
assert bid_price(63.0, 70, "rare") is None                # MAL-09: value - margin = 56 = 0.8 x book, below RARE_FLOOR 0.9
assert bid_price(1.5, 10, "common") is None               # nothing clears the margin
assert ask_price(4.0, 25, "uncommon") == 20               # a LAV-06 spare: worth 4 to us, the market pays ~20
checks += 8

RAR = {"SAL-06": "uncommon", "SAL-09": "rare", "SAL-10": "rare", "RET-02": "common", "RET-09": "rare",
       "MAL-06": "uncommon", "LAT-06": "uncommon", "LAV-06": "uncommon"}
VAL = {"SAL-06": 27.5, "SAL-09": 77.0, "SAL-10": 77.0, "RET-02": 13.0, "RET-09": 91.0, "MAL-06": 22.5, "LAT-06": 12.5}
missing = {"SAL": ["SAL-06", "SAL-09", "SAL-10"], "RET": ["RET-02", "RET-09"], "MAL": ["MAL-06"], "LAT": ["LAT-06"]}
pages = [{"set": "SAL", "have": 7, "of": 10}, {"set": "RET", "have": 4, "of": 10}, {"set": "MAL", "have": 6, "of": 10},
         {"set": "LAT", "have": 5, "of": 10}]
spares = [{"id": 704, "ref": "LAV-06", "your_value": 4.0}]
q = plan(missing, pages, spares, VAL.get, RAR.get, BOOK, {}, set(), budget=180)
bids = [x for x in q if x["side"] == "bid"]
assert [x["ref"] for x in bids[:3]] == ["SAL-06", "SAL-09", "SAL-10"], bids     # the page closest to completion first
assert sum(x["price"] for x in bids) <= 180, bids                               # never over the budget
assert all(x["gain"] >= 2 for x in bids), bids                                  # every bid gains at our values
assert "LAT-06" not in [x["ref"] for x in bids]                                 # 12.5 value: no price clears at market
assert q[-1] == {"side": "ask", "ref": "LAV-06", "price": 20, "value": 4.0, "gain": 16.0, "asset": 704, "ratio": 0.8}, q[-1]
assert all(x["ratio"] > 0 for x in q), q
checks += 5
# a card someone on our key already bids for is never bid again
q = plan(missing, pages, [], VAL.get, RAR.get, BOOK, {}, {"SAL-09"}, budget=500)
assert "SAL-09" not in [x["ref"] for x in q]; checks += 1
# a budget too small for a rare skips it but keeps the cheap bids
q = plan(missing, pages, [], VAL.get, RAR.get, BOOK, {}, set(), budget=40)
assert all(x["price"] <= 40 for x in q) and "RET-02" in [x["ref"] for x in q], q; checks += 1

# guard: wins, stops, holds
g = Guard()
g.score(24.2); g.fill(600, "SAL-06", "bid", 20, 27.5); g.score(31.7)
lv = [a[0] for a in g.drain()]
assert "WIN" in lv and "UP" in lv and not g.stopped, lv
g.fill(601, "MAL-04", "bid", 10, 9.0)                                           # a fill that lost value
assert g.stopped and "lost" in g.reason, g.reason; checks += 2
g = Guard(); g.score(24.2, 600); g.own_trade(598); g.score(20.0, 605)          # fell soon after a trade of ours: stop
assert g.stopped and "after a trade of ours" in g.reason; checks += 1
g = Guard()
for t in range(5):
    g.error(700 + t, "insufficient_cash")
assert g.stopped; checks += 1
g = Guard()
g.fill(800, "RET-09", "bid", 68, 91.0); g.fill(810, "SAL-09", "bid", 68, 77.0); g.fill(820, "SAL-10", "bid", 68, 77.0)
assert not g.stopped
g.fill(830, "RET-10", "bid", 68, 91.0)                                          # 272 P in 30 ticks > 250
assert g.stopped and "spent" in g.reason, g.reason
assert Guard().may_bid(150) and Guard().may_bid(20) and not Guard().may_bid(10); checks += 2   # floor is 15 now
# ---- 14:xx changes: floor 15, earmark, score-drop attribution, reset, scaling, hand-buy exclusion
import tempfile  # noqa: E402
from bz.guard import bid_budget, earmark_total, spend_allowed, tick_scale  # noqa: E402

# floor and earmark: Saturday 17:xx, cash 27. No budget today, with or without the earmark.
assert bid_budget(27, 0, 180, 0) == 12 and bid_budget(27, 0, 180, 60) == 0
# Sunday: cash 177 after the 150 P allowance. Earmark 60 + floor 15 leave 102 for standing bids.
assert bid_budget(177, 0, 180, 60) == 102 and bid_budget(177, 0, 180, 0) == 162 and bid_budget(500, 0, 180, 60) == 180
assert bid_budget(177, 40, 180, 60) == 62                       # other open bids' cash comes off first
checks += 4
# the earmark releases the moment we hold the card
assert earmark_total({"RET-09": 60}, set()) == 60 and earmark_total({"RET-09": 60}, {"RET-09"}) == 0
assert earmark_total({}, set()) == 0 and earmark_total({"RET-09": 60, "SAL-09": 70}, {"SAL-09"}) == 60; checks += 2
# what the earmark may block: only a real spend that would leave less than the earmark
assert spend_allowed(2, 27, 60)            # a swap fee: never blocked
assert spend_allowed(5, 27, 60)            # at the 5 P line
assert not spend_allowed(11, 27, 60)       # a small win would eat into the 60
assert spend_allowed(-65, 27, 60)          # money coming in (a sale accepted)
assert spend_allowed(0, 27, 60)            # a card-for-card swap with no fee
assert spend_allowed(40, 177, 60) and not spend_allowed(120, 177, 60)  # 177 - 120 = 57 < 60
checks += 6

# the score-drop stopper: a drop soon after OUR trade stops us; a drop with no trade of ours is only an alert
g = Guard(); g.score(29.1, 605); g.score(19.1, 608)                  # Saturday tick 608: nothing of ours happened
assert not g.stopped and [a[0] for a in g.drain()] == ["SCORE-DROP"]; checks += 1
g = Guard(); g.score(29.1, 600); g.own_trade(597); g.score(19.1, 608)  # a trade of ours 11 ticks earlier: blamed
assert g.stopped; checks += 1
g = Guard(); g.score(29.1, 600); g.own_trade(560); g.score(19.1, 608)  # our last trade was 48 ticks ago: not blamed
assert not g.stopped; checks += 1
g = Guard(scale=2.0); g.score(29.1, 600); g.own_trade(580); g.score(19.1, 608)  # 15 s ticks: the lag window doubles (30 ticks)
assert g.stopped
g = Guard(scale=1.0); g.score(29.1, 600); g.own_trade(580); g.score(19.1, 608)  # the same 28 ticks at 30 s: outside the 15-tick window
assert not g.stopped; checks += 2
g = Guard(); g.score(14.2, 700); g.own_trade(690); g.score(14.2, 710); g.score(14.4, 712)
assert not g.stopped; checks += 1                                          # a flat or rising score never stops us

# reset: a stop clears, errors are forgotten, the spend history stays so a spending stop returns at once
g = Guard()
for i in range(5):
    g.error(700 + i, "x")
assert g.stopped
g.drain(); g.reset()
assert not g.stopped and g.errors == [] and [a[0] for a in g.drain()] == ["RESUME"]
g.fill(800, "A", "bid", 100, 150.0); g.fill(801, "B", "bid", 100, 150.0); g.fill(802, "C", "bid", 100, 150.0)
assert g.stopped and "spent" in g.reason                                     # 300 P within the window
g.drain(); g.reset(); g.fill(803, "D", "bid", 5, 20.0)
assert g.stopped, "the spend history must survive a reset"; checks += 3

# a trader accept that settles worse than planned: the guard sees it (before, only quoter fills were checked)
g = Guard(); g.accept_result(900, "accept of offer 1", 20.5, 2); assert not g.stopped and "WIN" in [a[0] for a in g.drain()]
g.accept_result(901, "accept of offer 2", -1.5, 11); assert g.stopped and "lost 1.5" in g.reason; checks += 2

# windows scale with the tick length
assert tick_scale(30) == 1.0 and tick_scale(15) == 2.0 and tick_scale(60) == 0.5 and tick_scale(None) == 1.0; checks += 1
g = Guard(scale=2.0)
g.fill(100, "A", "bid", 200, 300.0); g.fill(200, "B", "bid", 100, 300.0)    # 100 ticks apart: inside 240 at 15 s, outside 120 at 30 s
assert g.stopped
g = Guard(scale=1.0)
g.fill(100, "A", "bid", 200, 300.0); g.fill(250, "B", "bid", 100, 300.0)    # 150 ticks apart: outside 120
assert not g.stopped; checks += 2

# trader helpers: the earmark text, the budget per hour read from the log, and the realized gain of an accept
import trader  # noqa: E402
assert trader.parse_earmark("RET-09:60") == {"RET-09": 60} and trader.parse_earmark("none") == {} and trader.parse_earmark("") == {}
assert trader.parse_earmark("RET-09:60, SAL-09:70") == {"RET-09": 60, "SAL-09": 70} and trader.parse_earmark("RET-09") == {}
checks += 2
import json  # noqa: E402
with tempfile.TemporaryDirectory() as d:
    path = os.path.join(d, "acc.jsonl")
    with open(path, "w") as f:
        for tick, src, cash, fee in ((100, "board", 9, 2), (150, "board", 9, 2), (170, "to_us", 50, 2), (210, "board", 20, 2)):
            f.write(json.dumps({"tick": tick, "source": src, "cash_out": cash, "fee": fee}) + "\n")
    assert trader.spent_recent(215, 120, path) == 44          # ticks 100 (115 away), 150 and 210: 11 + 11 + 22; the to_us accept is not a board spend
    assert trader.spent_recent(215, 60, path) == 22           # only tick 210 is within 60 ticks (150 is 65 away)
    assert trader.spent_recent(215, 240, path) == 44 and trader.spent_recent(300, 60, path) == 0
checks += 3
buy = {"cash_in": 0, "cash_out": 9, "fee": 2, "surplus": 5.0}
assert trader.realized_gain(buy, {"price": 9, "fee": 2}) == (5.0, 11)           # as planned
assert trader.realized_gain(buy, {"price": 9, "fee": 3}) == (4.0, 12)           # the game charged 1 P more fee
assert trader.realized_gain(buy, {"price": 12, "fee": 2})[0] == 2.0
swap = {"cash_in": 0, "cash_out": 0, "fee": 2, "surplus": 20.5}
assert trader.realized_gain(swap, {"price": 0, "fee": 2}) == (20.5, 2)
sale = {"cash_in": 70, "cash_out": 0, "fee": 5, "surplus": 2.0}
assert trader.realized_gain(sale, {"price": 70, "fee": 5}) == (2.0, 0)
checks += 5
# ---- spares: a copy already in an open offer counts as sold (RET-01 / RET-08 / SAL-02 at tick 1041)
from bz.quotes import free_spares  # noqa: E402
c = lambda i, ref, v=3.0: {"id": i, "ref": ref, "your_value": v}  # noqa: E731
two = {"RET-01": [c(1, "RET-01"), c(2, "RET-01")]}
assert [a["id"] for a in free_spares(two, set())] == [1]            # 2 copies, nothing listed: one spare (lowest id on a tie)
assert free_spares(two, {1}) == [] and free_spares(two, {2}) == []   # one copy already listed: NO spare left, whichever copy
assert free_spares(two, {1, 2}) == []
three = {"X": [c(1, "X", 9.0), c(2, "X", 3.0), c(3, "X", 1.0)]}
assert [a["id"] for a in free_spares(three, set())] == [3, 2]       # 3 copies: two spares, cheapest first
assert [a["id"] for a in free_spares(three, {3})] == [2]            # one listed: one spare left
assert free_spares({"Y": [c(1, "Y")]}, set()) == []                 # a single copy is never a spare
checks += 6
print(f"test_quotes: {checks} checks passed")
