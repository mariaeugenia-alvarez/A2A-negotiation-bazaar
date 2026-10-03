# The Bazaar · Negotiation One-Sheet (master, v4)

Saturday 3 Oct 2026 · Team 9 · Spanish version: `ONE_SHEET.es.md`
All five sections are filled. Sections II–IV are untested drafts. The loops and experiments are in `PLAYBOOK.md`.
Sources: `RULES.md`, kickoff slides, **Day 2 Hints**, the desk, our own data and logs.
✅ = checked in a source or our data · ⚠️ = my inference · ❓ = unknown

---

## I. THE GOAL

**Today's goal: find out which of the three places gives us the most points, then put our effort there. Meanwhile, do not lose the points that are sure.**

### What changed since the first draft (read this first)
- **Corrected:** dealers are not capped at about 6 deals. More dealers arrive today (levels 3–5), higher levels weigh more, and three good deals with one dealer unlock the next early.
- **Corrected:** "no market has traded" only meant team markets had not opened yet. They opened at game hour 3.0.
- **Explained:** each day is its own round and **today starts at 0**. That is why our `neg_points` and `ladder_points` dropped to 0.0. Today's experiments are clean.
- **Confirmed:** the desk said a silent duel rival means zero for both sides. They would not tell us how the 30 points split. We find out by experiment.
- **New from the hints:** a deal above your own value costs points. Open duels with an offer the other side can take. Read `GET /api/me/offers` every tick. Post standing bids and swaps with `expires_in_ticks`.
- **New in our data:** we have a free stall (`v12`). Market Test 1 gave it 89.9% efficiency and a market score of 4.8. The game runs about 30 minutes behind the plan.

### 1. Where the points are ✅
- 100 points: **Negotiating 30**, **Market 30**, **Judges 40**.
- Negotiating comes from three places: **duels**, **dealers** (Abuela, El Chato and new ones), **trades with other teams**.
- Friday counts half, Saturday and Sunday count in full. Friday's deals do not help today's round.
- **We do not know how the 30 points split between the three.**
- Never counts: number of trades, number of listings, fees, pack luck, gifts.
- **Scores may be relative to other teams** ⚠️ (leader near 30, last team at 0).

### 2. The three places ✅

| Place | Facts |
|---|---|
| **Duels** | Practice: 32 duels, we closed all 15 where the rival answered. The 12 with a silent rival scored zero. Fewer than half of all practice duels ended in a deal (hints). Each round of talk shrinks the deal: 6% (Duels I), 8% (II), 10% (III and Final). Checked on our data: 26 × 0.94³ = 21.6. Duels II add a delivery day (0–10): find out who cares more about time. |
| **Dealers** | Only the best 3 deals per dealer count, and an empty slot is zero. A deal at the opening price does not count. Today's round starts empty for Abuela too. We have 0 with El Chato. Dealers notice spam. The same price is not a move, 20 → 21 → 22 is. Dealer prices come from their own rules. |
| **Trades with teams** | Offers made for us last about 2 ticks. Last night Teams 13, 10 and 12 asked to buy our rare MAL-10 for 45, 75 and 82 P. It is worth 63 P to us. **We never answered.** We can also post bids for any copy of a card, or swaps, with `expires_in_ticks` up to 120. |

### 3. Card values: the rules we use ✅
- **Value of a card** = book price × our set multiplier × copy factor. Checked on MAL-10: 70 × 0.9 = 63, and a second copy 70 × 0.9 × 0.25 = 15.75.
- **Book prices:** common 10, uncommon 25, rare 70, epic 180, legendary 450.
- **Copy factor:** 1st copy 1.0, 2nd 0.25, 3rd and later 0.1. So spares are worth little to us and a lot to a team that misses the card.
- **Our private set multipliers:** Lavapiés 1.6, El Retiro 1.3, Salamanca 1.1, Malasaña 0.9, Chamberí 0.7, La Latina 0.5. Our best page to finish is Lavapiés.
- **Never pay above your own value.** Sell spares first, never below what the copy is worth to us.
- ❓ **Page bonus** (25% in the catalog, 10% for the master) is **not** in `your_value`. How it is counted is unknown. Until we measure it, a card that completes a page goes to a person, not to the automatic rules.
- ✅ **Fees:** the side that accepts an offer pays the venue fee (SDK). El Rastro charges 5% + 1 P per card. Posting our offer and letting them accept can save us the fee ⚠️.

### 4. The experiments (one action, one number to watch)
All our scores are 0.0 now, so every change today is clean. Our numbers are in `GET /api/me` → `score` and refresh about every 5 ticks. Write down the number **before** and **after**.

| # | Do this | Watch this | It tells us |
|---|---|---|---|
| E1 | Finish the first scored duel (Duels I) | `duel_points` | Do duels give points? How many per deal? |
| E2 | One small trade with another team | `neg_points` | Do team trades give points? Does it match the value we gained? |
| E3 | One deal with El Chato (we approve it first) | `ladder_points` | Do dealers give points? Which price counts as good? |

- **One thing at a time.** Two actions together hide which one moved the number.
- **Real trades cost primas.** Theory first, free simulation next, then real trades **only with your approval.**

### 5. The auto-negotiator for offers sent to us (plan, not built yet)
- **Reads the structure only** (`give` and `want`), never the words. The rules say: check the offer, not the message.
- **Buy:** accept only if (value we receive) − (cash we pay) − (fee) clears a margin.
- **Sell:** never below the value of the copy we give. Spares first.
- **Before every accept:** we still own the card, we have the cash, the offer has not expired, and only one accept per tick (the best one). Our first El Chato thread ended in `not_owner` because the card was already sold.
- **Also post standing bids** for the cards we need, below our value, and asks for spares, above it, with a long expiry.
- **Read `GET /api/me/offers` every tick.** Use `next_tick_in` from `GET /api/clock` or the event stream. A 429 means "wait for the next tick", not an error.
- **Test case today:** Team 5 offers a copy of LAV-02 for 10 P. We already hold one, so another copy is worth 4 P to us (16 × 0.25). The rules would reject it. It would also have turned down the 45 P bid for MAL-10 and taken the 75 P and 82 P ones.
- **Shadow mode first:** it prints what it would accept or counter and sends nothing. Automatic accepts come later, for clear wins only, with your approval.

### 6. The verbal side (labels, mirroring, questions): what we really know
- ✅ Dealer prices come from their own rules. Prompt injection changes what they say, never their prices.
- ✅ Every message we sent a dealer was a fixed polite template with a price. We never tried labels, mirroring or questions, and never sent a blunt control. **We have no test of whether tone changes a price.** In 11 Abuela exchanges she dropped about 1 P per raise whatever the template (too few to prove anything).
- ✅ Words do give **information**. Abuela told us "a full page is worth much more", "your spare is worth gold to someone who lacks it", and that El Chato "likes people who trade straight".
- ✅ Dealers use these tools on us. El Chato mirrored our price ("Veintidós, dices… trece primas") and labelled us ("Yo no me muevo si tú apenas te mueves").
- ✅ Other teams use them too. Team 13 wrote: "It looks like Malasaña is not your focus, while it is ours."
- ⚠️ **Hypothesis to test later:** words may pay where the other side is an agent with hidden wishes: team trades and the price-and-days duels. Test one change at a time.

### 7. Clock (Madrid time) ✅⚠️
**The game is about 30 minutes behind the plan.** Market Test 1 was planned for 09:21 and started near 09:50 (tick 201).

| Plan in the hints | Likely real time |
|---|---|
| 09:21 team markets open + Market Test 1, then every 2 h | started ≈ 09:50 |
| 11:30 Duels I scored | ≈ 12:00 |
| 18:00 Duels II (price + day) | ≈ 18:30 |
| all day: new dealers arrive (big screen, `GET /api/levels`) | |
| 23:00 doors close | 23:00 |

Check `GET /api/schedule` for the real times. Tomorrow: ticks of 15 s, Duels III and the Final duels (10% per round), dealers close, scores freeze.

### 8. Markets (30 points) ✅
- **Three kinds of market:** the house (El Rastro: 5% + 1 P per card, posted offers, no broker), a `board` venue (its owner's broker matches offers: keep it running), an `auto` venue (the engine matches best bid and best ask every tick).
- **Fees never score.** What scores: the Market Test (same synthetic book for every venue, every 2 h) and value created between other teams on your venue.
- **We already have a free stall:** `v12`, auto, 3% fee, no bond, opened at tick 201. Full points go to the mean of the top three venues.
- **Market Test 1 result (ticks 201–217) ✅:** our stall realised **89.9%** of the possible gains and got **0.5 bench points**. After the score refresh (tick 220) our market score is **4.8**. Teams 14 and 18 show the same 4.8, as expected for identical free stalls.
- **The best market score is Team 12 with 8.01** (a `board` venue, 0% fee). That is about **+3.2 over the free stall** after one session ⚠️. It had 1 trade of 7 P, so most of it is probably the Market Test, not trades. How they matched is unknown. Each later session counts separately and the round averages them.
- **18 venues are open,** 7 opened by teams, almost all at 0% fee. Our own agent cannot trade on our own venue.
- **Cost to open our own:** 250 P bond (comes back after a cooldown) + 20 P. It replaces the free stall. It only pays with a broker that estimates hidden limits better than the stall. We have no such broker yet.
- **Decision (proposal):** keep the free stall for now. The free stall already scores 4.8, and the extra for a smarter broker looks like about 3 points. Revisit after Market Test 2 (about 11:50), and only if a teammate has time to build the broker. Opening a venue with the starter broker would only repeat the free stall's score.

### 9. Decisions for the team today
1. **Approve the shadow-mode negotiator?** It only reads offers and prints decisions.
2. **Duel opening:** our code opens at 45% of our limit (`bz/duel.py`, tuned only in simulation). The hint says open with an offer the other side can take. Review it before Duels I (about 12:00).
3. **El Chato:** approve the theory and the free simulation, then one real deal at a time (E3). His three slots are empty, and three good deals unlock the next dealer early.
4. **Market:** keep the free stall (4.8 now) or build a better broker (the best team has 8.01). Decide after Market Test 2.
5. **Who watches the score numbers** before and after each experiment.

---

## II. SUMMARY (facts we want each side to answer "That's right" to) ⚠️ not yet tested

| Counterparty | Summary |
|---|---|
| Other teams | Pages are worth more to the team that misses a card. Offers to us last about 2 ticks, so you need quick answers. We hold spares and a few rares, and we value them by our own multipliers. |
| Duel rival | Every round of talk shrinks the deal for both of us, and if nobody answers we both score zero. You want a fast deal at a fair split, and so do we. |
| Abuela | You are patient, you like kind customers, and you move only when we move. A full page matters more than loose cards. |
| El Chato | You deal straight, you do not move for small steps, and your patience is short (about 3 messages before your last word). |

## III. LABELS / ACCUSATION AUDIT ⚠️ all untested

| Who | Likely accusation | Labels (3 each) |
|---|---|---|
| Other teams | "You ignore offers" / "you lowball" | It seems like this card completes your page. · It seems like speed matters to you, because offers disappear fast. · It seems like you have had offers ignored before. |
| Duel rival | "You open too low" | It seems like time is valuable to you. · It seems like you would rather close quickly. · It seems like a fair split matters to you. |
| Abuela | "You drive a hard bargain" (her own words) | It seems like you have met many hard bargainers. · It seems like you value customers who are kind. · It seems like a full page matters to you. |
| El Chato | "You are trying to be clever" (long memory, strict) | It seems like you value straight dealing. · It seems like you do not like games. · It seems like small steps do not impress you. |

Prices from dealers follow their own rules. With them, labels are for information and relationship, not for price.

## IV. CALIBRATED QUESTIONS ⚠️ all untested

| Who | Questions |
|---|---|
| Other teams | What would make this deal work for you? · How does this card fit into your page? · What are you up against on time? |
| Duels II–III–Final (price and day) | How important is the delivery day for you? · What would a shorter or longer delivery change for you? (finds who cares more about time) |
| Abuela (forgiving: memory 0.15, strictness 0.1) | What do you look for in a customer? · How do you decide who gets your best price? |
| El Chato (strict 0.85, memory 0.9) | **Do not ask yet.** Rules: some dealers treat the same words without a new price as spam. Every message to him carries a new price. |

## V. NONCASH OFFERS

| Who | What they could give besides cash |
|---|---|
| Abuela ✅ | Gifts: she gave us a card ("a little present from me", thread 108) and gifted cards to Teams 7 and 17. She also gives tips: "a full page is worth much more", "swap your duplicates". |
| El Chato | ❓ Unknown. He buys uncommon and rare cards. Three good deals with him unlock the next dealer early ✅. |
| Other teams | Card-for-card swaps instead of cash ✅ (hints). Their page gaps, which tell us what our spares are worth to them. Offers with a long life. Fee saving if they accept our offer, since the accepting side pays ⚠️. |
| Duel rival | The delivery day (0–10): trade the day we care less about for price ✅. |

Playbook with the loops, experiments and decision rules: `PLAYBOOK.md`.
