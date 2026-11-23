# ADR 0001: Modular monolith with PostgreSQL + pgvector

Status: Accepted

## Context
The MVP needs document storage, metadata, vector search, incidents and metrics, run locally by one engineer with `docker compose up`.

## Decision
One FastAPI service with internal modules (`ingestion`, `retrieval`, `llm`, `incidents`, `rca`), one PostgreSQL 16 database with the pgvector extension, and FastAPI background tasks for ingestion.

## Consequences
- One database for relational data and vectors: owner filtering, cascades and transactions work in plain SQL.
- No queue or vector database to operate. Background tasks are lost on restart; documents stuck in `processing` must be re-uploaded. A worker queue is the upgrade path if ingestion volume grows.
- Module boundaries are kept so a service can be split out later without rewriting logic.
