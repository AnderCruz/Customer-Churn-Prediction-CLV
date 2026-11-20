# Customer Data Contract Design Proposal

> **Historical design record.** This document preserves the Phase 02 assessment and its implementation observations at the time of review. For governing requirements, see the [approved Customer Data Contract](customer_data_contract.md) and [ADR-010](../03_architecture/adr_episode_identity_and_identifier_management.md).

**Document ID:** NCI-CONTRACT-DESIGN-PROPOSAL-001
**Version:** 0.1
**Status:** Draft for technical review
**Scope:** Phase 2.4.4.4 — Customer Data Contract Design
**Assessment date:** 2026-11-15

## 1. Executive Summary

Customer Data Contract v1.1 defines a useful five-CSV interface for subscription-level contractual churn, but its “one record per subscription” grain and `subscription_id` description do not explicitly establish the durable identity of an individual contractual episode. Approved ADR-010 and EP-DEC-001–005 establish that an episode is the prediction entity, `customer_id` identifies its customer/account, and `subscription_id` is the Nowa-owned canonical identifier for exactly one episode. Reactivation following termination creates a new episode, while earlier episodes and identity history are preserved.

This proposal translates those approvals and PD-001–PD-007 into a target conceptual contract: one canonical episode per subscription row; dependent datasets refer to canonical episode IDs only when their attribution is supported; optional dataset availability is separated from data quality and modelling eligibility; and identifier provenance, ambiguity, repeat submissions, and migration are treated explicitly. It does not define a final CSV schema.

Important dependencies remain open. Client source-ID availability/reuse, namespaces, lifecycle boundaries, snapshot/usage/invoice attribution, usage periods crossing episodes, snapshot convention, historical coverage, and exact consumer compatibility require discovery or decisions. PD-006 approves snapshots as optional for basic ingestion and mandatory for temporal-modelling workflows, but the current loader still requires them unconditionally. No approval authorizes code changes, a Registry implementation, source mapping, migration tooling, or a contract revision. This document is a design proposal, not an approved or versioned replacement contract.

## 2. Design Objectives and Non-Goals

### Objectives

- Make the approved episode-level prediction unit and canonical identifier semantics explicit in a future contract.
- Keep customer, episode, and source-system identities distinct.
- Define conceptual dataset grain and key relationships without inventing client source behavior.
- Preserve identity across repeat submissions and preserve previous episodes and mapping lineage.
- Keep existence validation, identity resolution, temporal consistency, and model eligibility separate.
- Align future dataset availability language with PD-006 and expose current implementation gaps.
- Provide a basis for exact-delta compatibility review under PD-007.

### Non-goals

This proposal does not implement or design the Episode Identity Registry’s database, storage, APIs, transactions, deployment, or operational workflows. It does not perform client-specific source mapping; train models or engineer features; define customer-level churn or risk aggregation (DD-EP-014/015 remain **DEFERRED**); implement migration; settle pending lifecycle, attribution, or temporal decisions; set historical coverage/training thresholds; or assign a contract version. It does not prescribe source fields or produce a final CSV schema.

## 3. Governing Decisions and Design Constraints

Approved decisions are binding constraints, but do not imply implementation authorization. Recommendations below remain proposals.

| Authority | Status | Contract design implication |
|---|---|---|
| ADR-009 — Subscription-Level Churn Prediction | Accepted | Preserve the individual subscription episode as prediction entity and `subscription_id` as prediction key; customer aggregation is not the prediction unit. |
| ADR-010 — Subscription Episode Identity and Identifier Management | Accepted | Nowa owns canonical episode identity; UUID is the initial strategy; IDs are created once for authoritatively established new episodes, persisted and reused; a persistent, client-isolated Registry is required; ambiguity is not silently resolved. Detailed technical design remains open. |
| EP-DEC-001 — Customer Identity | Approved | `customer_id` identifies the customer/account and remains distinct from episode identity. |
| EP-DEC-002 — Episode as Prediction Entity | Approved | One contractual episode is one independent prediction entity; a customer may have multiple episodes. |
| EP-DEC-003 — Historical Episode Preservation | Approved | Previous episodes and their historical identity must be preserved. |
| EP-DEC-004 — Customer/Episode Relationship | Approved | A customer may relate to multiple episodes; do not collapse episode identity into customer identity. |
| EP-DEC-005 — Reactivation | Approved | Reactivation following termination creates a new episode; detailed event criteria remain open. |
| PD-001 — Registry Functional Requirements | Approved, Option B | Require conflict detection, unresolved-identity visibility, traceable corrections, auditable identity/mapping history, and preservation of previous mapping lineage. No Registry implementation/workflow design is approved. |
| PD-002 — Canonical ID Issuance | Approved, Option B | Issue a new canonical ID only after authoritative evidence establishes a new episode; reuse persisted IDs for recognized episodes. A new row alone or weak signals are not proof. |
| PD-003 — Ambiguous Identity Handling | Approved, Option C | Isolate unresolved/ambiguous/conflicting records and exclude them from identity-dependent processing; preserve traceability. |
| PD-004 — Repeated CSV Submissions | Approved, Option C | A received file is a new submission event, not proof of new episodes. Reimport alone never justifies replacement IDs; preserve history. |
| PD-005 — Historical Migration | Approved, Option B | Partial acceptance is allowed only for sufficiently attributable history, with lineage, explicit exclusions, and separate intended-use suitability assessment. No fabrication or heuristic attribution. |
| PD-006 — Dataset Availability | Approved, Option B | Snapshots are optional for basic ingestion and mandatory for temporal-modelling workflows. Absence is not zero; ingestion, DQ acceptance, and modelling eligibility are distinct. No implementation or threshold is approved. |
| PD-007 — Compatibility | Approved, Option C | Prefer genuinely safe backward-compatible changes; assess exact semantics, structure, consumers, validators, and migration before classifying or assigning a version. |

**RECOMMENDATION:** Use these approvals to state target semantics, while leaving source-field representation, lifecycle evidence, and interface mechanics explicitly open. Contract v1.1 remains the current contract until a separately reviewed revision is approved.

## 4. Target Data Model and Dataset Grain

The following is a conceptual target, not a final field-level schema. “Required” and “optional” distinguish approved/product policy from current loader behavior.

| Dataset | Purpose and proposed grain | Key and relationships | Target availability | Unresolved questions |
|---|---|---|---|---|
| `customers.csv` | Customer/account attributes; one row per customer/account. | Primary key `customer_id`; referenced by subscriptions. | Required under v1.1. | Client customer key semantics and source mapping remain subject to discovery. |
| `subscriptions.csv` | Contractual episode master/current attributes; exactly one canonical episode per row. | Primary key canonical `subscription_id`; required relationship to `customer_id`. | Required under v1.1. | Episode boundaries and lifecycle event meaning; canonical ID exchange/persistence interface; source identity evidence. |
| `subscription_snapshots.csv` | Historical episode state at an observation date; one record per canonical episode/date. | Composite key `(subscription_id, snapshot_date)`; `subscription_id` references an episode. | Optional for basic ingestion; mandatory for temporal modelling (PD-006). | Snapshot date convention, historical attribution, cutoff, coverage, availability semantics. |
| `usage_monthly.csv` | Usage observations; contract currently states one record per subscription/month. | Composite key `(subscription_id, usage_month)`; target reference is canonical episode ID. | Optional under v1.1 and retained as optional. | Actual usage grain, covered period, attribution and crossing-episode treatment. |
| `invoices.csv` | Invoice records; one record per invoice. | Primary key `invoice_id`; target `subscription_id` references canonical episode where attribution is evidenced. | Optional under v1.1 and retained as optional. | Invoice-to-episode relationship, service periods, multi-episode invoices, source traceability. |

### Relationship concept

`customers.customer_id` identifies an account and may be referenced by multiple episode rows. Each `subscriptions.subscription_id` identifies exactly one canonical contractual episode. Snapshot, usage, and invoice references are intended to identify the episode to which the record is actually attributable, not merely any existing ID. Existence checks cannot prove correct historical attribution.

## 5. Canonical and Source Identifier Design

| Identifier concept | Proposed contractual meaning | Status and limit |
|---|---|---|
| `customer_id` | Customer/account identity. | **APPROVED REQUIREMENT**; not the prediction identifier. |
| `subscription_id` | Nowa-owned canonical ID for exactly one contractual episode; stable, persistent, never reassigned, and reused when an existing episode is recognized. | **APPROVED REQUIREMENT**. UUID initial generation strategy approved; UUID version and technical implementation are open. The CSV exchange/supply mechanism is not specified here. |
| Source-system subscription identifier | Identifier for a source subscription object or relationship. | May be reused, scoped, absent, or otherwise client-specific. It must not be assumed to identify an episode. |
| Source-system episode identifier | Source key that may specifically identify one episode, if provided. | Availability and reliability require source discovery; not assumed. |
| Source-system namespace | Provenance/mapping context that can distinguish identifier domains. | Separate from canonical ID and client isolation. Its representation and requiredness are unresolved. |
| Dependent reference | Child dataset’s reference to the canonical episode. | A valid existing value establishes key existence only. Reliable evidence is required to establish correct episode attribution. |

Whether source identifiers should appear in CSV exchange is a design question for later discovery and interface work. The episode specification recommends preserving source identifiers when available, but does not approve or mandate a `source_subscription_id` column. This proposal does not introduce a namespace field, universal source-ID requirement, UUID version, generation instructions, or Registry schema. Conceptual identity architecture must not be mistaken for a finalized exchange format.

## 6. Dataset-by-Dataset Target Design

### 6.1 Customers

- **Current v1.1:** One customer row, primary key `customer_id`, with required `created_at` and optional customer attributes.
- **Conceptual target:** Retain one account/customer per row. Do not add episode identity to customer records.
- **Unchanged meaning:** `customer_id` remains customer/account identity; subscription episodes relate to customers through this value.
- **Potential additions:** None proposed. Source identifier additions would require evidence and a separate exact-delta review.
- **Keys and compatibility:** Existing customer key remains. No episode relationship is inferred from customer attributes.
- **Pending/deferred:** Client key semantics need discovery. Customer-level churn and risk aggregation remain **DEFERRED**.

### 6.2 Subscriptions

- **Current v1.1:** One row per subscription; `subscription_id` unique; `customer_id` FK; current status and lifecycle/revenue attributes.
- **Conceptual target:** One row per canonical contractual episode. `subscription_id` identifies that episode, not an unverified source subscription object. `customer_id` identifies its associated account.
- **Unchanged field candidates:** Existing lifecycle and descriptive fields may remain, but exact interpretation of `start_date`, `end_date`, `cancellation_date`, `subscription_status`, and recurring revenue must be reviewed against source semantics. No data type/nullability change is implied.
- **Potential additions:** A source identifier may be considered for traceability only after discovery. It is not approved or mandatory. No namespace field is proposed as an approved schema element.
- **Key/compatibility:** Canonical key meaning or supply mechanism can be a breaking semantic change even with the same column name. Assess existing identifiers, consumers, and migration.
- **Pending:** Episode boundary, cancellation/termination effectiveness, renewal, pause/suspension, source-ID reuse, and how canonical IDs are exchanged.

### 6.3 Subscription snapshots

- **Current v1.1:** One row per subscription/date with composite key `(subscription_id, snapshot_date)`.
- **Conceptual target:** One observation per canonical episode and snapshot date; preserve the composite key and do not overwrite historical state with present-day values.
- **Unchanged field candidates:** Current status, plan, recurring revenue, currency, billing frequency, and auto-renew fields remain subject to existing meanings pending review.
- **Potential additions:** No field is approved here. Recording/availability timestamps would require source evidence and separate design if needed for point-in-time verification.
- **Key/compatibility:** Existing subscription reference becomes canonical episode reference only after reliable episode attribution. Same-key membership is insufficient evidence.
- **Pending:** DD-EP-008 historical attribution; DD-001 snapshot date convention; DD-002 coverage; timezone/cutoff and availability semantics.

### 6.4 Monthly usage

- **Current v1.1:** Optional; one record per subscription/month; composite key `(subscription_id, usage_month)`.
- **Conceptual target:** Preserve optionality and reference a canonical episode only where the source usage record is attributable to that episode.
- **Unchanged field candidates:** Current count/volume/metric fields retain their present type and validation ownership unless a later decision changes them.
- **Potential additions:** No additional period-start/end or availability field is approved. Such fields may be assessed after source discovery, not presumed.
- **Key/compatibility:** A reference may exist but point to the wrong episode. Do not split/allocate periods crossing episode boundaries without approved policy.
- **Pending:** DD-EP-009 attribution; DD-EP-010 crossing periods; TC-007 remains `PENDING_DECISION`.

### 6.5 Invoices

- **Current v1.1:** Optional; one row per invoice, keyed by `invoice_id`, with a `subscription_id` reference.
- **Conceptual target:** Preserve invoice grain and optionality. Reference the canonical episode when source evidence establishes which episode the invoice belongs to.
- **Unchanged field candidates:** Existing issue/due/paid dates, amount, currency, and status keep existing schema checks; no financial interpretation follows from validation.
- **Potential additions:** Service-period or source-lineage fields are not approved and require finance/source discovery.
- **Key/compatibility:** Reinterpreting `subscription_id` can be breaking. Date-only matching cannot establish attribution. Do not split invoices spanning episodes without a policy.
- **Pending:** DD-EP-011 invoice attribution, including historical and multi-episode invoices; point-in-time availability fields and semantics.

This section does not enumerate a final set of columns or revise types and nullability. The actual contract delta must be authored and reviewed separately.

## 7. Episode Lifecycle and Historical Preservation

Approved episode principles:

1. **New episode:** Issue one canonical UUID only after authoritative evidence establishes a new contractual episode; persist it.
2. **Recognized episode:** Reuse its persisted canonical `subscription_id`; do not generate a replacement on repeat submission.
3. **Reactivation:** Reactivation following termination is a new episode with a new canonical ID. Keep the prior episode and history.
4. **Repeated submission:** Each file is a new submission event, not evidence that its rows are new. A previously unseen row alone does not establish identity.
5. **Ambiguous/conflicting evidence:** Surface and isolate unresolved identity; do not issue or reuse an ID automatically or silently.
6. **Corrections:** Preserve traceable correction history and prior mapping lineage; do not silently erase historical associations.

Dates, status, row order, identifier similarity, or heuristics alone do not establish identity; reusing one source identifier across episodes does not prove sameness. **Unresolved:** exact episode start/end boundaries, cancellation effectiveness, renewals/extensions, suspension/pause, source event interpretation, and universal evidence thresholds. These require the responsible decision and client/source evidence. This proposal does not add lifecycle rules.

## 8. Dependent Dataset Attribution

For snapshots, usage, and invoices, “correct attribution” means that the child record’s canonical `subscription_id` identifies the contractual episode to which the source record actually pertains. Referential integrity can establish that the value matches a key in the subscription table, but cannot establish that it is the right episode.

| Dataset | Evidence question | Pending decisions | If attribution cannot be established |
|---|---|---|---|
| Snapshots | Does the source row carry a stable episode key or auditable crosswalk to the applicable canonical episode? Does it represent that episode at the stated observation date? | DD-EP-008, episode boundaries, snapshot convention and cutoff. | Keep identity unresolved; exclude from identity-dependent processing under PD-003. Do not assign by date/status. |
| Usage | What entity/period was measured, and can that period be linked to one episode? Does it cross episode boundaries? | DD-EP-009/010 and TC-007. | Keep unresolved/excluded; do not split or allocate the usage period. |
| Invoices | Does the invoice identify one episode, represent a service period, or cover multiple episodes? Is linkage source-supported? | DD-EP-011 and invoice availability semantics. | Keep unresolved/excluded; do not infer from invoice date or arbitrarily allocate. |

Potentially useful evidence may include a source-provided episode-level identifier or an auditable client/source crosswalk, but no universal field or threshold is established. Client evidence and approved mapping decisions determine whether it is sufficient. A missing/ambiguous linkage is not repaired by an existing foreign-key value.

## 9. Dataset Availability and Ingestion Modes

**APPROVED REQUIREMENT — PD-006:** Snapshots are optional for basic ingestion and mandatory for workflows claiming temporal modelling. Absence is distinct from a header-only, zero-record file; neither absence nor low counts mean zero activity. Ingestion success does not imply DQ acceptance or model eligibility. No workflow-selection API, minimum coverage, or training threshold is selected.

The future contract should state dataset availability by intended use, distinguish required inputs for basic ingestion from temporal-modelling prerequisites, and preserve separate outcomes for ingestion, DQ, and modelling eligibility. This describes policy, not an interface mechanism.

**CURRENT IMPLEMENTATION GAP:** `REQUIRED_DATASETS` contains `customers`, `subscriptions`, and `subscription_snapshots`; the loader fails if any is absent. `usage_monthly` and `invoices` are optional. Header inspection validates a supplied dataset’s header but does not select workflow mode. Code must be separately authorized and coordinated with requiredness constants, discovery, headers, DQ presence/reporting, and downstream eligibility. PD-006 approval has not changed these files.

## 10. Absent, Empty, and Invalid Datasets

| State | Proposed contract distinction | Consequence |
|---|---|---|
| Dataset absent | No file supplied. Under policy, optional for basic ingestion where specified; snapshots still prerequisite for temporal-modelling workflows. | Record as absent; do not interpret as zero or as schema/RI pass. |
| Present with header and zero records | A supplied, structurally present dataset with no rows. | Distinct from absence. Empty-file acceptance and use-specific adequacy remain unresolved; do not infer zero activity or coverage adequacy. |
| Present with records | Supplied data rows exist. | Must still pass header, parsing, normalization, schema, and applicable DQ checks; presence is not acceptance. |
| Present but invalid | Supplied file fails structural, parsing, type, schema, or applicable DQ requirements. | Report at the owning stage; do not silently treat it as absent or skip an invalid optional file. Recovery/quarantine behavior is not defined here. |

No final empty-file acceptance rule is selected. A temporal workflow’s snapshot requirement concerns dataset availability, while actual eligibility still depends on valid, attributable, sufficient data under separately approved criteria.

## 11. Data Types, Nullability, and Validation Ownership

### 11.1 Stage responsibilities

| Layer | Current responsibility | Contract-design boundary |
|---|---|---|
| Header inspection | UTF-8 CSV header, known required/optional columns, duplicate/empty/whitespace names, unexpected columns. | Exact contract column registry; strict rejection means additive fields can affect old consumers. |
| CSV ingestion | Record width, parse/read CSV as strings, required files present, optional files loaded when present. | File availability and parsing; currently snapshot requirement conflicts with PD-006 basic-ingestion policy. |
| Type normalization | Copy input; convert known string, UTC datetime, nullable numeric/integer/boolean fields; preserve unknown columns for schema stage. | Representation conversion, not business identity or cross-file validation. No implicit identifier trimming. |
| Pandera schemas | Per-frame types, nullability, keys, controlled values and supported in-frame checks; strict, no coercion, add declared missing columns. | Own schema-level validity. DQ must not repeat primary/composite uniqueness, nullability, or value checks. |
| Data Quality validation | Implemented RI-001–004 and TC-001/002 over schema-valid frames. | Cross-frame reference existence and limited chronology only; not identity resolution, migration, or feature eligibility. Report/coordinator not implemented. |

Actual executable order is header inspection → ingestion → type normalization → Pandera → DQ functions. Contract v1.1’s pipeline drawing differs in where preprocessing/normalization appears; current code and the DQ specification describe normalization before Pandera.

### 11.2 Type and rule ownership observations

- Identifiers are CSV strings. Schemas reject null/empty/whitespace-invalid identifiers and do not normalize them. Canonical UUID syntax is not currently validated and no version-specific syntax requirement is approved.
- Normalizer parses ISO dates/UTC timestamps to UTC-aware pandas datetimes. Schemas expect UTC datetime dtypes, with required and nullable date fields as defined per dataset.
- Numeric CSV tokens normalize to float, nullable `Int64`, or required float where applicable; schemas check non-negativity and usage count relation. Do not change numeric representation or nullability without an exact approved contract delta.
- Booleans normalize to nullable pandas BooleanDtype; schemas validate nullable boolean fields.
- Currency regex checks three uppercase letters only; it does not prove ISO 4217 membership. Full list membership requires DD-009 policy/reference.
- Subscription and snapshot statuses use canonical allowlists in schemas, while contract v1.1 calls categories provisional and says client-specific values should be mapped during discovery. Mapping is upstream and currently unresolved (DD-007/BR-010); do not treat schema acceptance as source-system mapping.
- Invoice schema enforces due/paid dates not preceding invoice date. These are schema-owned, not DQ duplications.
- Optional declared columns may be added by Pandera with null values when missing; the independent header inspector still requires required header names and rejects unexpected names. `strict=True`/`coerce=False` mean contract/header/schema changes must be coordinated.

No type, nullability, or schema change is made by this proposal.

## 12. Data Quality Design Implications

| Rule | Current status | Contract design relevance |
|---|---|---|
| RI-001 | `IMPLEMENTED_IN_DQ` | Tests subscription customer reference existence; it does not resolve canonical episode identity. |
| RI-002 | `IMPLEMENTED_IN_DQ` | Tests snapshot key existence in subscriptions, not historically correct episode attribution. |
| RI-003 | `IMPLEMENTED_IN_DQ` | Runs only when optional usage is supplied; absent usage is `NOT_APPLICABLE`. Does not resolve period/episode alignment. |
| RI-004 | `IMPLEMENTED_IN_DQ` | Runs only when optional invoices are supplied; absent invoices is `NOT_APPLICABLE`. Does not resolve invoice attribution. |
| RI-005 | `PROPOSED` | Reverse rule requiring each customer have a subscription; do not claim execution or change it here. |
| TC-001 / TC-002 | `IMPLEMENTED_IN_DQ` | Check present end/cancellation date against start date. Do not expand to episode inference. |
| TC-003 | `PENDING_DECISION` | Snapshot-to-applicable-episode start comparison needs reliable attribution and lifecycle/date semantics. |
| TC-007 | `PENDING_DECISION` | Usage validity against episode periods needs period boundaries, attribution, and crossing-period policy. |
| BR-006 | `PROPOSED` | Optional dataset absence is non-blocking by policy; while unimplemented, do not claim a rule pass or execution. Presence may be reported separately once reporting exists. |

FK existence, episode attribution, and identity resolution are distinct: an existing key can still be the wrong episode. TC-003/007 cannot safely be finalized until relevant evidence and decisions are resolved. Other TC statuses remain as specified in the DQ Specification; this proposal does not redefine, execute, or duplicate schema-owned checks.

## 13. Historical Migration and Compatibility

PD-003/004/005 constrain any future transition:

- Do not split existing IDs into episodes or construct historical boundaries without authoritative evidence.
- Reuse persisted canonical IDs for recognized episodes; do not replace them merely because of a new file or row order.
- Preserve each prior episode and source-to-canonical mapping history through corrections.
- Isolate ambiguous or insufficiently attributable records; exclude them from identity-dependent processing until an appropriate disposition exists.
- Partial acceptance is permitted only for sufficiently attributable history, with traceability and explicit exclusions. It does not imply complete coverage or population representation.
- Assess accepted history separately for each intended use. Missing history is not zero activity or proof an episode did not exist.

Before transitioning v1.1 data, discovery must identify actual source keys, their reuse/stability, episode events, dependent dataset linkage, coverage, and consumer needs. No fabricated mappings, universal evidence threshold, or migration workflow is introduced.

## 14. Contract Versioning Strategy

PD-007 Option C governs: prefer additions/clarifications only when genuinely safe; classify breaking semantic or structural changes based on the exact delta and affected consumers. The matrix is preliminary risk assessment, not a version decision.

| Potential change | Preliminary compatibility risk | Evidence needed |
|---|---|---|
| Clarify subscription row grain as one episode | Potentially breaking semantic change if current source/consumer means differ; safe clarification only if semantics already align. | Client source grain, current consumers and labels. |
| Define canonical meaning/supply of `subscription_id` | Potentially breaking even if the column name is unchanged. | Existing key semantics, canonical ID exchange, registry/migration plan and all dependent consumers. |
| Change dependent FK from source subscription identity to canonical episode identity | Potentially breaking data/key semantics. | Crosswalk coverage and correct attribution for snapshots, usage, invoices. |
| Add optional source identifier column | Structurally additive, but potentially breaking to strict header consumers. | Source availability and consumer acceptance; exact field semantics. |
| Make source identifier mandatory | Likely breaking and unsupported as universal requirement. | Evidence for all affected clients plus explicit approval. |
| Make snapshots optional for basic ingestion | Approved policy direction; behavior may break clients/consumers that rely on unconditional presence. | Exact workflow contract, loader/header/DQ/model consumers, migration/release plan. |
| Other field or dataset changes | Unknown until specified; semantic changes can break without column changes. | Exact diff, schema/header impact, consumer inventory, migration and release review. |

Do not assign a version in this proposal. DD-EP-016 remains pending; the `1.1` versus `1.1.0` notation inconsistency remains unresolved. Version assignment follows exact-delta review, client/consumer impact, migration and release planning.

## 15. Impact on Current Repository Implementation

| Component | Current behavior | Potential change after approval | Dependency | Authorized here? |
|---|---|---|---|---|
| `DATASET_COLUMNS` | Fixed required/optional header columns for all five datasets. | Update only for an approved field/grain delta; retain strict unexpected-column handling unless contract changes. | Final contract delta and consumer review. | No. |
| `REQUIRED_DATASETS` / `OPTIONAL_DATASETS` | Customers, subscriptions, snapshots required; usage/invoices optional. | Represent PD-006 basic vs temporal requirement in a future coordinated design; no mechanism selected. | Workflow contract, exact interface and compatibility. | No. |
| Header inspection | Validates one file header; does not decide workflow-level file availability. | Coordinate header requirements with approved fields and workflow policies. | Contract and ingestion design. | No. |
| CSV ingestion | Reads all values as strings; requires three files; loads optional files when present; invalid optional files fail. | Change snapshot absence behavior only with authorization and defined mode semantics. | PD-006 implementation approval and tests. | No. |
| Type normalization | Per-dataset mapping converts known columns; preserves input by returning a copy. | Add/change mappings only for approved fields/types. | Contract schema and source formats. | No. |
| Five Pandera schemas | Strict, no coercion; enforce frame-level fields, nullability, values and keys. | Update in lockstep with approved field and semantic contract changes; do not add identity resolution here. | Exact schema delta and migration compatibility. | No. |
| RI validators | RI-001–004 compare reference existence; optional child rules apply when supplied. | Do not reinterpret as attribution or add pending rules without authorization. | Reliable canonical IDs and decisions for additional checks. | No. |
| TC validator | TC-001/002 compare subscription dates; pending rules absent. | TC-003/007 require resolved semantics and evidence before implementation. | DD-EP-008/009/010, DD-001, boundaries. | No. |
| DQ reporting / coordination | Models and RI/TC rule functions exist; report construction/coordinator do not. | Future reporting may distinguish presence, DQ, blocking and eligibility. | Separate approved scope; privacy and report design. | No. |
| Synthetic fixtures | Unit tests use synthetic data and temporary CSVs; current integration tests cover CSV ingestion. | Update only alongside approved contract behavior; no live-client evidence. | Approved delta. | No. |
| Unit tests | Cover header, ingestion, normalization, five schemas, models, RI, TC. | Add tests for accepted contract changes and ensure pending rules remain unenforced. | Implementation authorization. | No. |
| Integration tests | Current integration coverage is CSV ingestion; no full DQ public coordinator integration. | Add after coordinator and contract interface are implemented. | Future approved interface. | No. |

## 16. Open Decisions and Design Dependencies

Statuses below are retained from governing records; product approval does not silently resolve DD entries.

| ID | Current status | Contract design dependency |
|---|---|---|
| DD-EP-001 | `PENDING_CLIENT_DECISION` | Contractual episode boundary and source event evidence. |
| DD-EP-002 | `PENDING_CLIENT_DECISION` | Source subscription ID availability, stability, reuse and history. |
| DD-EP-003 | `PENDING_PRODUCT_DECISION` (partially resolved by ADR-010 and PD-001) | Remaining registry/ID design, exchange, workflow and operation details; do not mark fully resolved. |
| DD-EP-004 | `PENDING_CLIENT_DECISION` | Source namespaces and identifier collision domains. |
| DD-EP-005/006/007 | `PENDING_CLIENT_DECISION` | Cancellation, renewal/extension, pause/suspension semantics. |
| DD-EP-008 | `PENDING_CLIENT_DECISION` | Snapshot-to-episode evidence. |
| DD-EP-009 | `PENDING_CLIENT_DECISION` | Usage grain and episode attribution. |
| DD-EP-010 | `PENDING_PRODUCT_DECISION` | Policy for periods crossing episode boundaries after usage semantics are known. |
| DD-EP-011 | `PENDING_CLIENT_DECISION` | Invoice-to-episode evidence and multi-episode invoices. |
| DD-EP-012 | `PENDING_PRODUCT_DECISION` | PD-005 principles approved, but coverage/evidence and migration acceptance remain contextual. |
| DD-EP-013 | `PENDING_PRODUCT_DECISION` | Episode churn qualification; outside contract field design alone. |
| DD-EP-014/015 | `DEFERRED` | Customer-level churn and risk aggregation remain outside initial episode scope. |
| DD-EP-016 | `PENDING_PRODUCT_DECISION` | Exact contract delta and client/consumer impact before version/compatibility decision. |
| DD-EP-017 | `PENDING_PRODUCT_DECISION` | Downstream model evaluation grouping/temporal strategy; not a prerequisite for every contract clarification. |
| DD-001/002 | Open in Contract v1.1 | Snapshot convention and minimum history/coverage. |
| DD-007–011 | Open in Contract v1.1 as applicable | Status mapping, recurring revenue meaning, currency policy, timezone/cutoff, historical availability. |
| Empty-file policy | Unresolved | Handling/acceptance of present header-only files. |

PD-001–007 are approved product decisions, but implementation and contract changes still require their own authorization and review. Do not alter decision statuses in this proposal.

## 17. Recommended Contract Structure

**RECOMMENDATION:** Organize a future revised contract so that clients and implementers can trace each field to grain, identity, validation, availability, and compatibility. A suitable document structure is:

1. Purpose, scope, supported use cases, and terminology.
2. Prediction entity and row grain, including episode/customer distinction.
3. Canonical and source identifier semantics and exchange boundaries.
4. Dataset classification by basic-ingestion and temporal-modelling use.
5. Dataset definitions: business meaning, grain, keys, relationships, and field tables.
6. Data types, nullability, CSV formats, missing-value representation, and timezone conventions.
7. Validation ownership: header, ingestion, normalization, Pandera, and cross-dataset DQ.
8. Referential integrity versus identity attribution; unresolved-record treatment boundaries.
9. Temporal/lifecycle requirements with explicit pending decisions and no unsupported event rules.
10. Historical migration, lineage, partial acceptance, and backward-compatibility principles.
11. Versioning, change review, and decision register references.

This is a document organization recommendation, not a final schema or approval of additional fields. Each unresolved behavior should remain identified with its governing decision and status.

## 18. Design Readiness Assessment and Next Steps

| Workstream | Readiness | Rationale / next step |
|---|---|---|
| Contract semantic revision for episode identity | **PARTIALLY READY** | Core episode/canonical ID semantics are approved; draft precise wording while marking source exchange and episode boundary dependencies. |
| Field-level schema definition | **NOT READY** | Source identifiers, namespace, lifecycle meanings and dependent attribution are unresolved; exact columns/nullability cannot be finalized. |
| Source identifier exchange | **NOT READY** | Requires client discovery of availability, reuse, scope and consumer needs; no mandatory source field approved. |
| Snapshot/usage/invoice attribution | **NOT READY** | Requires auditable source linkage and relevant DD-EP decisions; FK existence is insufficient. |
| Snapshot optionality policy wording | **READY** | PD-006 direction is approved; state basic versus temporal use without choosing a technical mode interface. |
| Snapshot optionality implementation | **NOT READY** | Loader still requires snapshots; needs separate implementation authorization and coordinated compatibility work. |
| Historical migration principles | **READY** | PD-003/004/005 principles constrain design; client evidence, specific acceptance and tooling remain open. |
| Compatibility classification | **PARTIALLY READY** | PD-007 principles approved; exact field/semantic delta and consumer inventory are required before final classification. |
| Contract version assignment | **NOT READY** | No final delta or compatibility assessment; notation inconsistency unresolved. |
| Implementation planning | **NOT READY** | Requires approved revised contract, exact interface decisions, compatibility plan, and explicit implementation authorization. |
| Customer-level churn/risk | **DEFERRED** | DD-EP-014/015 remain outside initial episode-level contractual scope. |

Recommended sequence:

1. Review and approve episode-semantic contract wording without adding unsupported source requirements.
2. Conduct client/source discovery for IDs, namespaces, lifecycle events, dataset grain, historical attribution and consumers.
3. Resolve dependent-data attribution and relevant lifecycle/period decisions; preserve unresolved records where evidence is insufficient.
4. Specify dataset availability and empty-file policy separately from modelling eligibility; maintain PD-006’s approved distinction.
5. Draft the exact contract delta and assess each change against strict consumers, validators, migration and release impact under PD-007; resolve DD-EP-016 and version notation through their governing process.
6. Approve a contract revision and migration/compatibility plan before implementation authorization.
7. Separately design Registry, mapping, reporting, and pipeline implementation within authorized scopes.

This proposal preserves approved decisions, unresolved statuses, and implementation boundaries. It does not modify the current Customer Data Contract or authorize code, schema, ingestion, migration, Registry, or DQ reporting changes.
