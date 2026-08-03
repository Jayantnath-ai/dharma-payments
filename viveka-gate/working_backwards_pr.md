# Working Backwards press release (interview artifact, internal draft format)

FOR RELEASE, [future date]

## Viveka Gate cuts catastrophic AI-agent payment losses in half without slowing
## routine business

Businesses deploying AI agents for accounts payable report a persistent dilemma: agents
confident enough to be useful are confident enough to be fooled. Business email
compromise, a $2.9B/year reported-loss category, is engineered to maximize an
agent's certainty while redirecting funds to unrecoverable accounts.

Viveka Gate resolves the dilemma by changing what the gate measures. Instead of asking
"how confident is the agent?", it computes, per transaction, "can this be undone?" , 
using recovery mechanics calibrated to FBI Financial Fraud Kill Chain statistics, and
runs a priced competition between executing, probing with a reversible test
transaction, and escalating to a human whose time and error rate are honestly costed.

In benchmark testing on invoice streams with adversarial BEC fraud, Viveka Gate
reduced unrecovered fraudulent losses by approximately 50% versus best-practice
confidence thresholds at equivalent operational friction, and maintained its advantage
when reviewer accuracy degraded.

"Fraud can fake legitimacy; it cannot fake reversibility," said [founder]. "We stopped
asking the agent how it feels and started asking the transaction what it is."

Customer FAQ (excerpt):
Q: Will this slow down my payments? A: 80%+ of routine payments below risk thresholds
execute with zero added latency; the gate's friction concentrates on transactions
whose loss, if wrong, could not be recovered.
Q: What does it need to integrate? A: Transaction metadata, payee history, and your
recall/dispute procedures, no model retraining.
