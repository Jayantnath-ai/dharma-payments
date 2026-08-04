# Adhikara Ledger, shadow calibration for the Viveka Gate

**Trust in an agent's judgment should be earned per segment from observed outcomes,
not set as a constant.**

## The problem this solves
Viveka Gate v0.1 had a magic number: `calibration = 0.85`, the degree to which the
agent's stated confidence is believed. It came from nowhere. Worse, once a gate is
live it censors its own training data, transactions it blocks never resolve, so
you never learn whether a block was correct, exactly in the region the gate refuses.

## Shadow mode
The gate runs as an observer for 30–180 days: it records what it *would* have done
while the existing human process executes everything. This is the only period with
**uncensored labels** across the whole decision space, and it is the standard way
fraud models are deployed in banks. After go-live a 10% exploration channel releases
low-value escalations anyway so labels never fully censor.

## Fraud is too rare to calibrate on
180 days of a ~1,000-invoice/month AP shop yielded **8 fraud attempts**. Any method
that needs fraud labels will not calibrate. Trust is therefore learned from the three
abundant signals: confidence reliability across thousands of ordinary payments, human
override direction (hundreds of labels), and realized recovery outcomes (few, used
only as a gross sanity check on R).

## Results (180 days, 6,163 invoices, 8 fraud attempts)
| policy | friction (legit payments held) | fraud caught |
|---|---|---|
| Incumbent human process | 1.7% | 1 of 6 |
| Gate, static config | 60.5% | 5 of 6 |
| Gate, shadow-calibrated | **21.2%** | **5 of 6** |

Shadow calibration is not a refinement, it is what makes the gate deployable at all.
Same protection, friction cut by two thirds. Over six months of continued
recalibration friction falls 60.7% → 14.7% while protection holds (7 of 8 caught).

## Negative result: earned trust is an attack surface
When fraud relocates *into* the trusted segment (ordinary amounts, recurring vendor,
domestic major bank), the calibrated gate's catch rate collapses from 5/8 to **1/8**.
Learning where to relax teaches an adversary where to attack. A drift-decay rule that
shrinks earned trust toward the prior on composition shift recovers 4/8 at the cost of
most of the friction gain. **This is unsolved and stated as unsolved.** Any adaptive-
trust system that does not show this test has not run it.

## Bug found during the build (kept in the record)
v1 scored trust as `|realized − stated|`, symmetrically. In a low-base-rate world the
agent is systematically *under*confident, 0.63 stated on invoices that are legitimate
99.5% of the time. Symmetric scoring read harmless pessimism as unreliability and
lowered trust, which would have made the gate more paranoid the longer it ran.
Underconfidence is costly; overconfidence is dangerous; they must not be scored alike.

## Files
`shadow.py` (stream + incumbent process) · `ledger.py` (offline calibration) ·
`golive.py` (evaluation, learning curve, adversarial test) · `regret_demo.html` ·
`learning_curve.png` · `report_data.json`

## Lineage
Second executable component of DharmaAGI. *Adhikāra* as scope granted in proportion to
demonstrated judgment, per segment, rather than a fixed global limit; regret accounting
as the mechanism by which scope is revised.

---

# Trust binding: the design that shipped, and the one that did not

**Rejected first design.** The initial approach attached earned trust to SEGMENT LABELS (`vendor_class`,
`bank`). Those are attributes an attacker selects. Mimic the label, inherit the
trust. The error was conceptual: trust was granted to a *category* when it had been
earned by *specific counterparties behaving consistently over time*.

**Fix (see `trust.py`), three parts:**
1. **Identity binding**, trust attaches to `(payee_id, account_fingerprint)`. A
   vendor's bank details are part of who they are; if the fingerprint changes,
   earned trust is void. Aimed squarely at the actual BEC mechanism.
2. **Behavioral envelope**, trust applies only inside the amount range that earned
   it. A payee whose 40 payments ran $2k–$9k has earned nothing about a $60k wire.
3. **Bounded uplift**, earned trust can never fully override structure; effective
   confidence is capped so residual fraud probability has a floor scaled by
   irreversibility.

**Results (deterministic scoring, 180-day stream):**

Catch rate, mean across 15 seeds with ~150 fraud events per run:

| attack | label-bound (rejected) | identity-bound (shipped) | static baseline |
|---|---|---|---|
| BEC: real vendor, changed account | **2.1%** | **61.7%** | 61.5% |
| Known account, abnormal amount | 49.9% | **86.2%** | 86.5% |
| Full takeover: everything matches | 2.6% | 33.1% | 62.3% |

Attacks 1 and 2 are **fully closed**: identity binding recovers static-equivalent
protection within noise.
Attack 3 is **partially** closed and remains the honest limit: if an attacker
presents the real payee, the real account, and an ordinary amount, nothing in the
transaction distinguishes it. That case requires out-of-band verification, not
better inference.

**What the fix cost.** The rejected design's 17.3% friction was not real, it was borrowed against
a vulnerability. The honest price of attack-resistant earned trust is **44.1%
friction**, versus 64.4% static. Roughly a third of the friction can be removed
safely, not four fifths. Normal-operation protection is identical across all three.


---

## Closing the loop: gate configuration from shadow data

The Viveka Gate's `base_rate_legit` is the single parameter most likely to be set
wrong, and setting it wrong makes the gate hold ~60% of legitimate payments. The
shadow period already measures it, so the ledger hands it over directly:

```python
from ledger import derive_gate_config, shadow_summary
cfg = derive_gate_config(shadow_df)      # gate configured from observed traffic
report = shadow_summary(shadow_df)       # numbers for the customer report
```

Two guards, both of which matter in practice. The estimate is Laplace corrected with
one pseudo-event, so a shadow window containing zero fraud produces a rate reflecting
what the sample can support rather than a claim that fraud is impossible. And windows
under 500 observations keep the shipped default rather than overriding it on thin
evidence, with the reason printed rather than silently applied.


---

## Friction, decomposed

A single event-count percentage conflates three different costs. `friction.py`
reports them separately.

| | human friction | dollar friction | analyst hrs/week |
|---|---|---|---|
| Incumbent process | 0.9% | 2.1% | 0.4 |
| Gate, static | 61.1% | 78.3% | 29.5 |
| Gate, calibrated | 40.5% | 62.0% | 19.5 |

The decomposition does not favour the gate. Dollar-weighted friction exceeds
event-weighted friction (62% vs 44%) because held payments skew large. Reporting only
the event count understated the operational cost.

The binding constraint is not the percentage. It is 19.5 analyst hours per week
against 0.4 for the incumbent process, roughly half a full-time reviewer. Reducing
that is the next problem, and it is an escalation-handling problem rather than a
gating one.


---

## Seed stability

See [../stability](../stability). Friction and analyst-time figures are stable across
20 seeds (sd under 2 points). Dollar exposure figures were **withdrawn** as anecdotal,
since a realistic 180-day stream contains a mean of 4.5 fraud events. The full-takeover
residual was **revised downward** on fuller testing: identity-bound trust catches 33.1%
against a static baseline of 62.3%, a larger cost than the single-seed run suggested.
