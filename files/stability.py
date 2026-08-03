"""
Seed stability: which headline numbers survive re-randomisation.

Every result published so far comes from a single random seed. Twice in this project
a number that looked good turned out to be an artifact, so the honest step before
building anything on top of these figures is to find out which are stable and which
have wide error bars.

Each headline claim is re-run across N independent seeds. Both the transaction stream
and the stochastic review outcomes are re-randomised, so this measures sampling
variability in the whole pipeline, not just in one component.

What to expect, stated in advance so it is not rationalised afterwards:
  - Friction and analyst-hours should be STABLE. They are averages over thousands of
    legitimate payments.
  - Anything counted in fraud events should be UNSTABLE. A 180-day stream contains
    single-digit fraud attempts, so catch rates and exposure are near-anecdotal and
    should be reported as ranges or not at all.
"""

import numpy as np
import pandas as pd


def summarise(values, label, unit="", pct=False):
    v = np.array([x for x in values if x is not None and np.isfinite(x)])
    if len(v) == 0:
        return {"metric": label, "n": 0}
    return {
        "metric": label,
        "n": len(v),
        "mean": float(v.mean()),
        "median": float(np.median(v)),
        "sd": float(v.std(ddof=1)) if len(v) > 1 else 0.0,
        "p05": float(np.percentile(v, 5)),
        "p95": float(np.percentile(v, 95)),
        "min": float(v.min()),
        "max": float(v.max()),
        "cv": float(v.std(ddof=1) / v.mean()) if len(v) > 1 and v.mean() != 0 else 0.0,
    }


def stability_verdict(row) -> str:
    """
    Coefficient of variation as a blunt but honest stability signal.
    A metric whose spread across seeds is comparable to its own magnitude
    should not be published as a point estimate.
    """
    cv = row.get("cv", 0.0)
    if row.get("n", 0) < 3:
        return "insufficient runs"
    if cv < 0.05:
        return "stable: publish as point estimate"
    if cv < 0.15:
        return "moderate: publish with range"
    if cv < 0.40:
        return "unstable: publish range only"
    return "anecdotal: do not publish as a number"


def report(rows) -> pd.DataFrame:
    df = pd.DataFrame(rows)
    df["verdict"] = df.apply(stability_verdict, axis=1)
    return df
