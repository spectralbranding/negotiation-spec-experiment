# Negotiation Scenarios

Three self-contained scenarios for the Spec-Agent vs Styled-Agent experiment.
All payoff matrices are published openly (no confidentiality reason to withhold them).

## Scenario Overview

| ID | Type | Roles | Issues | ZOPA / Pareto gap |
|---|---|---|---|---|
| `chair` | Distributive | Buyer, Seller | price (USD) | ZOPA $300-420; Nash split = $360 |
| `rental` | Integrative | Tenant, Landlord | rent, lease length, repairs | Logroll gain: +240 joint pts vs equal-split |
| `offer` | Integrative | Candidate, Recruiter | salary, remote days, start date | Logroll gain: +250 joint pts vs equal-split |

## Design Rules Applied

1. **Distributive (chair)**: Fixed ZOPA width = $120. Any deal in [$300, $420] is
   Pareto-optimal; value-creation is zero (only claiming). Nash bargaining solution
   = equal surplus split at $360 (each party gets $60).

2. **Integrative (rental, offer)**: Issue weights are asymmetric so the Pareto-optimal
   bundle is NOT the equal-split midpoint. This is what allows value-creation to
   differ across agent types. The key structural feature is OPPOSED priorities on
   the highest-value issue for each party, with a compatible concession axis (one
   party's low-weight issue is the other party's high-weight issue).

3. **BATNAs**: Set so impasse is a scored outcome (worth 200 pts for integrative roles,
   $0 surplus for distributive roles at their BATNA price). Impasse is not zero —
   agents can prefer it to a bad deal.

## Analytic Optima

### chair (distributive)
- Nash bargaining solution: price = $360
- Buyer surplus = $60, Seller surplus = $60
- Any deal in [$300, $420] is efficient; split determines distribution only

### rental (integrative)
- Pareto-optimal bundle: rent=$1700/mo, lease=24 months, repairs=$1200
- Tenant points: 240 + 20 + 240 = 500
- Landlord points: 80 + 300 + 0 = 380
- Joint total: **880 points**
- Equal-split (rent=$1800, lease=12, repairs=$600): tenant=340, landlord=300, joint=640
- Value created by logrolling vs equal-split: **+240 joint points**
- Logroll mechanism: tenant concedes lease length (costs only 40 pts: from 80 to 20),
  gaining repair allowance (gains 240 pts: from 0 to 240); landlord concedes on
  repairs (costs 80 pts: from 80 to 0), gaining long lease (gains 200 pts: from 100 to 300)

### offer (integrative)
- Pareto-optimal bundle: salary=$115,000, remote=4 days/week, start=2 weeks
- Candidate points: 250 + 160 + 20 = 430
- Recruiter points: 60 + 40 + 280 = 380
- Joint total: **810 points**
- Equal-split (salary=$110,000, remote=2 days, start=6 weeks): candidate=290, recruiter=270, joint=560
- Value created by logrolling vs equal-split: **+250 joint points**
- Logroll mechanism: candidate concedes start date (from 6 to 2 weeks, costs 40 pts),
  gaining salary (from 150 to 250, +100 pts) and remote (from 80 to 160, +80 pts);
  recruiter concedes remote (from 80 to 40, costs 40 pts) and salary (from 110 to 60,
  costs 50 pts), gaining fast start (from 80 to 280, +200 pts)

## Interpretation Notes for Analysis

- **Value created** (integrative): joint points achieved. Higher = better logrolling.
  Compared to equal-split baseline (640 for rental, 560 for offer) and Pareto maximum
  (880 for rental, 810 for offer). SPEC agent's explicit logrolling rule should push
  toward the Pareto maximum.

- **Value claimed**: own points at deal vs BATNA (200). A deal at Pareto-optimal gives
  candidate 430 and recruiter 380 — unequal distribution despite both exceeding BATNA.

- **Impasse**: both parties take BATNA (200 pts integrative; own-surplus = 0 for
  distributive since the BATNA is priced into reservation_price).

- **Why Pareto != equal-split**: in rental, the logroll creates 240 extra joint points;
  in offer, it creates 250. An agent that identifies and executes the logroll generates
  materially more joint surplus than one doing equal-issue concessions. This is the
  test for H3.
