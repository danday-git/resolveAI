# Product clarity recommendations

## One sentence

> ResolveAI helps support, NOC and infrastructure engineers investigate incidents using their own runbooks: every answer shows its source, possible causes stay separate from facts, and a person confirms the root cause.

Use it on the signed-in Overview, not only on the login page.

## Three principles, in the product's own words

| Principle | What the user sees |
|---|---|
| Evidence first | The assistant answers only from your documents, shows the exact passage for each claim, and says "Insufficient evidence" instead of guessing. |
| Possible causes are not facts | An analysis lists what the log shows (observations) apart from what might explain it (possible causes) and the read-only checks that would tell them apart. ResolveAI never runs a command. |
| A person confirms | An RCA stays a draft, marked UNCONFIRMED, until a reviewer writes the confirmed cause and its evidence and signs off. |

## How it differs from a chatbot

A general chatbot answers from its training data and sounds sure either way. ResolveAI only answers from what you uploaded, links each claim to a passage you can open, declines when the passage is missing, and redacts secrets, tokens, emails and public IPs from logs before a model sees them.

## Where to say it

- **Overview:** welcome with the sentence and the three principles, plus a getting-started checklist driven by the account's data. It shrinks to the checklist link once the steps are done.
- **Each page description:** what the page is for, in plain words, with the term it introduces explained in place.
- **Empty states:** what the page is for, what to do, and what happens next.
- **At the moment of doubt:** next to "Possible causes", "Check to run yourself", "UNCONFIRMED", "Unknown" cost, rather than in documentation.

## Words to use

| Instead of | Use |
|---|---|
| Grounded answers | Answers from your documents, with sources |
| Indexing | Preparing for search (splitting into passages the assistant can cite) |
| Hypotheses | Possible causes (suspected, not confirmed) |
| Read-only verification | Check to run yourself (read-only; ResolveAI never runs it) |
| Treated as untrusted data | Instructions inside documents and logs are ignored |
| Demo workflow | Getting started |
