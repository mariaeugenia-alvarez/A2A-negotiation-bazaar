"""Fixes A, B, C of tick 1445 (self-outbid, far sell counters, low rare bids). python3 tests/test_trader_fixes.py"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from trader import MAX_COUNTER_RATIO, counter_too_far, record_bids  # noqa: E402
from bz.quotes import bid_price  # noqa: E402

checks = 0
# A. our own bid on the board (pseudonym maker) is not another team's bid; a real other bid is
board = [{"id": 19855, "maker": "m4000a5c3", "give": {"cash": 24}, "want": {"types": ["card:SAL-06"]}},
         {"id": 20001, "maker": "m77", "give": {"cash": 22}, "want": {"types": ["card:SAL-06"]}},
         {"id": 20002, "maker": "t09", "give": {"cash": 30}, "want": {"types": ["card:SAL-10"]}}]
bids = {}
record_bids(bids, board, {19855}, "t09", 1300)
assert bids == {"SAL-06": [(1300, 22)]}, bids; checks += 1
bids = {}
record_bids(bids, board, set(), "t09", 1300)                       # the old behaviour: our 24 counted, the cause of 20 -> 24
assert max(p for _, p in bids["SAL-06"]) == 24; checks += 1
# with only our own bid on the board, the quoter no longer prices against itself: same price as with no bid
assert bid_price(27.5, 25, "uncommon", 0) == 20 and bid_price(27.5, 25, "uncommon", 24) == 24; checks += 1

# B. sell counters: the real cases of tick 1203 (161 for their 20) and 320 (65 for their 56)
assert MAX_COUNTER_RATIO == 1.25
assert counter_too_far({"cash_in": 20, "cash_out": 0}, 161) is True
assert counter_too_far({"cash_in": 4, "cash_out": 0}, 6) is True        # 1.5 x: 12 sent to t08 and t13, none accepted
assert counter_too_far({"cash_in": 56, "cash_out": 0}, 65) is False      # 1.16 x: accepted on Saturday
assert counter_too_far({"cash_in": 12, "cash_out": 0}, 14) is False
assert counter_too_far({"cash_in": 0, "cash_out": 15}, 10) is False      # a BUY counter is not limited here
assert counter_too_far({"cash_in": 20}, None) is False; checks += 7

# C. rare bids below 0.9 x book: none; uncommon and common floors unchanged
assert bid_price(63.0, 70, "rare", 0) is None                             # MAL-09/10: top 56 = 0.8 x book
assert bid_price(77.0, 70, "rare", 0) == 68                               # SAL-10: 0.97 x book, still posted
assert bid_price(90.0, 80, "epic", 0) is None                             # market ref 0.8 x 80 = 64 < 0.9 x 80 = 72
assert bid_price(90.0, 80, "epic", 75) == 76                              # another team bids 75: 76 clears both rules
assert bid_price(27.5, 25, "uncommon", 0) == 20 and bid_price(9.0, 10, "common", 0) == 7   # floors 0.5: unchanged
checks += 5
print(f"test_trader_fixes: {checks} checks passed")

# D. hard rule 2: never give our last free copy of a card (the real LAV-06 counter of tick 1203)
from bz.trade import judge  # noqa: E402


class V:
    def lose(self, a):
        return a["your_value"]

    def gain(self, ref):
        return 10.0


LAV = {"LAV-06": [{"id": 693, "ref": "LAV-06", "your_value": 146.0}]}
RET = {"RET-01": [{"id": 706, "ref": "RET-01", "your_value": 3.2}, {"id": 984, "ref": "RET-01", "your_value": 3.2}]}
buy = lambda ref, cash, oid=1: {"id": oid, "maker": "t12", "venue": "v11", "status": "open", "give": {"cash": cash},  # noqa: E731
                                "want": {"types": [f"card:{ref}"]}}
d = judge(buy("LAV-06", 20), V(), LAV, 351, {}, {}, "t09")
assert d["action"] == "ignore" and "hard rule 2" in d["why"], d                 # was "counter at 161"
d = judge(buy("LAV-06", 300), V(), LAV, 351, {}, {}, "t09")
assert d["action"] == "ignore", d                                               # not even far above its value
named = {"id": 2, "maker": "t12", "venue": "v11", "status": "open", "give": {"cash": 300}, "want": {"assets": [{"id": 693, "kind": "card", "ref": "LAV-06"}]}}
assert judge(named, V(), LAV, 351, {}, {}, "t09")["action"] == "ignore"          # asked by asset id: same rule
d = judge(buy("RET-01", 9), V(), RET, 351, {}, {}, "t09")
assert d["action"] == "accept", d                                               # a spare copy: still sold (9 - 3.2 - 0 fee)
d = judge(buy("RET-01", 9), V(), RET, 351, {}, {}, "t09", reserved={706})
assert d["action"] == "ignore" and "last free copy" in d["why"], d             # the spare is already in our open ask
checks += 5
print(f"test_trader_fixes (with D): {checks} checks passed")

# E. a counter is settled only by a trade with the SAME team (tick 1057: counter to t13, RET-08 sold to t07)
from trader import settlement_for  # noqa: E402


class FeedB:
    def feed(self, limit=300):
        return {"events": [{"type": "settlement", "payload": {"tick": 1057, "parties": ["t09", "t07"], "price": 24,
                                                              "items": [{"ref": "RET-08"}]}}]}


assert settlement_for(FeedB(), "t09", {"RET-08"}, 1055, party="t13") is None
assert settlement_for(FeedB(), "t09", {"RET-08"}, 1055, party="t07")["price"] == 24
assert settlement_for(FeedB(), "t09", {"RET-08"}, 1055)["price"] == 24      # no party given: old behaviour (quotes, accepts)
checks += 3

# D2 (Thameur, 2026-10-04): the rule protects complete pages and the page we complete (RET); another single copy may go
# when the gain is at least 20 % of its value (SINGLE_SHARE)
from bz.trade import SINGLE_SHARE  # noqa: E402
F0 = {"v11": (0, 0)}  # the buyer pays the fee when THEY accept our ask; here a 0 % venue keeps the numbers plain
MISS = {"LAV": [], "RET": ["RET-09"], "LAT": ["LAT-07", "LAT-09"], "MAL": ["MAL-09"]}
LAT = {"LAT-06": [{"id": 50, "ref": "LAT-06", "your_value": 11.0}]}
RET8 = {"RET-08": [{"id": 51, "ref": "RET-08", "your_value": 32.5}]}
MAL8 = {"MAL-08": [{"id": 52, "ref": "MAL-08", "your_value": 63.0}]}
assert SINGLE_SHARE == 0.20
d = judge(buy("LAT-06", 20), V(), LAT, 351, F0, MISS, "t09")
assert d["action"] == "accept" and d["surplus"] == 9.0, d                         # the real LAT-06 sale: +9.0 on 11 (82 %)
d = judge(buy("RET-08", 60), V(), RET8, 351, F0, MISS, "t09")
assert d["action"] == "ignore" and "protected" in d["why"], d                     # El Retiro: never, even at 60 for 32.5
assert judge(buy("RET-08", 60), V(), RET8, 351, F0, MISS, "t09", protect=frozenset())["action"] == "accept"   # flag cleared
d = judge(buy("MAL-08", 65), V(), MAL8, 351, F0, MISS, "t09", guard={})
assert d["action"] == "counter" and d["counter_cash"] == 76, d                    # no guard: 20 % -> 63 + 12.6 = 76
d = judge(buy("MAL-08", 76), V(), MAL8, 351, F0, MISS, "t09", guard={})
assert d["action"] == "accept", d                                                  # 76 - 63 = 13 >= 12.6
assert judge(buy("LAV-06", 300), V(), LAV, 351, F0, MISS, "t09")["action"] == "ignore"   # complete page: never
assert judge(buy("LAT-06", 20), V(), LAT, 351, F0, {}, "t09")["action"] == "ignore"      # page state unknown: never
checks += 8

# D3 (Thameur, 2026-10-04): Salamanca and Malasana guarded at 50 % until the team decides; complete pages found by themselves
from trader import complete_pages, parse_guard  # noqa: E402
d = judge(buy("MAL-08", 76), V(), MAL8, 351, F0, MISS, "t09")
assert d["action"] == "counter" and d["counter_cash"] == 95, d                    # default guard MAL 0.5: 63 + 31.5 -> 95
assert judge(buy("MAL-08", 95), V(), MAL8, 351, F0, MISS, "t09")["action"] == "accept"   # 95 - 63 = 32 >= 31.5
assert judge(buy("LAT-06", 20), V(), LAT, 351, F0, MISS, "t09")["action"] == "accept"    # La Latina: 20 % still
assert parse_guard("SAL:0.5,MAL:0.5") == {"SAL": 0.5, "MAL": 0.5} and parse_guard("none") == {} and parse_guard("") == {}
assert complete_pages({"LAV": [], "RET": ["RET-09"], "MAL": ["MAL-09"]}) == {"LAV"}
assert complete_pages({"LAV": [], "RET": []}) == {"LAV", "RET"}                    # El Retiro done: protected with no flag
RET9 = {"RET-09": [{"id": 60, "ref": "RET-09", "your_value": 177.1}]}
assert judge(buy("RET-09", 400), V(), RET9, 351, F0, {"RET": []}, "t09", protect=frozenset())["action"] == "ignore"
checks += 7
print(f"test_trader_fixes (with D3): {checks} checks passed")
