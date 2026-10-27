# Reproducing this external-baseline report

The package has three distinct reproducibility levels. Report tables can be
recomputed entirely from the published per-fit records. Native search reruns
also require the exact numerical input archive, method sources/weights and six
separate environments. Large raw archives are retained externally, following
this repository's original storage policy; cloning this repository alone does
not supply every binary environment or complete native candidate frontier.

## 1. Verify and recompute the published report

From this report directory, use Python 3.11 and run:

```bash
python reproduction/frozen_benchmark/scripts/external/verify_report_bundle.py --root .
python reproduction/frozen_benchmark/scripts/external/build_report_tables.py \
  --evidence evidence --output /tmp/b7-recomputed-tables
```

The table builder uses the standard library. Compare every generated CSV, JSON
and deterministic gzip template with `tables/`. It checks all 221,400 selected
records, six-method case membership, identical paired data/budgets, failure
denominators and complete ODE component membership. It never trains a model.

To regenerate the figures, use the recorded plotting environment:

```bash
python -m pip install 'numpy==2.4.6' 'matplotlib==3.11.1'
python reproduction/frozen_benchmark/scripts/external/plot_report_tables.py \
  --tables /tmp/b7-recomputed-tables --output /tmp/b7-recomputed-figures
```

The SVG/PDF outputs have fixed identifiers and no current-time metadata.
The original 55 Benchmark tests and the additional report tests are included:

```bash
PYTHONPATH=reproduction/frozen_benchmark \
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 \
python -m pytest reproduction/frozen_benchmark/tests -q -p no:cacheprovider
```

Tests require the Benchmark test dependencies (`pytest`, `psutil`, NumPy,
SciPy, SymPy and jsonschema); consult the environment locks for the versions
used. Passing these tests is contract evidence, not proof that a rerun found
the same expression or that a method is superior.

## 2. Result schema and metric targets

`evidence/<method>.results.jsonl.gz` contains every selected terminal result:
the expression, native metadata, scores on both observed and clean targets,
resource records, source hashes, failure information and the original raw
result-file SHA256. Paths have portable root placeholders. These portable
files have their own hashes; their bytes must not be confused with the raw
result or original request hashes.

The exporter checks every selected raw result against the completed native
audit and its effective frozen request. It does not pretend to freshly hash
the multi-terabyte frontier store: expected frontier hashes and saved
prediction metadata come from the completed native audits. The original raw
results, full exposed candidate/frontier records and prediction arrays remain
in the retained artifact store.

Primary tabular robustness metrics use clean latent test targets when available;
black-box metrics use the unchanged observed test targets. ODE metrics use the
independent clean derivative targets. The original completed audit's generic
`test_nrmse` is an observed-target score. Do not mix it with clean-target
robustness figures. Invalid/no-model outcomes contribute zero attainment in
the all-applicable denominator. NA and conditional finite-error counts remain
explicit.

## 3. Obtain and verify the exact numerical inputs

The preserved input package is named `b7-frozen-inputs-20261027.tar.gz`.
Its verification receipt and input hashes identify all 1,845 scalar datasets
and 5,535 train/validation/test CSVs. The package layout is `data/...` plus
`INPUT_MANIFEST.json` and attribution records. Set `B7_ROOT` to the extracted
directory. Dataset-source commits and revisions are recorded in
`metadata/corpus-source-manifest.json` and the frozen catalog.

This repository does not automatically redistribute all third-party input
rows: the frozen catalog requires per-task license checks. Local storage
locations are supplied separately to the experiment owner. A public cold-start
search reproduction therefore requires obtaining the identified frozen input
package under the applicable source terms, or rebuilding from the pinned
sources and verifying every expected CSV checksum. This dependency is not
hidden by the availability of the smaller report metadata.

For a maintainer who has the original input tree, the included packager creates
the exact-byte preservation package without deleting or moving any original:

```bash
python reproduction/frozen_benchmark/scripts/external/package_frozen_inputs.py \
  --requests "$ORIGINAL_B7_REQUESTS" --b7-root "$ORIGINAL_B7_ROOT" \
  --output "$NEW_ARCHIVE" --notices "$SOURCE_ATTRIBUTIONS"
```

The packager checks every source CSV against its frozen request SHA256 and
independently streams every archived member back through SHA256. It rejects
unsafe member paths and refuses to overwrite an existing archive. Packaging
is preservation evidence, not an assertion of redistribution rights.

## 4. Rebuild the native execution environment

`environments/*.environment.yml` and `*.conda-linux-64.txt` record Python/Conda
and pip dependencies. Machine-local prefixes were removed; substitutions are
documented in `metadata/environment-lock-derivation.json`. Resolve
`${ENV_PREFIX}` to the new private prefix before using the PySR YAML variables.
Rebuild the six independent prefixes with the names expected by the runner:

```text
env_1_pysr, parallel_operon, parallel_dsr,
parallel_ai_feynman, parallel_gplearn, parallel_tf4sr
```

The actual installed distributions are enumerated in
`metadata/installed-versions.json`. An upstream checkout commit is not proof
that an installed wheel came from that commit. For PySR, retain Julia 1.10.3,
the Julia Project/Manifest under `environments/pysr-julia/`, and
SymbolicRegression.jl 2.0.0-beta.8. The frozen runner expects the Julia binary
under the private PySR prefix at `opt/julia-1.10.3/bin/julia` and its private
depot under `julia_depot/`; create that layout in the new prefix, not in a shared
existing environment.

Check out the exact commits in `metadata/upstream-source-lock.json`. Place
DSR under `$SOURCES_ROOT/dsr-pytorch` and TF4SR under `$SOURCES_ROOT/tf4sr`.
Retrieve the pinned TF4SR checkpoint and verify
`metadata/tf4sr-weight-identity.json`; do not use the current upstream default
weights without checking their hash. AI-Feynman's installed Fortran components
must be available; verify the source/version and executable paths recorded by
its environment. All methods run on CPU. The frozen runtime bundle hashes
identify the preserved binary environments; those large bundles are not
committed to this repository.

## 5. Replay one selected external fit

The original Benchmark source is vendored under `reproduction/frozen_benchmark`
with 44 original-file hashes in `metadata/frozen-source-sha256.json`.
Report tools/tests are additional files and are independently included in
the package-wide `SHA256SUMS`.

For the expanded-scope AI-Feynman/TF4SR requests, make a separate deployment
copy and apply the exact three-file scope patch:

```bash
cp -a reproduction/frozen_benchmark "$REPLAY_CODE"
patch -p1 -d "$REPLAY_CODE" < reproduction/applicability-extension.patch
```

The patch changes only registration gates and scope-provenance fields. It
retains TF4SR's six-input and positive-training-row requirements and changes no
search settings. Original B7 requests can also run with this code because the
new gate bypass requires the explicit amendment identifier.

Inside a one-CPU Slurm allocation with the appropriate hardware condition:

```bash
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1
export JULIA_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1 PYTHON_JULIACALL_THREADS=1
srun --ntasks=1 --cpus-per-task=1 --cpu-bind=threads \
  python "$REPLAY_CODE/scripts/external/replay_published_fit.py" \
  --code-root "$REPLAY_CODE" \
  --requests evidence/effective-requests.portable.jsonl.gz \
  --relative-output tabular/tf4sr/legacy-classic-keijzer_0/clean/constrained_resource/23654 \
  --b7-root "$B7_ROOT" --sources "$SOURCES_ROOT" --env-root "$ENV_ROOT" \
  --output-root "$NEW_RESULT_ROOT"
```

Use a fresh output directory outside the retained original input/result tree.
The wrapper validates the frozen protocol and expected input split hashes.
It enforces one-CPU affinity and requires the scope patch for amended fits.
It preserves the original 120/900-second scientific budgets and does not add
startup/scoring or memory caps. Do not set an extra Slurm wall/memory limit
unless the research protocol or the experiment owner explicitly requires it.

Native searches use wall-time budgets and can stop at different iteration
counts on different machines. Reproduction means the same documented inputs,
settings, resource condition and outcome accounting; bit-identical discovered
expressions or elapsed times are not guaranteed by a matching seed alone.

The frozen adapter's synchronous checkpoint collection/serialization/storage
inside the search loop also consumes supervised search time. The gplearn, DSR
and Operon checkpoint writers use a minimum10-second interval; this does not
make their storage cost identical. That overhead was not measured separately
or subtracted from the budget. Final post-search export/scoring is a different
stage. Do not infer equal algorithm-only compute from equal nominal wall budgets.

## 6. Prepare future MySR comparisons

`tables/mysr-run-template.jsonl.gz` contains unexecuted MySR request templates.
They include every scalar case and each required physical/SMT hardware
condition. Their condition-specific output roots are distinct. They do not
select MySR parameters and cannot be executed by the six-method external
worker. Freeze a future MySR adapter/version/configuration before its run.

Match the common data, seed, budget and hardware-condition keys. Keep invalid
and not-applicable outcomes, and distinguish learned/pretrained methods and
development-data reuse. The ODE comparison is derivative prediction with all
components required, not a trajectory-integration benchmark. No MySR
superiority, best-tuned leaderboard or publication-ready final comparison is
claimed by this external-only package.
