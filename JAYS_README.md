# Jay's README: what this thing actually is

Plain language. No framework vocabulary. Read this before demoing it to anyone.

---

## The one paragraph version

You have an AI agent that pays invoices. Sometimes an invoice is fake, sent by a
criminal pretending to be your real vendor and asking you to send money to a new
bank account. The agent cannot tell, because the fake invoice is designed to look
convincing. This system sits between the agent and the bank and decides, for each
payment: send it, test it with a small payment first, or stop and ask a human. It
decides based mainly on one question the criminal cannot fake. If this turns out to
be wrong, can we get the money back?

![How the pieces fit together](docs/system_flow.svg)

Read it top to bottom: a payment comes in, the gate decides, anything needing a human
goes to the queue, and everything that happens gets recorded so the system knows more
next time. The arrow curving back up the left side is the important one. It is why the
system interrupts you less as the months go by.

Three pieces:

**Viveka Gate v0.1.1** makes the call on each payment.
**Adhikara Ledger v0.1** (the earned trust ledger) learns over time which vendors have
earned the right to be paid without a human checking.

---

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

---

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

One percentage was hiding three different costs, so the system now reports all of
them. An escalation eats analyst time. A probe is an automated test payment that no
human ever sees. And a held $80,000 wire is not the same event as a held $500
invoice.

| | needs a human | dollars delayed | analyst hours per week |
|---|---|---|---|
| Your process today | 0.9% | 2.1% | 0.4 |
| Gate, no learning | 61.7% | 79.0% | 29.3 |
| Gate, shadow calibrated | 39.8% | 62.0% | 18.9 |

Every figure above is a mean across 20 random seeds with a standard deviation under
2 points, so they are measurements rather than one lucky run.

Two things to notice, and the second one matters more.

Splitting the number did not flatter the system. Dollar friction is higher than event
friction, 62 against 44 percent, because held payments skew large by construction.
The honest measure looks worse than the blunt one.

And the number that decides adoption is not a percentage at all. It is 19.5 analyst
hours a week, roughly half a person, against 0.4 today. That is the real barrier, and
it is the thing to attack next. The percentage was never the problem.

---

## Part 3: Pause Engine, making the interruptions cheap

### The problem it solves

Measuring friction properly showed the real barrier was not the percentage of
payments held. It was that clearing the queue needed 19.7 analyst hours a week,
roughly half a person, against 0.4 hours today. Nobody hires half a person to run a
fraud gate.

The gate cannot fix this, because those payments genuinely are uncertain. The cost has
to come out of the review itself.

![Inside the review queue](docs/pause_engine_flow.svg)

Grey boxes are payments resolved without anyone looking at them. Teal is the one path
that costs analyst time. Two of the three ways out never touch a person.

### What we do

Show the reviewer the evidence up front. Most of a review was spent working out why
the payment was flagged and what this vendor normally does, all of which the system
already knew. A review drops from about 12 minutes to 4.

Work the queue in the order that protects the most money, not the order things
arrived. Skip reviews where the amount at stake is less than the cost of looking. Work
same-vendor items together. And give every held payment an expiry with a sensible
default, because a payment held forever because nobody looked is the worst outcome in
the system.

### What the numbers mean

18.9 analyst hours a week becomes **5.1**, with identical fraud protection. About
$3,000 of labour over 90 days instead of $11,300.

The surprise: nearly all of that came from the simplest change, showing the reviewer
the evidence. The clever mechanisms, priority ordering and batching, contributed less
than a fifth between them.

### The design error worth knowing about

The first version of the priority ordering sent the biggest, riskiest payments to
humans first. That sounds obviously right and it was wrong. Those payments are already
safe, because when nobody reviews them in time the system holds them rather than
releasing them. Meanwhile the smaller payments, the ones the system releases by
default when time runs out, were sitting unreviewed. Prioritising by size actively
made things worse than reviewing in arrival order.

The fix: prioritise by what is at stake **among payments the system would otherwise
let through**. A review is only worth paying for when the default would be risky.
Money released without review went from roughly $30,000 to exactly zero, on every
one of fifteen random seeds tested.

---

## What numbers survived, and what did not

Every result here was originally produced from a single run. Because two earlier
numbers in this project turned out to be flukes, everything was re-run across 15 to 20
independent random simulations.

The friction and analyst-time numbers held up almost exactly. The savings are real.

Two things did not survive and were withdrawn. Any statement about dollars lost to
fraud, and any statement of the form "caught 5 of 6", rest on a handful of fraud
events in a six month window. Rerun the simulation and those numbers move wildly. They
are illustrations, not measurements, and the repository now says so.

One claim got worse on closer inspection. Against an attacker who has completely taken
over a real vendor, including their genuine bank account, the earned-trust system
catches about a third of attacks where the untrusting version catches about two
thirds. Earning trust genuinely costs protection against that attacker. It was worth
knowing before telling anyone otherwise.

---

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

---

## Demo scripts

There are three demos, one per component. Each stands alone in about two minutes. Run
all three in order and it is about six, with a natural arc: the gate decides, the
ledger learns, the queue gets worked.

If you only have time for one, use the **Pause Engine**. It contains the most
surprising idea and needs the least setup.

---

### Demo 1: Viveka Gate, about 90 seconds

Open `viveka-gate/demo.html`. Four preset buttons across the top.

**Start on "BEC lookalike fraud."**

> An AI agent is 82 percent confident this $22,000 invoice is legitimate. Every
> guardrail on the market would send it. This one refuses, because fraud is
> engineered to defeat confidence and cannot defeat irreversibility.

Point at the R value, around 0.46, and the red ESCALATE verdict.

**Tap "Small routine payment."** It turns green.

> It is not just a blocker. A $22 expected loss does not justify a $60 human review,
> so it acts. Every option bids and the cheapest wins.

**Now drag the amount slider up slowly.** The execute bar grows until escalate
overtakes it.

> Same confidence the whole time. The verdict flips because the stakes crossed what
> that confidence can carry. That threshold is computed from recovery odds, not
> hand-tuned.

**Switch the bank to International without touching anything else.** It flips again.

> Same dollars, same confidence. An international wire under $50,000 is nearly
> unrecoverable, so the same judgment no longer carries it.

**Close on "Large legit wire."** Execute shows BLOCKED with a striped bar.

> Ninety-five percent confident, fully legitimate, still blocked. It is above the
> agent's delegated limit. Some decisions are not the agent's to make at any
> confidence. That is the line no probabilistic guardrail draws.

---

### Demo 2: Adhikara Ledger, about 2 minutes

Open `adhikara-ledger/adhikara_demo.html`. Work down the cards.

**Card 1, the comparison.**

> Your current process is on the left. It interrupts almost nobody and catches a
> minority of fraud. The middle is the gate with no learning: it works, but it
> interrupts 66 percent of payments and you would switch it off in a week. On the
> right is the same gate after a shadow period. Same protection, far less
> interruption. The learning is the difference between a demo and something you would
> actually run.

**Card 2, the timeline.**

> Month one it is cautious, because it has not earned an opinion about anybody yet. By
> month six it knows which of your vendors are boring and predictable and stops
> bothering you about them. Protection stays flat throughout. This is the answer when
> someone says it interrupts too much. Only at first.

**Card 3, the segment table.**

> Recurring domestic vendors, twelve hundred payments observed, earned almost full
> discretion. New international payees, thirty four payments, earned almost none. Not
> one global setting. Every vendor earns their own.

**Card 4, the attack test.** This is the one that wins the room.

> Here is where most demos stop. I kept going. What happens if the criminal simply
> pretends to be a vendor you trust? The first version collapsed, catching two percent.
> So trust now attaches to the vendor's actual bank account details and their normal
> invoice size. Change the account, which is exactly what this fraud does, and the
> trust vanishes. Two of three attacks fully closed. The third is not, and I will tell
> you why: if they have the real vendor, the real account, and a normal amount, nothing
> about that payment is wrong. That needs a phone call, not better software.

---

### Demo 3: Pause Engine, about 2 minutes

Open `pause-engine/pause_demo.html`. It opens on the correct ordering with three
reviews of capacity, showing $0 at risk.

**Set it up before clicking anything.**

> Ten payments are waiting and the analyst has time for three. The obvious move is to
> review the biggest, riskiest ones first.

**Click "Rank by stake."** Value at risk jumps to $7,269.

> There it is. The three largest payments went to the top, and $7,269 walked out the
> door.

**Point at the Why column on those top three rows.** Every one says *Redundant*.

> That is the whole error. Those payments are too large and unrecoverable to ever be
> released without review, so the system holds them whether or not anyone has time.
> The analyst spent the entire day confirming decisions that were already correct,
> while the small recoverable payments expired and got released.

**Click "Arrival order."** It stays at $7,269.

> And here is the damning part. Ranking by importance did no better than not ranking
> at all.

**Click back to "Rank by what review changes."** Zero.

> A review is only worth its cost when the default would be risky. Rank by that and
> the loss goes to zero. Fifteen random seeds, zero every time.

**If you have another thirty seconds, land the general principle.**

> This is emergency triage. The most severely injured patient is not always the one
> who benefits most from the next available surgeon. The value of an action is the
> difference it makes, not the size of the thing it acts on.

---

### Running all three together

The connective tissue between demos, said while switching tabs:

After demo 1: *"So that is the decision. But it escalates 66 percent of payments, which
nobody would tolerate. That is the next problem."*

After demo 2: *"Learning brings it to 44 percent, and protection holds. But 44 percent
of payments needing review still means about half a full-time analyst, and that is what
actually blocks adoption."*

Then demo 3 closes it: *"Which is fixed downstream, by making each review cheaper rather
than rarer. Eighteen point nine hours a week becomes five point one."*

---

### The question you will get, and the answer

**"Are these numbers real?"**

> The friction and analyst-time figures are means across twenty random simulations with
> standard deviations under two points. The dollar-loss figures are not, and I withdrew
> them: a realistic six-month window contains about four fraud events, so those numbers
> were reporting which invoices happened to be fraudulent. The repository says which
> claims survived that testing and which did not.

That answer is worth more than any of the numbers in it.

## How this was built

Architected and directed by Jayant Nath. Implementation written by Claude in a
session where every version was attacked before it was accepted.

That loop is why this repository contains a rejected design, a documented bug, and an
unsolved adversarial case rather than only results. The three findings that most
shaped the outcome all came from refusing an earlier answer: that deferral must be
priced rather than treated as a free safe harbour, that shadow mode is what makes
calibration labels uncensored, and that the first version's 17 percent friction
figure was unsafe and could not be published.
