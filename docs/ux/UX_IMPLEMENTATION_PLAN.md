# UX implementation plan

Numbers refer to [UX_PROBLEM_REPORT.md](UX_PROBLEM_REPORT.md). Nothing here changes an API, the database, authentication or the RCA rules.

## P0: critical (done in this pull request)

- **Welcome on the Overview (1).** What ResolveAI is, who it is for, the three principles.
- **Getting-started checklist (2).** Six steps, ticked from the account's documents, conversations and incidents. Step 6 (RCA review) is not tracked and says so.
- **Empty knowledge base notice on the Assistant (3).** Shown while no document is ready; links to the Knowledge Base. Suggestions are labelled as examples.
- **Correct OCR copy (4).**

## P1: important (done in this pull request)

- Knowledge Base: what happens after upload and what each status means (5).
- Assistant description in plain words (6).
- Incident form: what helps and what not to paste (7).
- Analysis: "Possible causes" and "Check to run yourself" labels with explanations (8).
- RCA: draft banner explains UNCONFIRMED (9).
- Ops page: plain description, term hints, "Unknown" cost explained, provider note (10).

## P2: quality of life

- Login copy without environment variable names (11). Done.
- Overview cost hint when the price is unknown (12). Done.
- Remember a dismissed welcome per browser. Not done: the welcome already shrinks once the checklist is complete.

## P3: optional polish

- Explain `obs-` and `hyp-` ids (13).
- Group or filter `/auth/me` rows in request traces (14).
- A sample incident a new user can load on request, clearly labelled as sample data.

## After: re-test as a new user

Filled in after the changes; see the bottom of this file.

### Result

The same new-account walk-through was repeated after the changes, with a fresh account and the mock provider: upload `nginx-502-runbook.md`, ask the first example question, record a 502 incident with a log excerpt, analyze it and generate the RCA draft. The checklist went from 5 steps left to "All tracked steps are done" one step at a time, each tick caused by the account's real data. The 36-step browser regression test also passes.

| Acceptance check | Result | Where the user learns it |
|---|---|---|
| Explain what ResolveAI does | Pass | Overview description and the three principles |
| Why it differs from a chatbot | Pass | "Evidence first" and the Assistant description |
| Upload SOPs and runbooks | Pass | Checklist step 1, Knowledge Base drop zone |
| Ask and inspect the evidence | Pass | Numbered sources open the exact passage |
| Know a question will be declined without documents | Pass | "Nothing to search yet" notice |
| Submit an incident | Pass | "What helps" and "What not to paste" |
| Observations vs suspected causes | Pass | "Possible causes: suspected, not confirmed" |
| Checks are read-only | Pass | "Checks to run yourself (read-only; ResolveAI never runs them)" |
| Why an RCA is unconfirmed, and how to confirm | Pass | RCA banner and the review panel gates |
| Purpose of Evaluation / Ops | Partial | The page now explains its numbers, but its name still promises evaluation results it does not show |

### Scores (after)

| Category | Before | After | Why |
|---|---|---|---|
| First impression | 5 | 8 | Signed-in Overview says what it is and what to do first. |
| Product clarity | 5 | 8 | One sentence plus three principles. |
| Value proposition | 5 | 8 | Difference from a chatbot is stated where work starts. |
| Navigation clarity | 7 | 7 | Unchanged; "Evaluation / Ops" name remains. |
| Ease of getting started | 4 | 8 | Data-driven checklist; empty knowledge base warned about. |
| Knowledge Base usability | 6 | 8 | What happens after upload; statuses explained; OCR copy correct. |
| Assistant usability | 6 | 8 | Plain description; examples labelled. |
| Incident investigation usability | 7 | 8 | Input guidance; clearer cause and check labels. |
| RCA workflow clarity | 7 | 8 | Reason for UNCONFIRMED stated in the draft. |
| Trust and transparency | 7 | 8 | Same safeguards, explained in plain words. |
| Overall | 6 | 8 | |

### Final question

Mostly yes. A new user can now say what ResolveAI is, why it is safer than a chatbot, and follow the checklist to a reviewed RCA without help. Two gaps remain: the "Evaluation / Ops" name, and step 6 (confirming the RCA) is a manual step the checklist cannot verify.
