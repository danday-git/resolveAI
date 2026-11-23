# SOP: Database connection pool exhaustion (synthetic)

Version 1.0. Owner: Data platform team.

## Symptoms
Application logs show timeout acquiring connection from pool or remaining connection slots are reserved. Latency rises sharply while CPU on the database may stay normal.

## Read-only checks
1. Count active sessions per application with SELECT usename, application_name, state, count(*) FROM pg_stat_activity GROUP BY 1,2,3.
2. Look for sessions in the idle in transaction state, which hold connections without doing work.
3. Compare the application pool size multiplied by the number of replicas with the PostgreSQL max_connections setting.

## Interpretation
Many idle in transaction sessions usually indicate an application bug that does not commit or roll back. If pool size times replicas exceeds max_connections, new replicas will fail to connect.

## Escalation
Terminating database sessions requires approval from the data platform on-call engineer.
