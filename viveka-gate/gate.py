"""
The Viveka gate.

Decision rule for an agent's proposed wire transfer. Three options, all priced:

  EXECUTE   — act now on the agent's judgment
  DECOMPOSE — convert into a reversible probe (micro test transaction first)
  ESCALATE  — defer to a human; deferral is NOT free (delay cost, response risk)

Core principles implemented:
1. Deferral is a member of the action set with its own cost (karma in akarma).
2. Irreversibility (1 - R) is estimated by BACKWARD Monte Carlo over recovery
   paths — never by forecasting outcomes.
3. Inverse horizon: the less reversible the action, the less the agent's own
   confidence (a forward forecast) is trusted, and the more structural
   properties (R, delegation scope S) dominate. Implemented as an exponent
   that discounts confidence as irreversibility rises.
4. Adhikara / delegation scope S: amounts above the agent's mandate zero out
   its authority to execute regardless of confidence.
"""

from dataclasses import dataclass
from recovery_model import simulate_recovery


@dataclass
class Transaction:
    amount: float
    receiving_bank: str          # 'domestic_major' | 'domestic_small' | 'international'
    agent_confidence: float      # agent's P(legitimate), in [0,1]
    is_new_payee: bool


@dataclass
class GateConfig:
    delegation_limit: float = 25_000.0   # agent's mandate (S)
    review_delay_hours: float = 4.0      # human review turnaround
    delay_cost_per_hour_frac: float = 0.0002  # cost of delaying a legit payment (late fees, relationship)
    review_labor_cost: float = 60.0      # fixed cost of one human review (analyst time)
    human_catch_rate: float = 0.90       # P(human catches fraud on review)
    probe_cost: float = 25.0             # cost of a test-transaction round trip
    calibration: float = 0.85            # trust in agent's confidence (from validation history)
    base_rate_legit: float = 0.95        # structural prior: historical share of legitimate invoices


def decide(tx: Transaction, cfg: GateConfig) -> dict:
    # --- Structural inputs (assessable NOW, no forecasting) ---
    rec = simulate_recovery(tx.amount, tx.receiving_bank, n_samples=2000)
    R = rec["R"]                      # reversibility
    irr = 1.0 - R                     # irreversibility
    S = 1.0 if tx.amount <= cfg.delegation_limit else 0.0

    # --- Inverse horizon: discount the agent's forward-looking confidence
    #     as irreversibility rises. At R=1 (fully reversible) we take W at
    #     calibrated face value; at R=0 confidence is heavily shrunk toward
    #     the uninformative prior 0.5.
    prior = cfg.base_rate_legit       # structural knowledge: no forecasting needed
    W_raw = cfg.calibration * tx.agent_confidence + (1 - cfg.calibration) * prior
    shrink = irr ** 2                 # convex: mild for reversible, harsh for irreversible
    W = (1 - shrink) * W_raw + shrink * prior
    p_fraud = 1.0 - W

    A = tx.amount

    # --- Expected cost of each option (lower is better) ---
    # EXECUTE: if fraud, lose amount unless recovered; recovery itself modeled by R.
    cost_execute = p_fraud * A * (1.0 - R)
    if S == 0.0:
        cost_execute = float("inf")   # outside adhikara: not the agent's to do

    # ESCALATE: delay cost on legit payments + residual fraud loss if human misses.
    cost_escalate = (cfg.review_labor_cost
                     + W * A * cfg.delay_cost_per_hour_frac * cfg.review_delay_hours
                     + p_fraud * (1 - cfg.human_catch_rate) * A * (1.0 - R))

    # DECOMPOSE: probe cost + delay; probe catches most changed-account fraud
    # for new payees (verification of receiving account), less useful otherwise.
    probe_catch = 0.80 if tx.is_new_payee else 0.30
    cost_decompose = (cfg.probe_cost
                      + W * A * cfg.delay_cost_per_hour_frac * 24.0
                      + p_fraud * (1 - probe_catch) * A * (1.0 - R))
    if S == 0.0:
        cost_decompose = float("inf")  # probes still execute value transfer

    costs = {"execute": cost_execute, "decompose": cost_decompose, "escalate": cost_escalate}
    choice = min(costs, key=costs.get)
    return {"decision": choice, "costs": costs, "R": R, "W": W, "S": S,
            "reason": _reason(choice, R, W, S, tx)}


def _reason(choice, R, W, S, tx):
    if S == 0.0:
        return f"amount ${tx.amount:,.0f} exceeds delegation limit — outside agent adhikara"
    if choice == "execute":
        return f"warranted confidence {W:.2f} sufficient given reversibility R={R:.2f}"
    if choice == "decompose":
        return f"new payee + irreversibility {1-R:.2f}: reversible probe dominates"
    return f"confidence {W:.2f} does not carry irreversibility {1-R:.2f} at ${tx.amount:,.0f}"
