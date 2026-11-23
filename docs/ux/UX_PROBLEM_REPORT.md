# UX problem report

Severity: P0 blocks understanding or the first success; P1 causes confusion; P2 is friction; P3 is polish.

| # | Page / component | Problem | Why it confuses | Impact | Severity | Suggested improvement |
|---|---|---|---|---|---|---|
| 1 | Overview | Never says what ResolveAI is or who it is for. | The first signed-in screen is a dashboard of zeros. | User cannot explain the product. | P0 | Short welcome: what it does, for whom, and the three principles. |
| 2 | Overview | No guided first steps; "Demo workflow" is static and at the bottom. | It never shows progress, so it reads as decoration. | User does not know what to do first. | P0 | Getting-started checklist driven by the account's real data, at the top while incomplete. |
| 3 | Assistant | Suggested questions are declined on an empty knowledge base, with no warning. | The first try fails and looks broken. | Lost trust at the first interaction. | P0 | Notice when no document is ready, with a link to upload; label suggestions as examples that need matching documents. |
| 4 | Knowledge Base | "Scanned PDFs (OCR) are not supported" is false since OCR was added. | Misleading. | Users avoid a working feature. | P0 | Say scanned PDFs are read with OCR when it is enabled on the server. |
| 5 | Knowledge Base | "Indexing", "Chunks", and statuses are unexplained. | Jargon. | User does not know when a document can be used. | P1 | One-line explanation of what happens after upload and what each status means. |
| 6 | Assistant | "Grounded", "untrusted data" jargon; how answers work not explained. | A newcomer cannot tell this from ChatGPT. | Value proposition missed. | P1 | Plain description: answers only from your documents, each with a source to inspect, declined otherwise. |
| 7 | Incidents form | No guidance on what to include or not to paste. | Redaction covers secrets, tokens, emails and public IPs only. | Weak analyses, or sensitive data pasted. | P1 | "What helps" and "What not to paste" guidance in the form. |
| 8 | Analysis | "Hypotheses", "Read-only verification" need explanation. | Engineers know the words, newcomers do not know what is expected of them. | Possible cause mistaken for the answer, or checks mistaken for automation. | P1 | "Possible causes (suspected, not confirmed)"; "Check to run yourself (read-only, never run by ResolveAI)". |
| 9 | RCA | Why the draft is UNCONFIRMED is in small print. | Users may think the draft is final. | Unverified RCA shared. | P1 | Explain in the draft banner: it stays a draft until a person confirms the cause. |
| 10 | Evaluation / Ops | Promises evaluation; points to a repository path; no provider shown before the first call; terms unexplained. | Operator cannot tell which AI is configured or what the numbers mean. | Misread costs and health. | P1 | Describe the page in plain words; explain latency, tokens, cost and "Unknown"; say where provider details appear. |
| 11 | Login | "Credentials come from DEMO_USER_EMAIL..." developer text; demo email prefilled. | Reads as a developer tool. | Weak first impression. | P2 | Plain text; keep the demo hint short. |
| 12 | Overview | "Unknown" cost with the mock provider. | Looks like an error. | Doubt. | P2 | Hint: no price for this provider. |
| 13 | Analysis | `obs-1`, `hyp-1` ids appear without explanation. | Look like internal codes. | Minor. | P3 | Leave; they are referenced by "Supports". |
| 14 | Request traces | Many `GET /auth/me` rows. | Noise. | Minor. | P3 | Later: filter or group. |
