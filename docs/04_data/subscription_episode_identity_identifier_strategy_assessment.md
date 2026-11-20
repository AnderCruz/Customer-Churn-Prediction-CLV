# Subscription Episode Identity and Identifier Strategy Assessment

> **Historical design record.** This document preserves the Phase 02 assessment and its implementation observations at the time of review. For governing requirements, see the [approved Customer Data Contract](customer_data_contract.md) and [ADR-010](../03_architecture/adr_episode_identity_and_identifier_management.md).

**Phase:** 2.4.3.2
**Assessment type:** Technical and architectural assessment
**Status:** Analysis only

## 1. Executive Summary

The approved architecture requires one unique identity for each contractual subscription episode, preserves earlier episodes, and treats a terminated episode’s reactivation as a new episode. The current contract and code have one `subscription_id` key across subscriptions, snapshots, usage, and invoices, but they do not define whether this is a source-system identifier or an internal episode identifier. They also do not provide a way to recognize an episode across repeated CSV submissions.

**RECOMMENDATION:** Use a conditional hybrid architecture. Keep `customer_id` as the customer/account identity. Use a stable canonical `subscription_id` as the episode identity in Nowa’s contract and dependent datasets. Preserve source-system subscription identifiers and source-system namespace as separate provenance/mapping attributes when available. If a source can supply a reliable episode-level identifier, map it. Otherwise, assign a canonical episode ID once, persist its mapping, and reuse it on later submissions. Do not mint a fresh ID for each ingestion.

This strategy depends on authoritative information that identifies an episode or a client-approved mapping. A source subscription ID reused after reactivation is not sufficient to distinguish episodes. Dates, status transitions, or heuristic similarity cannot prove identity. A persistent, client-isolated identity mapping/registry is architecturally necessary if Nowa owns canonical episode IDs or must reconcile changing source keys; its full design is outside this assessment.

**PENDING CLIENT DECISION:** Actual source identifier availability, reuse, stability, and coverage across subscriptions, snapshots, usage, and invoices cannot be verified without client source-system discovery. **PENDING PRODUCT DECISION:** Identifier ownership and registry operation, contract representation, and compatibility policy require approval before the contract is changed.

## 2. Approved Requirements and Existing Decisions

The following are fixed requirements from EP-DEC-001 through EP-DEC-005 in `docs/04_data/subscription_episode_lifecycle_decision_specification.md`:

- **APPROVED REQUIREMENT:** `customer_id` identifies the customer/account.
- **APPROVED REQUIREMENT:** Each contractual subscription episode is an independent prediction entity with its own unique identifier.
- **APPROVED REQUIREMENT:** A customer may have multiple episodes.
- **APPROVED REQUIREMENT:** Previous episodes remain historically preserved and are not overwritten or merged into a later episode.
- **APPROVED REQUIREMENT:** Reactivation following termination creates a new episode.

The episode specification recommends `subscription_id` as an internal episode identifier and a separate `source_subscription_id` where available. These are **RECOMMENDATIONS**, not approved contract requirements. DD-EP-002, DD-EP-003, and DD-EP-004 remain pending in that specification. This assessment does not change their status.

ADR-003 requires client-scoped data, artefacts, configuration, and predictions. ADR-009 establishes the individual subscription as the prediction entity, names `subscription_id` as its identifier and `customer_id` as its associated account, and leaves reactivation/episode details to data discovery. The episode decisions clarify that approved prediction entity as a contractual episode; they do not make `customer_id` the prediction key.

## 3. Current Implementation and Limitations

### 3.1 Contract and Schemas

**CURRENT IMPLEMENTATION:** Customer Data Contract v1.1 defines one subscription row per subscription and a unique `subscription_id`, with `customer_id` as FK. No `source_subscription_id`, source-system namespace, source episode ID, or identifier mapping is defined.

`SUBSCRIPTION_SCHEMA` enforces `subscription_id` as a unique, non-null string and validates its non-empty/no-surrounding-whitespace form. `CUSTOMER_SCHEMA` enforces unique `customer_id`. `SUBSCRIPTION_SNAPSHOT_SCHEMA` enforces uniqueness on `(subscription_id, snapshot_date)`. `USAGE_MONTHLY_SCHEMA` enforces uniqueness on `(subscription_id, usage_month)`. `INVOICE_SCHEMA` enforces unique `invoice_id` and a non-null `subscription_id`. These constraints apply to one DataFrame/client submission; they do not establish identity stability between submissions.

There is no source ID or internal episode ID reconciliation constraint. Pandera cannot determine whether two rows from separate submissions represent the same episode, a new episode, or an ambiguous record.

### 3.2 Ingestion, Normalization, and Validation

**CURRENT IMPLEMENTATION:** `header_inspection.py` uses fixed required/optional column tuples; `csv_ingestion.py` reads CSV fields as strings and requires customers, subscriptions, and snapshots, with usage and invoices optional. `type_normalization.py` converts known identifiers as strings and known dates to UTC-aware datetimes, returning a copy. Adding an identity field would require registering its header and normalization type and adding it to the appropriate schema/contract.

`validate_referential_integrity()` implements RI-001–RI-004. RI-001 checks subscription-to-customer key existence; RI-002–RI-004 check that snapshot, usage, and invoice `subscription_id` values exist in subscriptions. These are existence checks; a wrong but existing episode ID passes. `validate_temporal_consistency()` implements TC-001/002 inside the subscription table. There is no identity registry, cross-submission state, ingestion coordinator, migration service, or episode recognition operation.

**CURRENT IMPLEMENTATION — TESTS:** Schema and normalization tests use synthetic IDs and enforce per-frame constraints. CSV unit/integration tests use simple fixtures such as `subscription-1` and `customer-1`; DQ tests cover key matching and chronology. They do not test multi-submission identity stability, source ID reuse, multiple source systems, identity conflicts, or ambiguous episode attribution. No live client source records or benchmark provenance were available to inspect.

### 3.3 Client Scope

ADR-003 states client isolation as a design principle. Existing dataset mappings and schema checks are local to supplied frames; a schema’s unique constraint is therefore evaluated within that frame. The DQ report model includes a pseudonymous `client_scope`, but the RI/TC validator APIs accept a mapping of DataFrames and do not themselves implement a multi-client identity store. No globally shared identity namespace or registry is present.

## 4. Identity Concepts and Terminology

These concepts must remain distinct even when a particular client system combines or omits them:

| Concept | Meaning | Expected relationship |
|---|---|---|
| Customer/account identity | Account represented by `customer_id`. | One customer can own multiple episodes. It is not the episode ID or prediction key. |
| Contractual episode identity | One independently modelled period of contractual subscription, represented by canonical `subscription_id` in the recommended contract. | One unique, stable identity per episode; survives repeated submissions and is never reassigned to another episode. |
| Source-system subscription identity | Identifier for a subscription object/relationship in a source system. | May be absent, source-scoped, or reused across episodes; behavior is client-specific and unverified. |
| Source-system episode identity | Source identifier that specifically identifies one episode, if the source has one. | Potentially usable as a stable mapping key after verification; must not be assumed to exist. |

The source subscription and source episode concepts are not interchangeable. A source system might provide a single episode-specific key, a reusable subscription key, multiple source-system records, or no adequate identifier. The repository does not establish which pattern any client uses.

## 5. Strategy A — Source-Generated Episode Identifier

Under Strategy A, the source system supplies an identifier guaranteed to distinguish each contractual episode.

**Advantages / conditions:** A stable episode-level source key can support repeat ingestion, history preservation, and foreign-key linkage without Nowa inventing identity. If it is unique within one client and source namespace, it can be the canonical `subscription_id` or be mapped to it.

**Risks and dependencies:** The guarantee must cover episode separation, reactivation, corrections/merges, identifier stability, dependent datasets, and repeated exports. A generic source subscription ID may be reused after reactivation. If multiple systems contribute data, identical values may collide. Source updates could change identifiers or omit closed episodes. Client onboarding and exports become dependent on the source maintaining the key and retaining historical rows or mappings.

**Migration:** Historical records can only be migrated reliably when the source supplies the episode key or an authoritative mapping to one. A key unique in the latest CSV does not prove continuity with a previous submission.

**UNVERIFIED ASSUMPTION:** No repository evidence supports a claim that client source systems commonly separate subscription and episode identifiers. Whether any given client can supply an episode key must be established individually through source discovery and representative documentation/data, not presumed.

## 6. Strategy B — Internally Generated Episode Identifier

Under Strategy B, Nowa owns the canonical episode key and generates one when an episode is first established.

**Generation options:** A random UUID such as UUIDv4 is technically suitable as an opaque identifier with negligible accidental collision risk. A deterministic UUID (for example, namespace-based) is only stable if its namespace and input are stable and uniquely identify an episode. A reusable source subscription ID alone is not a valid deterministic input when it may cover several episodes. UUID format does not solve identity recognition or idempotency.

**Critical stability requirement:** Generating a new UUID every time a CSV is ingested would create a new apparent episode on each submission. That is invalid. The generation event must occur once for a newly identified episode, and the generated ID must be durably persisted and reused.

To achieve idempotency, the system needs a stable episode recognition key or an authoritative mapping on subsequent submissions. It must also know when a row represents a new/reactivated episode rather than an update to an existing one. Those facts cannot be inferred from date proximity, a status change, or a reused source ID alone. Without sufficient evidence, the record must be rejected, held for resolution, or otherwise handled according to an approved policy rather than silently assigned.

**Historical preservation:** Persist the old canonical ID and episode record; create a different one only when a new episode is authoritatively identified. Do not overwrite the old episode to represent reactivation.

**Operational implications:** Nowa takes on durable identity storage, mapping lifecycle, correction/conflict handling, backup, access control, audit, and client-specific isolation. The current repository has none of these capabilities. Migration from v1.1 needs an authoritative existing-episode map or explicit unresolved-data handling.

## 7. Strategy C — Hybrid Identity

Under Strategy C, the client/source supplies the identifiers it has, while Nowa maintains a canonical stable episode ID and a durable mapping to source identity.

The conceptual separation is:

1. `customer_id`: the customer/account.
2. Canonical `subscription_id`: the contractual episode and prediction entity.
3. `source_subscription_id`: source-system subscription object/relationship, where supplied.
4. A source episode ID: a source-provided episode-level key, if available; otherwise, a mapping or verified source evidence is needed to distinguish episodes.

These four identities do not necessarily all exist separately in a client system. The model must represent what the source can substantiate and must not manufacture false precision.

Hybrid identity supports stable canonical references while retaining source lineage. It can accommodate multiple source systems if the mapping includes a verified source namespace. Source ID reuse is manageable only when an episode-level discriminator, authoritative crosswalk, or explicit lifecycle event mapping distinguishes the new episode. A mapping table/registry supports repeated ingestion, idempotency, preserved identity after source corrections, and audit.

This approach has greater operational complexity than directly using a source episode key: it requires persistent state, secure client isolation, reconciliation workflows, and ownership of mapping conflicts. It also cannot recover missing historical identity without evidence. It is the strongest conditional product architecture because it separates the stable product key from client-specific identifiers while allowing a verified source episode key to simplify mappings.

## 8. Identifier Scope and Namespace

### 8.1 Uniqueness Scope

The episode specification recommends uniqueness within applicable client data scope. That is consistent with ADR-003 client isolation. A client-scoped identifier can be sufficient inside a physically/logically isolated client dataset. Any central cross-client registry, shared feature store, export, or API needs a non-colliding composite scope or a globally unique opaque ID.

| Scope | Benefits | Limits |
|---|---|---|
| Client-scoped | Matches client isolation and permits simple canonical IDs within each client. | Same value can occur for different clients; every cross-client join/export must retain client scope. |
| Source-system-scoped | Disambiguates values from separate systems within one client. | Source IDs can still be reused across episodes; source namespace does not itself identify an episode. |
| Composite source key | `(client scope, source system, source identifier[, source episode key])` can support mapping uniqueness when all components are stable and meaningful. | Components and their reuse semantics are client-dependent; the tuple may not exist in every client. |
| Globally unique opaque canonical ID | Reduces accidental collision and is convenient for shared infrastructure/API references. | Does not prove business identity, solve repeat-ingestion matching, or justify exposing a database key. Client authorization/isolation is still required. |

### 8.2 Recommendation

**RECOMMENDATION:** Keep `client_scope` as an access-control/isolation boundary; treat any source-system namespace as separate provenance metadata; keep the canonical episode identifier opaque and stable. Do not encode customer or other sensitive information into IDs. Use `(client_scope, canonical_episode_id)` as an explicit scope wherever data can cross a client boundary, unless the product chooses and governs a globally unique external episode ID. Do not use source-system namespace as a replacement for client scope.

Technical uniqueness is a collision property. Business identity is the assertion that two records refer to the same contractual episode. A UUID can provide the former; only evidence and persistent mapping can support the latter. Do not expose an internal database primary key in client-facing files or APIs unless an explicit product contract requires it. The canonical `subscription_id` in CSVs is a contract-level identifier and need not be the database’s internal row key.

## 9. Idempotency and Episode Recognition

### 9.1 Recognition Cases

| Incoming row case | Safe conclusion from current contract alone | Evidence required for a safe decision |
|---|---|---|
| Existing episode in a later submission | None; same source ID or similar row does not prove identity. | Stable canonical episode ID or persistent authoritative mapping key. |
| New episode | None from a new row alone. | Source episode ID, explicit episode creation/event key, or approved source-to-episode mapping. |
| Reactivated customer after episode termination | Approved direction says a new episode, but the row must still be linked to that new episode identity. | Evidence that the prior contractual episode terminated and the reactivation is a new episode under approved lifecycle semantics. |
| Reused source subscription ID | Cannot distinguish old and new episodes. | Separate source episode key, authoritative crosswalk, or other verified episode-level key. |
| Ambiguous record | Must not be auto-matched. | Resolution through a documented, auditable mapping/decision process. |

Date proximity, status changes, similarity of fields, file ordering, or per-file uniqueness are not proof of episode identity.

### 9.2 Is a Persistent Mapping Component Necessary?

**RECOMMENDATION:** Yes, if the product owns canonical IDs or must preserve mappings across repeated submissions and source key changes. If every client supplies stable episode IDs that are directly adopted as canonical IDs, a separate mapping registry may be reduced or unnecessary for that client, but the source-to-canonical lineage still needs to be auditable. The product should not assume this favorable condition before discovery.

At an architectural level, a mapping/identity registry would be responsible for:

- Persistently associating a canonical episode ID with verified source identity components.
- Scoping mappings by client and, where required, source-system namespace.
- Reusing the existing canonical ID across submissions and recording a new ID only for an established new episode.
- Detecting key reuse, conflicting mappings, source corrections, and ambiguous inputs for review rather than silently resolving them.
- Retaining lineage and audit events for creation, source-key changes, approved merges/splits, and resolution decisions.
- Preventing mappings or identifiers from crossing client isolation boundaries.

Potential attributes for future design include client scope, source-system namespace, source subscription ID, source episode ID when present, canonical episode ID, mapping state/confidence as a controlled operational state, valid/source record references, created/updated timestamps, ingestion/run provenance, and audit history. This is an assessment of responsibilities, not a registry schema or implementation design. No confidence score should be interpreted as identity proof without an approved policy.

## 10. Strategy Comparison Matrix

| Criterion | A — Source-generated episode ID | B — Internally generated episode ID | C — Hybrid identity |
|---|---|---|---|
| Identity correctness | Strong when the source key is explicitly episode-level and stable; unverified for current clients. | Strong only when episode recognition is authoritative before ID creation. Random ID generation alone does not establish correctness. | Strongest conditional option: canonical ID plus verified source mapping; still depends on source evidence. |
| Uniqueness | Depends on client guarantees and scope/namespace. | UUID collision risk is negligible, but uniqueness does not prove distinct episodes were recognized correctly. | Canonical ID can be unique; mapping-key uniqueness depends on verified source components. |
| Stability | Good if the source guarantees no reassignment or reuse; source changes can break it. | Good only if generated once and persisted. New UUID per ingestion is invalid. | Canonical ID remains stable while source IDs can change through audited mapping updates. |
| Idempotent ingestion | Straightforward if stable episode ID is present on every export. | Requires a persistent lookup key/registry to retrieve rather than regenerate IDs. | Registry/crosswalk directly supports repeat matching and stable canonical identity. |
| Source ID reuse | Fails to distinguish episodes if the supplied ID is subscription-level and reused. | Must be resolved by a separate source discriminator/mapping; reusable ID alone is insufficient. | Can represent reuse when source episode key or authoritative mapping distinguishes episodes. |
| Multiple source systems | Requires namespacing and compatible source episode semantics. | Canonical ID can span sources, but recognizing one episode across sources still requires mapping evidence. | Designed to retain multiple namespaced source references, at additional reconciliation cost. |
| Client isolation | Requires client-scoped uniqueness or external client namespace. | Registry and ID creation must be isolated/scoped per client. | Registry can enforce client and source namespaces; governance/access control is required. |
| Historical migration | Feasible where source episode keys exist historically. | Requires a trustworthy migration crosswalk and persistent ID store. | Can preserve source lineage and canonical IDs, but cannot resolve records lacking evidence. |
| Auditability | Depends on source lineage and change history available from client. | Requires internal registry audit. | Strong lineage potential if mappings and changes are retained. |
| Operational complexity | Lower inside Nowa; higher onboarding/source dependency. | High for identity store, reconciliation, and lifecycle operations. | Highest overall due to both source discovery and registry/reconciliation. |
| Client onboarding | Client must prove and supply the required episode key consistently in dependent datasets. | Client must provide enough data to identify episodes even if it does not provide an ID. | Client supplies available source keys and mapping evidence; onboarding validates behavior and unresolved cases. |
| Future scalability | Limited by source-specific conventions and integrations. | Scales with robust identity service and governance. | Flexible across sources and client formats, with registry and operational investment. |

No numerical scores are assigned because the repository provides no client evidence or product cost data to support them.

## 11. DD-EP-002 — Source Subscription ID Availability and Reuse

**PENDING CLIENT DECISION:** Determine for each relevant source system whether identifiers exist at subscription-object and episode levels, and whether snapshots, usage, and invoices carry the same linkage fields.

Evidence to request during client/source discovery:

- Source data dictionary, key definitions, and vendor/system documentation.
- Representative historical extracts spanning initial subscription, termination, reactivation, renewal, and corrections, with approved privacy handling.
- Whether IDs are reused, reassigned, regenerated, or changed on merges/migrations.
- Whether the key persists in closed/historical rows and dependent datasets.
- Whether IDs are unique per client, tenant, source database, or only within another partition.
- Whether the source exposes an explicit episode/contract-period ID or stable event/crosswalk table.
- Whether late-arriving updates or backfills change prior identifiers or lifecycle dates.

**Can be decided at product architecture level:** Keep source identifiers separate from canonical episode identity; preserve provenance when available; require verified mapping; do not infer identity from dates/status; define safe handling for ambiguity; maintain client isolation.

**Client-specific:** Actual fields, ID reuse, historical retention, key stability, namespace boundaries, and which dependent datasets can supply episode linkage. No claims about common source-system behavior are verifiable from this repository.

## 12. DD-EP-003 — Internal Episode ID Generation and Ownership

**RECOMMENDATION:** The product should own the semantics and governance of the canonical episode identifier; an approved product/service component should assign it once when an episode is authoritatively identified. A random UUID (such as UUIDv4 in the current Python version) is suitable as an opaque value, subject to operational review. UUID version choice is not a substitute for persistent identity recognition.

Stability/idempotency requires that the system consult a durable mapping on each submission. It must find the prior canonical ID by a verified stable source episode key or approved mapping, and only create a new canonical ID for a verified new episode. If the available source identifier is reused and no episode discriminator/crosswalk exists, the system cannot safely decide whether an incoming row updates an old episode or represents a new episode. It must leave the case unresolved according to an approved ingestion policy.

A persistent registry is necessary for the internally generated path and generally for the hybrid path. A client-supplied stable episode ID may simplify this, but the product still needs client scoping, provenance, and conflict handling. The repository has no registry or persistence layer, so implementation requires a separately designed component and operational owner.

Before changing the contract, approve:

1. Whether canonical `subscription_id` is source-supplied, Nowa-issued, or conditional by onboarding.
2. ID stability, scope, non-reuse, and dependent-dataset FK rules.
3. Persistent mapping ownership and storage lifecycle.
4. Conflict/ambiguous record behavior and migration acceptance.
5. Whether this changes required CSV fields or allows an approved mapping artifact/process.

## 13. DD-EP-004 — Source-System Namespace

**RECOMMENDATION:** Preserve namespace as separate metadata/mapping context rather than embedding client or source names into the canonical episode ID. Use the namespace as part of a source mapping key where the source can collide across systems. Keep client scope independently enforced. This avoids exposing client/source information in opaque IDs and allows a source system to change without changing canonical episode identity.

Namespace is required when a client uses multiple systems whose identifiers can overlap, when one source instance/tenant has local rather than global uniqueness, or when lineage/audit must identify the originating system. It may be unnecessary as a CSV field for a client with one known source and isolated storage, but the system must still know that source context during mapping. The decision cannot be made globally from repository evidence.

**PENDING CLIENT DECISION:** Determine the number and boundaries of source systems, tenant/account partitions, identifier collision behavior, and whether source-system metadata is present in each dataset. Multiple systems belonging to one client require separate source namespaces, while remaining inside the same client isolation boundary. Do not make the namespace part of an ID string by informal concatenation; if a composite key is needed, define its components and encoding explicitly in the data model.

## 14. Recommended Architecture

The recommended architecture is conditionally hybrid:

1. `customer_id` remains the account/customer identity and customer FK.
2. Canonical `subscription_id` identifies exactly one contractual episode, is stable across submissions, is never reused, and is the prediction entity key.
3. Source subscription identifiers are retained separately when supplied; their meaning and uniqueness are source-specific.
4. Source episode identifiers are retained/mapped when available, but are not assumed to exist.
5. Source-system namespace and client scope remain separate metadata/security dimensions. Mapping keys include verified namespace components as needed.
6. A persistent identity registry/crosswalk maps verified source identity to canonical episode identity, supports repeat ingestion, detects conflicts, preserves lineage, and enforces client isolation.
7. An existing episode reuses its canonical ID. A reactivation after termination creates a new episode ID only when the source/event evidence identifies it as the new episode. The old episode and mapping remain preserved.
8. Ambiguous rows are not heuristically assigned. They follow a future approved reject/quarantine/review policy.

This is an architectural recommendation, not approval of a registry design, field list, or migration rule. If client discovery demonstrates reliable source-generated episode keys in all required datasets, Strategy A may be used for that client with appropriate namespace and stability validation. If not, the hybrid path depends on persistent mapping. Strategy B without reliable recognition inputs is not viable for repeated CSV ingestion.

## 15. Future Data Contract Implications

This assessment does not define a final schema. The likely contract concerns are:

| Dataset/concern | Possible contract implication | Decision dependency |
|---|---|---|
| `customers` | Keep `customer_id` as customer PK; multiple episode rows may reference it. No identity field change required solely for episodes. | Approved EP-DEC-001/004. |
| `subscriptions` | Required canonical episode `subscription_id` (unique at defined client scope), required `customer_id` FK, one row per episode. A source subscription ID and optional source episode ID may be added if supported; nullability/uniqueness not yet set. | DD-EP-002/003/004; lifecycle dates also DD-EP-001/005–007. |
| `subscription_snapshots` | `subscription_id` FK must refer to canonical episode key; composite `(subscription_id, snapshot_date)` remains a candidate key. May require source linkage or an approved crosswalk before normalization to canonical key. | DD-EP-008 and snapshot source capability. |
| `usage_monthly` | `subscription_id` should refer to an episode if episode attribution is available; composite `(subscription_id, usage_month)` remains candidate key only under the existing one-row-per-episode-per-month grain. | DD-EP-009/010 and usage period semantics. |
| `invoices` | Keep `invoice_id` PK; define whether `subscription_id` FK is canonical episode ID; source invoice/episode mapping may be needed. | DD-EP-011. |
| Namespace/client scope | Prefer separate controlled source metadata/mapping context over embedding identifiers. Client scope remains the isolation boundary; do not include sensitive client data in opaque ID values. | DD-EP-004 and deployment/data governance. |
| Repeated submissions | State how canonical episode IDs are preserved and how mapping artifacts/identity service participate in CSV onboarding. | DD-EP-003/012. |

Potential keys must be explicit about their scope. The current per-DataFrame `unique=True` check establishes within-file uniqueness only. A contract must specify whether canonical IDs are unique per client or globally and how cross-client interfaces preserve scope. Source ID uniqueness must not be asserted until its source behavior is verified.

Under Contract v1.1 Section 12, breaking changes to required fields, keys, or structure are major-version changes; backward-compatible additions/clarifications may be minor. Reinterpreting `subscription_id` can be breaking even without changing its column name. DD-EP-016 requires a product decision after the actual delta and compatibility plan are known. No version is assigned here.

## 16. Outstanding Questions and Evidence Requirements

| Question | Evidence/approval needed | Classification |
|---|---|---|
| Do clients provide a stable episode-level key? | Per-client source schema and historical examples across reactivation/updates. | PENDING CLIENT DECISION (DD-EP-002) |
| Are source IDs reused or changed? | Source documentation and longitudinal extracts including closed episodes. | PENDING CLIENT DECISION (DD-EP-002) |
| Who owns canonical ID issuance and persistence? | Product/platform ownership and operational design decision. | PENDING PRODUCT DECISION (DD-EP-003) |
| Is mapping registry approved and who operates it? | Product decision on persistence, access, audit, conflict handling, retention, and deletion. | PENDING PRODUCT DECISION (DD-EP-003) |
| What namespace components are required? | Source inventory and collision/tenant semantics per client. | PENDING CLIENT DECISION (DD-EP-004) |
| Which datasets can identify episodes? | Field-level source lineage for snapshots, usage, invoices, and subscriptions. | PENDING CLIENT DECISION (DD-EP-002/004 and DD-EP-008/009/011) |
| What is acceptable for legacy records lacking identity? | Explicit reject/quarantine/manual-resolution/exclusion criteria. | PENDING PRODUCT DECISION (DD-EP-012) |
| What contract version and transition are required? | Enumerated breaking changes and compatibility review. | PENDING PRODUCT DECISION (DD-EP-016) |

No source-system examples, client mappings, evidence of source key reuse, or historic identity crosswalks could be verified from repository content. Any claim that these are available or consistent is an **UNVERIFIED ASSUMPTION** until discovery confirms it.

## 17. Recommended Next Steps

1. Preserve the approved episode requirements and keep DD-EP-002/003/004 pending until evidence/ownership decisions are recorded.
2. Conduct client/source discovery for subscription and episode IDs, reuse, namespaces, historical retention, and identifiers carried by every dependent dataset.
3. Make the product-level decision on canonical ID ownership, persistent mapping, ambiguity handling, and client-scoped storage.
4. Review the recommended hybrid model and explicitly approve, reject, or defer each recommendation; do not treat this assessment as approval.
5. Resolve episode boundary and dependent-record attribution decisions that determine field semantics.
6. Prepare a proposed contract delta and version/backward-compatibility analysis only after the identifier requirements are sufficiently supported.
7. Design registry/ingestion changes and tests in a separately authorized implementation phase. Include repeat-submission idempotency, source-ID reuse, multiple namespaces, multiple episodes per customer, conflicts, and unresolved attribution.

## 18. Scope Exclusions

This report does not:

- Change or approve DD-EP-002, DD-EP-003, DD-EP-004, any other pending decision, ADR-009, or the Data Contract.
- Define a final contract schema or contract version.
- Assert source-system behavior without client evidence.
- Implement an ID generator, identity registry, mapping store, migration, or ingestion changes.
- Assign historical records using dates, statuses, or heuristic matching.
- Modify code, schemas, tests, fixtures, dependencies, or existing documentation.
- Use live client data or commit/push any change.

## 19. Verification and Limitations

This report was prepared from repository documents, source, and synthetic tests. No live client data was used. The only new file for this task is this assessment report; no existing file was modified. `git diff --check` was run where applicable, and the untracked report was checked directly for whitespace errors. No tests or implementation changes were performed. No commit or push was performed.
