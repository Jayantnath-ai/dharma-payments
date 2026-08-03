# Dharma Payments

**Governance for AI agents that move money.**

An AI agent paying invoices cannot tell a real vendor from a criminal impersonating
one, because business email compromise is engineered to produce high confidence. A
fake invoice carries the real vendor's name, a plausible invoice number, urgency,
and changed bank details. Confidence is the one signal the attacker controls.

This repository contains two components that decide differently.

## [Viveka Gate](./viveka-gate) v0.1.1

Decides each payment by what the attacker cannot fake: whether the money could be
recovered if the payment turns out to be wrong. Reversibility is computed per
transaction by a backward Monte Carlo over recall mechanics, calibrated to FBI
Financial Fraud Kill Chain statistics and the FinCEN 50,000 dollar international
recovery threshold. Execution, a reversible test payment, and human escalation
compete on expected cost, so deferral is priced rather than treated as a free safe
harbour.

Result on a 500 invoice benchmark with 5 percent adversarial fraud: roughly half the
catastrophic loss of a confidence threshold at matched friction.

## [Adhikara Ledger](./adhikara-ledger) v0.1

The earned trust ledger. Runs first in shadow mode, observing without blocking,
which is the only period in which outcome labels are uncensored: once a gate blocks
a payment, that payment never resolves and the system can never learn about the
cases where it is most cautious. Fraud is far too rare to calibrate on, so trust is
learned from abundant signals instead, and it accrues per counterparty rather than
per category.

Trust binds to payee identity, account fingerprint, and the amount envelope that
earned it. Change the bank details, which is precisely what this fraud does, and
earned trust is void.

Result: human reviews fall from 62 percent of payments to 9 percent with protection
held constant, and two of three adversarial attacks are fully closed.

## The finding worth reading

An earlier design bound trust to segment labels such as vendor class and bank type.
It reported an excellent friction number. Under adversarial test its catch rate
collapsed to near zero, because segment labels are attributes an attacker selects.
Measured properly, with identity bound trust, 9.2 percent of payments reach a human.

The third attack, in which an adversary presents the real payee, the real account,
and an ordinary amount, remains only partially closed. Nothing in such a transaction
is wrong. It requires out of band verification rather than better inference, and the
repository says so rather than hiding it.

## Tuning

There is one dial: how expensive you consider a human review. Friction is a
consequence of that choice rather than a setting. Between the $60 and $250 positions,
human reviews fall from 40 percent to 9 percent for roughly $1,500 of additional
expected exposure. Past $500 the curve is dominated, buying losses for no time back.
See `viveka-gate/tuning_demo.html`.

Holds are not one thing. An automated test payment costs about a dollar and the
finance team never sees it; a human review costs analyst time. Reporting both as a
single friction number, which an earlier version of this work did, understates the
system badly.

## Reading order

Start with [JAYS_README.md](./JAYS_README.md) for a plain language explanation of
what both components do and why. Each component folder then has its own README with
methodology, calibration sources, and limitations.

## Status

Research prototype. Synthetic transaction streams; recovery calibration anchored to
aggregate published statistics rather than transaction level data. Collaboration and
critique welcome, particularly from payments and fraud operations practitioners who
can identify where the recovery model is naive.

Part of the DharmaAGI architecture: governance components for agentic systems.
