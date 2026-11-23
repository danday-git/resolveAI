# Improved user journey

From first visit to a confirmed RCA, for an IT support engineer who has never seen ResolveAI.

1. **Sign in.** The login page states the promise: investigate incidents with evidence, not guesses, and lists the three principles.
2. **Overview, first visit.** A welcome explains what ResolveAI is, who it is for and how it differs from a chatbot. Below it, "Getting started" lists six steps; each step is ticked from the account's real data, never faked:
   1. Upload a runbook or SOP (done when the account has a document).
   2. Wait until it is ready (done when a document is ready).
   3. Ask a question and open its source (done when the account has a conversation).
   4. Record an incident (done when the account has an incident).
   5. Run an analysis (done when an incident has moved past "open").
   6. Review the RCA draft and confirm it yourself (not tracked; links to the incidents list).
3. **Knowledge Base.** The page says why documents are needed. After upload, the status legend explains Queued, Processing, Ready and Failed, and that "Ready" means the assistant can cite it.
4. **Assistant.** If nothing is ready, a notice says questions will be declined and links to the Knowledge Base. Otherwise the user asks, sees numbered sources, opens the exact passage, and learns that a question without supporting text is declined.
5. **Incident.** The form says what helps (symptoms, timeline, a log excerpt) and what not to paste. After creating it, the user runs the analysis.
6. **Analysis.** Observations quote the log; possible causes are marked suspected; each has a check to run yourself. "Reviewer decision" leads to the RCA.
7. **RCA.** The draft banner explains it stays UNCONFIRMED until a person confirms. The reviewer fills in the confirmed cause and evidence, ticks the acknowledgement, confirms, and exports Markdown.
8. **Ops.** The page explains latency, tokens and estimated cost, why cost can read "Unknown", and where the provider and model appear.
9. **Return visit.** With every tracked step done, the Overview shows the dashboard first and keeps a short "How ResolveAI works" reminder.
