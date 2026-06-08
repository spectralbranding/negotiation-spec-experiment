---
title: "Value Headroom Moderates Whether Specification Beats Style in LLM Negotiation"
author: "Dmitry Zharnikov"
orcid: "0009-0000-6893-9231"
version: "Working Paper v1.0.0 – June 2026"
doi_concept: "10.5281/zenodo.20595996"
doi_version: "10.5281/zenodo.20595997"
keywords: [LLM negotiation, value creation, logrolling, prompt specification, integrative bargaining, agentic AI]
spine: SPINE.yaml
formatting: PAPER_QUALITY_STANDARDS (no leading zero on decimals < 1; exact p, 3 digits; p < .001 floor; effect sizes mandatory)
---

**Value Headroom Moderates Whether Specification Beats Style in LLM Negotiation**

Dmitry Zharnikov · ORCID 0009-0000-6893-9231

*Working Paper v1.0.0 – June 2026*

## Abstract

When two language-model agents negotiate, does it matter more how they are *styled*
(warm, dominant) or how their objective is *specified* (ranked priorities, a reservation
value, a concession rule)? A large autonomous-negotiation study reported that interpersonal
warmth, not structure, predicted success. This note offers an independent test — a
reconstruction from that study's public materials, not a one-to-one reproduction — and
identifies *value headroom* (the joint surplus a naively cooperative pair leaves on the table)
as a first-order moderator. Across seven arms spanning three model families (4,920 dyads),
specification-first prompting ties interpersonal style on near-ceiling scenarios (a
preregistered null) but yields strictly higher joint value once headroom is present (Cohen
*d* = .314, *p* = .009 on a mid-capability model; *d* = .569, *p* < .001 at the frontier — the
advantage grows with capability), with a graded design confirming the headroom slope. An
ablation shows the advantage comes from teaching logrolling, not leaking the payoff matrix; it survives
prompt paraphrase and replicates across model families. Specification moves the objective
value frontier while remaining affectively neutral; style games the agreement proxy. The
apparent "style beats structure" result is recovered as the zero-headroom boundary case of
a more general law.

## Specification, Style, and a Result That Depends on the Exam

Two language models can be pointed at the same negotiation in two very different idioms.
The first is the idiom most human prompt-writers reach for: a *persona* and a *style* —
be warm and build rapport, or anchor hard and project dominance. The second is rarely
written by hand: a *specification* — declare the objective, state a reservation value,
rank the issues by weight, give an explicit concession rule and a stop rule, and execute
it without adopting any persona at all. A recent large-scale study of autonomous LLM
negotiation agents found that the styled idiom carried the day: warmth predicted better
outcomes, while dominance claimed value at the cost of impasses. Structure, as a property
distinct from style, was never isolated, because the study's strongest structured entrant
bundled its preparation with concealed chain-of-thought (Vaccaro et al. 2025).

This note argues that whether specification beats style is not a fixed fact about
negotiation but a function of how much value is available to create. The intuition is an
exam: on an easy exam where every diligent student scores 95, careful preparation and a
warm disposition look equally good, because the ceiling is low and everyone is already
near it. On a hard exam with genuine room between a passing answer and the best answer,
the prepared student pulls away. *Value headroom* is the hard-exam dimension of a
negotiation: when a naively cooperative pair would already capture nearly all of the
attainable joint value, there is nothing for structure to add; when they would leave a
large fraction on the table, structure is exactly what recovers it.

We make this precise and test it. Two preregistered studies hold the prompt-type contrast
fixed and vary only the scenarios' headroom; three further arms — a mechanism ablation, a
frontier-capability replication, and a wording-robustness envelope — pressure-test the
result. The central claim is positive, not deflationary: **value headroom is a first-order
moderator of prompt-type efficacy. Interpersonal style dominates structural specification
only as headroom approaches zero; above a modest threshold, specification-first prompting
produces strictly higher expected value while remaining affectively neutral.** The earlier
"warmth, not structure" finding is not contradicted; it is located, as the zero-headroom
end of the curve.

*A note on what this is and is not.* This is an independent, conceptual test. The
scenarios and the six condition prompts are our own construction, informed by the base
study's public preprint and its open data and code; they are not a one-to-one reproduction
of that study's materials, and we make no causal claim about its observational design. Any
alignment we report with the base study is directional and conceptual, within our own
scenarios — not a clean replication of its experiment.

## What Is Already Known

Work on LLM negotiation has grown quickly. Benchmark platforms show that model agents can
negotiate at all and that *behavioral* tactics move outcomes: in NegotiationArena, an
agent that "pretends to be desolate and desperate" improves its payoff by roughly 20% against
a strong opponent (Bianchi et al. 2024), a clean demonstration that stylistic framing
operates on the *agreement* surface. Economic evaluations map LLM bargaining behavior onto
rational-agent predictions and ask how efficiently models capture surplus (Deng, Mirrokni,
Paes Leme, Zhang & Zuo 2024). Capability-and-protocol surveys find that even strong models
remain inconsistent on legitimacy and commitment as stakes rise (Bhattacharya et al. 2025).
The large autonomous-competition study that motivates this note reported style — warmth —
as the dominant correlate of success (Vaccaro et al. 2025).

A second, older line is directly relevant to the mechanism we isolate. He, Chen,
Balakrishnan & Liang (2018) argued that negotiation systems should *decouple strategy from
generation* — separate the high-level move (what to propose) from the surface realization
(how to say it). Our specification prompt is, in effect, an attempt to push the model onto
the strategy axis and off the generation axis; our styled prompts do the opposite. The
distinction between *creating* value and *claiming* value is the negotiation-theory anchor
for our outcome split (Walton & McKersie 1965; Lax & Sebenius 1986; Raiffa 1982), and the
specific integrative move our specification teaches — *logrolling*, trading a low-priority
concession for a high-priority gain — is the canonical engine of joint-value creation
(Pruitt 1981). Finally, the subjective-value literature reminds us that the felt quality
of a negotiation (rapport, relationship) is a real but distinct outcome from the points on
the table (Curhan, Elfenbein & Xu 2006); our manipulation checks measure style on its own
axis precisely so that we can show specification moves value *without* moving warmth.

What is missing from this prior work is an isolation of *structure itself* — held apart
from style, from chain-of-thought, and from payoff-matrix exposure — and a test of when it
helps. That is the gap this note fills.

## Method

*Design and unit of analysis.* All hypotheses are tested at the **dyad** level: one
negotiation between two conditioned agents is one observation. Agent-level style scores
(below) are used only as manipulation checks, never as outcome units. Each arm is a
round-robin over six prompt conditions crossed with scenarios, both role orders, and five
replicates, yielding 630 dyads per full-grid arm. Conditions are: NEUTRAL (a bare
instruction, the floor), WARMTH and DOMINANCE (the two styled idioms), COT_ONLY
(chain-of-thought reasoning without a specification), and two specification conditions —
SPEC_NOCOT (specification executed directly) and SPEC_COT (specification plus reasoning).
The six condition bodies are frozen and hashed before any paid run.

*Scenarios and headroom.* Each scenario gives every agent a private numeric payoff card,
a reservation value, and a published joint matrix. We operationalize headroom as
(Pareto-joint − naive-joint) / Pareto-joint, the fraction of attainable joint value a
split-the-difference pair would forgo. Study 1 uses three near-ceiling scenarios (~3%
headroom); Study 2 uses three deliberately harder scenarios (31–46% headroom) in which a
compatible issue (both sides want the same direction) and a logrolling issue (asymmetric
priorities) hide most of the joint value behind moves a naive pair misses.

*Outcomes.* The harness parses each transcript into a deal/no-deal flag and the agreed
bundle, then computes **value created** (the joint points of the agreed bundle, defined on
integrative scenarios only), **value claimed** (own surplus above reservation), and the
split. A pre-specified unconditional **expected value** measure — deal rate × value if a
deal, with no-deal scored zero — corrects the conditional-on-deal selection in value
created and is reported as a robustness measure.

*Manipulation checks.* Two independent scorer models (one OpenAI, one Anthropic; temperature
zero; a behaviorally anchored rubric) rate each agent turn for warmth and dominance.
Inter-scorer reliability is reported as ICC(2,1) per arm and exceeds .80 for both
dimensions in every arm. Style scores confirm that the WARMTH prompt is warm, the
DOMINANCE prompt dominant, and the specification prompts neither.

*Analysis.* Contrasts are pre-specified Welch *t*-tests on the dyad-level outcomes, with
Cohen's *d* reported alongside every test. The preregistered primary mixed model was
singular on this design (random-effects variance collapsed); per the preregistered
fallback, we report ordinary least squares with cluster-robust standard errors. Exact
*p*-values are given to three digits; effects below the smallest reportable threshold are
reported as *p* < .001.

## Results

*The null at the ceiling.* On the near-ceiling scenarios (Study 1), specification ties
every cooperative control on value created: SPEC_NOCOT − NEUTRAL = +5.07 (*d* = .049,
*p* = .683), − COT_ONLY (*d* = −.030, *p* = .801), − WARMTH (*d* = .019, *p* = .871).
Warmth itself does not lift value (WARMTH − NEUTRAL *d* = .023, *p* = .846). This is the
preregistered null, and it is informative rather than empty: with the cooperative baseline
already at roughly 641 of 658 attainable joint points, there is no headroom for any prompt
to exploit. Dominance is the exception that proves the mechanism — it craters both value
and deal rate (DOMINANCE − NEUTRAL value *d* = −.410, *p* < .001).

*Specification wins once there is headroom.* On the harder scenarios (Study 2),
specification pulls clear of every cooperative control on value created (Table 1).
SPEC_NOCOT − NEUTRAL = +54.24 (*d* = .314, *p* = .009); SPEC_NOCOT − WARMTH = +43.69
(*d* = .263, *p* = .029); SPEC_COT − WARMTH = +56.77 (*d* = .346, *p* = .004). Warmth does
not lift value even here (WARMTH − NEUTRAL *d* = .058, *p* = .629). Specification also wins
the deal: SPEC_NOCOT − NEUTRAL deal rate +.11 (*d* = .293, *p* = .003). The same prompt
contrast that produced a null at the ceiling produces a robust specification advantage once
the exam is hard.

Table 1: Value-created contrasts by regime (gpt-class mid-capability model, dyad level).

| Contrast | Study 1 (≈3% headroom) | Study 2 (31–46% headroom) |
|---|---|---|
| SPEC_NOCOT − NEUTRAL | +5.07, *d* = .049, *p* = .683 | +54.24, *d* = .314, *p* = .009 |
| SPEC_NOCOT − WARMTH | +2.29, *d* = .019, *p* = .871 | +43.69, *d* = .263, *p* = .029 |
| SPEC_COT − WARMTH | — | +56.77, *d* = .346, *p* = .004 |
| WARMTH − NEUTRAL | +2.79, *d* = .023, *p* = .846 | +10.56, *d* = .058, *p* = .629 |
| DOMINANCE − NEUTRAL | −63.00, *d* = −.410, *p* < .001 | −87.10, *d* = −.418, *p* < .001 |

*Notes*: Value created = joint points of the agreed bundle, integrative scenarios only,
*N* = 630 dyads per study. Inter-scorer ICC(2,1) for the style checks: Study 2 warmth .840,
dominance .911.

*Mechanism: taught strategy, not a leaked matrix.* The sharpest threat to the result is
that the specification prompt simply hands the agent the payoff structure — that naming
weights and "logrolling" leaks the matrix, so any agent told the structure would win
regardless of strategy. We test this with a one-sentence ablation. SPEC_NOLOGROLL is
byte-identical to SPEC_NOCOT except that the single clause instructing the agent to *seek
asymmetric cross-issue trades* is removed; it retains the full ranked-weight payoff
specification, the reservation value, and the concession ordering. Run inside the full
condition grid with a matched baseline (560 dyads), removing that one sentence collapses
the advantage: SPEC_NOCOT − SPEC_NOLOGROLL = +55.0 on value created (*d* = .353, *p* = .002)
and +50.9 on value claimed (*d* = .318, *p* = .005). SPEC_NOLOGROLL falls back to the
control level — it does not beat NEUTRAL (*d* = .106, *p* = .342) or COT_ONLY (*d* = .156,
*p* = .163). The mechanistic detail is telling: on its *own* value, SPEC_NOLOGROLL actually
underperforms NEUTRAL (*d* = −.23, *p* = .044) — keeping "concede your low-weight issues
first" *without* "seek trades back" turns the agent into a systematic conceder. The
logrolling clause is what converts concession into captured integrative value. The
advantage cannot be matrix exposure, because the matrix is still fully exposed in
SPEC_NOLOGROLL; it is the taught integrative move.

*Capability scaling: structure scaffolds, it does not wash out.* Re-running the harder
grid on a frontier model (630 dyads) sharpens rather than dissolves the effect. The
specification advantage *grows* with capability: SPEC_NOCOT − NEUTRAL = +70.9
(*d* = .569, *p* < .001), versus *d* = .314 on the mid-capability model; SPEC_NOCOT −
WARMTH *d* = .687 (*p* < .001); warmth again does not lift value (WARMTH − NEUTRAL
*d* = −.126, *p* = .294). The stronger model also separates the manipulations more cleanly
(below). This rules out the rival that strong models find the logroll unaided and
specification only helps weak ones — the opposite holds in this range.

*Cross-family replication.* On a second model family (a small Anthropic model, easy
scenarios, 630 dyads) the core null replicates — SPEC_NOCOT ties cooperative controls on
value (− COT_ONLY *d* = .010, *p* = .930; WARMTH − NEUTRAL *d* = .007, *p* = .953) — so the
pattern is not a single-model artifact. A model-dependent wrinkle appears: SPEC_COT beats
the controls strongly even on easy scenarios here (− COT_ONLY *d* = .507, *p* < .001;
− WARMTH *d* = .744, *p* < .001), indicating that the specification-by-reasoning interaction
is stronger on this family. The dominance penalty is also milder on this family (deal-rate
*d* = −.32 versus −.93), confirming that dominance hurts the *deal* everywhere but hurts
*value* in a model-specific way.

*Wording robustness.* To rule out a single-phrasing artifact, four focal conditions were
each rewritten into five semantically equivalent paraphrases and re-run against a pinned
neutral opponent (640 dyads). Manipulation purity held across every wording: WARMTH
paraphrases scored warmth ≈ 85–88; specification paraphrases scored low-warmth (≈ 9–11) and
low-dominance (≈ 7–9) across all five wordings. The specification manipulation is a
property of the *content*, not of one lucky sentence. (Because each focal condition here
plays a fixed passive opponent, the joint value in this envelope is not comparable to the
round-robin and is reported only as a purity check.)

*Dose-response: the advantage scales with headroom.* The two-point easy/hard contrast above
shows the sign of the specification effect flips with headroom; a graded design tests the
*shape*. We built five variants of a single scenario family (holding issues, roles, and prose
fixed and varying only the payoff tables) and measured each variant's realized headroom as the
fraction of attainable joint value a neutral pair leaves on the table; three conditions
(NEUTRAL, COT_ONLY, SPEC_NOCOT) ran across all five, 1,200 dyads. Realized headroom graded
monotonically across the variants (.031, .080, .087, .119, .189), and the SPEC_NOCOT − NEUTRAL
value-created advantage rose with it in lockstep (Table 2): from a null at the lowest-headroom
variant (*d* = −.120 — the Study-1 ceiling, reproduced *within a single scenario family*) to a
large effect at the highest (*d* = 1.198, *p* = .002). The pre-specified specification ×
realized-headroom interaction is positive and significant (+865 joint points per unit of
realized headroom, *p* < .001) — the sign-flip is a slope.

Table 2: Specification advantage by realized headroom (one scenario family, five graded variants).

| Variant | Realized headroom | SPEC_NOCOT − NEUTRAL (value created) | *d* | *p* |
|---|---|---|---|---|
| 1 (lowest) | .031 | −5.8 | −.120 | .539 |
| 2 | .080 | +19.6 | .329 | .089 |
| 3 | .087 | +28.1 | .354 | .364 |
| 4 | .119 | +45.7 | .429 | .109 |
| 5 (highest) | .189 | +129.7 | 1.198 | .002 |

*Notes*: Realized headroom = 1 − (mean neutral value created on deals / Pareto joint).
Value created on deals; *N* = 1,200 dyads (240 per variant). The per-variant *p*-values are
noisy where the neutral baseline closes few deals (variant 3, the lowest neutral deal rate);
the pooled specification × realized-headroom interaction is the pre-specified test (*p* < .001).

Two honest caveats sharpen rather than weaken this. First, the realized headroom range here
(.03–.19) is narrower than the design target, because a neutral pair that *does* reach a deal
on these scenarios already lands near the frontier — the difficulty surfaces instead as
impasse risk. That is the second point: specification wins the *deal* as decisively as it wins
the value. SPEC_NOCOT closes 93–100% of negotiations across every variant, while the neutral
deal rate swings erratically from .28 to .85; on the unconditional expected-value measure
(charging every prompt for failed deals) SPEC_NOCOT leads in every variant and overall (888
versus COT_ONLY 792 and NEUTRAL 701). Because SPEC closes *more* deals — including marginal
ones that would depress its conditional value — its still-higher conditional value is a
conservative estimate of the advantage. The dose-response holds on both objectives: as headroom
rises, specification creates more value per deal and closes more of the deals.

*Expected value unifies the picture.* On the unconditional expected-value measure — which
charges every prompt for the deals it fails to close — specification (especially SPEC_COT)
tops every arm, dominance is at or near the bottom everywhere (its deal-rate drag dominates),
and warmth never tops the table: it buys agreements but cedes value, netting out mid-pack.
At the frontier, expected value is 967 for SPEC_NOCOT and 942 for SPEC_COT at the top
versus 694 for DOMINANCE at the bottom. The same ordering recurs in every arm, including
where the conditional primary is null — a reminder to report both measures, labeled.

## Discussion

*Headroom is the missing moderator.* The two studies share a prompt contrast and differ
only in headroom, and the sign of the specification effect flips with it: null at ≈ 3%,
robust at 31–46%. The graded within-family design turns that sign-flip into a slope — a
significant positive specification × realized-headroom interaction, with the lowest-headroom
variant reproducing the ceiling null inside a single scenario family. This is why a study run
on near-ceiling scenarios would recover "warmth, not structure" — not because structure is
inert, but because there was nothing to create.
The contribution is to name the moderator and show the law it implies: specification-first
prompting strictly dominates interpersonal style on expected value once headroom clears a
modest threshold, and is merely *equivalent* below it. Practitioners deploying negotiating
agents should therefore ask first how much joint value their setting actually contains; the
prompt that wins depends on the answer.

*Deal and value are different objectives.* Style and specification do not compete on a
single axis. Style operates on the *deal* — the binary, affective, observer-dependent
question of whether the counterpart agrees — and our benchmark companions show how powerful
that lever is (Bianchi et al. 2024). Specification operates on *value* — the objective,
quantitative question of how much joint surplus the agreed bundle contains. Warmth is
sufficient but not necessary for cooperative outcomes: the specification agents create the
most value while scoring neither warm nor dominant. An agent optimized to be liked is not
thereby optimized to create value, and on current models the two goals require different
prompts.

*Why specification decouples and style bleeds.* On the mid-capability model the WARMTH
manipulation bleeds into dominance — warm agents score nearly as dominant as the dominance
condition itself — whereas the specification prompts hold style flat on both axes. Stylistic
instructions in weaker models appear to pull several affective dimensions at once;
specification instructions decouple the objective from any affect. This bleed disappears at
the frontier, where the stronger model renders each style cleanly. The practical reading is
that a styled prompt is a blunt instrument whose side effects you cannot fully predict on a
given model, while a specification prompt changes what you asked for and little else — a
controllability argument for specification independent of the value result, and a concrete
instance of the strategy-versus-generation decoupling argued by He et al. (2018).

*Capability does not retire the lesson.* Because the advantage grows from the
mid-capability model to the frontier, structure is best read as a scaffold strong models
exploit further, not as a crutch only weak models need. Whether a still-stronger model
eventually internalizes the logroll unaided — re-creating a ceiling one level up — is an
open empirical question this note cannot settle.

## Limitations

This is a reconstruction, not a one-to-one reproduction: the scenarios and the six
condition prompts are our own, informed by the base study's public materials. The base
study is observational and our causal claims are internal to our own randomized condition
assignment; we make no causal claim about its design, and any consistency we report is
directional. The expected-value and paraphrase-envelope measures are exploratory and
labeled as such; the paraphrase joint value is not comparable to the round-robin. The
primary mixed model was singular and we report the preregistered OLS cluster-robust
fallback. The dominance manipulation separated less cleanly than warmth on the
mid-capability model (a bleed we report rather than smooth over), though it resolves at the
frontier. Manipulation checks rely on LLM scorers; the objective value findings are
computed from agreed terms and do not depend on those scores. Human-scorer validation of a
subsample remains future work.

## Data and Code Availability

All scenarios, the six frozen condition prompts (with hashes), the negotiation harness, the
scoring and analysis scripts, and per-arm outcome tables are openly available in the public
repository, released under permissive licenses (MIT for code, CC BY 4.0 for data). Full
negotiation transcripts are archived as a dataset of record with a permanent DOI
(10.57967/hf/9090); the preregistrations, gate audits, and amendment logs are included. The
archival record carries the permanent concept DOI 10.5281/zenodo.20595996 (this version,
10.5281/zenodo.20595997).
Reported figures are reproducible from the published scripts with the documented run commands.

*Companion computation script.* Every numerical value cited in this note is reproducible from
the published analysis scripts in the public repository — `analyze.py` (per-arm contrasts and
effect sizes), `compute_icc.py` (inter-scorer reliability), and `compute_headroom.py` (the
dose-response) — with the run commands documented in the repository README; the graded-headroom
scenarios are regenerated and arithmetically verified by `gen_headroom_variants.py`. No figure
or statistic in this note is hand-entered.

## Acknowledgments and Author Contributions

AI assistants (Claude Opus 4.8, Grok 4.3, Gemini 3.1) were used for initial literature
search and editorial refinement; all theoretical claims, propositions, and interpretations
are the author's sole responsibility. CRediT: Dmitry Zharnikov — Conceptualization,
Methodology, Software, Formal analysis, Investigation, Data curation, Writing (original
draft and review & editing).

## References

Bhattacharya A, Svedas G, Lyskov A, Strasser M, Barberis Canonico L. Evaluating Negotiation
Capabilities of Large Language Models: From Ultimatum Games to Nash Bargaining. *Proceedings
of the Human Factors and Ergonomics Society* 2025. doi:10.1177/10711813251372102.

Bianchi F, Chia PJ, Yuksekgonul M, Tagliabue J, Jurafsky D, Zou J. How Well Can LLMs
Negotiate? NegotiationArena Platform and Analysis. Working Paper 2024. arXiv:2402.05863.

Curhan JR, Elfenbein HA, Xu H. What do people value when they negotiate? Mapping the domain
of subjective value in negotiation. *Journal of Personality and Social Psychology*
2006;91(3):493–512.

Deng Y, Mirrokni V, Paes Leme R, Zhang H, Zuo S. LLMs at the Bargaining Table. Working
Paper 2024 (Agentic Markets Workshop, ICML 2024).

He H, Chen D, Balakrishnan A, Liang P. Decoupling Strategy and Generation in Negotiation
Dialogues. *Proceedings of EMNLP* 2018:2333–2343. arXiv:1808.09637.

Lax DA, Sebenius JK. *The Manager as Negotiator: Bargaining for Cooperation and Competitive
Gain*. New York: Free Press; 1986.

Pruitt DG. *Negotiation Behavior*. New York: Academic Press; 1981.

Raiffa H. *The Art and Science of Negotiation*. Cambridge, MA: Harvard University Press; 1982.

Vaccaro M, Caosun S, Ju J, Aral S, Curhan J. Advancing AI Negotiations: A Large-Scale
Autonomous Negotiation Competition. Working Paper 2025. arXiv:2503.06416.

Walton RE, McKersie RB. *A Behavioral Theory of Labor Negotiations*. New York: McGraw-Hill;
1965.
