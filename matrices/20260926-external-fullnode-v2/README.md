**Superseded:** [current asynchronous-bookkeeping deployment](../20260926-external-fullnode-v3/README.md), jobs 34104/34105.

# Full-node concurrency amendment, 2026-09-26

The user requested both nodes' 1,024 logical CPUs. The former twelve arrays and
their summary dependency were superseded by two whole-node work pools:

| Node | Slurm job | Logical CPUs | Independent single-thread workunit slots |
|---|---:|---:|---:|
| node1 | 34101 | 512 | 512 |
| node2 | 34102 | 512 | 512 |

Summary job **34103** runs after both pools terminate and writes completion
summaries to the original deployment archive. A job ending is not proof that
all expected results exist; the summary reports failures and missing records.

All 189,000 original matrix slots, method assignments, immutable adapter
releases, per-run budgets, seeds and result directories are retained. The
scheduler commit is `bb1b37f`. Solver code remains
PySR `8f3d8ce` and other methods `a43fe88`. 6,644 existing result files (including
component/recovery records) were checksummed and retained; 96 interrupted
locations were archived before retry. This is not a count of completed matrix
slots. Original raw results have not been uploaded in this scheduling amendment.

Each workunit and its descendants are pinned to one distinct OS logical CPU.
The manager interleaves method/track queues, admits up to eight workunits per
second, and pauses new admissions below 96 GiB MemAvailable. A reserved CPU is
not proof of continuous busy time: staging, I/O, memory pressure and the queue
tail can reduce active work. Per-run thread counts and RSS/time limits remain
unchanged. Both hardware threads of each physical core now participate.

`config.json` fixes the pool inputs; `submission.json` records new and superseded
jobs. `interruption-audit.json` and `preservation-ledger.json` locate retained
attempts and checksums. Live per-node allocation, events, status and logs are in
`/data5/taomingyu_5/MySR_Benchmark/20260926-external-fullnode-v2/pools/`.
The scheduler passed 21 tests, including actual subprocess affinity/isolation.

The resource epoch is **full-node-smt-v1**, distinct from the original sparse
arrays. Low-concurrency results remain identifiable by original job IDs; SMT
contention affects wall-time-limited work and must be addressed when matching
MySR and interpreting efficiency. `formal_claim=false` remains unchanged. No
final combined MySR/external result release or method ranking is made here.

## Local supervisor correction

The first full-node jobs 34096/34097 stalled on shared-filesystem imports in the
supervisor environment. They were stopped and retained in the v1 audit. This
corrected deployment stages the original Python/NumPy/psutil dependency closure
(36 packages, 328 MiB archive) and byte-identical original adapter releases on
node-local disk. No package was upgraded. Node probes verified NumPy 2.4.6 and
psutil 7.2.2 importing in 0.105 seconds on node1 and 0.110 seconds on node2.
All original 6,534 result-file hashes remained unchanged after the first attempt.
The additional partial attempts and 6,644 retained results are indexed here.
Supervisor package versions and bundle hashes accompany this amendment.
