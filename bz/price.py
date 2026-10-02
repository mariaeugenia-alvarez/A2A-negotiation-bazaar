"""What an item is worth to us, and the limits that follow: the hard cap when buying, the floor when selling.

The catalog publishes the rules, so we compute values ourselves instead of guessing from list prices:

  card value   book price x our affinity for the set x copy marginal (1st copy 1.0, 2nd 0.25, 3rd and later 0.1)
  pack value   for each slot, the odds of each rarity x the average value of a card of that rarity
               (we assume a uniform draw over the cards of the released sets)

A limit is fixed when a conversation opens and never rises during it. The page and master bonuses are
not in these numbers yet, so a card that completes a page is worth more than card_value() says.
Run `python3 -m bz.price` to check the formulas against /api/me/value (read-only, costs 0 P).
"""
import math


class Valuer:
    def __init__(self, catalog: dict, affinity: dict, held: dict = None):
        """held: card id -> number of copies we own."""
        self.book = {r: v["book"] for r, v in catalog["rarities"].items()}
        self.marginals = catalog["values"]["copy_marginals"]
        self.packs = {p["id"]: p for p in catalog["packs"]}
        self.affinity = affinity
        self.held = dict(held or {})
        self.cards = {c["id"]: dict(c, set=s["id"]) for s in catalog["sets"] if s.get("released") for c in s["cards"]}

    def _marginal(self, copies: int) -> float:
        return self.marginals[min(max(copies, 0), len(self.marginals) - 1)]

    def card_value(self, card_id: str, owned: int = None) -> float:
        """Value of the next copy of a card, given `owned` copies (default: what we hold now)."""
        c = self.cards[card_id]
        n = self.held.get(card_id, 0) if owned is None else owned
        return self.book[c["rarity"]] * self.affinity[c["set"]] * self._marginal(n)

    def copy_value(self, card_id: str) -> float:
        """What we lose by selling one copy of a card we hold: the value of our last copy."""
        return self.card_value(card_id, owned=max(self.held.get(card_id, 0) - 1, 0))

    def pack_value(self, pack_id: str) -> float:
        total = 0.0
        for slot in self.packs[pack_id]["slots"]:
            for rarity, odds in slot.items():
                pool = [cid for cid, c in self.cards.items() if c["rarity"] == rarity]
                if pool:
                    total += odds * sum(self.card_value(cid) for cid in pool) / len(pool)
        return total


def buy_cap(value: float, cash: int = None, margin: float = 0.1) -> int:
    """The most we pay: the value to us minus a margin, never more than our cash."""
    cap = math.floor(value * (1 - margin))
    return min(cap, cash) if cash is not None else cap


def sell_floor(value: float) -> int:
    """The least we take for something we own: what we lose by selling it."""
    return max(1, math.ceil(value))


def from_state(st) -> Valuer:
    held = {ref: len(copies) for ref, copies in st.by_ref().items()}
    return Valuer(st.catalog, st.me["affinity"], held)


if __name__ == "__main__":
    import agent
    from bz.state import State

    agent.load_env()
    b = agent.connect()
    v = from_state(State(b))
    bad = 0
    for ref in sorted(v.cards):
        mine, api = v.card_value(ref), b.value(ref)["your_value"]
        if abs(mine - api) > 0.06:
            bad += 1
            print(f"MISMATCH {ref}: ours {mine:.2f}, api {api}")
    print(f"{len(v.cards)} cards checked, {bad} mismatches")
    for pid in v.packs:
        print(f"pack {pid}: worth {v.pack_value(pid):.1f} P to us (catalog neutral {v.packs[pid]['expected_book']})")
