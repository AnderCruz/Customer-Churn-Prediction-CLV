# Product Decision Proposals

**Document ID:** NCI-PRODUCT-DECISIONS-001
**Version:** 0.2
**Status:** Product decisions approved; implementation not authorized
**Scope:** Phase 2.4.4.2.2 — Product Decision Proposals
**Assessment date:** 2026-11-15

## 1. Executive Summary

This document records seven product-owned decisions identified in the Phase 2.4.4.2.1 Product Decision Inventory. It provides approved decision records, remaining dependencies, and consequences. PD-001 through PD-007 have been approved as recorded below. Client-dependent evidence and joint decisions remain open where applicable. This document does not authorize contract or implementation changes.

ADR-010 and the approved Episode Specification establish binding architectural constraints: Nowa owns canonical episode identity; UUID is the initial generation strategy; canonical identifiers are generated once, persisted, and reused; a persistent, client-isolated Episode Identity Registry is required; ambiguous identity matches must not be silently resolved; each contractual episode is the prediction entity; termination followed by reactivation creates a new episode; previous episodes are preserved; and `customer_id` remains the distinct customer/account identity.

The seven decision areas are Registry functional requirements (PD-001), canonical ID issuance (PD-002), ambiguity disposition (PD-003), repeated CSV submissions (PD-004), historical migration acceptance (PD-005), dataset availability and snapshot requirements (PD-006), and contract versioning and compatibility (PD-007). PD-001 is **APPROVED** as Option B, PD-002 is **APPROVED** as Option B, PD-003 is **APPROVED** as Option C, PD-004 is **APPROVED** as Option C, PD-005 is **APPROVED** as Option B, PD-006 is **APPROVED** as Option B, and PD-007 is **APPROVED** as Option C, all on 2026-11-15. Client-dependent and joint decisions remain open where applicable. Client source facts remain unknown and must not be inferred, and decisions requiring client evidence or joint agreement remain open.

## 2. Binding Architectural Constraints

The following requirements from accepted ADR-010 and approved EP-DEC-001–005 / episode identity decisions are constraints on every proposal here, not decisions to reopen:

- Nowa Analytics owns the canonical `subscription_id`; it identifies exactly one contractual episode, is stable throughout its lifecycle, and is never reassigned.
- UUID is the approved initial canonical ID generation strategy. Generate it once when a new episode is authoritatively established, persist it, and reuse it across subsequent submissions and ingestion executions. The UUID version and implementation mechanism remain undecided.
- A persistent Episode Identity Registry is required to associate canonical IDs with verified source identifiers when available, recognize episodes across repeated submissions, enforce client isolation, and preserve identity history and mapping lineage.
- Ambiguous identity matches must be surfaced and must not be silently resolved. Date proximity, status, row order, or heuristic similarity is not proof of identity.
- One contractual episode is the initial prediction entity. One customer may have multiple episodes.
- Reactivation following termination creates a new episode. Prior episodes and their historical identity must be preserved.
- `customer_id` remains the customer/account identity and is distinct from the episode prediction entity.

ADR-010 does not specify UUID version, Registry schema or storage, APIs, operational ownership, conflict and correction workflows, retention or deletion, source namespace representation, or exact CSV exchange mechanics. This proposal does not decide those technical details.

PD-001 Option B additionally approves product-level Registry requirements for conflict detection, visibility of unresolved identity, traceable mapping corrections, auditable identity and mapping history, and preservation of prior mapping lineage. Its approval does not decide the technical or operational details listed above.

## 3. PD-001 — Episode Identity Registry Functional Requirements

**Decision context:** ADR-010 approves the persistent Registry and its core responsibilities. PD-001 Option B is now approved for additional product-level functional outcomes; technical and operational design remains outside its scope.

### Requirements already imposed by ADR-010

The Registry must persist canonical episode identity; associate it with verified source-system identifiers when available; support recognition across repeated submissions and creation for authoritatively established new episodes; isolate client data; preserve identity history and mapping lineage; and prevent silent resolution of ambiguous matches.

### Options and trade-offs

| Option | Advantages | Disadvantages |
|---|---|---|
| A. Treat the ADR-010 responsibilities as the entire acceptance boundary and defer operational criteria | Minimizes premature specification. | Leaves product acceptance, visible unresolved states, and correction expectations underspecified. |
| B. Define additional product-level functional outcomes while deferring workflow and technology | Makes later review and implementation acceptance more concrete without selecting a design. | Product approval is recorded; client evidence is still needed to define what counts as a verified source identity in each context. |
| C. Specify a complete Registry service now | Could appear to accelerate delivery planning. | Would prematurely settle storage, APIs, operations, and conflict processes that ADR-010 explicitly leaves open and that require design authorization. |

**Recommendation — APPROVED (2026-11-15):** Option B was selected. In addition to the approved ADR-010 core, the Registry must support detection of conflicting identity evidence, visibility of unresolved or ambiguous identity, traceable mapping corrections, auditable identity and mapping history, and preservation of previous mapping lineage so corrections never silently erase historical associations. These are product-level functional requirements. Detailed workflows, audit record format, authorization mechanics, storage, APIs, cloud/deployment architecture, operational ownership, UUID version/generation implementation, namespace representation, mandatory source identifier fields, and Registry implementation remain outside this approval.

**Dependencies and consequences:** Interacts with client/source evidence under DD-EP-002 and DD-EP-004, the approved issuance principle in PD-002, and the approved PD-003 isolation policy. Operational handling beyond the approved policy remains open. It supports reliable CSV ingestion, migration, and dependent-dataset attribution but does not itself establish the truth of client source keys. It does not authorize a Registry implementation.

**Approval record**

| Field | Approved record |
|---|---|
| Decision | PD-001 — Episode Identity Registry Functional Requirements |
| Selected option | Option B — Define additional product-level functional outcomes while deferring workflow and technology |
| Approval date | 2026-11-15 |
| Approved scope | Conflict detection; visibility of unresolved or ambiguous identity; traceable mapping corrections; auditable identity and mapping history; preservation of previous mapping lineage so corrections never silently erase historical associations. |
| Exclusions | Storage/database, APIs/service/cloud/deployment architecture, audit record format or technical logging implementation, authorization mechanics, operational ownership, detailed conflict/correction workflows, UUID version or generation implementation, source namespace representation, mandatory source identifier fields, CSV identity exchange, and Registry implementation. |

## 4. PD-002 — Canonical ID Issuance

**Decision context:** ADR-010 approved one-time UUID generation, persistence, and reuse; PD-002 Option B now approves issuance only after authoritative evidence establishes a new episode. The evidence and client/context-specific application remain open.

| Situation | Approved product principle |
|---|---|
| A new episode is authoritatively established | Nowa may issue one new canonical UUID and persist its identity in the Episode Identity Registry. |
| An existing episode is reliably recognised | Reuse its previously persisted canonical `subscription_id`; do not generate a replacement ID. |
| Reactivation following termination is confirmed | Treat it as a new episode with a new canonical ID; preserve the previous episode and its identity. |
| Identity evidence is ambiguous, conflicting, or insufficient | Do not automatically issue or reuse an ID. Keep the identity unresolved until an appropriate disposition is established. |
| A CSV row is previously unseen | The row’s novelty alone is not evidence of a new episode. |
| Dates, statuses, row order, or heuristic similarity are present | None, individually or collectively without authoritative supporting evidence, proves episode identity. |
| A source identifier is reused across multiple episodes | Reuse alone does not establish that those episodes are the same episode. |
| A record is corrected or arrives late | Preserve identity history and require evidence to associate it with an existing or new episode. Correction and late-arrival behavior remains subject to PD-004 and migration policy. |

### Options and trade-offs

- **A. Issue only when an authoritative canonical identity or approved mapping is supplied.** This reduces Nowa-side ambiguity but depends on an exchange mechanism and source/client capability not yet established.
- **B. Issue a canonical ID only after authoritative evidence establishes a new contractual subscription episode.** This is the selected product policy; evidence availability and verification remain client/context dependent.
- **C. Issue for every previously unseen row and reconcile later.** This is operationally simple at first but can create duplicate or wrongly split identities and does not satisfy stable recognition safely.

**Decision — APPROVED (2026-11-15): Option B selected.** Issue a canonical ID only after authoritative evidence establishes a new contractual subscription episode. Apply the principles in the table above: issue one new UUID and persist it in the Registry for an authoritatively established new episode; reliably recognised episodes retain their persisted canonical ID; confirmed reactivation after termination receives a new ID while preserving the previous episode; ambiguous, conflicting, or insufficient evidence triggers neither automatic issuance nor reuse; row novelty is not evidence; dates, statuses, row order, and heuristic similarity are not proof without authoritative supporting evidence; and a reused source identifier alone does not establish episode identity. UUID generation alone does not establish episode identity.

**Approval record**

| Field | Approved record |
|---|---|
| Decision | PD-002 — Canonical ID Issuance |
| Selected option | Option B — Issue a canonical ID only after authoritative evidence establishes a new contractual subscription episode |
| Approval date | 2026-11-15 |
| Approved scope | The seven canonical ID issuance, reuse, reactivation, ambiguity, row novelty, identity evidence, and reused-source-identifier principles stated above. |
| Exclusions | Universal evidence thresholds or mandatory source fields; client-specific identity verification criteria; universal methods for identifying episodes without stable source identifiers or proving reactivation; source namespace representation; UUID version or technical generation implementation; Registry schema, storage, APIs, transactions, or operational workflows; duplicate-record criteria or detailed disposition; CSV submission, correction, or late-arrival semantics; further ambiguity disposition beyond the approved PD-003 principles; and implementation authorization. |

**Dependencies and consequences:** Client/context-specific application depends on DD-EP-001–004 evidence; the approved PD-003 isolation principles constrain handling of unresolved identity, while any further resolution or rejection procedure remains open. It affects the subscription key and dependent dataset references, Registry behavior, ingestion, and migration. A generated UUID alone does not establish episode identity or idempotency.

## 5. PD-003 — Ambiguous Identity Handling

**Decision context:** ADR-010 requires ambiguity to be surfaced and prohibits silent resolution. PD-003 Option C is approved: explicitly attributable records may be accepted while ambiguous, conflicting, or insufficiently supported identity records are isolated as unresolved and excluded from identity-dependent processing. Record-level acceptance remains distinct from submission-level acceptance.

| Option | Data integrity | Operations and client experience | Model eligibility and audit |
|---|---|---|---|
| A. Reject the affected record or submission | Prevents uncertain identity from entering accepted data. | Simple boundary, but may block otherwise usable records or require resubmission. | Requires a clear rejection reason and retained evidence; excludes rejected data until corrected. |
| B. Hold unresolved records for authorized review | Preserves the opportunity to resolve identity with evidence. | Requires a controlled review process, ownership, and turnaround expectations. | Keeps records out of identity-dependent use pending resolution; requires a durable unresolved state and review history. |
| C. Accept an explicitly attributable subset and isolate unresolved records | Allows verified records to proceed without assigning identity to unresolved records. | More complex partial-acceptance communication and reconciliation. | Requires explicit exclusions, coverage reporting, and checks that downstream use cannot accidentally include unresolved records. |

Option C is conditional on explicit episode attribution: accepting an attributable record does not permit unresolved records in the same submission to enter identity-dependent processing. Record-level acceptance and submission-level acceptance are separate. This decision permits an attributable subset to proceed; it does not by itself accept or reject an entire submission, and it does not permanently reject unresolved records. An accepted subset must not be represented as complete client history or as the full population. Matching by dates, status, row order, or similarity without authoritative supporting evidence must never establish episode identity.

**Decision — APPROVED (2026-11-15): Option C selected.** Only records whose contractual episode identity is established with sufficient authoritative evidence may enter identity-dependent processing. Ambiguous, conflicting, or insufficient identity records must be explicitly isolated as unresolved and excluded from episode-level training, evaluation, and predictions. Reports must disclose the number and proportion of accepted and unresolved records. Accepted records must retain traceability to their source and the evidence supporting their episode attribution. Unresolved records must not receive automatically generated or reused canonical `subscription_id` values merely to enable acceptance. Partial acceptance does not establish complete historical coverage or full-population representation.

**Approval record**

| Field | Approved record |
|---|---|
| Decision | PD-003 — Ambiguous Identity Handling |
| Selected option | Option C — Accept an explicitly attributable subset and isolate unresolved records |
| Approval date | 2026-11-15 |
| Approved scope | Accept only records with sufficiently authoritative episode attribution for identity-dependent processing; isolate and exclude unresolved records from episode-level training, evaluation, and predictions; disclose accepted and unresolved counts and proportions; preserve source/evidence traceability for accepted records; do not assign unresolved records canonical IDs to enable acceptance; do not characterize partial acceptance as complete history or full-population representation. |
| Exclusions | Technical representation/storage of unresolved records; Registry schema/database/APIs/implementation; manual review workflows or ownership; conflict-resolution authority; service levels; numerical thresholds or minimum coverage; universal client acceptance criteria; submission-level rejection policy; correction, resubmission, or late-arrival semantics; model-specific eligibility thresholds beyond unresolved-record exclusion; and implementation authorization. |

**Dependencies and consequences:** Applies with client evidence under DD-EP-002/004/008–011 and the migration principles in PD-005. It constrains Registry, ingestion, reporting, onboarding, and model eligibility without defining technical isolation, operational review, or submission-level acceptance/rejection. A product policy cannot substitute for client evidence.

## 6. PD-004 — Repeated CSV Submission Semantics

**Decision context:** ADR-010 requires reuse of the canonical ID for a recognized episode on subsequent submissions and prohibits replacement IDs merely because a file is reimported. PD-004 Option C establishes each received file as a new submission event while keeping submission receipt, record/content version, canonical episode identity, and historical lifecycle separate. Technical and operational details remain open.

| Submission case | Approved principle and remaining question |
|---|---|
| Identical file submitted again | Each receipt is a new submission event, but not necessarily a new record or episode. File-level hashing or duplicate-file detection remains open; recognised episodes reuse their persisted IDs. |
| Existing episodes plus new episodes | Reuse IDs for reliably recognised episodes; issue new IDs only under PD-002. Isolate unresolved records under PD-003. |
| Corrected record | Corrections must not silently overwrite identity or mapping history. The technical versioning and correction workflow remain open. |
| Late-arriving historical record | Preserve identity history and do not infer identity from its date alone. Evidence and late-arrival handling remain open. |
| Changed source identifier | Assess using evidence; preserve prior and current mapping lineage if corrected. Client-specific criteria and correction mechanics remain open. |
| Record conflicts with an existing mapping | Follow PD-003: isolate unresolved identity; do not silently overwrite mappings. Detailed conflict and correction workflows remain open. |
| Record appears to be a reactivation | Only authoritative evidence can establish the new episode; under PD-002 it receives a new canonical ID and the prior episode remains preserved. |

### Options and trade-offs

- **A. Treat repeat files as idempotent submissions where records map to known episodes.** This supports stable identity but requires persistent state and reliable recognition evidence; file equality alone is not an identity rule.
- **B. Require a client-supplied canonical identity or approved mapping each time.** This can make identity explicit at exchange boundaries but depends on a client workflow not established in source evidence and cannot replace Nowa’s approved ownership/Registry requirements.
- **C. Treat each file as a new submission of supplied data and resolve identities through separately governed persistent state.** This separates submission receipt from record/content version, canonical episode identity, and historical lifecycle; technical submission and correction semantics remain open.

**Decision — APPROVED (2026-11-15): Option C selected.** Keep submission receipt, record/content version, canonical contractual episode identity, and historical episode lifecycle distinct. Each received file is a new submission event, not proof that its records or episodes are new. Reuse the previously persisted canonical `subscription_id` when an existing episode is reliably recognised, and never generate a replacement ID solely because a file was submitted again. Issue a new ID only under approved PD-002 when authoritative evidence establishes a new episode. Corrections, omissions, late-arriving records, changed source identifiers, and conflicts must not silently overwrite identity or mapping history; assess changed identifiers with evidence and preserve prior and current mapping lineage when corrected. Conflicts and ambiguous evidence follow approved PD-003; unresolved records receive no automatic ID issuance or reuse. CSV ingestion alone is not idempotent without persistent identity state.

**Approval record**

| Field | Approved record |
|---|---|
| Decision | PD-004 — Repeated CSV Submission Semantics |
| Selected option | Option C — Treat each file as a new submission of supplied data and resolve identities through separately governed persistent state |
| Approval date | 2026-11-15 |
| Approved scope | Separate submission receipt, record/content version, canonical episode identity, and historical lifecycle; treat each received file as a new submission event without assuming its records are new; reuse recognised episode IDs; issue IDs only under PD-002; preserve identity and mapping history across corrections, omissions, late arrivals, changed identifiers, and conflicts; follow PD-003 for ambiguous/conflicting identity; do not claim ingestion idempotency without persistent identity state. |
| Exclusions | File hashing or duplicate-file detection; record-level duplicate criteria; technical versioning or storage schemas; database, API, Registry implementation, or transaction design; correction, omission, or late-arrival operational workflows; manual review ownership or service levels; client-specific identity criteria; CSV transport or exchange redesign; and implementation. |

**Dependencies and consequences:** Depends on PD-001–003 and DD-EP-002/004/005–008/012. It affects ingestion, Registry history, auditability, migration, and interpretation of subscription and dependent data, but does not specify implementation mechanics.

## 7. PD-005 — Historical Migration Acceptance Principles

**Decision context:** Existing contract-valid rows are not necessarily attributable to distinct contractual episodes. The approved architecture prohibits fabricating episode identity or inferring it from weak signals. Per-client coverage, keys, and lineage have not been established.

| Migration condition | Product-level consideration |
|---|---|
| Episode is authoritatively identifiable | May be accepted subject to the approved contract and intended-use eligibility assessment. |
| Historical row is reliably mapped to an episode | Preserve source lineage and mapping evidence; accept only within an approved migration process. |
| Dataset is partially attributable | PD-005 Option B permits an explicitly documented and isolated attributable subset; assess its limitations separately for the intended use. |
| Identity is unresolved | Under PD-003, isolate and exclude the record from identity-dependent processing; this does not permanently reject it. Do not fabricate or heuristically assign an episode. |
| Historical coverage is missing | Assess eligibility for the intended use separately; missing history is not proof of zero activity or that an episode did not exist. |
| Source identifiers conflict | Preserve the conflict for explicit resolution; do not overwrite an existing mapping. |
| Historical records cannot safely be split into episodes | Do not manufacture episode boundaries. Their eligibility requires a separate approved disposition. |

### Options and trade-offs

- **A. Strict acceptance:** accept only data with authoritative episode identity. This protects identity integrity but can reduce history and delay onboarding.
- **B. Partial acceptance with documented exclusions:** can preserve attributable history but may create coverage bias and requires clear downstream eligibility controls.
- **C. Review-based acceptance:** permits evidence gathering for ambiguous data but requires client participation, ownership, and process capacity.
- **D. Reject migration when minimum evidence is unavailable:** avoids unsupported use but requires an explicit product definition of minimum evidence and may exclude a client entirely.

**Decision — APPROVED (2026-11-15): Option B selected.** Historical records may be partially accepted when contractual episode identity is supported by sufficient authoritative evidence. Every accepted record must retain source lineage and traceability to its attribution evidence. Records with unresolved, ambiguous, conflicting, or insufficient identity evidence must be isolated and excluded from identity-dependent processing under PD-003. Do not fabricate episode identities or boundaries, or infer identity from dates, statuses, row order, or heuristic similarity alone. Partial acceptance and exclusions must be explicit, traceable, and auditable; missing historical coverage is not zero activity or proof an episode did not exist. Assess suitability of accepted history separately for each intended use. Partial acceptance is not complete historical coverage or full-population representation.

**Approval record**

| Field | Approved record |
|---|---|
| Decision | PD-005 — Historical Migration Acceptance Principles |
| Selected option | Option B — Partial acceptance with documented exclusions |
| Approval date | 2026-11-15 |
| Approved scope | Partially accept historical records with sufficiently authoritative episode identity; preserve source and attribution-evidence lineage; isolate unresolved records per PD-003; do not fabricate identity or episode boundaries; prohibit identity inference from weak signals alone; make partial acceptance explicit, traceable, and auditable; do not treat missing coverage as zero or as proof an episode did not exist; assess intended-use eligibility separately; do not imply full coverage or population representation. |
| Exclusions | Universal numeric coverage thresholds; minimum historical duration; universal client eligibility criteria; client-specific evidence requirements or a universal evidence checklist; manual review workflow or ownership; automatic rejection of an entire migration; fabricated episode boundaries; migration implementation or technical architecture. Client-specific eligibility remains dependent on representative, privacy-approved source data and intended use. |

**Dependencies and consequences:** Depends on approved PD-001–004 principles and client evidence for DD-EP-002, DD-EP-008–012. Product policy establishes the partial-acceptance boundary; client evidence establishes whether actual history satisfies it. It affects migration readiness and model eligibility. No acceptance threshold or migration implementation is approved.

## 8. PD-006 — Dataset Availability and Snapshot Requirement

### 8.1 Evidence and current discrepancy

Customer Data Contract v1.1, Section 2.3, labels `subscription_snapshots.csv` **“Required for temporal modelling”** and distinguishes it from optional `usage_monthly.csv` and `invoices.csv`. The wording describes a modelling requirement rather than unambiguously stating whether snapshots are required for every ingestion or validation run.

The inspected implementation is stricter at ingestion: `csv_ingestion.py` places `subscription_snapshots` in `REQUIRED_DATASETS`; `ingest_client_datasets()` raises an error if its file is absent. `usage_monthly` and `invoices` are in `OPTIONAL_DATASETS` and are loaded only when present. Therefore, current ingestion requires snapshots unconditionally. Successful current ingestion also does not itself establish schema validity, data quality acceptance, or model-training eligibility.

An absent optional dataset is not equivalent to a present file with a header and zero records. Nor does absence mean zero usage, invoices, or other activity. Availability, record count, data-quality result, and eligibility for a particular modelling task should remain distinct concepts.

### 8.2 Options and trade-offs

| Option | Ingestion implications | Data quality and modelling implications | Client, contract, and compatibility implications | Complexity |
|---|---|---|---|---|
| **A. Snapshots mandatory for every ingestion** | Preserves current loader behavior. Every client submission must contain the file, including any empty-file policy that is separately defined. | Makes no distinction between basic data validation and temporal model eligibility. Presence alone does not ensure useful history or training eligibility. Empty and absent files still need distinct handling. | Simplest alignment with code, but stricter than a reading of “required for temporal modelling”; may prevent non-temporal/basic workflows. | Lowest immediate change; retains current inflexibility. |
| **B. Snapshots optional for basic ingestion, mandatory for temporal modelling** | Loader must permit absence in an explicitly defined basic workflow while keeping required files distinct. | Data-quality reporting must represent absence without treating it as zero or a validation failure by default. Temporal training must check its own required data and eligibility criteria. A present empty file is distinct from absence. | Clarifies two use cases but changes current behavior and requires contract language, interface behavior, and consumer compatibility review. | Moderate; requirements must be coordinated across ingestion, validation, and model eligibility. |
| **C. Explicit ingestion or dataset modes with different requirements** | A declared mode determines which files are mandatory; mode selection and invalid combinations need defined behavior. | Can make validation and eligibility expectations explicit per workflow, but does not make missing snapshots satisfy temporal modelling requirements. Optional absence remains visible and is never imputed as zero. | May support multiple product workflows, but adds contract/interface concepts and migration/support burden. | Highest; requires mode specification, versioning, and coordinated implementation. |

**Decision — APPROVED (2026-11-15): Option B selected.** `subscription_snapshots.csv` is optional for basic ingestion and mandatory for workflows that claim temporal modelling. Keep its absence distinguishable from a present but empty file, and never interpret a missing dataset as zero activity or zero values. Successful ingestion does not establish data-quality acceptance or model-training eligibility; assess temporal modelling eligibility separately from basic ingestion. The current loader still requires snapshots unconditionally until any separately authorized implementation change.

**Approval record**

| Field | Approved record |
|---|---|
| Decision | PD-006 — Dataset Availability and Snapshot Requirement |
| Selected option | Option B — Snapshots optional for basic ingestion and mandatory for temporal modelling |
| Approval date | 2026-11-15 |
| Approved scope | Distinguish basic ingestion from temporal modelling eligibility; make snapshots optional for basic ingestion and mandatory for temporal modelling workflows; distinguish absent from present-empty snapshots; never infer zero values or activity from missing datasets; assess temporal modelling eligibility separately from ingestion success and data-quality acceptance. |
| Exclusions | Snapshot date conventions; historical coverage or migration eligibility decisions and evidence; DD-EP-017 evaluation strategy; numeric minimum-history or training-eligibility thresholds; and any loader, schema, contract, validator, or model implementation. |

**Dependencies and consequences:** Requires resolution of product workflow scope and DD-EP-016 compatibility review. It affects dataset classification in the contract, ingestion required-file behavior, validation/report semantics, onboarding, and temporal model eligibility. It does not decide snapshot date conventions (DD-001) or other snapshot-specific contract requirements. Historical migration acceptance, including coverage and disposition of unresolved history, is associated with DD-EP-012; source subscription ID availability and reuse remain associated with DD-EP-002. Model evaluation grouping and temporal strategy remain associated with DD-EP-017. An empty-file policy also remains open. No code or contract change is authorized here.

## 9. PD-007 — Contract Versioning and Compatibility Principles

### 9.1 Existing policy and compatibility facts

Customer Data Contract v1.1 Section 12 classifies breaking changes to required fields, keys, or dataset structure as major; backward-compatible additions or clarifications as minor; and corrections/documentation improvements as patch. It requires structural changes to be documented and changes affecting schema validation, feature engineering, or model compatibility to be reviewed.

The existing header inspector uses fixed per-dataset required and optional column lists and rejects unexpected columns. Existing Pandera schemas are strict, use `coerce=False`, and do not silently accept unregistered fields. The current schemas and loader use the contract's present keys; no implementation for canonical ID issuance, source-to-canonical mapping, Registry persistence, or cross-submission identity stability exists. A changed meaning or supply mechanism for `subscription_id` can therefore be breaking even if the column name remains unchanged. The contract’s current version notation (`1.1`) and its patch example (`1.1.0 → 1.1.1`) are inconsistent; the alignment proposal and DD-EP-016 leave that notation for explicit resolution.

### 9.2 Options and trade-offs

- **A. Require a synchronized major transition for breaking identity/key changes.** Provides one clear target but may impose coordinated client and consumer migration.
- **B. Temporarily support old and new contract versions.** Can reduce cutover pressure, but requires parallel validation, support, and deprecation policy; no such compatibility mechanism currently exists.
- **C. Prefer backward-compatible additions where genuinely safe and separately version breaking semantic changes.** Can stage adoption, but strict old consumers reject unknown columns, and optional fields cannot resolve a breaking key-semantics change by themselves.

**Decision — APPROVED (2026-11-15): Option C selected.** Prefer backward-compatible additions or clarifications when they are genuinely safe, and version breaking semantic or structural changes separately according to their actual compatibility impact. A changed meaning or supply mechanism for an existing field may be breaking even when its column name is unchanged. Include strict consumers and validators in compatibility assessments. Before assigning a version, assess the exact contract delta, affected clients and consumers, field/key semantics, dependent references, validators, migration needs, and release implications. Temporary coexistence may be considered only where a justified transition need exists and its support costs are accepted. Define appropriate deprecation and migration principles before releasing incompatible changes.

**Approval record**

| Field | Approved record |
|---|---|
| Decision | PD-007 — Contract Versioning and Compatibility Principles |
| Selected option | Option C — Prefer safe backward-compatible changes and separately version breaking semantic or structural changes according to compatibility impact |
| Approval date | 2026-11-15 |
| Approved scope | Apply the existing version classifications to the actual contract delta; include strict consumers and validators in compatibility review; assess affected clients, consumers, keys, references, migration, and release impacts; consider coexistence only when justified; define deprecation and migration principles before releasing incompatible changes. |
| Exclusions | Assigning a new contract version; resolving the `1.1` versus `1.1.0` notation inconsistency; mandating temporary coexistence; setting a migration schedule or deprecation date; changing DD-EP-016 before the exact delta and client impact are assessed; or implementing contract, header, schema, loader, migration, or compatibility changes. |

**Dependencies and consequences:** Depends on the approved product decisions and a complete field/key/interface delta, plus client consumer evidence under DD-EP-016. It affects contract, header inspection, schemas, ingestion, templates, migration, and release support. A version label alone does not provide backward compatibility.

## 10. Consolidated Product Decision Register

| Product decision | Related source decisions/status | Existing approved constraints | Recommendation / decision | Dependencies | Client evidence required | Approval status |
|---|---|---|---|---|---|---|
| PD-001 — Episode Identity Registry functional requirements | DD-EP-003: `PENDING_PRODUCT_DECISION` (partially resolved by ADR-010 and PD-001) | ADR-010 Registry architecture plus approved PD-001 functional requirements for conflict detection, ambiguity visibility, traceable corrections, auditability, and preservation of mapping lineage. | Option B approved: define product-level outcomes and defer workflow and technology. | PD-002/003; DD-EP-002/004. | Source identifiers, namespace, and submission processes needed to verify mappings. | `APPROVED` (2026-11-15) |
| PD-002 — Canonical ID issuance | DD-EP-001/002/003/004: `PENDING_CLIENT_DECISION` or `PENDING_PRODUCT_DECISION` per source register; statuses unchanged by PD-002 approval. | Nowa-owned UUID generated once for an authoritatively established new episode, persisted and reused. | Option B approved: issue only after authoritative evidence establishes a new episode; reuse reliably recognised identities; leave ambiguous or unsupported identity unresolved. | PD-001/003; DD-EP-001–004. | Client/context-specific lifecycle and source identity evidence remain necessary; no universal criteria are established. | `APPROVED` (2026-11-15) |
| PD-003 — Ambiguous identity handling | DD-EP-003 and DD-EP-008–012 retain their source statuses and open dependencies. | ADR-010 prohibits silent ambiguity resolution; PD-001/002 require visible ambiguity and evidence-based identity. | Option C approved: accept explicitly attributable records and isolate unresolved records; exclude unresolved records from identity-dependent processing; report counts/proportions and preserve attribution traceability. | PD-001/002/005; relevant dependent-data decisions. | Source linkage and evidence supporting episode attribution remain client/context dependent. | `APPROVED` (2026-11-15) |
| PD-004 — Repeated CSV submission semantics | DD-EP-002/003/004/008/012 retain their source statuses. | Reuse canonical identity for recognised episodes; no replacement ID solely due to reimport; persistent Registry required. | Option C approved: each file is a new submission event; separate submission, record/content version, canonical identity, and lifecycle; preserve mapping history. | Approved PD-001–003 principles; client correction/late-arrival practices. | Stable keys, repeat exports, changed identifiers, and correction histories. | `APPROVED` (2026-11-15) |
| PD-005 — Historical migration acceptance | DD-EP-012: `PENDING_PRODUCT_DECISION`; attribution decisions DD-EP-002/008–011 retain their statuses. | Preserve episode identity and history; do not fabricate or heuristically attribute. | Option B approved: partially accept only sufficiently attributable history with explicit exclusions, lineage, and separate intended-use eligibility assessment. | Approved PD-001–004 principles; DD-EP-008–012. | Coverage, historical crosswalks, source lineage, conflict volume, and intended client use. | `APPROVED` (2026-11-15) |
| PD-006 — Dataset availability and snapshot requirement | Contract v1.1 Section 2.3; current loader behavior differs in scope. | Current implementation requires snapshots; contract says “Required for temporal modelling”; usage and invoices are optional. | Option B approved: snapshots optional for basic ingestion and mandatory for temporal modelling; assess temporal eligibility separately. | Product workflow scope; DD-EP-016 compatibility assessment. | Client workflow needs, snapshot availability/history, and intended use. | `APPROVED` (2026-11-15) |
| PD-007 — Contract versioning and compatibility | DD-EP-016 remains `PENDING_PRODUCT_DECISION`; client impact must inform joint resolution. | Existing v1.1 major/minor/patch classifications; strict headers reject unknown columns. | Option C approved: prefer genuinely safe backward-compatible changes; classify breaking changes by actual compatibility impact after reviewing the exact delta and consumers. | Final contract delta; approved product decisions as applicable. | Consumer behavior, client field/key use, migration capacity, and compatibility impact. | `APPROVED` (2026-11-15) |

Related decisions remain at their source status. DD-EP-014 and DD-EP-015 remain `DEFERRED`, intentionally outside initial episode-level contractual churn. DD-EP-017 remains `PENDING_PRODUCT_DECISION`; this document does not prescribe a temporal or customer-grouped evaluation split strategy. Client-dependent matters remain `PENDING_CLIENT_EVIDENCE` where evidence is not yet available, and product/client questions remain `PENDING_JOINT_DECISION` where both policy and source evidence are necessary. These labels do not change the source register’s decision statuses.

## 11. Recommended Approval Sequence

The sequence is a review aid, not a prerequisite chain for every contract change:

1. Apply approved PD-001–PD-005 principles as product constraints while keeping client evidence and technical/operational details open.
2. Apply PD-006 to distinguish basic ingestion from temporal model eligibility. Resolve snapshot date conventions, coverage, and intended-use requirements separately; no numeric history or training thresholds are approved.
3. Apply PD-007 when assessing an exact proposed contract delta. Assess clients, consumers, fields/keys, references, validators, migration, and release impacts before assigning a version; DD-EP-016 remains pending until that assessment is complete.
4. Obtain client/source evidence for identifiers, namespaces, lifecycle events, dependent-dataset attribution, history, and consumers where relevant. Record resulting product/client decisions in their governing decision documents before implementation is separately authorized.

DD-EP-017 is a downstream modelling and evaluation dependency. Resolve it before choosing or implementing evaluation grouping and temporal strategy, but do not make it a prerequisite for unrelated contract changes. DD-EP-014/015 stay deferred.

## 12. Explicit Boundaries

This proposal:

- Records PD-001 through PD-007 as approved product decisions.
- Does not modify Customer Data Contract v1.1 or approve a new contract version.
- Does not resolve the `1.1` versus `1.1.0` version-notation inconsistency, mandate coexistence, or set a migration/deprecation schedule.
- Does not modify ADR-010 or the approved Episode Specification decisions.
- Does not authorize implementation of approved requirements or unapproved recommendations, a Registry, ingestion behavior, schemas, validators, migration, or reporting.
- Does not define database, cloud, API, deployment, UUID-version, or CSV transport architecture.
- Does not resolve client-specific lifecycle, identifier, namespace, attribution, or source-system semantics without evidence.
- Does not change DD-EP-014/015 from `DEFERRED`, DD-EP-017 from `PENDING_PRODUCT_DECISION`, or DD-EP-016 from its existing source status.
- Does not prescribe evaluation split strategy, customer-level prediction, or customer-level risk aggregation.
- Does not interpret absent optional datasets as zero or equate ingestion success with data-quality acceptance or model eligibility.

## References

- `docs/03_architecture/adr_episode_identity_and_identifier_management.md` — ADR-010.
- `docs/04_data/subscription_episode_lifecycle_decision_specification.md` — approved episode and identity decisions; DD-EP-001–017.
- `docs/04_data/product_decisions_and_contract_design_assessment.md` — Phase 2.4.4.2.1 inventory and ownership analysis.
- `docs/04_data/customer_data_contract_episode_alignment_proposal.md` — contract impact and versioning assessment.
- `docs/04_data/customer_data_contract.md` — Customer Data Contract v1.1, including Sections 2.3 and 12.
- `docs/04_data/data_quality_specification.md` — rule scope, pending decisions, and dataset/report semantics.
- `docs/04_data/data_quality_implementation_architecture.md` — approved DQ implementation boundaries and architecture.
- `src/nowa_customer_intelligence/data/ingestion/header_inspection.py` and `csv_ingestion.py` — current headers and required/optional ingestion behavior.
- `src/nowa_customer_intelligence/data/preprocessing/type_normalization.py` — current normalized types.
- `src/nowa_customer_intelligence/data/schemas/` — current per-dataset schemas and in-frame validation.
- `src/nowa_customer_intelligence/data/validation/referential_integrity.py` and `temporal_consistency.py` — current RI/TC behavior.

---

**Review status:** PD-001 through PD-007 are approved as recorded above. This document does not authorize implementation.
