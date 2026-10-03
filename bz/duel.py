"""One decision in a duel, as a pure function of the duel the API returns: BOA in code, no words read.

What the practice session taught us (duels 1, 2, 79, 80):
  - the deal's value is our surplus x (1 - decay) ** rounds, compounded (26 x 0.94^3 = 21.6, 22 x 0.94^7 = 14.3);
    a round is an exchange, so talking costs and silence does not (duels with a silent rival kept 0 rounds)
  - rivals are LLM agents that reciprocate: a 1 P step earns a 1-3 P step, a real step earns a real step.
    Tiny Boulware steps burn rounds. So we concede over a budget of a few EXCHANGES, not over the ticks left.

Bidding     target utility falls from the opening to a reserve over `rounds_budget` exchanges (beta > 1 concedes
            early, which reciprocal rivals answer in kind), never below what he already offers us.
Opponent    his concessions so far: the next one is the last one times their observed ratio (default 0.7);
            for days, his preferred day is the one he first offers, his weight per day comes from his trades of
            days for price.
Acceptance  his offer inside our limit and either at least as good as our next counter, or worth more than
            waiting one more round (his expected answer = his elasticity to our steps x our planned step, so only
            once he has answered a real step of ours), or the deadline is near.

Hard rules: the price never crosses our limit (on price alone, whatever the days), no price below 1, days 0-10,
the same offer is never sent twice, and we never talk twice in a row while he has not answered.

Two issues (price and days): U = price surplus + w * days. The sign of w comes from days_meaning (gain or cost);
when it cannot be read, days count for nothing to us and we simply give him his day.
Among packages worth the same U to us we offer his day if a day matters less to us than to him, ours otherwise.
"""

OPEN_FRAC = 0.45  # sim (tests/sim_duel.py): 0.45 + 3 exchanges + beta 2 gave 0.48 of the pie vs 0.36 for v0
COST_WORDS = ("cost", "lose", "loss", "penal", "worse", "less", "delay hurts")
GAIN_WORDS = ("gain", "earn", "worth", "value", "benefit", "better", "more")


def surplus(role: str, limit: float, price: float) -> float:
    return (limit - price) if role == "buyer" else (price - limit)


def price_for(role: str, limit: float, s: float) -> int:
    return round(limit - s) if role == "buyer" else round(limit + s)


def inside(role: str, limit: float, price: float) -> bool:
    return price >= 1 and surplus(role, limit, price) >= 0


def days_weight(d: dict, override: int = None) -> tuple:
    """(w, how): our value per day of delivery, signed. override (+1/-1) multiplies the raw weight as given."""
    if "days" not in (d.get("issues") or []):
        return 0.0, "price only"
    raw = float(d.get("your_days_weight") or 0.0)
    if override in (1, -1):
        return raw * override, f"override {override}"
    meaning = (d.get("days_meaning") or "").lower()
    cost = any(word in meaning for word in COST_WORDS)
    gain = any(word in meaning for word in GAIN_WORDS)
    if cost and not gain:
        return -raw, "cost per day"
    if gain and not cost:
        return raw, "gain per day"
    return 0.0, f"unread days_meaning: {meaning!r}"


def history(d: dict) -> tuple:
    """(our offers, his offers, exchanges, awaiting): offers as [(tick, price, days)] in order; an exchange is one of
    our offers that he answered; awaiting is True when the last priced message is ours."""
    ours, his, exchanges, last_ours = [], [], 0, False
    for m in d.get("messages") or []:
        if m.get("price") is None:
            continue
        if m.get("from") == "you":
            ours.append((m["tick"], m["price"], m.get("days")))
            last_ours = True
        else:
            his.append((m["tick"], m["price"], m.get("days")))
            exchanges += last_ours
            last_ours = False
    return ours, his, exchanges, last_ours


def decide(d: dict, tick: int, *, beta: float = 2.0, rounds_budget: int = 3, days_sign: int = None,
           open_frac: float = OPEN_FRAC) -> dict:
    """{"action": "accept" | "offer" | "wait", "price", "days", "why", ...estimates} for one duel at one tick."""
    role, limit, decay = d["role"], float(d["your_limit"]), float(d.get("decay_per_round") or 0.0)
    two = "days" in (d.get("issues") or [])
    w, w_how = days_weight(d, days_sign)
    ours, his, k, awaiting = history(d)
    left = d["deadline_tick"] - tick

    def U(price, days):
        return surplus(role, limit, price) + (w * (days or 0) if two else 0.0)

    # --- opponent model
    his_u = [U(p, dd) for _, p, dd in his]  # his offers in OUR utility: rising = he concedes
    steps = [b - a for a, b in zip(his_u, his_u[1:])]
    ratios = [b / a for a, b in zip(steps, steps[1:]) if a > 0 and b >= 0]
    ratio = min(0.95, max(0.3, sum(ratios) / len(ratios))) if ratios else 0.7
    moving = bool(steps) and steps[-1] > 0
    next_step = steps[-1] * ratio if moving else 0.0
    his_day = his[0][2] if (two and his and his[0][2] is not None) else None
    w_rival = abs(w)  # prior: a day matters to him as much as to us
    for (_, p1, d1), (_, p2, d2) in zip(his, his[1:]):
        if two and d1 is not None and d2 is not None and d1 != d2 and p1 != p2:
            w_rival = abs(p2 - p1) / abs(d2 - d1)  # what he paid in price per day he moved

    my_day = None
    if two:
        if w == 0:
            my_day = his_day if his_day is not None else 5  # days are free to us: give him his
        else:
            mine = 10 if w > 0 else 0
            my_day = mine if (his_day is None or abs(w) >= w_rival) else his_day
        my_day = max(0, min(10, int(my_day)))

    # --- bidding: target utility after k exchanges
    u_open = limit * open_frac + (w * my_day if two else 0.0)
    reserve = max(1.0, 0.05 * limit) if left > 2 else 1.0
    frac = min(1.0, (k / max(1, rounds_budget)) ** (1 / beta)) if k else 0.0
    u_target = u_open - frac * (u_open - reserve)
    if his_u:  # never ask for less than he already offers; while he still moves, expect a bit more
        u_target = max(u_target, min(u_open, his_u[-1] + 2 * next_step) if moving else his_u[-1], reserve)
    if left <= 2:
        u_target = max(reserve, min(u_target, his_u[-1]) if his_u else reserve)

    price = price_for(role, limit, u_target - (w * my_day if two else 0.0))
    price = min(price, int(limit)) if role == "buyer" else max(price, int(-(-limit // 1)))  # never cross our limit
    price = max(1, price)
    if ours and (ours[-1][1], ours[-1][2]) == (price, my_day):  # the same offer twice is no offer
        nudged = price + (1 if role == "buyer" else -1)
        price = nudged if inside(role, limit, nudged) else price
    u_mine = U(price, my_day)

    # his answer to OUR step: reciprocal rivals move in proportion to what we give (practice, Rival Rojo: our 1-5 P
    # steps earned 5-14 P), so a small step of his after none of ours says nothing about his room
    ours_u = [U(p, dd) for _, p, dd in ours]
    our_steps = [a - b for a, b in zip(ours_u, ours_u[1:])]  # our concessions, in our utility
    pairs = [(o, h) for o, h in zip(our_steps, steps[1:]) if o > 0]  # his step that answered each of ours
    elastic = min(3.0, max(0.3, sum(h for _, h in pairs) / sum(o for o, _ in pairs))) if pairs else 1.0
    planned = (ours_u[-1] - u_mine) if ours_u else 0.0
    # what he should give back: his answer to our planned step, or his own pace if he concedes regardless
    answer = max(elastic * max(0.0, planned), next_step)

    est = {"u_target": round(u_target, 1), "u_his": round(his_u[-1], 1) if his_u else None,
           "next_step": round(answer, 1), "elastic": round(elastic, 2), "ratio": round(ratio, 2), "w": w, "w_how": w_how,
           "w_rival": round(w_rival, 2), "his_day": his_day, "left": left, "k": k}

    # --- acceptance
    rival = d.get("rival_offer")
    if rival and rival.get("price") is not None and (not two or rival.get("days") is not None):
        u_r = U(rival["price"], rival.get("days"))
        if inside(role, limit, rival["price"]) and u_r >= 1:
            if u_r >= u_mine:
                return {"action": "accept", "why": f"his {u_r:.1f} >= our next {u_mine:.1f}", **est}
            if pairs and (u_r + answer) * (1 - decay) <= u_r:  # only once he has answered a real step of ours
                return {"action": "accept", "why": f"his answer ~{answer:.1f} to our step does not pay a round's decay", **est}
            if left <= 2:
                return {"action": "accept", "why": "deadline", **est}

    if not inside(role, limit, price) or u_mine < 1:
        return {"action": "wait", "why": "no offer inside our limit", **est}
    if ours and (ours[-1][1], ours[-1][2]) == (price, my_day):
        return {"action": "wait", "why": "our offer stands", **est}
    if awaiting and left > 2:  # talking again before he answers only spends our concessions
        return {"action": "wait", "why": "waiting for his reply", **est}
    return {"action": "offer", "price": price, "days": my_day, "why": f"U {u_mine:.1f}", **est}


# ---------------------------------------------------------------- v2: read the bot (doctrine approved 13:35, ONE_SHEET §VI)
# Measured on 61 duels (Duels I + practice): a round counts only when the rival answers one of OUR offers, so his solo
# messages cost nothing; rivals conceded while we were silent in 89 of 104 cases (+4.2 P on average, +6.0 after a
# message of ours); about half opened inside our limit. Aliases are reused across duels: no memory per rival.
# Hard rules unchanged: our price never crosses our limit, no price below 1, days 0-10, never the same offer twice.

OPEN2 = {"buyer": 0.75, "seller": 1.30}  # first offer as a share of our limit (tests/sim_duel2.py)
MAX_COUNTERS = 2
GOOD = 0.10            # his offer leaves us at least this share of our limit: "inside with a good surplus"
STEP_AFTER_OURS = 6.0  # his mean step after a message of ours (Duels I), used until we see his own
LAST_CALL = True       # tests/sim_duel2.py decides
DUEL_TICKS = 16        # Duels II length; duels.py passes the real start as d["_start"] (Sunday: 12)


def _toward_us(role: str, prev: float, cur: float) -> float:
    """How much his price moved in our favour (positive = good for us)."""
    return (prev - cur) if role == "buyer" else (cur - prev)


def read_bot(d: dict) -> dict:
    """His behaviour so far, from the priced messages in order: solo steps (no offer of ours in between) and steps
    that answered one of our offers. kind: 'self' (concedes alone), 'recip', 'hard' (does not move for us), 'new'."""
    role, msgs = d["role"], [m for m in d.get("messages") or [] if m.get("price") is not None]
    solo, answered, prev, ours_since = [], [], None, False
    for m in msgs:
        if m.get("from") == "you":
            ours_since = True
            continue
        if prev is not None:
            (answered if ours_since else solo).append(_toward_us(role, prev, m["price"]))
        prev, ours_since = m["price"], False
    his = [m for m in msgs if m.get("from") != "you"]
    if solo and max(solo) > 0 and (not answered or len(solo) >= len(answered)):
        kind = "self"
    elif answered and max(answered) >= max(2.0, 0.02 * float(d["your_limit"])):  # a real step, not a token 1 P
        kind = "recip"
    elif answered:
        kind = "hard"
    else:
        kind = "new"
    return {"kind": kind, "solo": solo, "answered": answered, "his_ticks": [m["tick"] for m in his],
            "his_days": [m.get("days") for m in his if m.get("days") is not None]}


def decide2(d: dict, tick: int, *, open2: dict = None, max_counters: int = MAX_COUNTERS, days_sign: int = None,
            last_call: bool = LAST_CALL) -> dict:
    """{"action": "accept" | "offer" | "wait", "price", "days", "why", "kind", ...} for one duel at one tick."""
    open2 = open2 or OPEN2
    role, limit, decay = d["role"], float(d["your_limit"]), float(d.get("decay_per_round") or 0.0)
    two = "days" in (d.get("issues") or [])
    w, w_how = days_weight(d, days_sign)
    ours, his, k, awaiting = history(d)
    left = d["deadline_tick"] - tick
    bot = read_bot(d)
    start = d.get("_start", d["deadline_tick"] - DUEL_TICKS)
    priced = [m for m in d.get("messages") or [] if m.get("price") is not None]
    we_opened = bool(priced) and priced[0].get("from") == "you"
    counters = len(ours) - (1 if we_opened else 0)  # our opening to a silent rival is not a counter

    def U(price, days):
        return surplus(role, limit, price) + (w * (days or 0) if two else 0.0)

    rival = d.get("rival_offer")
    r_price = rival.get("price") if rival else None
    r_days = rival.get("days") if rival else None
    u_his = U(r_price, r_days) if r_price is not None and (not two or r_days is not None) else None
    his_ok = u_his is not None and inside(role, limit, r_price) and u_his >= 1
    last_his = bot["his_ticks"][-1] if bot["his_ticks"] else None
    moving = bool(bot["solo"]) and bot["solo"][-1] > 0 and last_his is not None and tick - last_his < 2 and not awaiting
    exp_step = (sum(s for s in bot["answered"] if s > 0) / max(1, sum(1 for s in bot["answered"] if s > 0))
                if any(s > 0 for s in bot["answered"]) else STEP_AFTER_OURS)
    est = {"kind": bot["kind"], "u_his": None if u_his is None else round(u_his, 1), "exp_step": round(exp_step, 1),
           "left": left, "k": k, "counters": counters, "we_opened": we_opened, "w": w, "w_how": w_how, "his_days": bot["his_days"],
           "solo": bot["solo"][-3:], "answered": bot["answered"][-3:]}

    # 1. accept
    if his_ok:
        if left <= 2:
            return {"action": "accept", "why": "fewer than 3 ticks left", **est}
        if moving:  # he concedes alone: silence costs no round, so let him come
            return {"action": "wait", "why": "waiting: self-conceder (his offer is inside, he is still moving)", **est}
        if (u_his + exp_step) * (1 - decay) <= u_his:
            return {"action": "accept", "why": f"one more round (~{exp_step:.1f}) cannot beat the {decay:.0%} decay", **est}
        if bot["kind"] == "self" and last_his is not None and (tick - last_his >= 2 or bot["solo"][-1] <= 0):
            return {"action": "accept", "why": "self-conceder stopped (no move for 2 ticks): take his in-limit offer", **est}
        if counters >= max_counters:
            return {"action": "accept", "why": f"{counters} counters used: take the in-limit offer", **est}
        if counters >= 1 and u_his >= GOOD * limit:
            return {"action": "accept", "why": "inside with a good surplus after our counter", **est}

    # 2. wait
    if awaiting and left > 2:
        return {"action": "wait", "why": "our offer stands: he owes the next move", **est}
    if moving:
        # wait only if his own pace can bring him inside our limit before the last 3 ticks; otherwise speak
        need = max(0.0, -surplus(role, limit, r_price)) if r_price is not None else 0.0
        pace = sum(s for s in bot["solo"] if s > 0) / max(1, sum(1 for s in bot["solo"] if s > 0))
        if pace > 0 and need / pace <= left - 3:
            return {"action": "wait", "why": f"waiting: self-conceder (needs ~{need / pace:.0f} of {left} ticks)", **est}
    if his and not ours and last_his is not None and tick - his[0][0] < 2 and left > 4:
        return {"action": "wait", "why": "waiting: watching his first moves", **est}
    if not his and not ours and tick - start < 1:  # rivals who speak first do it at tick 0: let him open
        return {"action": "wait", "why": "tick 0: letting him open", **est}
    if counters >= max_counters:
        if last_call and left <= 3 and not his_ok:  # no deal scores 0 for both: one final offer near our limit
            margin = max(1, round(0.03 * limit))
            p = int(limit) - margin if role == "buyer" else int(-(-limit // 1)) + margin
            if inside(role, limit, p) and not (ours and ours[-1][1] == p):
                day = None
                if two:
                    day = bot["his_days"][-1] if bot["his_days"] else 5
                return {"action": "offer", "price": max(1, p), "days": day, "why": "last call near our limit", **est}
        return {"action": "wait", "why": "counters used: waiting for an in-limit offer (no deal is fine)", **est}

    # 3. offer: the opening, then real steps (40 % of the gap between his offer and ours)
    if not ours:
        target = open2[role] * limit
    else:
        last = ours[-1][1]
        gap = (r_price - last) if (r_price is not None) else (limit - last)
        target = last + 0.4 * gap
    if r_price is not None:  # never worse for us than what he already offers
        target = min(target, r_price - 1) if role == "buyer" else max(target, r_price + 1)
    price = int(round(target))
    price = min(price, int(limit)) if role == "buyer" else max(price, int(-(-limit // 1)))  # never cross our limit
    price = max(1, price)

    day = None
    if two:  # hypothesis under test: lean the day toward our side, but never forced to 0 or 10
        his_day = bot["his_days"][-1] if bot["his_days"] else None
        base = his_day if his_day is not None else 5
        w_rival = abs(w)
        if w == 0:
            day = base
        else:
            mine = 10 if w > 0 else 0
            day = round(base + (mine - base) / 2) if (his_day is None or abs(w) >= w_rival) else base
        day = max(0, min(10, int(day)))
    if ours and (ours[-1][1], ours[-1][2]) == (price, day):
        nudged = price + (1 if role == "buyer" else -1)
        if inside(role, limit, nudged):
            price = nudged
        else:
            return {"action": "wait", "why": "at our limit: waiting", **est}
    if not inside(role, limit, price):
        return {"action": "wait", "why": "no offer inside our limit", **est}
    return {"action": "offer", "price": price, "days": day,
            "why": ("opening" if not ours else f"real step {counters + 1}/{max_counters}") + f" vs a {bot['kind']} bot", **est}
