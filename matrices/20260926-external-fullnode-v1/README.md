# Full-node concurrency amendment, 2026-09-26

The user requested both nodes' 1,024 logical CPUs. The former twelve arrays and
their summary dependency were superseded by two whole-node work pools:

| Node | Slurm job | Logical CPUs | Independent single-thread workunit slots |
|---|---:|---:|---:|
| node1 | 34096 | 512 | 512 |
| node2 | 34097 | 512 | 512 |

Summary job **34098** runs after both pools terminate and writes completion
summaries to the original deployment archive. A job ending is not proof that
all expected results exist; the summary reports failures and missing records.

All 189,000 original matrix slots, method assignments, immutable adapter
releases, per-run budgets, seeds and result directories are retained. The
scheduler commit is `01d74a8196ed09592a0e90abbb9642e9c3ff1d99`. Solver code remains
PySR `8f3d8ce` and other methods `a43fe88`. 6,534 existing result files (including
component/recovery records) were checksummed and retained; 29 interrupted
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
`/data5/taomingyu_5/MySR_Benchmark/20260926-external-fullnode-v1/pools/`.
The scheduler passed 21 tests, including actual subprocess affinity/isolation.

The resource epoch is **full-node-smt-v1**, distinct from the original sparse
arrays. Low-concurrency results remain identifiable by original job IDs; SMT
contention affects wall-time-limited work and must be addressed when matching
MySR and interpreting efficiency. `formal_claim=false` remains unchanged. No
final combined MySR/external result release or method ranking is made here.
