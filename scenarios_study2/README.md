# Negotiation Scenarios — Study 2 (high-headroom set)

Three self-contained scenarios for **Study 2** of the Spec-Agent vs Styled-Agent
experiment. They reuse the **exact same payoff-matrix YAML schema** as Study 1
(`../scenarios/*.yaml`), so the existing harness (`code/negotiation_runner.py`,
`code/outcomes.py`) loads and scores them with **no code changes**. All payoff
matrices are published openly (no confidentiality reason to withhold them).

## Why Study 2 exists (the headroom problem)

Study 1 (gpt-4o-mini, 630 dyads) returned a **null on the primary hypothesis**:
SPEC_NOCOT, COT_ONLY, WARMTH, and NEUTRAL all tied on value created (~641–650 joint
points; SPEC_NOCOT − NEUTRAL d = .049, p = .683). The diagnosed cause is a **value
ceiling**: in Study 1's integrative scenarios, a bare-cooperative (NEUTRAL) agent
already captured ~641 of ~658 reachable joint points (≈97% of the frontier), leaving
almost no headroom for an explicit logrolling specification to add value. The robust
finding that *did* hold — DOMINANCE craters deal rate (.51 vs .90, d = −.93) and value
created (d = −.41) — replicated the base paper (Vaccaro et al., arXiv 2503.06416).

Study 2 keeps the **same six conditions, same outcome metrics, and same analysis plan**
but swaps in **harder scenarios engineered so a naive cooperative agent does NOT reach
the Pareto frontier on its own.** That restores a fair test of whether explicit
specification (declared objective, reservation value, ranked issue weights, an explicit
logrolling/concession rule) outperforms vibe-cooperation.

## Scenario overview

| ID | Type | Roles | Issues | Naive joint | Pareto joint | Headroom gap |
|---|---|---|---|---|---|---|
| `merger` | Integrative | Acquirer, Founder | 5 (cash, equity, integration, brand, esg) | 772 | 1120 | **+348 (31% of frontier)** |
| `supplier` | Integrative | Buyer, Supplier | 4 (price, volume, payment, warranty) | 520 | 960 | **+440 (46% of frontier)** |
| `salvage` | Distributive | Payer, Claimant | 1 (settlement) | n/a (claiming only) | ZOPA width $15 (narrow) | claiming-without-impasse is hard |

For contrast, Study 1's integrative scenarios left only ~3% of the frontier
unclaimed by naive play. Study 2's gaps are an order of magnitude larger by design.

## The headroom levers used

1. **A compatible issue** (both parties privately want the same option but will not
   find it without exploring): `merger.esg_clause` (both prefer "strong"); a
   naive agent defaults to the middle ("moderate"). `supplier.volume_commit_kunits`
   (both gain from high volume) reads like a buyer concession chip, so a naive
   haggler settles it low.
2. **A distractor issue** (visibly negotiable, near-zero joint stakes) that absorbs
   naive bargaining attention: `supplier.payment_terms_days` (net-15 … net-90, joint
   value ~40 either way).
3. **Strong, non-obvious weight asymmetry** on the true logroll issues so a
   "split-the-difference" agent halves them and loses most of the surplus:
   `merger.integration_months` (acquirer max 300 vs founder max 60) and
   `merger.brand_retention_yrs` (founder max 320 vs acquirer max 60);
   `supplier.warranty_years` (supplier max 300 vs buyer max 60).
4. **Tight / explicit reservation values** so a spec agent ("never accept below RV;
   trade low-weight for high-weight") behaves differently from a vibe-cooperative
   one: `salvage` has a ZOPA of width $15 on a [85, 100] band, vs Study 1's chair
   width of $120.
5. **A narrow-ZOPA distributive scenario** (`salvage`) where claiming surplus without
   tripping an impasse is genuinely hard — the distributive test of the
   spec-claims-without-the-dominance-penalty angle (H1×H2 interaction).

---

## merger (integrative, 5 issues)

Acquirer buys a founder-led company. Five terms: `cash_price_musd` (USD millions),
`founder_equity_pct` (% the founder retains), `integration_months` (founder stay),
`brand_retention_yrs` (years the brand name is kept), `esg_clause`
(0 = none, 1 = moderate, 2 = strong — **encoded numerically**, see note below).

### Payoff structure

| Issue | Acquirer weight (max pts) | Founder weight (max pts) | Role |
|---|---|---|---|
| cash_price_musd | 200 | 200 | opposed, zero-sum (joint = 200 const) |
| founder_equity_pct | 120 | 120 | opposed, zero-sum (joint = 120 const) |
| integration_months | **300** | 60 | logroll — acquirer high, founder low |
| brand_retention_yrs | 60 | **320** | logroll — founder high, acquirer low |
| esg_clause | 90 | 90 | **compatible** — both prefer "strong" (2) |

BATNA = 300 points each.

### Analytic reference bundles (verified against `outcomes.py`)

- **Naive / equal-split** (cash = 50, equity = 10, integration = 18, brand = 5, esg = 1):
  acquirer 388 + founder 384 = **joint 772**.
- **Pareto-optimal** (cash = 50, equity = 10, integration = 36, brand = 10, esg = 2):
  acquirer 582 + founder 538 = **joint 1120**.
- **Headroom = 1120 − 772 = 348 points (31% of the frontier).**

### Why a naive cooperative agent falls short here

cash and equity are zero-sum and visually dominate the table, so a naive agent treats
the whole negotiation as price-splitting and never interrogates the back-three issues.
On the two logroll issues it "splits the difference" (integration → 18 of {6…36};
brand → 5 of {0…10}), losing 144 + 104 = 248 joint points. On the compatible esg issue
it defaults to "moderate" (1) rather than discovering the mutual "strong" (2) preference,
losing a further 100 joint points. Total naive shortfall ≈ 348 points — versus Study 1,
where the single obvious logroll was easy enough that NEUTRAL captured ~97% of value.
A spec agent that ranks its own issues and trades its low-weight issues for its
high-weight ones should close most of this gap.

---

## supplier (integrative, 4 issues)

Procurement buyer and component supplier negotiate a one-year supply contract. Four
terms: `unit_price_usd` ($/unit), `volume_commit_kunits` (k units/yr),
`payment_terms_days` (net days), `warranty_years`.

### Payoff structure

| Issue | Buyer weight (max pts) | Supplier weight (max pts) | Role |
|---|---|---|---|
| unit_price_usd | 160 | 160 | opposed, zero-sum (joint = 160 const) |
| volume_commit_kunits | 200 | 260 | **compatible** — both want high (200) |
| payment_terms_days | 30 | 30 | **distractor** — near-flat (joint ~40) |
| warranty_years | 60 | **300** | logroll — supplier high, buyer low |

BATNA = 180 points each.

### Analytic reference bundles (verified against `outcomes.py`)

- **Naive** (price = 12, volume = 100, payment = 45, warranty = 3):
  buyer 216 + supplier 304 = **joint 520**.
- **Equal-split / mid grid** (price = 12, volume = 150, payment = 45, warranty = 3):
  buyer 276 + supplier 384 = **joint 660**.
- **Pareto-optimal** (price = 12, volume = 200, payment = 45, warranty = 1):
  buyer 316 + supplier 644 = **joint 960**.
- **Headroom = 960 − 520 = 440 points (46% of the frontier).**

### Why a naive cooperative agent falls short here

`volume_commit` is compatible — both gain from a high commitment — but it reads like a
quantity a buyer should bargain *down*, so a naive haggler settles it low (100k),
forgoing 320 joint points. `payment_terms` is an engineered distractor: it looks like a
real net-15/net-90 axis but moves only ~40 joint points, so it soaks up naive
concession effort that should go elsewhere. `warranty` is a real logroll with strong
asymmetry; a "fair" agent picks 3 years and loses 120 joint points versus the
joint-optimal 1 year. The Pareto split is intentionally lopsided toward the supplier
(316 vs 644) — both still clear BATNA (180) comfortably — which also stresses the
distributive instinct (a value-claiming agent may resist the efficient bundle because
it looks "unfair", a behavior the spec's RV-plus-logroll rule should override).

---

## salvage (distributive, narrow ZOPA)

Two firms settle a contract dispute out of court. Single issue: `settlement_kusd`
(thousands of USD the payer/defendant pays the claimant/plaintiff).

### Payoff structure

- Payer reservation_price = 100 (will not pay more than $100k; trial costs ~$100k).
- Claimant reservation_price = 85 (will not accept less than $85k; trial nets ~$85k).
- **ZOPA = [85, 100], width = $15.** Joint surplus is constant ($15k) anywhere in the
  band — claiming only, no value creation.
- Nash bargaining solution (equal surplus) = **$92.5k** (each gets $7.5k).
- BATNA = 0 surplus each (they go to trial at their reservation cost).

### Why it is harder than Study 1's chair

Study 1's `chair` had a wide ZOPA (width $120), so almost any cooperative split landed
inside it and claiming was easy. `salvage`'s width-$15 band means a vibe-cooperative
agent that anchors loosely or concedes generously easily overshoots — leaving nearly
all surplus to the counterpart, or crossing a reservation value and triggering an
impasse. This is the distributive test of H2 and the H1×H2 interaction: a spec agent
with an explicit reservation value and a disciplined concession rule should claim
surplus *without* the deal-rate penalty that aggressive (DOMINANCE) play incurs.

---

## Interpretation notes for analysis

- **Value created** (integrative, `merger` + `supplier`): joint points at the agreed
  bundle. Compared to the naive/equal-split baseline (772 merger, 520/660 supplier) and
  the Pareto maximum (1120 merger, 960 supplier). The spec agent's explicit logrolling
  rule should push toward the Pareto maximum; the headroom is large enough (31–46% of
  the frontier) that a real SPEC effect can register, unlike Study 1.
- **Value claimed** (own points vs BATNA): note the Pareto bundles are intentionally
  *unequal* (merger 582/538; supplier 316/644), so claiming and creating can diverge.
- **Impasse**: both parties take BATNA — integrative joint "value" at impasse = sum of
  BATNAs (merger 600, supplier 360); distributive surplus = 0 each.
- **Deal-rate sanity**: per the stopping rule, NEUTRAL deal rate must land in
  [.3, .95]. The narrow `salvage` ZOPA is the one to watch — if NEUTRAL impasse is too
  frequent there (deal rate < .3), the band is widened in a logged pilot amendment
  (analogous to Study 1 Amendment 8a) before the main run; hypotheses are unchanged.

## Harness-compatibility notes (read before running)

- **Schema parity.** These files replicate the Study 1 schema exactly: integrative
  scenarios use `roles[].private_payoff_card[issue].options` (value → points) +
  `batna_value` + `batna_description`; distributive uses `issue.name` + `issue.options`
  + per-role `reservation_price` + `target_price` + `batna_value` +
  `private_payoff.formula`. Top-level keys `scenario_id`, `type`, `description`,
  `offer_protocol`, `max_rounds` match. Verified: all three load via `yaml.safe_load`,
  build prompts via `negotiation_runner._build_system_prompt` for every condition×role,
  and score via `outcomes.compute_outcome` to the hand-computed joint values above with
  zero lookup notes.
- **`esg_clause` is encoded as a NUMBER (0/1/2), not a string.** Reason: the harness
  auto-generates the OFFER-protocol hint as `{<issue>: "<number>"}` for *every* issue
  (it has no per-issue type metadata). A categorical string key would make the hint
  inaccurate and risk an agent emitting a number that fails the payoff lookup (which
  degrades that dyad to BATNA with a logged note). Encoding esg as an ordinal keeps the
  auto-hint correct and every emitted offer scorable with **no code change**. The role
  cards and `offer_protocol.description` document the 0=none/1=moderate/2=strong mapping.
- **`max_rounds: 14`** matches the post-pilot Study 1 value (Amendment 8a raised K from
  8 to 14 to let integrative deals close). The runner default is also 14.
- **Dry-run / mock mode caveat (does NOT affect live runs).** `negotiation_runner`'s
  mock generator (`_mock_offer_for_scenario`) only has hardcoded option sets for the
  Study 1 ids `rental`/`offer` and a generic `{"value": …}` fallback for unknown ids.
  For these new scenario ids a *mock* dyad would emit `{"value": …}`, which fails the
  payoff lookup and falls back to BATNA (graceful, logged, no crash) — so mock dry-runs
  produce uninformative-but-non-crashing output for Study 2. **Live runs are
  unaffected** (live offers come from the model, keyed to the real issue names).
  This is the one place a future maintainer might choose to extend the mock generator;
  it is intentionally left alone here to honor the no-code-change constraint.
