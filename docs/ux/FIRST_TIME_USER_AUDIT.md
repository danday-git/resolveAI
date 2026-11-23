# First-time user audit

Method: a new account was registered on the running app (`/register`, mock provider, empty knowledge base) and every page was opened at 1440px and 390px. The same pages were then opened with the seeded demo account, which has 15 documents and one analyzed incident. Every score below was given before the changes in this pull request; the final section re-runs the test afterwards.

## 1. First impression (before)

| Question | Answer from the interface alone |
|---|---|
| What does ResolveAI do? | Only the login page says it: "Investigate incidents with evidence, not guesses." After sign-in the first heading is "Overview: Knowledge base health, recent incidents and the last 7 days of usage." Nothing on the signed-in screens says what the product is. |
| Clear in 5 to 10 seconds? | No. A new user sees zeros, `0/0`, and an estimated cost of "Unknown". |
| Target users? | Not stated anywhere. |
| Problem it solves? | Implied by "Incidents" and "Knowledge Base", never stated. |
| Different from a chatbot? | The login page lists "Grounded answers / Structured triage / Human-confirmed RCA", but these are gone after sign-in. |
| What to do first? | Two buttons ("Ask assistant", "New incident") are offered first, although both are weak without documents. The right first step, uploading a runbook, sits in a static "Demo workflow" strip at the bottom of the page (below the fold on a phone). |

## 2. Product understanding (before)

| Question | Answered by the UI? | Where, or what is missing |
|---|---|---|
| What is ResolveAI? | Partly | Login page only. |
| Who should use it? | No | Not stated. |
| What problems does it solve? | Partly | Page descriptions hint at it. |
| What must the user provide? | Partly | Knowledge Base says "Runbooks and SOPs"; the incident form gives no advice on what to paste. |
| Where do answers come from? | Yes | Assistant: "Grounded answers from your knowledge base." "Grounded" is jargon. |
| How does the Knowledge Base work? | Partly | "Indexing", "Chunks", and the Queued/Processing statuses are never explained. The drop zone says "Scanned PDFs (OCR) are not supported", which is wrong since OCR was added. |
| Assistant vs Incidents? | No | Never contrasted. |
| What is a suspected cause? | Partly | Analysis labels causes "Suspected" under a "Hypotheses" heading; what that means for the reader is not explained. |
| What does UNCONFIRMED mean? | Yes, small print | "A cause is only CONFIRMED by explicit reviewer acknowledgement." |
| Are commands executed? | Partly | "Read-only verification" label, plus a line at the end of the analysis. |
| Is an answer backed by evidence? | Yes | Numbered sources and an exact excerpt panel; "Insufficient evidence" badge when it declines. |
| What to do after a result? | Yes | "Reviewer decision" step and "Open the RCA". |

## 3. Journey walk-through (before)

1. **Discover.** The login page explains the idea. The signed-in Overview does not, and it shows no welcome for an empty account.
2. **Knowledge Base.** Upload is obvious. Why it is needed is one sentence in the empty state. What happens after upload, what "indexing" means, and when a document is usable are not explained, and the OCR sentence is false.
3. **Assistant.** The three suggested questions are about Nginx, connection refused and CPU. With an empty knowledge base each one is declined, and nothing warns the user beforehand. The citation flow itself is good once documents exist.
4. **Incident.** The form says secrets, tokens, emails and public IPs are redacted, but not what to include, and not that other data (customer names, internal hostnames) is kept. The analysis keeps observations, suspected causes and checks apart well; "Hypotheses", `obs-1` ids and "Read-only verification" need a short explanation.
5. **RCA.** The draft, UNCONFIRMED state, gates and export are clear once found; the reason for the unconfirmed state is in small print.
6. **Operations.** "Evaluation / Ops" shows no evaluation; it points to `evals/reports/`, a repository path. The provider and model appear only after calls exist, so a new user cannot tell what AI is configured. "Unknown" cost (mock provider has no price) and terms like p95 and tokens are not explained.

## 4. Information architecture

The five menu items follow the work (knowledge, ask, investigate, observe) and the page titles match the menu. Two problems: the Overview does not tell a new user the order to use them in, and "Evaluation / Ops" promises evaluation results that the page does not have. Assistant and Incidents are not linked to each other, which is acceptable because they answer different jobs, but the difference must be explained.

## 5. Scores (before)

| Category | Score | Evidence |
|---|---|---|
| First impression | 5/10 | Clean, but signed-in pages never say what the product is; zeros and "Unknown" first. |
| Product clarity | 5/10 | Value stated on the login page only. |
| Value proposition | 5/10 | Evidence-first idea is on the login page and in small print on Assistant and RCA. |
| Navigation clarity | 7/10 | Clear labels and icons; "Evaluation / Ops" is vague. |
| Ease of getting started | 4/10 | No guided order; suggested questions fail on an empty knowledge base. |
| Knowledge Base usability | 6/10 | Upload and preview work well; statuses unexplained; wrong OCR copy. |
| Assistant usability | 6/10 | Excellent citation inspection; no warning when there is nothing to search. |
| Incident investigation usability | 7/10 | Strong structure; form gives no guidance on content. |
| RCA workflow clarity | 7/10 | Explicit gates; reason for UNCONFIRMED in small print. |
| Trust and transparency | 7/10 | AI labels, sources, redaction counts, read-only checks; spread out and partly jargon. |
| Overall | 6/10 | Strong product once understood; a stranger needs help to get there. |

## 6. Final question (before)

No. A new user would understand that it is an incident tool, but not why it is different from a chatbot or what to do first, and the first question they try would be declined without explanation.

## 7. Re-test after the changes

See the "After" section in [UX_IMPLEMENTATION_PLAN.md](UX_IMPLEMENTATION_PLAN.md).
