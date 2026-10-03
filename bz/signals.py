"""Market signals from the public boards. Pure functions; signals_watch.py feeds them every tick. Read-only.

Signal 1 (Thameur's idea): a team lowers its own ask for a card with no outside reason. Measured on the feed log
(ticks 223-843, 2,279 single-card asks): a re-listed ask whose price DROPPED filled 3.4 % of the time (n=386), the same
price 0.2 % (n=947), a higher price 0 % (n=278); all asks 1.8 %. After a drop the same maker dropped again in 103 of
316 cases (33 %); the median drop is 12 % of the old price. Not proven: a drop also lowers the price, and cheaper asks
fill more anyway (asks under 0.6 of book filled 10.8 %), so a drop may say nothing about willingness beyond the price.
Fills are fast (median 4 ticks, 22 of 52 within 2 ticks), so a signal is only useful if read within a tick or two.
"""
import math

MEMORY = 80          # ticks a team's earlier ask for a card is remembered
MIN_SURPLUS = 2.0
MIN_SHARE = 0.10
NEAR = 0.25          # a dropped ask within this share above the most we would pay is "near": one more drop clears it


class AskTracker:
    """Remembers each maker's asks for each card and labels every new ask: new, drop, raise or same."""

    def __init__(self, memory: int = MEMORY):
        self.memory, self.hist, self.seen = memory, {}, set()

    def update(self, tick: int, asks: list) -> list:
        """asks: [{"id", "maker", "ref", "price", "venue"}]. Returns one event per ask not seen before."""
        events = []
        for a in sorted(asks, key=lambda a: a["id"]):
            if a["id"] in self.seen:
                continue
            self.seen.add(a["id"])
            key = (a["maker"], a["ref"])
            prev = [(t, p) for t, p in self.hist.get(key, []) if tick - t <= self.memory]
            kind, last, drops = "new", None, 0
            if prev:
                last = prev[-1][1]
                kind = "drop" if a["price"] < last else "raise" if a["price"] > last else "same"
                if kind == "drop":  # how many drops in a row, this one included
                    prices = [p for _, p in prev] + [a["price"]]
                    drops = 0
                    for x, y in zip(reversed(prices[:-1]), reversed(prices[1:])):
                        if y < x:
                            drops += 1
                        else:
                            break
            self.hist[key] = prev + [(tick, a["price"])]
            events.append({**a, "tick": tick, "kind": kind, "last": last,
                           "pct": round((last - a["price"]) / last, 3) if last and kind == "drop" else 0.0,
                           "drops_in_row": drops})
        return events


def assess(ev: dict, value: float, fee: int) -> dict:
    """Would we take this ask? value: what one more copy is worth to us (the game's number). fee: what we pay if we accept.
    max_price is the most we would pay as the ACCEPTER (the fee is ours). gap > 0: how far above that the ask still is."""
    margin = max(MIN_SURPLUS, MIN_SHARE * value)
    max_price = math.floor(value - margin - fee)
    gap = ev["price"] - max_price
    return {"max_price": max_price, "gap": gap, "clears": gap <= 0,
            "near": 0 < gap <= NEAR * ev["price"], "gain": round(value - ev["price"] - fee, 1)}
