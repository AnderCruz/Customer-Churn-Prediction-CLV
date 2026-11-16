# Data Quality Specification

**Document ID:** NCI-DQ-SPEC-001
**Version:** 0.2
**Status:** Draft for technical review
**Scope:** Phase 2.4.1 — Data Quality Architecture & Validation Rules
**Sources:** Customer Data Contract v1.1, ADR-003, ADR-009, ADR-010, and Subscription Episode & Lifecycle Decision Specification v0.4

## 1. Purpose and scope

The Data Quality Validation layer evaluates cross-dataset relationships, temporal
consistency, and approved business rules after files have passed structural inspection,
type normalization, and Pandera schema validation. It produces a structured, client-scoped
report and prevents data with critical quality failures from continuing to downstream
processing.

This specification defines the responsibilities, initial rule inventory, severities,
report content, gating policy, privacy requirements, tests, and unresolved decisions for
that layer. This specification remains a design document. The repository currently
implements RI-001 through RI-004 and TC-001 through TC-002 in the Data Quality Validation
package; the rule inventory below records each rule's current implementation status.

This layer does not repeat column, nullability, type, primary-key, composite-key, or
single-DataFrame value checks already owned by CSV Header Inspection, Data Type
Normalization, or Pandera. It also does not perform feature engineering, define churn
labels, infer missing business meaning, or interpret financial measures.

The prediction entity is an individual contractual subscription episode. Under the
approved Subscription Episode & Lifecycle Decision Specification v0.4 and ADR-010,
`subscription_id` is the canonical episode identifier, owned by Nowa Analytics;
`customer_id` identifies the associated customer/account and remains distinct. Reactivation
following termination creates a new episode, and previous episodes remain historically
preserved. `customer_id` is not the prediction identifier. Customer-level reporting may
aggregate episode-level results without changing the prediction unit. These are architecture
constraints, not executable Data Quality rules. See [Subscription Episode & Lifecycle Decision Specification v0.4](subscription_episode_lifecycle_decision_specification.md)
and [ADR-010](../03_architecture/adr_episode_identity_and_identifier_management.md).

## 2. Position in the data pipeline

The current code path and the future conceptual mapping stage are:

```text
Client CSV files
       |
       v
File discovery and required/optional dataset handling
       |
       v
CSV Header Inspection
       |
       v
CSV Ingestion (all source values retained as strings)
       |
       v
Data Type Normalization
       |
       v
Client-specific Value Mapping (future; only when approved)
       |
       v
Pandera Schema Validation
       |
       v
Data Quality Validation (cross-dataset RI, TC, and approved BR)
       |
       v
Quality report and blocking decision
       |
       v
Approved datasets for downstream feature engineering and model preparation
```

Client-specific Value Mapping is not implemented. It is shown as a future stage because
approved mappings must be applied after type normalization and before Pandera validates
canonical values. Until that component and a client-approved mapping configuration exist,
unknown status values are not silently mapped by normalization or Data Quality Validation
and may fail the applicable Pandera schema.

The current implemented sequence omits that future mapping stage: CSV ingestion preserves
all fields as strings, type normalization produces the dtypes required by the schemas, and
Pandera validates the normalized frames. Data Quality Validation is a later, distinct
stage. It consumes schema-valid frames and does not rewrite source data.

`usage_monthly` and `invoices` are optional. Their absence is reported as informational
and does not by itself fail validation. If either optional dataset is supplied, it is
subject to applicable schema and quality checks.

## 3. Separation of responsibilities

| Layer | Responsibility | Out of scope for that layer |
|---|---|---|
| CSV Header Inspection | Confirm a supported dataset identifier; inspect the CSV header; enforce required/optional column names, duplicate-name, unexpected-name, and header-format rules. | Field values, cross-file references, business meaning, temporal consistency. |
| CSV Ingestion | Read structurally accepted CSV files; preserve all source values as strings; preserve empty fields as empty strings; load required files and present optional files. | Type conversion, null-token inference, schema or cross-file validation. |
| Data Type Normalization | Convert known present columns to explicit pandas string, numeric, boolean, and UTC datetime dtypes; turn empty known values into missing values; reject malformed conversions. | Schema validation, identifier cleanup, category mapping, key checks, cross-dataset checks, business interpretation. |
| Client-specific Value Mapping (future) | Apply only approved, client-scoped mappings from source categories such as subscription, snapshot, or invoice statuses to canonical values before schema validation. | Unapproved mappings, generic normalization, cross-file checks, or changes to source values without an approved configuration. |
| Pandera Schema Validation | Validate each DataFrame against its declared columns, types, nullability, primary/composite uniqueness, controlled values, and checks already encoded in its schema. | Cross-file foreign keys, client-specific temporal cutoffs, unresolved episode rules, financial interpretation. |
| Data Quality Validation | Evaluate cross-dataset referential integrity, approved cross-column or cross-dataset temporal rules, and approved business rules; create findings and apply the quality gate. | Re-running schema checks, silently correcting data, imputing values, dropping rows, feature engineering, or inventing unresolved semantics. |

### 3.1 Future ownership of client-specific status mapping

Client-specific value mapping is a transformation responsibility, not a Data Quality
Validation responsibility. It is not implemented in the current pipeline. Before it can be
used, data discovery must identify each client's source values and approve a client-specific
mapping configuration. The future component must apply that configuration after Data Type
Normalization and before Pandera Schema Validation. The normalizer and DQ layer must not
silently map unknown values. Without an approved mapping, a noncanonical status remains
unchanged and may be rejected by the existing schema.

### 3.2 Checks owned by existing schemas

The quality layer must consume the outcome of Pandera and must not duplicate these checks:

- Required column presence, strict unexpected-column rejection, and per-column types and
  nullability.
- Identifier non-empty and whitespace rules.
- Unique keys: `customers.customer_id`, `subscriptions.subscription_id`, and
  `invoices.invoice_id`.
- Composite keys: `(subscription_id, snapshot_date)` in subscription snapshots and
  `(subscription_id, usage_month)` in monthly usage.
- Canonical subscription, snapshot, and invoice status values.
- Non-negative recurring revenue, invoice amount, usage volume, and usage counts.
- Three-uppercase-letter currency format. This is a format check only and does not prove
  membership in ISO 4217.
- `active_users <= total_users` when both usage fields are present.
- Invoice `due_date` and `paid_date` not preceding `invoice_date`.

These checks are marked **ALREADY IMPLEMENTED** in the rule inventory to identify their
owner. That status does not mean a duplicate implementation exists in the Data Quality
Validation package.

## 4. Rule identifiers and status vocabulary

Rule identifiers are stable references for findings, tests, and future implementation.
Changing a rule's meaning should be reviewed and versioned. A rule may apply only when its
dataset is present and its prerequisites are available.

Every rule has an implementation status:

| Status | Meaning |
|---|---|
| **ALREADY IMPLEMENTED** | The rule is currently enforced by another identified layer, normally Pandera, ingestion, or normalization. The Data Quality layer must not duplicate it. |
| **IMPLEMENTED_IN_DQ** | The rule has been implemented and is actively enforced by the Data Quality Validation layer itself. |
| **PROPOSED** | The source contract supports the rule and a Data Quality implementation is proposed, but no Data Quality code currently enforces it. |
| **PENDING_DECISION** | The contract or architecture identifies the issue, but a business or temporal decision is needed before the rule can be finalized. |
| **DEFERRED** | The rule depends on fields, policy, or downstream definitions not currently supplied; implementation is intentionally postponed. |

The allowed implementation lifecycle transition is **PROPOSED** to
**IMPLEMENTED_IN_DQ**. This transition is allowed only after the corresponding DQ
implementation and its required tests are complete and have been reviewed. **ALREADY
IMPLEMENTED** remains reserved for a check enforced by another layer. Introducing this
status does not change the current status of any rule in the inventory.

The severity meanings are defined in Section 8. For rules pending decisions, the listed
severity is the proposed severity if the rule is confirmed; it is not permission to enforce
the undecided rule.

## 5. Referential Integrity rules (RI)

These rules operate across datasets after each supplied dataset has passed its own schema.
They do not repeat primary-key uniqueness or foreign-key nullability checks already owned
by the schemas.

| ID | Description | Applicability | Severity | Implementation status | Basis and notes |
|---|---|---|---|---|---|
| RI-001 | Every `subscriptions.customer_id` must match a `customers.customer_id`. | Required customers and subscriptions. | ERROR | IMPLEMENTED_IN_DQ | Contract v1.1, Sections 4.2 and 5. Broken subscription-to-customer references are critical. |
| RI-002 | Every `subscription_snapshots.subscription_id` must match a `subscriptions.subscription_id`. | Subscription snapshots, when supplied; currently required by the loader. | ERROR | IMPLEMENTED_IN_DQ | Contract v1.1, Sections 4.3 and 5. |
| RI-003 | Every `usage_monthly.subscription_id` must match a `subscriptions.subscription_id`. | Only when optional `usage_monthly` is present. | ERROR | IMPLEMENTED_IN_DQ | Contract v1.1, Sections 4.4 and 5. Absence of the entire dataset is not a failure. |
| RI-004 | Every `invoices.subscription_id` must match a `subscriptions.subscription_id`. | Only when optional `invoices` is present. | ERROR | IMPLEMENTED_IN_DQ | Contract v1.1, Sections 4.5 and 5. Absence of the entire dataset is not a failure. |
| RI-005 | Every customer record must be referenced by at least one subscription in the initial dataset. | Required customers and subscriptions. | ERROR | PROPOSED | This reverse-reference requirement is stated in Contract v1.1, Section 4.1. No orphan-customer exception is currently documented. |
| RI-006 | Required relationship identifiers must be non-null. | Subscription, snapshot, usage, and invoice foreign-key columns. | ERROR | ALREADY IMPLEMENTED | Required foreign-key nullability is checked by the applicable Pandera schemas. Do not repeat it in the DQ layer. |
| RI-007 | Primary and composite keys must be unique. | All supplied datasets. | ERROR | ALREADY IMPLEMENTED | Owned by Pandera schemas as listed in Section 3.2 — Checks owned by existing schemas. Do not repeat key checks in the DQ layer. |

The validator must compare identifiers as strings. It must not cast them to numeric values,
trim them, or otherwise change their representation while joining.

## 6. Temporal Consistency rules (TC)

Only rules supported by the contract are listed. Undecided snapshot conventions, episode
semantics, data-availability timestamps, and usage-period boundaries are not to be guessed.

| ID | Description | Applicability | Severity | Implementation status | Basis and notes |
|---|---|---|---|---|---|
| TC-001 | `subscriptions.end_date` must not precede `subscriptions.start_date`. | Subscriptions where both dates are present. | ERROR | IMPLEMENTED_IN_DQ | Explicit contract rule; enforced by `temporal_consistency.py` when both dates are present. |
| TC-002 | `subscriptions.cancellation_date` must not precede `subscriptions.start_date`. | Subscriptions where both dates are present. | ERROR | IMPLEMENTED_IN_DQ | Explicit contract rule; enforced by `temporal_consistency.py` when both dates are present. |
| TC-003 | A snapshot must not precede the applicable subscription start date. | Subscription snapshots with a resolvable subscription lifecycle start. | ERROR | PENDING_DECISION | Contract v1.1, Section 7. The applicable episode must be reliably attributable and date semantics approved; the approved reactivation direction does not establish source-record episode attribution or episode boundaries (DD-004 and DD-006). |
| TC-004 | A snapshot must not be later than the agreed data extraction cutoff. | Subscription snapshots, when an agreed cutoff is supplied. | ERROR | PENDING_DECISION | Explicit contract rule, but the cutoff value and its timezone/convention are not supplied by the current data contract (DD-010). |
| TC-005 | Snapshot dates must follow a consistent monthly convention. | Subscription snapshots. | ERROR | PENDING_DECISION | Contract requires consistency, while DD-001 leaves first-of-month versus last-of-month open. No convention may be assumed. |
| TC-006 | Snapshot state must contain only information available on or before its observation date. | Subscription snapshots used for point-in-time training or evaluation. | ERROR | DEFERRED | Contract requires point-in-time correctness, but the current snapshot contract has no separate recording or availability timestamp to verify this rule. Depends on DD-011 and source-system metadata. |
| TC-007 | Usage records must correspond to valid subscription periods. | `usage_monthly`, when present. | ERROR | PENDING_DECISION | Explicit contract requirement. Usage-period boundaries and the policy for periods crossing episode boundaries remain undefined (DD-001, DD-004, and DD-006); source data must reliably identify the applicable episode. Do not infer month-boundary or episode attribution from dates. |
| TC-008 | Invoice payment information must not be treated as available before its actual availability date. | `invoices`, when present, and a defined prediction observation timestamp. | ERROR | DEFERRED | Contract states the point-in-time principle, but the contract does not provide payment-recording/availability timestamps or a rule to infer availability from `paid_date` (DD-010 and DD-011). |
| TC-009 | Invoice due and paid dates must not precede invoice date. | Invoices where applicable dates are present. | ERROR | ALREADY IMPLEMENTED | Cross-column checks already exist in `INVOICE_SCHEMA`. The DQ layer must not duplicate them. |
| TC-010 | `customers.created_at` must not be later than the agreed extraction date. | Customers where an agreed extraction date is supplied. | ERROR | PENDING_DECISION | Explicit contract rule, but the agreed extraction date and timezone/cutoff convention must be supplied (DD-010). |
| TC-011 | Report when snapshot history falls below an approved minimum coverage period. | Subscription snapshots used for model development. | WARNING | PENDING_DECISION | The contract describes historical coverage as dependent on modelling needs; no minimum period is set (DD-002). |
| TC-012 | Use only information available on or before a prediction observation timestamp when building predictive features. | Future point-in-time feature datasets. | ERROR | DEFERRED | Explicit contract/ADR principle, but this DQ phase validates source datasets and does not yet have prediction observation or all source availability timestamps. |

The approved episode semantics are that reactivation following termination creates a new
contractual episode with a new canonical `subscription_id`, while the previous episode
remains historically preserved. This does not resolve all lifecycle event semantics,
episode boundaries, source identifiers, or dependent-record attribution. Data Quality must
not infer episode identity from dates, status, row order, or heuristic similarity; decide
whether a source record represents a new or existing episode; or infer snapshot, usage, or
invoice attribution. Dependent records require reliable source evidence or an explicitly
approved mapping, and unresolved attribution remains unresolved. TC-003 and TC-007 remain
pending for their stated attribution and date/period semantics. Snapshot dates must not be
required to fall on the first or last day of a month until DD-001 is resolved. See the
Subscription Episode & Lifecycle Decision Specification v0.4 and ADR-010.

## 7. Business Rules (BR)

Business rules below distinguish validity checks from financial interpretation. A numeric
or status validity failure does not authorize the DQ layer to reinterpret revenue or map a
client-specific category.

| ID | Description | Applicability | Severity | Implementation status | Basis and notes |
|---|---|---|---|---|---|
| BR-001 | `active_users` must not exceed `total_users` when both are available. | `usage_monthly`, when present. | ERROR | ALREADY IMPLEMENTED | Enforced by `USAGE_MONTHLY_SCHEMA`; do not duplicate. |
| BR-002 | Usage counts, usage volume, recurring revenue, and invoice amount must be non-negative. | Applicable fields in supplied datasets. | ERROR | ALREADY IMPLEMENTED | Enforced by Pandera schemas; do not duplicate. This does not define financial meaning. |
| BR-003 | Subscription, snapshot, and invoice statuses must match the canonical allowed values. | Subscriptions, snapshots, and invoices after any approved upstream mapping. | ERROR | ALREADY IMPLEMENTED | Existing Pandera schemas validate canonical status values. This rule covers validation only; it does not perform client-specific mapping. |
| BR-004 | Currency values must have the contract-required three-uppercase-letter format. | Currency fields in supplied datasets. | ERROR | ALREADY IMPLEMENTED | Schemas enforce the pattern `^[A-Z]{3}$` only. |
| BR-005 | Currency values must be members of the applicable ISO 4217 currency list. | Currency fields where full membership is required. | ERROR | PENDING_DECISION | Contract calls for valid ISO 4217 codes, but current schemas verify only shape. An authoritative reference, versioning policy, treatment of withdrawn codes, and acceptance of historical codes must be decided before implementation (DD-009). A regular expression is not full membership validation. |
| BR-006 | Missing `usage_monthly` or `invoices` should be recorded as informational, not treated as a validation failure. | Client runs where either optional file is absent. | INFO | PROPOSED | Contract v1.1, Section 2.3, identifies both datasets as optional. While unimplemented, BR-006 has runtime result `NOT_EVALUATED` if represented in an execution record; dataset presence or absence may still be recorded in `dataset_presence`. Absence does not block the pipeline. |
| BR-009 | Report optional or predictive field missingness when it exceeds an approved threshold. | Supplied datasets and fields selected for analysis. | WARNING | PENDING_DECISION | The contract lists high missingness as a warning example but defines no fields, denominator, or threshold (DD-015). |
| BR-010 | Map client-specific subscription, snapshot, and invoice status values to approved canonical values before schema validation. | Clients whose source statuses differ from the canonical schema values. | ERROR | PENDING_DECISION | Mapping is not implemented. It requires data discovery and an approved client-specific mapping configuration (DD-007). It belongs to the future Client-specific Value Mapping stage, not DQ. ERROR describes the potential consequence of failing to provide required canonical values when mapping is mandatory; it is not a DQ runtime severity. BR-010 must not produce a DQ finding or runtime result. |

No other category mappings, cross-field business assumptions, financial thresholds,
outlier limits, or status transitions are defined by this specification.

### 7.1 Financial interpretation boundary

Data Quality Validation does not:

- Calculate MRR or ARR.
- Perform currency conversion.
- Reconcile subscription recurring revenue against invoice amounts.
- Calculate revenue-at-risk or CLV, or otherwise interpret financial measures.

These activities belong to downstream analytical components and depend on decisions such
as the recurring-revenue basis and currency policy (DD-008 and DD-009). Data Quality may
validate only approved data-quality rules; it must not introduce financial interpretation
rules unsupported by the current contract.

## 8. Severity definitions

The specification uses the runtime severities **ERROR**, **WARNING**, and **INFO**. These
map to the contract's Critical, Warning, and Informational classifications.

| Severity | Meaning | Default pipeline effect |
|---|---|---|
| **ERROR** | A confirmed violation that makes the affected dataset or relationship unsafe for downstream use. | Blocks the affected dataset and dependent downstream processing. If cross-dataset integrity fails, block the affected participating datasets/workflow. |
| **WARNING** | A concern that requires review but is not defined as a critical contract failure. | Continue under the default policy and include the finding in the report. No warning threshold is defined yet. |
| **INFO** | A non-failing observation, such as an absent optional dataset or a count summary. | Continue; report for transparency. |

Implementation status and runtime result are separate. A runtime result records what was
actually executed; it must not be inferred from documentation status or assumptions. The
mapping for Data Quality rules is:

| Implementation status and execution condition | Runtime behavior |
|---|---|
| ALREADY IMPLEMENTED by another layer | The owning layer reports its result. Do not duplicate it in DQ findings. |
| PROPOSED but not implemented | `NOT_EVALUATED` |
| IMPLEMENTED_IN_DQ, applicable, and executed | `PASS` if no violations are found; `FAIL` if one or more are found. |
| PENDING_DECISION | `NOT_EVALUATED` |
| DEFERRED | `NOT_EVALUATED` |
| Implemented rule whose applicability condition is not met in the current execution, so it is correctly not executed | `NOT_APPLICABLE` |

A proposed rule without an implementation must never be reported as `PASS`. A pending or
deferred rule must never be reported as `PASS` or emitted as an enforced ERROR. An
unimplemented proposed rule remains `NOT_EVALUATED` even when its applicability condition
is not met. Only an implemented rule whose applicability condition is not met is
`NOT_APPLICABLE`; for example, a future implemented rule for an optional dataset is not
applicable when that dataset is absent. Absence alone is not a failed validation. A
Pandera-owned rule is reported by the schema stage and must not be duplicated in DQ
execution results.

## 9. Data Quality Report

Data Quality Validation runs only after successful schema validation. Its report contains
only Data Quality Validation results: Referential Integrity rules, approved Temporal
Consistency rules, approved Business Rules, Data Quality findings, DQ severity counts, and
the DQ blocking decision. It must not reproduce header inspection, ingestion, normalization,
or Pandera schema findings. BR-010 is a future mapping dependency, not an executable DQ
rule, and must not appear as a finding or runtime result. The exact serialization format is
an implementation decision; this section defines the expected information, not a
dependency or storage format.

### 9.1 Run-level fields

| Field | Description |
|---|---|
| `report_id` | Unique identifier for this report. |
| `run_id` | Identifier linking the report to one pipeline execution. |
| `client_scope` | Client-scoped pseudonymous identifier; never a shared cross-client key. |
| `created_at_utc` | Report creation timestamp in UTC. |
| `contract_version` | Contract version used for validation, currently v1.1. |
| `specification_version` | Version of this quality specification. |
| `pipeline_stage` | Constant identifying `data_quality_validation`. |
| `dataset_presence` | Presence of DQ-relevant datasets; an absent optional dataset is not a DQ failure. |
| `summary` | DQ-only counts by severity and runtime result, DQ outcome, and whether the DQ stage blocks downstream processing. |
| `findings` | Collection of rule-level records described below. |

### 9.2 Finding fields

Each Data Quality finding should include:

- `rule_id`, `implementation_status`, `severity`, and runtime `result` (`PASS`, `FAIL`,
  `NOT_APPLICABLE`, or `NOT_EVALUATED`).
- `dataset` or the related datasets, and a logical `column` or relationship when relevant.
- A concise, sanitized description of the rule outcome.
- `records_evaluated` and `records_affected` where meaningful.
- A boolean or enumerated `blocking` effect and the affected downstream scope.
- Optional safe diagnostic references only when required and approved; no full row or
  DataFrame payloads.

| Runtime result | Meaning |
|---|---|
| `PASS` | The rule was executed and no violations were found. |
| `FAIL` | The rule was executed and one or more violations were found. |
| `NOT_APPLICABLE` | An implemented rule's applicability condition is not met in the current execution, so the rule is correctly not executed; for example, a future implemented rule for an optional dataset when that dataset is absent. |
| `NOT_EVALUATED` | The rule was not evaluated because a required decision, prerequisite, or data element is unavailable. |

A proposed but unimplemented, pending-decision, or deferred rule must be
`NOT_EVALUATED`, never `PASS`, even if its applicability condition is not met. BR-006 is
proposed and unimplemented, so it remains `NOT_EVALUATED` if represented in an execution
record; dataset presence or absence may still be captured in `dataset_presence`. An
implemented rule that does not apply to the current run is `NOT_APPLICABLE`; an absent
optional dataset must not create a failed validation. A rule already implemented in
Pandera is reported only by the schema stage and must not be duplicated in Data Quality
findings. Runtime results must describe actual execution, not documentation status or
assumptions.

### 9.3 Pipeline Execution Summary

The Pipeline Execution Summary is a separate, broader execution-level concept. It
consolidates stage outcomes for CSV Header Inspection, CSV Ingestion, Data Type
Normalization, Pandera Schema Validation, and Data Quality Validation. It must retain an
upstream failure even when a later stage, including Data Quality Validation, was never
reached.

The summary should provide stage-level outcomes and may reference the Data Quality Report
by `report_id` when that report exists. It must not copy detailed Data Quality findings;
those remain in the Data Quality Report. This document defines only this conceptual
distinction and does not design or implement a full orchestration or monitoring system.

## 10. Pipeline blocking and continuation policy

1. Data Quality Validation runs only after the affected datasets pass header inspection,
   ingestion, normalization, and schema validation. If an upstream stage fails, no DQ
   findings are generated for the blocked dataset. The Pipeline Execution Summary retains
   the upstream failure; the Data Quality Report does not reproduce it.
2. A confirmed DQ **ERROR** blocks the affected dataset. A broken foreign-key relationship
   blocks the related tables from downstream processing because the relationship cannot be
   trusted.
3. A **WARNING** does not block by default. It remains visible for analyst review; no
   numerical warning thresholds are established here.
4. **INFO** does not block. The absence of `usage_monthly` or `invoices` does not block
   processing, and dataset presence or absence may be recorded in `dataset_presence`.
   BR-006 remains `PROPOSED`; while unimplemented, its runtime result is `NOT_EVALUATED`
   if represented in an execution record. A future implemented rule that checks an absent
   optional dataset would receive `NOT_APPLICABLE`; absence is not a failed validation.
5. No record may be silently dropped, repaired, imputed, or quarantined by the DQ layer.
   Any future row-level reject/quarantine policy needs explicit approval and traceability.
6. Proposed but unimplemented, pending-decision, and deferred DQ rules are not enforced or
   blocking; report them as `NOT_EVALUATED` when relevant, even if an applicability
   condition is not met. Only an implemented rule that does not apply to the current
   execution is `NOT_APPLICABLE`.
7. The Data Quality Report should still be produced when a DQ blocking error occurs, so the
   DQ reason and scope of the block are reviewable. The Pipeline Execution Summary retains
   stage outcomes independently, including upstream failures that prevent DQ execution.

## 11. Privacy requirements

- Keep every report, log, temporary result, and diagnostic scoped to the relevant client,
  consistent with accepted ADR-003 client isolation.
- Use a pseudonymous client scope. Do not place direct personal identifiers or raw source
  values in report messages.
- Do not include full rows, DataFrames, identifiers, free-text cancellation reasons, or
  invoice details in findings. Prefer rule IDs, dataset/column names, and affected-record
  counts.
- Do not include absolute filesystem paths or credentials in persisted report content.
  Error wrappers should sanitize paths and low-level parser details before reporting to
  client-facing or broadly accessible systems.
- If row-level diagnostics are later required, use an approved access-controlled mechanism
  with data minimization and retention controls; do not expose raw values by default.
- Restrict report access, retention, export, and deletion consistently with client data
  governance. Do not use live client data in automated tests or examples.

Current normalization errors include a bounded representation of the offending value, and
some ingestion/header errors include paths or underlying parser details. Those messages
must not be copied verbatim into broadly accessible or client-facing DQ reports without
sanitization. This specification does not modify those existing implementations.

## 12. Automated testing strategy

Data Quality tests must use synthetic DataFrames that conform to Contract v1.1 and must
not use live client data. Tests should be deterministic and independent of external
services. The repository currently has unit tests for the models and the implemented
RI-001–RI-004 and TC-001–TC-002 rules. Preserve and extend those tests only for behavior
that is implemented and authorized.

- Unit-test currently implemented rules with valid, violating, null, and boundary cases
  as applicable. Keep primary/composite uniqueness, column types, nullability, and other
  schema-level constraints in Pandera tests rather than repeating them as DQ behavior.
- A PROPOSED rule becomes an executable business-rule test target only after its
  implementation is explicitly approved and implemented. Do not treat a design or test
  proposal as evidence that the rule is executable.
- RI-005 and BR-006 tests that assert their business behavior may be added only when their
  implementation is explicitly authorized and implemented. Until then, preserve their
  current statuses and do not test them as enforced business rules.
- For PENDING_DECISION and DEFERRED rules, test that they remain `NOT_EVALUATED` and do not
  enforce blocking behavior when represented by an execution/reporting layer. Such tests
  verify the implementation boundary; they do not implement or approve the rules. An
  implemented rule whose applicability condition is unmet returns `NOT_APPLICABLE`.
- Test each currently implemented foreign-key direction, orphan detection, optional
  dataset presence/absence, and input immutability. Do not test RI-005 customer-orphan
  behavior as an enforced rule unless separately authorized and implemented.
- Test currently implemented temporal rules with explicit date values. Future rules that
  depend on cutoffs must use fixed cutoffs and UTC-aware values; do not depend on wall-clock
  time or assume a first/last-of-month snapshot convention.
- Test that absent optional datasets do not fail validation and that Pandera-owned rules
  do not appear as duplicate DQ results.
- When report construction is implemented, test report structure, runtime result
  semantics, rule identifiers, DQ-only severity counts, blocking outcome, and optional
  dataset findings. Test Pipeline Execution Summary stage outcomes when that interface is
  implemented, confirming upstream failures remain visible without copying detailed DQ
  findings.
- Test existing error-handling behavior only where it is currently implemented and
  testable. When report construction and the coordinating/reporting interfaces are
  implemented, add tests for report sanitization, client-scope isolation of generated
  reports, and confirmation that reports do not expose raw rows or direct identifiers.
- Add integration tests through the DQ interface after the coordinating interface is
  implemented. Cover schema-valid datasets, referential failures, temporal failures with
  approved semantics, optional files, and an empty optional dataset. Do not add ingestion
  or normalization behavior to this layer.

## 13. Open decisions and dependencies

| Decision/dependency | Impact on this specification |
|---|---|
| DD-001 — Snapshot convention | Needed before enforcing a specific monthly snapshot date boundary. Until decided, TC-005 is pending and no first/last-day assumption is allowed. |
| DD-002 — Historical coverage | Needed to define any minimum snapshot coverage warning or adequacy rule. No threshold is proposed here. |
| DD-003 — Churn definition | Needed for outcome/label correctness; outside current DQ checks until agreed. |
| DD-004 — Reactivation | The approved direction is that reactivation following termination creates a new episode. Detailed termination/event semantics and reliable attribution of snapshots and usage to the applicable episode remain necessary before selecting an interval. |
| DD-005 — Contract renewal | May affect episode boundaries and status transitions; do not infer rules. |
| DD-006 — Subscription episodes | Episode-level prediction identity and new-episode treatment after termination are approved. Reliable source identifiers, episode boundaries, and dependent-record attribution remain necessary before evaluating lifecycle membership. |
| DD-007 — Subscription status mapping | Required before client-specific statuses can be compared with the current canonical schema values; requires data discovery and an approved client-specific mapping configuration for the future pre-schema mapping stage. |
| DD-008 — Revenue definition | Needed before comparing or interpreting recurring revenue as MRR, ARR, or another measure. |
| DD-009 — Currency handling | Needed for conversion policy and a versioned authoritative ISO 4217 membership reference. |
| DD-010 — Timezone and cutoff | Needed to provide an agreed extraction cutoff and consistent timestamp comparison semantics. |
| DD-011 — Historical availability | Needed for snapshot/invoice point-in-time rules that depend on recording or availability time. |
| DD-015 — Missing-data thresholds | Needed before warning thresholds for optional or predictive fields can be defined. |
| Optional dataset policy | Contract says monthly usage and invoices are optional; missing either is INFO, not a blocking error. |
| Required snapshot policy | Contract classifies snapshots as required for temporal modelling; current ingestion requires them unconditionally. Product policy must confirm whether basic non-temporal validation may omit snapshots. |
| Validation stage ownership | Contract Section 11 lists Data Quality Checks, Referential Integrity Validation, and Temporal Validation as separate pipeline steps. This specification groups them as rule families under one Data Quality Validation layer; architecture owners should confirm whether implementation needs separate execution stages. |
| Report schema and retention | A report format, storage location, access control, and retention/deletion policy must be selected before production use. |
| Validation package implementation | RI-001–RI-004 and TC-001–TC-002 are implemented in the validation package. Reporting, coordination, and remaining approved rule work must be separately implemented and reviewed; pending/deferred rules remain outside executable scope. |

## 14. Documentation conflicts and ambiguities

1. **Pipeline order:** Customer Data Contract v1.1, Section 11, places schema validation
   before data preprocessing and places type normalization after “Validated Raw Data.” The
   current ingestion reads every field as a string, while current Pandera schemas require
   normalized pandas types. The implemented normalizer therefore must run before Pandera
   validation. This specification documents the executable dependency order; the contract
   diagram remains unchanged and should be reconciled through a later documentation review.
2. **Snapshot requirement:** Contract Section 2.3 says snapshots are required for temporal
   modelling, but the current loader treats them as unconditionally required alongside
   customers and subscriptions. Whether snapshots are mandatory for non-temporal data
   validation remains unresolved.
3. **Customer coverage:** Contract Section 4.1 says every customer record must be
   referenced by at least one subscription. This is stronger than the forward foreign-key
   rule and may reject legitimate accounts without subscriptions. The requirement is
   retained as RI-005 without adding an exception; product/data discovery should confirm
   its intended application.
4. **Currency validity:** The contract requires valid ISO 4217 codes, but current Pandera
   schemas check only three uppercase letters. Full membership needs a versioned code list
   and a policy for withdrawn or historical currencies.
5. **Status values:** The contract describes status categories as provisional and says
   client-specific statuses should be mapped during data discovery. Schemas currently
   enforce the canonical lists directly; status mapping must happen before schema
   validation and requires the unresolved DD-007 mapping.
6. **Temporal evidence:** The contract requires data availability to be point-in-time
   correct, but current snapshot and invoice fields do not include separate recording or
   availability timestamps. Several temporal requirements cannot be verified from the
   listed columns alone.
7. **Financial semantics:** Contract fields identify decimal values and currency, but do
   not settle recurring-revenue basis or currency conversion. Data validity must remain
   separate from MRR/ARR, revenue reconciliation, CLV, or revenue-at-risk interpretation.
8. **Reject/quarantine policy:** System Architecture Section 4.1 allows invalid records to
   be rejected or quarantined according to documented rules, but no row-level policy is
   currently defined. This specification proposes blocking affected datasets on confirmed
   ERROR findings and forbids silent row removal; a different reject/quarantine workflow
   requires explicit approval.
9. **Validation stage boundaries:** Contract Section 11 lists data quality, referential
   integrity, and temporal validation as separate steps. This specification treats them as
   rule families governed by one Data Quality Validation layer. Confirm the desired runtime
   stage boundaries before implementing Phase 2.4.2.

No existing contract, ADR, schema, ingestion, normalization, test, or configuration file is
changed by this specification.

## Revision history

| Version | Revision |
|---|---|
| 0.2 | Introduces `IMPLEMENTED_IN_DQ` and clarifies its implementation lifecycle and runtime semantics. |
