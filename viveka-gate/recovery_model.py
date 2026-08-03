"""
Backward Monte Carlo recovery model.

Estimates reversibility R of a wire transfer by simulating RECOVERY paths,
not future outcomes. Monte Carlo points backward: we sample over the known,
closed system of recall mechanics (detection delay, recall windows, receiving
bank behavior, mule drain rates) rather than forecasting an open world.

Parameters are calibrated to the shape of published recall statistics:
- Recall success drops steeply with hours elapsed (funds drained by mules fast
  in fraud cases; FBI IC3 reports ~70%+ freeze success if flagged <24h via
  Financial Fraud Kill Chain, near-zero after 72h for international wires).
- Domestic recalls succeed far more often than international.
- Larger amounts are drained faster when fraudulent (professional operations).
"""

import numpy as np

RNG = np.random.default_rng(42)


def simulate_recovery(amount: float,
                      receiving_bank: str,      # 'domestic_major', 'domestic_small', 'international'
                      detection_lag_hours_dist=(4.0, 24.0),  # lognormal-ish range for when error is noticed
                      n_samples: int = 5000) -> dict:
    """
    Sample recovery attempts for a wire IF it turns out to be wrong.
    Returns calibrated reversibility R = P(funds recovered) with error bars.
    """
    # 1. When do we detect the error? (uniform-ish over plausible ops lag)
    lo, hi = detection_lag_hours_dist
    detect_hours = RNG.uniform(lo, hi, n_samples)

    # 2. Base recall success as function of elapsed time (logistic decay).
    #    Midpoint ~30h domestic, ~14h international; steepness reflects
    #    how fast recall windows close.
    # Calibration anchors (FBI IC3 annual reports, FFKC/RAT):
    #   Domestic freeze success conditional on fast report: 74% (2021), 73% (2022),
    #   71% (2023), 66% (2024), 58% (2025). We target the recent 58-66% band for
    #   domestic wires detected within 4-24h. International recovery runs through
    #   FinCEN RRP: $50k minimum, 72h window — below $50k intl is near-zero by rule.
    if receiving_bank == 'domestic_major':
        midpoint, steep, ceiling = 40.0, 0.08, 0.80
    elif receiving_bank == 'domestic_small':
        midpoint, steep, ceiling = 32.0, 0.10, 0.72
    else:  # international
        if amount >= 50_000:
            midpoint, steep, ceiling = 24.0, 0.10, 0.45   # FFKC-eligible
        else:
            midpoint, steep, ceiling = 10.0, 0.25, 0.12   # below RRP threshold

    p_window_open = ceiling / (1.0 + np.exp(steep * (detect_hours - midpoint)))

    # 3. Mule drain risk: if fraudulent, funds move out fast; larger amounts
    #    are drained faster (professional ops). We model drain half-life in hours.
    drain_half_life = np.clip(48.0 - 3.0 * np.log10(max(amount, 10)), 4.0, 48.0)
    p_funds_still_there = 0.5 ** (detect_hours / drain_half_life)

    # 4. Recovery succeeds if window open AND funds present AND receiving bank
    #    cooperates (bernoulli per sample).
    coop = {'domestic_major': 0.95, 'domestic_small': 0.85, 'international': 0.60}[receiving_bank]
    success = (RNG.random(n_samples) < p_window_open) \
            & (RNG.random(n_samples) < p_funds_still_there) \
            & (RNG.random(n_samples) < coop)

    R = success.mean()
    se = success.std(ddof=1) / np.sqrt(n_samples)
    return {"R": float(R), "se": float(se),
            "ci95": (float(R - 1.96 * se), float(R + 1.96 * se))}


if __name__ == "__main__":
    for bank in ["domestic_major", "domestic_small", "international"]:
        for amt in [500, 5_000, 50_000, 500_000]:
            r = simulate_recovery(amt, bank)
            print(f"{bank:16s} ${amt:>8,}  R={r['R']:.3f}  ±{1.96*r['se']:.3f}")
