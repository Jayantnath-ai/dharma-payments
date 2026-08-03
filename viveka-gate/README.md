# Viveka Gate v0.1.1, research prototype

**Continuous, computed reversibility for financial rails: a deferral-priced action gate
for agentic payments.**

An AI agent that moves money will eventually move it wrongly. The question a gate must
answer is not "is the agent confident?" but "can this be undone, and is the pause worth
its price?" This prototype answers both quantitatively.

## Claim
A gate that (1) computes reversibility R per transaction via backward Monte Carlo over
*recovery* mechanics, never by forecasting outcomes, and (2) prices deferral and
decomposition as options competing with execution, roughly **halves catastrophic loss at
matched friction** versus the industry-standard confidence threshold, on a synthetic
stream of 500 invoices with 5% BEC-style fraud ($632k at risk). The result is robust to
degrading human reviewer catch rate from 90% to 70% (gate: $145k loss @ 62% friction vs
threshold: $182k @ 68%).

## Why confidence thresholds fail here
BEC fraud is engineered to defeat confidence, lookalike domains, urgency, changed bank
details produce adversarially high agent certainty. It cannot defeat structural
irreversibility. The gate therefore shrinks the agent's confidence toward the historical
base rate as irreversibility rises (inverse-horizon rule), and hard-stops actions above
the delegated mandate at any confidence (adhikāra as category, not cost).

## Calibration
The recovery model targets published FBI IC3 Recovery Asset Team / Financial Fraud Kill
Chain statistics: domestic freeze success conditional on fast report of 74% (2021), 73%
(2022), 71% (2023), 66% (2024), 58% (2025); international recovery via FinCEN's Rapid
Response Program with its $50k minimum and 72-hour window, the model reproduces the
resulting discontinuity (R ≈ 0.02 below $50k international, ≈ 0.15 above). R here is a
freeze-and-return proxy conditional on detection within 4–24h; unconditional recovery in
the wild is far lower because most fraud is reported late, which strengthens, not
weakens, the case for gating at execution time.

## Related work (this is an active frontier)
Reversibility-tiered human approval is now mainstream practice (Redis, Galileo, and
BetterClaw-style Tier 1/2/3 frameworks; Tuskira: "the real guardrail is reversibility").
Recent research formalizes adjacent pieces: irreversibility as a budgeted scalar with
pause-for-reauthorization (arXiv 2603.03515); human oversight as a finite, fatiguing
resource where escalate-everything is *less* safe (arXiv 2606.08919); recoverability as
a real-time deferral signal (arXiv 2601.22352); and control-theoretic consequence
forecasting with fallback policies (arXiv 2510.13727), the forward-forecasting camp
this framework argues against. **Differentiation of this prototype:** prior work
hand-labels tiers or assumes the irreversibility scalar is given; here R is *computed*
from domain recovery mechanics, and the decision is a three-way priced auction
(execute / reversible probe / escalate) rather than a binary gate.

## Files
- `recovery_model.py`, backward MC over recall paths → calibrated R with error bars
- `gate.py`, the comparative decision rule (inverse horizon, priced deferral, mandate stop)
- `benchmark.py`, `frontier.py`, 500-invoice benchmark, loss/friction frontier
- `demo.html`, interactive single-file demo (open in any browser)
- `frontier.png`, `*.csv`, results

## Important default (found after publication of v0.1)
`base_rate_legit` defaults to 0.95, i.e. 5% fraud, which matches the stress
benchmark but not reality. A real accounts payable operation runs around 0.15%
fraud. At the wrong base rate the gate holds roughly 60% of legitimate payments and
no finance team would keep it switched on. Set this from your own observed data, or
better, run the Adhikara Ledger shadow period first and let it be measured.

## Honest limitations
Synthetic invoice distribution; recovery calibration is anchored to aggregate FFKC
statistics, not transaction-level data; the gate cannot reach low-friction regimes , 
its economics refuse mid-size irreversible wires on ~88%-confident judgment, a feature
under this framework's values and a bug under a CFO's. The frontier chart is the
instrument for having that argument as an explicit tradeoff.

## Lineage
This is the first executable component of DharmaAGI: the Viveka Resolution Protocol as
a decision rule. *Viveka* (discernment) → knowing where warranted judgment ends and
structural humility begins; *adhikāra* (rightful scope) → the mandate hard-stop;
*karma in akarma* (inaction is also action) → deferral priced as a bidder, never a free
safe harbor; *nishkāma karma* → deciding by what is structurally verifiable now rather
than by forecasts of fruits, whose error compounds with horizon depth.

Collaboration and critique welcome. Contact: github.com/Jayantnath-ai
