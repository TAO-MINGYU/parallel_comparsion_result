# Full-node external campaign: current deployment

| Node | Slurm job | Allocated logical CPUs | Single-thread workunit slots |
|---|---:|---:|---:|
| node1 | 34104 | 512 | 512 |
| node2 | 34105 | 512 | 512 |

Summary job **34106** audits both original result roots after these jobs end.
The 189,000 registered matrix slots, task/seed/budget membership and original
solver releases are unchanged. Scheduler revision: `c83114f07b99a68461bed59120c76faadd019a2c`.
PySR still executes byte-identical `8f3d8ce` adapter code; other methods use
`a43fe88`. MySR remains excluded from this external campaign.

Each workunit and all solver descendants are pinned to one distinct OS logical
CPU, using both SMT siblings. Workers start at up to eight per second; admission
pauses below 96 GiB host MemAvailable. CPU allocation and slot occupancy are not
a promise of 100% instantaneous CPU activity: input/output, startup, memory
pressure and the queue tail can leave slots idle. Per-fit numerical threads,
wall limits and process-tree RSS enforcement remain unchanged.

Solver environments, the supervisor's unchanged Python/NumPy/psutil dependency
closure (36 packages), and original code releases are checksum-staged locally.
The supervisor imports in 0.105/0.110 seconds in the two-node probes. A separate
probe showed four shared log-file creations cost 10.86 seconds, so pool status,
events and console logs now originate on local disk. Status/events mirror to the
durable archive asynchronously about every ten seconds; completed console logs
are copied in the background. `allocation.json` records local log paths for
interruption recovery. Original per-run solver evidence remains at the original
durable result roots, not only in temporary directories.

The previous array attempt and two full-node startup attempts remain in v1/v2
archives. The last transition retained 6,687 result files, archived 63 interrupted
locations, and reverified all original 6,534 result-file hashes unchanged. These
counts include component/recovery records, not just matrix-level outcomes. The
interruption and checksum ledgers are provided here. No raw scientific results
or final combined MySR/external benchmark release are published by this amendment.

Live allocation, events, status and logs are under
`/data5/taomingyu_5/MySR_Benchmark/20260926-external-fullnode-v3/pools/`.
Raw results remain in `parallel_comparsion_result/runs/20260926-external-tabular-v2`
and `20260926-external-ode-v2`; completion summaries remain in the original
`20260926-external-deployment-v2` archive. Missing/failed work stays visible.

Validation: 21 automated tests, actual subprocess affinity isolation, two-node
supervisor import checks and live deployment inspection. The resource epoch is
`full-node-smt-v1`; earlier sparse-array results remain identifiable by job ID.
SMT contention and scheduling phases must be accounted for when comparing wall
budgets and matching later MySR runs. `formal_claim=false` remains unchanged.
