"""bz/tape on the real settlement shape of the feed. python3 tests/test_tape.py"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from bz.tape import alerts_for, reference_price, summarize, trade_of  # noqa: E402

BOOK = {"common": 10, "uncommon": 25, "rare": 70}
RAR = {"RET-08": "uncommon", "RET-02": "common", "SAL-09": "rare"}


def ev(i, tick, parties, price, items, venue="rastro", persona=None, fee=0, kind="trade"):
    return {"id": i, "tick": tick, "type": "settlement", "payload": {"settlement": i, "tick": tick, "kind": kind, "parties": parties,
            "venue": venue, "persona": persona, "fee": fee, "price": price, "items": items}}


def card(ref, frm, to, rar=None):
    return {"id": 1, "kind": "card", "ref": ref, "rarity": rar or RAR.get(ref), "frm": frm, "to": to}


checks = 0
# the real RET-08 sale of Saturday: 24 P to Team 7, an uncommon (book 25): 0.96 of book
t = trade_of(ev(1, 1057, ["t09", "t07"], 24, [card("RET-08", "t09", "t07")], fee=3), BOOK, RAR)
assert t["kind"] == "team" and t["venue"] == "rastro" and t["price"] == 24 and t["ratio"] == 0.96 and t["fee"] == 3, t
# a dealer trade, a pack, a bundle and other events
d = trade_of(ev(2, 1060, ["picaros", "t14"], 57, [card("SAL-09", "picaros", "t14")], venue=None, persona="picaros"), BOOK, RAR)
assert d["kind"] == "dealer" and d["persona"] == "picaros" and d["ratio"] == 0.81, d
p = trade_of(ev(3, 1061, ["abuela", "t07"], 21, [{"id": 5, "kind": "pack", "ref": "sobre_barrio", "frm": "abuela", "to": "t07"}], venue=None, persona="abuela"), BOOK, RAR)
assert p["ratio"] is None and p["cards"][0]["kind"] == "pack"
bundle = trade_of(ev(4, 1062, ["t01", "t02"], 30, [card("RET-08", "t01", "t02"), card("RET-02", "t01", "t02")]), BOOK, RAR)
assert bundle["ratio"] is None and len(bundle["cards"]) == 2
assert trade_of({"type": "offer.listed", "payload": {}}, BOOK, RAR) is None
assert trade_of(ev(5, 1, ["a", "b"], 1, [], kind="fee"), BOOK, RAR) is None            # not a trade
checks += 6

# reference price: median of the last 5 TEAM trades of one card within the window; dealers and bundles do not count
ts = [trade_of(ev(10 + i, 1000 + 20 * i, ["t01", "t02"], pr, [card("RET-08", "t01", "t02")]), BOOK, RAR) for i, pr in enumerate([30, 20, 22, 24, 26, 18])]
ts.append(trade_of(ev(30, 1110, ["picaros", "t03"], 5, [card("RET-08", "picaros", "t03")], venue=None, persona="picaros"), BOOK, RAR))
assert reference_price(ts, "RET-08", 1110) == 22                                           # last five team prices 20, 22, 24, 26, 18
assert reference_price(ts, "RET-08", 1110, window=30) == 22 and reference_price(ts, "RET-08", 1110, window=5) is None
assert reference_price(ts, "RET-08", 2000) is None                                         # too old
assert reference_price(ts, "RET-02", 1110) is None                                         # never traded
assert reference_price(ts, "RET-08", 1110, n=2) == 22                                      # last two: 26 and 18
checks += 1
checks += 3

# alerts: a card we still need that traded, a spare that traded; nothing for other cards, dealers or bundles
val = {"RET-02": 13.0, "RET-08": 8.1}.get
a = alerts_for(trade_of(ev(40, 1200, ["t01", "t02"], 8, [card("RET-02", "t01", "t02")]), BOOK, RAR), {"RET-02"}, set(), val)
assert a == [("TAPE-NEED", "RET-02 (we need it) traded at 8 P on rastro: our value 13.0, gain about +5.0 P")], a
a = alerts_for(trade_of(ev(41, 1201, ["t01", "t02"], 24, [card("RET-08", "t01", "t02")]), BOOK, RAR), set(), {"RET-08"}, val)
assert a and a[0][0] == "TAPE-SPARE" and "24 P" in a[0][1] and "8.1" in a[0][1], a
assert alerts_for(trade_of(ev(42, 1202, ["t01", "t02"], 9, [card("RET-02", "t01", "t02")]), BOOK, RAR), set(), set(), val) == []
assert alerts_for(d, {"SAL-09"}, set(), lambda r: 77.0) == []                               # a dealer trade is not a team price
assert alerts_for(bundle, {"RET-08"}, set(), val) == []
checks += 5

# summary: venues, rarities, buyers and sellers, dealers
tr = [trade_of(ev(50, 1300, ["t01", "t02"], 24, [card("RET-08", "t01", "t02")], fee=3), BOOK, RAR),
      trade_of(ev(51, 1301, ["t03", "t04"], 20, [card("RET-08", "t03", "t04")], venue="v07"), BOOK, RAR),
      trade_of(ev(52, 1302, ["t01", "t05"], 9, [card("RET-02", "t01", "t05")]), BOOK, RAR), d]
s = summarize(tr)
assert s["team_trades"] == 3 and s["dealer_trades"] == 1, s
assert s["venues"] == {"rastro": [2, 33], "v07": [1, 20]} and s["rarity_ratio"] == {"uncommon": (0.88, 2), "common": (0.9, 1)}, s
assert s["sellers"]["t01"] == 2 and s["buyers"] == {"t02": 1, "t04": 1, "t05": 1} and s["dealers"] == {"picaros": [1, 57]}, s
assert summarize(tr, since_tick=1302)["team_trades"] == 1
checks += 4
print(f"test_tape: {checks} checks passed")
