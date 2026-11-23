# SOP: Employee VPN connection problems (synthetic)

Version 2.3. Owner: IT support.

## First response for L1 support
1. Ask the user for the exact error message and the time it occurred.
2. Confirm the user can reach the internet without the VPN.
3. Check whether the user's account is locked in the identity portal.
4. Confirm the VPN client version is 5.2 or newer; older clients are blocked since the March security update.

## Common errors
Error 809 usually means a local firewall or hotel network blocks the VPN ports. Error AUTH_FAILED means the password or the MFA code was rejected.

## Escalation
If more than five users report VPN failures within 15 minutes, open a SEV2 incident and page the network on-call engineer.
