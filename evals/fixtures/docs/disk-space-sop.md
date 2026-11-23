# SOP: Disk space exhaustion on Linux hosts (synthetic)

Version 2.0. Owner: Infrastructure team.

## Symptoms
Services fail with No space left on device, databases stop accepting writes, and log rotation fails.

## Read-only checks
1. Show filesystem usage with df -h and identify filesystems above 90 percent usage.
2. Check inode exhaustion with df -i, because a filesystem can be full of inodes while bytes remain free.
3. Find the largest directories with du -xh --max-depth=1 /var | sort -h.
4. Look for deleted files still held open by a process with lsof +L1.

## Thresholds
The monitoring warning threshold is 80 percent disk usage and the critical threshold is 90 percent disk usage.

## Escalation
Deleting files or truncating logs on production hosts requires approval from the service owner. Never delete database files to free space.
