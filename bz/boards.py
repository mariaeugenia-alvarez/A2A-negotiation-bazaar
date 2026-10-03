"""Reads the public boards without bursts. One full pass over 21 venues is 21 calls in a second; the game allows 5 calls
per second per team key (bursts of 20), and the trader, the signal watcher, the duel agent and the observer share that key.

Boards that hold offers (the active ones) are read every tick. The others are probed `per_tick` at a time in rotation,
so a board that fills up is noticed within a few ticks and no tick makes more than about 5 extra calls.
"""


class BoardScanner:
    def __init__(self, per_tick: int = 4):
        self.per_tick, self.active, self._next = per_tick, set(), 0

    def scan(self, read, venues: list) -> dict:
        """read(venue) -> list of offers. venues: all venue ids. Returns {venue: offers} for every board read this tick."""
        out, venues = {}, list(venues)
        self.active &= set(venues)
        for v in sorted(self.active):  # the boards that held offers: read them all, every tick
            offers = read(v)
            out[v] = offers
            if not offers:
                self.active.discard(v)
        quiet = [v for v in venues if v not in self.active]
        if quiet:
            for i in range(min(self.per_tick, len(quiet))):
                v = quiet[(self._next + i) % len(quiet)]
                offers = read(v)
                out[v] = offers
                if offers:
                    self.active.add(v)
            self._next = (self._next + self.per_tick) % max(1, len(quiet))
        return out
