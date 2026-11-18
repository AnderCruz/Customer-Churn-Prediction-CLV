# Subscription Episode & Lifecycle Decision Specification

**Document ID:** NCI-EPISODE-SPEC-001\
**Version:** 0.4
**Status:** Draft for Review\
**Project:** Nowa Customer Intelligence

**Related Documents:**
- Customer Data Contract v1.1
- ADR-009 — Subscription-Level Prediction Entity
- `docs/03_architecture/adr_episode_identity_and_identifier_management.md` — ADR-010
- Data Quality Specification v0.2
- Data Quality Implementation Architecture v0.2
- Subscription Episodes and Reactivation — Technical Assessment

---

## 1. Purpose

This document establishes the architectural and business decision framework for representing subscription lifecycle episodes in Nowa Customer Intelligence.

Its purpose is to clarify how customers, source-system subscriptions, contractual subscription episodes, and related historical records should be represented before modifying the existing Customer Data Contract v1.1.

The document distinguishes between:

1. **Approved decisions:** Architectural directions explicitly accepted for the project.
2. **Technical recommendations:** Proposed design choices requiring review and approval.
3. **Pending business or client decisions:** Matters that cannot be safely finalized without understanding client business processes or source-system capabilities.
4. **Deferred decisions:** Matters intentionally postponed until their dependencies or product requirements are established.

This document does not authorize implementation or modify the existing data contract.

## 2. Scope

This specification covers:

- Customer and subscription identity.
- Contractual subscription episode definition.
- Subscription lifecycle events.
- Reactivation, renewal, suspension, and cancellation.
- Source-system identifier traceability.
- Historical data attribution.
- Dataset relationships.
- Churn prediction implications.
- Data migration and backward compatibility.
- Decisions required before implementation.

### 2.1 Out of Scope

The following subjects are not defined by this document:

- Final churn prediction model design.
- Model selection and hyperparameter optimization.
- Customer Lifetime Value calculation.
- Revenue forecasting and financial reconciliation.
- Revenue recovery or campaign uplift estimation.
- Production API and deployment architecture.
- Final client-specific source-system mappings.

These subjects may depend on decisions established here but require separate specifications.

## 3. Decision Classification

Every decision in this document belongs to one of the following categories.

| Classification | Meaning |
|---|---|
| APPROVED | Explicitly accepted architectural direction. |
| RECOMMENDED | Proposed technical direction requiring formal approval. |
| PENDING_CLIENT_DECISION | Requires information or agreement from a future client. |
| PENDING_PRODUCT_DECISION | Requires a product or business policy decision. |
| DEFERRED | Intentionally postponed because it is outside the current scope or depends on other decisions. |

A recommendation must not be treated as an approved contract requirement until formally accepted.

---

## 4. Approved Architectural Decisions

The following decisions represent the currently approved architectural baseline.

### 4.1 Customer Identity

**Decision ID:** EP-DEC-001\
**Status:** APPROVED

`customer_id` represents the customer or account identity.

A customer may have multiple contractual subscription episodes over time.

The customer remains the grouping and reporting entity, but is not the primary prediction entity for the initial contractual churn use case.

### 4.2 Subscription Episode as the Prediction Entity

**Decision ID:** EP-DEC-002\
**Status:** APPROVED

Each contractual subscription episode is represented as an independent entity with its own unique identifier.

A reactivation following the termination of a contractual episode creates a new episode.

Previous episodes must be preserved historically and must not be overwritten or merged with subsequent episodes.

This decision establishes the interpretation of the existing subscription-level prediction architecture: the prediction entity is an individual contractual subscription episode.

### 4.3 Historical Episode Preservation

**Decision ID:** EP-DEC-003\
**Status:** APPROVED

A previous episode remains historically identifiable after cancellation, termination, or subsequent reactivation.

A later episode must not modify the historical identity or lifecycle record of an earlier episode.

### 4.4 Customer and Episode Relationship

**Decision ID:** EP-DEC-004\
**Status:** APPROVED

The logical relationship is:

- One customer can have multiple subscription episodes.
- Each subscription episode belongs to one customer.
- Each episode has an independent lifecycle.

The customer identity and episode identity must remain distinct.

### 4.5 Reactivation Creates a New Episode

**Decision ID:** EP-DEC-005\
**Status:** APPROVED

A reactivation following the termination of a contractual episode creates a new episode with an independent identity.

The previous episode remains historically preserved.

This decision does not define the detailed business criteria for determining when a cancellation or termination is effective. Those event semantics remain subject to further definition.

### 4.6 Canonical Episode Identity and Identifier Management

The following product-level architecture decisions are approved by ADR-010. They do not authorize implementation.

#### EP-ID-DEC-001 — Canonical Episode Identifier Ownership

**Status:** APPROVED

Nowa Analytics owns the canonical identity of each contractual subscription episode.

- `subscription_id` is the canonical episode identifier and identifies exactly one contractual episode.
- It is independent of `customer_id`.
- It remains stable throughout the episode lifecycle and must never be reassigned to another episode.

#### EP-ID-DEC-002 — UUID-Based Identifier Generation

**Status:** APPROVED

UUID is the approved initial generation strategy for canonical episode identifiers.

- Generate the identifier once, when a new episode is authoritatively established, and persist it.
- Reuse it across subsequent CSV submissions and ingestion executions; never generate a replacement merely because a CSV is reimported.
- A new episode following termination receives a new canonical identifier.
- Previous episode identifiers and their historical records remain preserved.

The UUID version and implementation details remain open technical decisions. UUID generation alone does not solve episode recognition or idempotency.

#### EP-ID-DEC-003 — Persistent Episode Identity Registry

**Status:** APPROVED

The architecture must include a persistent Episode Identity Registry. Its responsibilities are to:

- Maintain associations between canonical episode identifiers and verified source-system identifiers.
- Preserve source identity information when available.
- Recognize existing episodes across repeated submissions and support identity creation for authoritatively established new episodes.
- Enforce client isolation and preserve identity history and mapping lineage.
- Prevent silent resolution of ambiguous identity matches.

The registry schema, storage technology, APIs, transaction/idempotency design, operational ownership, conflict-resolution workflow, mapping correction and audit-event design, retention, deletion, and service boundaries remain open.

### 4.7 Identity Concepts and Source-System Namespace

The identity concepts remain distinct:

1. `customer_id`: customer/account identity.
2. `subscription_id`: Nowa-owned canonical contractual episode identity.
3. `source_subscription_id`: source-system subscription identifier, when available.
4. Source-system episode identifier: source-provided identifier for an individual episode, when available.

Not every client source system is assumed to provide all four identifiers. Source identifiers must not automatically be treated as canonical episode identifiers, and `source_subscription_id` must not be assumed to uniquely identify an episode.

Client scope remains the primary isolation boundary. Source-system namespace is separate provenance and mapping context and may be required to distinguish identifiers from multiple systems or source partitions. Client or source-system information must not be embedded informally into canonical UUID values. Exact namespace fields and requiredness remain subject to client/source discovery.

---

## 5. Recommended Identity Architecture

### 5.1 Identity Model

**Decision ID:** EP-REC-001\
**Status:** RECOMMENDED

ADR-010 approves the distinction between customer identity, canonical episode identity, source subscription identity, and a source episode identifier when available. This recommendation concerns their proposed data representation and traceability; it does not approve a contract schema or make source fields mandatory.

The proposed identity model distinguishes four concepts.

| Identifier | Meaning | Proposed responsibility |
|---|---|---|
| `customer_id` | Customer or account identifier | Identifies the customer relationship. |
| `source_subscription_id` | Identifier assigned by the client's source system | Preserves source-system traceability. |
| `subscription_id` | Internal contractual episode identifier | Identifies one episode and its prediction entity. |
| Source-system episode identifier | Source-provided identifier for an individual episode, if available | Supports source-to-canonical mapping when verified. |

The proposed model is:

```text
Customer
  |
  | 1:N
  |
Subscription Episodes
  |
  +-- Episode 001
  |
  +-- Episode 002
  |
  +-- Episode 003
```

A source-system subscription identifier may be reused across multiple episodes, depending on the client's system.

Therefore, it must not automatically be assumed to uniquely identify a contractual episode.

### 5.2 Internal Episode Identifier

**Decision ID:** EP-REC-002\
**Status:** RECOMMENDED

ADR-010 approves Nowa ownership of the canonical `subscription_id`, its identity as exactly one contractual episode, stability/non-reassignment, and UUID as the initial generation strategy. This recommendation covers contract/interface details not settled by those decisions.

The identifier should:

- Be unique for each canonical episode within the applicable registry/client context. Global versus client-scoped uniqueness in external interfaces remains unresolved and requires subsequent design.
- Remain stable throughout the episode lifecycle.
- Remain stable across repeated CSV submissions and ingestion executions.
- Be referenced by dependent datasets when episode attribution is established.
- Never be reused for another episode.
- Preserve historical traceability.

The UUID version and implementation details remain unresolved. The registry must recognize existing episodes across submissions and persist canonical IDs; UUID generation alone does not provide episode recognition or idempotency.

Possible approaches include:

1. The client provides a reliable source episode-level identifier to associate with the canonical ID.
2. The client provides an authoritative source-to-episode mapping.
3. The registry generates and persists a canonical UUID after receiving authoritative information that establishes a new episode.

The source evidence and mapping input remain client-specific. These approaches do not change the approved UUID strategy or assume that client systems provide episode-level identifiers.

In particular, an ingestion process must not generate a different identifier for the same episode on each execution.

### 5.3 Source-System Identifier

**Decision ID:** EP-REC-003\
**Status:** RECOMMENDED

ADR-010 requires source-system identity information to be preserved when available. Retaining a separate `source_subscription_id` as a contract field is recommended where appropriate, but its presence in every CSV and its mandatory status are not approved.

Its purpose is to preserve traceability to the client's original system.

Before making this field mandatory, the project must establish:

- Whether the source system exposes such an identifier.
- Whether the identifier is reused after cancellation or reactivation.
- Whether its meaning is consistent across datasets.
- Whether historical records retain the identifier.
- Whether it is unique, nullable, or subject to source-specific constraints.

The field's mandatory status and exact semantics remain pending client confirmation.

### 5.4 Source-System Namespace

**Decision ID:** EP-REC-004\
**Status:** RECOMMENDED

ADR-010 approves source-system namespace as separate provenance and mapping context. This recommendation concerns whether and how that context is represented in a future contract or mapping interface.

Different source systems may use identical identifier values.

A source identifier alone may therefore be insufficient to establish global traceability when data originates from multiple systems.

Potential metadata may include:

- Source system identifier.
- Source subscription identifier.
- Client scope.
- Internal episode identifier.

No additional field or composite key is approved at this stage.

The final requirement depends on client source-system architecture and the agreed data integration model.

---

## 6. Subscription Episode Definition

### 6.1 Proposed Definition

**Decision ID:** EP-REC-005\
**Status:** RECOMMENDED

A contractual subscription episode is a distinct period of contractual service associated with a customer.

Each episode has:

- One customer identity.
- One unique episode identifier.
- An independently defined start.
- An independently defined lifecycle.
- An independently determined contractual end, where applicable.

A subsequent contractual relationship following termination or cancellation is represented as a new episode.

### 6.2 Episode Boundaries

The following lifecycle events require explicit business definitions.

| Event | Proposed interpretation | Status |
|---|---|---|
| Initial activation | Starts an episode | PENDING_CLIENT_DECISION |
| Cancellation | May initiate or define episode termination | PENDING_CLIENT_DECISION |
| Contractual termination | Ends the episode according to contractual semantics | PENDING_CLIENT_DECISION |
| Reactivation after termination | Creates a new episode | APPROVED |
| Renewal | May continue the existing episode or create a new one | PENDING_CLIENT_DECISION |
| Temporary suspension | May preserve the existing episode | PENDING_CLIENT_DECISION |
| Service pause | Requires source-specific lifecycle interpretation | PENDING_CLIENT_DECISION |
| Contract extension | Requires business-specific interpretation | PENDING_CLIENT_DECISION |

The approved reactivation direction does not automatically determine how renewals, pauses, suspensions, or extensions must be represented.

### 6.3 Episode Date Semantics

The existing fields are:

- `start_date`
- `end_date`
- `cancellation_date`

Their exact meaning must be reviewed before modifying the data contract.

In particular, the project must distinguish:

- Cancellation request date.
- Cancellation effective date.
- Last day of contractual service.
- Actual service termination date.
- Contractual expiration date.

These dates may differ.

The project must not assume that `cancellation_date` and `end_date` represent the same business event.

**Status:** PENDING_CLIENT_DECISION.

---

## 7. Dataset Attribution Requirements

### 7.1 Customers

**Decision ID:** EP-REC-006\
**Status:** RECOMMENDED

The customer dataset should retain one record per customer identity.

No episode-specific structural change is currently implied.

The relationship between customers and episodes remains one-to-many through `customer_id`.

### 7.2 Subscriptions

**Decision ID:** EP-REC-007\
**Status:** RECOMMENDED

The subscriptions dataset should contain one record per contractual episode.

The proposed logical fields are:

| Field | Purpose |
|---|---|
| `subscription_id` | Internal episode identifier |
| `customer_id` | Customer identity |
| `source_subscription_id` | Original source-system identifier, where available |
| `start_date` | Episode start date |
| `end_date` | Episode end date |
| `cancellation_date` | Cancellation event date |

This is a logical proposal, not an approved schema.

Additional episode metadata may be necessary depending on source-system capabilities and lifecycle requirements.

### 7.3 Subscription Snapshots

**Decision ID:** EP-REC-008\
**Status:** RECOMMENDED

Each snapshot should reference the episode it describes.

The logical key remains:

```text
subscription_id + snapshot_date
```

Historical snapshots must not be assigned to episodes based solely on date proximity, current status, or inferred lifecycle boundaries.

If the source system cannot identify the episode associated with a historical snapshot, the record requires an approved mapping or must be treated as unresolved.

### 7.4 Monthly Usage

**Decision ID:** EP-REC-009\
**Status:** RECOMMENDED

Usage records should reference the episode to which the usage belongs.

The logical key remains:

```text
subscription_id + usage_month
```

However, the following questions remain unresolved:

- What defines the boundaries of `usage_month`?
- Does usage represent activity during a calendar month or another billing period?
- How should usage spanning two episodes be handled?
- Can the source system identify the episode responsible for the usage?
- Are usage records available at episode level or only at customer/source-subscription level?

No automatic allocation across episodes should be implemented without an approved policy.

### 7.5 Invoices

**Decision ID:** EP-REC-010\
**Status:** RECOMMENDED

Invoices should reference a contractual episode when the source data supports reliable episode-level attribution.

The following scenarios require consideration:

- One invoice belongs to one episode.
- One invoice covers multiple services.
- One invoice covers multiple episodes.
- One source-system subscription identifier is reused across episodes.
- Historical invoices cannot be reliably associated with a specific episode.

Invoice attribution must not be inferred solely from invoice dates.

The invoice-to-episode relationship and any allocation policy remain pending.

---

## 8. Churn Definition and Modelling Implications

### 8.1 Episode-Level Churn

**Decision ID:** EP-REC-011\
**Status:** RECOMMENDED

The initial churn prediction target should be defined at the contractual episode level.

A qualifying termination of an episode may represent churn for that episode, even if the customer subsequently starts another episode.

The exact qualifying event and label construction rules remain pending business approval.

### 8.2 Reactivation and Churn Labels

**Decision ID:** EP-REC-012\
**Status:** PENDING_PRODUCT_DECISION

Although reactivation creates a new episode, the business must still determine:

- Which cancellation events qualify as churn.
- Whether a cancellation request can be reversed before its effective date.
- How quickly a new episode may begin after termination.
- Whether a contractual cooling-off or grace period affects episode classification.
- Whether specific termination reasons should be excluded from churn labels.

The identity decision alone does not finalize the churn-label policy.

### 8.3 Customer-Level Relationship Churn

**Decision ID:** EP-REC-013\
**Status:** DEFERRED

Customer-level churn requires a separate definition.

Potential considerations include:

- No active episodes remaining.
- No active contractual relationship.
- No service activity over an agreed period.
- Customer termination recorded in the source system.

These definitions are not interchangeable.

Customer-level churn must not be inferred automatically from one episode ending.

### 8.4 Customer-Level Risk Aggregation

**Decision ID:** EP-REC-014\
**Status:** DEFERRED

Customer-level risk aggregation requires a separate methodology.

Episode-level predictions may eventually be aggregated to support customer-level reporting, but the aggregation method must be explicitly defined and validated.

An episode-level probability must not be interpreted directly as a customer-level churn probability.

### 8.5 Model Evaluation and Data Leakage

**Decision ID:** EP-REC-015\
**Status:** RECOMMENDED

Episode-level observations belonging to the same customer may be statistically dependent.

Training and evaluation design must consider:

- Temporal separation.
- Customer-level grouping.
- Multiple episodes from the same customer.
- Feature availability at prediction time.
- Potential leakage across episodes.

The final split strategy must reflect the intended production use case and evaluation objective.

---

## 9. Data Quality Implications

The existing Data Quality rules must be reassessed after the episode identity and lifecycle definitions are finalized.

| Rule | Current purpose | Episode-level requirement | Current specification status | Current implementation status |
|---|---|---|---|---|
| RI-001 | Subscription customer references a valid customer | Remains valid per episode | PROPOSED | IMPLEMENTED_IN_DQ |
| RI-002 | Snapshot references a valid subscription | Must reference the correct episode | PROPOSED | IMPLEMENTED_IN_DQ |
| RI-003 | Usage references a valid subscription | Must reference the correct episode | PROPOSED | IMPLEMENTED_IN_DQ |
| RI-004 | Invoice references a valid subscription | Requires confirmed invoice-to-episode linkage | PROPOSED | IMPLEMENTED_IN_DQ |
| TC-001 | End date is not before start date | Applies to each episode | PROPOSED | IMPLEMENTED_IN_DQ |
| TC-002 | Cancellation date is not before start date | Applies to each episode, subject to event semantics | PROPOSED | IMPLEMENTED_IN_DQ |
| TC-003 | Snapshot is not before subscription start | Requires reliable episode attribution and date semantics | PENDING_DECISION | PENDING_DECISION |
| TC-007 | Usage corresponds to valid subscription periods | Requires period boundaries and cross-episode policy | PENDING_DECISION | PENDING_DECISION |

### 9.1 Referential Integrity Limitations

RI-001 validates the relationship between subscriptions and customers.

The current RI-002, RI-003 and RI-004 rules verify whether referenced `subscription_id` values exist in the subscriptions dataset.

They do not establish that a source record has been attributed to the correct episode.

Episode-level correctness requires reliable source identity or an approved mapping.

### 9.2 TC-003

TC-003 may be implemented once:

- Every relevant snapshot references an unambiguous episode.
- Episode start dates have approved semantics.
- Historical attribution is reliable.

### 9.3 TC-007

TC-007 requires additional decisions about:

- Usage period boundaries.
- Boundary inclusivity.
- Partial periods.
- Usage spanning episode transitions.
- Source-system attribution.

### 9.4 Existing Data Quality Ownership

Existing Pandera validation remains responsible for structural requirements such as primary-key uniqueness and non-nullability.

Episode-level DQ rules must not duplicate existing schema validations.

---

## 10. Historical Data and Migration

**Decision ID:** EP-REC-016\
**Status:** RECOMMENDED

A change to the meaning of `subscription_id`, required columns, or dataset keys may affect compatibility with existing CSV files.

Before revising the contract, the project must assess:

1. Existing client data using one source identifier across multiple episodes.
2. Availability of reliable episode-level identifiers.
3. Historical mapping between source subscriptions and episodes.
4. Snapshot attribution.
5. Usage attribution.
6. Invoice attribution.
7. Existing synthetic datasets and test fixtures.
8. CSV templates and onboarding documentation.

### 10.1 Historical Attribution Principles

The following principles are recommended:

- Preserve historical records.
- Do not overwrite previous episodes.
- Do not fabricate historical episode attribution.
- Do not assign records to episodes based solely on dates or status.
- Preserve source-system traceability where possible.
- Require an explicit and auditable mapping when source data does not directly identify the episode.

### 10.2 Unresolved Historical Records

Historical records without reliable episode attribution must be treated as unresolved.

The project must not silently assign these records to an episode.

The following handling options require a future product decision:

- Reject the affected records or dataset.
- Quarantine unresolved records for manual or client-assisted review.
- Accept the dataset with explicitly documented exclusions, where the intended use case permits it.

The acceptance criteria, impact on data completeness, and effect on model eligibility must be defined before implementation.

### 10.3 Contract Versioning

The existing contract is v1.1.

The following changes may require a new contract version:

- New required fields.
- Changed primary-key semantics.
- Changed dataset granularity.
- New foreign-key relationships.
- Changed required dataset behavior.

Whether clarifying `subscription_id` alone requires a version increment must be assessed against the existing contract versioning policy.

No version change is approved by this document.

---

## 11. Open Decision Register

The following decisions must be resolved before implementation.

| ID | Decision | Category | Dependency |
|---|---|---|---|
| DD-EP-001 | Define the contractual episode boundary | PENDING_CLIENT_DECISION | Source lifecycle semantics |
| DD-EP-002 | Confirm source subscription identifier availability and reuse | PENDING_CLIENT_DECISION | Source-system discovery |
| DD-EP-003 | Define remaining internal episode ID and registry design/operational details; canonical ownership, UUID strategy, and registry requirement are approved by ADR-010; additional Registry functional requirements are approved by PD-001 | PENDING_PRODUCT_DECISION | DD-EP-002 |
| DD-EP-004 | Confirm whether source-system namespace metadata is required | PENDING_CLIENT_DECISION | Source-system architecture |
| DD-EP-005 | Define cancellation event semantics | PENDING_CLIENT_DECISION | Contract and source event definitions |
| DD-EP-006 | Define renewal and contract extension behavior | PENDING_CLIENT_DECISION | Contract lifecycle |
| DD-EP-007 | Define suspension and pause behavior | PENDING_CLIENT_DECISION | Service lifecycle |
| DD-EP-008 | Define snapshot-to-episode attribution | PENDING_CLIENT_DECISION | Source data availability |
| DD-EP-009 | Define usage-to-episode attribution | PENDING_CLIENT_DECISION | Source data and usage periods |
| DD-EP-010 | Define usage periods crossing episode boundaries | PENDING_PRODUCT_DECISION | DD-EP-009 |
| DD-EP-011 | Define invoice-to-episode attribution | PENDING_CLIENT_DECISION | Financial source semantics |
| DD-EP-012 | Define historical migration acceptance criteria | PENDING_PRODUCT_DECISION | DD-EP-002, DD-EP-008, DD-EP-009, DD-EP-011 |
| DD-EP-013 | Define episode-level churn qualification | PENDING_PRODUCT_DECISION | DD-EP-005 |
| DD-EP-014 | Define customer-level churn, if included | DEFERRED | Episode-level model |
| DD-EP-015 | Define customer-level risk aggregation | DEFERRED | DD-EP-014 |
| DD-EP-016 | Define contract version and backward compatibility | PENDING_PRODUCT_DECISION | Approved schema changes |
| DD-EP-017 | Define model evaluation grouping and temporal strategy | PENDING_PRODUCT_DECISION | Historical episode structure |

DD-EP-003 is partially resolved at product architecture level by ADR-010 and further defined by approved PD-001 Option B in `docs/04_data/product_decision_proposals.md`. Its approved scope includes Nowa ownership of canonical episode identity, UUID as the initial generation strategy, the persistent Episode Identity Registry requirement, and product-level functional requirements for conflict detection, visibility of unresolved identity, traceable mapping corrections, auditable identity and mapping history, and preservation of previous mapping lineage. Registry schema, storage/persistence technology, APIs and service boundaries, transaction design, operational ownership, detailed conflict and correction workflows, retention/deletion, source namespace representation, and CSV identity exchange remain pending. The existing status vocabulary has no partially resolved category, so the decision remains `PENDING_PRODUCT_DECISION` for these unresolved details.

---

## 12. Recommended Documentation and Implementation Sequence

No implementation should begin until the relevant decisions have been reviewed and approved.

| Sequence | Activity | Expected output |
|---|---|---|
| 1 | Review and approve this specification | Approved decision baseline |
| 2 | Resolve remaining episode lifecycle and identity decisions | Completed decision register, with client-dependent items explicitly identified |
| 3 | Update ADR-009 | Explicit episode-level prediction entity |
| 4 | Design the approved identity registry, resolve remaining source-ID/namespace decisions, and revise the Customer Data Contract | Approved detailed design and client-dependent requirements; new contract version, if required |
| 5 | Update dataset examples and CSV templates | Consistent episode-level examples |
| 6 | Update Pandera schemas | Episode-level structural validation |
| 7 | Update ingestion and normalization mappings | Support for approved fields and keys |
| 8 | Update Referential Integrity rules | Episode-level reference validation |
| 9 | Reassess temporal consistency rules | Approved TC-003 and TC-007 definitions |
| 10 | Update synthetic datasets and tests | Multi-episode and reactivation coverage |
| 11 | Define migration and onboarding procedures | Client data acceptance criteria |
| 12 | Resume downstream modelling design | Episode-level modelling baseline |

---

## 13. Approval Criteria

This specification may be approved when:

- The approved architectural decisions are confirmed.
- Technical recommendations have been reviewed and their current disposition is explicitly documented. Recommendations may remain open, provided they are not treated as approved requirements or implementation instructions.
- Client-dependent decisions are clearly identified.
- No unresolved decision is incorrectly represented as a finalized requirement.
- Dependencies between decisions are understood.
- The implementation sequence is agreed.

Approval of this document does not automatically authorize changes to the Data Contract, schemas, ingestion, normalization, or Data Quality implementation.

Those changes require their own scoped implementation steps and review.

---

## 14. Final Architectural Position

The Nowa Customer Intelligence architecture will use the contractual subscription episode as the prediction entity.

Each episode will have an independent identity and lifecycle, while the customer remains the associated account identity.

A reactivation following termination creates a new episode, and previous episodes remain historically preserved.

The canonical `subscription_id` is Nowa-owned and UUID-based, identifies one contractual episode, and remains stable and never reassigned. Source-system identifiers remain separate provenance and mapping information and do not automatically identify an episode.

The canonical identifier is generated once for an authoritatively established new episode, persisted, and reused across submissions. The persistent Episode Identity Registry supports episode recognition and mapping within strict client isolation. UUID version and implementation details, and registry design and operations, remain unresolved.

Historical snapshots, usage records, and invoices must be associated with episodes only when their attribution is supported by reliable source data or an explicitly approved mapping.

The existing Data Contract v1.1 must be reviewed and potentially revised before episode-level reactivation support can be implemented safely.

**Implementation boundary:** ADR-010 approves the identity architecture but does not authorize implementation. UUID generation, the Episode Identity Registry, registry schema/database design, ingestion, normalization, schema, referential integrity, temporal validation, migration, and Customer Data Contract v1.1 changes remain outside this specification's implementation scope and require separately authorized work.
