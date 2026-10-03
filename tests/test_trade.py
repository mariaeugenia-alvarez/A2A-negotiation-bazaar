"""bz/trade.judge on the offers we really saw, and on the mistakes of Saturday morning. python3 tests/test_trade.py"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from bz.price import Valuer  # noqa: E402
from bz.trade import anchor, cost, counter_body, is_lowball, judge  # noqa: E402

RARITIES = {"common": {"book": 10}, "uncommon": {"book": 25}, "rare": {"book": 70}}
CATALOG = {
    "rarities": RARITIES, "values": {"copy_marginals": [1.0, 0.25, 0.1]}, "packs": [],
    "sets": [{"id": "LAV", "released": True, "cards": [{"id": "LAV-01", "rarity": "common"}, {"id": "LAV-02", "rarity": "common"},
                                                      {"id": "LAV-03", "rarity": "common"}]},
             {"id": "MAL", "released": True, "cards": [{"id": "MAL-10", "rarity": "rare"}]}],
}
AFF = {"LAV": 1.6, "MAL": 0.9}
FEES = {"rastro": (500, 1), "v02": (0, 0), "v07": (0, 0)}
MISSING = {"LAV": ["LAV-02", "LAV-03"], "MAL": []}


class Game:
    """Values as the game reports them (page bonus included): your_value on each held asset, a table for new copies."""
    def __init__(self, held, gains):
        self.by_id, self.gains = {a["id"]: a for a in held}, gains

    def lose(self, asset):
        return self.by_id[asset["id"]]["your_value"]

    def gain(self, ref):
        return self.gains[ref]


def card(i, ref, kind="card", value=None):
    a = {"id": i, "kind": kind, "ref": ref}
    if value is not None:
        a["your_value"] = value
    return a


def by_ref_of(held):
    out = {}
    for a in held:
        out.setdefault(a["ref"], []).append(a)
    return out


def run(offer, held, cash=300, missing=None, values=None, reserved=frozenset()):
    by_ref = by_ref_of(held)
    if values is None:
        values = Valuer(CATALOG, AFF, {r: len(c) for r, c in by_ref.items()})
    return judge(offer, values, by_ref, cash, FEES, MISSING if missing is None else missing, "t09", reserved)


def offer(give, want, venue="rastro", maker="t05", status="open"):
    return {"id": 1, "maker": maker, "to": "t09", "venue": venue, "status": status,
            "give": {"cash": 0, "assets": [], "types": [], **give}, "want": {"cash": 0, "assets": [], "types": [], **want}}


checks = 0
# 1. Team 5's real offer: a second LAV-02 for 9-10 P, worth 4 P to us. Never accept. Our counter (they would pay
#    the fee) clears at 2 P: a probe under half their ask, which trader.py rations.
a = run(offer({"assets": [card(486, "LAV-02")]}, {"cash": 10}), [card(127, "LAV-02")])
assert a["action"] == "counter" and a["got"] == 4.0 and a["counter_cash"] == 2 and is_lowball(a, anchor(a)), a; checks += 1

# 2. MAL-10 (held, worth 63). Friday's 45 bid: counter. 75 and 82 clear even when WE accept and pay the fee.
held = [card(135, "MAL-10")]
a = run(offer({"cash": 45}, {"types": ["card:MAL-10"]}, maker="t13"), held)
assert a["action"] == "counter" and a["counter_cash"] == 70, a; checks += 1          # 63 + margin 6.3, no fee: they accept
for price in (75, 82):
    a = run(offer({"cash": price}, {"types": ["card:MAL-10"]}, maker="t10"), held)
    assert a["action"] == "accept" and a["assets"] == [135], a; checks += 1

# 3. THE MAL-10 MISTAKE: Team 13 bid 56 and we sold at 65 while bids of 70 (Team 17, standing) and 82 had been seen.
#    With the best recent bid passed in, the counter opens above it.
a = run(offer({"cash": 56}, {"types": ["card:MAL-10"]}, maker="t13"), held)
assert anchor(a) == 70 and anchor(a, best_bid=82) == 83, (a, anchor(a, best_bid=82)); checks += 1

# 4. THE DOUBLE-OFFER MISTAKE: a card already in one of our open offers is never offered or handed over again
a = run(offer({"cash": 90}, {"types": ["card:MAL-10"]}, maker="t17"), held, reserved={135})
assert a["action"] == "ignore" and "another open offer" in a["why"], a; checks += 1
two = [card(135, "MAL-10"), card(136, "MAL-10")]
a = run(offer({"cash": 40}, {"types": ["card:MAL-10"]}, venue="v02"), two, reserved={136})
assert a["assets"] == [135], a; checks += 1                                          # the free copy, not the reserved one

# 5. THE DEALER MISTAKE: offers from dealers (or with no venue: dealer threads) are never ours
for maker, venue in (("abuela", None), ("chato", None), ("abuela", "rastro"), ("t05", None)):
    a = run(offer({"cash": 6}, {"assets": [card(127, "LAV-02")]}, maker=maker, venue=venue), [card(127, "LAV-02")])
    assert a["action"] == "ignore" and "dealer" in a["why"], a; checks += 1

# 6. THE PAGE-BONUS DANGER: with Lavapies complete the game values our single LAV-01 at 122 (16 + 25 % of the page).
#    Our formula says 16. A 40 P bid must be refused with game values; the formula would have sold it.
page = [card(201, "LAV-01", value=122.0)]
bid = offer({"cash": 40}, {"types": ["card:LAV-01"]}, venue="v02", maker="t12")
assert run(bid, page)["action"] == "accept"                                          # formula: 16 + margin < 40: SELLS
a = run(bid, page, values=Game(page, {}))
assert a["action"] == "counter" and a["lost"] == 122.0 and a["counter_cash"] >= 135, a; checks += 2
# a spare copy of a page card carries no bonus: the game values it low, and selling it is fine
spare = [card(301, "LAV-02", value=4.0), card(302, "LAV-02", value=4.0)]
a = run(offer({"cash": 8}, {"types": ["card:LAV-02"]}, venue="v02"), spare, values=Game(spare, {}))
assert a["action"] == "accept" and a["lost"] == 4.0, a; checks += 1

# 7. ownership and cash
a = run(offer({"cash": 82}, {"types": ["card:MAL-10"]}), [])
assert a["action"] == "ignore", a
a = run(offer({"cash": 82}, {"assets": [card(999, "MAL-10")]}), held)
assert a["action"] == "ignore", a
a = run(offer({"assets": [card(5, "LAV-03")]}, {"cash": 50}), held, cash=20)
assert a["action"] == "ignore", a; checks += 3

# 8. a card that completes a page, a pack, an unknown type, several copies of one card, the same card both ways: a person
assert run(offer({"assets": [card(7, "LAV-03")]}, {"cash": 5}), [], missing={"LAV": ["LAV-03"]})["action"] == "human"
assert run(offer({"assets": [card(8, "sobre_barrio", kind="pack")]}, {"cash": 5}), [])["action"] == "human"
assert run(offer({"cash": 5}, {"types": ["rarity:rare"]}), held)["action"] == "human"
assert run(offer({"cash": 80}, {"types": ["card:MAL-10", "card:MAL-10"]}), two)["action"] == "human"
assert run(offer({"assets": [card(9, "MAL-10")]}, {"types": ["card:MAL-10"]}), held)["action"] == "human"
checks += 5

# 9. our own offers and expired ones are skipped
assert run(offer({"cash": 82}, {"types": ["card:MAL-10"]}, maker="t09"), held)["action"] == "ignore"
assert run(offer({"cash": 82}, {"types": ["card:MAL-10"]}, status="expired"), held)["action"] == "ignore"; checks += 2

# 10. public asks: the fee is ours when we accept (El Rastro 2 P on a 9 P card), nothing on a 0 % venue
pub = offer({"assets": [card(61, "LAV-03")]}, {"cash": 9}, maker="m1"); pub["to"] = None
a = run(pub, [])
assert a["action"] == "accept" and a["fee"] == 2 and a["surplus"] == 5.0 and cost(a) == 11, a
a0 = run({**pub, "venue": "v02"}, [])
assert a0["fee"] == 0 and a0["surplus"] == 7.0, a0; checks += 2

# 11. counter bodies: a sale hands over the chosen copy; a buy asks for the card; a swap gets no cash-only counter
o17 = offer({"cash": 70}, {"types": ["card:MAL-10"]}, maker="t17")
a = run(o17, held)  # accepting nets 70 - 63 - 5 fee = +2 < 6.3; the same 70 posted by US nets +7: they pay the fee
assert a["action"] == "counter" and a["counter_cash"] == 70 and anchor(a) == 81, a
assert counter_body(o17, a, 81) == {"give": {"assets": [135]}, "want": {"cash": 81}}, a
swap = offer({"cash": 10, "assets": [card(70, "LAV-03")]}, {"types": ["card:MAL-10"]})
d = run(swap, held)
assert d["action"] != "counter" or counter_body(swap, d, anchor(d) or 1) is None, d; checks += 3
# 12. our own open bids (posted in bulk at tick 378): a card we already bid for goes to a person, never bought twice
from bz.trade import wanted_refs  # noqa: E402
ask = offer({"assets": [card(80, "LAV-03")]}, {"cash": 5}, venue="v02", maker="t06")
assert run(ask, [])["action"] == "accept"
d = judge(ask, Valuer(CATALOG, AFF, {}), {}, 300, FEES, MISSING, "t09", pending={"LAV-03"})
assert d["action"] == "human" and "already bid" in d["why"], d
assert wanted_refs({"want": {"cards": ["RET-02"]}}) == ["RET-02"]
assert wanted_refs({"want": {"types": ["card:MAL-06"], "assets": [{"ref": "SAL-01"}]}}) == ["MAL-06", "SAL-01"]; checks += 3
print(f"test_trade: {checks} checks passed")
