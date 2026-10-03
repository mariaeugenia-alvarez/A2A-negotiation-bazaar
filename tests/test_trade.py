"""bz/trade.judge on the offers we really saw. python3 tests/test_trade.py"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from bz.price import Valuer  # noqa: E402
from bz.trade import judge  # noqa: E402

RARITIES = {"common": {"book": 10}, "uncommon": {"book": 25}, "rare": {"book": 70}}
CATALOG = {
    "rarities": RARITIES, "values": {"copy_marginals": [1.0, 0.25, 0.1]}, "packs": [],
    "sets": [{"id": "LAV", "released": True, "cards": [{"id": "LAV-02", "rarity": "common"}, {"id": "LAV-03", "rarity": "common"}]},
             {"id": "MAL", "released": True, "cards": [{"id": "MAL-10", "rarity": "rare"}]}],
}
AFF = {"LAV": 1.6, "MAL": 0.9}
FEES = {"rastro": (500, 1), "v02": (0, 0)}


def card(i, ref, kind="card"):
    return {"id": i, "kind": kind, "ref": ref}


def run(offer, held, cash=300, missing=None):
    by_ref = {}
    for a in held:
        by_ref.setdefault(a["ref"], []).append(a)
    valuer = Valuer(CATALOG, AFF, {r: len(c) for r, c in by_ref.items()})
    return judge(offer, valuer, by_ref, cash, FEES, missing or {"LAV": ["LAV-02", "LAV-03"], "MAL": []}, "t09")


def offer(give, want, venue="rastro", maker="t05", status="open"):
    return {"id": 1, "maker": maker, "to": "t09", "venue": venue, "status": status,
            "give": {"cash": 0, "assets": [], "types": [], **give}, "want": {"cash": 0, "assets": [], "types": [], **want}}


checks = 0
# 1. Team 5's real offer: a second LAV-02 for 10 P. The next copy is worth 4 P, so we pay 10 for 4: no.
#    No price clears a 2 P margin plus the fee, so there is nothing to counter either.
a = run(offer({"assets": [card(486, "LAV-02")]}, {"cash": 10}), [card(127, "LAV-02")])
assert a["action"] == "ignore" and a["got"] == 4.0 and a["surplus"] < 0, a; checks += 1
# 2. Friday's MAL-10 bids (we hold one, worth 63): 45 is too low, 75 and 82 clear it after the 5 % + 1 P fee
held = [card(135, "MAL-10")]
a = run(offer({"cash": 45}, {"types": ["card:MAL-10"]}, maker="t13"), held)
assert a["action"] == "counter" and a["counter_cash"] > 63, a; checks += 1
for price in (75, 82):
    a = run(offer({"cash": price}, {"types": ["card:MAL-10"]}, maker="t10"), held)
    assert a["action"] == "accept" and a["assets"] == [135], a
    assert abs(a["surplus"] - (price - 63 - (-(-price * 500 // 10000) + 1))) < 0.11, a; checks += 1
# 3. we hold no copy: never accept (a sale of a card we no longer have ends in not_owner)
a = run(offer({"cash": 82}, {"types": ["card:MAL-10"]}), [])
assert a["action"] == "ignore", a; checks += 1
# 4. a named copy that is not ours, and an offer we cannot pay
a = run(offer({"cash": 82}, {"assets": [card(999, "MAL-10")]}), held)
assert a["action"] == "ignore", a; checks += 1
a = run(offer({"assets": [card(5, "LAV-03")]}, {"cash": 50}), held, cash=20)
assert a["action"] == "ignore", a; checks += 1
# 5. with two copies we hand over a spare, and the loss is the second copy's value (17.5), not the first's (63)
held2 = [card(135, "MAL-10"), card(136, "MAL-10")]
a = run(offer({"cash": 40}, {"types": ["card:MAL-10"]}, venue="v02"), held2)
assert a["action"] == "accept" and a["lost"] == 15.8 and a["assets"] == [136], a; checks += 1
# 6. a card that completes a page, a pack and an unknown type go to a person
a = run(offer({"assets": [card(7, "LAV-03")]}, {"cash": 5}), [], missing={"LAV": ["LAV-03"], "MAL": []})
assert a["action"] == "human", a; checks += 1
a = run(offer({"assets": [card(8, "sobre_barrio", kind="pack")]}, {"cash": 5}), [])
assert a["action"] == "human", a; checks += 1
a = run(offer({"cash": 5}, {"types": ["rarity:rare"]}), held)
assert a["action"] == "human", a; checks += 1
# 7. our own offers and expired ones are skipped
a = run(offer({"cash": 82}, {"types": ["card:MAL-10"]}, maker="t09"), held)
assert a["action"] == "ignore", a
a = run(offer({"cash": 82}, {"types": ["card:MAL-10"]}, status="expired"), held)
assert a["action"] == "ignore", a; checks += 2
print(f"test_trade: {checks} checks passed")
