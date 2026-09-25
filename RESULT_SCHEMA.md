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
