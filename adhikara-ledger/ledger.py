"""
Adhikara Ledger, phase 1: offline calibration from shadow-mode outcomes.

The Viveka Gate had a magic constant: calibration = 0.85, the degree to which the
agent's stated confidence is trusted. This module earns that number instead of
assuming it, PER SEGMENT, from shadow data.

Design constraint that drives everything: fraud is too rare to calibrate on
(2 events in 90 days). So trust is learned from the abundant signals:

  1. RELIABILITY , when the agent says 90% legitimate, what share actually were?
                    Thousands of labels. This is a calibration curve, not a
                    fraud model.
  2. HUMAN OVERRIDE, where did the incumbent reviewers disagree with the agent,
                    and who was right? Hundreds of labels. Directional signal on
                    which segments the agent misreads.
  3. RECOVERY    , when funds did go wrong, what actually got recovered? Few
                    labels, but they re-anchor R against reality.

Output: a calibration parameter per (vendor_class x bank) segment, shrunk toward
the global prior by evidence volume (empirical Bayes). Segments with thin data
inherit the conservative global value. Trust is granted incrementally, in
proportion to demonstrated judgment, adhikara as earned scope rather than a
fixed limit.
"""

import numpy as np
import pandas as pd


GLOBAL_PRIOR_TRUST = 0.85     # what the gate assumed before it had evidence
SHRINK_STRENGTH = 120.0       # pseudo-observations: how much data to override the prior


def reliability_curve(df: pd.DataFrame, bins=None) -> pd.DataFrame:
    """
    Signal 1: is the agent's stated confidence meaningful?
    Compare stated confidence against realized legitimacy in confidence buckets.
    """
    if bins is None:
        bins = [0.4, 0.7, 0.8, 0.85, 0.9, 0.95, 1.001]
    d = df.copy()
    d["bucket"] = pd.cut(d.confidence, bins, right=False)
    out = d.groupby("bucket", observed=True).agg(
        n=("fraud", "size"),
        stated=("confidence", "mean"),
        realized_legit=("fraud", lambda s: 1.0 - s.mean()),
    ).reset_index()
    out["gap"] = out.realized_legit - out.stated
    return out


def override_signal(df: pd.DataFrame) -> pd.DataFrame:
    """
    Signal 2: where did humans disagree with the agent, and who was right?
    A 'productive hold' = human held it AND it was fraud.
    A 'false hold'      = human held it AND it was legitimate (friction with no benefit).
    High false-hold segments are where the gate can safely relax; productive-hold
    segments are where it must stay tight.
    """
    d = df[df.human_reviewed].copy()
    g = d.groupby(["vendor_class", "bank"], observed=True).agg(
        reviewed=("human_held", "size"),
        holds=("human_held", "sum"),
        productive=("human_held", lambda s: 0),  # placeholder, filled below
    ).reset_index()
    prod = d[d.human_held & d.fraud].groupby(["vendor_class", "bank"], observed=True) \
            .size().rename("productive_holds").reset_index()
    g = g.drop(columns=["productive"]).merge(prod, on=["vendor_class", "bank"], how="left")
    g["productive_holds"] = g.productive_holds.fillna(0).astype(int)
    g["false_holds"] = g.holds - g.productive_holds
    g["false_hold_rate"] = g.false_holds / g.reviewed.clip(lower=1)
    return g


def learn_segment_calibration(df: pd.DataFrame,
                              prior_trust: float = GLOBAL_PRIOR_TRUST,
                              strength: float = SHRINK_STRENGTH) -> pd.DataFrame:
    """
    Learn, per segment, how the agent's stated confidence should be RECALIBRATED.

    BUG FOUND IN v1 OF THIS MODULE (kept in the record because it matters):
    the first version scored trust by |realized - stated|, symmetrically. But in a
    low-base-rate world the agent is systematically UNDERconfident, it says 0.63
    on invoices that are legitimate 99.5% of the time. Symmetric scoring read that
    harmless pessimism as unreliability and LOWERED trust, which would make the
    gate more paranoid the longer it ran. Underconfidence is costly; overconfidence
    is dangerous. They must not be scored alike.

    Correct formulation: the gate does not need to "trust the number", it needs
    P(legitimate | segment, stated confidence). We learn two things per segment:

      base_legit  , realized legitimacy rate, shrunk toward the global rate
                     (Beta-Binomial; thin segments inherit the global prior)
      discrimination, does lower stated confidence actually predict higher fraud
                     risk within this segment? Measured as the gap in realized
                     legitimacy between the segment's low- and high-confidence
                     halves. Positive = the signal carries information and may be
                     leaned on; ~zero = the number is noise and the segment should
                     be governed by its base rate alone.

    Effective confidence handed to the gate:
        W_eff = w * recalibrated_estimate + (1 - w) * stated
    where recalibrated_estimate is the segment base rate adjusted by whatever
    discrimination the confidence signal has actually demonstrated, and w rises
    with evidence volume. Trust is earned by volume of demonstrated accuracy.
    """
    global_legit = 1.0 - df.fraud.mean()
    rows = []
    for (vc, bank), g in df.groupby(["vendor_class", "bank"], observed=True):
        n = len(g)
        realized = 1.0 - g.fraud.mean()

        # Beta-Binomial shrinkage of the segment legitimacy rate toward global
        base_legit = (n * realized + strength * global_legit) / (n + strength)

        # Discrimination: split segment at its median confidence, compare outcomes
        med = g.confidence.median()
        lo, hi = g[g.confidence <= med], g[g.confidence > med]
        if len(lo) > 0 and len(hi) > 0:
            disc = (1.0 - lo.fraud.mean()) - (1.0 - hi.fraud.mean())
            disc = -disc  # positive when HIGH confidence => more legitimate
        else:
            disc = 0.0

        # Evidence weight: how much to lean on learned recalibration vs raw number
        w = n / (n + strength)

        rows.append(dict(vendor_class=vc, bank=bank, n=n,
                         mean_stated=g.confidence.mean(),
                         realized_legit=realized,
                         base_legit=base_legit,
                         discrimination=disc,
                         evidence_weight=w))
    return pd.DataFrame(rows).sort_values("n", ascending=False).reset_index(drop=True)


def effective_confidence(stated: float, seg_row) -> float:
    """
    Apply learned recalibration to a single transaction's stated confidence.
    Blends the segment's earned base rate with the raw signal by evidence weight.
    Never exceeds the segment's demonstrated legitimacy rate, earned trust is a
    ceiling, not a licence.
    """
    w = float(seg_row["evidence_weight"])
    base = float(seg_row["base_legit"])
    # lean on the raw signal only to the extent it demonstrated discrimination
    disc = float(np.clip(seg_row["discrimination"], 0.0, 1.0))
    signal_adj = base + disc * (stated - 0.5)
    est = w * signal_adj + (1 - w) * stated
    return float(np.clip(est, 0.0, base))


def recovery_reanchor(df: pd.DataFrame) -> dict:
    """
    Signal 3: realized recovery outcomes. Sparse but real, used to sanity-check
    the backward-MC recovery model rather than to retrain it. With 0-3 events per
    quarter this can only flag gross miscalibration, and the module says so
    honestly rather than pretending to fit a curve.
    """
    lost = df[df.fraud & df.executed]
    return {"fraud_executed": int(len(lost)),
            "dollars_exposed": float(lost.amount.sum()),
            "note": "too few events to refit R; used only as a gross sanity check"}


def calibration_report(df: pd.DataFrame) -> dict:
    return {
        "reliability": reliability_curve(df),
        "overrides": override_signal(df),
        "segment_calibration": learn_segment_calibration(df),
        "recovery": recovery_reanchor(df),
    }


if __name__ == "__main__":
    df = pd.read_csv("shadow_stream.csv")
    rep = calibration_report(df)
    print("=== Signal 1: reliability curve (abundant: every invoice) ===")
    print(rep["reliability"].to_string(index=False))
    print("\n=== Signal 2: human override behaviour (hundreds of labels) ===")
    print(rep["overrides"].to_string(index=False))
    print("\n=== Learned segment calibration (empirical Bayes) ===")
    print(rep["segment_calibration"][["vendor_class","bank","n","realized_legit","base_legit","discrimination","evidence_weight"]].to_string(index=False))
    print("\n=== Signal 3: recovery ===")
    print(rep["recovery"])
    rep["segment_calibration"].to_csv("segment_calibration.csv", index=False)
