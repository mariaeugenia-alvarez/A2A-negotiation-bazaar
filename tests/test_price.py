import os
import sys; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from bz.price import Valuer, buy_cap, sell_floor

CATALOG = {
    "rarities": {"common": {"book": 10}, "uncommon": {"book": 25}},
    "values": {"copy_marginals": [1.0, 0.25, 0.1]},
    "packs": [{"id": "p", "slots": [{"common": 1.0}, {"common": 0.5, "uncommon": 0.5}], "expected_book": 0}],
    "sets": [{"id": "A", "released": True, "cards": [{"id": "A-1", "rarity": "common"}, {"id": "A-2", "rarity": "uncommon"}]},
             {"id": "B", "released": True, "cards": [{"id": "B-1", "rarity": "common"}]},
             {"id": "C", "released": False, "cards": [{"id": "C-1", "rarity": "common"}]}],
}
AFF = {"A": 1.6, "B": 0.5, "C": 3.0}


def close(a, b):
    return abs(a - b) < 1e-9


v = Valuer(CATALOG, AFF, {"A-1": 2})
assert close(v.card_value("A-1", owned=0), 16.0)   # first copy: full value
assert close(v.card_value("A-1", owned=1), 4.0)    # second copy: 25 %
assert close(v.card_value("A-1", owned=5), 1.6)    # third and later: 10 %
assert close(v.card_value("A-1"), 1.6)             # we hold 2, so the next one is the third
assert close(v.copy_value("A-1"), 4.0)             # selling one of two loses the second copy
assert close(v.copy_value("A-2"), 40.0)            # a single copy loses full value
assert "C-1" not in v.cards                        # unreleased sets are ignored

# slot 1: average of A-1 (1.6) and B-1 (5.0) = 3.3. slot 2: 0.5 x 3.3 + 0.5 x A-2 (40)
assert close(v.pack_value("p"), 3.3 + 0.5 * 3.3 + 0.5 * 40.0)

assert buy_cap(16.6) == 14 and buy_cap(16.6, cash=10) == 10 and buy_cap(0.5) == 0
assert sell_floor(5.6) == 6 and sell_floor(0.0) == 1
print("price tests ok")
