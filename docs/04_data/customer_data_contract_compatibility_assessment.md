# Customer Data Contract Compatibility and Change Assessment

> **Historical design record.** This document preserves the Phase 02 assessment and its implementation observations at the time of review. For governing requirements, see the [approved Customer Data Contract](customer_data_contract.md) and [ADR-010](../03_architecture/adr_episode_identity_and_identifier_management.md).

**Document ID:** NCI-CONTRACT-COMPATIBILITY-001
**Version:** 0.1
**Status:** Draft for technical review
**Project:** Nowa Customer Intelligence
**Scope:** Phase 2.4.4.6 — Contract Compatibility and Change Assessment
**Assessment date:** 2026-11-15

## 1. Executive Summary

The approved Customer Data Contract v1.1 defines five CSV datasets and the current field-level interface. Its subscription dataset is described as one row per subscription, with a unique string `subscription_id`. The Semantic Revision Proposal retains the existing fields, types, nullability, and key shapes while proposing a different domain meaning: each subscriptions row represents one canonical contractual episode, and `subscription_id` is a Nowa-owned identifier for that episode.

That distinction is material. Identical column names and types do not make a semantic change backward-compatible. Existing producers may supply source-system subscription identifiers, and consumers may interpret an identifier as a persistent source object rather than a particular contractual episode. Existing snapshots, usage, and invoice references could therefore point to identifiers whose semantics change. Actual client source behavior and external consumers have not been inventoried, so compatibility with them cannot be established.

The repository implementation is strict about headers and schema columns, does not coerce schema inputs, and enforces keys and field checks. Current ingestion requires customers, subscriptions, and subscription snapshots. Approved PD-006 instead makes snapshots optional for basic ingestion and required for temporal-modelling workflows. The policy is approved, but the loader and integration tests still implement unconditional snapshot requirement. Episode identity issuance, persistence, and reliable attribution of dependent records are not implemented by the inspected ingestion, normalization, schema, or DQ code.

The highest preliminary risks are the semantic/supply change to `subscription_id`, historical and dependent-record attribution, and the snapshot-availability behavior gap. Usage-period crossing and invoice-to-episode attribution remain unresolved. No new contract version should be assigned based on this assessment alone.

**Overall conclusion: NOT READY for formal approval of the proposed semantic revision as an executable contract or for coordinated implementation.** The proposal is a useful semantic basis, but readiness requires an exact approved contract delta, resolution or explicit handling of attribution and migration dependencies, an assessment of actual producers and consumers, and a separately authorized implementation plan. The snapshot policy is approved but its implementation interface and workflow-mode behavior remain to be designed. No implementation is authorized by this assessment.

## 2. Assessment Scope and Methodology

This assessment compares approved Customer Data Contract v1.1 with the Customer Data Contract Semantic Revision Proposal v0.1, and considers the related Design Proposal v0.1 and Impact Analysis v0.1. It also considers ADR-009, ADR-010, the Subscription Episode Lifecycle Decision Specification v0.4, product decisions PD-001 through PD-007, supporting episode assessments, the Data Quality Specification v0.2, and the Data Quality Implementation Architecture v0.2.

Repository inspection covered the actual header inspection, CSV ingestion, and type normalization modules; all five Pandera schema modules; data-quality models and referential-integrity and temporal-consistency validators; unit tests for those components; and the CSV ingestion integration tests. Compatibility is distinguished as follows:

- **Semantic:** whether the business meaning or interpretation of an unchanged field, row, key, or relationship changes.
- **Structural:** whether names, field presence, types, nullability, keys, or dataset/file requirements change.
- **Behavioral:** whether the current loader, normalizer, schemas, validators, or pipeline behave differently from approved or proposed policy.
- **Migration:** whether existing records and references can be mapped to the target semantics with adequate evidence and traceability.

Repository evidence establishes current code behavior and documented policy, but does not establish actual client source-system semantics, client data quality, live data distributions, external consumer expectations, or deployment-specific workflows. No live client data or actual client producer/consumer inventory was available. Preliminary compatibility classifications and risks are therefore not substitutes for client discovery or consumer testing.

## 3. Governing Decisions and Constraints

The table separates binding decisions from current implementation and open dependencies. Approval of a principle does not itself authorize code or contract changes.

| Decision | Status and governing constraint | Compatibility implication |
|---|---|---|
| ADR-009 | Approved subscription-level prediction granularity. | Establishes the prediction granularity; it does not alone state the fully explicit episode-level prediction entity. |
| ADR-010 | Approved canonical episode identity architecture: Nowa-owned canonical ID, persistent client-isolated registry, issue after authoritative evidence, reuse for reliably recognized episodes, and no silent ambiguity resolution. | Source identifiers cannot be assumed canonical. Identity issuance, persistence, and evidence resolution are not current CSV-loader behavior. |
| EP-DEC-001 | Approved customer identity distinction. | `customer_id` identifies the customer/account, not the prediction entity. |
| EP-DEC-002 | Approved explicit definition of the contractual subscription episode as the prediction entity. | A subscription episode is the prediction entity within the subscription-level prediction granularity established by ADR-009. |
| EP-DEC-003 | Approved preservation of historical episodes and identity history. | Corrections or reactivation handling must not silently erase previous associations. |
| EP-DEC-004 | Approved customer-to-episode relationship. | A customer may relate to episode-level records; this does not make `customer_id` the episode key. |
| EP-DEC-005 | Approved that reactivation following termination creates a new episode. | Historical episode splitting and dependent-record attribution may be required; termination evidence and boundaries remain open. |
| PD-001 | Approved Option B registry functional requirements: conflict detection, unresolved-identity visibility, traceable corrections, auditable history, and preserved mapping lineage. | Adds functional outcomes, not a registry technology, workflow, or implementation authorization. |
| PD-002 | Approved Option B canonical ID issuance principles. | A new canonical ID follows authoritative evidence of a new episode; recognized episodes reuse persisted IDs; unseen rows, dates, statuses, order, similarity, or reused source IDs alone do not prove identity. Evidence thresholds and client criteria remain open. |
| PD-003 | Approved Option C ambiguity handling. | Ambiguous, conflicting, or insufficiently evidenced records remain unresolved and are excluded from identity-dependent processing until disposition; no silent resolution. |
| PD-004 | Approved Option C history/correction principles. | Preserve prior episodes and mapping lineage; corrections must be traceable and must not silently replace history. Detailed workflow and technical representation remain open. |
| PD-005 | Approved Option B historical migration principles. | Partial historical acceptance is permitted where sufficient evidence exists; unresolved records are not silently assigned. Client-specific coverage and acceptance evidence remain required. |
| PD-006 | Approved Option B availability policy. | Snapshots are optional for basic ingestion and required for temporal-modelling workflows; usage and invoices remain optional. The current loader has not implemented snapshot optionality. |
| PD-007 | Approved Option C compatibility/versioning principles. | Classify exact changes against real consumers and validators; semantic changes may break compatibility without structural changes. No version or coexistence policy is assigned here. |

Approved decisions above constrain the target, while the current implementation described in Sections 8–11 remains the observed behavior. Open DD items in Section 17 must not be treated as approved requirements.

## 4. Contract Baseline Comparison

| Topic | Contract v1.1 baseline | Semantic Revision Proposal | Assessment |
|---|---|---|---|
| Prediction entity | Subscription-level prediction granularity is documented; the subscription row is one row per subscription. | A contractual episode is the prediction entity and one row represents one canonical episode. | Semantic clarification/change aligned with ADR-009 and EP-DEC-002; source-system “subscription” may not have the same grain. |
| `customer_id` | Customer/account identifier and customer primary key. | Continues to identify the associated customer/account. | No intended change; it is not the prediction identifier. |
| `subscription_id` | Unique subscription identifier; string key referenced by dependent datasets. | Nowa-owned canonical identifier for one contractual episode, issued/reused under ADR-010 and PD-002. | Major semantic and supply change despite the same field name/type. |
| Episode identity | Episode boundaries and lifecycle interpretation are unresolved in v1.1. | Canonical episode identity is explicit; termination followed by reactivation creates a new episode. | Direction approved, but source evidence, precise boundaries, and historical attribution remain unresolved. |
| Reactivation | Open in v1.1. | Following termination, reactivation creates a new episode and prior episode history is preserved. | EP-DEC-005 approved; operational criteria are not thereby defined. |
| Historical preservation | Snapshot history is required for temporal modelling; episode identity/mapping lineage is not represented explicitly in the CSV contract. | Preserve prior episodes and identity history; migration can be partial where sufficient evidence exists. | Changes downstream interpretation and migration needs; no migration results are available. |
| Dataset availability | Contract identifies snapshots as required for temporal modelling; usage and invoices are optional. | Per PD-006, snapshots are optional for basic ingestion and mandatory for temporal-modelling workflows; usage and invoices remain optional. | Approved policy differs from current loader behavior and requires an explicit workflow interface. |
| Dependent references | `subscription_id` is used in snapshots, usage, and invoices. | Those references must identify the applicable canonical episode. | Semantic change affects all child references; existence checks alone cannot prove correct episode attribution. |
| Fields, types, nullability | Five datasets with defined field tables. | Proposal retains field names, types, and nullability; no source-ID/namespace fields are approved. | No structural delta is proposed in the semantic revision itself. Do not add unapproved fields. |
| Keys | Customer and subscription IDs unique; snapshots and usage composite keys; invoice ID unique. | Same CSV key shapes, interpreted against canonical episode identity. | Structural keys remain, but reference meaning and migration mapping change. |
| Validation | Contract field and temporal requirements; schemas enforce a subset. | Responsibilities remain divided among header inspection, normalization, schemas, and DQ. | Exact contract wording and actual enforcement differ; Section 10 identifies gaps. |
| Temporal conventions | Snapshot date convention and some lifecycle/coverage semantics remain open. | No first/last-of-month rule or new universal temporal convention is established. | DD-001 remains open. Do not invent date boundaries or attribution rules. |

## 5. Dataset-by-Dataset Compatibility Assessment

### 5.1 `customers.csv`

**Current and proposed grain:** One row per customer/account remains the intended grain. `customer_id` remains the unique customer/account identifier and the referenced customer key. The episode revision does not make a customer row an episode row.

**Fields, types, and key:** Contract v1.1 defines required string `customer_id` and required date/datetime `created_at`, with optional string `country`, `industry`, `company_size`, and `account_status`. The primary key is `customer_id`. The proposal does not add or remove customer fields or change their types/nullability.

**Relationship and compatibility:** `subscriptions.customer_id` continues to associate an episode with a customer/account. Multiple episodes may relate to one customer under the episode model. Existing one-customer/one-subscription assumptions in downstream consumers, if any, could be incompatible, but no consumer inventory establishes whether such assumptions exist. The customer schema's unique key check is compatible with this unchanged customer grain. No customer-level prediction identifier or new feature-selection rule is introduced by this assessment.

### 5.2 `subscriptions.csv`

**Grain:** Contract v1.1 currently says one row per subscription. The proposed target is one row per canonical contractual episode. This is the principal semantic change.

**Identifier:** The current field is a required unique string `subscription_id`; under the target it is the Nowa-owned canonical identifier for exactly one episode, generated only after authoritative evidence establishes a new episode and reused for a reliably recognized existing episode. A source-system subscription identifier is conceptually distinct. The proposal does not approve a source ID or namespace field. Source identifier availability, reuse, and exchange remain subject to DD-EP-002 and related decisions.

**Fields and key:** The existing fields and types are retained: required `subscription_id`, `customer_id`, `start_date`, and `subscription_status`; nullable `plan_id`, `end_date`, `billing_frequency`, `recurring_revenue`, `currency`, `auto_renew`, `cancellation_date`, and `cancellation_reason` with the types specified in v1.1. `subscription_id` remains unique, but its population and meaning change.

**Reactivation and history:** A confirmed reactivation following termination represents a new episode with a new canonical ID; the prior episode and identity history must be preserved. A cancellation label, row arrival, date/status combination, row order, or heuristic similarity by itself does not establish a new or existing episode. Exact lifecycle/event evidence remains unresolved.

**Compatibility implications:** Producers that currently put a source subscription key in `subscription_id` cannot be presumed compatible with a canonical Nowa ID contract. Consumers joining or aggregating on that column may change behavior even if their code still parses a string. Existing records may need reconciliation; no evidence supports a universal mapping or a claim that current IDs already represent episodes.

### 5.3 `subscription_snapshots.csv`

**Grain and key:** Contract v1.1 defines snapshot observations for subscriptions, uniquely keyed by (`subscription_id`, `snapshot_date`). The proposed interpretation makes `subscription_id` a canonical episode reference; the composite key remains structurally the same. The required fields remain subscription ID, snapshot date, and status; revenue, currency, plan, billing frequency, and auto-renew fields remain optional under the contract.

**Attribution:** Existing references must resolve to the correct episode, not merely to any existing subscription row. Snapshot-to-episode attribution remains a client/source-evidence dependency (DD-EP-008); FK existence alone cannot establish correctness. No first/last day of month convention or new cutoff semantics are inferred.

**Availability:** Approved PD-006 changes snapshots from unconditionally required for the current basic loader to optional for basic ingestion and mandatory when a workflow claims temporal modelling. The current loader incompatibility is concrete and described in Section 8. Existing integration tests encode current unconditional requirement, not the approved target policy.

### 5.4 `usage_monthly.csv`

**Grain and key:** The contract defines monthly usage keyed by (`subscription_id`, `usage_month`). Under the proposed interpretation, the ID refers to one canonical episode. A subscription may have multiple monthly rows, but it is unresolved whether one row per episode/month is sufficient when an existing source usage period spans a termination/reactivation boundary or another episode boundary.

**Period semantics and attribution:** DD-EP-009 leaves source usage period semantics and episode attribution open; DD-EP-010 leaves treatment of periods crossing episode boundaries pending product decision. `usage_month` alone does not establish period start/end, availability, or which episode receives usage. TC-007 remains pending. No split, duplication, allocation, or date-based attribution policy is proposed here.

**Compatibility and migration:** A reference that used to identify a source subscription object may need to identify a canonical episode. Existing usage cannot be reassigned safely without appropriate evidence. The dataset remains optional under PD-006. Whether the unchanged composite key can represent every source record is undetermined pending client source semantics and downstream usage requirements.

### 5.5 `invoices.csv`

**Grain and key:** Invoice rows remain at invoice grain, keyed by required unique `invoice_id`. Contract v1.1 requires a non-null string `subscription_id` on each invoice. The proposed meaning is a reference to one canonical episode; neither the field's presence nor an existing FK check proves that a historical invoice can be attributed to one episode.

**Historical attribution:** DD-EP-011 leaves invoice-to-episode attribution pending. Invoice dates alone do not prove which episode incurred an invoice, and there is no approved allocation rule for invoices spanning multiple episodes. An invoice that cannot yet be reliably attributed creates a compatibility/migration issue under PD-003, but this assessment does not make `subscription_id` nullable or change its requiredness.

**Compatibility:** Existing producers may supply source subscription identifiers, while downstream consumers may rely on invoice-to-subscription joins. The required field and current schema should remain unchanged absent an approved structural change. The invoices dataset remains optional as a dataset; when supplied under current contract it still has its required columns and row-level requirements.

## 6. Semantic Compatibility Analysis

| Change | Current meaning | Proposed meaning | Why it matters | Affected producers/consumers | Evidence required | Preliminary classification |
|---|---|---|---|---|---|---|
| Subscription row grain | One row per subscription. | One row per canonical contractual episode. | A source subscription object may contain multiple episodes; row counts and lifecycle interpretation can change. | Source exports, ingestion, model dataset construction, reporting. | Source lifecycle semantics, episode boundaries, actual export examples, consumer assumptions. | **Potentially breaking**; exact impact undetermined. |
| Canonical `subscription_id` | Unique subscription identifier, potentially supplied from a source; actual supply is unverified. | Nowa-owned stable ID for one episode, generated/reused through approved identity principles. | Joins may silently become incorrect if producers/consumers assume source-object identity. | All datasets, producers, DQ, models, reporting, migration. | Producer field provenance, current key semantics, exchange design, consumer inventory. | **Potentially breaking; high risk**. |
| Source versus canonical IDs | Contract does not fully distinguish source ID from canonical identity. | Source identifier and canonical episode identifier are distinct concepts; no source field is yet approved. | Existing source keys cannot be presumed suitable for canonical identity or stable across episodes. | Source integrations, registry, CSV producers. | Client source ID availability/reuse and namespace topology. | **Undetermined**. |
| Reactivation | Open in v1.1. | Terminated episode followed by reactivation creates a new episode; prior episode preserved. | Historical records may require episode separation and remapping. | Producers, identity resolution, migration, snapshots/usage/invoices, models. | Evidence for termination effectiveness and reactivation; episode boundary decisions. | **Potentially breaking; high risk**. |
| Historical preservation | Historical snapshots exist, but canonical episode lineage is not explicit in the interface. | Preserve prior episode IDs and mapping history; no silent replacement. | Existing records and correction history must be retained and traceable. | Registry, migration, storage/reporting consumers. | Historical mappings and accepted evidence, retention and correction process. | **Potentially breaking**. |
| Dependent FK meaning | `subscription_id` references subscription rows. | References identify canonical episodes. | FK existence may pass while pointing to the wrong episode. | Snapshot, usage, invoice producers and consumers; RI validators. | Reliable dataset-specific attribution evidence. | **Potentially breaking; high risk**. |
| Snapshot interpretation | Snapshot keyed to subscription/date, required for temporal modelling. | Snapshot is episode state; optional for basic ingestion, required for temporal modelling. | Both reference meaning and dataset availability behavior change. | Loader, workflow selection, model eligibility, DQ reporting. | Workflow definition and exact interface; snapshot attribution/coverage. | **Potentially breaking behavior change**. |
| Usage period interpretation | One monthly row per subscription/month. | One monthly row per canonical episode/month is implied by key, but crossing episodes is unresolved. | Existing period may straddle episode boundaries; no allocation rule exists. | Usage producers, feature builders, model training. | Source period boundaries and approved crossing-period disposition. | **Undetermined**. |
| Invoice attribution | Required subscription reference on invoice. | Reference should identify a canonical episode, but attribution policy/evidence is unresolved. | Invoice may be attributable to a source account/subscription but not one episode. | Billing exports, financial features, reports, migration. | Invoice service-period semantics and client source evidence. | **Undetermined; high risk**. |

No field-name or string-type change is needed for the semantic change to affect compatibility. Conversely, semantic alignment does not establish that a particular producer can supply canonical IDs.

## 7. Structural Compatibility Analysis

The Semantic Revision Proposal retains current dataset fields, types, nullability, and key shapes. Its intended contract delta is primarily semantic. The following classifications apply to the proposal as inspected, not to a future unreviewed CSV design.

| Structural element | Proposed delta from v1.1 | Preliminary classification | Qualification |
|---|---|---|---|
| Field names and presence | No fields added, removed, or renamed. | **No structural change** | Source ID/namespace fields are not approved; do not add them by implication. |
| Requiredness/nullability | Existing field-level requirements retained. | **No structural change** | In particular, invoice `subscription_id` remains required; attribution uncertainty is not authorization to make it nullable. |
| Data types | Existing types retained. | **No structural change** | Normalization output and Pandera expectations still require consistent interfaces. |
| Primary/composite keys | Same keys retained, with canonical episode semantics for subscription references. | **No key-shape change; semantic change** | FK meaning is material even when key structure is identical. |
| Dataset availability | Snapshots optional for basic ingestion, required for temporal modelling; usage/invoices optional. | **Potentially breaking behavioral/interface change** | Current loader unconditionally requires snapshots. Workflow-mode mechanism and consumer expectations are not settled. |
| CSV conventions | No proposal to change delimiter, encoding, header, or record structure. | **No structural change proposed** | Current strict header and row-width behavior limits tolerance for variations. |
| Additive source identity fields | None approved. | **Not proposed** | Any future addition needs client evidence, exact contract delta, and consumer assessment. |

An exact future contract diff and actual consumer inventory are necessary before final backward-compatibility classification. No consumer compatibility or coexistence strategy is established by the current evidence.

## 8. Dataset Availability Compatibility

Approved PD-006 target policy is: `customers` and `subscriptions` required; `subscription_snapshots` optional for basic ingestion but mandatory for workflows claiming temporal modelling; `usage_monthly` and `invoices` optional. Current code in `csv_ingestion.py` defines customers, subscriptions, and snapshots as `REQUIRED_DATASETS`, and usage and invoices as `OPTIONAL_DATASETS`. `ingest_client_datasets()` therefore rejects missing snapshots without a workflow distinction.

Consequences requiring authorized design and implementation work:

- **`REQUIRED_DATASETS` / `OPTIONAL_DATASETS`:** The current constants encode a single unconditional requirement. Moving snapshots to a basic-ingestion optional path requires a workflow-aware policy without selecting an interface here.
- **File discovery and headers:** Header inspection has per-dataset column definitions but does not decide whether a dataset may be absent. Missing-file policy must be coordinated with ingestion rather than treated as a header issue.
- **Ingestion:** Current missing required files raise errors; missing optional files are accepted. A present optional file is still parsed and invalid content fails. The target must preserve validation of supplied files while distinguishing basic and temporal workflows.
- **DQ presence reporting:** The DQ specification treats optional-dataset absence as informational/non-blocking; the DQ report/coordinator is not implemented. Dataset presence can be reported independently of rule implementation/runtime results.
- **Downstream modelling eligibility:** Absence of snapshots may permit basic ingestion but cannot establish temporal-modelling eligibility. Required coverage or minimum-history thresholds remain unresolved (DD-002); no automatic eligibility threshold is proposed.
- **Integration tests:** Existing tests verify missing snapshots fail as a required dataset and that missing usage/invoices are accepted. They reflect the current implementation and will need a separately approved update if the policy is implemented.

No workflow-mode argument, default, dataset state, or API is selected in this assessment. Snapshot optionality implementation is not authorized here.

## 9. Header Inspection and CSV Ingestion Impact

Inspected modules are `src/nowa_customer_intelligence/data/ingestion/header_inspection.py` and `csv_ingestion.py`; tests include unit coverage for each and `tests/integration/test_csv_ingestion.py`.

- **`DATASET_COLUMNS`:** Header inspector maintains known column names for all five datasets. An unknown header, duplicate header, empty/whitespace header, malformed header, or invalid UTF-8 in the inspected header is rejected. It checks header structure, not episode identity or dataset availability policy.
- **Required headers:** The inspector's required/optional column definitions align with the contract field tables. `strict=True`-style header rejection means adding a new column to an input is not automatically backward-compatible for this loader. Missing optional columns are supported through the current schema/loader design as tested; required headers remain required.
- **Row width:** Ingestion checks record width against the header and errors on mismatched records. It does not establish semantic equivalence of IDs or attribution.
- **Encoding:** Header inspection uses UTF-8 with BOM handling and inspects the header; invalid header encoding is rejected. This behavior is covered by focused tests. No encoding change is proposed.
- **Dataset presence:** Customers, subscriptions, and snapshots are required in the current loader; usage and invoices are optional. A missing optional file is accepted, while a present invalid optional file is still processed and may fail. Empty-file behavior must be distinguished from missing-file behavior; existing integration tests include header-only required datasets. The governing documents do not settle a universal empty-file policy for all workflows.
- **Repeat submissions:** The code does not interpret a repeated file submission as a new episode. This is consistent with PD-002; identity issuance and idempotent registry behavior are not implemented by the loader.

The canonical-ID semantic shift does not itself change CSV header parsing, but it changes what producers must place under the same header and what joins mean downstream. Snapshot availability is a direct behavioral mismatch between approved policy and current implementation.

## 10. Type Normalization and Pandera Compatibility

Inspected code includes `preprocessing/type_normalization.py` and the five schemas under `schemas/`. Schemas use `strict=True`, `coerce=False`, and `add_missing_columns=True`; normalization is a separate explicit stage. The normalizer returns normalized copies and maps string, datetime, numeric, nullable `Int64`, and nullable boolean fields. It does not create canonical episode identity or silently resolve ambiguous references.

| Concern | Current implementation evidence | Compatibility assessment |
|---|---|---|
| Strictness/coercion | Schemas reject unexpected columns and do not coerce values; missing optional schema columns can be added according to schema configuration. | Exact contract field changes and stage order matter. No automatic compatibility for added producer columns should be assumed. |
| Identifiers | String fields have non-null/non-empty/whitespace constraints; subscription ID is unique in subscriptions. | Type and key shape fit the proposal, but schema validation cannot establish Nowa ownership, authoritative issuance, or episode meaning. |
| Dates | Normalizer converts declared date fields to datetime representations; schemas require date/datetime-compatible fields and nullability. | Normalized types support present-column comparisons, but do not resolve episode boundaries or source date semantics. |
| Numeric/boolean nullability | Nullable numeric and boolean types are explicitly normalized; schema fields retain nullable behavior. | No proposed field-type change. CSV representation and normalized values must remain aligned. |
| Status values | Schemas enforce canonical subscription, snapshot, and invoice status values. Contract v1.1 describes some status sets as provisional/client-mappable; mapping is not implemented and DD-007 remains open. | Contract-to-schema operational discrepancy: source values may require an approved pre-schema client mapping stage. This assessment does not add one. |
| Currency | Schema checks three uppercase letters; full ISO 4217 membership is not guaranteed by regex. DQ BR-005 is pending decision. | Shape validation is narrower than complete official membership; no dependency/reference-list policy is approved. |
| Keys | Customer ID unique; subscription ID unique; snapshot and usage composite keys; invoice ID unique. | Key checks establish row-level uniqueness only. They do not establish canonical identity or correct child-to-episode attribution. |
| Field checks | Schemas enforce documented nonnegative numeric constraints, identifier formats, allowed values, and selected date constraints. | Some contract temporal requirements are implemented in DQ; others remain pending. Do not duplicate existing schema checks in DQ. |

The actual schema and normalizer behavior should be treated as the current executable interface, not as proof that all v1.1 language is enforced. No schema or normalizer changes are proposed or authorized by this assessment.

## 11. Data Quality Compatibility

The DQ specification and implementation distinguish schema-level validation from cross-dataset/lifecycle checks. Current implementation status documented in the DQ specification is summarized below; “implemented” means the rule code exists, not that it verifies canonical episode attribution.

| Rule group | Current status | Compatibility relevance |
|---|---|---|
| RI-001–RI-004 | `IMPLEMENTED_IN_DQ` | Current referential checks establish existence relationships for required and recognized optional datasets. They do not verify that a reference identifies the correct episode. |
| RI-005 | `PROPOSED` | Must remain unimplemented unless explicitly authorized; no compatibility behavior should be assumed. |
| TC-001 and TC-002 | `IMPLEMENTED_IN_DQ` | Compare present subscription end/cancellation dates with start date; they do not determine episode boundaries or validate dependent-record attribution. |
| TC-003 and TC-007 | `PENDING_DECISION` | Snapshot/usage lifecycle checks depend on reliable episode attribution and unresolved date/period semantics. |
| BR-006 | `PROPOSED` | Optional dataset absence is intended informational/non-blocking policy but must not be represented as executed while unimplemented. |

Referential integrity can pass when a child ID exists in the parent table yet still refer to the wrong canonical episode. Neither current RI logic nor the Pandera FK-related field constraints determine whether source evidence supports that mapping. Identity-dependent processing must respect PD-003 for unresolved records. Any future DQ changes depend on the approved contract delta, attribution decisions, and explicit implementation authorization. Full DQ report construction and coordination are not implemented, so report-level behavior should not be inferred from rule functions alone.

## 12. Historical Data and Migration Compatibility

The repository contains no live client history, migration crosswalk, or evidence sufficient to identify existing IDs as source subscription objects versus canonical episodes. Consequently, no migration result, split, join, or automatic mapping can be asserted.

- Existing `subscription_id` values require provenance review. ADR-010/PD-002 require canonical Nowa IDs issued after authoritative evidence and reused for recognized episodes. An existing value cannot be assumed canonical merely because it is unique or is present in every dataset.
- Historical termination/reactivation may mean one source subscription history contains multiple canonical episodes. EP-DEC-005 requires a new episode after confirmed reactivation and preservation of the previous episode; boundary evidence remains client-dependent.
- Existing snapshots, usage rows, and invoices need episode-level attribution if their references change meaning. A matching FK is insufficient evidence. Usage crossing episode boundaries has no allocation rule; invoice service/episode attribution is unresolved.
- Source identifier reuse can represent multiple episodes and cannot alone establish identity. Source namespace representation and exchange remain open.
- PD-003 requires ambiguous or insufficient identity records to remain unresolved and excludes them from identity-dependent processing until disposition. PD-004 and ADR-010 require traceable corrections and preserved identity/mapping history.
- PD-005 permits partial historical acceptance where sufficient evidence exists; it does not prescribe universal evidence thresholds or claim that all legacy rows can be migrated. Client-specific coverage, evidence, and accepted/rejected/unresolved counts must be established in a later authorized migration assessment.

Migration planning should identify retained originals, canonical assignments, dependent-record mappings, unresolved cases, and lineage in a traceable way once evidence and technical design are approved. This is a planning implication, not a defined storage format or migration implementation.

## 13. Consumer and Producer Compatibility

Potentially affected categories are:

| Category | Potential impact | Repository evidence / limitation |
|---|---|---|
| Client source systems | Whether source keys, lifecycle events, and dependent records can support canonical episode identity. | No live data or client source inventory; source semantics are unresolved. |
| CSV producers | Meaning and provenance of `subscription_id`; snapshot file presence by workflow; field values under unchanged headers. | Current interface is documented and tested locally, but no external producer is inventoried. |
| CSV ingestion | Snapshot requirement policy and workflow distinction. | Current loader implementation is present and tested; approved PD-006 differs. |
| Internal data preparation | ID mapping, history preservation, ambiguity disposition, and episode-level child attribution. | Current normalization does not implement identity resolution. |
| Pandera validators | Existing strict columns, types, nullability, uniqueness, and field checks. | All five schemas inspected; they do not validate identity provenance. |
| DQ components | Referential existence, date comparisons, future attribution-aware rules and dataset presence. | RI/TC functions exist; full coordinator/report is absent; rule statuses vary. |
| Model training datasets | Episode-level prediction rows, possible leakage across episodes of one customer, snapshot eligibility, and correct feature attribution. | ADR-009 fixes episode-level unit; DD-EP-017 evaluation grouping/temporal strategy remains pending. |
| Prediction pipelines | Stable identifier reuse and consistent joins to episode-level outputs. | No deployed/external pipeline compatibility evidence available. |
| Reporting consumers | Assumptions about one subscription per customer, ID continuity, or invoice/usage aggregation. | No actual consumer inventory. |
| Historical migration processes | Reconciliation, partial acceptance, preserved mapping lineage. | No migration implementation or client evidence inspected. |

The repository's unit and integration tests demonstrate local component behavior only. They are not evidence of compatibility with external clients or downstream systems.

## 14. Compatibility Risk Register

Risk levels are preliminary. **HIGH** is used where repository behavior or approved semantic change directly creates a material failure mode. **UNDETERMINED** is used where the outcome depends on unavailable client/consumer evidence or an unresolved decision. No risk is rated solely from speculation.

| ID | Proposed change | Compatibility dimension | Affected component | Preliminary risk | Evidence/dependency | Required action |
|---|---|---|---|---|---|---|
| CR-01 | Reinterpret subscription row as one canonical episode. | Semantic | Producers, model data, reporting, migration | HIGH | v1.1 says subscription grain; proposal changes it; no client consumer inventory. | Validate source grain and consumer assumptions before final contract approval. |
| CR-02 | Canonical Nowa-owned `subscription_id` replaces/clarifies source ID meaning. | Semantic/supply | All datasets, producer exchange, joins, registry, migration | HIGH | ADR-010/PD-002 approve principles; source-ID availability/reuse and CSV exchange remain open. | Discover source keys and determine authorized exchange/mapping design; assess consumers. |
| CR-03 | Reactivation creates a new episode and preserves prior identity. | Lifecycle/history | Subscriptions, identity registry, dependent datasets, migration | HIGH | EP-DEC-005 approved; termination/effectiveness evidence and exact boundaries unresolved. | Resolve lifecycle evidence and test representative histories before migration design. |
| CR-04 | Child `subscription_id` references become canonical episode references. | Referential semantics | Snapshots, usage, invoices, RI, consumers | HIGH | Current RI validates existence; DD-EP-008/009/011 attribution open. | Establish dataset-specific evidence/attribution rules; preserve unresolved cases per PD-003. |
| CR-05 | Snapshot optional for basic ingestion but required for temporal workflows. | Behavioral | Dataset constants, discovery, ingestion, DQ, tests, model eligibility | HIGH | Approved PD-006; loader currently requires snapshots and integration test expects failure if absent. | Specify workflow behavior and authorize coordinated loader/test/report changes. |
| CR-06 | Keep one usage row per episode/month where source periods may cross episodes. | Semantic/structural sufficiency | Usage producer, feature builder, training | UNDETERMINED | DD-EP-009/010 and TC-007 unresolved; no allocation policy. | Establish source period semantics and product disposition before changing/affirming grain. |
| CR-07 | Keep invoice `subscription_id` required while episode attribution may be unavailable. | Semantic/migration | Invoice producers, schema, financial features, migration | UNDETERMINED | Contract requires the field; DD-EP-011 unresolved; no client data. | Assess whether reliable episode attribution exists; preserve requirement unless separately approved change. |
| CR-08 | Strict header/schema behavior meets changed producer output. | Structural/behavioral | Header inspection, schemas, external producers | MEDIUM | Code rejects unexpected columns and schemas are strict; exact proposed field set is unchanged. | Compare exact future contract with producers; test accepted headers and rows. |
| CR-09 | Snapshot optionality does not silently imply temporal eligibility. | Behavioral/modeling | Workflow selection, DQ, training | HIGH | PD-006 separates basic and temporal workflows; thresholds and workflow interface remain open. | Define eligibility and presence reporting before enabling temporal modeling. |
| CR-10 | Existing history can be mapped to canonical episodes. | Migration | Registry, data preparation, all dependent datasets | UNDETERMINED | PD-005 allows partial acceptance; no client history/evidence or crosswalk is available. | Perform client-specific evidence inventory; record accepted and unresolved populations. |
| CR-11 | Canonical status values are directly consumable from source exports. | Structural/validation | Producers, pre-schema mapping, schemas | MEDIUM | Schemas enforce canonical values; contract says some status sets provisional; DD-007 mapping open and absent. | Discover source values and approve mapping before relying on direct schema acceptance. |
| CR-12 | Existing external consumers tolerate unchanged-shape semantic changes. | Consumer compatibility | Client and internal consumers | UNDETERMINED | No actual producer/consumer inventory or contract tests. | Inventory consumers and obtain compatibility evidence before version classification. |

## 15. Contract Versioning Assessment

PD-007 Option C requires assessment of the exact delta, producers, strict consumers/validators, dependent references, migration, and release/deprecation needs. This assessment does not assign a version.

The proposal retains the field structure, so some clarifications may ultimately be compatible if consumers already implement the same semantics. However, changing `subscription_id` from a source/subscription identifier to a Nowa-owned ID for exactly one contractual episode can break joins and business interpretation while preserving the field name and string type. The same is true of changing row grain, reactivation representation, and child-reference meaning. Such changes may warrant a breaking major revision or staged migration, but that cannot be decided without exact approved contract text and consumer evidence.

Snapshot availability is a behavioral contract change relative to current code and tests. It may be a compatible relaxation for some clients but still changes workflow eligibility and loader behavior. A backward-compatible additive revision is not implicated by the present semantic proposal because no fields are approved for addition. Clarification within a compatible revision is only appropriate where it does not alter expectations; this cannot be presumed for the episode identity changes.

Before version assignment, resolve or bound the open semantic and client dependencies, produce the exact contract diff, inventory consumers/producers, assess migration and release needs, and follow DD-EP-016 governance. Temporary coexistence of versions is not assumed mandatory. Deprecation and migration principles must be decided before an incompatible release. The existing `1.1` versus `1.1.0` notation discrepancy is recorded in Section 17 and intentionally not resolved here.

## 16. Implementation Change Inventory

This is a future component inventory only. **No implementation is authorized by this assessment.**

| Component | Current behavior | Potential future change | Trigger/dependency | Authorization status |
|---|---|---|---|---|
| `DATASET_COLUMNS` | Header allowlist for five datasets; strict against unknown columns. | Change only if an approved contract field delta occurs. | Exact approved structural contract diff. | Not authorized. |
| `REQUIRED_DATASETS` | Customers, subscriptions, snapshots required. | Separate basic-ingestion from temporal-workflow snapshot requirement. | PD-006 interface/workflow design. | Not authorized. |
| `OPTIONAL_DATASETS` | Usage and invoices optional. | Preserve these; coordinate presence semantics in any workflow policy. | PD-006 and DQ reporting design. | Not authorized. |
| Header inspection | Validates UTF-8 header, column names/shape, duplicates, expected columns. | Likely no semantic identity logic; availability coordination may be needed. | Approved interface delta. | Not authorized. |
| CSV ingestion | Reads CSV values as strings without NA inference; validates widths; required/optional file behavior. | Implement approved snapshot workflow availability while validating any supplied file. | Workflow interface and PD-006 authorization. | Not authorized. |
| Type normalization | Converts declared types; does not resolve IDs or identity. | No episode logic unless separately designed/authorized. | Approved normalization requirements, if any. | Not authorized. |
| Customer schema | Strict schema; unique customer ID and field checks. | No change proposed by semantic revision. | Future exact field delta only. | Not authorized. |
| Subscription schema | Strict schema; unique ID and field checks/statuses. | Schema shape may remain; identity semantics cannot be proven by schema. | Contract wording and identity exchange design. | Not authorized. |
| Snapshot schema | Strict schema; composite (`subscription_id`, `snapshot_date`) uniqueness. | Key shape likely retained; canonical attribution remains outside schema. | Attribution and contract decisions. | Not authorized. |
| Usage schema | Strict schema; composite (`subscription_id`, `usage_month`) uniqueness and metric checks. | Key sufficiency/period rules may need later decisions; no policy selected. | DD-EP-009/010 and contract approval. | Not authorized. |
| Invoice schema | Strict schema; unique invoice ID and required subscription reference. | No nullable/reference change proposed; attribution issue is semantic/evidence-related. | DD-EP-011 and any separately approved delta. | Not authorized. |
| DQ validators | RI-001–004 and TC-001/002 implemented; other rules have pending/proposed statuses. | Attribution-aware checks only after semantics/evidence and rule approval. | DQ specification and contract decision. | Not authorized. |
| DQ reporting/coordinator | Data-quality models and rule functions exist; coordinating report construction is absent. | Coordinate presence, results, findings, and workflow policy if approved. | Architecture and implementation authorization. | Not authorized. |
| Synthetic fixtures | Tests use local fixtures; no live client data used. | Update fixtures for episode semantics only after rules/contract approved. | Approved contract and migration examples. | Not authorized. |
| Unit tests | Cover header, ingestion, normalization, schemas, RI, and TC behavior. | Add tests for authorized behavior and exact compatibility decisions. | Corresponding implementation authorization. | Not authorized. |
| Integration tests | Verify current required/optional file behavior and pipeline stages. | Update snapshot availability and end-to-end behavior under defined modes. | PD-006 interface design and authorization. | Not authorized. |
| Documentation | v1.1 approved; proposals and decision records are separate. | Revise contract and aligned docs after decisions and version assessment. | Formal approval/change control. | Not authorized. |

## 17. Open Decisions and Blocking Dependencies

### 17.1 Episode decisions

Statuses below preserve the governing episode specification. Approved principles remain approved; unresolved details remain open.

| Decision | Current status | Relevance to compatibility |
|---|---|---|
| DD-EP-001 — Contractual episode boundary | `PENDING_CLIENT_DECISION` | Requires source lifecycle evidence to distinguish episodes. |
| DD-EP-002 — Source subscription ID availability and reuse | `PENDING_CLIENT_DECISION` | Needed to understand source-to-canonical identity and producer exchange. |
| DD-EP-003 — Remaining Registry design/operational details | `PENDING_PRODUCT_DECISION` (partially resolved by ADR-010 and PD-001) | Core identity architecture and product functions approved; technical/operational details remain open. |
| DD-EP-004 — Source namespace metadata | `PENDING_CLIENT_DECISION` | Need/representation depends on source topology. |
| DD-EP-005 — Cancellation event semantics | `PENDING_CLIENT_DECISION` | Required evidence for episode termination and reactivation boundaries. |
| DD-EP-006 — Renewal/extension behavior | `PENDING_CLIENT_DECISION` | Can alter episode boundaries. |
| DD-EP-007 — Suspension/pause behavior | `PENDING_CLIENT_DECISION` | Lifecycle interpretation remains client-dependent. |
| DD-EP-008 — Snapshot-to-episode attribution | `PENDING_CLIENT_DECISION` | Blocks confident historical snapshot references. |
| DD-EP-009 — Usage-to-episode attribution | `PENDING_CLIENT_DECISION` | Blocks usage grain and reference interpretation. |
| DD-EP-010 — Usage periods crossing episode boundaries | `PENDING_PRODUCT_DECISION` | No allocation/splitting disposition selected. |
| DD-EP-011 — Invoice-to-episode attribution | `PENDING_CLIENT_DECISION` | Blocks confident invoice linkage. |
| DD-EP-012 — Historical migration acceptance | `PENDING_PRODUCT_DECISION` | PD-005 principles approved; client evidence and coverage still needed. |
| DD-EP-013 — Episode-level churn qualification | `PENDING_PRODUCT_DECISION` | Episode identity does not define the qualifying churn event. |
| DD-EP-014 — Customer-level churn | `DEFERRED` | Outside initial episode-level scope. |
| DD-EP-015 — Customer-level risk aggregation | `DEFERRED` | Outside initial episode-level scope. |
| DD-EP-016 — Contract version/backward compatibility | `PENDING_PRODUCT_DECISION` | Requires exact delta and consumer impact evidence; PD-007 principles are approved. |
| DD-EP-017 — Evaluation grouping/temporal strategy | `PENDING_PRODUCT_DECISION` | Downstream modeling dependency, including potential customer grouping/leakage; not a prerequisite for every contract clarification. |

### 17.2 Contract v1.1 decisions

The proposal's register records DD-001 through DD-015 as open in v1.1, with the following constraints relevant here. These entries are not resolved by this assessment.

| Decision | Current state in governing material | Relevance |
|---|---|---|
| DD-001 — Snapshot date convention | Open | No first/last-day convention may be assumed. |
| DD-002 — Historical coverage | Open | No minimum snapshot-history threshold. |
| DD-003 — Churn definition | Open | Episode identity does not settle qualifying churn. |
| DD-004 — Reactivation | Open in v1.1; direction superseded by approved EP-DEC-005 | New episode follows termination; source criteria remain unresolved. |
| DD-005 — Contract renewal | Open | Renewal/extension episode treatment remains unresolved. |
| DD-006 — Subscription episodes | Open in v1.1; canonical episode identity approved | Lifecycle, boundaries, and legacy representation remain open. |
| DD-007 — Subscription status | Open | Client-specific mapping to canonical statuses remains unresolved. |
| DD-008 — Revenue definition | Open | No MRR/ARR or equivalent interpretation is selected. |
| DD-009 — Currency handling | Open | Conversion and full currency-membership policy unresolved. |
| DD-010 — Timezone/cutoff | Open | No universal extraction cutoff/timezone convention. |
| DD-011 — Historical availability | Open | Recording/availability evidence may be missing from current fields. |
| DD-012 — Prediction horizon | Open | Provisional horizon not confirmed. |
| DD-013 — Observation window | Open | Provisional window not confirmed. |
| DD-014 — Customer aggregation | Open in v1.1; customer-level scope deferred under DD-EP-014/015 | Initial scope remains episode-level. |
| DD-015 — Missing data | Open | No completeness thresholds are established. |

### 17.3 Other dependencies and inconsistencies

- **Empty-file policy:** Integration tests accept header-only required datasets, while a dataset's empty status versus missing status is not fully defined across all workflows. Clarify intended policy before treating empty input as equivalent to valid zero-row data.
- **Source identifier exchange:** No source ID/namespace field is approved. Client discovery and a later product/contract decision are needed; do not infer source fields.
- **Client consumer inventory:** No external producers or consumers were inventoried. Compatibility classification and release planning remain incomplete without it.
- **Historical attribution:** Existing data and dependent rows cannot be reliably assigned to episodes from FK existence, row order, dates/status alone, or source ID reuse alone.
- **Version notation:** Contract versioning material contains a `1.1` versus `1.1.0` notation inconsistency. This assessment does not resolve it.
- **Snapshot workflow:** PD-006 policy is approved, but the interface for identifying basic versus temporal workflows is not selected.

## 18. Overall Readiness and Recommended Next Steps

| Readiness area | Assessment | Basis |
|---|---|---|
| Semantic contract approval | **PARTIALLY READY** | Episode identity principles are approved, but source evidence, boundaries, and dependent attribution remain open. |
| Structural contract revision | **PARTIALLY READY** | Proposal retains fields/types; exact normative wording and any future structural additions require separate review. |
| Source identifier exchange | **NOT READY** | Availability, reuse, namespace, and representation depend on client discovery and open decisions. |
| Snapshot optionality implementation | **PARTIALLY READY** | PD-006 is approved; workflow interface and implementation behavior remain undefined/currently incompatible. |
| Usage attribution | **NOT READY** | DD-EP-009/010 and TC-007 semantics remain unresolved. |
| Invoice attribution | **NOT READY** | DD-EP-011 is pending and required `subscription_id` cannot be silently relaxed. |
| Historical migration | **PARTIALLY READY** | PD-003/004/005 provide constraints and partial acceptance principles; client evidence and coverage are absent. |
| Consumer compatibility | **NOT READY** | No actual producer/consumer inventory or external compatibility tests. |
| Contract version assignment | **NOT READY** | Exact delta, consumers, migration, release/deprecation needs and DD-EP-016 remain open. |
| Coordinated implementation | **NOT READY** | This is an assessment; key semantics, workflow interface, and implementation authorization are outstanding. |

Recommended sequence:

1. Keep Contract v1.1 as the approved interface until a separately reviewed and approved change is issued.
2. Obtain client source and producer evidence for subscription identifiers, lifecycle events, snapshots, usage periods, and invoice attribution without presuming the evidence exists.
3. Inventory actual internal/external producers and consumers; determine their assumptions about row grain, identifier provenance, joins, and dataset availability.
4. Resolve episode boundaries and dependent-record attribution to the extent necessary for the exact contract scope; retain unresolved cases under PD-003 and avoid inventing usage or invoice allocation rules.
5. Define the basic-ingestion versus temporal-workflow contract behavior for PD-006 without making snapshot coverage assumptions that remain open.
6. Produce an exact proposed contract diff and assess each change under PD-007, including release, migration, and deprecation implications; resolve DD-EP-016 through its governing process.
7. Only after formal approval and explicit implementation authorization, coordinate changes across constants, ingestion, validation, tests, migration processes, and documentation. Do not implement decisions that remain pending or deferred.

This assessment does not approve the Semantic Revision Proposal, assign a contract version, authorize implementation, require temporary version coexistence, or resolve any open product/client decision.
