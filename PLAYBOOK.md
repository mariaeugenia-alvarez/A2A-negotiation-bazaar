# The Bazaar · Playbook: test, observe, improve (v2)

Saturday 3 Oct 2026, 13:05 (tick 583) · Team 9 · Spanish version: `PLAYBOOK.es.md` · Strategy and source of truth: `ONE_SHEET.md`

**Rule for every loop: one change, one number to watch, and the decision rule written down BEFORE we look at the result.**
Real trades cost primas: nothing below sends anything unless it says LIVE, and LIVE needs an OK: **duels from Thameur, cards (dealers, team trades, quoter) from Maru**.
**Who does what on our shared key:** dealers = Maru's scripts (`agent.py`, `bz/haggle.py`, `bz/predict.py`).
Team trades = `trader.py` (trader session). Duels = `duels.py` under `duels_watch.py`, on **Thameur's machine only**. All of
them spend the same cash, so tell each other before a big purchase or before posting offers.

## 1. What is built now

| Tool | What it does | Command |
|---|---|---|
| `observe.py` | Records our score numbers whenever one changes, with the experiment tag and the leader's and median's negotiating score | `python3 observe.py` · `python3 observe.py tag D2` |
| `trader.py` | Judges offers from **other teams only**, by structure, with values from the game. Shadow by default. `touch logs/trader.pause` stops it. Every trade goes in `TRADES.md` | `python3 trader.py [--live [--live-boards]]` |
| `trader.py --quotes` | **Quoter:** standing bids for missing page cards, asks for spares, watched by a guard. Cash floor 15 P kept for accepts; board accepts capped at 40 P per hour; no probe counters; `--hands-off RET-09` (Maru buys it by hand: no quote, accept or counter); `--earmark REF:AMOUNT` off by default. Timers scale to the tick length (Sunday 15 s). Guard: STOP on a loss, on a score drop within 15 ticks of our own trade, on spending or errors; SCORE-DROP is an alert. Deleting `logs/trader.pause` resets it. Alerts in `logs/alerts.jsonl`. Posts only with `--live`. Writes `logs/trader.heartbeat` | `python3 trader.py --quotes --live-boards [--quote-budget 180] [--live]` |
| `trader_review.py` | **Review loop:** read-only report on health, rank against the field, accepts planned vs realized, counters, quote fills by price, missed clear wins (`logs/trader_blocked.jsonl`) and signals; at most 3 proposals with evidence. Runs by itself every 2 h (09:17-23:17) while the Claude session is open. A person approves any change | `python3 trader_review.py [--hours 2]` |
| `duels.py` | Plays every live duel. The code decides, the words carry it. **Default `--policy v2`: the waiting play** (`ONE_SHEET.md` §VI). `--policy v1` = old logic, the safety switch | `python3 duels.py [--dry] [--policy v1]` |
| `duels_watch.py` | **Supervisor:** starts `duels.py` when duels go live, restarts it after a crash or when a live duel waits 3 ticks for us. Alerts DUEL_START, DUEL_SILENT, DUEL_CRASH | `python3 duels_watch.py [--silent 3] [-- <duels.py args>]` |
| `analyze_duels.py` | Deal rate, result ÷ limit, rounds, per role and per arm | `python3 analyze_duels.py --since <first duel id>` |
| `bz.predict` (Maru) | One model per dealer and kind of deal. `agent.py` uses it by default | `python3 agent.py learn && python3 -m bz.predict` |
| `broker.py` (Maru) | Broker for our own venue: records the book, matches trades. Not in use | see the file |
| Tests | trade, quotes, rules, duel, dealer models | `python3 tests/test_trade.py`, `tests/test_quotes.py`, `tests/test_rules.py`, `tests/test_predict.py` … |

## 2. The loops

| # | Loop | Cadence | Observe | Decision rule (fixed now) | Action |
|---|---|---|---|---|---|
| L1 | **Score** | always on | `logs/score.jsonl`: our numbers, the tag, the leader and the median | An experiment is read only if our number moved **and** the leader and median moved less. The negotiating score is relative ✅, so always compare with the median | Set the tag before each experiment |
| L2 | **Offers to us** | every tick | `logs/trader.jsonl` | Every accept must gain value. Never sell below our value or a card we need for a page | `trader.py`; LIVE only with Maru's OK (`logs/trader.pause` exists since 11:09, so it is paused) |
| L3 | **Duels** | each session | Deal rate, result per deal, rounds, unanswered duels, how many bots concede on their own | **Duels I baseline:** 18 deals of 34, result 13.3 per deal, deals in ≤ 2 rounds 20.4 vs ≥ 4 rounds 5.7, **8 duels lost to our silence**. Duels II target: 0 unanswered, ≥ 80% deals, median ≤ 2 rounds, ≥ 18 per deal. **Safety switch:** after the first wave, if < 70% of duels close or the bots stop conceding on their own → restart with `--policy v1` | `duels_watch.py` on Thameur's machine, `observe.py tag D2`, then `analyze_duels.py` |
| L4 | **Quoter** | every tick once LIVE | Fills, `neg_points`, alerts | Each fill must raise `neg_points`. If a fill lowers it, or a STALE / FOREIGN alert appears, pause (`touch logs/trader.pause`) and look | `trader.py --quotes --live` after Maru's OK |
| L5 | **Dealers** | per dealer | Thread logs, `ladder_points`, `neg_points` | Dealer score is tiny (0.14). Deal only for value: page cards below value, spares above it. **No sale below our value, no page card** | Maru's scripts, `--model predict` |
| L6 | **Market Test** | every 2 h | `bench_efficiency`, `market` for us and the best team | Free stall gave 0.933 → market 7.5. **Since tick 575 our own venue v21 replaces it** (no broker seen yet). If v21 scores below 7.5 in Market Test 3 → a broker for it becomes the top market task | Read only |
| L7 | **Words** | team trades first | Reply rate and price reached, per wording | Two wordings (plain vs label + one calibrated question), alternated, at least 10 each. Keep the one with the higher reply rate, then the better price. Never on El Chato | After L2 sends counters |

## 3. Timeline (Madrid, estimated from `/api/schedule` at tick 583, 13:03)

| ≈ When | Do |
|---|---|
| 17:55 · 19:55 · 21:55 | Market Tests: write down our numbers and the best team's (L6) |
| **18:05–20:05** | **Pilar's Salamanca fever (+25% over book).** Team decides first: sell Salamanca or finish the page |
| **already on** | `python3 duels_watch.py` runs on Thameur's machine since 15:52 (v2, the waiting play) |
| **≈20:35** | **Duels II** (8% per round, 16 ticks, up to 6 at once). `observe.py tag D2`. Days-reading check when it opens. 21:00 review, then `analyze_duels.py` and apply L3 |
| 23:00 | Doors close |
| **Sunday** | 09:00 opens (15-second ticks). ≈09:35 hard Market Test. ≈11:35 round 3 at zero, Chamberí released, +150 P. **≈13:35 Duels III** (10%, 12 ticks = 3 min). 15:00 close. Grand Final / freeze ❓ (after 15:00 in the current schedule) |

## 4. Build list (in this order)

1. ✅ **Duel logic for Duels II** (`bz/duel.py` v2, trader session): doctrine approved 13:35, waiting play approved 14:00 (`ONE_SHEET.md` §VI). Default `--policy v2`; `--policy v1` is the safety switch. Delivery day: hypothesis only.
2. **Dealer guard** (Maru): `sell-spares` sells only spares, never below `sell_floor`; `--limit` clamped to `sell_floor`/`buy_cap` (15:36). **Done.**
3. **Quoter LIVE** with Maru's OK (180 P of bids, +79 of value if all fill). Cash is 48 P after the v21 bond: set `--quote-budget` to what we have.
4. **Broker:** v21 is open without one. Read L6 at the next Market Test and decide then, not at the hard test.

## 5. Open questions the experiments must answer
- The exact formula from `neg_points`, `duel_points` and `ladder_points` to the 30 negotiating points.
- Why `neg_points` fell at tick 567 (Pilar sales below value?).
- The master bonus.
- Whether words change an LLM rival's price (L7).
