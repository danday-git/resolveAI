# SOP: DNS resolution failures (synthetic)

Version 1.4. Owner: Network operations.

## Symptoms
Applications log Name or service not known, NXDOMAIN, or SERVFAIL when calling an internal hostname. Users may see intermittent failures if only one resolver is broken.

## Read-only checks
1. Inspect the resolver configuration in /etc/resolv.conf to see which nameservers are in use.
2. Query each internal resolver directly with dig @10.0.0.53 api.internal.example and compare the answers.
3. Check the TTL of the record; a recently changed record may still be cached for up to the TTL value.
4. Compare results from two different hosts to rule out a single misconfigured client.

## Interpretation
SERVFAIL from only one resolver points to that resolver, not to the record. NXDOMAIN from all resolvers suggests the record was deleted or the zone was not published.

## Escalation
Changes to internal DNS zones are made only by the network operations team through a change request.
