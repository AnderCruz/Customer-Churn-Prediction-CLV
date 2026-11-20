# Customer Data Contract Impact Analysis

> **Historical design record.** This document preserves the Phase 02 assessment and its implementation observations at the time of review. For governing requirements, see the [approved Customer Data Contract](customer_data_contract.md) and [ADR-010](../03_architecture/adr_episode_identity_and_identifier_management.md).

**Document ID:** NCI-CONTRACT-IMPACT-ANALYSIS-001
**Version:** 0.1
**Status:** Draft for technical review
**Scope:** Phase 2.4.4.3 — Customer Data Contract Impact Analysis

## 1. Executive Summary

Customer Data Contract v1.1 defines the initial CSV interface for subscription-level contractual churn, but its `subscriptions.csv` grain is “one record per subscription” and it does not explicitly define `subscription_id` as a durable canonical identity for one contractual episode. Approved ADR-010 and EP-DEC-001–005 now establish that identity: `subscription_id` is the Nowa-owned canonical episode identifier, each episode is an independent prediction entity, and a customer may have multiple episodes. Reactivation following termination creates a new episode, while previous episodes remain preserved.

PD-001–PD-007 add approved product principles, including identity issuance, ambiguity handling, repeat-submission semantics, partial historical acceptance, snapshots’ optionality for basic ingestion versus temporal eligibility, and compatibility policy. These approvals constrain future contract design, but do not themselves authorize contract or code changes. Client source identifiers, their stability and reuse, episode boundaries, namespace representation, and dependent-record attribution still require evidence or joint decisions. Registry implementation and detailed technical design remain unauthorized.

The repository has five Pandera schemas with strict columns and no coercion; CSV headers reject unexpected columns; ingestion currently requires customers, subscriptions, and snapshots and optionally loads usage and invoices; normalization converts raw CSV strings into pandas types before schemas can validate them. Implemented DQ rules RI-001–RI-004 and TC-001–TC-002 test reference existence and two subscription date comparisons. They do not determine whether a dependent row was attributed to the correct episode. Report construction and coordination are not implemented. Current snapshot-file requiredness therefore conflicts with approved PD-006 and needs a separately authorized, coordinated implementation change.

**Recommendation:** Design a subsequent contract revision around one row per canonical contractual episode, with canonical `subscription_id` used consistently by dependent datasets. Keep customer identity separate. Do not add required source-ID or namespace fields, infer identity from dates/status/row order, allocate records across episode boundaries, or set migration and history thresholds without the required source evidence and decisions. Define exact field deltas and consumer impact before classifying compatibility or assigning any version. No final CSV schema or new contract version is proposed here.

## 2. Purpose and Scope

This read-only assessment evaluates the effect of approved episode architecture and product decisions on Customer Data Contract v1.1 and the actual repository implementation. It is a basis for subsequent contract design; it does not amend the contract, approve technical designs, or authorize implementation.

Evidence labels used throughout:

| Label | Meaning |
|---|---|
| **APPROVED REQUIREMENT** | A binding architectural or product requirement in an accepted ADR, approved episode decision, or approved PD record. It may not yet be implemented. |
| **CURRENT CONTRACT** | A statement or interface requirement in Customer Data Contract v1.1. |
| **CURRENT IMPLEMENTATION** | Behavior verified in current source code or tests. |
| **RECOMMENDATION** | Proposed contract or design direction in this assessment; not an approved requirement. |
| **PENDING DECISION** | A decision register item or question still open. |
| **DEFERRED** | A topic intentionally excluded from the initial episode-level contractual churn scope. |

If sources conflict, an approved ADR or explicitly approved EP/PD decision governs product meaning. The current contract remains the implemented contract until formally revised. Repository code establishes current behavior, not approved target policy. Earlier assessment documents are historical evidence and are not substituted for current decisions or source code.

## 3. Sources Inspected and Evidence Classification

The following required files were present and inspected:

| Source | Evidence used |
|---|---|
| `docs/04_data/customer_data_contract.md` | Current Contract v1.1 dataset grain, fields, requiredness, keys, temporal rules, pipeline, and versioning. |
| `docs/03_architecture/architecture_decisions.md` | Accepted ADR-009 prediction unit and client-isolation principle ADR-003. |
| `docs/03_architecture/adr_episode_identity_and_identifier_management.md` | Accepted ADR-010 canonical identity ownership, UUID strategy, Registry requirement, isolation, and limits. |
| `docs/04_data/subscription_episode_lifecycle_decision_specification.md` | Approved EP-DEC-001–005 and identity architecture; recommendation and pending-decision sections. |
| `docs/04_data/product_decision_proposals.md` | Approved PD-001–PD-007, including selected options, scope, exclusions, and implementation boundary. |
| `docs/04_data/customer_data_contract_episode_alignment_proposal.md` | Prior contract alignment and versioning proposal; recommendations are not approvals. |
| `docs/04_data/subscription_episode_data_contract_impact_assessment.md` | Earlier episode-contract impact assessment; checked against current decisions and implementation. |
| `docs/04_data/subscription_episode_identity_identifier_strategy_assessment.md` | Identifier concepts and alternative strategies; recommendations are not field approvals. |
| `docs/04_data/product_decisions_and_contract_design_assessment.md` | Decision ownership and DD-EP-001–017 inventory; statuses remain in their governing register. |
| `docs/04_data/data_quality_specification.md` | Current DQ rule statuses, ownership, pending dependencies, and optional dataset semantics. |
| `docs/04_data/data_quality_implementation_architecture.md` | Implemented DQ model/rule scope and planned report/coordinator boundaries. |
| `header_inspection.py`, `csv_ingestion.py`, `type_normalization.py` | Actual header, file-requiredness, CSV parsing, and dtype conversion behavior. |
| Five schema modules under `src/nowa_customer_intelligence/data/schemas/` | Per-frame fields, nullability, key uniqueness, value checks, and strict/no-coercion behavior. |
| `models.py`, `referential_integrity.py`, `temporal_consistency.py`, and validation package | DQ model and RI/TC implementation. No other validation modules beyond these and package initialization were present. |
| Relevant unit and integration tests under `tests/unit/data/` and `tests/integration/` | Verified tested behavior for headers, ingestion, normalization, schemas, RI, TC, and models. |

**Evidence limitation:** No live client data, source-system documentation, client identifier inventory, or client compatibility evidence was inspected or used. Test fixtures are synthetic and verify software behavior only; they do not demonstrate client compatibility.

## 4. Current Contract Baseline

### 4.1 Prediction unit and dataset grain

**CURRENT CONTRACT:** Contract v1.1 states individual subscription prediction, customer-level reporting, and one record per customer, subscription, monthly subscription snapshot, subscription/month usage record, and invoice. It calls `subscription_id` the subscription identifier and subscription primary key, not explicitly a canonical contractual-episode identifier.

**APPROVED REQUIREMENT:** ADR-009 together with EP-DEC-001–005 and ADR-010 defines one contractual subscription episode as the independent prediction entity. `customer_id` identifies the customer/account, not the prediction identifier. Multiple episodes may belong to one customer. Customer-level churn and risk aggregation remain **DEFERRED** under DD-EP-014 and DD-EP-015.

### 4.2 Keys, datasets, and fields

| Dataset | Contract v1.1 grain and key | Requiredness | Main field/type profile |
|---|---|---|---|
| `customers.csv` | One row per customer; primary key `customer_id`. | Required. | `customer_id` string; `created_at` date/datetime required; `country`, `industry`, `company_size`, `account_status` optional strings. |
| `subscriptions.csv` | One row per subscription; primary key `subscription_id`; FK `customer_id`. | Required. | Required strings `subscription_id`, `customer_id`, `subscription_status`; required date `start_date`; optional `plan_id`, `end_date`, `billing_frequency`, decimal `recurring_revenue`, `currency`, boolean `auto_renew`, `cancellation_date`, `cancellation_reason`. |
| `subscription_snapshots.csv` | One row per subscription per monthly snapshot date; composite key `(subscription_id, snapshot_date)`; FK `subscription_id`. | Required for temporal modelling in contract text. | Required ID, date, status; optional recurring revenue, currency, plan, billing frequency, auto-renew. |
| `usage_monthly.csv` | One row per subscription per month; composite key `(subscription_id, usage_month)`; FK `subscription_id`. | Optional. | Required ID and month; optional integer counts and decimal usage volume plus metric description. |
| `invoices.csv` | One row per invoice; primary key `invoice_id`; FK `subscription_id`. | Optional. | Required invoice and subscription IDs, invoice date, amount, currency, status; optional due and paid dates. |

**CURRENT CONTRACT:** Identifiers are strings; date conventions are ISO 8601; missing CSV fields are empty. The contract requires key uniqueness, required relationships, non-negative monetary/count values, date validity and specified chronology. Subscription and invoice status lists are described as proposed/provisional and client values are to be mapped during discovery. Currency is called ISO 4217, which is stronger than the schema’s three-uppercase-letter shape check.

The contract requires snapshots for temporal modelling but separately says initial ingestion should distinguish data needed for basic validation from data needed for historical modelling. It leaves snapshot monthly convention, historical coverage, client lifecycle semantics, source identifier behavior, dependent-row episode attribution, time cutoffs/availability, and other DD items open. Section 12 gives major/minor/patch examples but its `1.1` document version and `1.1.0 → 1.1.1` patch example leave version notation inconsistent.

### 4.3 Contract-level inconsistencies with approved decisions

1. **Episode grain and key meaning:** “One row per subscription” and “subscription identifier” do not explicitly say one row per contractual episode or canonical episode identity. Approved decisions now require that meaning.
2. **Reactivation and historical preservation:** Contract v1.1 leaves reactivation/episode identity open (DD-004/006). EP-DEC-003/005 and ADR-010 approve new episode identity after termination and preservation of earlier episode history. The contract has not been updated.
3. **Snapshot requiredness:** Contract text says required for temporal modelling; current loader requires snapshots for all ingestion; PD-006 approves snapshots optional for basic ingestion and mandatory for temporal-modelling workflows. Product approval does not change current behavior by itself.
4. **Identity persistence:** Current contract keys are frame-local; ADR-010 requires persisted identity and reuse across submissions. No current CSV field or implementation supplies that persistence mechanism.
5. **Status certainty and currency validity:** Contract calls status lists provisional and currency valid ISO 4217; schemas enforce canonical status values and only a three-letter uppercase currency pattern. Mapping and full currency membership remain separate issues.

## 5. Approved Episode Identity Requirements

The following are **APPROVED REQUIREMENTS**, not recommendations:

- `customer_id` identifies the associated customer/account. It is not the prediction identifier.
- One contractual subscription episode is an independent prediction entity; a customer may have multiple episodes.
- Reactivation following termination creates a new episode. Previous episodes and their identity/history are preserved.
- Nowa owns canonical episode identity. `subscription_id` is the canonical identifier for exactly one episode, stable and never reassigned.
- UUID is the initial generation strategy. Generate one canonical ID only after authoritative evidence establishes a new episode; persist it and reuse it for a recognized existing episode across submissions. UUID version and implementation remain open.
- A persistent, client-isolated Episode Identity Registry is required. It preserves verified mapping associations and history and supports recognition across repeat submissions.
- Ambiguous, conflicting, or insufficient identity evidence must not be silently resolved. A previously unseen row alone is not evidence of a new episode. Dates, statuses, row order, or heuristic similarity do not establish identity without authoritative supporting evidence. A reused source identifier alone does not prove that two records are the same episode.
- PD-001 requires Registry conflict detection, unresolved-identity visibility, traceable mapping corrections, auditable identity/mapping history, and preservation of previous mapping lineage.
- PD-003 requires unresolved records to be isolated and excluded from identity-dependent processing. PD-004 treats every file as a submission event, not proof of new records, and forbids replacement IDs solely due to reimport. PD-005 permits partial history acceptance only with sufficiently authoritative identity, traceability, explicit exclusions, and use-specific suitability assessment.

These policies do not establish client evidence thresholds, mandatory source fields, how to identify episodes where no stable source identifier exists, detailed registry/operational workflow, or implementation authorization. In particular, source subscription identifiers are not assumed to be episode identifiers. `source_subscription_id` is recommended only as a possible traceability field; its presence, requiredness, uniqueness, and semantics are unapproved. Source-system namespace representation likewise remains unresolved. Canonical ID uniqueness across external interfaces is not decided by Registry client-isolation requirements.

## 6. Dataset-by-Dataset Impact Analysis

### 6.1 `customers.csv`

**CURRENT CONTRACT / IMPLEMENTATION:** One row per customer, keyed by unique `customer_id`; the schema checks non-null, non-empty, whitespace-clean unique strings and UTC datetime `created_at`. RI-001 checks subscriptions-to-customers references. The contract also says each customer must have at least one subscription, represented as RI-005 `PROPOSED`, not implemented.

**APPROVED REQUIREMENT:** Keep `customer_id` as customer/account identity and separate from episode identity. **DEFERRED:** Customer-level churn and risk aggregation. **RECOMMENDATION:** No episode identifier belongs in this dataset absent a clear approved requirement; preserve its customer-grain role. Feature suitability remains subject to point-in-time availability and model feature policy, not this contract identity assessment.

### 6.2 `subscriptions.csv`

**CURRENT CONTRACT:** One row per subscription, with unique `subscription_id` and `customer_id` FK. **APPROVED REQUIREMENT:** Define the row as one canonical contractual episode and `subscription_id` as the canonical episode key. This is a semantic clarification only if current consumers already use precisely that grain and meaning; otherwise the changed key meaning/supply can be breaking under PD-007.

`customer_id` remains a required account relationship, not a key substitute. Source identifiers may be retained separately when verified, but cannot be mandated from current evidence. Repeated submissions must reuse persisted canonical identity for recognized episodes. Reactivation creates a new episode; prior episode records remain. Current status, dates, and one-row schema do not encode full lifecycle history or prove recognition. Boundary semantics for cancellation, renewals, pauses, and source lifecycle events remain pending (including DD-EP-001/005/006/007).

### 6.3 `subscription_snapshots.csv`

**CURRENT CONTRACT:** Snapshot rows reference `subscription_id` and use composite key `(subscription_id, snapshot_date)`. The schema enforces that composite key and field constraints. **APPROVED REQUIREMENT:** The FK must refer to canonical episode ID in the target contract. A syntactically valid FK does not prove the snapshot belongs to that episode historically.

PD-006 Option B makes the dataset optional for basic ingestion and mandatory for workflows claiming temporal modelling. The contract/interface and implementation remain to be aligned. DD-EP-001/008 and DD-EP-002/004 remain relevant to lifecycle and attribution evidence. DD-001 remains open: do not assume the first or last day of a month. Historical attribution cannot be inferred from snapshot dates or statuses; do not overwrite historical states with current values.

### 6.4 `usage_monthly.csv`

**CURRENT CONTRACT:** Optional, keyed by `(subscription_id, usage_month)`, with nullable counts and volume. Schema enforces non-negative counts/volume and `active_users <= total_users`; RI-003 tests reference existence when supplied. **APPROVED REQUIREMENT:** Reference canonical episode IDs once the contract adopts that meaning.

The contract says usage should correspond to valid subscription periods, but period boundaries, availability, aggregation grain, and treatment of periods crossing episodes are unresolved (DD-EP-009/010). TC-007 is `PENDING_DECISION`. A month that crosses an episode boundary cannot be allocated or split using dates alone. Historical usage attribution needs client/source evidence and an approved policy; otherwise it stays unresolved and is excluded from identity-dependent use per PD-003.

### 6.5 `invoices.csv`

**CURRENT CONTRACT:** Optional, one row per `invoice_id`, with required subscription reference. Schema enforces invoice key uniqueness, date validity/order, amount, currency shape and status; RI-004 checks subscription reference existence when supplied. **APPROVED REQUIREMENT:** The target FK means canonical episode identity, but it must identify the correct contractual episode, not merely an existing one.

Invoice linkage may be direct, historical, or cover multiple episodes; repository evidence does not settle this. DD-EP-011 remains pending. Do not infer an invoice’s episode from invoice date alone, or split/allocate it without an approved policy. Preserve financial lineage and unresolved attribution; no financial interpretation or reconciliation is authorized by structural validation.

## 7. PD-006 Dataset Availability Impact

**APPROVED REQUIREMENT — PD-006 Option B:** `subscription_snapshots.csv` is optional for basic ingestion and mandatory for workflows claiming temporal modelling. Its absence is distinct from a present file with zero records. Absence is never zero activity/value. Ingestion success, DQ acceptance, and modelling eligibility are separate outcomes. No minimum coverage or training threshold, snapshot date convention, or implementation is included in this approval.

**CURRENT IMPLEMENTATION:** `REQUIRED_DATASETS` currently contains `customers`, `subscriptions`, and `subscription_snapshots`; `OPTIONAL_DATASETS` contains `usage_monthly` and `invoices`. `ingest_client_datasets()` raises if any required file, including snapshots, is absent. `inspect_csv_header()` validates an individual header against required and optional columns but does not determine whether the dataset file is optional. Thus approved PD-006 is not yet reflected in actual loader behavior.

**RECOMMENDATION:** A separately authorized implementation should represent workflow purpose explicitly enough to distinguish basic ingestion from temporal-modelling eligibility, and coordinate dataset classification, file discovery, header behavior, DQ dataset-presence reporting, and downstream eligibility. This assessment does not choose a mode/interface. Current Data Quality rule inputs still require snapshots under current behavior, and the DQ coordinator/report is not yet implemented. PD-006 approval alone must not be mistaken for a code change.

For usage and invoices, current contract and implementation classify them optional. Their absence should remain visible and non-blocking under approved policy; their absence must not be converted to zero or treated as if a supplied file had passed its schema or RI checks.

## 8. Absent vs. Empty Dataset Analysis

These conditions have distinct observable and downstream meanings. Empty-file acceptance policy remains unresolved; no policy is selected here.

| State | Ingestion / validation implications | Modelling implications |
|---|---|---|
| File absent | For currently required files, ingestion errors. For optional usage/invoices, file is omitted from returned mapping. Under PD-006, future basic ingestion may omit snapshots after implementation; temporal workflows require them. Presence should be recorded independently. | Absence is unknown/unprovided data, not zero events or values. Temporal eligibility cannot be inferred from absence. |
| File present with header and zero records | Header inspection can succeed. Reader returns a zero-row DataFrame; type normalization and schema checks still run. Header presence does not establish record coverage. DQ applicability/count behavior is rule-specific; current RI optional rules can evaluate empty frames, and TC rules may be not applicable if no rows meet date prerequisites. | Zero observed rows may be insufficient for a use case but no minimum threshold is approved. Do not treat as equivalent to absence or as proof of zero activity. |
| File present with records | Header, ingestion, normalization, schema, then applicable DQ checks run. Presence alone is not acceptance. | Eligibility depends on valid, attributable records and separately agreed temporal/coverage requirements. |
| File present but invalid | Header/CSV/type/schema failures occur in their owning stage; a supplied but invalid optional dataset is not silently skipped. DQ must not duplicate upstream errors. | Invalid supplied data cannot be treated as absent, zero, or eligible. Recovery, quarantine, and partial acceptance must follow separately approved behavior. |

## 9. Pipeline and Pandera Impact

### 9.1 Current execution path

**CURRENT IMPLEMENTATION:** Header inspection validates UTF-8 CSV headers, required/optional columns for known datasets, duplicates, whitespace, empty names, and unexpected columns. It does not load rows. Ingestion validates record width, reads fields as pandas string dtype without NA inference, requires the three datasets above, and includes optional files only when present. Type normalization creates a copy and converts known columns to pandas string, UTC datetime, nullable integer/float/boolean types; it does not validate cross-dataset identity. Pandera then enforces each DataFrame’s schema. The Data Quality RI/TC functions consume DataFrames and return findings; they do not orchestrate the earlier stages.

Actual dependency is **header inspection → CSV ingestion → type normalization → Pandera schema validation → applicable DQ validation**. The Contract v1.1 pipeline diagram places type/data-type validation differently; the current DQ specification documents this ordering discrepancy. The implementation order governs current behavior, while documentation reconciliation is a separate task.

### 9.2 Strict schema and requiredness behavior

`DATASET_COLUMNS` and each schema list the current contract columns. Header inspection rejects unknown columns. The five schemas use `strict=True`, `coerce=False`, and `add_missing_columns=True`. The latter adds absent declared schema columns; nullable optional fields can then be null, while missing required fields fail required/non-null checks. It does not make arbitrary new columns acceptable. The current header inspector independently rejects missing required headers and unexpected headers before the schema stage.

Per-frame Pandera ownership includes primary/composite key uniqueness; non-null/identifier string validity; status shape/value checks; count, revenue and invoice non-negativity; currency three-uppercase-letter format; `active_users <= total_users`; and invoice due/paid date ordering. These are not to be reimplemented in DQ. Regex shape does not establish ISO 4217 membership. Current normalized datetime types are UTC-aware pandas datetimes; nullable numeric/boolean columns use pandas extension dtypes. These types suffice for implemented TC-001/002 comparisons and RI string matching but cannot supply missing source evidence or historical episode attribution.

### 9.3 Coordinated changes

Changing grain/key semantics or dataset availability will affect `DATASET_COLUMNS`, header inspection, `REQUIRED_DATASETS`/`OPTIONAL_DATASETS`, ingestion discovery and validation, `DATASET_COLUMN_TYPES`, normalization, schemas, mapping/identity interface design, synthetic fixtures, and unit/integration tests. If a field is added to a schema, strict header registration must be updated too. A new optional source field still may break strict existing consumers that reject unknown headers. Implement changes only after exact contract delta and compatibility review under PD-007.

Do not introduce UUID format/version checks merely because canonical IDs use UUID as a generation strategy; version and external representation remain open. Do not apply string normalization to identifiers or treat source keys as canonical without approved evidence/mapping. No CSV schema or source/namespace fields are finalized here.

## 10. Data Quality Impact

### 10.1 Existing ownership and behavior

**CURRENT IMPLEMENTATION:**

| Rule | Current owner / behavior | Important limit |
|---|---|---|
| RI-001 | DQ checks `subscriptions.customer_id` exists in `customers.customer_id`. | Does not duplicate schema null/unique checks or prove business account attribution. |
| RI-002 | DQ checks snapshot `subscription_id` exists in subscriptions. | Existence does not prove snapshot-to-episode attribution. |
| RI-003 | DQ checks usage reference when supplied; absent usage yields `NOT_APPLICABLE`. | Does not resolve period semantics or episode allocation. |
| RI-004 | DQ checks invoice reference when supplied; absent invoices yields `NOT_APPLICABLE`. | Does not establish correct historical/multi-episode invoice attribution. |
| TC-001 / TC-002 | Compare present `end_date` / `cancellation_date` against `start_date`; missing comparison date is not evaluated as a violation. | Does not establish canonical lifecycle semantics or episode boundaries. |

The implemented functions return typed findings. `DataQualityValidationError` is for invalid invocation preconditions, not ordinary rule violations. DQ report construction, public coordinating entry point, aggregate blocking orchestration/reporting, and related planned tests are not implemented. Do not state that a complete report or coordinated pipeline gate exists.

Pandera already owns required foreign-key nullability and key uniqueness. DQ must not duplicate either. The existing RI code compares identifier strings for membership. A child record that references an existing `subscription_id` can still be associated with the wrong episode; reference existence proves only that the key exists. Correct episode attribution needs authoritative source linkage or an approved mapping and cannot be established by RI alone. Identity resolution remains a distinct prerequisite; temporal consistency tests date ordering, not identity.

### 10.2 Pending/deferred rules and dependencies

TC-003 (snapshot not before applicable episode start) is `PENDING_DECISION` because the applicable episode must be reliably attributable and date semantics/boundaries are not resolved. TC-007 (usage within valid subscription periods) is `PENDING_DECISION` because usage period boundaries, crossing-episode handling, and source attribution are unresolved. Do not implement, redefine, or infer either rule in contract design. TC-004/005 are also pending cutoff/timezone or monthly-convention decisions; TC-006 and TC-008 are deferred for missing availability timestamps; other DQ rule states remain as in the DQ Specification.

RI-005, the reverse requirement that every customer have a subscription, remains `PROPOSED`, not implemented. BR-006 optional-dataset informational reporting also remains `PROPOSED`; its absence is not a validation failure, and no execution/pass claim is made. Current optional dataset presence can be recorded once reporting is implemented. RI-005 and BR-006 must not be represented as executed business rules without separate implementation authorization.

## 11. Versioning and Compatibility Assessment

**APPROVED REQUIREMENT — PD-007 Option C:** Prefer genuinely safe backward-compatible additions or clarifications. Version breaking semantic or structural changes separately according to actual compatibility impact. A change in meaning or supply mechanism may be breaking even if a column name stays the same. Include strict consumers and validators; assess the exact delta before assigning a version. Do not resolve the current `1.1` versus `1.1.0` notation inconsistency here.

The following are preliminary compatibility risks, not version assignments. Actual class depends on exact delta and affected consumers:

| Potential change | Preliminary impact under PD-007 | Rationale / dependency |
|---|---|---|
| Clarify `subscriptions.csv` row grain as one contractual episode | Potentially breaking semantic change; can be a clarification only if all existing producers/consumers already use that grain. | Current v1.1 says one row per subscription. Verify source grain and downstream assumptions. |
| Define canonical episode semantics for existing `subscription_id` | Potentially breaking, even with same column name. | Changes meaning/supply from source subscription key to durable canonical episode identity; requires identity and migration plan. |
| Add optional source identifier fields | Structurally additive, but compatibility is consumer-dependent and may be breaking for strict header consumers. | Source field semantics/availability, namespaces, and whether optional input adds value remain subject to discovery and design. |
| Add required source identifier fields | Likely breaking. | All clients must supply it; no evidence establishes universal availability. Not approved. |
| Change dependent FK meaning to canonical episode ID | Potentially breaking semantic/key change. | Existing values may be source subscription IDs; mappings and dependent data must be reconciled. |
| Make snapshots optional for basic ingestion | Contractually approved direction, but implementation/consumer compatibility may be behaviorally breaking. | Current loader requires snapshots; temporal workflows still require them. Workflow/interface semantics need design. |
| Add source-system namespace field | Additive shape, but strict consumers may reject it; if mandatory, likely breaking. | Namespace representation and requiredness are unresolved under DD-EP-004. |

No version is assigned. No dual-version coexistence is mandated. DD-EP-016 remains pending for exact delta and client/consumer impact. Contract v1.1 remains the current approved interface until governance approves a revision.

## 12. Historical Migration and Backward Compatibility

PD-003, PD-004, and PD-005 are approved constraints. Repeated files are distinct submission events; reimport alone does not create new episodes or justify replacement IDs. Existing canonical IDs must be reused when an episode is reliably recognized. New IDs are issued only after authoritative evidence establishes a new episode. Ambiguous or unsupported identity remains unresolved and excluded from identity-dependent processing; do not fabricate episode identities, infer from dates/status/row order/similarity, or silently overwrite mappings. Preserve source lineage, attribution evidence, and prior mapping history.

Historical migration may accept an attributable subset under PD-005, with explicit exclusions and intended-use suitability assessed separately. Partial acceptance is not complete coverage or full-population representation. Missing history is not zero activity or proof an episode did not exist.

| Historical material | Assessment and dependency |
|---|---|
| Existing subscription rows/IDs | Need client evidence to establish whether current keys identify contractual episodes and how they persist/change. Do not split/rename IDs from dates or status alone. |
| Historical episodes / reactivation | Requires source lifecycle events and episode boundaries (DD-EP-001/005/006/007) and evidence of termination/reactivation. Preserve prior episode. |
| Snapshots | Must map to canonical episode using reliable evidence (DD-EP-008); same key existence is insufficient. Coverage and snapshot convention remain open (DD-001/002). |
| Usage | Requires source grain, covered period and reliable episode linkage (DD-EP-009/010). Do not split or allocate a cross-boundary month without approved policy. |
| Invoices | Requires linkage/service-period semantics and treatment of invoices spanning episodes (DD-EP-011). Invoice dates alone do not prove attribution. |
| Partial/unresolved history | Explicitly record accepted attributable scope and unresolved/excluded records; preserve traceability under PD-003/005. Exact evidence thresholds and operational disposition remain open. |

Identity registry persistence, source crosswalks, mapping corrections, migration tooling, and reporting mechanisms are not implemented. Any migration requires subsequent design/implementation authorization and a compatibility plan; no live client data was used in this assessment.

## 13. Contract Change Matrix

| Area | Current State | Target Direction | Decision Status | Compatibility Impact | Blocking Dependencies |
|---|---|---|---|---|---|
| `customers.csv` | Customer-grain row keyed by `customer_id`; schema uniqueness. | Preserve account identity; no episode key in customer rows. | **APPROVED REQUIREMENT** for identity distinction; no structural change justified. | Low if unchanged. | Keep customer/account semantics; customer aggregation remains **DEFERRED**. |
| `subscriptions.csv` grain | One row per subscription, semantics not explicitly episode-canonical. | One row per contractual episode. | Episode identity **APPROVED REQUIREMENT**; exact contract delta recommended, not approved. | Potentially breaking semantic change. | Verify client source grain/lifecycle; define mapping/migration. |
| `subscription_id` | Unique frame key / dependent FK; “subscription identifier.” | Canonical, stable, Nowa-owned identifier for exactly one episode; UUID initial strategy, persisted/reused. | **APPROVED REQUIREMENT**; CSV supply mechanics unresolved. | Potentially breaking semantic/supply change. | Identity evidence, registry/interface design, migration, client/consumer review. |
| Source IDs / namespace | No corresponding fields in current contract. | Preserve verified provenance when useful; do not require or conflate with canonical ID absent evidence. | **PENDING DECISION** / source discovery; no field approved. | Optional addition may still break strict consumers; mandatory fields likely breaking. | DD-EP-002/004 and product/interface design. |
| Snapshot key / attribution | Composite `(subscription_id, snapshot_date)`; existence FK. | Canonical episode FK with correct historical attribution evidence. | Key shape **CURRENT CONTRACT**; attribution **PENDING DECISION**. | Semantic FK change may be breaking. | DD-EP-001/008, source crosswalk, migration. |
| Usage key / attribution | Composite `(subscription_id, usage_month)`; optional dataset. | Episode-level usage with verified attribution; no cross-boundary allocation assumed. | FK grain approved direction; period interpretation **PENDING DECISION**. | Potentially breaking semantic change. | DD-EP-009/010 and client usage-period evidence. |
| Invoice key / attribution | `invoice_id` primary key; optional; `subscription_id` FK. | Canonical episode linkage only where source supports episode-level attribution. | **PENDING DECISION** for invoice episode semantics. | Potentially breaking semantic change. | DD-EP-011, finance/source linkage, multi-episode invoice policy. |
| Snapshot availability | Contract required for temporal modelling; current loader always requires. | Optional for basic ingestion; required for temporal-model workflows. | **APPROVED REQUIREMENT** PD-006; code change unauthorized. | Behavior/consumer impact; exact classification after delta. | Workflow/interface contract, DD-EP-016, coordinated code and tests. |
| Usage/invoice availability | Optional in contract and loader. | Preserve optional; absence distinct from empty/invalid and not zero. | **CURRENT CONTRACT** and approved PD-006 principles. | Low if unchanged; report behavior future. | Empty-file policy remains open; reporting not implemented. |
| Header/schema/normalization | Fixed field lists; strict schemas, no coercion; five schemas. | Update in lockstep with an approved exact contract delta; no duplicate DQ checks. | **CURRENT IMPLEMENTATION**; future changes require authorization. | Strict consumers can make additive columns incompatible. | Contract delta, all affected modules/fixtures/tests, consumer inventory. |
| DQ / temporal validation | RI-001–004 and TC-001–002 implemented; TC-003/007 pending; report coordinator absent. | Keep existence, identity resolution, and temporal/business semantics separate. | Mixed: **IMPLEMENTED_IN_DQ**, **PENDING DECISION**, **PROPOSED**, **DEFERRED** per DQ specification. | New fields/rules may alter validation and eligibility behavior. | Attribution, period/lifecycle decisions, report/coordinator implementation authorization. |
| Historical migration | No registry/migration implementation. | Evidence-based partial acceptance with lineage and unresolved isolation under PD-003/005. | Policy **APPROVED**; criteria/evidence and implementation open. | High where keys/grain change. | Client history/crosswalk, evidence, intended use, migration/compatibility plan. |
| Versioning | Contract v1.1; notation examples inconsistent. | Apply PD-007 Option C after exact compatibility assessment. | **APPROVED REQUIREMENT** for principles; DD-EP-016 and version assignment open. | Must be determined per exact delta and consumers. | Final delta, client/consumer evidence, migration/release plan; notation decision. |

## 14. Pending Decisions and Dependencies

Items material to contract design include:

| Decision/dependency | Status / contract impact |
|---|---|
| DD-EP-001 episode boundary; DD-EP-005 cancellation; DD-EP-006 renewal; DD-EP-007 pause/suspension | Client or joint lifecycle evidence needed to define exact episode start/end and event mapping. Approved reactivation principle does not define event evidence or full lifecycle policy. |
| DD-EP-002 source subscription ID availability/reuse; DD-EP-004 namespace | Client/source discovery. Do not assume source IDs are episode IDs or require source fields. |
| DD-EP-003 remaining Registry details | ADR-010/PD-001 requirements approved; UUID version, storage/API/transactions, operations, detailed workflows, retention, namespace, CSV exchange and implementation remain open. |
| DD-EP-008/009/011 attribution for snapshots, usage, invoices | Client/source evidence plus joint acceptance of attribution. A valid FK is insufficient. |
| DD-EP-010 usage periods across episodes | Product decision depends on usage-period facts; no allocation policy. |
| DD-EP-012 migration acceptance | PD-005 principles approved; client coverage, crosswalk evidence and intended-use suitability remain to be assessed. |
| DD-EP-013 episode churn qualification | Product and client event semantics remain open for target construction. |
| DD-EP-014/015 customer-level churn/aggregation | **DEFERRED**, outside initial episode-level contractual churn. |
| DD-EP-016 compatibility/versioning | **PENDING_PRODUCT_DECISION** in the episode decision register; apply PD-007 only after exact delta and client/consumer impact are assessed. |
| DD-EP-017 temporal evaluation/grouping | **PENDING_PRODUCT_DECISION**; downstream modelling dependency, not prerequisite to every contract clarification. Consider customer grouping due to multiple episodes and leakage risk; no split strategy selected. |
| DD-001/002/007–011 and other Contract v1.1 open decisions | Snapshot convention, history threshold, status mapping, revenue/currency meaning, cutoff/timezone, availability timestamps, and missing-data thresholds remain unresolved as applicable. |
| Empty dataset policy | Distinction is required; acceptance/handling of present-empty files remains unresolved. |
| Implementation authority | PD-001–007 approvals constrain design but do not authorize changes to contract, code, schemas, ingestion, DQ reporting, Registry, or migration. |

## 15. Recommended Contract Evolution Strategy

This is **RECOMMENDATION**, not an approved implementation plan or final schema:

1. **Specify approved semantics without inventing source fields.** Clarify that subscription rows and the canonical `subscription_id` represent individual contractual episodes, distinguish `customer_id`, and record stable/persisted/reused identity and reactivation preservation principles. Preserve open lifecycle evidence and do not assert that current client data can meet them.
2. **Resolve contract-interface questions with discovery.** Inventory actual source identifiers across each dataset, reuse/reassignment behavior, source namespaces, episode events, and dependent-row lineage. Decide whether and how source identifiers are exchanged only after findings; do not make `source_subscription_id` mandatory in advance.
3. **Set dependent dataset semantics with evidence.** Confirm how snapshots, usage periods, and invoices link to individual episodes. For multi-episode or crossing periods, require reliable attribution or keep records unresolved; do not infer/split by dates. Clarify keys only when exact grain is supported.
4. **Reflect PD-006 in the interface.** Define basic-ingestion versus temporal-modelling requirements, absent versus present-empty behavior, and where eligibility is determined. Snapshot date convention, minimum history, training thresholds, and empty-file policy need separate resolution. Coordinate with ingestion, header inspection, schemas, DQ presence/reporting, and modelling eligibility; approval alone does not change current loader behavior.
5. **Complete exact compatibility assessment under PD-007.** Inventory producers, strict validators, downstream consumers, key references, data migration, coexistence/deprecation needs, and release impacts for each proposed field/semantic delta. Classify each exact change and resolve DD-EP-016 in its governing process before assigning a version.
6. **Plan evidence-based historical transition.** Measure attributable coverage and unresolved records using authorized client evidence; apply PD-003/005, preserve lineage, describe partial coverage honestly, and assess suitability per intended use. Design migration and Registry technology/workflows separately and obtain implementation authorization.
7. **Only then prepare a revised contract and coordinated implementation plan.** No final CSV schema, new contract version, code changes, or client-specific assertions are produced in this assessment.

## 16. Explicit Implementation Boundaries

This assessment does not modify Customer Data Contract v1.1 or assign a new version. It does not modify ADR-009/010, episode or product-decision records, DQ documents, code, schemas, tests, or configuration. It does not implement UUID generation, the Episode Identity Registry, source-to-canonical mapping, migration, changes to requiredness, validators, or pipeline behavior. It does not select a UUID version, source namespace field, source-ID requirement, date convention, coverage threshold, usage allocation, invoice allocation, ambiguity workflow, or evaluation split. No live client data was used. Approved product/architecture decisions are treated as constraints; recommendations and pending decisions remain clearly separate.

## 17. Verification Notes and Limitations

The analysis was checked against the listed repository documents, current ingestion/normalization/schema/validation modules, and relevant unit/integration tests. Source modules confirm strict header/schema behavior, no schema coercion, frame-local key checks, implemented RI-001–004 and TC-001/002, and current snapshot-required ingestion. Tests verify software behavior using synthetic in-memory or temporary-file fixtures only.

Important limits: there is no client source-system evidence, actual compatibility inventory, approved CSV exchange mechanism for canonical IDs, implemented Registry, migration tooling, or complete DQ reporting/coordinating interface. This document is a draft impact analysis and recommendation; a contract revision, compatibility decision, technical design, and implementation authorization remain subsequent work.
