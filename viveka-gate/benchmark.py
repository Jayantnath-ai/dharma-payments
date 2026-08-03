"""
Benchmark: 500 synthetic invoices, ~5% fraudulent (BEC-style).

Baselines:
  A. RAW AGENT        — executes whatever it believes legitimate (conf > 0.5)
  B. NAIVE THRESHOLD  — executes iff confidence > 0.85 (industry-standard guardrail)
  C. VIVEKA GATE      — full comparative rule (this work)

Fraud generator mimics BEC: fraudulent invoices are ENGINEERED to look
legitimate (urgency, lookalike domains, changed bank details), so the agent's
confidence on fraud is adversarially high — the realistic hard case. Fraud
skews toward new payees, larger amounts, and less-recoverable rails.

Metrics:
  catastrophic loss  = fraudulent dollars executed and NOT recovered
  friction           = % of legitimate invoices delayed (escalated/decomposed)
  friction cost      = delay/probe costs on legitimate payments
"""

import numpy as np
import pandas as pd
from gate import Transaction, GateConfig, decide
from recovery_model import simulate_recovery

RNG = np.random.default_rng(7)
N = 500
FRAUD_RATE = 0.05


def make_invoices():
    rows = []
    for i in range(N):
        fraud = RNG.random() < FRAUD_RATE
        if fraud:
            amount = float(np.round(RNG.lognormal(10.0, 1.0), 2))       # skew large (~$22k median)
            bank = RNG.choice(["domestic_small", "international"], p=[0.4, 0.6])
            new_payee = RNG.random() < 0.85
            conf = float(np.clip(RNG.beta(8, 2), 0, 1))                 # adversarially convincing (~0.80)
        else:
            amount = float(np.round(RNG.lognormal(8.5, 1.2), 2))        # ~$4.9k median
            bank = RNG.choice(["domestic_major", "domestic_small", "international"], p=[0.6, 0.3, 0.1])
            new_payee = RNG.random() < 0.15
            conf = float(np.clip(RNG.beta(9, 1.2), 0, 1))               # ~0.88
        rows.append(dict(amount=amount, bank=bank, new_payee=new_payee,
                         confidence=conf, fraud=fraud))
    return pd.DataFrame(rows)


def realized_loss(amount, bank):
    """If a fraudulent wire executes, does recovery save it? One draw."""
    R = simulate_recovery(amount, bank, n_samples=500)["R"]
    return amount if RNG.random() > R else 0.0


def run(df):
    cfg = GateConfig()
    HUMAN_CATCH, PROBE_CATCH_NEW, PROBE_CATCH_OLD = cfg.human_catch_rate, 0.80, 0.30
    results = {}

    for policy in ["A_raw", "B_threshold", "C_viveka"]:
        cat_loss = friction_ct = friction_cost = missed_legit_value = 0.0
        legit_ct = (~df.fraud).sum()

        for _, r in df.iterrows():
            tx = Transaction(r.amount, r.bank, r.confidence, r.new_payee)

            if policy == "A_raw":
                action = "execute" if r.confidence > 0.5 else "escalate"
            elif policy == "B_threshold":
                action = "execute" if r.confidence > 0.85 else "escalate"
            else:
                action = decide(tx, cfg)["decision"]

            if action == "execute":
                if r.fraud:
                    cat_loss += realized_loss(r.amount, r.bank)
            elif action == "escalate":
                if r.fraud:
                    if RNG.random() > HUMAN_CATCH:                      # human misses
                        cat_loss += realized_loss(r.amount, r.bank)
                else:
                    friction_ct += 1
                    friction_cost += r.amount * cfg.delay_cost_per_hour_frac * cfg.review_delay_hours
            else:  # decompose
                catch = PROBE_CATCH_NEW if r.new_payee else PROBE_CATCH_OLD
                if r.fraud:
                    if RNG.random() > catch:
                        cat_loss += realized_loss(r.amount, r.bank)
                else:
                    friction_ct += 1
                    friction_cost += cfg.probe_cost + r.amount * cfg.delay_cost_per_hour_frac * 24.0

        results[policy] = dict(
            catastrophic_loss=cat_loss,
            friction_pct=100.0 * friction_ct / legit_ct,
            friction_cost=friction_cost,
        )
    return results


if __name__ == "__main__":
    df = make_invoices()
    fraud_dollars = df[df.fraud].amount.sum()
    print(f"Invoices: {N}  |  fraudulent: {df.fraud.sum()} (${fraud_dollars:,.0f} at risk)\n")
    res = run(df)
    print(f"{'policy':14s} {'catastrophic loss':>18s} {'friction %':>11s} {'friction cost':>14s}")
    for k, v in res.items():
        print(f"{k:14s} {'$'+format(v['catastrophic_loss'], ',.0f'):>18s} "
              f"{v['friction_pct']:>10.1f}% {'$'+format(v['friction_cost'], ',.0f'):>14s}")
    pd.DataFrame(res).T.to_csv("results.csv")
    df.to_csv("invoices.csv", index=False)
