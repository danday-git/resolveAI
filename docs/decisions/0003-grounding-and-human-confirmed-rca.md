# ADR 0003: Server-side citation validation and human-confirmed RCA

Status: Accepted

## Context
The main risk of an operational assistant is a fluent, wrong answer that an engineer acts on.

## Decision
- The model must return citations as `{chunk_id, quote}`. The server keeps only citations whose chunk was retrieved for this request and whose quote appears in the stored chunk text (whitespace/case-normalized, minimum length). An answer with no surviving citations becomes an abstention.
- When retrieval returns no chunk above the similarity threshold, the API abstains without calling the LLM.
- Analysis hypotheses are always `suspected`. RCA reports start `UNCONFIRMED` with an empty confirmed cause; only an explicit reviewer acknowledgement can set `CONFIRMED`, and any later edit resets it.

## Consequences
Some correct answers are suppressed when the model paraphrases instead of quoting. We accept lower answer rate for higher trust; abstention accuracy and citation validity are tracked in evals.
