# External campaign continuation: no default scheduler caps

The previous full-node jobs `34104` and `34105` retain their original 48-hour
scheduler cap. They are not modified because Slurm denied in-place TimeLimit
updates. Continuation jobs were submitted with **no batch time limit**:

| Node | Continuation job | CPU allocation | Dependency |
|---|---:|---:|---|
| node1 | 34118 | 512 logical CPUs | afterany:34104,34105 |
| node2 | 34119 | 512 logical CPUs | afterany:34104,34105 |
| summary | 34120 | 1 CPU | afterany:34118,34119 |

The continuation uses scheduler commit `d1f043293b0cef200bde8f8ca1d6dee780300978`.
It reuses successful records and removes only stale `running.lock` files left by
terminated incomplete attempts. The old attempt directory, result files and
failure logs remain preserved.

## Failure handling

The explicit benchmark search budgets remain unchanged: constrained resource is
20,000 evaluations/120 seconds/8 GiB, and capability ceiling is 500,000
evaluations/900 seconds/32 GiB. Those limits define the registered benchmark and
remain recorded as `search_timeout` or `memory_limit` outcomes; they are not
silently converted to unlimited searches.

The continuation retries only `startup_timeout` and `scoring_timeout`, because
those were supervisor convenience caps rather than scientific benchmark budgets.
Startup and scoring now have no default wall-time cap. Each retry archives the
prior result and logs under the same run's `attempts/` directory before writing a
replacement. `solver_error`, `incomplete_system`, invalid output, native search
timeouts and not-applicable outcomes are retained for separate diagnosis; they
are not blindly retried as if they were infrastructure failures.

The parent pool has no scheduler time or memory cap. The per-fit RSS cap remains
only where explicitly present in the benchmark resource track. Node admission
still pauses below 96 GiB available memory as an operational safety check; this
is not a job memory limit. `formal_claim=false` remains unchanged.

Raw results remain in the existing tabular and ODE result roots. The continuation
anchor records the deployment archive rather than rescanning the large NFS result
tree. Future completion summaries must be checked for missing records and retry
outcomes before any comparison claim.
