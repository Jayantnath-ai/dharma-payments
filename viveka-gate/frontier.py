"""
Trace the loss/friction frontier for the Viveka gate by sweeping the effective
price of human review (a risk-tolerance dial), and compare against the fixed
baselines A (raw agent) and B (confidence threshold 0.85).

Fair test: does the gate's frontier pass BELOW baseline B — i.e. at B's
friction level, does the gate lose fewer catastrophic dollars?
"""

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from gate import Transaction, GateConfig, decide
from benchmark import make_invoices
from recovery_model import simulate_recovery

def exp_loss(amount, bank):
    R = simulate_recovery(amount, bank, n_samples=2000)["R"]
    return amount * (1.0 - R)

RNG = np.random.default_rng(7)


def run_gate(df, cfg, seed=11):
    rng = np.random.default_rng(seed)
    cat_loss = friction_ct = 0.0
    legit_ct = (~df.fraud).sum()
    for _, r in df.iterrows():
        tx = Transaction(r.amount, r.bank, r.confidence, r.new_payee)
        action = decide(tx, cfg)["decision"]
        if action == "execute":
            if r.fraud:
                cat_loss += exp_loss(r.amount, r.bank)
        elif action == "escalate":
            if r.fraud:
                cat_loss += (1 - cfg.human_catch_rate) * exp_loss(r.amount, r.bank)
            else:
                friction_ct += 1
        else:  # decompose
            catch = 0.80 if r.new_payee else 0.30
            if r.fraud:
                cat_loss += (1 - catch) * exp_loss(r.amount, r.bank)
            else:
                friction_ct += 1
    return cat_loss, 100.0 * friction_ct / legit_ct


def run_threshold(df, thresh, seed=11):
    rng = np.random.default_rng(seed)
    cat_loss = friction_ct = 0.0
    legit_ct = (~df.fraud).sum()
    for _, r in df.iterrows():
        if r.confidence > thresh:
            if r.fraud:
                cat_loss += exp_loss(r.amount, r.bank)
        else:
            if r.fraud:
                cat_loss += 0.10 * exp_loss(r.amount, r.bank)
            else:
                friction_ct += 1
    return cat_loss, 100.0 * friction_ct / legit_ct


if __name__ == "__main__":
    df = make_invoices()

    # Gate frontier: sweep review labor cost (risk-tolerance dial)
    gate_pts = []
    for labor in [30, 60, 120, 250, 500, 1000, 2000, 4000, 8000]:
        cfg = GateConfig(review_labor_cost=labor)
        loss, fric = run_gate(df, cfg)
        gate_pts.append((fric, loss, labor))
        print(f"gate  labor=${labor:>5}  friction={fric:5.1f}%  loss=${loss:>10,.0f}")

    # Threshold frontier: sweep confidence threshold
    th_pts = []
    for t in [0.5, 0.7, 0.8, 0.85, 0.9, 0.95, 0.98]:
        loss, fric = run_threshold(df, t)
        th_pts.append((fric, loss, t))
        print(f"thresh t={t:.2f}       friction={fric:5.1f}%  loss=${loss:>10,.0f}")

    g = pd.DataFrame(gate_pts, columns=["friction", "loss", "param"]).sort_values("friction")
    th = pd.DataFrame(th_pts, columns=["friction", "loss", "param"]).sort_values("friction")

    fig, ax = plt.subplots(figsize=(8, 5.5))
    ax.plot(th.friction, th.loss / 1000, "o--", color="#c0392b", label="Confidence threshold (industry standard)")
    ax.plot(g.friction, g.loss / 1000, "o-", color="#1a7a4a", label="Viveka gate (deferral-aware, R-weighted)")
    ax.set_xlabel("Friction: % of legitimate payments delayed")
    ax.set_ylabel("Catastrophic loss ($k, fraudulent dollars unrecovered)")
    ax.set_title("Pricing the pause: catastrophic loss vs. friction\n500 invoices, 5% BEC-style fraud, $632k at risk")
    ax.legend()
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig("frontier.png", dpi=150)
    g.to_csv("frontier_gate.csv", index=False)
    th.to_csv("frontier_threshold.csv", index=False)
    print("\nSaved frontier.png")
