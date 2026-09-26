# Corrected SRSD baseline calibration v2

The first v1 runner only searched `material-A`; SRSD is in `material-B`, so the affected v1 records are retained as runner configuration errors. v2 resolves both material roots and resubmits the 24 SRSD entries on node2.

Slurm array: `33871` on node2, indices 0--23. This remains calibration evidence (`formal_claim=false`), not a method ranking.
