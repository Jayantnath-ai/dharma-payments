# Evaluation methodology

The strongest claim this repository makes is not any individual number. It is that the
numbers were tested hard enough that two of them were withdrawn and one was revised
downward. This document states how that testing was done, so a reader can judge the
evidence rather than take the results on trust.

---

## 1. Baselines

No result is reported without a baseline, and the baselines are the things a real
buyer would otherwise be running.

**Incumbent human process.** A rule-based accounts payable policy: manual review above
a dollar threshold and for any new payee, with a reviewer who catches 72% of the fraud
they look at and wrongly holds 6% of legitimate payments they see. This is the
comparison that matters commercially, because it is what the gate replaces.

**Confidence threshold.** Execute if the agent's stated confidence exceeds a cut-off.
This is the industry-standard guardrail and the thing the gate claims to beat. It is
swept across thresholds from 0.5 to 0.98 rather than evaluated at one point, so the
comparison is frontier against frontier rather than point against point.

**Static configuration.** The gate with no learning, used to isolate the contribution
of the Adhikara Ledger from the contribution of the gate itself.

**Arrival order.** For the Pause Engine, the null hypothesis: work the queue in the
order things showed up. Any ordering worth having must beat it. This baseline is what
exposed the triage design error, because the first triage key lost to it.

---

## 2. Metrics

**Catastrophic loss.** Fraudulent dollars executed and not subsequently recovered,
where recovery is drawn from the calibrated recovery model rather than assumed. Now
reported as illustrative only, for reasons in section 5.

**Friction, decomposed.** A single event-count percentage conflates three different
costs, so five measures are reported: share of legitimate payments needing a human,
share auto-verified by probe, share of legitimate dollars delayed, analyst hours per
week, and working capital delayed in dollar-hours. The decomposition made the system
look worse and surfaced the number that actually governs adoption.

**Analyst capacity required.** For the Pause Engine, the metric is the review capacity
needed to clear the queue with zero unresolved backlog, not the hours consumed at a
fixed capacity. Measuring hours at fixed capacity conflates efficiency with throughput,
which produced a misleading first result during development.

**Catch rate under attack.** Share of adversarial fraud attempts intercepted, measured
separately per attack model.

---

## 3. Adversarial evaluation

Three attacker models, each targeting a different assumption in the system.

**Label mimicry.** The attacker impersonates a real recurring vendor and supplies new
bank details. This is the actual mechanism of business email compromise, and it is the
attack the trust mechanism must survive.

**Envelope break.** The attacker uses a known payee and their genuine account, but an
amount far outside that payee's historical range.

**Full takeover.** The attacker presents the real payee, the real account, and an
ordinary amount. Included specifically because it is the case the system cannot solve,
and omitting it would misrepresent the results.

Attack streams use 3,000 transactions at a 5% attack rate, giving roughly 150 fraud
events per run. This is deliberately unrealistic: the realistic base rate produces too
few events to measure anything, so the stress test trades realism for statistical
power and says so.

---

## 4. Ablation

Each mechanism is added cumulatively and measured in isolation, because a system that
only reports its final number cannot tell you which part is doing the work.

The Pause Engine ablation produced the most useful finding in the project: prefilled
context accounts for nearly the entire 73% saving, while expected-value triage,
same-payee batching, and the worthiness threshold together contribute less than a
fifth. The reverse would have been assumed.

---

## 5. Seed stability, and claims withdrawn

Every headline result was re-run across 15 to 20 independent seeds, re-randomising both
the transaction stream and the stochastic review outcomes. Stability is judged by
coefficient of variation: below 0.05 publish as a point estimate, below 0.15 publish
with a range, above 0.40 do not publish as a number at all.

**Survived.** Friction percentages (sd under 2 points), analyst hours per week, and the
73.0% Pause Engine reduction (sd 0.5). The corrected triage returns exactly $0
unreviewed released value on every seed, not on average.

**Withdrawn.** All dollar exposure figures, coefficient of variation 0.60, ranging
$6,333 to $46,191 across seeds. A realistic 180-day stream contains a mean of 4.5 fraud
events, so those figures were reporting which invoices happened to be fraudulent rather
than system performance. Also withdrawn: any claim of the form "caught 5 of 6."

**Revised downward.** The full-takeover residual. A single seed suggested identity-bound
trust caught 6.3 of 13 against a static baseline of 8.1. Across 15 seeds with far more
events the gap is larger: 33.1% against 62.3%. Earned trust roughly halves protection
against an adversary who fully controls a legitimate payee's identity.

---

## 6. What this evaluation does not establish

**Synthetic data throughout.** Invoice distributions, payee behaviour, and fraud
patterns are generated, not observed. The generators encode assumptions that could be
wrong in ways no amount of seed testing would reveal.

**Recovery calibration is aggregate.** The recovery model targets published FBI IC3 and
FinCEN statistics at the population level, not transaction-level recovery outcomes. It
reproduces the right shape and the right discontinuity at the $50,000 international
threshold, but it has not been validated against a real recall dataset.

**Human reviewer behaviour is a parameter, not a measurement.** Catch rate, false-flag
rate, and review duration are set from plausible values and varied in sensitivity
analysis, not derived from observed analyst performance.

**No live deployment.** Every result is simulation. The shadow-mode design exists
precisely so that a real deployment would produce these measurements on real traffic
before the gate is permitted to block anything.

---

## 7. Deliberate non-use of retrieval

This system does not use retrieval-augmented generation, and the omission is a design
decision rather than an oversight.

The payee profile lookup is a keyed read of a known counterparty record: identity,
account fingerprints seen, amount distribution, payment count. The correct answer is
exact and the key is known, so retrieval over embeddings would introduce approximation
and latency in place of a database read that is already correct. Semantic similarity is
the wrong tool when the join key is a payee ID.

Retrieval would be appropriate if the system needed to reason over unstructured vendor
correspondence, contract terms, or historical dispute narratives. It does not, and
adding it to satisfy an expected architecture would make the system worse.

---

## 8. LLM integration

The agent whose confidence the gate consumes is implemented in `agent.py`. It sends an
invoice, plus structured payee history, to Claude (`claude-sonnet-4-6`) and receives a
structured JSON assessment: probability the invoice is legitimate, the specific signals
that drove the judgement, whether banking details differ from history, and a one
sentence rationale.

Most benchmark results in this repository use a **simulated** confidence drawn from a
Beta distribution rather than a live model call. This is deliberate and worth being
explicit about. Running 6,000 invoices through a live API per seed, across 20 seeds,
is neither affordable nor necessary: the gate's argument is that its decision is
driven by reversibility rather than by how the confidence was produced. The simulated
distribution is calibrated to be adversarially favourable to fraud, meaning fraudulent
invoices receive high confidence, which is the hard case.

The live integration exists to make that assumption falsifiable rather than assumed,
and to let the pipeline be demonstrated end to end on a real invoice.

**What the integration demonstrates.** On the sample business email compromise invoice,
the gate escalates at every agent confidence level from 0.70 to 0.95. On the legitimate
invoice from a known payee, the gate executes at 0.95. The decision boundary moves with
reversibility and delegated scope, not with the model's certainty, which is the claim
the system exists to make.

**What it does not establish.** Two sample invoices are an illustration, not an
evaluation. A proper assessment of the agent layer would require a labelled corpus of
real invoices and would measure the agent's calibration directly. That corpus does not
exist here.
