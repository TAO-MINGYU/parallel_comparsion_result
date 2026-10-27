# MySR Parallel Comparison Results

This public repository is the result index and paper-facing link for horizontal symbolic-regression comparisons. Each run directory records the benchmark commit, corpus manifest/hash, method source commits, environment locks, Slurm allocation, seeds, raw metrics, failure records, and reviewed summaries.

Large raw artifacts and complete third-party corpus files remain in the external versioned archive; this repository stores their checksums and reproducibility metadata. No result is a formal claim until the run is marked `reviewed` and tied to a frozen protocol commit.

## Completed external baseline report

The [2026-10-27 B7 report](reports/20261027-external-b7/README.md) contains the
completed six-method baseline and the explicitly documented applicability
extension: 221,400 terminal scalar records, 37,800 complete ODE system records,
portable per-fit result metadata, observed/clean target scores, fixed method
settings, environment/source/weight locks, and reproducible CSV/SVG/PDF outputs.
It is an external-only, fixed-configuration comparison preparation package;
MySR results and a final superiority claim are absent. Failed and unsupported
outcomes are retained. Physical-core and SMT execution conditions remain
distinct in the future MySR templates.

See [reproduction instructions](reports/20261027-external-b7/REPRODUCE.md) for
the exact scope of public report recomputation and externally retained native
input/frontier/runtime archives. Historical matrices below retain their original
protocols and must not be mixed into the B7 score table.
