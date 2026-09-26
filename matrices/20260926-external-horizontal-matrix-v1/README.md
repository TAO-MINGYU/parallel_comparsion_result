# Complete external horizontal matrix v1

This matrix contains only the six external methods: PySR, Operon, DSR, AI-Feynman 2.0, gplearn, and TF4SR. MySR is deliberately excluded.

- 315 tabular tasks: Material A (75) + Material B (240)
- clean, 1%, 5%, and 10% output noise
- constrained-resource and capability-ceiling tracks
- 10 formal search seeds
- 1,890 Slurm work units, representing 151,200 method/task/condition/seed runs
- Slurm arrays: 33895--33900, one held array per external method

The arrays are held (`JobHeldUser`) because the six unified solver adapters are not all complete. Releasing them before adapters emit the common result contract would create import smoke records, not valid benchmark results. ODEBench remains a separate dynamic-system extension until external ODE adapters are validated.
