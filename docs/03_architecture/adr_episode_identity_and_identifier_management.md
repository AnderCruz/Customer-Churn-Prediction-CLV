# ADR-010: Subscription Episode Identity and Identifier Management

**Document ID:** NCI-ADR-010
**Version:** 1.0
**Status:** Accepted
**Project:** Nowa Customer Intelligence
**Date:** 2026-11-15

## 1. Context

ADR-009 establishes subscription-level churn prediction, with `subscription_id` identifying the prediction entity and `customer_id` identifying the associated customer account. The approved Subscription Episode & Lifecycle Decision Specification clarifies that the prediction entity is an individual contractual subscription episode: each episode has its own identity, earlier episodes are preserved, and reactivation following termination creates a new episode.

Customer Data Contract v1.1 and the current implementation use `subscription_id` across subscriptions and dependent datasets, but do not define a durable identity process across repeated CSV submissions. The source system may expose a subscription identifier, an episode-specific identifier, both, or neither; source behavior is client-specific and has not been verified. A unique key in one CSV does not establish that a later CSV row represents the same episode.

The product requires a stable canonical episode identity independent of source-system identifier conventions. This ADR records the approved product-level ownership, generation approach, and registry requirement. It does not specify the registry implementation or change the data contract.

## 2. Decision Drivers

- Preserve the approved episode-level prediction entity and customer/account distinction.
- Keep each episode independently identifiable throughout its lifecycle.
- Preserve earlier episode identities when a customer reactivates.
- Recognize existing episodes across repeated CSV submissions and ingestion executions.
- Avoid treating reused or unstable source identifiers as episode identities without evidence.
- Retain source lineage when available while respecting client isolation.
- Prevent ambiguous identity matches from being silently resolved.
- Avoid embedding client or source-system information informally in canonical identifiers.

## 3. Approved Decisions

### 3.1 Canonical Episode Identifier Ownership

Nowa Analytics owns the canonical identity of each contractual subscription episode.

- `subscription_id` represents the canonical episode identifier.
- It identifies exactly one contractual episode.
- It is independent of `customer_id`, which identifies the customer/account.
- It remains stable throughout the episode lifecycle.
- It must never be reassigned to another episode.

### 3.2 UUID-Based Identifier Generation

UUID is the approved initial generation strategy for a canonical episode identifier.

- Generate the identifier once, when a new episode is authoritatively established.
- Persist the generated identifier.
- Reuse it across subsequent CSV submissions and ingestion executions.
- Do not generate a replacement identifier merely because a CSV is imported again.
- A new contractual episode following termination receives a new canonical identifier.
- Preserve previous episode identifiers and their historical records.

The UUID version and implementation details remain technical decisions for a later design phase. UUID generation by itself does not recognize episodes, guarantee idempotency, or establish that an incoming row is a new or existing episode.

### 3.3 Persistent Episode Identity Registry

The architecture must include a persistent Episode Identity Registry. Its approved responsibilities are to:

- Maintain associations between canonical episode identifiers and verified source-system identifiers.
- Preserve source-system identity information when available.
- Support recognition of existing episodes across repeated submissions.
- Support creation of identities for authoritatively established new episodes.
- Operate within strict client isolation boundaries.
- Preserve identity history and mapping lineage.

The registry must not silently resolve ambiguous identity matches. Detailed schema, storage technology, APIs, lifecycle operations, conflict-resolution workflow, retention policy, and operational ownership are not decided by this ADR.

## 4. Identity Model

The architecture preserves the distinction between:

| Identity | Meaning | Decision |
|---|---|---|
| `customer_id` | Customer/account identity | Remains independent from episode identity; one customer may have multiple episodes. |
| `subscription_id` | Canonical contractual episode identity | Nowa-owned, UUID-based, persistent, stable, and never reassigned. This is the episode prediction entity. |
| `source_subscription_id` | Source-system subscription identifier | Preserve and map when available; do not assume it uniquely identifies an episode. |
| Source-system episode identifier | Source-provided identifier for an individual episode, if available | Preserve and associate when verified; availability is not assumed. |

These identities may not all exist separately in every client system. A source-system subscription identifier or episode identifier must not automatically become the canonical `subscription_id` without evidence that it reliably identifies one contractual episode and an approved mapping decision.

This ADR does not specify whether canonical UUID uniqueness is global or client-scoped in external interfaces. Registry lookup and access must be client-scoped. Any cross-client use must preserve client isolation and avoid collisions; the interface-level uniqueness scope remains for later design.

## 5. Source-System Namespace

- Client scope remains the primary isolation boundary.
- Source-system namespace is separate provenance and mapping context.
- Namespace may be required to distinguish identifiers from multiple systems or source partitions.
- Client or source-system information must not be embedded informally into canonical UUID values.

The precise namespace fields, their requiredness, and how multiple systems belonging to one client are represented remain subject to source-system discovery. This ADR does not approve a namespace schema or make `source_subscription_id` mandatory.

## 6. Episode Identity Registry Responsibilities

The registry is a required architectural component because Nowa owns canonical IDs, must persist them, and must support cross-submission episode recognition. Stateless CSV ingestion cannot provide this stability by itself unless every submission carries an authoritative canonical ID or equivalent approved mapping; the product must still preserve identity history and client isolation.

At minimum, the registry must uphold the approved responsibilities in Section 3.3. It must allow the same verified episode to resolve to its existing canonical ID, and allow a different canonical ID for a newly established episode. It must retain history rather than overwrite an earlier episode mapping when a customer reactivates.

Where identity evidence is ambiguous, the registry must surface the ambiguity for an approved resolution process. It must not select an episode using date proximity, status changes, row order, or heuristic similarity as proof of identity.

The registry’s detailed data model, persistence mechanism, transaction/idempotency design, APIs, audit-event schema, correction and conflict workflows, retention/deletion policy, and service boundaries are explicitly outside this decision and require subsequent design.

## 7. Consequences

### 7.1 Architectural Consequences

- A persistent identity component is required; an in-memory or per-file ID generator is insufficient.
- CSV ingestion alone cannot guarantee cross-submission stability without persistent state or authoritative canonical identity/mapping input.
- UUIDs must be generated once per authoritatively established new episode and stored for reuse.
- Client isolation must extend to identity mappings, registry access, and audit history.
- Previous episode identities and mappings must remain historically preserved.
- Source identifiers provide lineage but are not canonical episode identity by default.
- Ambiguous matches require an explicit future resolution policy and cannot be silently accepted.

### 7.2 Current Implementation Consequences

The repository currently does not implement an Episode Identity Registry, UUID generation for subscription episodes, persistent identity mappings, or cross-submission idempotency. The current Pandera uniqueness checks validate keys within a DataFrame; they do not guarantee identity stability across submissions. RI-001–RI-004 validate reference existence between supplied DataFrames, not correct episode attribution. These statements describe current implementation, not the approved target architecture.

### 7.3 Data Contract and Migration Consequences

Customer Data Contract v1.1 currently defines `subscription_id` as a unique subscription identifier and uses it as the dependent-dataset reference. A future contract must clarify that this is the canonical contractual episode identifier and define the required mapping/interface behavior. Whether source identifiers or namespace fields appear in CSVs, and their nullability/constraints, depends on source discovery and subsequent contract design.

Migration from v1.1 requires separate analysis and authoritative mapping evidence. Existing identifiers must not be split, replaced, or inferred into episode identities solely from dates or status. Records whose episode identity cannot be established remain ambiguous until handled under an approved migration policy. Contract versioning and backward compatibility are not decided here.

## 8. Outstanding Decisions

| Decision | Status after this ADR | Remaining scope |
|---|---|---|
| DD-EP-002 — Source Subscription ID Availability and Reuse | PENDING_CLIENT_DECISION | Determine source ID availability, reuse, stability, historical retention, and dependent-dataset linkage through client/source discovery. |
| DD-EP-003 — Internal Episode ID Generation and Ownership | Partially resolved at product architecture level; detailed design remains open. | Ownership of canonical identity, UUID as initial strategy, and persistent registry requirement are approved here. Registry schema, persistence, APIs, conflict handling, ambiguity workflow, mapping correction/audit, retention/deletion, and operational ownership remain undecided. |
| DD-EP-004 — Source-System Namespace | PENDING_CLIENT_DECISION | Establish systems per client, identifier uniqueness boundaries, tenant/partition semantics, and namespace representation requirements. |

The original episode specification’s DD-EP-002 and DD-EP-004 remain pending. This ADR does not claim DD-EP-003 is fully resolved: it approves only the product-level ownership, UUID strategy, and registry requirement listed above.

## 9. Implementation Boundaries

This ADR records approved architecture but does not authorize implementation. The following remain outside scope until separately designed and authorized:

- UUID version selection, API, and implementation details.
- Registry schema, storage technology, service boundaries, and operational ownership.
- Source-system identifier and namespace fields, constraints, and client-specific mapping rules.
- Conflict resolution, ambiguous-record disposition, mapping correction, and audit workflow details.
- Retention and deletion operations.
- Changes to Customer Data Contract v1.1, schemas, ingestion, normalization, RI/TC validators, tests, or migration logic.
- Any source-system behavior not verified through client discovery.

## 10. References

- `docs/03_architecture/architecture_decisions.md` — ADR-003 and ADR-009.
- `docs/04_data/subscription_episode_lifecycle_decision_specification.md` — approved EP-DEC-001–005 and pending DD-EP-002–004 details.
- `docs/04_data/subscription_episode_data_contract_impact_assessment.md` — contract and implementation impact assessment.
- `docs/04_data/subscription_episode_identity_identifier_strategy_assessment.md` — identifier strategy analysis.
- `docs/04_data/customer_data_contract.md` — Customer Data Contract v1.1.
