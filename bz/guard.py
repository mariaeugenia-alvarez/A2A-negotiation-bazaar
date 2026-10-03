"""Stoppers and alerts for live trading. Pure: trader.py feeds it what happened and obeys what it says.

STOP (trader.py then cancels our quotes and writes logs/trader.pause with the reason; a person must remove it):
  - a fill that lost value at our private values
  - neg_points went DOWN (it only grows with value gained in team trades, so a drop means something is wrong)
  - more than SPEND_CAP primas spent in the last SPEND_WINDOW ticks
  - ERROR_CAP refused calls in the last ERROR_WINDOW ticks
HOLD (no new bids, everything else goes on): cash below CASH_FLOOR
ALERTS: a win, a page one card from complete (decide by hand), a bid outbid by another team, a quote unfilled for long
"""
CASH_FLOOR = 100
SPEND_CAP = 250
SPEND_WINDOW = 120
ERROR_CAP = 5
ERROR_WINDOW = 20
WIN = 5.0
STALE_TICKS = 100


class Guard:
    def __init__(self):
        self.stopped, self.reason = False, ""
        self.spends, self.errors = [], []
        self.last_neg = None
        self.alerts = []  # (level, text) to print; drained by the caller

    def _stop(self, why: str) -> None:
        if not self.stopped:
            self.stopped, self.reason = True, why
            self.alerts.append(("STOP", why))

    def fill(self, tick: int, ref: str, side: str, price: int, value: float) -> None:
        gain = (value - price) if side == "bid" else (price - value)
        if side == "bid":
            self.spends.append((tick, price))
        if gain < 0:
            self._stop(f"{side} {ref} at {price} lost {gain:.1f} P of value")
        elif gain >= WIN:
            self.alerts.append(("WIN", f"{side} {ref} at {price}: +{gain:.1f} P of value"))
        recent = sum(p for t, p in self.spends if tick - t <= SPEND_WINDOW)
        if recent > SPEND_CAP:
            self._stop(f"spent {recent} P in {SPEND_WINDOW} ticks (cap {SPEND_CAP})")

    def score(self, neg_points) -> None:
        if neg_points is None:
            return
        if self.last_neg is not None and neg_points < self.last_neg - 0.05:
            self._stop(f"neg_points fell from {self.last_neg} to {neg_points}")
        elif self.last_neg is not None and neg_points > self.last_neg + 0.05:
            self.alerts.append(("UP", f"neg_points {self.last_neg} -> {neg_points}"))
        self.last_neg = neg_points

    def error(self, tick: int, what: str) -> None:
        self.errors.append(tick)
        if sum(1 for t in self.errors if tick - t <= ERROR_WINDOW) >= ERROR_CAP:
            self._stop(f"{ERROR_CAP} refused calls in {ERROR_WINDOW} ticks (last: {what})")

    def may_bid(self, cash: int) -> bool:
        return not self.stopped and cash >= CASH_FLOOR

    def drain(self) -> list:
        out, self.alerts = self.alerts, []
        return out
