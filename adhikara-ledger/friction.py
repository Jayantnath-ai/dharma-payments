"""
Friction, measured honestly.

The headline number reported so far ("44% friction") counts EVENTS and lumps two
very different interventions together. Both choices make the gate look worse than
it is, and neither is what a finance team actually cares about.

Three problems with a single event-count percentage:

1. An escalation and a probe are not the same cost. An escalation consumes analyst
   attention, which is the genuinely scarce resource. A probe is an automated test
   payment: it delays settlement by roughly a day and costs a few dollars in fees,
   but no human ever looks at it. Reporting them together overstates the
   operational burden.

2. Counting events treats a $500 invoice and an $80,000 wire identically. Held
   payments skew large by construction, so the dollar-weighted picture differs
   materially from the event-weighted one, in both directions depending on policy.

3. The number a CFO acts on is not a percentage. It is analyst hours per week and
   working capital delayed. Those are derivable and should be reported directly.

This module reports all of it, so the tradeoff can be argued with the right units
instead of one blunt figure.
"""

from dataclasses import dataclass, asdict


@dataclass
class FrictionProfile:
    """Complete friction accounting for one policy over one stream."""
    legit_total: int = 0
    legit_value: float = 0.0

    escalated_ct: int = 0            # human attention consumed
    escalated_value: float = 0.0
    probed_ct: int = 0               # automated, no human touch
    probed_value: float = 0.0

    # cost parameters, carried so the report is self-describing
    analyst_minutes_per_review: float = 12.0
    probe_delay_hours: float = 24.0
    escalation_delay_hours: float = 4.0

    def record_legit(self, amount: float, action: str):
        self.legit_total += 1
        self.legit_value += amount
        if action == "escalate":
            self.escalated_ct += 1
            self.escalated_value += amount
        elif action == "decompose":
            self.probed_ct += 1
            self.probed_value += amount

    # ---- headline rates -------------------------------------------------
    @property
    def held_ct(self) -> int:
        return self.escalated_ct + self.probed_ct

    @property
    def friction_pct(self) -> float:
        """The legacy number: any legitimate payment not executed immediately."""
        return 100.0 * self.held_ct / max(self.legit_total, 1)

    @property
    def human_friction_pct(self) -> float:
        """The number that actually costs staff time."""
        return 100.0 * self.escalated_ct / max(self.legit_total, 1)

    @property
    def probe_friction_pct(self) -> float:
        return 100.0 * self.probed_ct / max(self.legit_total, 1)

    # ---- dollar weighted ------------------------------------------------
    @property
    def value_friction_pct(self) -> float:
        """Share of legitimate DOLLARS delayed, not share of invoices."""
        held_value = self.escalated_value + self.probed_value
        return 100.0 * held_value / max(self.legit_value, 1.0)

    @property
    def human_value_friction_pct(self) -> float:
        return 100.0 * self.escalated_value / max(self.legit_value, 1.0)

    # ---- operational units ----------------------------------------------
    def analyst_hours(self) -> float:
        return self.escalated_ct * self.analyst_minutes_per_review / 60.0

    def analyst_hours_per_week(self, days_observed: int) -> float:
        if days_observed <= 0:
            return 0.0
        return self.analyst_hours() * 7.0 / days_observed

    def working_capital_delayed(self) -> float:
        """Dollar-hours of settlement delay, the treasury-facing cost."""
        return (self.escalated_value * self.escalation_delay_hours
                + self.probed_value * self.probe_delay_hours)

    def summary(self, days_observed: int = None) -> dict:
        out = {
            "legit_payments": self.legit_total,
            "legit_value": round(self.legit_value, 2),
            "friction_pct_events": round(self.friction_pct, 1),
            "human_friction_pct": round(self.human_friction_pct, 1),
            "probe_friction_pct": round(self.probe_friction_pct, 1),
            "friction_pct_value": round(self.value_friction_pct, 1),
            "human_friction_pct_value": round(self.human_value_friction_pct, 1),
            "analyst_hours": round(self.analyst_hours(), 1),
            "working_capital_delayed_dollar_hours": round(self.working_capital_delayed(), 0),
        }
        if days_observed:
            out["analyst_hours_per_week"] = round(self.analyst_hours_per_week(days_observed), 1)
        return out

    def one_line(self, days_observed: int = None) -> str:
        """The sentence to put in front of a finance team."""
        base = (f"{self.human_friction_pct:.1f}% of invoices need a human "
                f"({self.probe_friction_pct:.1f}% auto-verified), "
                f"{self.value_friction_pct:.1f}% of dollars delayed")
        if days_observed:
            base += f", {self.analyst_hours_per_week(days_observed):.1f} analyst hours per week"
        return base
