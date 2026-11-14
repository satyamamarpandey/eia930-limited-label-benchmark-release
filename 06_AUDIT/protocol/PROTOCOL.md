# Pre-registered experimental protocol (local pre-registration)

* Protocol version: 1.0
* Machine-readable twin: `03_CODE/configs/protocol.yaml` (its SHA-256 is recorded in `PROTOCOL_FREEZE.json` and in every run manifest).
* Status at freeze: the source audit (Phase 1) and a **validation-only** development run (`04_RESULTS/dev`) had been executed. No test-period (Sep–Dec 2024) detection metric had been computed. The development run evaluates only on validation hours (`eval_split = val`).
* This is a local, self-recorded pre-registration (not registered with a third party). Its integrity evidence is the timestamped freeze file and the config hash embedded in all final outputs.

## 1. Research question and hypotheses

RQ: How well do detector families identify *controlled anomalies injected into observed EIA-930 hourly demand records* when verified labels are scarce, the unlabeled background is contaminated, and observations are missing?

Hypotheses (directional expectations, stated before test evaluation; each is tested descriptively with paired, authority-clustered uncertainty, not as a significance claim). Transparency note: H2 and H4 were written after viewing validation-period (Jul–Aug) development metrics, so they are informed by validation data and are confirmatory only with respect to the held-out test period.

* H1 (label budget): AP of the budgeted PU logistic detector increases with the label budget (8 < 32 < 128 verified hour labels).
* H2 (supervision vs. none): At 128 labels the PU detector exceeds the robust seasonal statistical detector in pooled AP; at 8 labels it does not.
* H3 (missingness): Background missingness (5%, 15%; random and block) reduces AP for all detectors relative to 0%, with larger losses at 15%.
* H4 (fault family): Ranking differs by fault family: point spikes favour residual statistics; flatlines favour learned detectors using a staleness feature; level shift, drift and timing errors at the declared severities remain hard for all methods (AP near prevalence for low severity).
* H5 (authority heterogeneity): Method rankings are not identical across the five authorities.

## 2. Data

* Inputs: the two EIA-930 BALANCE 2024 files (hashes in `01_SOURCE_AUDIT/SHA256SUMS.txt`).
* Authorities: CISO, ERCO, NYIS, PJM, SWPP (codes verified in files).
* Variable: reported `Demand (MW)`. Not used as detector inputs: demand forecast, net generation, interchange, EIA imputed/adjusted columns.
* Index: hour-ending UTC. Inclusion/exclusion rules: see `protocol.yaml` and `01_SOURCE_AUDIT/data_quality_report.md` (blank and non-positive values are naturally invalid, never zero-filled, never scored, never injected; extreme positive values retained).
* Natural-suspect audit flag (defined after the validation-only development run revealed natural repeats in SWPP; defined before any test evaluation): hours inside runs of >= 3 identical consecutive reported values (repeats after the first) and isolated reversals with |Δlog x| > 0.2 in both directions. Used only for a sensitivity analysis that removes such unlabeled hours from the negatives; the primary analysis keeps them as negatives.

## 3. Chronological partitions (hour-ending UTC, inclusive)

| Split | Bounds | Use |
|---|---|---|
| Train | 2024-01-01 01:00 – 2024-07-01 00:00 (first 336 h of each series = feature warm-up, not fitted) | fitting, imputation medians, scaling, robust centre/scale, label sampling |
| Validation | 2024-07-01 01:00 – 2024-09-01 00:00 | label-free threshold selection; (secondary regime only) hyperparameter selection |
| Test | 2024-09-01 01:00 – end of 2024 local year | held-out evaluation only |

Features are causal; test-hour features may use earlier (validation) observations, which would be available at detection time. No statistic of the test period is used for fitting, imputation, scaling, tuning or thresholds.

## 4. Synthetic fault injection

Five families (definitions in `gridbench/inject.py`): spike (1 h, ±5/10/20%), level shift (6–12 h, ±3/6/12%), drift (12–24 h linear ramp to ±5/10/20%), flatline (stale repeat of previous value for 3–4 / 6–8 / 12–16 h), timing error (6–12 h window displaced by ±1/2/3 h). Severity tiers low/medium/high cycle within family. Events per family: train 6, validation 2, test 3 (test therefore has one event per family per tier per authority-seed). Events are non-overlapping (>= 24 h apart), >= 48 h from split boundaries, only on hours whose window and source hours are naturally valid. An hour is labeled positive iff its injected value differs from the reported value. The full ground-truth record is written to `04_RESULTS/final/raw/injection_ground_truth.csv`.

## 5. Missingness (nuisance)

Conditions: none; MCAR 5%; MCAR 15%; contiguous blocks (3–12 h) 5%; blocks 15%. Rate = exact fraction of naturally valid hours, applied in all splits. Masked hours are not scored. Natural missingness is retained in all conditions. Missingness is a nuisance, not a detection target.

**v1.1 amendment (post-hoc, see `PROTOCOL_CHANGES.md`).** v1.0 excluded injected event windows from nuisance masking. That made the missingness indicators predictive of the label. Since v1.1, masks are drawn independently of the injections, and masked injected hours are unscored.

## 6. Detectors

* A — Robust seasonal statistic: max of robust z-scores (train median/MAD) of (i) log demand minus median of the same hour on the previous 7 days, (ii) hourly log change minus the median change at that hour on the previous 7 days.
* B — Isolation Forest (scikit-learn), 200 trees, max_samples 256, all 12 causal features, fit on training rows; score = −score_samples.
* C — PU logistic regression (L2, C = 1) on the same 12 features: verified positives and verified normals from the label budget, plus all other training hours as weak (assumed) negatives with 50% of the negative-side weight.

Feature set (all causal, log-scale): seasonal residual, weekly residual, profile-adjusted hourly change, hourly change, 24 h volatility, stale-run length, hour-of-day sin/cos, weekend flag, three missingness indicators.

## 7. Label budget definition

Budget B ∈ {8, 32, 128} = total number of **expert-verified hour labels** per authority and seed, all drawn from the training period: B/2 verified anomalous hours (spread round-robin over randomly ordered training events) and B/2 verified normal hours (outside any event window). Unlabeled training hours used as weak negatives are *assumed*, not verified, labels; their contamination by injected faults (and by unknown natural anomalies) is recorded per run. No validation or test labels are used by any detector in the primary regime. Five independent label draws per seed.

## 8. Thresholds and metrics

* Primary operating threshold: label-free, the 98th percentile of the detector's validation scores (target 2% alert rate). Sensitivity: 1% and 5%.
* Ranking metrics (threshold-free): average precision (AP, primary), ROC-AUC, TPR at 1% FPR.
* Operating metrics at the threshold: precision, recall, F1, false alerts per authority-week, event detection rate (any altered hour alerted), detection delay (hours from first altered hour).
* Breakdowns: authority, fault family (family positives vs. all negatives), severity tier, missingness condition, label budget.
* Undefined metrics are NaN and reported as such.

## 9. Statistical comparison plan

* Unit of replication: authority (5 clusters); seeds and label draws are nested replicates sharing the same underlying series, so hourly observations are never treated as independent.
* Paired differences of AP between methods on matched cells (same authority, seed, condition, events, eligible hours); PU values are first averaged over the 5 label draws.
* Uncertainty: two-stage hierarchical percentile bootstrap (resample authorities, then seeds within authority), 10,000 replicates, seed 2026; plus per-authority sign counts and an exact sign-flip test over the 5 authority means (smallest attainable two-sided p = 0.0625, so no conventional significance claims are possible).

## 10. Secondary analyses (declared before test evaluation)

* Tuned regime: hyperparameters chosen by validation AP using validation injection labels (explicitly outside the label budget; an optimistic reference). Grids in `protocol.yaml`.
* Ablations: without residual features; without missingness indicators; labels-only (no weak negatives); training contamination 2 / 6 / 10 events per family (at 2 events per family only B = 8 and 32 are run, because the training period can contain fewer than 64 altered hours; found in the validation-only development run); leave-one-family-out positives (B = 32).
* Natural-suspect sensitivity (Section 2).
* Error analysis of top false positives on the test period (holidays, DST days, natural-suspect hours) using saved scores.

## 11. Stopping and reporting rules

All configured cells are reported; failures are logged with tracebacks in the run manifest. No test-based re-specification. Any change after freeze is recorded in `PROTOCOL_CHANGES.md` with reason and timing.
