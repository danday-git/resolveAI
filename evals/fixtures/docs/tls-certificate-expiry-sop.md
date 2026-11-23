# SOP: TLS certificate expiry (synthetic)

Version 1.2. Owner: Security engineering.

## Symptoms
Clients report certificate has expired, browsers show NET::ERR_CERT_DATE_INVALID, and API clients fail with certificate verify failed.

## Read-only checks
1. Read the served certificate dates with openssl s_client -connect portal.example.com:443 -servername portal.example.com and inspect notAfter.
2. Confirm the full chain is served, because a missing intermediate certificate also causes verify failed errors.
3. Check the certificate inventory dashboard for the renewal owner.

## Policy
Certificates must be renewed at least 14 days before expiry. Automated renewal alerts fire 30 days before expiry.

## Escalation
Installing a new certificate is a change and requires a change request approved by security engineering.
