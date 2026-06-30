#!/bin/bash
# Best-effort graceful ClickHouse stop on VM shutdown to avoid truncating parts
# mid-flush (the corruption mode the compose stack guards with stop_grace_period: 5m).
#
# CAVEAT: GCE shutdown scripts get a bounded window (~90s on a normal stop), so a
# very large flush may not finish. `scheduling.on_host_maintenance = MIGRATE` avoids
# SIGTERM on host maintenance (the common case). For a guaranteed multi-minute grace,
# run ClickHouse on a GKE StatefulSet with terminationGracePeriodSeconds = 300.
docker stop -t 90 clickhouse-server || true
