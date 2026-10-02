# Dealers: what we know, one section per dealer

Rule: each dealer keeps its own section. Never average dealers together. The pooled prior lives in its own section at the end.

## Abuela Carmen (patience 0.85, strictness 0.1, memory 0.15)

Source: 9 threads, `logs/threads/`. Small sample: treat as hypotheses.

| Deal | Her first price | Her best price | Messages before final | Deals |
|---|---|---|---|---|
| buy `sobre_barrio` (list 26, ask 30) | 17 (ticks 0-1), 30 (ticks 35, 60) | 19, 21 | about 7 | 17, 19, 21 |
| sell uncommon | 12 | 13 | about 5 | 13, 13 |
| sell common | 5 | 6 | about 5 | 6 |

- She moved about 1.5 P for every 1 P we conceded (threads 66, 108).
- A deal at her opening price does not count for the score or for unlocking a level.
- Her best price for the pack was 73-81% of list price. Her bid for an uncommon was about 52% of list price.

## El Chato (patience 0.35, shrewdness 0.85, memory 0.9, strictness 0.85)

Status: no conversation yet. Everything below is theory, to test in `tests/sim_chato.py` and then in one real conversation.

| Hypothesis | Number | Reason |
|---|---|---|
| H1: first ask for the silver pack | 188 | menu: `opening_ask` |
| H2: his best price for the silver pack | 110-122 | Abuela's best was 73-81% of list, list is 150 |
| H3: messages before his final offer | about 3 | Abuela 0.85 gave 5-7, so about 8 x trait |
| H4: he ends the thread on a repeated price and dislikes insulting prices | n/a | memory 0.9, strictness 0.85 |
| H5: his bid for an uncommon (list 26) | 13-16 | Abuela's bid was about 52-60% of list |

Our leaving prices today: pack 122 P (value 135.9 P to us, 10% margin).

First real contact, proposal: sell one spare uncommon, not the 150 P pack.
- The stake is small. The most we can lose is the gain over Abuela's 13 P.
- It tests H3, H4 and H5 at low cost.
- Our leaving price (floor) is 13 P, because Abuela pays that.

Simulation (`tests/sim_chato.py`, uncommon sale, 72 worlds where a deal can beat our floor of 13):

| Opening | Pacing | Deals | Average price |
|---|---|---|---|
| 31 (list x 1.2, the default) | 15% steps | 48 of 72 | 15.5 |
| 31 | over 2 messages | 54 of 72 | 16.6 |
| 22 | over 2 messages | 63 of 72 | 15.9 |
| 18 | over 2 messages | 66 of 72 | 14.9 |

The simulation rests on the assumptions in its docstring. Proposal for the first contact: `--open 22`, pacing over 2 (the agent now guesses 2 from his patience trait). It closes more deals than 31 and costs little price.

Checks after the first conversation:
1. Did he open where H1 or H5 says?
2. How many messages before his final offer? (H3)
3. Did he end the thread for a repeat or a low price? (H4)

## Pooled prior (all dealers together)

Not built yet. Plan: prices as a share of list price, patience as a function of the patience trait. It starts a new dealer. A real conversation replaces it.
