# Contract Revision Readiness and Decision Decomposition

> **Historical design record.** This document preserves the Phase 02 assessment and its implementation observations at the time of review. For governing requirements, see the [approved Customer Data Contract](customer_data_contract.md) and [ADR-010](../03_architecture/adr_episode_identity_and_identifier_management.md).

**Document ID:** NCI-CONTRACT-READINESS-001
**Version:** 0.1
**Status:** Draft for product and technical review
**Project:** Nowa Customer Intelligence
**Scope:** Phase 2.4.4.7 — Contract Revision Readiness and Decision Decomposition
**Assessment date:** 2026-11-15

> This assessment is a decision framework and recommendation. It does not approve a revised contract, assign a contract version, or authorize implementation.

## 1. Executive Summary

Contract v1.1 remains the approved interface. The semantic revision proposal is directionally aligned with approved identity decisions, but it is not ready to become an executable revised contract. The most consequential unresolved items are client source identifier behavior, evidence for episode boundaries and reactivation, correct attribution of snapshots/usage/invoices, snapshot workflow orchestration, actual producer/consumer compatibility, and contract versioning. The current loader still requires snapshots despite approved PD-006 policy that makes them optional for basic ingestion.

Nowa can independently define internal technical choices and product acceptance principles within ADR-010 and PD-001–PD-007, provided those choices do not presume client facts or alter approved decisions. Client evidence is required for source-system behavior, identifiers, lifecycle events, and dependent-record attribution. Joint agreement is needed where Nowa’s product acceptance policy must be applied to a client’s evidence and operating process, including unresolved records, partial migration, source-to-canonical exchange, and release arrangements.

**Overall conclusion: PARTIALLY READY to define a tightly bounded MVP and proceed with internal design; NOT READY to approve the proposed revised contract or process arbitrary client history as episode-resolved.** A safe MVP can implement data acceptance and validation foundations and a minimum persistent identity capability, then process only records whose episode identity is supported by authoritative evidence. Unresolved records must remain identifiable and excluded from identity-dependent feature/model processing. A limited persistent Registry may be sufficient for an initial controlled deployment if it satisfies ADR-010 and PD-001–PD-004; an in-memory or file-local ID generator is not sufficient.

The MVP need not solve every future lifecycle case, migrate all history, or use optional usage/invoice data. It must not claim temporal-modelling eligibility without snapshots, treat missing snapshots as zero activity, infer identity from source IDs/dates/status/order/heuristics alone, or report partial acceptance as full-population acceptance. Before formal contract approval, Nowa and the client need a concrete, evidence-supported normative contract delta, producer/consumer review, dataset availability behavior, reference semantics, and a version/release assessment under PD-007.

## 2. Scope and Assessment Methodology

This assessment uses Customer Data Contract v1.1, the semantic revision proposal, design proposal, impact analysis, and compatibility assessment; ADR-009/010; the Episode Lifecycle Decision Specification; product decision and DD registers; Data Quality Specification and implementation architecture; and supporting episode/contract impact assessments. Actual code reviewed includes header inspection, CSV ingestion, type normalization, all five Pandera schemas, DQ models and RI/TC validators, and relevant unit and integration tests.

Ownership categories describe who supplies facts or has authority to decide a policy. They do not change an existing decision’s status. MVP relevance asks whether a capability is necessary to make the declared initial product claim safely, not whether it is useful in the future. Technical dependencies identify implementation prerequisites but do not grant implementation authority.

This document marks statements as:

- **Documented/observed:** directly stated in repository documents or implemented in inspected code.
- **Approved:** explicitly approved by the governing decision records.
- **Recommendation/inference:** assessment judgment, not an approved requirement.
- **Assumption:** a bounded planning condition that must be verified before use.

No live client data, client source-system evidence, or actual external producer/consumer inventory was available. Therefore client compatibility, source identifier capability, history coverage, and client-specific episode attribution cannot be asserted. No universal questionnaire, evidence threshold, or source behavior is inferred.

## 3. Governing Architecture and Decision Traceability

| Decision | Approved status and scope | Constraint on this assessment |
|---|---|---|
| ADR-009 | Approved subscription-level prediction granularity. | Establishes the prediction granularity. It does not alone state the fully explicit episode-level prediction entity. |
| EP-DEC-002 | Approved: the contractual subscription episode is the prediction entity. | Defines the entity within ADR-009’s subscription-level prediction granularity. |
| ADR-010 | Approved canonical episode identity architecture: Nowa owns the canonical ID; a persistent, client-isolated Episode Identity Registry is required; issuance follows authoritative evidence; recognized episodes reuse persisted IDs; ambiguity is not silently resolved. | Canonical identity principles are binding; UUID version, registry technology/API/operations and CSV exchange are not thereby decided. |
| EP-DEC-001 | Approved customer identity distinction. | `customer_id` identifies customer/account, not episode prediction identity. |
| EP-DEC-003 | Approved historical episode preservation. | Prior episodes and identity history cannot be silently erased or overwritten. |
| EP-DEC-004 | Approved customer-to-episode relationship. | A customer can relate to multiple episodes; no customer-level aggregation is added to initial scope. |
| EP-DEC-005 | Approved: reactivation following termination creates a new episode. | Does not define client termination evidence or all lifecycle boundaries. |
| PD-001 | Approved Option B: registry functional requirements for conflict detection, unresolved identity visibility, traceable corrections, auditable identity/mapping history, and preservation of prior mapping lineage. | Functional outcomes are binding; technical implementation/workflows are not approved by PD-001. |
| PD-002 | Approved Option B: issue canonical ID only after authoritative establishment of a new episode; reuse persisted ID for recognized episodes; unseen rows and source IDs/dates/status/order/heuristics alone do not establish identity. | No automatic ID issuance/reuse from file novelty or weak evidence. Universal thresholds and client criteria remain open. |
| PD-003 | Approved Option C: explicitly attributable records may be accepted; unresolved records remain identifiable and excluded from identity-dependent processing; no silent resolution. | Partial acceptance must be explicit and must not be represented as full-population acceptance. |
| PD-004 | Approved Option C: repeated file is a submission event, recognized episodes reuse canonical IDs, and changes/corrections must preserve identity history. | No replacement ID merely because a file is resubmitted; exact duplicate/correction workflow remains open. |
| PD-005 | Approved Option B: partial historical acceptance where authoritative evidence exists; unresolved records remain excluded from identity-dependent processing. | No fabricated episode boundaries, attribution, or universal acceptance threshold. |
| PD-006 | Approved Option B: snapshots optional for basic ingestion and mandatory for temporal-modelling workflows; usage/invoices optional. | Missing snapshots do not mean zero activity; ingestion success is not modelling eligibility. Current loader behavior differs. |
| PD-007 | Approved Option C compatibility/versioning principles. | Assess exact delta against strict consumers, validators, migration, release and deprecation needs; do not assign version here. |

All statuses above remain as governed. This assessment neither reopens nor expands approved decisions.

## 4. Decision Ownership Framework

| Ownership category | Meaning | Example boundary |
|---|---|---|
| `NOWA_PRODUCT_DECISION` | Nowa product policy, commercial scope, acceptance criteria, or intended outcomes. | Define whether unresolved records can be excluded from a particular product workflow, consistent with PD-003. |
| `NOWA_TECHNICAL_DECISION` | Internal implementation, architecture, validation, security, testing, and engineering choices within approved policy. | Select internal persistence and transaction mechanisms for an authorized Registry design. |
| `CLIENT_DECISION` | Client-owned source-system or business facts requiring client confirmation. | Confirm source ID reuse behavior or the meaning of a source termination event. |
| `JOINT_DECISION` | Nowa product policy applied to client-specific evidence/process, requiring agreement by both parties. | Agree canonical mapping exchange and how unresolved records affect a client submission. |
| `EXTERNAL_DEPENDENCY` | Facts or capabilities controlled by a third-party system/provider outside both parties. | Provider export behavior or retention/access controls that neither Nowa nor the client can independently change. |

Ownership is not approval status: an item may be owned by Nowa while remaining proposed or pending, and a client decision remains pending until evidence/confirmation is obtained. Some decisions split across categories; the inventory preserves original decision IDs and shows the primary ownership plus any split.

## 5. Complete Decision Inventory and Ownership Classification

Statuses are transcribed from governing registers. Ownership and actions are recommendations only; they do not change those statuses.

| Decision ID | Topic | Existing status | Ownership | MVP relevance | Required evidence/input | Dependency | Recommended next action |
|---|---|---|---|---|---|---|---|
| DD-EP-001 | Contractual episode boundary | `PENDING_CLIENT_DECISION` | `JOINT_DECISION` | Blocking for episode-resolved records. | Client contract and lifecycle event semantics. | DD-EP-005/006/007. | Obtain source evidence; define a reproducible boundary for supported records. |
| DD-EP-002 | Source subscription ID availability/reuse | `PENDING_CLIENT_DECISION` | `CLIENT_DECISION` for facts; joint mapping policy | Blocking for source-linked recognition path. | IDs by source/dataset, stability, reuse, history, availability. | DD-EP-004/003. | Discover actual identifiers; do not mandate a field beforehand. |
| DD-EP-003 | Remaining Registry design/operations | `PENDING_PRODUCT_DECISION`, partially resolved by ADR-010 and PD-001 | Split: approved architecture/functions; remaining `NOWA_PRODUCT_DECISION` / `NOWA_TECHNICAL_DECISION` / joint exchange | Minimum persistent identity capability is MVP-required; broader operations can be phased. | Approved acceptance criteria and client submission process. | ADR-010, PD-001, DD-EP-002. | Preserve approved scope; decompose unresolved technology, operations, and exchange decisions. |
| DD-EP-004 | Source namespace | `PENDING_CLIENT_DECISION` | `JOINT_DECISION` | Needed if source IDs are namespace-scoped for recognition. | Source topology, identifier collision domains, metadata. | DD-EP-002/003. | Discover source systems; choose minimum representation later. |
| DD-EP-005 | Cancellation/termination semantics | `PENDING_CLIENT_DECISION` | `JOINT_DECISION` | Blocking when lifecycle events determine episode identity or labels. | Effective/request dates, reversals, contractual evidence. | DD-EP-001/013. | Map supported source events; do not infer from status labels. |
| DD-EP-006 | Renewal/extension behavior | `PENDING_CLIENT_DECISION` | `JOINT_DECISION` | Conditional for histories with renewals. | Contract terms and source representation. | DD-EP-001. | Confirm whether supported examples continue or create an episode. |
| DD-EP-007 | Suspension/pause behavior | `PENDING_CLIENT_DECISION` | `JOINT_DECISION` | Conditional for affected episodes. | Meaning/timing of pause/suspension and service state. | DD-EP-001/013. | Keep affected identity/label decisions unresolved until mapped. |
| DD-EP-008 | Snapshot-to-episode attribution | `PENDING_CLIENT_DECISION` | `JOINT_DECISION` | Blocking for temporal use of affected snapshots. | Stable episode linkage/crosswalk over history. | PD-006; DD-EP-001/002. | Accept only evidence-supported attribution. |
| DD-EP-009 | Usage-to-episode attribution | `PENDING_CLIENT_DECISION` | `JOINT_DECISION` | Blocking only for usage-dependent records/features. | Usage key, measurement interval, episode linkage. | DD-EP-010. | Keep usage excluded where unsupported. |
| DD-EP-010 | Usage periods crossing episode boundaries | `PENDING_PRODUCT_DECISION` | `JOINT_DECISION` | Not blocking if usage is excluded. | Period boundaries and client process, plus product disposition. | DD-EP-009. | Decide a policy only when usage is in scope; do not assume allocation. |
| DD-EP-011 | Invoice-to-episode attribution | `PENDING_CLIENT_DECISION` | `JOINT_DECISION` | Blocking only for invoice-dependent processing. | Invoice reference, service period, credits/reissues, multi-episode behavior. | PD-006; DD-EP-002. | Leave invoices optional and exclude unattributable records from episode features. |
| DD-EP-012 | Historical migration acceptance | `PENDING_PRODUCT_DECISION` | `JOINT_DECISION` | Not required for a controlled new/current dataset if migration is excluded; required for historical migration. | Client coverage, crosswalks, unresolved population and intended use. | PD-005; DD-EP-008/009/011. | Set client-specific acceptance criteria after profiling. |
| DD-EP-013 | Episode-level churn qualification | `PENDING_PRODUCT_DECISION` | `JOINT_DECISION` | Blocking for supervised churn labels/training; not for validation-only ingestion. | Product target/horizon and client contractual events. | DD-EP-005/001. | Define product label policy and validate event mapping jointly. |
| DD-EP-014 | Customer-level churn | `DEFERRED` | `DEFERRED` | Outside initial MVP. | None for initial episode scope. | DD-EP-015. | Keep customer-level churn unavailable. |
| DD-EP-015 | Customer-level risk aggregation | `DEFERRED` | `DEFERRED` | Outside initial MVP. | None for initial episode scope. | DD-EP-014. | Keep customer aggregation unavailable. |
| DD-EP-016 | Contract version/backward compatibility | `PENDING_PRODUCT_DECISION` | `JOINT_DECISION` | Blocking for formal revised contract/release, not internal foundation work. | Exact delta and client consumer behavior. | PD-007. | Complete compatibility review before version assignment. |
| DD-EP-017 | Model evaluation grouping/temporal strategy | `PENDING_PRODUCT_DECISION` | `NOWA_PRODUCT_DECISION`, informed by client data | Needed before evaluation claims/model release; not a CSV prerequisite. | Episode/customer relationships, temporal coverage, evaluation objective. | ADR-009; training data. | Resolve for model evaluation; no split strategy prescribed here. |
| DD-001 | Snapshot date convention | Open in v1.1; pending | `JOINT_DECISION` | Blocking for convention-specific temporal checks, not basic ingestion. | Source observation-date convention. | Snapshot use. | Do not assume first/last day; resolve before enforcing convention. |
| DD-002 | Historical snapshot coverage | Open in v1.1; pending | `JOINT_DECISION` | Blocking for coverage claims/thresholds only. | Available history and intended model needs. | PD-006, temporal workflow. | Define coverage expectation only for a stated use case. |
| DD-003 | Churn definition | Open in v1.1; pending | `JOINT_DECISION` | Blocking for supervised churn model labels. | Client event semantics and product target. | DD-EP-013. | Resolve before training; not a schema prerequisite. |
| DD-004 | Reactivation | Open in v1.1; direction superseded by EP-DEC-005 | `JOINT_DECISION` | Boundary evidence blocking for affected history. | Termination effectiveness/reactivation evidence. | DD-EP-001/005. | Apply approved new-episode direction only when evidence supports it. |
| DD-005 | Contract renewal | Open in v1.1 | `JOINT_DECISION` | Conditional for renewal histories. | Renewal/extension semantics. | DD-EP-006. | Keep affected episode attribution unresolved until confirmed. |
| DD-006 | Subscription episodes | Open in v1.1; canonical episode direction approved | `JOINT_DECISION` | Core episode processing requires supported boundaries/identity. | Source evidence and legacy representation. | ADR-010, EP-DEC-002. | Preserve approved direction; resolve client mapping/boundaries. |
| DD-007 | Subscription status mapping | Open in v1.1 | `JOINT_DECISION` | Blocking when source statuses are not canonical. | Client source status values and meanings. | Schema validation. | Approve client mapping before schema validation of such values. |
| DD-008 | Revenue definition | Open in v1.1 | `JOINT_DECISION` | Blocking only for financial/revenue interpretation. | Billing basis and meaning. | DD-009. | Do not label or transform revenue as MRR/ARR without agreement. |
| DD-009 | Currency handling | Open in v1.1 | `NOWA_PRODUCT_DECISION` plus client facts | Blocking for conversion/combined-currency financial claims. | Currency codes and applicable finance requirements. | DD-008. | Keep raw currency amounts uncombined unless policy is approved. |
| DD-010 | Timezone/cutoff | Open in v1.1 | `JOINT_DECISION` | Blocking for cutoff-dependent temporal claims. | Source timezone and extraction cutoff. | TC checks. | Supply explicit cutoff context before cutoff rules run. |
| DD-011 | Historical availability | Open in v1.1 | `JOINT_DECISION` | Blocking for point-in-time availability claims. | Recording/availability timestamps and source lineage. | Snapshot/invoice temporal use. | Restrict point-in-time claims if evidence is absent. |
| DD-012 | Prediction horizon | Open in v1.1 | `NOWA_PRODUCT_DECISION` informed by client feasibility | Blocking for churn label/training target. | Product outcome needs and data feasibility. | DD-003/013. | Define before supervised modeling. |
| DD-013 | Observation window | Open in v1.1 | `NOWA_PRODUCT_DECISION` informed by client feasibility | Blocking for feature/label construction. | Product design and temporal data coverage. | DD-012. | Define before training; no provisional window assumed final. |
| DD-014 | Customer aggregation | Open in v1.1; customer-level scope deferred | `DEFERRED` for initial MVP | Not in initial scope. | None for initial episode scope. | DD-EP-014/015. | Do not add customer-level targets or outputs. |
| DD-015 | Missing-data thresholds | Open in v1.1 | `NOWA_PRODUCT_DECISION` with client evidence | Blocking only for threshold-based quality claims. | Field completeness and use-case tolerance. | DQ reporting. | Report observed completeness without inventing universal thresholds. |
| EXT-01 | Source ID and namespace exchange | No approved field/interface; related DD-EP-002/004 pending | `JOINT_DECISION` | Blocking for source-linked registry matching. | Actual source identifiers, reuse, namespace. | ADR-010, DD-EP-002/004. | Discover first; do not add fields by assumption. |
| EXT-02 | Empty-file policy | Not explicitly resolved | `NOWA_PRODUCT_DECISION` with client workflow input | Blocking only when empty datasets are submitted. | Missing vs header-only vs zero-row meaning. | Ingestion/DQ. | Define distinct states before accepting empties as valid data. |
| EXT-03 | Snapshot workflow interface | PD-006 approved; interface unresolved | `NOWA_TECHNICAL_DECISION` with product approval | Required to implement optionality safely. | Workflow intent and temporal claim. | PD-006, ingestion. | Propose an interface for review; do not silently infer workflow from file presence. |
| EXT-04 | Client producer/consumer inventory | Not available | `CLIENT_DECISION` / joint compatibility work | Blocking for compatibility claims and final release plan. | Producer/consumer list and contract assumptions. | PD-007, DD-EP-016. | Inventory before contract release. |
| EXT-05 | Contract version notation (`1.1` vs `1.1.0`) | Inconsistent in existing material | `NOWA_PRODUCT_DECISION` | Blocking for assigning a new version. | Versioning convention owner and policy. | DD-EP-016, PD-007. | Resolve separately; preserve both notations until decided. |
| EXT-06 | Implementation authorization | Not granted by this assessment | `NOWA_PRODUCT_DECISION` and governance | Blocking for code changes. | Approved scope, acceptance criteria, owners. | Contract/architecture gates. | Seek explicit authorization after readiness decisions. |
| EXT-07 | Registry technical/operational design | Not fully specified; ADR-010/PD-001 constrain it | `NOWA_TECHNICAL_DECISION`, some joint operating choices | Persistent minimum capability is MVP-required. | Security/isolation, lifecycle, operational support needs. | ADR-010, PD-001. | Design minimum compliant implementation and review separately. |
| EXT-08 | External provider limitations | Not inventoried | `EXTERNAL_DEPENDENCY` | Client/feature dependent. | Provider API/export/retention behavior. | Relevant client workflows. | Record only when discovery identifies a provider dependency. |

The `DD-001` to `DD-015` entries retain the open state recorded against v1.1 unless a specific approved direction is noted. Overlap with `DD-EP-*` is intentional: contract-era decisions and episode-specific decomposition are distinct registers, not interchangeable IDs.

## 6. Decisions Nowa Can Make Independently

The following are candidates for internal decisions, not approvals created by this document:

| Topic | Existing approved principle | Possible independent decision | Unresolved choice / approval needed |
|---|---|---|---|
| Canonical ID representation and UUID detail | ADR-010 approves UUID as initial generation strategy and canonical Nowa ownership. | Choose an internal UUID version/format consistent with that principle. | Version and lifecycle details remain open; require architecture/security review and formal decision. |
| Registry technology and isolation | ADR-010 requires persistent, client-isolated Registry; PD-001 defines functional outcomes. | Compare internal storage/service approaches and enforce tenant/client isolation. | Storage, schema, API, transactions, operations, retention and authorization mechanics remain unresolved. |
| Conflict and unresolved representation | PD-001 requires conflict detection and unresolved identity visibility; PD-003 forbids silent resolution. | Define internal states and safe diagnostics. | Do not invent a public status enum or operational disposition without product approval. |
| Auditability and correction | PD-001/004 require traceable corrections and preserved mapping lineage. | Select technical audit/event representation and immutability controls. | Exact records, retention/deletion, permissions, and workflow require review. |
| Validation boundaries | Existing architecture separates header, ingestion, normalization, schemas, and DQ. | Refine orchestrator stage boundaries and error propagation. | Report/coordinator implementation requires separate authorization and approved interface. |
| Basic vs temporal orchestration | PD-006 policy is approved. | Propose explicit internal workflow input and prevent implicit eligibility. | Product approval of API/default and downstream effects needed; missing snapshots cannot imply zero. |
| Internal MVP scope | Approved episode identity principles and optional datasets constrain scope. | Limit MVP to supported, evidence-attributed episodes and make exclusions visible. | Product sign-off and client acceptance required; cannot weaken identity requirements. |
| Test/synthetic strategy | No live client data is required for unit testing. | Use synthetic, non-client fixtures for deterministic edge cases and isolation tests. | Ensure fixtures do not encode unresolved policy as approved behavior. |
| Documentation/release governance | PD-007 requires exact-delta review. | Define internal review checklist and change-control artifacts. | Contract version and client rollout remain joint/product decisions. |

## 7. Decisions Requiring Client Evidence

Client evidence is needed to establish facts, not to delegate Nowa product policy to each client.

| Topic | Evidence needed | Consequence if absent |
|---|---|---|
| Source subscription IDs and reuse (DD-EP-002) | Identifier fields per source/dataset, stability, reuse/reassignment, history, and whether IDs appear in snapshots/usage/invoices. | Do not match episodes based on assumed source key uniqueness. |
| Source namespace (DD-EP-004) | Systems/tenants and identifier collision domains; namespace metadata actually available. | Avoid assuming source IDs are globally unique. |
| Episode boundaries (DD-EP-001, DD-006) | Contractual lifecycle events and source representation of start/end/effectiveness. | Affected records remain unresolved for episode-dependent processing. |
| Cancellation/termination/reactivation (DD-EP-005, DD-004) | Effective termination evidence, reversals, reactivation linkage, event history. | Do not infer new episode or reuse identity from status/date alone. |
| Renewal/extension and pause/suspension (DD-EP-006/007; DD-005) | Contract terms, transition events and source meaning. | Restrict lifecycle attribution for affected histories. |
| Snapshot attribution (DD-EP-008) | Stable episode key or auditable crosswalk across dates. | Snapshots cannot support episode temporal features unless attributable. |
| Usage attribution/periods (DD-EP-009/010) | Row aggregation grain, covered interval, linkage, partial periods and boundary behavior. | Exclude usage records/features with unsupported episode attribution; no allocation. |
| Invoice attribution (DD-EP-011) | Invoice relationship, service period, credits/reissues, multi-episode billing. | Do not include invoice in episode-level features absent reliable attribution. |
| Historical migration (DD-EP-012) | Actual history coverage, authoritative crosswalk/event evidence, unresolved population. | No migration completeness claim or fabricated historical episode splits. |
| Status mapping (DD-007) | Source status values, meanings, transitions. | Canonical schema rejection or unresolved mapping; no direct semantic mapping by label similarity. |
| Revenue/billing (DD-008/009) | Billing basis, amount meaning, currency population and client finance requirements. | Do not interpret as MRR/ARR or combine currencies. |
| Timezone/cutoff and availability (DD-010/011) | Source timezone, extraction cutoff, record availability timestamps/lineage. | Restrict temporal/cutoff and point-in-time claims. |
| Producer/consumer compatibility | Actual exporting systems, downstream joins, accepted columns/keys and consumer owners. | No external compatibility claim or release readiness conclusion. |

## 8. Joint Nowa/Client Decisions

Joint decisions combine Nowa’s product rules with client-specific evidence and operational agreement:

- **Canonical ID exchange and mapping:** Nowa owns the canonical identity and registry policy; the client confirms source identifiers and participates in a workable, governed exchange. Neither side may treat an unverified source key as canonical.
- **Ambiguous records:** Nowa defines safe product constraints under PD-003; parties agree submission consequences and review/escalation responsibilities. Records remain unresolved and excluded from identity-dependent processing until supported disposition.
- **Partial history acceptance:** Nowa owns migration acceptance principles under PD-005; client evidence determines which records meet them. Accepted subsets and excluded/unresolved populations must be distinguishable.
- **Corrections/resubmissions:** PD-004 makes each file a submission event and protects identity history. The parties need a correction and changed-identifier process that never silently overwrites mappings.
- **Dataset availability:** PD-006 defines snapshot policy; workflow intent and the client’s submitted data determine whether a run is basic or temporal. Missing snapshots do not mean zero activity and basic-ingestion success does not imply modelling eligibility.
- **Coverage and quality expectations:** Nowa defines product-specific use requirements; client data determines achieved coverage. No universal minimum is assumed.
- **Contract/release/migration:** Nowa applies PD-007 to the exact delta; client producer/consumer evidence informs transition impact, timing, and any support arrangements.

## 9. MVP Scope and Minimum Decision Requirements

Classifications describe the recommended first commercial product boundary, not current implementation completeness.

| Capability | Classification | Minimum condition / rationale |
|---|---|---|
| CSV header inspection | `MVP_REQUIRED` | Existing foundation; exact contract headers must be validated strictly. |
| CSV ingestion | `MVP_REQUIRED` | Required datasets and supplied optional files must be read safely; file presence/empty/error distinctions must be explicit. |
| Type normalization | `MVP_REQUIRED` | Explicit, loss-aware normalization before schema checks; no identity inference. |
| Field-level schema validation | `MVP_REQUIRED` | Enforce approved types, requiredness, keys and field constraints. |
| Cross-dataset referential integrity | `MVP_REQUIRED` | Check relationships for supplied datasets; existence must not be presented as proof of episode attribution. |
| Basic Data Quality reporting | `MVP_REQUIRED` | Communicate run/dataset/record findings and excluded/unresolved populations without leaking raw rows or identifiers. Existing full report/coordinator is absent and needs authorized work. |
| Snapshot optionality under PD-006 | `MVP_REQUIRED` | Basic ingestion must allow omission; temporal workflow must require snapshots. Missing snapshots are not zero; orchestration must be explicit. |
| Episode identity management | `MVP_REQUIRED` | Any episode-dependent processing needs persistent, client-isolated canonical identity per ADR-010. |
| Canonical ID issuance and reuse | `MVP_REQUIRED` | Issue only after authoritative evidence; reuse persistent ID for recognized episodes. No in-memory/file-local IDs. |
| Ambiguous identity handling | `MVP_REQUIRED` | Detect/surface unresolved identity and exclude affected records from identity-dependent processing per PD-003. |
| Historical migration | `CLIENT_DEPENDENT` | Only needed when historical source records are in scope; partial acceptance follows PD-005 and evidence. A new controlled/current dataset may avoid migration. |
| Usage and invoice attribution | `CLIENT_DEPENDENT` | Optional datasets/features may be omitted; supplied records can be validated but not used as episode features absent reliable attribution and policy. |
| Episode-level feature engineering | `MVP_CONDITIONAL` | Needed for modelling product claim; limited to attributable, point-in-time appropriate inputs. |
| Churn model training | `MVP_CONDITIONAL` | Requires approved episode-level outcome, observation/horizon, adequate eligible data and evaluation design. Not a prerequisite to validate/accept datasets. |
| Episode-level predictions | `MVP_CONDITIONAL` | Core commercial model output only after identity, labels, eligibility, and evaluation safeguards are met. |
| Streamlit reporting | `POST_MVP` | No governing decision makes this the initial delivery interface; a safe report/API can be selected separately. |
| Model evaluation and monitoring | `MVP_CONDITIONAL` | Evaluation safeguards are required before claiming model quality or release; monitoring scope depends on deployment. DD-EP-017 remains pending. |
| Minimum identity and mapping audit/correction safeguards | `MVP_REQUIRED` | Persistent identity/history, conflict detection, unresolved visibility, traceable corrections, and preserved lineage are required by ADR-010 and PD-001–PD-004. Advanced interfaces and automation are separate post-MVP capabilities. |

The Registry scope distinction is:

| Capability | Recommended classification |
|---|---|
| Persistent identity and mapping history | `MVP_REQUIRED` |
| Conflict detection and unresolved identity visibility | `MVP_REQUIRED` |
| Traceable corrections and preservation of prior lineage | `MVP_REQUIRED` |
| Advanced client-facing review/correction UI | `POST_MVP` |
| Automated multi-step operational review workflows | `POST_MVP` |

Deferring the advanced interface and automation does not defer the identity invariants required by ADR-010 and PD-001–PD-004.

**Recommended MVP boundary (inference):** controlled client onboarding; validated required data; explicit optional-dataset presence; persistent canonical identity for only evidence-supported episodes; record-level unresolved/excluded reporting; and, when label/evaluation prerequisites are met, episode-level modeling for eligible records. Exclude customer-level churn/risk, unsupported history, unattributable usage/invoices, and temporal modeling without snapshots. Do not market ingestion success as full data acceptance or model eligibility.

## 10. Minimum Viable Episode Identity Strategy

A safe minimum strategy still needs more than generation: (1) authoritative evidence that a new episode exists, (2) persistent client-isolated mapping, (3) reuse of the stored canonical ID when the episode is reliably recognized, (4) conflict detection and an unresolved state, (5) traceable corrections that preserve prior mappings, and (6) a record of the evidence/disposition sufficient for audit. These derive from ADR-010 and PD-001–PD-004.

**Recommendation:** A limited persistent Registry implementation can support an MVP without full future operations if it implements the approved identity invariants and is approved against concrete acceptance criteria. It may defer broad workflow automation, client-facing review UI, generalized integrations, or large-scale migration tooling. It may not defer persistence, client isolation, unresolved identity visibility, lineage preservation, or safe ID reuse. An in-memory mapping, random ID per row/file, or source ID treated as canonical without evidence is insufficient.

The CSV path for receiving or returning canonical IDs remains unresolved. A product/technical design must define how the controlled client provides or receives the canonical mapping before the revised contract can claim an operational exchange. No field, UUID version, database, API, or review workflow is selected here.

## 11. MVP Data Acceptance and Processing Boundaries

These are conceptual gates, not a proposed status enum or API. A submission may contain datasets and records with different outcomes; a single “accepted” flag must not conceal partial processing.

| Boundary | Meaning | What it does not establish |
|---|---|---|
| File received | File is present as a submission artifact. | Valid header, valid rows, new episodes. |
| File structurally valid | Header and row shape conform to the applicable contract. | Valid types, values, identity. |
| Types normalized | Values were losslessly parsed to expected internal representations. | Schema validity or episode resolution. |
| Schema valid | DataFrame meets field, key, and documented schema constraints. | Cross-file existence or correct episode attribution. |
| Referential integrity valid | Required references exist in relevant supplied parent datasets under implemented rules. | That the referenced canonical episode is correct. |
| Episode identity resolved | Authoritative evidence supports canonical ID issuance/reuse and persistent mapping. | Child dataset attribution. |
| Dependent records attributable | A snapshot/usage/invoice is reliably linked to the appropriate episode. | Temporal/financial interpretation beyond approved semantics. |
| DQ accepted | Applicable implemented quality rules pass or findings are handled under approved policy. | Full population accepted when only a subset was eligible. |
| Feature eligible | Record and features satisfy identity, attribution, temporal availability, and feature policy. | Model training eligibility. |
| Training eligible | Label, observation/horizon, evaluation, and data criteria are approved and met. | Production prediction eligibility by itself. |
| Prediction eligible | The record satisfies deployed model’s input/identity requirements. | Broader population eligibility or customer-level conclusions. |

For partial acceptance under PD-003/005, reporting should distinguish submission-level processing outcome, dataset-level validation/presence, and record-level resolved, unresolved, excluded, or eligible counts once the report model is authorized. Report counts must reconcile to the relevant population; unresolved records remain visible as unresolved and excluded from identity-dependent stages. Do not invent a final status vocabulary here.

## 12. Contract Revision Readiness Matrix

| Area | Readiness | Basis and limit |
|---|---|---|
| Customer identity semantics | `READY` | `customer_id` remains customer/account identity; no change needed. |
| Episode prediction entity | `READY` | ADR-009 establishes subscription-level prediction granularity; EP-DEC-002 explicitly defines episode as prediction entity. |
| Canonical ID principles | `READY` | ADR-010 and PD-002 approve core issuance/reuse/ownership principles. |
| Source ID exchange | `NOT_READY` | DD-EP-002/004 and CSV exchange remain open; no source facts. |
| Subscription row grain | `PARTIALLY_READY` | Target episode grain is approved directionally; source grain/current data representation and precise boundaries need client evidence. |
| Reactivation | `PARTIALLY_READY` | New episode after termination approved; termination evidence and event rules remain unresolved. |
| Snapshot availability | `PARTIALLY_READY` | PD-006 policy approved; implementation interface and loader behavior not aligned. |
| Snapshot attribution | `NOT_READY` | DD-EP-008 pending client evidence. |
| Usage attribution | `NOT_READY` | DD-EP-009/010 pending; crossing periods unresolved. |
| Invoice attribution | `NOT_READY` | DD-EP-011 pending; field remains required in v1.1. |
| Historical migration | `PARTIALLY_READY` | PD-005 principles approved; actual evidence/coverage absent. |
| Data Quality responsibilities | `READY` | DQ ownership and statuses documented; full reporting/coordinator not implemented. |
| Producer/consumer compatibility | `NOT_READY` | No actual inventory or external tests. |
| Versioning | `NOT_READY` | Exact delta, notation, consumer impact, and DD-EP-016 unresolved. |
| MVP implementation scope | `PARTIALLY_READY` | Safe boundary can be proposed; formal contract, technical design and implementation authorization remain necessary. |

## 13. Blocking Decisions Versus Deferrable Decisions

### Blocking for any safe MVP claim

- **Canonical identity for any episode-dependent processing:** persistent ID issuance/reuse and client isolation under ADR-010. Without evidence, affected rows remain unresolved and are excluded per PD-003.
- **Ambiguity safeguards and lineage:** unresolved visibility and non-silent correction/history preservation under PD-001–PD-004. An MVP cannot omit these to accelerate delivery.
- **Input and partial-acceptance transparency:** distinguish file/schema validity from identity-resolved and model-eligible records. Do not call a partial population fully accepted.
- **A supported client exchange path:** before client production use, parties must agree how canonical mapping is represented or exchanged; otherwise source-linked recognition cannot be claimed.

These are blocking for the stated safe episode-level MVP, not necessarily for internal component development or schema-only demonstration.

### Blocking only for specific capabilities

| Decision/evidence | Capability blocked while unresolved | Permitted boundary meanwhile |
|---|---|---|
| DD-EP-008 and DD-001/002 | Temporal snapshot attribution, date-convention checks, coverage claims | Basic ingestion without snapshots; no temporal-modelling claim. |
| DD-EP-009/010 | Usage-based episode features for affected data | Keep usage optional and exclude unsupported rows/features. |
| DD-EP-011 | Invoice-based episode features | Keep invoices optional; do not alter required field contract or fabricate attribution. |
| DD-EP-012 | Historical migration | Use only evidence-supported new/current records if available; report no historical completeness claim. |
| DD-EP-013, DD-003, DD-012/013 | Supervised churn labels/training | Validate and prepare data; do not claim trained churn model. |
| DD-EP-017 | Model evaluation strategy and release-quality claims | No final evaluation strategy or performance claim; does not block unrelated contract clarifications. |
| DD-007/008/009 | Client status mapping or financial interpretation | Restrict unsupported statuses/financial use; do not infer mapping or revenue meaning. |
| DD-010/011 | Cutoff/point-in-time claims | Restrict cutoff-dependent and point-in-time claims. |
| DD-EP-016 and consumer inventory | Revised contract release/version assignment | Continue using approved v1.1 until gate is met. |

### Deferrable within a declared MVP boundary

- **Customer-level churn/risk (`DD-EP-014/015`, DD-014):** remain outside scope; do not emit customer-level targets or aggregation.
- **Full historical migration:** can be deferred only if the MVP uses no unverified historical episode assignments and limits processing to supported records. Historical rows remain excluded/unresolved.
- **Usage and invoice use:** can be deferred because datasets are optional; do not use unattributable rows as episode features.
- **Temporal modelling:** can be deferred for basic ingestion; snapshots are then optional, and no missing-snapshot zero or temporal eligibility claim is allowed.
- **Advanced Registry operational interfaces:** can be deferred only after the minimum persistent, isolated, auditable identity and correction safeguards exist. Do not defer required identity invariants.
- **Final evaluation grouping/temporal strategy (`DD-EP-017`):** can wait for contract changes unrelated to evaluation, but must be resolved before model evaluation/release claims. Customer grouping/leakage risk must not be ignored in any evaluation conducted meanwhile.

## 14. MVP Implementation Roadmap

The increments below are proposed planning groups, not approved phases. Each requires its own authorization.

| Increment | Objective | Dependencies / decisions | Components | Acceptance criteria | Explicit exclusions |
|---|---|---|---|---|---|
| MVP-A: Data acceptance and validation foundation | Reliably receive, inspect, normalize, schema-validate, and report datasets and presence. | Contract v1.1 baseline; approved PD-006 workflow interface design; empty-file policy. | Header/ingestion/normalization/schemas/DQ report and tests. | Required files and supplied optional files validated; missing snapshots allowed only for explicit basic mode; no silent coercion; stage outcomes clear. | Episode issuance, migration, temporal eligibility without snapshots. |
| MVP-B: Minimum persistent episode identity | Persist/reuse canonical IDs and surface unresolved/conflicting identity safely. | ADR-010/PD-001/002/003/004 acceptance; client source evidence and exchange agreement. | Registry persistence/isolation, mapping, audit/correction controls, identity tests. | New ID only with authoritative evidence; recognized episodes reuse; conflicts unresolved; lineage retained; client scope isolated. | Generic integration platform, universal evidence thresholds, all future review workflows. |
| MVP-C: Controlled episode-level processing | Process only records with resolved identity and attributable in-scope children. | Client episode boundaries; DD-EP-008/009/011 as applicable; partial-acceptance agreement. | Data preparation, DQ coordination, feature gating, reconciliation. | Record counts reconcile; unresolved rows excluded; child reference existence is not mislabeled attribution; exclusions visible. | Unsupported usage/invoice allocation or full-history migration. |
| MVP-D: Churn modeling and prediction | Build eligible episode-level labels/features and produce validated episode predictions. | DD-EP-013, DD-003/012/013, applicable temporal evidence, DD-EP-017 evaluation decisions. | Label/features, training/evaluation, prediction interface, model tests. | Episode-level unit; no unsupported labels; evaluation design documented; only eligible records scored. | Customer-level churn/risk and claims beyond validated cohort. |
| MVP-E: Reporting and operational controls | Provide suitable client-facing or internal view of status, output, exclusions, and monitoring. | Privacy/report requirements, operational ownership and deployment decisions. | Reporting UI/API, audit operations, monitoring. | Reports avoid raw rows/direct identifiers; scope isolation; safe correction process. | A specific UI framework is not prescribed. |

## 15. Formal Contract Revision Gate

### Minimal MVP-compatible contract

Before formal approval, the normative text must specify:

1. Prediction granularity and the episode as prediction entity, distinctly tied to ADR-009 and EP-DEC-002.
2. Subscription row grain and `subscription_id` as the Nowa-owned canonical ID for one episode, including source/canonical responsibility and a feasible agreed exchange path.
3. New-ID issuance and reuse semantics consistent with ADR-010/PD-002, and unresolved-record boundaries consistent with PD-003.
4. Snapshot dataset availability for basic ingestion versus temporal workflows consistent with PD-006, including explicit workflow behavior; absence is not zero activity.
5. Semantics of dependent references for only those datasets included in MVP and evidence needed to claim episode attribution.
6. Any requiredness/nullability decisions only where the exact use and evidence justify them; do not relax invoice `subscription_id` by inference.
7. Compatibility with actual producers/consumers and strict header/schema validators, including empty/missing dataset behavior.
8. Partial acceptance, submission/correction, identity-lineage, and release/migration implications consistent with PD-003–PD-005.
9. Exact version classification and deprecation/release principles under PD-007 and resolution of DD-EP-016/version notation.
10. Formal product and technical approval. Contract approval must be separate from implementation authorization.

### Broader future contract

Advanced lifecycle events, all source ID/namespace exchange, snapshot/usage/invoice attribution, usage crossing periods, revenue/currency interpretation, history coverage, point-in-time semantics, complete historical migration, and advanced Registry operations can be added when their client/product decisions and evidence are ready. Deferring these means the corresponding datasets, histories, checks, or modeling claims remain unavailable or restricted; it does not authorize guesswork.

## 16. Risks of Overengineering and Underengineering

| Direction | Risk | Balanced boundary |
|---|---|---|
| Overengineering | Full Registry workflow suite before validating a controlled MVP can consume time on unproven operations. | Build only what is needed to meet ADR-010/PD-001 invariants, with explicit interfaces and later extensibility. |
| Overengineering | Generic integrations before source discovery encode assumptions and create needless abstraction. | Discover actual source capability first; design the minimum agreed exchange path. |
| Overengineering | Resolving every lifecycle edge case before first use delays supported cases. | Process only evidence-supported episodes; leave affected cases unresolved and unavailable. |
| Overengineering | Building migration tooling without client history may encode speculative mappings. | Define migration principles now; implement client-specific tooling after evidence. |
| Underengineering | Generating IDs without persistence or treating source IDs as canonical can duplicate or conflate episodes. | Require persistent, isolated mappings and authoritative evidence before issuance/reuse. |
| Underengineering | Silently assigning ambiguous records or overwriting mappings violates approved policy. | Make conflicts/unresolved identity visible and preserve lineage/corrections. |
| Underengineering | FK existence alone can accept a child record linked to the wrong episode. | Gate dependent features on attribution evidence, not just key existence. |
| Underengineering | Treating missing snapshots as zero activity confounds absence with measured zero. | Report missing dataset separately; basic ingestion is not temporal eligibility. |
| Underengineering | Reporting partial acceptance as full-population success misstates coverage. | Reconcile counts and disclose unresolved/excluded records by level. |
| Underengineering | Ignoring customer grouping/leakage risk can overstate episode model evaluation. | Resolve DD-EP-017 before evaluation/release claims and apply leakage safeguards. |

## 17. Open Questions and Required Follow-up

### Internal product decisions

- Define the intended MVP commercial claim and the exact population eligible for episode-level output.
- Define label, horizon, observation-window and data-coverage requirements before supervised churn modeling (DD-EP-013, DD-003, DD-012/013).
- Define acceptable reporting of unresolved/excluded records and how basic versus temporal workflow intent is expressed (PD-006).
- Resolve DD-EP-016 and version notation before a contract release. Existing statuses remain pending.

### Internal technical decisions

- Determine UUID version, Registry storage/API/transaction/isolation design, operational controls, retention and correction mechanics, all within ADR-010/PD-001–004.
- Design explicit snapshot workflow orchestration and test policy after product approval.
- Define report implementation, safe diagnostics, privacy, record counts, and operational ownership.
- Develop a synthetic test matrix that exercises conflicts, repeat submissions, reactivation, unresolved records, isolation, and partial acceptance without treating fixtures as client facts.

### Client discovery

- Establish source identifiers, namespace, lifecycle event meaning, status values, timezones/cutoffs, snapshot/usage/invoice linkage, and historical coverage using actual client evidence.
- Inventory producers and consumers and their assumptions about ID meaning, required columns, dataset presence, and one-to-many customer/episode relationships.
- Establish whether source/provider limitations create external dependencies.

### Joint decisions

- Agree feasible canonical ID exchange, mapping correction/resubmission, unresolved-record handling, and client-level partial-acceptance consequences.
- Agree the exact MVP dataset availability and compatibility/release plan.
- Define client-specific historical acceptance from evidence; no universal threshold is set.

### Deferred topics

- DD-EP-014/015 customer-level churn and risk remain `DEFERRED`; no customer-level output is in the initial scope.
- Broader usage allocation, invoice allocation, full migration, and advanced operations may be deferred only with the associated capabilities restricted as specified in Section 13.
- DD-EP-017 remains `PENDING_PRODUCT_DECISION`; it is downstream of contract shape but required before robust model evaluation claims.

All referenced decision statuses remain governed by their source registers. This list does not approve or resolve any of them.

## 18. Final Recommendation

**Overall readiness:** `PARTIALLY_READY` for internal MVP design and data-foundation work; `NOT_READY` for formal approval of a revised executable contract, client episode processing without evidence, or implementation beyond separately authorized existing work.

**Recommended MVP boundary:** Build toward a controlled, client-isolated data acceptance path with strict ingestion/normalization/schema checks, explicit basic-versus-temporal availability, Data Quality reporting, and a minimum persistent Registry that meets ADR-010 and PD-001–PD-004. Process only identity-resolved episodes and reliably attributable dependent data. Keep unresolved records visible and excluded. Do not require optional usage/invoices or historical migration for an initial controlled use case; do not use them when attribution is unsupported. Train or score only after labels and evaluation prerequisites are approved and met.

**Finalize next:** (1) obtain client source and consumer evidence; (2) agree source-to-canonical exchange and supported episode evidence; (3) define the explicit PD-006 workflow interface and empty-file behavior; (4) specify what the MVP will exclude; (5) prepare the exact normative contract delta and PD-007 compatibility/version analysis; and (6) obtain formal product/technical approval followed by explicit implementation authorization.

**Can wait:** customer-level churn/risk, comprehensive historical migration, usage/invoice features where not attributable, advanced Registry user workflows, and final DD-EP-017 evaluation strategy for contract changes unrelated to modeling. These deferrals must preserve their restrictions and pending/deferred statuses.

The contract is not approved by this assessment. No contract version is assigned, and no implementation is authorized.
