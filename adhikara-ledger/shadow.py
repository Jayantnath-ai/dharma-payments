"""
Shadow mode: the gate observes, the humans decide, everything executes.

This is the only period in which outcome labels are UNCENSORED. Once the gate is
live, transactions it blocks never resolve, so the training distribution is
censored exactly in the region the gate refuses. Shadow mode buys one clean,
unbiased sample across the whole decision space.

Realism constraints deliberately imposed:
  - Fraud is RARE: ~0.15% of invoices (a mid-size AP shop sees a handful of BEC
    attempts a year, not 5% as in the synthetic stress benchmark).
  - Therefore we do NOT calibrate on fraud outcomes. We calibrate on the three
    ABUNDANT signals:
      1. agent confidence vs. realized legitimacy on ordinary payments (thousands)
      2. human reviewer overrides, and their direction (hundreds)
      3. realized recovery outcomes when something did go wrong (few, but real)
  - The incumbent human process is simulated with its own precision/recall so the
    shadow report can compare gate-vs-status-quo, not gate-vs-nothing.
"""

import numpy as np
import pandas as pd

RNG = np.random.default_rng(2026)

# --- incumbent AP process (the baseline the buyer already runs) ---
HUMAN_REVIEW_TRIGGER = {          # existing rule-based policy: what gets manually reviewed
    "amount_over": 15_000,
    "new_payee_always": True,
}
HUMAN_CATCH = 0.72                # reviewer catches this share of fraud they look at
HUMAN_FALSE_FLAG = 0.06           # share of legit reviewed payments wrongly held

DAYS = 90
INVOICES_PER_DAY = 34             # ~1,000/month AP shop
FRAUD_RATE = 0.0015               # realistic sparsity


def _agent_confidence(fraud: bool, new_payee: bool) -> float:
    """
    Agent's P(legitimate). On fraud it is adversarially HIGH (BEC is engineered to
    look right) but with a slightly heavier low tail when the payee is new.
    """
    if fraud:
        base = RNG.beta(8, 2)                       # ~0.80 mean
        if new_payee:
            base -= RNG.uniform(0.0, 0.10)
        return float(np.clip(base, 0.4, 0.995))
    base = RNG.beta(9, 1.2)                         # ~0.88 mean
    if new_payee:
        base -= RNG.uniform(0.0, 0.15)              # agent is genuinely less sure on new payees
    return float(np.clip(base, 0.4, 0.999))


# Stable payee population: recurring vendors have persistent identity + bank details.
N_RECURRING = 90
_RECURRING = [dict(pid=f"V{i:03d}",
                   fp=f"FP{i:03d}",
                   mu=RNG.uniform(7.6, 9.4),
                   sd=RNG.uniform(0.3, 0.7),
                   bank=RNG.choice(["domestic_major","domestic_small","international"],
                                   p=[0.70,0.24,0.06]))
              for i in range(N_RECURRING)]


def generate_shadow_stream(days: int = DAYS) -> pd.DataFrame:
    rows = []
    for day in range(1, days + 1):
        n = RNG.poisson(INVOICES_PER_DAY)
        for _ in range(n):
            fraud = RNG.random() < FRAUD_RATE
            if fraud:
                # Classic BEC: impersonate a REAL recurring vendor, changed bank details.
                v = _RECURRING[RNG.integers(0, N_RECURRING)]
                amount = float(np.round(RNG.lognormal(10.0, 1.0), 2))
                bank = RNG.choice(["domestic_small", "international"], p=[0.45, 0.55])
                new_payee = RNG.random() < 0.85
                vendor_class = "new"
                payee_id, fingerprint = v["pid"], f"FRAUD{RNG.integers(0,99999):05d}"
            else:
                if RNG.random() < 0.72:
                    v = _RECURRING[RNG.integers(0, N_RECURRING)]
                    amount = float(np.round(np.exp(RNG.normal(v["mu"], v["sd"])), 2))
                    bank, vendor_class, new_payee = v["bank"], "recurring", False
                    payee_id, fingerprint = v["pid"], v["fp"]
                else:
                    amount = float(np.round(RNG.lognormal(8.3, 1.15), 2))
                    bank = RNG.choice(["domestic_major", "domestic_small", "international"],
                                      p=[0.62, 0.30, 0.08])
                    new_payee = RNG.random() < 0.40
                    vendor_class = "new" if new_payee else "occasional"
                    payee_id = f"O{RNG.integers(0,900):03d}"
                    fingerprint = f"OFP{payee_id}"
            conf = _agent_confidence(fraud, new_payee)

            # --- incumbent human process ---
            reviewed = (amount > HUMAN_REVIEW_TRIGGER["amount_over"]) or \
                       (new_payee and HUMAN_REVIEW_TRIGGER["new_payee_always"])
            if reviewed and fraud:
                human_held = RNG.random() < HUMAN_CATCH
            elif reviewed:
                human_held = RNG.random() < HUMAN_FALSE_FLAG
            else:
                human_held = False

            # Ground truth outcome: executed unless the human held it.
            executed = not human_held
            rows.append(dict(day=day, amount=amount, bank=bank, new_payee=new_payee,
                             payee_id=payee_id, account_fingerprint=fingerprint,
                             vendor_class=vendor_class, confidence=conf,
                             fraud=fraud, human_reviewed=reviewed,
                             human_held=human_held, executed=executed))
    df = pd.DataFrame(rows)
    df["idx"] = np.arange(len(df))
    return df


if __name__ == "__main__":
    df = generate_shadow_stream()
    print(f"{len(df):,} invoices over {DAYS} days")
    print(f"fraud attempts: {df.fraud.sum()} (${df[df.fraud].amount.sum():,.0f} attempted)")
    print(f"human-reviewed: {df.human_reviewed.mean():.1%} of all invoices")
    print(f"fraud caught by incumbent process: {df[df.fraud].human_held.sum()}/{df.fraud.sum()}")
    print(f"legit payments wrongly held: {df[(~df.fraud) & df.human_held].shape[0]}")
    df.to_csv("shadow_stream.csv", index=False)
