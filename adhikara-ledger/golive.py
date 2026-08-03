"""
Go-live: the gate acts, using calibration earned in shadow mode.

Produces three things:
  1. The 30/90-day SHADOW REPORT, what the gate would have done, versus what the
     incumbent human process actually did. This is the artifact an enterprise buyer
     needs before allowing a gate to block anything.
  2. The TIME SERIES, friction falling month over month as trust is earned, with
     catastrophic exposure held flat. The answer to "your gate escalates too much":
     only at first.
  3. The ADVERSARIAL STRESS TEST, what happens when fraud MOVES into the segment
     the gate learned to trust. Reported honestly, because a learned-trust system
     that has never been tested against distribution shift is a liability.

Exploration channel: after go-live, a sampled fraction of low-severity escalations
is released anyway, so labels do not fully censor and calibration keeps updating.
"""

import numpy as np
import pandas as pd
from gate import Transaction, GateConfig, decide
from ledger import learn_segment_calibration, effective_confidence
from shadow import generate_shadow_stream
from recovery_model import simulate_recovery

RNG = np.random.default_rng(99)
EXPLORE_RATE = 0.10          # share of low-severity escalations released for labels
EXPLORE_MAX_AMOUNT = 5_000   # only explore where being wrong is survivable

_R_CACHE = {}


def R_of(amount, bank):
    key = (round(amount, -2), bank)
    if key not in _R_CACHE:
        _R_CACHE[key] = simulate_recovery(amount, bank, n_samples=800)["R"]
    return _R_CACHE[key]


def gate_decide(row, cfg, seg_table=None):
    """Run the gate, optionally with learned per-segment recalibration."""
    conf = row.confidence
    if seg_table is not None:
        m = seg_table[(seg_table.vendor_class == row.vendor_class) &
                      (seg_table.bank == row.bank)]
        if len(m):
            conf = effective_confidence(row.confidence, m.iloc[0])
    tx = Transaction(row.amount, row.bank, conf, row.new_payee)
    return decide(tx, cfg)["decision"], conf


def evaluate(df, cfg, seg_table=None, label=""):
    """Score a policy over a stream. Exposure = expected unrecovered fraud dollars."""
    exposure = 0.0
    friction_ct = 0
    legit_ct = int((~df.fraud).sum())
    caught = 0
    for row in df.itertuples():
        action, _ = gate_decide(row, cfg, seg_table)
        if action == "execute":
            if row.fraud:
                exposure += row.amount * (1 - R_of(row.amount, row.bank))
        elif action == "escalate":
            if row.fraud:
                if RNG.random() < cfg.human_catch_rate:
                    caught += 1
                else:
                    exposure += row.amount * (1 - R_of(row.amount, row.bank))
            else:
                friction_ct += 1
        else:  # decompose / probe
            if row.fraud:
                if RNG.random() < (0.80 if row.new_payee else 0.30):
                    caught += 1
                else:
                    exposure += row.amount * (1 - R_of(row.amount, row.bank))
            else:
                friction_ct += 1
    return dict(label=label, exposure=exposure,
                friction_pct=100.0 * friction_ct / max(legit_ct, 1),
                friction_ct=friction_ct, fraud_caught=caught,
                fraud_total=int(df.fraud.sum()))


# ---------------------------------------------------------------- shadow report
def shadow_report(df, cfg):
    """What the gate WOULD have done vs what humans actually did."""
    would_hold, human_held, agree_hold, gate_only, human_only = 0, 0, 0, 0, 0
    gate_caught_missed_by_human = []
    for row in df.itertuples():
        action, _ = gate_decide(row, cfg, None)
        g_hold = action in ("escalate", "decompose")
        h_hold = bool(row.human_held)
        would_hold += g_hold
        human_held += h_hold
        if g_hold and h_hold:
            agree_hold += 1
        elif g_hold and not h_hold:
            gate_only += 1
            if row.fraud:
                gate_caught_missed_by_human.append(row.amount)
        elif h_hold and not g_hold:
            human_only += 1
    return dict(n=len(df), gate_holds=would_hold, human_holds=human_held,
                agreed=agree_hold, gate_only=gate_only, human_only=human_only,
                fraud_gate_caught_human_missed=len(gate_caught_missed_by_human),
                dollars_saved=float(sum(gate_caught_missed_by_human)))


# ------------------------------------------------------- learning over the months
def rolling_learning(df, cfg, months=6):
    """
    Month 1 runs on the shadow-derived calibration. Each subsequent month
    recalibrates on everything observed so far (including exploration samples).
    """
    df = df.copy()
    df["month"] = ((df.day - 1) // 30) + 1
    max_m = int(df.month.max())
    results, observed = [], []
    seg = None
    for m in range(1, min(months, max_m) + 1):
        mdf = df[df.month == m]
        res = evaluate(mdf, cfg, seg, label=f"month {m}")
        results.append(res)
        # collect labels: everything executed, plus explored escalations
        for row in mdf.itertuples():
            action, _ = gate_decide(row, cfg, seg)
            if action == "execute":
                observed.append(row)
            elif row.amount <= EXPLORE_MAX_AMOUNT and RNG.random() < EXPLORE_RATE:
                observed.append(row)
        if observed:
            seg = learn_segment_calibration(pd.DataFrame(observed))
    return pd.DataFrame(results), seg


# ------------------------------------------------------------- adversarial shift
def adversarial_shift(df_shadow, cfg, seg):
    """
    The honest stress test: fraud relocates into the segment the gate learned to
    trust (recurring vendors, domestic major banks, amounts that look ordinary).
    Does earned trust become an attack surface?
    """
    rng = np.random.default_rng(5)
    rows = []
    for i in range(400):
        fraud = rng.random() < 0.02          # elevated attack rate
        if fraud:
            amount = float(np.round(rng.lognormal(9.0, 0.6), 2))   # ordinary-looking
            bank, vc, newp = "domestic_major", "recurring", False   # MIMICS TRUSTED SEGMENT
            conf = float(np.clip(rng.beta(9, 1.2), 0, 1))
        else:
            amount = float(np.round(rng.lognormal(8.3, 1.15), 2))
            bank = rng.choice(["domestic_major", "domestic_small"], p=[0.7, 0.3])
            vc, newp = "recurring", False
            conf = float(np.clip(rng.beta(9, 1.2), 0, 1))
        rows.append(dict(amount=amount, bank=bank, vendor_class=vc, new_payee=newp,
                         confidence=conf, fraud=fraud))
    adv = pd.DataFrame(rows)
    naive = evaluate(adv, cfg, None, "static calibration")
    learned = evaluate(adv, cfg, seg, "learned calibration")
    return naive, learned, adv


if __name__ == "__main__":
    cfg = GateConfig()
    df = generate_shadow_stream(days=180)

    print("=== SHADOW REPORT (180 days, gate observing only) ===")
    rep = shadow_report(df, cfg)
    for k, v in rep.items():
        print(f"  {k}: {v}")

    print("\n=== LEARNING CURVE (friction as trust is earned) ===")
    curve, seg = rolling_learning(df, cfg, months=6)
    print(curve[["label", "friction_pct", "exposure", "fraud_caught", "fraud_total"]].to_string(index=False))

    print("\n=== ADVERSARIAL SHIFT: fraud mimics the trusted segment ===")
    naive, learned, adv = adversarial_shift(df, cfg, seg)
    for r in (naive, learned):
        print(f"  {r['label']:22s} exposure=${r['exposure']:>10,.0f}  "
              f"friction={r['friction_pct']:5.1f}%  caught={r['fraud_caught']}/{r['fraud_total']}")

    curve.to_csv("learning_curve.csv", index=False)
    if seg is not None:
        seg.to_csv("segment_calibration_final.csv", index=False)
