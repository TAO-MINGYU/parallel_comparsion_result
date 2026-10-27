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

## Completed B7 records and scope amendment (2026-10-27)

The archived v2 description above is historical. B7 uses the frozen
`common-cpu-train-scale-v2` protocol: each scalar ODE component receives its own
120/900-second search budget. It does not divide one system budget among its
components, and has no cross-method evaluation-count or per-fit memory cap.

`reports/20261027-external-b7/evidence/<method>.results.jsonl.gz` contains all
selected terminal raw-result metadata, original raw-result SHA256, effective
request-line SHA256, portable artifact locations, primary/observed scores,
source/resource provenance and outcome status. The actual installed package
versions and separately pinned upstream checkout identities are global metadata;
an installed wheel's commit is not invented from a checkout revision.

The amended selection replaces only the 12,100 prespecified formerly NA slots,
retaining every amended failure. Original B7 and extension summaries are both
published; this is not best-test-score selection across retries. The final
amended matrix includes 202,878 usable predictions, 9,642 applicable records
without a usable prediction, and 8,880 not-applicable records.

The derived table schema keeps registered/applicable/usable counts separate,
reports failures in threshold-attainment denominators, and retains both clean
latent/derivative and observed-target errors. ODE system metrics require every
component. See the report for pretrained-model, configuration-optimality,
resource-epoch and historical preservation limitations.
