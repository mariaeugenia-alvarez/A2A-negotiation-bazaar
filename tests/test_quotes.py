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
assert bid_price(63.0, 70, "rare") == 56                  # MAL-09: value - margin caps it below the market
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
assert q[-1] == {"side": "ask", "ref": "LAV-06", "price": 20, "value": 4.0, "gain": 16.0, "asset": 704}, q[-1]
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
g = Guard(); g.score(24.2); g.score(20.0)
assert g.stopped and "fell" in g.reason; checks += 1
g = Guard()
for t in range(5):
    g.error(700 + t, "insufficient_cash")
assert g.stopped; checks += 1
g = Guard()
g.fill(800, "RET-09", "bid", 68, 91.0); g.fill(810, "SAL-09", "bid", 68, 77.0); g.fill(820, "SAL-10", "bid", 68, 77.0)
assert not g.stopped
g.fill(830, "RET-10", "bid", 68, 91.0)                                          # 272 P in 30 ticks > 250
assert g.stopped and "spent" in g.reason, g.reason
assert Guard().may_bid(150) and not Guard().may_bid(80); checks += 2
print(f"test_quotes: {checks} checks passed")
