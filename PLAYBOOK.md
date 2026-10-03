# The Bazaar · Playbook: test, observe, improve (v1)

Saturday 3 Oct 2026 · Team 9 · Spanish version: `PLAYBOOK.es.md` · Strategy: `ONE_SHEET.md`

**Rule for every loop: one change, one number to watch, and the decision rule written down BEFORE we look at the result.**
Real trades cost primas: nothing below sends anything unless it says LIVE, and LIVE needs your approval.
**Who does what:** the dealer scripts (`agent.py`, `bz/haggle.py`: teammate) handle Abuela, El Chato and Pilar. `trader.py` handles other teams only. Both spend the same cash, so tell each other before a big purchase.

## 1. What is built now (all read-only, tested)

| Tool | What it does | Command |
|---|---|---|
| `observe.py` | Records our score numbers whenever one changes. Stores the experiment tag, plus the leader's and the median's negotiating score, to tell our change from a drift of the whole field. | `python3 observe.py` · `python3 observe.py tag E1` |
| `trader.py` | Every tick judges offers from **other teams only**, by structure only, with values from the game (`bz/trade.py`). Shadow by default. `--live` accepts clear wins and counters. `--live-boards` also accepts public asks (40 P cap). Never two open offers for one card, never below the best recent bid. `touch logs/trader.pause` stops it. Every trade: `TRADES.md`. | `python3 trader.py [--live [--live-boards]]` |
| `duels.py --ab` | Split test of the duel opening: alternates two openings by duel id. Without `--ab` it behaves as before. | `python3 duels.py --ab 0.45,0.25` |
| `analyze_duels.py` | Reads the split test per arm and per role. | `python3 analyze_duels.py --since <first duel id>` |
| Tests | 13 trade checks, analyzer checks, the older duel and price checks. | `python3 tests/test_trade.py` and the other files in `tests/` |

Logs go to `logs/` (score, trader, duels). They are not committed.

## 2. The loops

| # | Loop | Cadence | Observe | Decision rule (fixed now) | Action |
|---|---|---|---|---|---|
| L1 | **Score** | always on | `logs/score.jsonl`: our numbers, the tag, the leader's and the median's score | An experiment is read only if our number moved **and** the leader and median numbers moved less. Otherwise repeat it. | Set the tag before each experiment: `observe.py tag E1` |
| L2 | **Offers to us** | every tick | `logs/trader.jsonl`: what each offer was worth to us | Go LIVE only after you have read at least 10 decisions and agree with every ACCEPT. Even then: one accept per tick, clear wins only. | `trader.py` now, `--live` later with your OK |
| L3 | **Duel opening** | each duel session | Deal rate, result ÷ our limit, rounds, per arm and role | Practice baseline: 34 duels, 53% deals, result 0.185 of the limit (buyer 0.137, seller 0.233), 3 rounds. If arm 0.25 has a deal rate no lower **and** a result within 0.01 of arm 0.45 or better → use 0.25 in the next session. If it is worse by more than 0.03 → keep 0.45. Anything in between → split again. | `duels.py --ab 0.45,0.25`, then `analyze_duels.py` |
| L4 | **Dealers** | per dealer | Thread logs, `ladder_points` | Per dealer: theory → free simulation → your approval → one real conversation → compare with the theory → update the model. Stop at 3 good deals per dealer. | Before each session: `python3 -m bz.predict` (one model per dealer; `agent.py` uses it by default, `--model predict`). A new dealer: `family_of` picks its family once it moves in some thread; until then, the prior (messages before the final ≈ 6 × patience). |
| L5 | **Market Test** | every 2 h | `bench_efficiency`, `bench_points`, `market` for us and for the best team | Test 1: free stall 0.899 efficiency, 0.5 bench points, market 4.8; best team 8.01. If after Test 3 the best team is still at least 3 above us **and** someone is free → build a broker. Otherwise keep the free stall. | Read only |
| L6 | **Words** | after L2 can send | Reply rate and price reached, per wording | Two wordings (plain vs label + one calibrated question), alternated per message, at least 10 each. Keep the one with the higher reply rate, then the better price. Never test on El Chato (strict, long memory). | Team trades first, then price-and-days duels |

## 3. Today's timeline (approximate: the game runs about 30 minutes behind the plan)

| When | Do |
|---|---|
| Now | Start `observe.py` and `trader.py` (shadow). Read the first decisions together. |
| ~11:50 | Market Test 2: note the numbers (L5). |
| ~12:00 | **Duels I:** start `duels.py --ab 0.45,0.25` and tag `E1`. Afterwards run `analyze_duels.py` and apply the L3 rule. |
| Before ~18:30 | Duels II adds the delivery day (0–10). Check the days logic with a dry run. Apply the L3 result. |
| All day | New dealers: watch `GET /api/levels`. Run L4 on each. |
| Sunday | Ticks of 15 s. Duels III and Final (10% per round). Dealers close about 14:30. |

## 4. Build list (in this order)

1. **Send counters and standing bids** (long `expires_in_ticks`) for cards we need and for spares. This is LIVE, so it needs your approval. It also unlocks the words test (L6).
2. **El Chato:** sell one spare uncommon to him as the first real conversation (E3). The agent now rechecks ownership before each sale. Run the simulation first (`tests/sim_chato.py`).
3. **Duels II:** confirm the days logic reads `your_days_weight` correctly in a dry run.
4. **Broker:** only if L5 says so.

## 5. Open questions the experiments must answer
- How the 30 Negotiating points split between duels, dealers and team trades (E1–E3).
- Whether scores are relative: our market score moved 4.8 → 5.23 while our bench points stayed at 0.5 ⚠️.
- How the page bonus is counted (until then, page-completing offers go to a person).
