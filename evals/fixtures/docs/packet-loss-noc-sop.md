# SOP: Packet loss between data centers (synthetic)

Version 1.3. Owner: NOC.

## Symptoms
Monitoring shows packet loss above 2 percent on the inter-DC link, replication lag grows, and users report slow file transfers.

## Read-only checks
1. Run mtr -rwc 100 dc2-core.example.net from a host in DC1 and note at which hop loss starts.
2. Check interface error counters on the edge router with show interfaces for CRC errors and drops.
3. Compare link utilization with the 80 percent capacity threshold in the NOC dashboard.

## Interpretation
Loss that starts at an intermediate hop but does not continue to the final hop is usually ICMP rate limiting, not real loss. Rising CRC errors indicate a physical layer problem such as a faulty optic or cable.

## Escalation
Contact the carrier only after collecting mtr output and interface counters. Packet loss above 5 percent for 10 minutes is a SEV2.
