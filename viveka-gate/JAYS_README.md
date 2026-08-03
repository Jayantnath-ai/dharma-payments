# Jay's README: what this thing actually is

Plain language. No framework vocabulary. Read this before demoing it to anyone.

\---

## The one paragraph version

You have an AI agent that pays invoices. Sometimes an invoice is fake, sent by a
criminal pretending to be your real vendor and asking you to send money to a new
bank account. The agent cannot tell, because the fake invoice is designed to look
convincing. This system sits between the agent and the bank and decides, for each
payment: send it, test it with a small payment first, or stop and ask a human. It
decides based mainly on one question the criminal cannot fake. If this turns out to
be wrong, can we get the money back?

Two pieces:

**Viveka Gate v0.1.1** makes the call on each payment.
**Adhikara Ledger v0.1** (the earned trust ledger) learns over time which vendors have
earned the right to be paid without a human checking.

\---

## Part 1: Viveka Gate, the decision

### The problem it solves

Everyone else builds this the same way. If the AI is more than 85 percent sure, pay
it. That fails, because fraud is engineered to make the AI sure. A fake invoice with
your real vendor's logo, real invoice number, urgent tone, and a changed bank
account will produce high confidence. Confidence is exactly the thing the attacker
controls.

### What we do instead

Three questions per payment.

**Can we get the money back if we are wrong?** A domestic wire to a big bank, caught
within a day, is roughly a coin flip. An international wire under 50,000 dollars is
close to hopeless, because the FBI recovery program has a 50,000 dollar minimum.
These numbers come from actual FBI recovery statistics, not guesses.

**Is this payment even the agent's to make?** If it is above the amount you have
delegated, it stops. No confidence level unlocks it. That is not a risk calculation.
It is simply not the agent's decision.

**What does each option actually cost?** Paying now, testing first, and asking a
human all get a price tag. Asking a human is not free. It costs analyst time of
roughly 60 dollars, it delays a legitimate payment, and the human misses fraud about
10 percent of the time anyway. Cheapest option wins.

That third point is the part nobody else does. Every other system treats "ask a
human" as the safe default. It is not. If you ask a human about everything, you have
built an expensive way to annoy your finance team, and they will switch it off.

### What the numbers mean

Tested on 500 invoices with 5 percent fraud, it produces about half the fraud losses
of the standard confidence threshold approach at the same level of disruption.

### The honest weakness

The gate cannot operate in a barely interrupts anyone mode. Its math refuses mid
size unrecoverable wires when the agent is only about 88 percent sure. A CFO may
call that too aggressive. The tradeoff chart exists so you can have that argument
with real numbers instead of opinions.

\---

## Part 2: Adhikara Ledger, learning who to trust

Adhikara means earned fitness to undertake something. Not permission granted, but
qualification demonstrated. Call it the earned trust ledger when you explain it.

### The problem it solves

The gate had a number in it, how much to believe the AI's confidence, and I set it
to 0.85 out of thin air. That is not acceptable in a real system.

There is also a nastier problem. Once the gate starts blocking payments, you never
find out whether the blocked ones were actually fraud, because they never happened.
So the system can never learn about exactly the situations where it is most
cautious.

### What we do instead: shadow mode

For the first 30 to 180 days the gate watches but does not block. Your existing
process runs normally. The gate records what it would have done. Because nothing was
blocked, every payment resolved, so you learn the truth about every case, including
the ones the gate wanted to stop.

At the end you hand the customer a report. Over 90 days I would have held 14
payments. Your team also flagged 2 of them. One that you approved was later
disputed. Here is what it would have cost you and what it would have saved.

That report is the sale. Nobody lets a new system block payments on day one.
Everybody will let it watch.

### What it learns

Fraud is far too rare to learn from. A real mid size company sees maybe 8 fraud
attempts in 6 months. So the system learns from things that happen thousands of
times instead: how often the AI's confidence was right on ordinary payments, when
your human reviewers overrode it and who turned out to be correct, and what actually
got recovered the few times money went out wrongly.

The result is that vendors earn discretion individually. A vendor you have paid 200
times, same bank account, same amount range, earns the right to be paid without a
human looking. A brand new international payee earns nothing.

### One number it sets for you

The gate needs to know roughly how common fraud is in your business. Guess too high
and it panics and holds most payments. The shadow period counts it directly, so
nobody has to guess. If the shadow window happens to contain no fraud at all, it does
not conclude fraud is impossible; it reports what a sample that size can actually
support, and says so.

### What the numbers mean

Your current human process interrupts 1.7 percent of payments and catches 1 fraud in
6. The gate with no learning interrupts 64 percent, which is unusable. The gate after
shadow learning interrupts 44 percent and catches most fraud.

More interruption than today, dramatically more fraud caught. Whether that trade is
worth it is the customer's call, and the shadow report is what lets them decide with
their own numbers.

\---

## The mistake I made, and why it is in the README

The first version let vendors earn trust based on category, such as recurring vendor
or domestic bank. It looked fantastic. Interruptions dropped to 17 percent.

Then I tested what happens if a criminal simply pretends to be in that category. The
catch rate collapsed to nearly zero. Category labels are things the attacker picks. I
had been handing out trust to anyone who claimed the right label.

The fix: trust attaches to the specific vendor, their specific bank account details,
and the amount range they normally invoice. Change the bank account, which is
literally what this fraud does, and all earned trust evaporates instantly.

After the fix, two of the three attacks are completely blocked. The third, where a
criminal has the real vendor, the real bank account, and a normal amount, is only
partly blocked, and that is genuinely unfixable by this method. At that point nothing
about the payment is wrong. It needs a phone call, not better math.

The important lesson: that 17 percent number was fake. It was cheap only because it
was unsafe. The real price of safe automation is 44 percent. Any vendor showing you a
dramatic improvement without showing you this test has not run it.

\---

## Demo script, about 3 minutes

Open the Adhikara Ledger demo. Work down the cards.

**Card 1, the comparison.** Point at the three columns.

> This is your current process on the left. It interrupts almost nobody and catches
> one fraud in six. The middle is our gate with no learning. It works, but it
> interrupts 64 percent of payments and you would switch it off in a week. On the
> right is the same gate after a shadow period. Same protection, far less
> interruption. The learning is not a nice to have. It is the difference between a
> demo and something you would actually run.

**Card 2, the timeline.** Point at the descending bars.

> Month one it is cautious, because it has not earned an opinion about anybody yet.
> By month six it has learned which of your vendors are boring and predictable, and
> it stops bothering you about them. Fraud protection stays flat the whole time. This
> is the answer when someone says your system interrupts too much. Only at first.

**Card 3, what it learned.** Point at the segment table.

> Recurring domestic vendors, twelve hundred payments observed, earned almost full
> discretion. New international payees, thirty four payments, earned almost none. It
> is not one global setting. Every vendor earns their own.

**Card 4, the attack test.** This is the one that wins the room.

> Here is where most demos stop. I kept going. I asked what happens if the criminal
> simply pretends to be a vendor you trust. The first version collapsed and caught
> almost nothing. So trust now attaches to the vendor's actual bank account details
> and their normal invoice size. Change the account, which is exactly what this fraud
> does, and the trust vanishes. Two of three attacks fully blocked. The third one is
> not, and I will tell you why. If they have the real vendor, the real account, and a
> normal amount, nothing about that payment is wrong. That needs a phone call, not
> better software.

Then stop. If they ask one question it will be about the friction number. The answer:

> The honest number is 44 percent, and it is higher than the fake number I could have
> shown you. The 17 percent version was cheap because it was unsafe.

\---

## If asked who built it

Architected and directed by Jayant Nath. Implementation written by Claude in a

session where every version was attacked before it was accepted.

Three impactful contributions were - 

Pricing the cost of inaction, which is the load bearing idea in the whole system and the thing no shipping guardrail does. 

Shadow mode as the calibration bootstrap. 

And refusing to publish the 65 percent friction reduction until it had been attacked, which is what revealed the number was borrowed against a vulnerability.

