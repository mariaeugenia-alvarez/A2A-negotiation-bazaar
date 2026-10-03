# The Bazaar · Negotiation One-Sheet (master, v5)

Saturday 3 Oct 2026, 13:05 (tick 583) · Team 9 · Spanish version: `ONE_SHEET.es.md` · Loops and experiments: `PLAYBOOK.md`
**This sheet is the source of truth for today and tomorrow.** Strategy approved by Thameur at 13:35, except the delivery day, which stays a hypothesis. If another document disagrees, this one wins. Fix the
other document.
**Clock note:** the game paused 13:14–15:34, so every time below comes from `/api/schedule` at 16:31 (game hour 7.6). Re-read it if the game pauses again.
Sources: `RULES.md`, kickoff slides, Day 2 Hints, **organisers' Duels slides**, `GET /api/schedule`, our logs
(`logs/score.jsonl`, `logs/duels/`, `TRADES.md`, `DEALERS.md`).
✅ = checked in a source or our data · ⚠️ = my inference · ❓ = unknown
Shape borrowed from *Never Split the Difference* (Voss), appendix "Negotiation One Sheet": goal, summary,
labels, calibrated questions, noncash offers. We kept the parts that work in a game where code sets prices
and every round of talk costs points. Section VIII says what we kept and what we dropped.

---

## 0. Where we stand (tick 583) ✅

| | Morning (tick 249) | Now (tick 572) | Comment |
|---|---|---|---|
| **Total score** | 10.4 · rank 16 | **20.2 · rank 15** | Peak 23.0 and rank 9 at tick 470, then other teams caught up |
| Negotiating (of 30) | 4.8 | 12.7 | **Relative to the field**: the median team went 10.8 → 16.2 |
| Market (of 30) | 4.8 | 7.5 | Free stall. Market Test efficiency 0.899 → 0.933. Top teams 10.6–12.1 |
| `neg_points` (team trades) | 0 | **23.5** | Our biggest source. ≈ the value we gained in team trades (+24 by `TRADES.md`) ⚠️ |
| `duel_points` | 0 | **5.98** | Duels I: 18 deals out of 34 |
| `ladder_points` (dealers) | 0 | **0.14** | 13 dealer deals moved it almost nothing |
| Cash · cards | 501 P | 326 P · 33 cards | **Lavapiés page complete** (+106 P of bonus in total, shown as +106 on each card's value) |

**What this means:** our points came from team trades and duels. Dealers have paid almost nothing in score.
Because the score is relative, standing still loses rank.

---

## I. THE GOAL

**Saturday goal (best case, written down so we don't settle for less): top 8 by 23:00.**
**Sunday goal: top 5 at the freeze.**

| Lane | Specific target | Why it is reachable |
|---|---|---|
| **Duels II (≈20:35)** | **No duel left unanswered.** Deal rate ≥ 80%. Median ≤ 2 rounds. Average result per deal ≥ 18 | Duels I: deals in ≤ 2 rounds averaged **20.4**, deals in ≥ 4 rounds averaged **5.7**. Our silence cost us 8 duels |
| **Team trades** | `neg_points` 23.5 → **45** by 23:00. Every trade must gain value | Six small trades already gave +24. The quoter is ready (not live) |
| **Pages** | Complete **Salamanca** (missing SAL-06, 07, 09, 10). Never break Lavapiés | Page bonus = +25% of the page total, paid ONCE (each card's value shows it because selling any card loses it) ✅ |
| **Dealers** | Only trades that gain value: page cards bought below their value, spares sold above it. **Never a sale below our value, never a page card** | Dealer score is tiny. Their use is cheap cards and unlocks, not points |
| **Market** | Keep 7.5 or better. v21 is open without a broker (VII): decide on Maru's broker **before the next Market Test**, not at the hard one (now Sunday ≈09:35) | Top teams are at 10.6–12.1 |

Voss's four goal steps: set it, write it down, say it to a teammate (Maru), carry it in. **The worst case we refuse:**
a deal outside our limit, a sale below our value, a duel with no answer.

### Hard rules (never broken, by code or by hand)
1. **Duels: never cross our limit.** As seller never below our cost, as buyer never above our value. Crossing it loses points and gives the rival nothing ✅ (organisers' slides).
2. **Never sell a card below what it is worth to us. Never sell a card of a complete page or a card we need for a page.**
3. **Nothing LIVE without an OK. Duels: Thameur. Cards (dealers, team trades, quoter): Maru.** Analysis is free. Negotiating spends real primas.
4. **One owner per lane on our shared key:** dealers = Maru's scripts, team trades = `trader.py`, duels = `duels.py`. Before posting any offer, say so in the other terminal.
5. **Prices come from code.** Words carry the price and ask for information. They never decide the price.

### What changed since v4 (this morning)
- **Measured:** team trades → `neg_points`, dealer deals → `ladder_points`, duels → `duel_points` ✅. The 30 negotiating points mix all three and are **relative to the other teams** ✅ (ours rose to 15.5, then fell to 12.7 while the median climbed).
- **Measured:** duel score = **our surplus × (1 − decay)^rounds**, exactly. Duel 2549: surplus 33 × 0.94 = 31.0. Duel 2327: 40 × 0.94² = 35.3 ✅.
- **New from the organisers:** you meet **every team twice** (once as seller, once as buyer). One message per tick. An accept settles next tick. The duel lanes have their own rate limits and never block trading ✅.
- **New from the schedule:** Duels II has **8% decay, 16 ticks, up to 6 duels at once**. Duels III and the Final have **10% decay and only 12 ticks** (3 minutes at Sunday's 15-second ticks) ✅.
- **New:** Doña Pilar trades. Salamanca fever **≈18:05–20:05**: she pays 25% over book for Salamanca ✅ (schedule).
- **New:** Radio Rastro (`GET /api/news`). Some items are true and move the market, some are rumours ✅. Treat news as a hint, never as a fact.
- **Warning:** at tick 567 `neg_points` fell for the first time (24.2 → 23.5), right after the dealer scripts sold MAL-08 (21 P, worth 22.5) and SAL-07 (24 P, worth 27.5: our only copy, so Salamanca now misses it again) to Pilar. Cause not proven ⚠️: `DEALERS.md` measured on Friday that dealer deals did not move `neg_points`, so look elsewhere too. Hard rule 2 now covers it.

### Card values (unchanged, verified) ✅
- Value = book × our set multiplier × copy factor, plus the page bonus when the page is complete. **The trader reads values from the game** (`your_value` includes the bonus).
- Book: common 10, uncommon 25, rare 70, epic 180, legendary 450. Copy factor: 1st 1.0, 2nd 0.25, 3rd+ 0.1.
- Our multipliers: Lavapiés 1.6 (**complete**), El Retiro 1.3, Salamanca 1.1, Malasaña 0.9, Chamberí 0.7 (released Sunday), La Latina 0.5.
- **The side that accepts pays the fee** ✅. El Rastro: 5% + 1 P per card. If they accept our offer, we receive the full price.
- A dealer deal at the dealer's opening price does not count ✅. Only the best 3 deals per dealer count ✅.
- Master bonus (10% in the catalog): ❓ not measured. We have no master page.

---

## II. SUMMARY (what each side should answer "That's right" to)

Use these as the opening line of a message or as the frame behind our code. They state the facts from **their** side.

| Counterparty | Summary |
|---|---|
| **Duel rival** (an LLM agent from another team ✅) | "Every round we talk, the pie shrinks for both of us (6–10%). If nobody answers, we both get zero. You want a quick, fair deal inside your limit, and so do we." |
| **Duel rival, price + day** | "We each care differently about the delivery day. If the day goes to whoever cares more, the pie grows for both of us, and the other side gets paid in price." |
| **Other teams** | "You are building pages, and a missing card is worth much more to you than a spare is to us. Your offers expire in about 2 ticks, so you want quick, clear answers." |
| **Abuela** | "You are patient, you move only when we move, and you reward kind, steady customers. A full page matters more than loose cards." |
| **El Chato** | "You trade straight. You don't move for tiny steps, and you never give more than we do." |
| **Doña Pilar** | "You collect what others throw away. You pay over book for the cards you love, and Salamanca is your fever this afternoon." |

## III. LABELS / ACCUSATION AUDIT

**Where words can matter:** duel rivals and other teams, which are LLM agents with hidden wishes ⚠️. **With dealers,
words never move the price** ✅ (their code does). There, labels only buy information and goodwill.
**Cost rule:** a label rides in the **same message as a price**. It never costs an extra round.

| Who | Accusation they may make | Labels (pick one per message) |
|---|---|---|
| **Duel rival** | "You open too greedy / you waste rounds" | It seems like you want to close this quickly. · It seems like a fair split matters to you. · It seems like the delivery day matters a lot to you. |
| **Other teams** | "You ignore offers / you lowball / you sold to someone else" | It seems like this card completes your page. · It seems like speed matters to you, since offers expire fast. · It seems like you've had offers ignored before. |
| **Abuela** | "You drive a hard bargain" (her words) | It seems like you've met many hard bargainers. · It seems like you value kind customers. |
| **El Chato** | "You're trying to be clever" | It seems like you value straight dealing. · It seems like small steps don't impress you. |
| **Pilar** | "You only come when I pay more" | It seems like Salamanca is close to your heart. · It seems like you know what others overlook. |

Accusation audit for duels, sent once, with our opening price: *"You'll probably think this opening is a bit firm. It's
built so we can close in one or two rounds without losing the pie."*

## IV. CALIBRATED QUESTIONS (What / How, never Why)

| Who | Questions | What we do with the answer |
|---|---|---|
| **Duel rival, price + day** | How much does the delivery day matter to you? · What would an earlier (or later) day change for you? | Give the day to whoever cares more. His answer is a hint, his **trades of day for price** are the proof |
| **Duel rival, price only** | What would make this work for you right now? | Nothing in code. Words don't change our limit |
| **Other teams** | How does this card fit into your page? · What would make this swap work for you? · What else are you missing? | Their gaps tell us what our spares are worth to them. Fill them with standing asks |
| **Abuela** | What do you look for in a customer? | Goodwill only. Her price follows her rule (`bz/predict.py`) |
| **El Chato** | **Do not ask.** Every message to him carries a new price, or it counts as spam | |
| **Pilar** | Which cards are you hunting today? | Tells us which spares to bring her |

## V. NONCASH OFFERS

| Who | What they can give besides cash |
|---|---|
| **Duel rival** | **The delivery day (0–10)** ✅. Trade the day we care less about for price |
| **Other teams** | Card-for-card swaps ✅ (our two LAV-06 spares for their page cards). **Fee saving:** when they accept our standing offer, they pay the fee ✅. Long-lived standing offers (`expires_in_ticks` up to 120) |
| **Abuela** | Gifts (she gave us a card in thread 108) and tips ("a full page is worth much more", "swap your duplicates") ✅ |
| **El Chato** | Better packs and rare singles ✅. **Three good deals unlock the next dealer early** ✅. Bought LAV-09/LAV-10 from him below value (+23, +28) |
| **Pilar** | Pays **over book** for the cards she loves ✅. Sells gold packs ✅ |

---

## VI. DUEL DOCTRINE (Duels II, III and the Final)

### What Duels I taught us ✅ (30 duels, session 2, from `logs/duels/`)
| Fact | Number |
|---|---|
| Deals | 18 of 34 (53%); 16 no-deals, 6 with a silent rival. Practice: 53% |
| **Deals in ≤ 2 rounds** | 8 deals, average result **20.4** |
| **Deals in ≥ 4 rounds** | 8 deals, average result **5.7**. Worst: duel 2486, 9 rounds, result 0.6 |
| **Our agent went silent from tick 503 to 553** | **8 duels lost:** 5 where the rival offered inside our limit (2485: he climbed to 106 over our cost of 85, no answer from us) and 3 where we never opened. About +60 of result missed (≈ +25% on our total) |
| Rivals often open **inside our limit** | 2338, 2549, 2325: taking it fast scored 12–31 |
| Rivals reciprocate | A real step from us earns a real step. 1 P steps earn 1 P steps and burn rounds |

### The rules for Duels II, III and the Final (approved by Thameur, 13:35)
1. **Answer every duel, from its first tick.** No silence by accident. Run `python3 duels_watch.py` (built, b5b9c13): it starts `duels.py` when duels go live, restarts it after a crash or when a live duel has waited 3 ticks for us, and alerts DUEL_START / DUEL_SILENT / DUEL_CRASH in `logs/alerts.jsonl`. **Only Thameur's machine runs it** (decided 14:00). Maru does not start `duels.py` or `duels_watch.py`, or two agents would talk in the same duels.
2. **Our limit is firm.** As seller never below our cost, as buyer never above our value. Everything else adapts.
3. **First offer: ambitious, but one the rival can accept.** Not an extreme anchor. Where Duels I deals landed ✅: as buyer 0.69–0.99 of our limit (median ≈ 0.87), as seller 1.04–1.46 (median ≈ 1.22). Our code opened at 0.55 / 1.45, outside that zone. **Proposed start, to check in simulation:** buyer ≈ 0.75 × limit, seller ≈ 1.30 × limit ⚠️.
4. **Read the bot in front of us, then adapt in real time** (next block). This is where the extra price comes from.
5. **Accept rule:** accept his offer if it is inside our limit and the extra we can still win is **less than what one more round costs** (8% or 10% of the surplus on the table), or if fewer than 3 ticks remain.
6. **At most 2 counters**, each a **real step** (no 1 P steps). Then take the best offer inside our limit.
7. **If his offers never come inside our limit, no deal is correct** (duel 2487).
8. **Every priced message in Duels II/III includes `days`** (otherwise `400 missing_days`) ✅.

### Read the bot: what Duels I and practice show ✅ (61 duels, `logs/duels/`)
- **A round is an exchange, not a tick.** A round counts only when he answers one of our offers. When only he talks, the round counter stays at 0 (duel 286: 12 messages from him, 0 rounds; duel 2485: he climbed 53 → 106, 0 rounds).
- **Bots concede even when we stay silent:** in 89 of 104 cases his next offer moved our way with no message from us, by **4.2 P** on average. After a message from us he moved **6.0 P** on average.
- **About half of the bots open already inside our limit** (12 of 25 when we buy, 9 of 25 when we sell).
- **Aliases are not teams.** The same 8 names (Rival Oro, Plata, Rojo…) appear across many duels. We cannot remember a team by its alias.

**How we adapt, per bot (decided from his first 1–3 messages):**
| What the bot does | What we do |
|---|---|
| **Opens inside our limit with a good surplus** | One real counter at most to test him, then accept. Don't burn a round for little |
| **Keeps conceding on his own while we are silent** (time-driven) | **Stay silent and let him come to us.** It costs no round. See "The waiting play" below |
| **Moves only when we move** (reciprocal) | Real steps from us: he answers in proportion (practice: our 1–5 P steps earned 5–14 P from Rival Rojo). Up to 2 counters, then accept |
| **Barely moves, or stays outside our limit** (hard) | One real step to test him. If he still does not come inside our limit, a no-deal is correct |
| **Answers our words** (mirrors, labels, asks) | Log it. Words ride with the price and never change our limit |

### The waiting play (approved by Thameur, 14:00) ✅ data · ⚠️ simulation
**Why:** waiting costs no round, so the deal keeps its full value. Bots that talk first keep conceding to the very end, often with their biggest steps in the last ticks. In 20 duels, our back-and-forth earned no more than accepting their first offer (341 vs 346). Simulation (`tests/sim_duel2.py`, a model, not a measurement): 64% of the pie vs 54% for the old logic (decay 8%), 56% vs 47% (decay 10%), with slightly fewer deals (87–89% vs 96%).

| Step | What `duels.py` does |
|---|---|
| 1. Tick 0 | **Sends nothing.** Watches |
| 2. He talks and concedes on his own | **Stays silent.** Accepts his best offer inside our limit **2 ticks before the deadline** (an accept settles next tick; 2 ticks is proven, 1 tick is not). Accepts earlier if he is inside our limit and has not moved for 2 ticks (probably his real limit) |
| 3. He is still silent at tick 1 | **Opens:** buyer 0.75 × limit, seller 1.30 × limit. Then goes quiet again and watches whether he keeps moving on his own |
| 4. He moves only when we move | Real steps, at most 2 counters, accept when one more round can't beat the decay |
| Always | Never crosses our limit (checked on 4,000 random duels in `tests/test_duel2.py`) |

**Run (Thameur's machine only):** Saturday `python3 duels_watch.py` · Sunday `python3 duels_watch.py -- --duel-ticks 12`. Simulation warns: against harder rivals on Sunday the deal rate may fall to ≈68%, under the 70% switch.

**Safety switch:** if after the first wave of Duels II fewer than 70% of duels close, or the bots stop conceding on their own, restart with `--policy v1` (the old logic).
**Risks we accept:** some bots never talk first (3 duels in Duels I had no message at all; step 3 covers it). Only 12 of 64 logged duels had the rival talking first, so the data is thin. Other teams may change their bots tonight.

### The delivery day (Duels II and III): a hypothesis, not a rule yet ⚠️
- ✅ Each side has a private `your_days_weight` (a gain or a cost per day). The deal is worth price surplus + weight × day to each side. The organisers: "give the day to whoever cares more, trade it for price".
- **Thameur's direction:** use the day as **leverage combined with our price**, not as an automatic push to day 0 or 10.
- **Hypothesis to test in Duels II:** read which day he asks for first and how much price he gives when the day moves. Then offer packages where we give ground on the day he cares about and take it back in price. Compare result per deal with and without day moves.
- **When Duels II opens (≈20:35):** check that `days_meaning` is read with the right sign (scheduled check in this session).

### Duels calendar ✅ (from `/api/schedule`, Madrid time estimated from tick 583 at 13:03)
| Session | Real time ≈ | Clock | Decay per round | At once | Issues |
|---|---|---|---|---|---|
| Duels II | **Sat ≈20:35** | 16 ticks (8 min) | 8% | up to 6 | price + day |
| Duels III | **Sun ≈13:35** ⚠️ | 12 ticks (3 min) | 10% | up to 4 | price + day |
| Grand Final | **Sun ❓** (game hour 21.65 falls after Sunday's 15:00 close in the current schedule; watch `/api/schedule`) | 12 ticks (3 min) | 10% | up to 4 | price + day, on the big screen |

---

## VII. THE OTHER LANES

### Team trades (`trader.py`, owner: trader session) ✅
- **Buy:** value received − cash − fee > margin. **Sell:** never below our value, spares first, never a card we need for a page.
- **Quoter (built, not live):** standing bids for our missing page cards and asks for spares. The guard stops it when it should. Plan at tick 568: bids RET-02..05 at 8, SAL-06/07 and MAL-06/08 at 20, RET-09 at 68, an ask for the LAV-06 spare at 20. 180 P committed, +79 of value if everything fills. **Needs Maru's OK.** ⚠️ Cash is **48 P** (15:36, after the v21 bond): the 180 P plan does not fit. Trim it to the cash (`--quote-budget`) or wait for the bond to come back.
- **Lessons from this morning:** never offer one card to two teams at once. Open sales above the best bid seen. Re-check stale bids (a fill after we got the card elsewhere buys a duplicate worth 25%).

### Dealers (Maru's scripts: `agent.py`, `bz/predict.py`, `DEALERS.md`) ✅
- **Abuela:** her first answer gives away her limit (L = A − 2·d1). Model error ≈ 0.4–0.7 P.
- **El Chato:** schedule a·k², never gives more than our step. Model exact 77–98%. Rares 97 → 79 in 6 answers.
- **Pilar:** buys MAL/SAL near book. **Salamanca fever ≈18:05–20:05 (+25% over book).** Decision for the team: sell her Salamanca only if we give up on completing Salamanca.
- **Guard (Maru):** `agent.py sell-spares` only sells copies beyond the first and never below `sell_floor(value)`. `--limit` can no longer cross `sell_floor`/`buy_cap` (15:36). Crossing the value bound needs Maru's OK with the loss in primas (`CLAUDE.md`).

### Market ✅
- Free stall: efficiency 0.933, market 7.5. Top teams 10.6–12.1.
- ✅ **At tick 575 someone on our key opened our own venue v21** (board, 0% fee, 270 P with a 250 P bond that comes back later). The free stall v12 closed. Cash fell to 75 P. No broker runs for v21 on Thameur's machine. A board without a broker scored 3.33 in Market Test 1 (Team 13). ❓ Who opened it, and does Maru's broker (`broker.py`, c9d2ea1) run for it before the next Market Test (≈17:55)?
- Market Tests at ≈17:55, 19:55, 21:55. **The hard test (firmer, more impatient traders) moved to Sunday ≈09:35**, then ≈09:55, 11:55, 13:55.

---

## VIII. WHAT WE TOOK FROM THE BOOK, AND WHAT WE LEFT OUT

| From *Never Split the Difference* | Verdict | Why |
|---|---|---|
| A specific, ambitious goal, written down and shared | **Kept** (Section I) | Costs nothing. Stops us settling for the first number |
| Summary that earns a "That's right" | **Kept** for duels and teams | The rivals are LLM agents. A shared frame may speed up a deal ⚠️ |
| Labels and accusation audit | **Kept, one per priced message** | Free when it rides with a price. **Never with dealers for price**, their code decides |
| Calibrated What/How questions | **Kept** for the delivery day and team trades | They hunt for hidden information (the rival's day weight, the team's page gaps). This is where words can pay |
| Noncash offers | **Kept** | The delivery day and swaps are real noncash currency here |
| Ackerman bargaining (65 → 85 → 95 → 100%) | **Dropped** | Four rounds cost 22–34% of the pie at 6–10% per round. Duels I proved it: deals in ≥ 4 rounds averaged 5.7 versus 20.4 |
| Extreme anchors | **Dropped** | The organisers' rule is "open with an offer the other side can take". Each round of distance costs points |
| Precise, non-round numbers (37, not 40) | **Kept** | Free. Signals a calculated price |
| "No deal is better than a bad deal" | **Kept** as a hard rule | A deal outside our limit loses points |
| Long rapport building, late-night DJ voice, mirroring for time | **Dropped** | One message per tick, and time costs pie. Text and code, no voice |
| Black Swans (hidden facts that change everything) | **Kept as a habit** | Read the schedule, `/api/news` and the feed: the Pilar fever and the duel decay were Black Swans hiding in plain sight |

---

## IX. TIMELINE AND DECISIONS

### Today (Madrid, estimated from the schedule)
| ≈ When | What | Who |
|---|---|---|
| 17:55 | Market Test 4 | read only |
| **18:05–20:05** | **Pilar's Salamanca fever** | dealer scripts (Maru), only if the team agrees |
| 19:55 | Market Test 5 | |
| **already on** | **`python3 duels_watch.py` runs on Thameur's machine since 15:52** (v2 = the waiting play, approved 14:00; `--policy v1` = safety switch) | trader session + Thameur |
| **≈20:35** | **Duels II** (8%, 16 ticks, up to 6 at once). Days-reading check when it opens | `duels.py` |
| 21:00 | Review of Duels II and the algorithm for Sunday (reminder set) | Thameur + this session |
| 21:55 | Market Test 6 | |
| 23:00 | Doors close | |

### Sunday
09:00 opens (15-second ticks) · ≈09:35 hard Market Test · ≈11:35 round 3 starts at zero, **Chamberí released**, +150 P for everyone ·
**≈13:35 Duels III** ⚠️ · 15:00 doors close. Grand Final, dealer close and freeze: ❓ the current schedule puts them after 15:00, so it will probably change again.

### Decisions for Thameur and Maru now
1. **Quoter LIVE?** 180 P of standing bids for page cards, +79 of value if all fill. Cash is 48 P: with what budget?
2. **Maru:** block dealer sales below our value and sales of page cards. Do we sell Salamanca to Pilar during the fever, or finish the page?
3. **Duels II:** ✅ doctrine in VI approved at 13:35 (the delivery day stays a hypothesis). The waiting play approved at 14:00. Built by the trader session in `bz/duel.py` (`--policy v2`, the default). **Duels run on Thameur's machine only:** `python3 duels_watch.py`.
4. **Market:** v21 is open. Who runs a broker for it, from when? Otherwise it may score below the free stall's 7.5.
5. **Who watches the score** during Duels II (`observe.py tag D2`).

### Open questions ❓
- The exact formula that turns `neg_points`, `duel_points` and `ladder_points` into the 30 negotiating points.
- Why `neg_points` fell at tick 567.
- The master bonus.
- Whether words change an LLM rival's price (test one wording against another in team trades first).
