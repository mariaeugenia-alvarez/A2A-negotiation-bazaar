"""Stoppers and alerts for live trading. Pure: trader.py feeds it what happened and obeys what it says.

STOP (trader.py then cancels our quotes and writes logs/trader.pause with the reason; a person looks, then deletes the
file and the guard resets itself):
  - a fill or an accept that lost value at our private values
  - neg_points went DOWN within SCORE_LAG ticks of a trade made by OUR OWN code (trader accept or quoter fill). The
    leaderboard refreshes every 5 ticks, so the drop shows up a few ticks after the trade.
  - more than SPEND_CAP primas spent in the last SPEND_WINDOW ticks
  - ERROR_CAP refused calls in the last ERROR_WINDOW ticks
HOLD (no new bids, everything else goes on): cash below CASH_FLOOR
ALERTS: a win, a score drop with no trade of ours (SCORE-DROP: it happened at tick 608 on Saturday with no trade at all,
and a manual sale by another session on our key caused another), a page one card from complete, a bid outbid, a quote
unfilled for long

All windows are in ticks at 30 s per tick. tick_scale() converts them when the game runs faster (Sunday: 15 s).
"""
CASH_FLOOR = 15      # reserve kept out of standing bids, for accepts: 26 of 38 clear wins cost 5-15 P, a swap costs 2 P
SPEND_CAP = 250
SPEND_WINDOW = 120
ERROR_CAP = 5
ERROR_WINDOW = 20
SCORE_LAG = 15       # ticks after our own trade in which a score drop is blamed on it
WIN = 5.0
STALE_TICKS = 100
FREE_SPEND = 5       # an accept that costs this much or less is never blocked by an earmark (swap fees, tiny wins)


def tick_scale(tick_seconds) -> float:
    """Windows below are in ticks at 30 s. Sunday ticks last 15 s, so the same wall time is twice as many ticks."""
    try:
        return 30.0 / float(tick_seconds)
    except (TypeError, ValueError, ZeroDivisionError):
        return 1.0


def earmark_total(earmark: dict, held: set) -> int:
    """Cash kept for buying cards by hand: the amount for each earmarked card we do not hold yet (it releases itself
    the moment the card is ours). earmark: {"RET-09": 60}."""
    return sum(int(a) for ref, a in (earmark or {}).items() if ref not in held)


def spend_allowed(net_spend: int, cash: int, earmark: int, free: int = FREE_SPEND) -> bool:
    """May we spend net_spend primas (cash out + fee - cash in) now? Money coming in is always fine. A small spend is
    fine. A larger one must leave at least `earmark` in cash."""
    if net_spend <= 0 or net_spend <= free:
        return True
    return cash - net_spend >= earmark


def bid_budget(cash: int, foreign_cash: int, cap: int, earmark: int, floor: int = CASH_FLOOR) -> int:
    """Cash our standing bids may promise: what is free after other open bids, the floor and the earmark."""
    return max(0, min(cap, cash - foreign_cash - floor - earmark))


class Guard:
    def __init__(self, scale: float = 1.0):
        self.scale = scale
        self.stopped, self.reason = False, ""
        self.spends, self.errors, self.own_ticks = [], [], []
        self.last_neg = None
        self.alerts = []  # (level, text) to print; drained by the caller

    def _w(self, n: int) -> int:
        return max(1, round(n * self.scale))

    def _stop(self, why: str) -> None:
        if not self.stopped:
            self.stopped, self.reason = True, why
            self.alerts.append(("STOP", why))

    def reset(self) -> None:
        """A person looked and removed the pause file. Errors are forgotten, the score baseline restarts, the spend
        history stays: if the cause was spending, the next fill stops us again."""
        self.stopped, self.reason = False, ""
        self.errors, self.last_neg = [], None
        self.alerts.append(("RESUME", "guard reset: the pause file was removed"))

    def own_trade(self, tick: int) -> None:
        """Our own code traded at this tick (a trader accept or a quoter fill)."""
        self.own_ticks.append(tick)

    def fill(self, tick: int, ref: str, side: str, price: int, value: float) -> None:
        self.own_trade(tick)
        gain = (value - price) if side == "bid" else (price - value)
        if side == "bid":
            self.spends.append((tick, price))
        self._judge(tick, f"{side} {ref} at {price}", gain)

    def accept_result(self, tick: int, label: str, realized_gain: float, spent: int = 0) -> None:
        """A trader accept settled: realized_gain is the planned surplus corrected by what the game really charged."""
        self.own_trade(tick)
        if spent > 0:
            self.spends.append((tick, spent))
        self._judge(tick, label, realized_gain)

    def _judge(self, tick: int, label: str, gain: float) -> None:
        if gain < 0:
            self._stop(f"{label} lost {abs(gain):.1f} P of value")
        elif gain >= WIN:
            self.alerts.append(("WIN", f"{label}: +{gain:.1f} P of value"))
        recent = sum(p for t, p in self.spends if tick - t <= self._w(SPEND_WINDOW))
        if recent > SPEND_CAP:
            self._stop(f"spent {recent} P in {self._w(SPEND_WINDOW)} ticks (cap {SPEND_CAP})")

    def score(self, neg_points, tick: int = None) -> None:
        if neg_points is None:
            return
        if self.last_neg is not None and neg_points < self.last_neg - 0.05:
            ours = tick is not None and any(0 <= tick - t <= self._w(SCORE_LAG) for t in self.own_ticks)
            if ours:
                self._stop(f"neg_points fell from {self.last_neg} to {neg_points} after a trade of ours")
            else:
                self.alerts.append(("SCORE-DROP", f"neg_points fell from {self.last_neg} to {neg_points} with no trade of "
                                                  f"ours in the last {self._w(SCORE_LAG)} ticks (not a stop)"))
        elif self.last_neg is not None and neg_points > self.last_neg + 0.05:
            self.alerts.append(("UP", f"neg_points {self.last_neg} -> {neg_points}"))
        self.last_neg = neg_points

    def error(self, tick: int, what: str) -> None:
        self.errors.append(tick)
        if sum(1 for t in self.errors if tick - t <= self._w(ERROR_WINDOW)) >= ERROR_CAP:
            self._stop(f"{ERROR_CAP} refused calls in {self._w(ERROR_WINDOW)} ticks (last: {what})")

    def may_bid(self, cash: int) -> bool:
        return not self.stopped and cash >= CASH_FLOOR

    def drain(self) -> list:
        out, self.alerts = self.alerts, []
        return out
