"""
Pause Engine: what happens after the gate says escalate.

The gate decides WHETHER to pause. Until now, escalation was a black box: the
transaction went to "a human" and the story ended. Measuring friction properly
showed that this is where the cost actually lives. 19.5 analyst hours per week
against an incumbent 0.4, roughly half a full-time reviewer, and no finance team
buys that.

The gate cannot fix it. Those escalations are genuinely uncertain payments and the
gate is right to flag them. The cost has to come out downstream, by making each
escalation cheaper rather than rarer.

Four mechanisms, in order of how much they save:

1. TRIAGE. Reviews are worked in expected-value order, not arrival order. Value of
   a review = P(fraud) x unrecoverable amount, minus the cost of the review itself.
   An $80,000 international wire to a new payee is worth 12 minutes. A $600 invoice
   from a known vendor with a slightly odd amount is not, and should be handled by
   a default rather than a person.

2. CONTEXT PREFILL. Most review time is spent reconstructing why the payment was
   flagged and what the payee's history looks like. All of that is already known to
   the gate and the ledger. A review with the evidence assembled takes roughly a
   third of the time of one without.

3. BATCHING. Reviews of the same payee, or the same anomaly type, share context.
   Working them together amortises the setup cost across the batch.

4. TIMEOUT DEFAULTS. An escalation nobody answers is the worst outcome in the
   system: it blocks a legitimate payment indefinitely while providing no safety
   benefit. Every paused item carries an explicit expiry and a default action
   chosen by irreversibility, not by convenience.

The engine reports what it costs and what it left undone. A queue that silently
grows is a failure mode, not a steady state.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional
import numpy as np


class Disposition(Enum):
    PENDING = "pending"
    APPROVED_BY_HUMAN = "approved_by_human"
    REJECTED_BY_HUMAN = "rejected_by_human"
    AUTO_RELEASED = "auto_released"        # timeout default: release
    AUTO_HELD = "auto_held"                # timeout default: keep blocked
    AUTO_RESOLVED = "auto_resolved"        # below review-worthiness threshold


# Review time model, minutes. Prefilled context removes the reconstruction step.
REVIEW_MINUTES_COLD = 12.0
REVIEW_MINUTES_PREFILLED = 4.0
BATCH_MARGINAL_MINUTES = 2.0     # additional items in a batch, once context is loaded
ANALYST_COST_PER_HOUR = 45.0


@dataclass
class PausedItem:
    txn_id: int
    amount: float
    bank: str
    payee_id: str
    reversibility: float
    p_fraud: float
    reason: str
    day: int
    is_fraud: Optional[bool] = None       # ground truth, evaluation only
    context: dict = field(default_factory=dict)
    disposition: Disposition = Disposition.PENDING
    review_minutes: float = 0.0
    expired: bool = False        # True only if resolved by timeout, not by policy

    @property
    def unrecoverable(self) -> float:
        return self.amount * (1.0 - self.reversibility)

    @property
    def expected_loss_if_wrong(self) -> float:
        """What is at stake in this decision. The triage key."""
        return self.p_fraud * self.unrecoverable


def build_context(item: PausedItem, payee_profiles: dict, ledger_row=None) -> dict:
    """
    Assemble the evidence a reviewer would otherwise reconstruct by hand. Everything
    here is already known to the gate and the ledger; the reviewer was simply not
    being shown it.
    """
    p = payee_profiles.get(item.payee_id)
    ctx = {
        "flagged_because": item.reason,
        "at_stake": f"${item.unrecoverable:,.0f} unrecoverable of ${item.amount:,.0f}",
        "recovery_odds": f"{item.reversibility:.0%} if caught within 24h",
    }
    if p:
        ctx["payee_history"] = f"{p['n']} prior payments"
        ctx["typical_amount"] = f"${np.exp(p['mu']):,.0f} typical, this is ${item.amount:,.0f}"
        ctx["account_known"] = "yes" if p.get("fingerprints") else "unknown"
        try:
            z = abs(np.log(max(item.amount, 1)) - p["mu"]) / max(p["sd"], 0.25)
            ctx["amount_deviation"] = f"{z:.1f} standard deviations from this payee's norm"
        except Exception:
            pass
    else:
        ctx["payee_history"] = "no prior payments on record"
    return ctx


@dataclass
class PauseEngineConfig:
    review_capacity_minutes_per_day: float = 60.0   # analyst time actually available
    timeout_hours: float = 48.0
    prefill_enabled: bool = True
    batching_enabled: bool = True
    triage_enabled: bool = True
    # An item is worth a human only if what is at stake exceeds the cost of looking.
    min_stake_to_review: float = 150.0
    # Timeout default: release only when the action is recoverable enough to survive
    # being wrong. Otherwise the item stays held and is reported as unresolved.
    auto_release_reversibility_floor: float = 0.55
    auto_release_max_amount: float = 10_000.0


class PauseEngine:
    """Queue, triage, review under finite capacity, and time out what is left."""

    def __init__(self, cfg: PauseEngineConfig = None):
        self.cfg = cfg or PauseEngineConfig()
        self.queue: list = []
        self.resolved: list = []
        self.minutes_spent = 0.0

    # ---------------------------------------------------------------- intake
    def enqueue(self, item: PausedItem, payee_profiles: dict = None):
        if self.cfg.prefill_enabled and payee_profiles is not None:
            item.context = build_context(item, payee_profiles)
        # Below the worthiness threshold, a human review costs more than it protects.
        if item.expected_loss_if_wrong < self.cfg.min_stake_to_review:
            item.disposition = self._auto_default(item, resolved_early=True)
            self.resolved.append(item)
            return
        self.queue.append(item)

    # ---------------------------------------------------------------- triage
    def _triage_key(self, item: "PausedItem") -> float:
        """
        Value of spending a human on this item.

        DESIGN ERROR CORRECTED HERE. The first version ranked purely by stake, which
        measurably made outcomes WORSE under scarce capacity. The reason: the highest
        stake items are precisely the ones the timeout default already handles safely,
        because large unrecoverable payments are auto-HELD rather than released.
        Ranking by stake therefore spent scarce review capacity on items that were
        already safe, while auto-release-eligible items timed out unreviewed.

        A review is only worth its cost when the DEFAULT would be risky. So the key is
        stake conditioned on the item being one the engine would otherwise release.
        """
        would_release = (item.reversibility >= self.cfg.auto_release_reversibility_floor
                         and item.amount <= self.cfg.auto_release_max_amount)
        if not would_release:
            # Default is to hold. A review can still help (it unblocks a legitimate
            # payment) but it is not protecting money, so it ranks below.
            return item.expected_loss_if_wrong * 0.1
        return item.expected_loss_if_wrong

    def _ordered(self) -> list:
        if not self.cfg.triage_enabled:
            return sorted(self.queue, key=lambda i: i.txn_id)      # arrival order
        return sorted(self.queue, key=lambda i: -self._triage_key(i))

    def _review_cost(self, item: PausedItem, prev: Optional[PausedItem]) -> float:
        base = REVIEW_MINUTES_PREFILLED if self.cfg.prefill_enabled else REVIEW_MINUTES_COLD
        if (self.cfg.batching_enabled and prev is not None
                and prev.payee_id == item.payee_id):
            return BATCH_MARGINAL_MINUTES
        return base

    # ----------------------------------------------------------- daily cycle
    def work_day(self, day: int, human_catch_rate: float = 0.90, rng=None):
        """
        Spend the day's review capacity on the highest-stakes items, then expire
        anything past its timeout.
        """
        rng = rng or np.random.default_rng(0)
        budget = self.cfg.review_capacity_minutes_per_day
        prev = None

        # Batching only helps if same-payee items are adjacent, so group after triage.
        ordered = self._ordered()
        if self.cfg.batching_enabled:
            ordered = self._group_by_payee_preserving_priority(ordered)

        for item in ordered:
            cost = self._review_cost(item, prev)
            if cost > budget:
                break
            budget -= cost
            self.minutes_spent += cost
            item.review_minutes = cost
            # Human decision: catches fraud at human_catch_rate, clears legitimate.
            if item.is_fraud:
                caught = rng.random() < human_catch_rate
                item.disposition = (Disposition.REJECTED_BY_HUMAN if caught
                                    else Disposition.APPROVED_BY_HUMAN)
            else:
                item.disposition = Disposition.APPROVED_BY_HUMAN
            self.resolved.append(item)
            prev = item

        self.queue = [i for i in self.queue if i.disposition == Disposition.PENDING]
        self._expire(day)

    @staticmethod
    def _group_by_payee_preserving_priority(ordered: list) -> list:
        """Keep highest-stakes payees first, but bring their other items alongside."""
        seen, out = set(), []
        for item in ordered:
            if item.payee_id in seen:
                continue
            seen.add(item.payee_id)
            out.extend([x for x in ordered if x.payee_id == item.payee_id])
        return out

    # --------------------------------------------------------------- expiry
    def _auto_default(self, item: PausedItem, resolved_early=False) -> Disposition:
        """
        Timeout default chosen by structure, never by convenience. Release only what
        could survive being wrong.
        """
        recoverable_enough = (item.reversibility >= self.cfg.auto_release_reversibility_floor
                              and item.amount <= self.cfg.auto_release_max_amount)
        if resolved_early:
            return Disposition.AUTO_RESOLVED if recoverable_enough else Disposition.AUTO_HELD
        return Disposition.AUTO_RELEASED if recoverable_enough else Disposition.AUTO_HELD

    def _expire(self, day: int):
        timeout_days = self.cfg.timeout_hours / 24.0
        still_pending = []
        for item in self.queue:
            if day - item.day >= timeout_days:
                item.disposition = self._auto_default(item)
                item.expired = True
                self.resolved.append(item)
            else:
                still_pending.append(item)
        self.queue = still_pending

    # -------------------------------------------------------------- reporting
    def report(self, days: int) -> dict:
        counts = {d.value: 0 for d in Disposition}
        for i in self.resolved:
            counts[i.disposition.value] += 1
        counts["pending"] = len(self.queue)
        hours = self.minutes_spent / 60.0
        return {
            "analyst_hours": round(hours, 1),
            "analyst_hours_per_week": round(hours * 7.0 / max(days, 1), 1),
            "analyst_cost": round(hours * ANALYST_COST_PER_HOUR, 0),
            "reviewed_by_human": counts["approved_by_human"] + counts["rejected_by_human"],
            "auto_resolved_below_threshold": counts["auto_resolved"],
            "auto_released_on_timeout": sum(1 for i in self.resolved
                if i.expired and i.disposition == Disposition.AUTO_RELEASED),
            "auto_held_on_timeout": sum(1 for i in self.resolved
                if i.expired and i.disposition == Disposition.AUTO_HELD),
            "held_below_threshold": sum(1 for i in self.resolved
                if not i.expired and i.disposition == Disposition.AUTO_HELD),
            "still_queued": counts["pending"],
            "unresolved_backlog": counts["pending"] + sum(1 for i in self.resolved if i.expired),
        }
