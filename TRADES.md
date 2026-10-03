# Trades · Saturday 3 Oct (round 2), Team 9

Every trade of ours from the round start to tick 381, from the game's own records: settlements in the feed, thread
offers ("settled") and each card's history (`GET /api/cards/{id}`). Value = what the card is worth to us at that moment
(book × our set multiplier × copy factor; page bonus noted where it applies). Gain = value received − value given ± cash.

## Team trades (feed `neg_points`)

| Tick | What | Price | Fee | Our value | Gain | Who | Note |
|---|---|---|---|---|---|---|---|
| 331 | **Sold MAL-10** to Team 13 | 65 | paid by them | 63 | **+2** | trader.py (our counter to their 56 bid) | ⚠️ Sold cheap: Team 17 had a 70 bid open, Friday's bids reached 82. The card was also in counters to Team 17 (81) and Team 13 (73) at the same time. |
| 353 | Bought LAV-04 from Team 18 (El Rastro ask) | 9 | 2, by us | 16 | **+5** | trader.py (`--live-boards`) | |
| 380 | Bought MAL-07 from Team 6 (El Rastro) | 17 | 2 | 22.5 | +3.5 (if we paid the fee) | not trader.py (paused since 11:09) | Who made it: to confirm |
| 380 | Bought SAL-08 from Team 2 (El Rastro) | 20 | 2 | 27.5 | +5.5 (if we paid the fee) | not trader.py | Who made it: to confirm |
| 381 | Bought MAL-04 from Team 6 (El Rastro) | 8 | 2 | 9 | **−1** if we paid the fee, +1 if they did | not trader.py | ⚠️ A possible loss |

## Dealer deals (feed `ladder_points`)

| Tick | Thread | What | Price | Our value | Gain | Who | Note |
|---|---|---|---|---|---|---|---|
| 333 | 492 | Sold LAT-05 to Abuela | 5 | 1.2 | +3.8 | dealer script (trade #4869) | trader.py also sent its own offer at 6: it did not settle. The trader's log wrongly marks it "accepted". |
| 337 | 503 | Sold LAT-02 to Abuela | 6 | 1.2 | +4.8 | **trader.py** accepted her offer (trade #4939) | ⚠️ Not the haggle logic: excluded from learning (`bz/learn.py` EXCLUDE) |
| 339 | 510 | Bought LAV-06 from El Chato | 33 | 40 | +7 | dealer script | ⚠️ 33 is his opening price and he never moved (also thread 495). **Probably does not count** for the ladder or the early unlock. |
| 342 | 511 | Sold SAL-04 to Abuela | 6 | 2.8 | +3.2 | dealer script (trade #5017) | |
| 347 | 518 | Sold LAV-03 to Abuela | 6 | 4.0 | +2 | dealer script (trade #5116) | trader.py also sent its own offer at 8: it did not settle |
| 352 | 526 | Bought **LAV-10** from El Chato | 84 | 112 | **+28** | dealer script | He opened at 97 |
| 361 | 543 | Bought **LAV-09** from El Chato | 89 | 112, **+106 page bonus** | **+23**, and it completed Lavapiés | dealer script | He opened at 97 |
| 369 | 552 | Sold LAV-02 (a second copy, from the welcome pack) to Abuela | 5 | 4.0 | +1 | dealer script | |

## What the score did (logs/score.jsonl)

| Tick | Event | neg_points | ladder_points |
|---|---|---|---|
| 249 | round start, no deal yet | 0.0 | 0.0 |
| 331 | MAL-10 sold to Team 13 | **4.0** | 0.0 |
| 337 → 347 | Abuela deals | 4.0 | 0.012 → 0.049 |
| 353 | LAV-04 bought from Team 18 (+ LAV-10 from El Chato) | **7.2** | 0.068 |
| 362 | LAV-09 from El Chato | 7.2 | 0.077 |

## Verified rules (use these, not the older notes)

1. **Team trades move `neg_points`. Dealer deals move `ladder_points`.** Dealer deals left `neg_points` unchanged five times in a row.
2. **The side that accepts pays the venue fee.** We received the full 65 when Team 13 accepted our offer. We paid 9 + 2 when we accepted Team 18's ask.
3. **Page bonus = 25 % of the page's total card value, added to every card of the complete page.** Lavapiés totalled 424, so +106 per card: commons 16 → 122, uncommons 40 → 146, rares 112 → 218. Selling one card of a complete page loses the whole bonus.
4. **A dealer deal at the dealer's opening price does not count** (rules). El Chato sells uncommons at 33 and does not move. Rares go 97 → 84–89.

## Mistakes and their fixes

| Mistake | Fix | Where |
|---|---|---|
| trader.py acted on Abuela's offers inside the dealer script's threads | Dealers' offers (maker abuela/chato/pilar, or no venue) are ignored | `bz/trade.py` judge() |
| One card offered to two teams at once | A card in one of our open offers is never offered again (`reserved`) | `bz/trade.py`, `trader.py` |
| MAL-10 sold below bids we had seen | A sale counter opens above the best bid seen for that card in the last 60 ticks, and we never accept below it | `bz/trade.py` anchor(), `trader.py` |
| Our value formula ignores the page bonus (would sell LAV-01 at 16 when it is worth 122) | Values come from the game (`GameValues`) | `bz/trade.py`, `trader.py` |
| Counter price counted a fee the other side pays | Counter clearing price without our fee | `bz/trade.py` |
| Cash check mixed up two sessions' trades (95 P "spent" = 11 ours + 84 El Chato) | Read the settlement from the feed, not our cash | `trader.py` |
| A counter marked "accepted" when the deal came from the thread | Match settlements on the card, and keep the trade id | `trader.py` |

## Resumen en español

- **Tratos con equipos → `neg_points`. Tratos con dealers → `ladder_points`.** Paga la comisión quien acepta. **El bono de página es el 25 % del total de la página en cada carta.** Completamos Lavapiés.
- **Errores:**
  - El trader actuó en un hilo de Abuela (503).
  - Ofreció MAL-10 a dos equipos a la vez y la vendió barata (65, con pujas vistas de 70–82).
  - Su fórmula ignoraba el bono de página.
  - LAV-06 se compró al precio de apertura de El Chato (33): seguramente no cuenta.
  - Las compras de los ticks 380–381 no son del trader: falta confirmar quién las hizo. MAL-04 pudo ser una pérdida de 1 P.
- **Los arreglos están en `bz/trade.py` y `trader.py`, con pruebas.**
