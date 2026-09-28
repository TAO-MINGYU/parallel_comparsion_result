# b3: complete b1 after non-protocol failure audit

b1 jobs `34104` and `34105` reached their scheduler time cap and ended as
`TIMEOUT`. b2 jobs `34118`, `34119`, and `34120` were withdrawn before b3; b2
was not used as a required scientific input.

| Node | b3 job | CPU allocation | Scheduler time/memory limit |
|---|---:|---:|---|
| node1 | 34189 | 448 logical CPUs | unlimited |
| node2 | 34190 | 512 logical CPUs | unlimited |
| summary | 34191 | 1 CPU | unlimited |

Node1 has an unrelated 64-CPU allocation, so b3 requests its available 448
CPUs. Node2 is idle and uses all 512. Each workunit still launches one
single-thread solver process. This capacity choice does not change the formal
request, seed, method, split or per-run benchmark budget.

## b1 audit and recovery rule

The audit is in `b1-failure-audit.json`. It identifies the result status by b1
job ID, including nested ODE component records. b3 replays the complete original
workunit list against the same result roots:

- existing successful and protocol-defined outcomes are reused;
- missing records are generated;
- `startup_timeout` and `scoring_timeout` are archived and retried without the
  old supervisor convenience limits;
- explicit benchmark search/evaluation/RSS outcomes remain unchanged;
- `solver_error`, invalid output, incomplete ODE systems and not-applicable
  cases remain recorded for diagnosis rather than being blindly rerun.

The formal resource tracks remain 20,000 evaluations/120 seconds/8 GiB and
500,000 evaluations/900 seconds/32 GiB. The scheduler itself has no time or
memory cap. The node's 96 GiB admission threshold is an operational pause, not
a job memory limit.

The b1 output roots and prior attempt archives are preserved. b3 writes retry
attempts under each run's `attempts/` directory. Summary job 34191 is the only
summary writer for b3. `formal_claim=false` remains unchanged.
