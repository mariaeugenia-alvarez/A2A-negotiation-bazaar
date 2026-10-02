"""What we hold and what it is worth to us: cards, spares, missing page cards."""
from collections import defaultdict

PAGE_RARITIES = ("common", "uncommon", "rare")


class State:
    def __init__(self, b):
        self.b = b
        self.catalog = b.catalog()
        self.cards_by_id = {c["id"]: c for s in self.catalog["sets"] for c in s["cards"]}
        self.me = b.me()

    def refresh(self) -> dict:
        self.me = self.b.me()
        return self.me

    @property
    def cash(self) -> int:
        return self.me["cash"]

    def cards(self) -> list:
        return [a for a in self.me["assets"] if a["kind"] == "card"]

    def packs(self, ref: str = None) -> list:
        return [a for a in self.me["assets"] if a["kind"] == "pack" and (ref is None or a["ref"] == ref)]

    def by_ref(self) -> dict:
        """card id -> our copies, most valuable first."""
        out = defaultdict(list)
        for a in self.cards():
            out[a["ref"]].append(a)
        for copies in out.values():
            copies.sort(key=lambda a: -(a.get("your_value") or 0))
        return out

    def spares(self, rarities=None) -> list:
        """Copies beyond the first, cheapest to us first: what we can sell without breaking a page."""
        out = []
        for ref, copies in self.by_ref().items():
            if rarities and self.cards_by_id.get(ref, {}).get("rarity") not in rarities:
                continue
            out.extend(copies[1:])
        return sorted(out, key=lambda a: a.get("your_value") or 0)

    def missing(self) -> dict:
        """set id -> page cards (common, uncommon, rare) of released sets we do not hold."""
        held = set(self.by_ref())
        out = {}
        for s in self.catalog["sets"]:
            if not s.get("released"):
                continue
            miss = [c["id"] for c in s["cards"] if c.get("page") and c["rarity"] in PAGE_RARITIES and c["id"] not in held]
            out[s["id"]] = miss
        return out
