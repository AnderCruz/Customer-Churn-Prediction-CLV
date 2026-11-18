# Subscription Episode Data Contract Impact Assessment

**Phase:** 2.4.3.1
**Assessment type:** Read-only technical impact assessment
**Subject:** Impact of approved episode architecture decisions on Customer Data Contract v1.1 and current validation implementation

## 1. Executive Summary

The approved direction is that each contractual subscription episode has its own identity, is an independent prediction entity, and remains historically preserved. A customer may have multiple episodes, and reactivation after termination creates a new episode. These requirements are consistent with the subscription-level prediction direction in ADR-009, but the current Data Contract v1.1 describes one row per subscription and does not distinguish an episode identifier from a source-system subscription identifier.

**APPROVED REQUIREMENT:** `customer_id` identifies the customer/account. Each contractual episode has a unique identity and prediction record. Reactivation after termination creates a new episode, and earlier episodes are retained.

**CURRENT IMPLEMENTATION:** `subscription_id` is unique in `subscriptions.csv` and is the foreign key used by snapshots, usage, and invoices. The schemas and referential-integrity code enforce key shape/existence, but cannot establish whether a dependent source record was attributed to the correct episode. No source-system identifier, episode-ID assignment process, migration mechanism, or episode-aware coordinator exists in the inspected code.

**RECOMMENDATION:** Clarify the contract so that one subscription row means one episode and define the episode key. Preserve a separate source-system identifier when available, but make its requiredness, uniqueness, scope, and interpretation contingent on client/source discovery. Require dependent rows to carry a reliable episode key before treating their foreign-key matches as correct attribution. Do not derive episode IDs or assign historical snapshots, usage, or invoices from dates alone.

**PENDING DECISION:** Identifier issuance/ownership, source ID reuse and availability, lifecycle boundaries, and historical attribution remain unresolved in the episode specification. These decisions affect whether a new contract can be adopted by existing clients without a breaking migration.

The inspection also found documentation that is behind the implementation: the Data Quality Specification still lists TC-001/TC-002 as `PROPOSED`, while their validator exists and emits `IMPLEMENTED_IN_DQ`; the Implementation Architecture describes DQ validation as not implemented although model, RI, and TC modules/tests now exist. This report records that discrepancy without correcting the documents.

## 2. Sources Inspected and Evidence Labels

Labels used below:

- **APPROVED REQUIREMENT** — explicitly approved in the Subscription Episode & Lifecycle Decision Specification.
- **CURRENT IMPLEMENTATION** — behavior verified in repository code or tests.
- **RECOMMENDATION** — proposed change or sequence; not an approved contract requirement.
- **PENDING DECISION** — explicitly unresolved or not verifiable from repository contents.

Relevant documents and implementation:

| Source | Relevant definition |
|---|---|
| `docs/04_data/customer_data_contract.md` | Contract v1.1, dataset grain, keys, columns, validation rules, temporal and churn requirements, versioning, DD-004/DD-006. Particularly Sections 2, 4, 5, 7, 8, 12, 13. |
| `docs/04_data/subscription_episode_lifecycle_decision_specification.md` | Approved EP-DEC-001–005; recommended identifier and attribution design; pending DD-EP-001–017. Particularly Sections 4–12. |
| `docs/03_architecture/architecture_decisions.md` | ADR-003 client isolation and accepted ADR-009 subscription-level prediction entity. ADR-009 still leaves reactivation and episodes to data discovery. |
| `docs/04_data/data_quality_specification.md` | Current rule definitions and implementation-status vocabulary, including RI and TC applicability. |
| `docs/04_data/data_quality_implementation_architecture.md` | Planned module interfaces and initial rule scope; contains stale implementation-state descriptions. |
| `src/nowa_customer_intelligence/data/schemas/*.py` | Five Pandera schemas and their field, key, and cross-column checks. |
| `src/nowa_customer_intelligence/data/preprocessing/type_normalization.py` | Per-dataset column dtype map and conversion behavior. |
| `src/nowa_customer_intelligence/data/ingestion/header_inspection.py`, `csv_ingestion.py` | Allowed CSV headers, required/optional files, string-preserving ingestion. |
| `src/nowa_customer_intelligence/data/validation/referential_integrity.py`, `temporal_consistency.py` | Implemented RI-001–004 and TC-001–002 behavior. |
| `tests/unit/data/schemas/`, `tests/unit/data/preprocessing/`, `tests/unit/data/validation/`, `tests/unit/data/test_csv_ingestion.py`, `tests/integration/test_csv_ingestion.py` | Existing schema, normalization, DQ, CSV fixtures and assertions. |

No live client data or source-system behavior was available for inspection.

## 3. Current Contract and Dataset Impact

### 3.1 Current Dataset Structure

| Dataset | Contract key and relationship | Relevant dates | Episode relationship and current limitation |
|---|---|---|---|
| `customers.csv` | Primary key `customer_id`. Parent for `subscriptions.customer_id`. One row per customer. | `created_at` required. | The account identity is distinct from episode identity. A one-to-many customer-to-episode relationship is compatible with the approved direction; customer schema need not change for episode identity alone. |
| `subscriptions.csv` | Primary key `subscription_id`; foreign key `customer_id`. One row per subscription in v1.1. | `start_date` required; `end_date` and `cancellation_date` optional. | The episode decision requires one row per contractual episode. The current contract does not say whether `subscription_id` is a source key or internal episode key, and has no separate source ID. Current uniqueness supports distinct episode rows only when each episode is given a distinct ID. |
| `subscription_snapshots.csv` | Composite primary key `(subscription_id, snapshot_date)`; `subscription_id` references subscriptions. One row per subscription per monthly snapshot date. | `snapshot_date` required. Its first/last-of-month convention is unresolved (DD-001). | The FK can identify an episode only if the snapshot carries that episode’s stable ID. The source may not distinguish episodes historically; date proximity or status is not an approved assignment method. |
| `usage_monthly.csv` | Optional. Composite primary key `(subscription_id, usage_month)`; subscription FK. One record per subscription per month. | `usage_month` required, but represented period bounds/meaning remain unclear. | The FK should identify the episode whose usage is reported. Cross-episode periods, partial months, and source-level rather than episode-level usage require policy and source data. |
| `invoices.csv` | Optional. Primary key `invoice_id`; `subscription_id` FK. One record per invoice. | `invoice_date` required; `due_date`, `paid_date` optional. | Current contract says the invoice is associated with a subscription but does not distinguish episode-level linkage from source-subscription linkage. Historical attribution and invoices spanning services/episodes are unresolved. |

### 3.2 Approved Identity Versus Current Contract

**APPROVED REQUIREMENT:** EP-DEC-001 and EP-DEC-004 keep customer and episode identities distinct and allow one customer to have multiple episodes. EP-DEC-002 makes every episode an independent prediction entity with a unique identifier. EP-DEC-003 preserves earlier episodes. EP-DEC-005 says reactivation following termination creates a new episode.

**CURRENT IMPLEMENTATION:** Contract v1.1 calls `subscription_id` a “Unique subscription identifier” and defines one record per subscription. `SUBSCRIPTION_SCHEMA` enforces uniqueness of that field. The episode specification’s recommended model treats `subscription_id` as the internal episode ID and `source_subscription_id` as a separate source-system ID, but this is a recommendation; it explicitly leaves ID generation/supply unresolved.

**RECOMMENDATION:** Define a stable, client-scoped episode key in the contract and explicitly state that every subscription row is one episode. Document a separate source identifier only after its source availability, reuse behavior, nullability, and namespace are established. A raw source key must not be used as the episode key when it can identify multiple episodes.

**PENDING DECISION:** DD-EP-002 and DD-EP-003 block choosing a contract-ready identifier supply/generation mechanism. DD-EP-004 blocks conclusions about namespacing when multiple source systems can contribute data.

### 3.3 Lifecycle Semantics

The approved reactivation direction does not finalize cancellation effectiveness, renewals, extensions, pauses, or suspensions. Current contract fields include start, end, cancellation date, status, and cancellation reason, but their event meanings are not sufficient to infer all episode boundaries. In particular, the contract distinguishes `end_date` and `cancellation_date` but does not fully define their relationship.

Renewal or extension behavior (DD-EP-006), suspension/pause behavior (DD-EP-007), and cancellation event semantics (DD-EP-005) must be decided before those cases receive definitive field semantics or validation rules. Preserve previous episode rows; do not overwrite an earlier lifecycle record when a new episode begins.

## 4. Impact by Dataset

| Dataset | Required contract/schema/pipeline impact | Constraints not yet supportable |
|---|---|---|
| Customers | Keep `customer_id` as account key. Document that multiple rows in subscriptions may reference the same customer. No episode field is needed in customers merely to support episodes. | Customer-level churn and risk aggregation remain separate, with DD-EP-014/DD-EP-015 deferred. |
| Subscriptions | Define row grain as one episode; define `subscription_id` as the unique stable episode identifier; retain `customer_id` as account FK. Consider `source_subscription_id` and source namespace metadata only after decisions. Define which dates/statuses describe an episode. | Identifier issuance (DD-EP-003), source ID behavior (DD-EP-002), namespace (DD-EP-004), event semantics (DD-EP-005–007), and churn qualification (DD-EP-013) are not finalized. |
| Snapshots | Keep the per-episode key `(subscription_id, snapshot_date)` if each row contains the episode key. Require reliable episode attribution. | DD-EP-008 blocks correct attribution of historical snapshots when source data lacks episode identity; snapshot convention DD-001 and date/cutoff decisions remain separate requirements. |
| Usage | Keep `(subscription_id, usage_month)` only when subscription_id is an episode ID. Clarify how a usage record identifies the episode whose service it measures. | DD-EP-009 and DD-EP-010 block ambiguous usage attribution and cross-episode period treatment; usage month bounds and DD-001 are also relevant. |
| Invoices | Keep invoice ID as invoice primary key. Define whether its subscription FK is an episode ID and require evidence for that mapping. | DD-EP-011 blocks invoice-to-episode semantics; no date-only allocation is supported. Invoice aggregation/allocation policy is not established. |

## 5. Pandera Schema Impact

All five current schemas use `strict=True`, `coerce=False`, and `add_missing_columns=True`. They encode structural field checks; cross-dataset foreign-key validation is separate. The current schema code does not include a `source_subscription_id` field.

| Schema | Existing relevant fields/constraints | Likely change under episode model | Breaking impact / unresolved constraints |
|---|---|---|---|
| `CUSTOMER_SCHEMA` | Unique non-null `customer_id`; required UTC `created_at`; optional account attributes. | No change indicated for episode identity alone. | Customer aggregation policy is outside this schema and remains deferred. |
| `SUBSCRIPTION_SCHEMA` | Unique non-null `subscription_id`; non-null `customer_id` and `start_date`; optional end/cancellation dates; controlled status; non-negative revenue; currency format; nullable boolean. | Clarify that each row/key is one episode. Add source identifier or namespace only if approved. Any lifecycle-specific fields require approved semantics. | Adding required columns or changing key meaning can break v1.1 files. No source ID nullability/uniqueness constraint can be chosen yet. Do not add renewal/pause rules before semantics are approved. |
| `SUBSCRIPTION_SNAPSHOT_SCHEMA` | Non-null subscription ID/date/status; composite unique `(subscription_id, snapshot_date)`; nullable other state fields. | Existing composite key remains valid per episode when the FK is an episode ID. Column name can remain if semantic contract changes. | Schema cannot determine correct historical episode attribution; RI existence does not solve it. TC-003 is not implemented and needs episode mapping plus date semantics. |
| `USAGE_MONTHLY_SCHEMA` | Non-null subscription ID/month; composite unique `(subscription_id, usage_month)`; count non-negativity and active-users bound; optional non-negative volume. | Existing key remains valid per episode if rows are episode-attributed. | Period cross-boundary and partial-period rules cannot be encoded until DD-EP-009/010 and usage-month semantics are settled; TC-007 remains pending. |
| `INVOICE_SCHEMA` | Unique invoice ID; non-null subscription ID, invoice date, amount, currency and status; invoice due/paid date ordering checks. | Clarify whether invoice FK points to episode ID; add source traceability only if approved. | Correct invoice episode assignment cannot be proven by schema. Existing date checks concern invoice chronology and do not determine episode attribution. |

Existing primary and composite key checks should remain in Pandera; episode DQ rules must not duplicate them. A source-ID uniqueness constraint is not justified until the identifier’s behavior is known. No schema changes are made by this assessment.

## 6. Pipeline and Data Quality Impact

### 6.1 Ingestion, Headers, and Normalization

**CURRENT IMPLEMENTATION:** `DATASET_COLUMNS` in `header_inspection.py` declares exact required/optional columns. Subscriptions currently require `subscription_id`, `customer_id`, `start_date`, and `subscription_status`; dependent datasets require their existing `subscription_id` key. `csv_ingestion.py` requires customers, subscriptions, and snapshots; usage and invoices are optional; CSV values are read as strings. `DATASET_COLUMN_TYPES` in `type_normalization.py` maps known columns to string, datetime, numeric, integer, or boolean types, preserving unknown/missing columns for later validation.

**RECOMMENDATION:** If an approved source ID is added, update contract field definitions, header allowlists, type-normalization mapping, schema, and fixtures together. The generic CSV reader itself does not hard-code individual fields beyond header inspection, but header contracts will reject unregistered fields. Keep episode IDs as strings to preserve exact identifier values and leading zeros.

### 6.2 Referential Integrity

RI-001 compares `subscriptions.customer_id` with `customers.customer_id`; it remains conceptually valid per episode. RI-002, RI-003, and RI-004 compare dependent dataset `subscription_id` values to the subscriptions key set. They remain valid as **existence checks** if dependent rows use episode IDs.

They do not establish that a snapshot, usage record, or invoice is linked to the correct episode. A record can reference an existing but incorrect episode and pass the current check. That limitation is especially important for legacy rows where source IDs are reused. No automatic assignment or correction should be performed by RI validation.

The actual implementation is `validate_referential_integrity()` in `referential_integrity.py`, returning RI-001 through RI-004 findings. Existing unit tests cover matches/orphans, optional datasets, safe errors, key comparisons, and input immutability; they do not prove episode identity or historical mapping correctness.

### 6.3 Temporal Consistency and Future DQ

TC-001 checks `end_date >= start_date`; TC-002 checks `cancellation_date >= start_date`, using present date pairs and null-excluding optional dates. These checks operate within one subscription row and continue to apply to each episode row, subject to the final meanings of episode start/end/cancellation dates.

TC-003 is intended to check that a snapshot does not precede the applicable episode start. It cannot be correctly implemented for ambiguous snapshots until their episode ID and applicable start date are resolvable. TC-007 requires a definition of usage period boundaries and behavior for usage that overlaps episode boundaries. Neither rule should be inferred from date proximity.

**Documentation mismatch:** `data_quality_specification.md` currently marks TC-001/TC-002 specification status `PROPOSED`, while the actual temporal validator returns findings with implementation status `IMPLEMENTED_IN_DQ`. `data_quality_implementation_architecture.md` at Section 2.0/2.1 says the validation package has no validators/models, which is no longer true in the inspected tree. The episode specification Section 9 correctly separates rule specification status from implementation status, but its TC-003/TC-007 status labels should be understood according to that document, not treated as execution status. Reconcile documentation in a separately authorized documentation task.

### 6.4 Future Validation Ownership

- Pandera should own field presence/types/nullability and within-file primary/composite keys.
- RI should own cross-file key existence only; it cannot certify semantic episode attribution absent trustworthy keys/mapping.
- TC-001/002 remain within-episode date ordering checks.
- TC-003 requires reliable snapshot-to-episode mapping and defined start-date meaning.
- TC-007 requires usage-period definitions and an approved cross-episode policy.
- Invoice allocation/episode validation requires explicit source/business semantics before a new rule is specified.

## 7. Migration and Backward Compatibility

Contract v1.1’s versioning policy says breaking changes to required fields, keys, or dataset structure are major-version changes; backward-compatible additions/clarifications are minor; corrections/documentation improvements are patch changes (Section 12). Changing the meaning of `subscription_id` from an unspecified/source “subscription” identifier to an internal episode key can be breaking for clients even if its column name is unchanged. Adding a required source or episode field is also potentially breaking. The appropriate version number must be determined under the policy after the final contract delta is known; no version is assigned here.

| Existing data | Compatibility risk | Safe treatment requirement |
|---|---|---|
| Subscription master rows | One source ID may currently collapse multiple episodes or be reused. Current key uniqueness prevents multiple rows with the same `subscription_id`. | Only split/create episode rows when authoritative episode identity and boundaries are available. Do not fabricate IDs. |
| Historical snapshots | Existing FK may point to a source subscription rather than a specific episode. | Preserve as unresolved or use an explicitly approved, auditable mapping. Date matching alone is insufficient. |
| Usage rows | Monthly record may refer to a source subscription, customer, billing period, or activity period rather than one episode. | Do not attribute a row to an episode until source granularity and crossing-period policy are known. |
| Invoice rows | Invoice FK may identify a source subscription; an invoice could cover multiple services/episodes. | Require explicit invoice-to-episode evidence or approved allocation; do not infer solely from invoice dates. |
| Reactivated customers | Existing records may describe a continuation or a reactivation without episode-level IDs. | Apply the approved new-episode direction only where termination/reactivation and distinct episode identity are evidenced; unresolved history remains unresolved. |
| Fixtures/benchmarks | Existing tests and CSV fixtures use simple subscription IDs and do not exercise multiple episodes, reuse, or ambiguous attribution. No live client or benchmark catalog was verified. | Revise synthetic fixtures and tests with the contract; preserve benchmark provenance and avoid presenting synthetic IDs as migration rules. |

**PENDING DECISION:** DD-EP-012 sets migration acceptance criteria. Until that is resolved, the project cannot state which legacy rows are acceptable, rejectable, quarantined, or excluded. Existing v1.1 compatibility cannot be guaranteed for all source files.

## 8. Outstanding Decisions

The IDs and states below are from Section 11 of the Subscription Episode & Lifecycle Decision Specification. “Blocks contract update” refers to finalizing the relevant contract semantics or fields, not to editing a draft with unresolved items clearly marked. “Blocks implementation” identifies components that cannot safely be finalized without the decision.

| Decision | Why it matters and affected components | Blocks contract update? | Blocks implementation or only specific functionality? |
|---|---|---|---|
| DD-EP-001 — Contractual episode boundary (PENDING_CLIENT_DECISION) | Defines which events begin/end an episode; subscriptions dates/status, snapshots, usage, invoices, and churn labels. | Blocks final lifecycle/date semantics; does not block recording approved high-level episode granularity with open semantics disclosed. | Blocks reliable episode extraction and episode-level temporal attribution. |
| DD-EP-002 — Source subscription ID availability/reuse (PENDING_CLIENT_DECISION) | Determines traceability and whether source keys can be mistaken for episode keys; affects all five datasets and migration. | Blocks deciding source ID fields and requirements. | Blocks source mapping and migration for clients without known source behavior. |
| DD-EP-003 — Internal episode ID generation/ownership (PENDING_PRODUCT_DECISION) | A stable unique episode key is required across repeated loads; affects subscriptions and every dependent FK, ingestion, and normalization. | Blocks finalized identifier ownership/source requirements. | Blocks end-to-end episode ingestion and dependent FK checks. |
| DD-EP-004 — Source-system namespace (PENDING_CLIENT_DECISION) | Same source ID may collide across source systems; affects traceability and source mappings. | Blocks namespace fields only if multi-system traceability is required; not the basic episode model. | Blocks unambiguous cross-system source-key mapping where collisions are possible. |
| DD-EP-005 — Cancellation event semantics (PENDING_CLIENT_DECISION) | Request, effective cancellation, last service day, and termination may differ; affects subscription date fields, TC-002 meaning, and churn labels. | Blocks final date descriptions and cancellation constraints. | Blocks semantic validation and churn qualification; basic ID/key implementation can proceed once identity is resolved. |
| DD-EP-006 — Renewal/extension behavior (PENDING_CLIENT_DECISION) | Determines whether renewal continues or creates an episode; affects subscription rows and historical attribution. | Blocks renewal-specific contract semantics. | Blocks renewal handling only; approved reactivation direction remains distinct. |
| DD-EP-007 — Suspension/pause behavior (PENDING_CLIENT_DECISION) | Determines whether service interruption changes episode lifecycle; affects status/date interpretations and usage periods. | Blocks suspension/pause semantics. | Blocks validation and labels for these states; not episode IDs generally. |
| DD-EP-008 — Snapshot-to-episode attribution (PENDING_CLIENT_DECISION) | Establishes which episode a snapshot describes; affects snapshot FK, RI interpretation, TC-003, and historical features. | Blocks dependable contract requirements for historical snapshot episode keys where source cannot provide them. | Blocks correct historical assignment and TC-003 for ambiguous rows. |
| DD-EP-009 — Usage-to-episode attribution (PENDING_CLIENT_DECISION) | Establishes whether use is measured per episode or source subscription; affects usage FK, RI-003 meaning, and features. | Blocks final usage FK semantics for source data that is not episode-grained. | Blocks reliable episode-level usage features/validation for ambiguous data. |
| DD-EP-010 — Usage periods crossing episodes (PENDING_PRODUCT_DECISION) | Requires period and boundary behavior for partial/cross-episode usage; affects usage contract, TC-007, and feature construction. | Blocks full temporal meaning and cross-boundary usage requirements. | Blocks TC-007 and cross-boundary allocation; basic record ingestion may be possible with unresolved attribution explicitly surfaced. |
| DD-EP-011 — Invoice-to-episode attribution (PENDING_CLIENT_DECISION) | Determines if invoice FK is episode-level and whether an invoice can span episodes; affects invoice contract, RI-004 interpretation, and financial features. | Blocks final invoice FK meaning where source linkage is unclear. | Blocks reliable episode-level invoice features/checks for ambiguous records. |
| DD-EP-012 — Historical migration acceptance (PENDING_PRODUCT_DECISION) | Defines handling of unresolvable legacy records and onboarding criteria; affects migration, ingestion policy, and model eligibility. | Blocks publishing migration/compatibility guarantees, not the logical target model. | Blocks migration and client acceptance policy. |
| DD-EP-013 — Episode-level churn qualification (PENDING_PRODUCT_DECISION) | Defines which termination events label episode churn; affects target construction and episode-labeling outputs. | Blocks final churn target contract, not key structure. | Blocks production churn labels/model target. |
| DD-EP-014 — Customer-level churn, if included (DEFERRED) | Separate definition of customer relationship termination; affects customer-level product outputs. | No, unless customer churn is added to contract scope. | Blocks only customer-level churn functionality. |
| DD-EP-015 — Customer-level risk aggregation (DEFERRED) | Defines aggregation of episode predictions; affects reporting. | No, unless aggregation outputs become a contract deliverable. | Blocks customer-level risk aggregation only. |
| DD-EP-016 — Contract version/backward compatibility (PENDING_PRODUCT_DECISION) | Chooses rollout compatibility and versioning after schema changes are known. | Blocks approving/publishing the revised contract version. | Blocks release/migration compatibility commitments; does not block technical assessment. |
| DD-EP-017 — Model evaluation grouping/temporal strategy (PENDING_PRODUCT_DECISION) | Repeated customer episodes may create dependence/leakage; affects train/test split and model evaluation. | No, except documenting required training metadata if contract scope changes. | Blocks final evaluation protocol, not data schema implementation. |

## 9. Recommended Sequence

1. Resolve the episode boundary and source identity questions (DD-EP-001–004) with representative source data discovery; do not use live client data in development artifacts.
2. Define cancellation and other lifecycle event semantics (DD-EP-005–007), including episode date meanings.
3. Define snapshot, usage, and invoice episode attribution and unresolved-record handling (DD-EP-008–012). Do not substitute date matching for source evidence.
4. Approve the internal episode identifier supply/ownership and source traceability requirements. Clarify ADR-009 to name the contractual episode as the individual prediction entity while preserving customer/account distinction.
5. Produce a contract delta: row grain, keys/FKs, field list, nullability, controlled values, optional datasets, and migration compatibility. Apply the contract’s versioning policy only after breaking changes are enumerated and reviewed.
6. Update the header definitions, normalizer map, Pandera schemas, and synthetic tests together; retain Pandera ownership of per-file keys and keep RI checks focused on cross-file existence.
7. Implement episode attribution and migration acceptance only from approved evidence-based mappings. Extend RI/TC tests for multiple episodes, valid linkage, orphan linkage, and ambiguous records.
8. Implement TC-003 after episode attribution and start-date semantics are reliable. Define usage periods/cross-boundary behavior before TC-007. Decide invoice-related DQ only after invoice attribution semantics are approved.
9. Reconcile the stale DQ documentation statuses and architecture implementation inventory in a separately scoped documentation task.

This is a recommendation, not authorization to implement any step.

## 10. Explicit Scope Exclusions

This assessment does not:

- Modify Customer Data Contract v1.1 or create a new contract version.
- Modify ADR-009, Data Quality documents, schemas, ingestion, normalization, validation code, tests, fixtures, or dependencies.
- Define the source system’s identifier behavior or invent an ID-generation mechanism.
- Assign historical snapshots, usage, or invoices to episodes based on dates, statuses, or other inferred signals.
- Finalize cancellation, renewal, extension, pause, suspension, invoice allocation, or churn-label policies.
- Implement migration, TC-003, TC-007, or any other validation rule.
- Use live client data.

## 11. Verification Notes and Limitations

The assessment is based on repository documents and synthetic tests/code only. No client source-system schemas, client sample data, migration inventory, or external benchmark provenance were available to verify. Therefore source ID reuse, episode-level historical coverage, and availability of dependent-record episode identifiers remain unverified.

No existing files were modified. This assessment is the only new file created for this task. `git diff --check` was run where applicable; because the report is untracked, ordinary `git diff --check` does not inspect its contents. No code changes or tests were run, and no commit or push was performed.
