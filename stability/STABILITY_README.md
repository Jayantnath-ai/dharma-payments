# Seed stability

Every result previously published in this repository came from a single random seed.
Twice in this project a number that looked good turned out to be an artifact, so each
headline claim was re-run across independent seeds before being built on.

Both the transaction stream and the stochastic review outcomes are re-randomised, so
this measures sampling variability in the whole pipeline. Verdicts use coefficient of
variation: below 0.05 publish as a point estimate, below 0.15 publish with a range,
above 0.40 do not publish as a number at all.

## Confirmed stable (20 seeds)

| claim | mean | sd | verdict |
|---|---|---|---|
| Friction, static config | 65.7% | 1.1 | point estimate |
| Friction, shadow calibrated | 43.7% | 1.4 | point estimate |
| Dollar friction, calibrated | 62.0% | 1.9 | point estimate |
| Analyst hrs/week, static | 29.3 | 0.9 | point estimate |
| Analyst hrs/week, calibrated | 18.9 | 0.8 | point estimate |

## Pause Engine (15 seeds)

| claim | mean | sd | verdict |
|---|---|---|---|
| Analyst hrs/week, no mechanisms | 18.9 | 0.5 | point estimate |
| Analyst hrs/week, full engine | 5.1 | 0.1 | point estimate |
| **Reduction** | **73.0%** | **0.5** | **point estimate** |
| Unreviewed value released, arrival order | $29,845 | $9,808 | range only |
| Unreviewed value released, corrected triage | **$0** | 0 | point estimate |

The triage correction returns exactly zero on every seed tested, not on average.

## Adversarial (15 seeds, 3,000 transactions and ~150 fraud events per run)

Catch rate by attack and trust binding:

| attack | static | label-bound (rejected) | identity-bound (shipped) |
|---|---|---|---|
| BEC, real vendor changed account | 61.5% | **2.1%** | **61.7%** |
| Known account, abnormal amount | 86.5% | 49.9% | **86.2%** |
| Full takeover, everything matches | 62.3% | 2.6% | **33.1%** |

The first two attacks are fully closed: identity binding recovers static-equivalent
protection within noise. The label-bound collapse is confirmed and severe.

## Claims withdrawn

**Exposure in dollars.** Coefficient of variation 0.60 across seeds, mean $19,190 with
a 5th-to-95th percentile range of $6,333 to $46,191. A 180-day realistic stream
contains a mean of 4.5 fraud events, so dollar exposure is driven almost entirely by
which few invoices happened to be fraudulent. Previously published exposure figures
should be read as illustrative, not as measurements, and have been removed from
headline claims.

**Catch counts in normal operation.** Statements of the form "caught 5 of 6" rest on
single-digit event counts. Catch rate across seeds is 82% for static and 81% for
calibrated, with a 5th percentile of 60%. The correct claim is that shadow calibration
leaves protection unchanged within noise, not that any specific number of frauds was
caught.

## Claim revised downward

The single-seed run suggested identity-bound trust caught 6.3 of 13 under full account
takeover against a static baseline of 8.1 of 13. Across 15 seeds with far more events,
the gap is larger: **33.1% against 62.3%**. Earned trust roughly halves protection
against an adversary who fully controls a legitimate payee's identity and account.

This is a real cost of the trust mechanism, not a tuning artifact, and it is larger
than previously reported. It remains the case that no transaction-level signal
distinguishes this attack, which is why the recommendation is out-of-band verification
rather than better inference. But the price of earned trust against this adversary is
now measured rather than estimated.

## Files
`stability.py` · `stability_report.csv` · `stability_adversarial.csv` ·
`stability_pause.csv` · `seeds_static.csv` · `seeds_learned.csv`
