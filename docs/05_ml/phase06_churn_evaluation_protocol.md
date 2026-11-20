# Phase 06 churn evaluation protocol

**Scope** — Fieldwise Cloud fictional subscription episodes, Phase 05 feature spec
`fieldwise-episode-features-v1`, export format 2, and outcome policy
`fieldwise-subscription-churn` v1. The observation is an eligible episode snapshot
at UTC time t. A positive is a confirmed qualifying effective termination in
(t, t+30 days]. A negative requires complete horizon evidence without that event.
Pending, censored and ineligible outcomes are excluded. The 90-day history window
and 30-day horizon are experimental. ADR-009/010 and the v1.1 contract continue to
govern identity and inputs. The complete standalone approved roadmap and Charter
were unavailable. Phase sequencing is traced through the owner brief and the
[implementation roadmap](../07_project_management/implementation_plan_and_roadmap.md).

## Gate 1 — Population and evaluation design

These rules are fixed before any Phase 06 model fitting:

| Partition | Source | Observation window (UTC) | Strict maturity boundary |
|---|---|---|---|
| Training | Accepted seed-42 Phase 05 bundle, training accounts | Before 1 April 2023 | 1 April 2023 |
| Validation | Same bundle, validation accounts | 1 April to 1 September 2023 (exclusive) | 1 September 2023 |
| Reserved holdout | Fresh seed **2027**, new Registry and fictional client scope | 1 September 2023 to 1 April 2024 (exclusive) | 1 April 2024, subject to source extraction cutoff |

Both horizon end and ascertainment must precede the right boundary. This purges
crossing labels even when an early termination was already known. Feature evidence
must be available at observation. The 90-day histories of different accounts can
overlap on the calendar, so shared seasonal patterns remain possible. There is no
additional calendar embargo on independent accounts. Repeated rows within a
partition can share history, and may share outcome-event information. Use row-level
metrics for the snapshot-scoring use case, and resample whole accounts for uncertainty.

Allocate seed-42 accounts once, before looking at labels. Interpret the first
eight bytes of SHA-256 of `nci-phase06-v1:<customer_id>` as a big-endian integer.
Buckets 0–69 modulo 100 are eligible for training and 70–99 for validation.
Keep only the observations in the assigned account's time window. This groups
reactivations and repeat observations with the same account. No seed-42 row from the
Batch 09 test period (September 2023 onward) enters training or validation. No Batch
09 performance enters selection.

Generate the fresh seed once with the existing reference scenario and feature
builder, using a fresh Registry and separate fictional client namespace. The
generator reuses account-number strings across independent fictional populations.
Identity across them is defined by population namespace and account number. Check
canonical UUID non-overlap across the entire bundles and record both seed and
evidence fingerprints. Use fresh labels only for aggregate feasibility until the
candidate is frozen. The confirmation gate requires both classes and at least
30/10/10 distinct positive accounts in training, validation and holdout respectively.
There is no seed or split search. Shared scenario rules, calendar and reporting lag
limit independence to a fresh synthetic draw. The holdout provides no evidence for
transfer to real clients.

The label-only audit counted 55, 8 and 19 positive accounts. The original
development-fit stop rule would have stopped at eight validation positives.
Before fitting, the scope was limited to the owner brief's development-only
fallback: report exploratory comparisons if both development partitions contain
both classes, and reserve the holdout without scoring. The split, seed,
confirmation floor and candidate menu are unchanged. The validation ranking and
threshold cannot support a confirmation claim. A partition without both classes
stops all fitting.

## Gate 2 — Fitting and validation-only decisions

Compare a training-prior dummy with L2 logistic regression (`C=1`, with and
without balanced training weights). Then compare Random Forest (120 trees, minimum
leaf 20, depths 4 and 8, balanced subsample weights) and histogram gradient boosting
(100 iterations, minimum leaf 30, learning rate 0.05, maximum 7 or 15 leaves and
L2 penalty 1). The deeper boosting configuration uses balanced training weights.
Early stopping is disabled so it cannot introduce an internal random validation split.
The estimator seed is 42. This small fixed menu limits adaptive search on scarce events.
Training and validation populations are identical across candidates.

Learn median imputation, explicit nullable-field flags, unknown-safe one-hot
encoding and constant-column removal in training-only pipelines. Standardise
numeric inputs for logistic regression. Retain source missingness and exact GBP
until conversion to numeric model inputs. Dummy also receives the same registry
inputs. Use no outcome evidence, record identifiers or observation dates as predictors.

Choose highest validation average precision (AP). A tie within 1e-12 favours the
simpler configuration in the declared candidate order. Select a candidate-specific
threshold by maximal validation F1 over distinct validation scores (including the
all-negative decision), breaking ties towards higher thresholds. This research rule
has no operational cost interpretation. Compare AP with prevalence, report ROC-AUC
where both classes occur, and record precision, recall, F1, FP, FN, confusion
counts and Brier score. Use 400 account-level bootstrap draws with fixed seed 42
for percentile intervals on AP and recall of the selected candidate. These are
descriptive and exclude selection uncertainty. Use fixed probability bins and
report sample counts before interpreting calibration. No calibrator is fitted.

## Gate 3 — Frozen evaluation

Keep the training-fitted winner and validation threshold without refitting. Bind
both to the validated input manifests and record the frozen protocol and candidate
before calling holdout prediction. Evaluate the fresh partition once and report
all declared metrics, even if poor. No holdout-driven changes or alternative model
scoring. Local artefacts contain no client data, stay outside version control and
are intended for controlled research. The notebooks render the artefacts offline
and do not fit models.

## Scoring integrity audit

The original Phase 06 code read probability column 1 by position. The retained
pipeline exposed class order `[0, 1]`, so this convention yielded confirmed-churn
probabilities in the reference run. The scoring implementation now locates class
`1` explicitly and rejects unexpected class sets. Deterministic fixtures cover
both column orders, perfect and reversed ranking, a constant score, scores equal
to the threshold, confusion orientation and calibration bin edges. The model,
reference artefacts, threshold and notebook conclusions are unchanged.

The audit verified the report linkage, reference manifest and frozen pipeline
digest `16d7a588ec36dc4b22beb20b56f98903af68d4453563921985ba063a024a8cd1`. It
reconstructed the ordered seed-42 validation inputs, with predictors and targets
taken from the same sequence. Read-only inference with the frozen pipeline
reproduced the saved validation AP (0.0113798009), ROC-AUC (0.2327221439), PR and ROC
curves, reliability bins and decision counts at threshold 0.003965284793899528.
The confusion matrix contained 14 true negatives, 695 false positives, zero
false negatives and eight true positives. All seven reports reconciled internally
against their saved curves, calibration counts and frozen threshold points.
Training AP (0.8196550113) is a retained in-sample result. Independent replay was
limited to the nominated model and its validation rows.

Of 5,672 positive–negative validation pairs, the positive scored higher in 112,
tied in 2,416 and scored lower in 3,144. Half credit for ties gives the reported
ROC-AUC. All eight positive observations occupied the 0–1% score band and all
241 observations in the higher bands were negative. The low threshold explains
why the model still alerted on every observed event. Its 703 alerts among 717
observations provide little evidence of useful prioritisation.

Sparse events, synthetic cohort or calendar effects and model flexibility are
plausible contributors to the training–validation difference. The evidence cannot
isolate their effects or establish calibration, independent generalisation or
commercial utility. Validation had eight positive accounts against the fixed
floor of ten. The seed-2027 reserve remains unscored. The [Phase 06 acceptance
record](../07_project_management/implementation_plan_and_roadmap.md#191-project-owner-final-acceptance)
records the accepted engineering scope and the limits of predictive evidence.
