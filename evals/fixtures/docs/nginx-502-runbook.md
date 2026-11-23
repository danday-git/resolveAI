# Runbook: Nginx 502 Bad Gateway (synthetic)

Version 3.1. Owner: Platform team. Synthetic document for the ResolveAI demo.

## Meaning
A 502 Bad Gateway from Nginx means the reverse proxy could not get a valid response from the upstream application. A 502 alone does not identify the cause; the fault can be the upstream process, an upstream port mismatch, DNS, a firewall rule, or application health.

## Log signatures
The error log line connect() failed (111: Connection refused) while connecting to upstream means nothing is listening on the upstream address and port.
The error upstream timed out (110: Connection timed out) means the upstream accepted the connection but did not respond in time.
The error no live upstreams means every server in the upstream block is marked as failed.

## Read-only checks
1. Confirm the configured upstream address in the Nginx site configuration, for example proxy_pass http://127.0.0.1:3000.
2. Check whether a process is listening on the upstream port with ss -ltnp | grep 3000.
3. Check the backend service state with systemctl status app-backend.
4. Request the backend health endpoint directly with curl -sS http://127.0.0.1:3000/health.

## Escalation
Restarting the backend service is a change and requires approval from the on-call incident lead. Do not restart services automatically.
