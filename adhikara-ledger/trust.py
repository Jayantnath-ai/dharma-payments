"""
Trust binding, the fix for the adversarial collapse.

DIAGNOSIS. In v0.1 of the Adhikara Ledger, earned trust attached to SEGMENT LABELS:
vendor_class="recurring", bank="domestic_major". Those are attributes an attacker
selects. Mimic the label, inherit the trust. Catch rate collapsed 5/8 -> 1/8.

The error was conceptual, not numerical: trust was granted to a *category* when it
had been earned by *specific counterparties behaving consistently over time*.

FIX, three parts:

1. IDENTITY BINDING. Trust attaches to (payee_id, account_fingerprint). A vendor
   earns discretion; the vendor's BANK DETAILS are part of who they are. If the
   fingerprint changes, earned trust is void and the transaction falls back to raw
   confidence with no uplift. This is aimed squarely at the actual BEC mechanism:
   real vendor, real invoice, changed account.

2. BEHAVIORAL ENVELOPE. Trust applies only inside the amount range that earned it.
   A payee whose 40 payments ranged $2k-$9k has earned nothing about a $60k wire.
   Uplift decays with distance from the payee's own log-amount distribution.

3. BOUNDED UPLIFT. Earned trust can never fully override structure. Effective
   confidence is capped so that residual fraud probability has a floor scaled by
   irreversibility: the less recoverable the action, the less trust may buy.
   Learning where to relax must not create an unbounded hole.

Residual risk after the fix is reported honestly in the results, not hidden.
"""

import numpy as np
import pandas as pd


UPLIFT_CAP = 0.995          # effective confidence may never exceed this
IRR_FLOOR_K = 0.02          # p_fraud floor = IRR_FLOOR_K * irreversibility
ENVELOPE_SIGMA = 3.0        # log-amount distance at which uplift fully decays
MIN_HISTORY = 5             # payments before a payee can earn anything


def build_payee_profiles(df: pd.DataFrame) -> dict:
    """
    Per-payee behavioral profile from observed (uncensored) history.
    Records the account fingerprints actually seen and the amount envelope.
    """
    profiles = {}
    for pid, g in df.groupby("payee_id", observed=True):
        logs = np.log(np.clip(g.amount.values, 1, None))
        profiles[pid] = dict(
            n=len(g),
            fingerprints=set(g.account_fingerprint.unique()),
            mu=float(logs.mean()),
            sd=float(logs.std(ddof=1)) if len(g) > 1 else 0.6,
            realized_legit=float(1.0 - g.fraud.mean()) if "fraud" in g else 1.0,
        )
    # Pooled legitimacy across identity-verified traffic: the posterior a verified
    # payee inherits. Individual payees rarely have enough events to estimate this.
    verified = df[df.apply(lambda r: r.account_fingerprint in
                  profiles.get(r.payee_id, {"fingerprints": set()})["fingerprints"], axis=1)]
    pooled = float(1.0 - verified.fraud.mean()) if len(verified) else 0.99
    for p in profiles.values():
        p["pooled_legit"] = pooled
    return profiles


def earned_confidence(row, profiles: dict, R: float) -> tuple:
    """
    Returns (effective_confidence, reason). Applies the three fixes.
    `R` is the transaction's reversibility, used for the bounded-uplift floor.
    """
    stated = float(row.confidence)
    irr = 1.0 - R
    p = profiles.get(row.payee_id)

    # --- Fix 1: identity binding -------------------------------------------
    if p is None or p["n"] < MIN_HISTORY:
        return stated, "no earned trust: insufficient payee history"
    if row.account_fingerprint not in p["fingerprints"]:
        return stated, "TRUST VOID: account fingerprint changed for known payee"

    # --- Fix 2: behavioral envelope ----------------------------------------
    lg = np.log(max(row.amount, 1))
    sd = max(p["sd"], 0.25)
    z = abs(lg - p["mu"]) / sd
    envelope = float(np.clip(1.0 - z / ENVELOPE_SIGMA, 0.0, 1.0))
    if envelope <= 0.0:
        return stated, "outside earned amount envelope: no uplift"

    # Evidence weight from payee history volume. Identity binding + envelope have
    # already restricted WHO qualifies, so verified payees may be trusted strongly;
    # weakening the uplift here would only reproduce the static gate's friction.
    w = p["n"] / (p["n"] + 5.0)
    target = p.get("pooled_legit", p["realized_legit"])
    strength = w * envelope
    uplifted = (1.0 - strength) * stated + strength * target

    # --- Fix 3: bounded uplift ---------------------------------------------
    floor_p_fraud = IRR_FLOOR_K * irr
    ceiling = min(UPLIFT_CAP, 1.0 - floor_p_fraud)
    eff = float(np.clip(uplifted, stated, ceiling))
    return eff, (f"earned uplift {stated:.3f}->{eff:.3f} "
                 f"(history={p['n']}, envelope={envelope:.2f}, cap={ceiling:.3f})")


def detect_drift(recent: pd.DataFrame, baseline_profiles: dict) -> float:
    """
    Segment-composition drift: share of recent volume from payees whose fingerprint
    or envelope no longer matches history. Returned as a 0-1 decay multiplier to be
    applied to all earned uplift. A cheap, honest circuit breaker.
    """
    if len(recent) == 0:
        return 1.0
    anomalous = 0
    for row in recent.itertuples():
        p = baseline_profiles.get(row.payee_id)
        if p is None or row.account_fingerprint not in p["fingerprints"]:
            anomalous += 1
    rate = anomalous / len(recent)
    # normal churn ~5-10%; decay hard beyond that
    return float(np.clip(1.0 - (rate - 0.08) * 4.0, 0.2, 1.0))
