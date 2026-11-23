# SOP: Sustained high CPU on application servers (synthetic)

Version 1.1. Owner: Platform team.

## Symptoms
CPU usage above 90 percent for more than 10 minutes, rising request latency, and load average above the number of cores.

## Read-only checks
1. Identify the top processes with top -b -n 1 | head -20.
2. Check whether CPU time is user, system, or iowait; high iowait points to storage rather than computation.
3. Compare the start of the CPU increase with the latest deployment time in the release log.
4. Check request rate in the metrics dashboard to see whether traffic increased.

## Interpretation
High CPU that starts right after a deployment suggests a regression in the new release. High CPU that tracks request rate suggests load rather than a defect.

## Escalation
Rolling back a release requires approval from the incident lead.
