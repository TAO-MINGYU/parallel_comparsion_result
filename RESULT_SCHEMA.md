# Result record contract

Every method/task/seed/resource record must contain:

```text
run_id, benchmark_id, corpus_digest, method_id, method_commit, environment_prefix,
task_id, material_id, noise_variant, resource_track, search_seed,
selected_expression, full_frontier, train_score, validation_score, test_score,
complexity, runtime, cpu_time, peak_memory, evaluations, failure_status,
hostname, slurm_job_id, slurm_nodelist
```

`failure_status` is one of `success`, `timeout`, `memory_limit`, `crash`,
`invalid_output`, or `not_applicable`.

## Executable external runs (v2)

The registered replacement campaign contains 151,200 tabular slots and 37,800
ODE system slots. It excludes MySR. Actual runs retain `result.json`, immutable
`request.json`, stdout/stderr, available native frontier and test predictions.

- `status` records detailed execution outcomes; `failure_status` maps them to
  the common success/timeout/memory/crash/invalid/not-applicable contract.
- Unknown evaluation counts are null with `evaluation_semantics`; zero is not
  substituted for unavailable measurements.
- AI-Feynman may retain a scored Pareto checkpoint after `search_timeout`; this
  remains a timeout and links to `recovery/result.json`.
- Native complexity and evaluation definitions differ across methods. These
  records are not an identical-search-space ranking.
- ODE results aggregate component runs under one system budget and evaluate
  clean held-out derivative prediction, not integrated trajectory recovery.
- `formal_claim=false` remains until the completed campaign and its scorer,
  applicability and pretraining/provenance limits have been reviewed.

Use `scripts/summarize_external_runs.py` with the executable manifest and raw
output root to audit all expected slots. Missing files are counted as missing;
completed failures are retained and never reclassified as successful fits.
