# Customer Data Contract Semantic Revision Proposal

> **Historical design record.** This document preserves the Phase 02 assessment and its implementation observations at the time of review. For governing requirements, see the [approved Customer Data Contract](customer_data_contract.md) and [ADR-010](../03_architecture/adr_episode_identity_and_identifier_management.md).

**Document ID:** NCI-CONTRACT-SEMANTIC-REVISION-001
**Version:** 0.1
**Status:** Draft for technical review
**Scope:** Phase 2.4.4.5 — Customer Data Contract Semantic Revision
**Assessment date:** 2026-11-15

> **Proposal status:** This document proposes revised contract wording. It is not the approved Customer Data Contract, does not assign a new contract version, and does not authorize implementation.

## 1. Purpose and Scope

This contract defines the CSV data interface proposed for Nowa Customer Intelligence’s initial contractual subscription churn use case. Its purpose is to state dataset grain, identity meaning, field requirements, relationships, availability, and validation responsibilities needed to prepare data for analysis.

The prediction entity is one contractual subscription episode. Model predictions and labels are at episode level. `customer_id` identifies the associated customer/account. Customer-level churn and risk aggregation are outside this initial scope.

The interface retains five datasets: customers, subscriptions, subscription snapshots, monthly usage, and invoices. Customers and subscriptions are required. Under approved PD-006, snapshots are optional for basic ingestion and required for workflows claiming temporal modelling. Usage and invoices are optional.

This is a semantic revision proposal based on approved architecture/product decisions and the current v1.1 contract. It does not finalize CSV field changes, source identifier exchange, episode boundaries, client mappings, Registry design, migration procedures, or a new version. Existing types and nullability are retained below unless a governing decision requires otherwise; no such type/nullability change is proposed here. Pending decisions remain open.

**RECOMMENDATION:** Review the proposed semantic wording against client source evidence and affected consumers before adopting it into a revised contract. Until approval, Contract v1.1 remains authoritative for the interface and the implementation remains unchanged.

## 2. Terminology and Prediction Entity

| Term | Proposed contract meaning | Status |
|---|---|---|
| Customer/account | The customer represented by `customer_id`, which may be associated with multiple contractual episodes. | **APPROVED REQUIREMENT** |
| Contractual subscription episode | One contractual period represented as an independent prediction entity. Reactivation after termination creates a new episode; prior episodes are preserved. | **APPROVED REQUIREMENT**; detailed boundary/event semantics remain unresolved. |
| Canonical episode identifier | Nowa-owned, stable identifier for exactly one episode, represented conceptually by `subscription_id`. | **APPROVED REQUIREMENT**; CSV supply/interface details remain unresolved. |
| Source-system identifier | Identifier assigned by a client/source system. It may refer to a subscription object or episode and must not be assumed to be episode-unique. | Source behavior is a **PENDING DECISION** requiring discovery. |
| Dependent dataset | A snapshot, usage record, or invoice that refers to an episode through `subscription_id`. | Proposed relationship; correct attribution requires evidence, not just key existence. |
| Basic ingestion | Ingestion and validation of required datasets without asserting temporal-modelling eligibility. | Concept governed by approved PD-006; interface details are unresolved. |
| Temporal modelling | A workflow that claims to construct time-aware prediction examples. | Snapshots are required by approved PD-006; coverage and eligibility thresholds remain unresolved. |

The prediction entity is the individual contractual episode, not the customer/account. `customer_id` is not a prediction identifier. One customer may have multiple episode rows and predictions. The current v1.1 contract also states that customer and subscription identifiers are identifiers rather than predictive features; this proposal makes no feature-selection change.

## 3. Dataset Overview and Grain

| Dataset | Conceptual grain | Key | Relationship | Proposed availability |
|---|---|---|---|---|
| `customers.csv` | One row per customer/account. | `customer_id` | Parent of subscriptions. | Required. |
| `subscriptions.csv` | One row per canonical contractual episode. | `subscription_id` | Each episode relates to a customer through `customer_id`. | Required. |
| `subscription_snapshots.csv` | One row per episode per snapshot date. | `(subscription_id, snapshot_date)` | Episode reference through canonical `subscription_id`. | Optional for basic ingestion; required for temporal-modelling workflows. |
| `usage_monthly.csv` | One row per subscription per usage month, as currently specified; future episode attribution must be supported. | `(subscription_id, usage_month)` | Intended to refer to the episode measured. | Optional. |
| `invoices.csv` | One row per invoice. | `invoice_id` | `subscription_id` identifies the episode to which the invoice is attributable. | Optional. |

The five-dataset structure is retained. Monthly date conventions, episode attribution, usage-period coverage, and invoice-to-episode semantics remain subject to the open decisions in Section 15. “Required” is policy-level availability, not a claim that the current loader implements the proposed snapshot behavior.

## 4. Identifier Semantics

### 4.1 `customer_id`

`customer_id` identifies a customer/account. It is the customer primary key and the subscription-to-customer relationship key. It does not identify a contractual episode or serve as the episode prediction identifier. A customer may relate to multiple episodes.

### 4.2 `subscription_id`

`subscription_id` is the Nowa-owned canonical identifier for exactly one contractual episode. It is stable throughout that episode’s lifecycle and must never be reassigned to another episode. UUID is the approved initial generation strategy. A new identifier is issued only after authoritative evidence establishes a new episode; a recognized existing episode reuses its persisted canonical identifier. UUID version and technical generation are not specified here.

### 4.3 Source identifiers

Source-system subscription identifiers and any source-system episode identifiers are distinct from canonical `subscription_id`. The existence, stability, uniqueness scope, reuse behavior, and presence of such identifiers are client/source-specific and require discovery. A reused source identifier alone does not prove that two records refer to the same episode.

The contract may later include a source identifier for traceability if source discovery establishes its meaning and consumers require it. This proposal does not add or mandate a `source_subscription_id` field, a source namespace field, or any universal source identifier.

### 4.4 Dependent references

The `subscription_id` in snapshots, usage, and invoices is intended to reference a canonical episode. Reference existence verifies only that a key is present in the parent dataset; it does not prove that the source record belongs to that episode. Correct attribution requires reliable source evidence or an approved, traceable mapping.

## 5. Dataset Definitions

The field tables below preserve Contract v1.1 field names, data types, and requiredness. The proposed semantic clarification is marked explicitly. No additional fields are approved by this proposal.

### 5.1 Customers

**File:** `customers.csv`
**Purpose:** Customer/account attributes.
**Grain:** One record per customer/account.
**Primary key:** `customer_id`
**Availability:** Required.

| Field | Data type | Required | Proposed meaning / existing semantics |
|---|---|---:|---|
| `customer_id` | string | Yes | Unique customer/account identifier. |
| `created_at` | date/datetime | Yes | Date the customer account was created. |
| `country` | string | No | Customer country. |
| `industry` | string | No | Customer industry. |
| `company_size` | string | No | Customer company-size category. |
| `account_status` | string | No | Current customer-account status. |

Every supplied `customer_id` must be unique and non-null. `created_at` must be valid and not later than the agreed extraction date. Customer categorical values must be consistent. Every subscription episode references a customer. Contract v1.1 also says each customer must be referenced by a subscription; its reverse-reference rule remains `RI-005 — PROPOSED`, not implemented. Client category values and future-field choices remain subject to discovery. No episode ID is added to this dataset.

### 5.2 Subscriptions

**File:** `subscriptions.csv`
**Purpose:** Episode master and contractual characteristics.
**Proposed grain:** One record per canonical contractual episode.
**Primary key:** Canonical episode identifier `subscription_id`.
**Foreign key:** `customer_id` references `customers.customer_id`.
**Availability:** Required.

| Field | Data type | Required | Proposed meaning / existing semantics |
|---|---|---:|---|
| `subscription_id` | string | Yes | Unique, stable Nowa-owned canonical identifier for exactly one episode. |
| `customer_id` | string | Yes | Associated customer/account identifier. |
| `plan_id` | string | No | Subscription plan identifier. |
| `start_date` | date | Yes | Subscription/episode start date; exact event semantics remain open. |
| `end_date` | date | No | Subscription/episode end date, if applicable; termination semantics remain open. |
| `subscription_status` | string | Yes | Current subscription status; source mapping remains subject to DD-007. |
| `billing_frequency` | string | No | Billing frequency. |
| `recurring_revenue` | decimal | No | Current recurring revenue amount; MRR/ARR/other basis remains open. |
| `currency` | string | No | Currency code; conversion and complete membership policy remain open. |
| `auto_renew` | boolean | No | Whether automatic renewal is configured. |
| `cancellation_date` | date | No | Date cancellation became effective, if applicable; effectiveness semantics remain open. |
| `cancellation_reason` | string | No | Recorded cancellation reason. |

The schema-level requirement for `subscription_id` uniqueness applies to episode records in a dataset; persistent identity across submissions is an architectural requirement and is not provided by frame-level uniqueness alone. `customer_id` must be non-null and reference a customer. `start_date` must be valid; `end_date` and `cancellation_date`, when present, must not precede `start_date`; recurring revenue must be non-negative; currency must satisfy the contract’s currency requirement; and `auto_renew`, when present, must be boolean. Contract v1.1 lists `active`, `trial`, `cancelled`, `expired`, `suspended`, and `paused` as provisional subscription statuses and requires client statuses to be mapped during discovery. A recognized episode reuses its persisted ID. Reactivation after termination creates a separate episode and ID; the previous row/history is retained. Renewal, extension, pause, suspension, cancellation effectiveness, and exact episode boundary rules remain unresolved. No source identifier field is added.

### 5.3 Subscription Snapshots

**File:** `subscription_snapshots.csv`
**Purpose:** Historical observations of episode state.
**Proposed grain:** One record per canonical episode per snapshot date.
**Composite primary key:** `(subscription_id, snapshot_date)`.
**Foreign key:** `subscription_id` references a contractual episode.
**Availability:** Optional for basic ingestion; required for temporal-modelling workflows.

| Field | Data type | Required | Proposed meaning / existing semantics |
|---|---|---:|---|
| `subscription_id` | string | Yes | Canonical episode identifier to which the snapshot is attributable. |
| `snapshot_date` | date | Yes | Date on which the episode state was observed. |
| `subscription_status` | string | Yes | Status at the snapshot date. |
| `recurring_revenue` | decimal | No | Recurring revenue at the snapshot date. |
| `currency` | string | No | Currency code. |
| `plan_id` | string | No | Plan at the snapshot date. |
| `billing_frequency` | string | No | Billing frequency at the snapshot date. |
| `auto_renew` | boolean | No | Automatic-renewal configuration at the snapshot date. |

The composite key prevents duplicate episode/date rows. It does not establish that historical rows were attributed to the correct episode. Snapshot status must use an accepted or mapped category; recurring revenue, when present, must be non-negative; currency must satisfy the contract’s currency requirement. Snapshot dates must follow a consistent monthly convention and not exceed the agreed extraction cutoff, but the convention and cutoff remain undecided. A snapshot must represent the state at its observation date and must not contain information available only later; current fields may not suffice to verify availability time. Historical states must not be overwritten with current values. No first-of-month or last-of-month convention is assumed. Snapshot-to-episode evidence and minimum history remain unresolved.

Contract v1.1 lists `active`, `trial`, `cancelled`, `expired`, `suspended`, and `paused` as provisional snapshot statuses. Client-specific values require mapping during discovery.

### 5.4 Monthly Usage

**File:** `usage_monthly.csv`
**Purpose:** Monthly subscription usage behavior.
**Current/proposed grain:** One record per subscription per usage month; episode attribution must be evidenced.
**Composite primary key:** `(subscription_id, usage_month)`.
**Foreign key:** `subscription_id` is intended to reference the episode measured.
**Availability:** Optional.

| Field | Data type | Required | Proposed meaning / existing semantics |
|---|---|---:|---|
| `subscription_id` | string | Yes | Canonical episode identifier, only where supported by attribution evidence. |
| `usage_month` | date | Yes | Month represented by the usage record; exact period boundaries/availability remain open. |
| `active_users` | integer | No | Number of active users. |
| `total_users` | integer | No | Total number of users. |
| `sessions_count` | integer | No | Number of sessions. |
| `events_count` | integer | No | Number of recorded events. |
| `usage_volume` | decimal | No | Total usage volume. |
| `usage_metric` | string | No | Description or unit of usage volume. |

The composite key is retained. Count fields must be non-negative integers; `active_users` must not exceed `total_users` when both are available; and `usage_volume`, when present, must be non-negative. Usage records must correspond to valid subscription periods, but usage-period meaning, rows crossing episode boundaries, temporal availability, and reliable usage-to-episode attribution remain unresolved. No allocation or splitting rule is introduced.

### 5.5 Invoices

**File:** `invoices.csv`
**Purpose:** Billing and payment information.
**Grain:** One record per invoice.
**Primary key:** `invoice_id`.
**Foreign key:** `subscription_id` is intended to identify the attributable contractual episode.
**Availability:** Optional.

| Field | Data type | Required | Proposed meaning / existing semantics |
|---|---|---:|---|
| `invoice_id` | string | Yes | Unique invoice identifier. |
| `subscription_id` | string | Yes | Canonical episode identifier only where invoice attribution is supported. |
| `invoice_date` | date | Yes | Invoice issue date. |
| `due_date` | date | No | Invoice due date. |
| `paid_date` | date | No | Date the invoice was paid. |
| `amount` | decimal | Yes | Invoice amount. |
| `currency` | string | Yes | ISO 4217 currency code as specified in v1.1. |
| `invoice_status` | string | Yes | Invoice payment status. |

The invoice key and fields remain as specified. `invoice_id` must be unique and non-null; `subscription_id` must be non-null; `invoice_date` must be valid; `due_date` and `paid_date`, when present, must not precede `invoice_date`; `amount` must be non-negative; currency and status must use accepted values. Contract v1.1 lists `paid`, `pending`, `overdue`, `failed`, `void`, and `refunded` as provisional invoice statuses and requires client-specific mapping during discovery. Invoice-to-episode attribution, historical linkage, service-period semantics, and invoices covering multiple episodes remain unresolved. Invoice date alone is not attribution evidence. This proposal defines no financial allocation or reconciliation rule.

## 6. Episode Identity and Lifecycle Principles

The following are **APPROVED REQUIREMENTS**:

1. When authoritative evidence establishes a new episode, one canonical ID may be issued and persisted.
2. When an existing episode is reliably recognized, reuse its persisted canonical `subscription_id`; do not issue a replacement merely because a file was resubmitted.
3. Reactivation following termination creates a new episode and canonical ID. Preserve the previous episode and its history.
4. A new CSV row or previously unseen source identifier alone is not proof of a new episode.
5. Ambiguous, conflicting, or insufficient identity evidence must remain unresolved; do not silently issue, reuse, or reassign identity.
6. Dates, status, row order, heuristics, and a reused source identifier alone do not establish identity.
7. Mapping corrections must be traceable and auditable and must preserve previous mapping lineage.

**PENDING DECISION:** Exact episode boundaries; cancellation/termination effectiveness; renewal and extension; suspension and pause; source lifecycle meanings; and contextual evidence sufficient to recognize episodes. This proposal does not establish those policies. The persistent, client-isolated Episode Identity Registry is required by ADR-010; PD-001 defines product-level functional outcomes only. No Registry technical design or implementation is specified.

## 7. Dataset Availability

The proposed availability policy follows approved PD-006:

| Dataset | Proposed availability |
|---|---|
| `customers.csv` | Required. |
| `subscriptions.csv` | Required. |
| `subscription_snapshots.csv` | Optional for basic ingestion; mandatory for a workflow claiming temporal modelling. |
| `usage_monthly.csv` | Optional. |
| `invoices.csv` | Optional. |

Dataset presence, ingestion success, Data Quality acceptance, and eligibility for a modelling use are separate concepts. Missing optional data is not zero activity or zero value. Presence of snapshots alone does not establish useful history or model eligibility. No technical workflow-selection interface or numeric temporal-eligibility threshold is defined here.

**CURRENT IMPLEMENTATION:** `ingest_client_datasets()` still requires customers, subscriptions, and snapshots unconditionally; usage and invoices are optional. The loader/header code has not been changed by PD-006 approval. The proposed policy requires separate authorized design and implementation work.

## 8. Missing, Empty, and Invalid Datasets

| Condition | Contract distinction and proposed treatment |
|---|---|
| File absent | Dataset was not supplied. Apply the availability policy in Section 7. Absence is not zero activity and is not a schema or DQ pass. |
| File present with header but no records | Dataset was supplied but contains zero rows. This is distinct from absence; acceptance and use-specific adequacy remain unresolved. |
| File present with records | Data is supplied; it must still pass structural, type, schema, and applicable DQ validation. Presence is not acceptance. |
| File present but invalid | A supplied file fails a responsible validation stage. Do not silently skip an invalid optional file or treat it as absent. |

The policy for accepting a present empty file remains **PENDING DECISION**. Neither absence nor an empty file may be interpreted as zero activity, zero value, or adequate historical coverage.

## 9. Data Types and Nullability

The proposed semantic revision retains Contract v1.1’s types and requiredness shown in Section 5. It does not authorize a type, nullability, column, controlled-value, or format change. The existing general CSV conventions remain proposed for retention: UTF-8, comma delimiter, header required, empty fields for missing values, identifiers as strings, decimal period, ISO 8601 dates, `true`/`false` booleans, UTC timestamps where time is present, and lowercase `snake_case` column names.

The following discrepancies must remain visible for later resolution:

- Contract v1.1 describes currency as ISO 4217. Current schemas check only three uppercase letters; format does not establish membership in the currency list.
- Contract v1.1 calls subscription/invoice status lists provisional and expects client mapping during discovery; schemas directly enforce canonical allowed values. Mapping is not implemented by the schemas and DD-007 remains open.
- The current subscription/snapshot status list is `active`, `trial`, `cancelled`, `expired`, `suspended`, `paused`; the current invoice status list is `paid`, `pending`, `overdue`, `failed`, `void`, `refunded`. These are Contract v1.1 values, not new mappings or status decisions in this proposal.
- Normalization parses dates/timestamps into UTC-aware pandas datetime values; contract field tables use date types for most fields and separately permit ISO datetime conventions. Exact date versus timestamp field semantics should be made consistent without changing source requirements silently.
- The contract’s pipeline diagram places normalization differently from the implemented order. Current code normalizes before Pandera schema validation.
- Pandera schemas use `strict=True`, `coerce=False`, and `add_missing_columns=True`; optional declared columns can be added as null, but unexpected columns are rejected and header inspection independently requires contract-required headers.

**CURRENT IMPLEMENTATION:** Identifiers are read as strings and schema checks reject null/empty/whitespace-invalid identifiers without trimming them. Numeric, boolean, and date values are normalized before schema validation. No UUID version or canonical-ID format check is implemented or approved here.

## 10. Keys and Relationships

The proposed conceptual relationships are:

```text
customers.customer_id
        1
        |
        +----< subscriptions.customer_id
                    |
                    | canonical episode subscription_id
                    +----< subscription_snapshots.subscription_id
                    +----< usage_monthly.subscription_id
                    +----< invoices.subscription_id
```

- `customers.customer_id` is the customer primary key.
- `subscriptions.subscription_id` is the canonical episode primary key; `subscriptions.customer_id` references a customer.
- `(subscription_id, snapshot_date)` is the snapshot composite key.
- `(subscription_id, usage_month)` is the usage composite key.
- `invoice_id` is the invoice primary key; invoice `subscription_id` is an episode reference where attribution is supported.

Pandera owns within-frame primary/composite uniqueness and relationship-field nullability. DQ RI-001–RI-004 owns cross-frame foreign-key existence. A matching key proves existence only; it does not prove that a snapshot, usage period, or invoice belongs to that particular episode. Correct historical attribution and identity resolution are separate and require reliable source evidence or an approved traceable mapping. No attribution, allocation, or splitting policy is invented here.

## 11. Validation Responsibilities

| Layer | Responsibility | Proposed contract boundary |
|---|---|---|
| Header inspection | Inspect CSV header structure, expected columns, duplicates, and unexpected fields. | Enforce the contract’s registered column names; no row-level semantic validation. |
| CSV ingestion | Read supplied CSVs, preserve source strings, detect malformed rows, and apply dataset availability requirements. | Do not normalize IDs or infer episode identity. Current snapshot requiredness differs from proposed policy. |
| Type normalization | Convert known source strings to declared pandas types. | Type conversion only; no cross-file identity or business interpretation. |
| Pandera schema validation | Validate per-frame types, nullability, keys, controlled values, and supported in-frame rules. | Own schema checks; DQ must not duplicate them. |
| Data Quality validation | Validate approved cross-dataset reference existence and implemented temporal rules. | Do not infer identity or correct episode attribution from FK existence. Do not claim unimplemented report/coordinator behavior. |

**CURRENT IMPLEMENTATION:** The executable order is header inspection, ingestion, type normalization, Pandera validation, then the available DQ rule functions. RI-001–RI-004 and TC-001/TC-002 are implemented. Data Quality model classes exist, but full report construction, public coordinating interface, and reporting/orchestration are not implemented. The contract’s pipeline depiction differs and should be reconciled in a later contract revision; this proposal does not claim code follows every illustrated stage boundary.

RI-005 and BR-006 remain `PROPOSED`; their business behavior must not be claimed as executed. TC-003 and TC-007 remain `PENDING_DECISION`, and other pending/deferred DQ rules retain the statuses in the Data Quality Specification. Optional dataset absence is non-blocking by approved policy, but BR-006 runtime reporting is not implemented. DQ must not duplicate Pandera-owned key, type, nullability, or in-frame checks.

## 12. Historical Data and Migration Principles

Approved PD-003, PD-004, and PD-005 constrain historical use:

- Repeated submission is not evidence of a new episode. Reuse persisted canonical IDs for reliably recognized episodes.
- A new ID requires authoritative evidence of a new episode; do not fabricate or heuristically assign identity or boundaries.
- Preserve historical episodes, canonical IDs, source lineage, evidence, and mapping correction history.
- Keep ambiguous, conflicting, or insufficiently attributable records unresolved and exclude them from identity-dependent processing until an appropriate disposition is established.
- Partially accept only sufficiently attributable history, with traceable evidence and explicit exclusions. Partial acceptance is not complete historical coverage or full-population representation.
- Assess history separately for its intended use; missing history is not zero activity or proof an episode did not exist.

Client-specific evidence thresholds, accepted historical crosswalks, exact exclusions, migration tooling, and operational workflows are not defined. Migration is not implemented or authorized by this proposal.

## 13. Temporal and Attribution Limitations

The following matters remain unresolved and must not be converted into implied contract requirements:

| Topic | Limitation / decision dependency |
|---|---|
| Snapshot date convention | DD-001 remains open; do not assume first or last day of month. |
| Snapshot historical coverage | DD-002 remains open; no minimum-history threshold is set. |
| Snapshot-to-episode attribution | DD-EP-008 remains `PENDING_CLIENT_DECISION`; FK existence is not sufficient. |
| Usage period semantics | DD-EP-009 remains `PENDING_CLIENT_DECISION`; exact period start/end and availability are not established by the month field. |
| Usage crossing episode boundaries | DD-EP-010 remains `PENDING_PRODUCT_DECISION`; no split/allocation policy is defined. TC-007 remains `PENDING_DECISION`. |
| Invoice-to-episode attribution | DD-EP-011 remains `PENDING_CLIENT_DECISION`; invoice dates alone do not prove linkage, and multi-episode invoices have no allocation rule. |
| Timezone and cutoff | DD-010 remains open for agreed timezone/cutoff semantics. |
| Point-in-time availability | DD-011 remains open; current fields may not provide recording/availability timestamps. |
| Lifecycle chronology | TC-001/002 check only their approved date ordering. TC-003 and TC-007 are not executable until their attribution and period semantics are settled. |

No prediction cutoff, new temporal validation rule, or client-specific attribution behavior is added here.

## 14. Compatibility and Versioning

PD-007 Option C applies: prefer backward-compatible additions or clarifications only when genuinely safe; classify breaking semantic or structural changes based on the exact delta and affected consumers. A change to field meaning or supply mechanism can be breaking even if its name remains unchanged. Strict headers, schemas, and consumers must be included in the review.

This is a **proposed semantic revision**. It does not assign a new contract version, approve a release, or resolve the `1.1` versus `1.1.0` version-notation inconsistency. Potential compatibility concerns include:

| Proposed change | Preliminary risk |
|---|---|
| Clarify subscription row grain as one canonical episode | Potentially breaking semantic change if source/consumer grain differs. |
| Define canonical semantics/supply for `subscription_id` | Potentially breaking even without a column-name change. |
| Clarify dependent references as canonical episode IDs | Potentially breaking key meaning and historical mappings. |
| Add an optional source identifier | Structurally additive but may break strict consumers that reject unknown columns; field itself is not approved. |
| Change snapshot availability for basic ingestion | Approved policy, but may alter loader and consumer behavior; compatibility must be assessed. |
| Any required field or altered type/nullability | Likely structural break; none is proposed here. |

Before version assignment, review the exact contract diff, producers, strict consumers/validators, dependent references, migration scope, and release/deprecation needs; then resolve DD-EP-016 in its governing process. Contract v1.1 remains the current approved interface until separately revised and approved.

## 15. Open Decisions and Limitations

| Decision | Status | Contract impact |
|---|---|---|
| DD-EP-001 episode boundary | `PENDING_CLIENT_DECISION` | Source lifecycle evidence needed to define episode start/end. |
| DD-EP-002 source subscription ID availability/reuse | `PENDING_CLIENT_DECISION` | No source-ID field can be required without discovery. |
| DD-EP-003 remaining Registry design | `PENDING_PRODUCT_DECISION` (partially resolved by ADR-010/PD-001) | Registry architecture and product functions approved; detailed technical and operational design and CSV identity exchange remain open. |
| DD-EP-004 source namespace | `PENDING_CLIENT_DECISION` | Namespace representation/need requires source topology discovery. |
| DD-EP-005/006/007 lifecycle semantics | `PENDING_CLIENT_DECISION` | Cancellation, renewal/extension, pause/suspension; approved reactivation direction does not settle all events. |
| DD-EP-008 snapshot attribution | `PENDING_CLIENT_DECISION` | Requires reliable source linkage. |
| DD-EP-009 usage attribution | `PENDING_CLIENT_DECISION` | Requires usage grain and episode evidence. |
| DD-EP-010 crossing usage periods | `PENDING_PRODUCT_DECISION` | No allocation/splitting policy. |
| DD-EP-011 invoice attribution | `PENDING_CLIENT_DECISION` | Requires invoice source/service-period evidence. |
| DD-EP-012 migration acceptance | `PENDING_PRODUCT_DECISION` | PD-005 principles approved; client coverage and evidence remain contextual. |
| DD-EP-013 episode-level churn qualification | `PENDING_PRODUCT_DECISION` | Churn event definition is not settled by structural contract design. |
| DD-EP-014/015 customer churn/risk | `DEFERRED` | Outside initial episode-level scope. |
| DD-EP-016 contract compatibility/versioning | `PENDING_PRODUCT_DECISION` | Exact delta and consumer impacts needed; PD-007 principles are approved. |
| DD-EP-017 evaluation grouping/temporal strategy | `PENDING_PRODUCT_DECISION` | Downstream modelling dependency, not a prerequisite for every contract semantic clarification. |
| DD-001 snapshot convention | Open in v1.1 | No first/last-day convention. |
| DD-002 historical coverage | Open in v1.1 | No minimum history requirement. |
| DD-003 churn definition | Open in v1.1 | Client contractual events and qualifying churn remain unresolved (also DD-EP-013). |
| DD-004 reactivation | Open in v1.1; direction superseded by approved EP-DEC-005 | Reactivation following termination creates a new episode; source termination/effectiveness criteria remain unresolved. |
| DD-005 contract renewal | Open in v1.1 | Renewal/extension lifecycle treatment remains unresolved. |
| DD-006 subscription episodes | Open in v1.1; canonical episode identity approved | Canonical IDs identify one episode; source lifecycle/boundary and legacy representation remain unresolved. |
| DD-007 subscription status | Open in v1.1 | Client-specific mapping to provisional canonical values. |
| DD-008 revenue definition | Open in v1.1 | MRR/ARR/other recurring revenue meaning. |
| DD-009 currency handling | Open in v1.1 | Currency conversion and complete code-membership policy. |
| DD-010 timezone | Open in v1.1 | Agreed timezone and extraction cutoff. |
| DD-011 historical availability | Open in v1.1 | Recording/availability timestamps and point-in-time evidence. |
| DD-012 prediction horizon | Open in v1.1 | Provisional 30-day horizon not confirmed. |
| DD-013 observation window | Open in v1.1 | Provisional 90-day window not confirmed. |
| DD-014 customer aggregation | Open in v1.1; customer-level scope **DEFERRED** by DD-EP-014/015 | No customer-level churn or risk aggregation in initial episode scope. |
| DD-015 missing data | Open in v1.1 | No completeness thresholds. |
| Empty-file policy | Unresolved | Acceptance of present header-only files is not determined. |

These statuses are transcribed as open/deferred from their governing registers. Approval of PD-001–PD-007 does not automatically resolve the listed DD items. No live client evidence was available for this proposal.

## 16. Change Summary Against v1.1

| Area | Current v1.1 | Proposed wording | Approval status | Compatibility concern |
|---|---|---|---|---|
| Prediction entity and episode grain | Individual subscription; one row per subscription. | One contractual episode is the independent prediction entity; one subscription row represents one canonical episode. | Episode semantics approved; exact contract revision not approved. | Potentially breaking if source grain or consumers differ. |
| `customer_id` | Customer associated with a subscription. | Customer/account identifier distinct from episode and prediction identity. | Approved requirement. | Low if current use already matches. |
| `subscription_id` | Unique subscription identifier. | Nowa-owned canonical ID for exactly one stable episode; generated once after authoritative evidence and reused. | Approved by ADR-010/PD-002; CSV exchange details open. | Semantic/supply change may break existing integrations. |
| Reactivation | Open in v1.1 DD-004. | Reactivation following termination creates a new episode; preserve previous episode. | EP-DEC-005 approved; event criteria remain open. | May require splitting existing histories; evidence and migration risk. |
| Historical preservation | Historical states preserved in snapshots; episode identity not explicit. | Preserve prior episodes, IDs, records, and mapping lineage; no silent replacement/correction. | EP-DEC-003, ADR-010, PD-001/004 approved. | Migration/crosswalk impact. |
| Snapshot availability | Required for temporal modelling; current loader requires unconditionally. | Optional for basic ingestion; mandatory for temporal-modelling workflows. | PD-006 approved; implementation not authorized. | Behavior/consumer compatibility and workflow definition. |
| Usage/invoice availability | Optional. | Remain optional; absence distinct from empty and invalid. | Current contract retained; absence must not imply zero. | Empty-file/reporting handling remains open. |
| Dependent references | Child `subscription_id` must exist in subscriptions. | Reference canonical episode and be correctly attributable; FK existence alone is insufficient. | Canonical key approved; attribution pending. | Potentially breaking key-semantic migration. |
| Source identifiers/namespace | Not defined as contract fields. | Keep conceptual distinction; consider exchange only after source discovery. | Pending; no field approved. | Optional field may still break strict headers; required fields would be breaking. |
| Types, nullability, and fields | v1.1 field tables. | Retain existing fields/types/nullability in this proposal. | No change approved. | Any later exact changes require PD-007 assessment. |
| Validation ownership | General validation requirements and pipeline diagram. | Separate header, ingestion, normalization, Pandera, and DQ responsibilities; no duplicate schema checks. | Current implementation evidence; contract wording proposed. | Diagram/order and current loader mismatch must be reconciled. |

**Proposal limitation:** This comparison describes proposed semantics only. It is not an approval, implementation instruction, final CSV schema, or new contract version. No existing contract, code, schema, test, Registry, or migration behavior is changed by this document.
