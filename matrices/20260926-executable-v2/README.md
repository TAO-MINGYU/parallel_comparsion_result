# Executable external comparison v2

**Scheduling amendment:** the arrays below were superseded by
[full-node pools](../20260926-external-fullnode-v3/README.md), jobs 34104/34105.
The original solver protocol and matrix remain unchanged.

Six real solvers replace the earlier held placeholder arrays: PySR, Operon,
DSR-PyTorch, AI-Feynman 2.0, gplearn and TF4SR. MySR is excluded.

- Tabular: 315 tasks × six methods × four noise variants × two finite resource
  tracks × ten fixed formal seeds = 151,200 slots.
- ODE: 63 systems × five trajectory conditions × six methods × two tracks ×
  ten seeds = 37,800 system-level slots, reported separately.
- Inapplicable combinations remain in the ledger with an explicit reason.
- Slurm replaces the old ODE condition-sized units with system/condition units.

The protocol and implementation live in
[Benchmark_mysr](https://github.com/TAO-MINGYU/Benchmark_mysr/blob/main/EXTERNAL_EXECUTION.md).
`submission.json` records exact code revision, node allocation, job IDs, raw
archive paths and validation evidence. Runtime bundle hashes fix the installed
environments used for node-local staging. Raw runs remain outside Git.

The unit/regression suite passed 18 tests. Node validation covers clean/noisy
fits, same-seed repeats, ODE components and actual native AI-Feynman candidate
recovery at timeout. These small validation cases are not performance rankings.
The complete matrix is a running campaign; submission is not completion.

The `environments/` directory preserves the six exported package specifications
and explicit Linux Conda locks; host-specific YAML prefixes were removed. The
source revision ledger distinguishes downloaded checkouts from installed wheel
versions recorded in those environment specifications.

## Active Slurm arrays

| Method | Tabular array | ODE array | Node |
|---|---:|---:|---|
| pysr | 33987 | 33988 | node1 |
| operon | 33940 | 33946 | node2 |
| dsr | 33941 | 33947 | node1 |
| ai_feynman_2 | 33942 | 33948 | node2 |
| gplearn | 33943 | 33949 | node1 |
| tf4sr | 33944 | 33950 | node2 |

The previous 33895–33906 held placeholders were cancelled. PySR arrays
33939/33945 were then superseded to exclude first-fit JIT from the search clock;
all their earlier records remain in the deployment archive. PySR uses commit
8f3d8ce; the other five methods retain a43fe88. Task membership, search seeds
and actual search budgets did not change.

Dependent job 33994 audits expected records after all arrays terminate and
writes the two completion summaries to the external deployment archive. Missing
records remain visible; its completion flag is not a performance claim.
