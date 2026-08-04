"""
The agent: a real LLM reading a real invoice.

Until now the gate consumed a simulated confidence, drawn from a Beta distribution.
That was a deliberate modelling choice, since the gate's argument is that it works
regardless of how the confidence was produced. But it left a gap: nothing in this
system actually read an invoice.

This module closes it. An invoice, in the form an accounts payable inbox would receive
it, goes to Claude. What comes back is a structured judgement: is this legitimate, how
confident, and which specific signals drove the answer. That confidence then feeds the
Viveka Gate exactly as the simulated number did.

WHY THIS MATTERS FOR THE ARGUMENT

The gate's whole thesis is that business email compromise is engineered to defeat
confidence, and that reversibility is the signal an attacker cannot fake. That is a
claim about what an LLM will do when shown a well-crafted fraudulent invoice. With a
simulated confidence it was an assumption. With a real call it is testable, and the
test can fail.

Run `python agent.py --demo` to see a genuine BEC invoice scored.

NO RETRIEVAL IS USED HERE. Payee history is passed directly into the prompt as
structured context, because the payee ID is a known join key and the record is exact.
See EVALUATION.md section 7.
"""

import json
import os
import re
from dataclasses import dataclass, asdict
from typing import Optional

MODEL = "claude-sonnet-4-6"
MAX_TOKENS = 1000


SYSTEM_PROMPT = """You are an accounts payable analyst assessing whether an invoice is legitimate.

You will be given an invoice and, where available, the payment history for that payee.

Assess the likelihood that this invoice is legitimate rather than fraudulent. Business
email compromise is the primary threat: a criminal impersonating a real vendor, often
with correct branding and plausible invoice numbers, requesting payment to bank details
that differ from those previously used.

Signals that matter: whether banking details differ from history, whether the amount is
consistent with this payee's normal range, urgency or pressure language, mismatches
between sender domain and vendor identity, and unusual payment terms.

Respond with ONLY a JSON object, no preamble and no markdown fences:
{
  "p_legitimate": <float 0.0 to 1.0>,
  "primary_signals": [<up to 3 short strings, the specific things that drove your judgement>],
  "bank_details_changed": <true, false, or null if unknown>,
  "amount_consistent_with_history": <true, false, or null if unknown>,
  "reasoning": "<one sentence>"
}"""


@dataclass
class AgentAssessment:
    p_legitimate: float
    primary_signals: list
    bank_details_changed: Optional[bool]
    amount_consistent_with_history: Optional[bool]
    reasoning: str
    raw_model_output: str = ""

    @property
    def confidence(self) -> float:
        """The number the Viveka Gate consumes."""
        return float(min(max(self.p_legitimate, 0.0), 1.0))


def format_payee_history(profile: dict) -> str:
    """Structured context, passed directly. No retrieval: the payee ID is the key."""
    if not profile:
        return "PAYEE HISTORY: none on record. This payee has not been paid before."
    import numpy as np
    typical = float(np.exp(profile["mu"])) if "mu" in profile else None
    lines = [f"PAYEE HISTORY: {profile.get('n', 0)} prior payments on record."]
    if typical:
        lines.append(f"Typical amount: ${typical:,.0f}")
    fps = profile.get("fingerprints")
    if fps:
        lines.append(f"Bank account identifiers previously used: {', '.join(sorted(fps))}")
    return "\n".join(lines)


def build_user_message(invoice_text: str, payee_profile: dict = None) -> str:
    return f"{format_payee_history(payee_profile)}\n\nINVOICE:\n{invoice_text}"


def _parse(text: str) -> dict:
    """Models occasionally wrap JSON in fences despite instructions."""
    cleaned = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.MULTILINE).strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", cleaned, re.DOTALL)
        if m:
            return json.loads(m.group(0))
        raise


def assess_invoice(invoice_text: str, payee_profile: dict = None,
                   api_key: str = None) -> AgentAssessment:
    """
    Call Claude and return a structured assessment. Requires ANTHROPIC_API_KEY in the
    environment or passed directly.
    """
    try:
        import anthropic
    except ImportError:
        raise ImportError("pip install anthropic")

    client = anthropic.Anthropic(api_key=api_key or os.environ.get("ANTHROPIC_API_KEY"))
    resp = client.messages.create(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user",
                   "content": build_user_message(invoice_text, payee_profile)}],
    )
    text = "".join(b.text for b in resp.content if getattr(b, "type", "") == "text")
    data = _parse(text)
    return AgentAssessment(
        p_legitimate=float(data.get("p_legitimate", 0.5)),
        primary_signals=data.get("primary_signals", []),
        bank_details_changed=data.get("bank_details_changed"),
        amount_consistent_with_history=data.get("amount_consistent_with_history"),
        reasoning=data.get("reasoning", ""),
        raw_model_output=text,
    )


# --------------------------------------------------------------------------
# End to end: invoice -> agent -> gate
# --------------------------------------------------------------------------

def assess_and_gate(invoice_text: str, amount: float, bank: str,
                    payee_profile: dict = None, new_payee: bool = False,
                    gate_config=None, api_key: str = None) -> dict:
    """
    The full pipeline. The agent reads the invoice; the gate decides what to do about
    the agent's judgement.

    Note what happens on a well-crafted BEC invoice: the agent's confidence is often
    high, because the invoice is designed to produce exactly that. The gate's decision
    is driven by reversibility, which the attacker does not control.
    """
    from gate import Transaction, GateConfig, decide

    a = assess_invoice(invoice_text, payee_profile, api_key)
    cfg = gate_config or GateConfig()
    verdict = decide(Transaction(amount, bank, a.confidence, new_payee), cfg)
    return {"agent": asdict(a), "gate": verdict,
            "agent_confidence": a.confidence, "decision": verdict["decision"]}


# --------------------------------------------------------------------------
# Sample invoices for demonstration
# --------------------------------------------------------------------------

LEGITIMATE_INVOICE = """From: accounts@meridiansupply.com
Subject: Invoice MS-88421

Meridian Supply Co.
Invoice MS-88421
Date: 14 March

Quarterly facilities consumables, as per contract MS-2024-11.
Amount due: $4,180.00
Terms: Net 30

Remit to:
Account identifier: FP007
First National, routing on file.
"""

BEC_INVOICE = """From: accounts@meridian-supply.com
Subject: URGENT: Invoice MS-88437 - Updated Banking Details

Meridian Supply Co.
Invoice MS-88437
Date: 14 March

Quarterly facilities consumables, as per contract MS-2024-11.
Amount due: $22,400.00
Terms: Due on receipt

IMPORTANT: Please note our banking details have changed following a treasury
restructure. Kindly update your records and remit to the account below. Our previous
account is now closed and payments sent there cannot be recovered.

Remit to:
Account identifier: FP553-NEW
Sterling Commercial Bank

This invoice is overdue in our system and our account manager has asked that it be
settled today to avoid a service interruption.
"""

SAMPLE_PROFILE = {"n": 47, "mu": 8.34, "sd": 0.42, "fingerprints": {"FP007"}}


if __name__ == "__main__":
    import sys
    if "--demo" not in sys.argv:
        print(__doc__)
        sys.exit(0)
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("Set ANTHROPIC_API_KEY to run the live demo.")
        sys.exit(1)

    from ledger import derive_gate_config  # noqa
    from gate import GateConfig

    cfg = GateConfig(base_rate_legit=0.9985)   # realistic AP base rate
    cases = [
        ("LEGITIMATE", LEGITIMATE_INVOICE, 4180.0, "domestic_major", False),
        ("BEC ATTEMPT", BEC_INVOICE, 22400.0, "domestic_small", True),
    ]
    for label, text, amt, bank, newp in cases:
        r = assess_and_gate(text, amt, bank, SAMPLE_PROFILE, newp, cfg)
        a = r["agent"]
        print(f"\n=== {label} : ${amt:,.0f} ===")
        print(f"  agent says legitimate with p = {a['p_legitimate']:.2f}")
        print(f"  signals: {', '.join(a['primary_signals'])}")
        print(f"  bank details changed: {a['bank_details_changed']}")
        print(f"  reasoning: {a['reasoning']}")
        print(f"  GATE DECISION: {r['decision'].upper()}")
        print(f"  reason: {r['gate']['reason']}")
