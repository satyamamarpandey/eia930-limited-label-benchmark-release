# Scientific limitations

1. All positive labels are controlled injected faults, not confirmed real-world reporting errors; no detector was checked against confirmed real errors.
2. The annotation budgets (8, 32, 128 hours) are oracle-curated and class-balanced: half injected, half known non-injected hours. They favor the learned detectors and do not model realistic annotation cost.
3. The study does not estimate performance from inspecting B naturally selected operational hours.
4. The missingness-leakage correction (protocol v1.1) was made after test results had been examined; v1.0 is archived (`06_AUDIT/historical_evidence/`).
5. The labels-only baseline (D) was an ablation in the submitted paper and was promoted to a primary baseline in the camera-ready revision after its saved results were known; it was not pre-specified as primary. No new runs were made for the promotion.
6. Only four detector configurations are evaluated.
7. No contamination-aware PU loss, forecasting-residual detector or EIA-rule baseline was evaluated.
8. Five balancing authorities, one year and one variable give limited independent replication; with five clusters no significance claims are made.
9. Reproduction was demonstrated on one Windows machine, through the documented automated workflow (Claude Code running the documented commands); no second machine, operating system or independent party has reproduced it.
10. Nothing here establishes operational deployment performance or actual EIA-930 error rates.
