# Product Decisions and Contract Design Assessment

**Document ID:** NCI-PRODUCT-CONTRACT-DESIGN-001
**Version:** 0.1
**Status:** Draft for product review
**Scope:** Phase 2.4.4.2.1 — Product Decision Inventory
**Assessment date:** 2026-11-15

## 1. Executive Summary

This assessment separates approved subscription-episode architecture from decisions Nowa Analytics can own, facts that require client/source-system evidence, and choices requiring both. It inventories DD-EP-001 through DD-EP-017, identifies product decisions that could proceed independently, describes client discovery needs, and assesses readiness for contract design.

**ALREADY_APPROVED_ARCHITECTURE:** ADR-010 and EP-DEC-001–005 approve episode-level prediction identity, canonical `subscription_id` ownership by Nowa, UUID as the initial generation strategy, persistent identity and reuse, an Episode Identity Registry, no silent resolution of ambiguous matches, reactivation after termination as a new episode, preservation of prior episodes, and a distinct customer/account identity. These decisions are recorded as constraints, not reopened here.

**PRODUCT_DECISION_REQUIRED:** Nowa can define product policy and acceptance criteria such as what evidence is sufficient before creating or reusing a canonical ID, how unresolved identity is surfaced, product-level migration principles, the episode-level churn target, contract compatibility policy, and evaluation objectives. These decisions must stay within ADR-010 and must not pretend to know a client's source behavior.

**CLIENT_DECISION_REQUIRED:** Actual source identifiers, their reuse/stability, namespaces, lifecycle event semantics, and record-level episode linkages require client/source-system discovery. Nowa cannot establish those facts from repository documents.

**JOINT_PRODUCT_CLIENT_DECISION:** A contract field or operational rule often needs both sides: Nowa defines the canonical target and safe acceptance policy; the client establishes whether its source data and business events can satisfy it. This applies especially to lifecycle boundaries, dependent-dataset attribution, and migration acceptance.

The assessment does not approve new product decisions, a new contract version, field requirements, or implementation. Not every unresolved decision blocks every contract design activity; readiness is assessed by design area in Section 9.

## 2. Decision Ownership Framework

Decision ownership describes who can supply the policy or evidence needed to settle a decision. It is separate from implementation status: an approved decision may not be implemented, and an implemented check does not resolve a pending product or client decision.

| Classification | Criteria |
|---|---|
| `APPROVED_PRODUCT_DECISION` | A product policy has already been explicitly approved. Record it as a constraint; do not reopen it through this inventory. |
| `PRODUCT_DECISION_REQUIRED` | Nowa can decide the product policy or acceptance criteria without asserting unverified client facts. Client data may inform feasibility but does not own the product choice. |
| `CLIENT_DECISION_REQUIRED` | Resolution depends on facts or business semantics controlled by a client's source systems or contractual process. Nowa cannot safely infer them. |
| `JOINT_PRODUCT_CLIENT_DECISION` | Nowa must define the product meaning/acceptance rule and the client must provide evidence or agreement that its source/process meets it. Neither side alone can complete the decision. |
| `DEFERRED` | The source decision register intentionally defers the subject outside initial episode-level contractual churn. Preserve that status; do not expand scope here. |
| `ALREADY_APPROVED_ARCHITECTURE` | ADR-010 or an approved EP-DEC has already set the architectural requirement. This is an authority label, not a claim that implementation exists. |

A single decision may contain independently owned parts. Where so, the inventory splits the approved architecture, Nowa-owned policy, client evidence, and any joint contract choice rather than forcing one owner label onto all parts. Source status is reported separately and preserved exactly.

## 3. Existing Approved Decisions

The following are **ALREADY_APPROVED_ARCHITECTURE** constraints from ADR-010 and the approved Subscription Episode & Lifecycle Decision Specification v0.4:

- Nowa Analytics owns canonical episode identity. `subscription_id` identifies exactly one contractual episode, is stable throughout its lifecycle, and is never reassigned.
- UUID is the approved initial canonical ID generation strategy. Generate it once when a new episode is authoritatively established, persist it, and reuse it across subsequent CSV submissions and ingestion executions.
- A persistent Episode Identity Registry is required. It must support verified source-to-canonical associations, repeat-submission recognition, client isolation, and historical mapping lineage.
- Ambiguous identity matches must not be silently resolved. Date proximity, status, row order, or heuristic similarity is not proof of identity.
- One contractual episode is the prediction entity. A customer may have multiple episodes.
- Reactivation following termination creates a new episode; prior episodes remain historically preserved.
- `customer_id` remains the customer/account identity and is distinct from the canonical episode identity.

ADR-010 approves architecture but not implementation. UUID version, Registry schema/storage/APIs, operational ownership, conflict and correction workflows, retention/deletion, source namespace representation, and exact CSV exchange mechanics remain open. These details must not be presented as already approved.

## 4. Product Decision Inventory

“Source status” below is copied from the current Episode Specification §11. Ownership classification is this assessment's recommendation and does not change that status.

| Decision | Current source status | Recommended ownership classification | Nowa can decide independently | Client/source evidence required | Unresolved scope and impact | Recommended next action |
|---|---|---|---|---|---|---|
| DD-EP-001 — Contractual episode boundary | `PENDING_CLIENT_DECISION` | `JOINT_PRODUCT_CLIENT_DECISION` | Define the product concept of a canonical episode and require a reproducible event basis. | Contract terms, source event meanings/timing, and treatment of corrections. | Exact episode start/end boundary; affects subscription row meaning, lifecycle fields, TC rules, migration, and labels. | Discover source lifecycle events, then approve one product interpretation that can be evidenced for the client. |
| DD-EP-002 — Source subscription ID availability and reuse | `PENDING_CLIENT_DECISION` | `CLIENT_DECISION_REQUIRED` for facts; separate product decision for mapping acceptance | Define that source IDs are provenance and are not presumed episode-unique. | Which identifiers exist, reuse/reassignment behavior, stability, history retention, and availability in each dataset. | Whether a source key can identify an episode or support repeat-submission matching; affects fields, Registry mappings, ingestion, and migration. | Inventory identifiers per source and dataset; do not mandate `source_subscription_id` before discovery. |
| DD-EP-003 — Internal Episode ID and Registry details | `PENDING_PRODUCT_DECISION` (partially resolved by ADR-010 and PD-001) | Split: `ALREADY_APPROVED_ARCHITECTURE`, approved PD-001 product-level Registry functional requirements, plus remaining `PRODUCT_DECISION_REQUIRED` and `JOINT_PRODUCT_CLIENT_DECISION` | PD-001 Option B is approved: require conflict detection, visibility of unresolved identity, traceable mapping corrections, auditable identity/mapping history, and preservation of prior mapping lineage. Define remaining issuance, operational, and client-dependent requirements without choosing unapproved technology or workflows. | Source keys/mapping evidence and the client submission process needed to make recognition reliable. | UUID version, storage/API/transaction design, owner/operator, detailed conflict/correction workflows, retention/deletion, source namespace representation, CSV identity exchange, and how sources link to canonical IDs; affects Registry, CSV, ingestion, migration, and security. | Preserve ADR-010 and approved PD-001 requirements; keep remaining design and client-evidence questions open. Do not reopen approved decisions. |
| DD-EP-004 — Source-system namespace | `PENDING_CLIENT_DECISION` | `JOINT_PRODUCT_CLIENT_DECISION` | Define client isolation and require namespace to remain separate from canonical UUIDs. | Systems, tenants/partitions, identifier collision domains, and source metadata availability. | Whether namespace is needed and whether it belongs in a CSV, mapping context, or both; affects Registry keys and possible contract fields. | Complete source topology discovery, then choose the minimum product representation needed for safe mapping. |
| DD-EP-005 — Cancellation event semantics | `PENDING_CLIENT_DECISION` | `JOINT_PRODUCT_CLIENT_DECISION` | Define how product churn policy consumes a verified effective event; do not equate labels/statuses without policy. | Source cancellation request/effective dates, termination events, reversals, and contractual evidence. | Meaning and relation of `cancellation_date`, `end_date`, status, and reason; affects episode boundary, DQ chronology, migration, and churn labels. | Map client events and have Product approve the canonical semantic mapping. |
| DD-EP-006 — Renewal and contract extension | `PENDING_CLIENT_DECISION` | `JOINT_PRODUCT_CLIENT_DECISION` | Define product-level distinction required between continuation and a new episode once source facts are known. | Renewal/extension terms, source identifiers, and historical representation. | Whether a renewal changes the current episode or establishes a new episode; affects identity, contract rows, snapshots, and labels. | Obtain contract/source examples; decide only after comparison with approved episode concept. |
| DD-EP-007 — Suspension and pause | `PENDING_CLIENT_DECISION` | `JOINT_PRODUCT_CLIENT_DECISION` | Define product treatment for churn/episode continuity after understanding the events. | Meaning and timing of paused/suspended statuses and service/contract state. | Whether pause/suspension ends, preserves, or changes an episode and how it affects label eligibility; affects status mapping, lifecycle, and modeling. | Discover events/status transitions and approve a product mapping; do not infer from status names. |
| DD-EP-008 — Snapshot-to-episode attribution | `PENDING_CLIENT_DECISION` | `JOINT_PRODUCT_CLIENT_DECISION` | Set evidence and acceptance requirements; prohibit heuristic assignment. | Whether snapshots carry stable episode IDs or auditable crosswalk keys over history. | Attribution of legacy/current snapshots and start-date association; affects FK contract semantics, Registry, RI limitations, TC-003, and migration. | Test source lineage on representative history; leave unsupported rows unresolved. |
| DD-EP-009 — Usage-to-episode attribution | `PENDING_CLIENT_DECISION` | `JOINT_PRODUCT_CLIENT_DECISION` | Define acceptable episode-level usage meaning and evidence threshold. | Usage keys, aggregation grain, covered service interval, and linkage to episodes. | Whether each usage row measures one episode; affects usage FK semantics, Registry/mapping, and TC-007. | Establish source grain/lineage and approve contract interpretation together. |
| DD-EP-010 — Usage periods crossing episode boundaries | `PENDING_PRODUCT_DECISION` | `JOINT_PRODUCT_CLIENT_DECISION` | Choose product treatment (for example, eligibility/exclusion or an approved allocation policy) only after understanding the period model. | Period start/end, partial-period availability, attribution evidence, and client billing/usage process. | Boundary inclusion and split/allocation policy; affects usage contract, DQ, and downstream features. | First resolve DD-EP-009 and obtain period semantics; then make an explicit product policy with client agreement. |
| DD-EP-011 — Invoice-to-episode attribution | `PENDING_CLIENT_DECISION` | `JOINT_PRODUCT_CLIENT_DECISION` | Define evidence needed for an episode FK and prohibit date-only allocation. | Invoice linkage, service period, credit/reissue behavior, and whether invoices can cover multiple episodes. | Historical and multi-episode invoice attribution; affects optional invoice contract, mapping, RI interpretation, and financial features. | Trace invoice references/lineage with client finance/source owners; agree on supported contract granularity. |
| DD-EP-012 — Historical migration acceptance | `PENDING_PRODUCT_DECISION` | `JOINT_PRODUCT_CLIENT_DECISION` | Define product acceptance principles and allowed dispositions for unresolved identity. | Actual coverage, source crosswalks, unresolved-row volume, and impact on the client's intended use. | Reject/quarantine/review/exclusion criteria and model eligibility; affects migration and onboarding. | Agree criteria from an evidence-based client inventory; do not fabricate historical identity. |
| DD-EP-013 — Episode-level churn qualification | `PENDING_PRODUCT_DECISION` | `JOINT_PRODUCT_CLIENT_DECISION` | Own the canonical product label definition and observation/horizon policy. | Client contract events and source evidence that can operationalize the label. | Which event qualifies, when it becomes effective, and applicable exclusions; affects labels and modeling, not just CSV fields. | Product drafts the outcome rule; client validates event mapping and contractual interpretation. |
| DD-EP-014 — Customer-level churn, if included | `DEFERRED` | `DEFERRED` | No decision in the initial scope. | None for this phase. | Intentionally outside the initial episode-level contractual churn scope. | Preserve deferred status; revisit only through separately approved scope. |
| DD-EP-015 — Customer-level risk aggregation | `DEFERRED` | `DEFERRED` | No aggregation policy in the initial scope. | None for this phase. | Intentionally outside the initial episode-level contractual churn scope. | Preserve deferred status; do not add contract or implementation requirements here. |
| DD-EP-016 — Contract version and backward compatibility | `PENDING_PRODUCT_DECISION` | `JOINT_PRODUCT_CLIENT_DECISION` | Apply v1.1 versioning rules, decide product release/compatibility policy, and define supported transition principles. | Client field/key usage, consumer behavior, onboarding capacity, and migration impact. | Final version, dual-version/transition support, deprecation and compatibility plan; affects contract, templates, validators, and migration. | Enumerate the approved delta and client impact before setting a version. |
| DD-EP-017 — Model Evaluation Grouping and Temporal Strategy | `PENDING_PRODUCT_DECISION` | `PRODUCT_DECISION_REQUIRED` (client evidence informs feasibility) | Define evaluation objectives, estimands, leakage controls, and acceptable evidence for model comparison. | Episode history, dates, customer grouping availability, and the number/relationship of episodes in actual data. | Temporal strategy and whether/how customer grouping is used. This is downstream modelling/evaluation, not an immediate CSV structure decision. | Assess evaluation objectives and synthetic/approved data structure; do not prescribe a final split here. |

### 4.1 Ownership notes for split decisions

- DD-EP-003's canonical ownership, UUID initial strategy, Registry requirement, and PD-001 functional requirements are approved constraints; DD-EP-003 remains open for its unresolved details and evidence.
- For DD-EP-012 and DD-EP-016, Nowa owns product acceptance/version policy, but client-specific compatibility and evidence are necessary to choose a safe transition.
- DD-EP-017 is a Nowa modeling-policy decision informed by observed data feasibility. It need not block contract changes that do not affect modeling or evaluation.
- DD-EP-014/015 remain `DEFERRED`, not open invitations to add customer-level targets or aggregation requirements.

## 5. Candidate Product Decisions

The PD-001 Registry functional-requirements recommendation below was subsequently approved as recorded in `docs/04_data/product_decision_proposals.md`. Other recommendations in this section remain **PROPOSED — NOT APPROVED**. Approved architecture cited in an item remains binding and is not being re-decided. “Options” describe decision space, not approved behavior.

### 5.1 Registry functional acceptance criteria

**Problem:** ADR-010 states Registry responsibilities, but operational acceptance criteria and failure behavior are not fully specified.

**Options:** (a) Keep only the approved functional boundary and defer detailed workflows; (b) specify product acceptance criteria for verified mappings, repeat recognition, history, client isolation, and ambiguity surfacing before choosing technology; (c) expand into a fully specified Registry service design now.

**Trade-offs:** (a) avoids premature design but leaves implementation acceptance vague; (b) clarifies product outcomes without locking implementation; (c) risks deciding storage/API/operations before evidence and authorization.

**Recommendation and status:** Option (b) was approved as PD-001 on 2026-11-15, limited to product-level functional outcomes consistent with ADR-010. The Registry must support conflict detection, visibility of unresolved identity, traceable mapping corrections, auditable identity/mapping history, and preservation of previous mapping lineage. Do not revisit the Registry requirement or infer approval of storage, APIs, UUID version, detailed workflows, or deployment design.

**Consequences/dependencies:** Enables later contract and implementation acceptance criteria; detailed workflows depend on DD-002/004 and separate product authorization. The approval does not authorize implementation.

### 5.2 Canonical ID issuance boundary

**Problem:** ADR-010 requires one-time UUID generation after a new episode is authoritatively established, but “authoritatively established” and the interface workflow are not fully defined.

**Options:** (a) Only accept a canonical ID already carried by an approved source/mapping; (b) Nowa issues after a verified source key or approved evidence identifies a new episode; (c) issue on every newly seen row and reconcile later.

**Trade-offs:** (a) depends on source capability; (b) aligns with Nowa ownership but needs evidence and persistent mapping; (c) is simple but can create duplicate identities and conflicts with stable recognition.

**Recommendation:** Preserve the approved one-time/stable ID lifecycle and require authoritative episode recognition before issuance. Do not treat row novelty as evidence. Exact source/mapping mechanics remain open.

**Consequences/dependencies:** Affects subscriptions and dependent-key handling, Registry, repeated ingestion, and migration. Depends on DD-001/002/003/004. **Approval status: PROPOSED — NOT APPROVED.**

### 5.3 Ambiguous identity disposition

**Problem:** ADR-010 forbids silent resolution and requires ambiguity to be surfaced; final operational disposition is open.

**Options:** (a) Reject affected submission/records; (b) hold unresolved records for client-assisted or authorized review; (c) accept only an explicitly approved subset with documented exclusions.

**Trade-offs:** Rejection is conservative but may block useful data; review preserves potential coverage but requires a controlled workflow; exclusion can preserve other records but can affect representativeness and model eligibility.

**Recommendation:** Product should choose an explicit fail/hold/exclusion policy based on safety and intended use, and require clear unresolved-state reporting. No option is approved here.

**Consequences/dependencies:** Affects Registry, ingestion, client onboarding, migration and availability. Depends on DD-003, DD-008–012. **Approval status: PROPOSED — NOT APPROVED.**

### 5.4 Repeated CSV submissions

**Problem:** ADR-010 requires reusing a canonical ID on later submissions, but exact duplicate, correction, omission, and late-arriving record behavior is open.

**Options:** (a) Treat an exact repeat as idempotent and reuse identity; (b) require a client-provided canonical ID/mapping each time; (c) treat each submission as a new snapshot of data but use a separately approved persistent mapping.

**Trade-offs:** Idempotence supports stable history but needs a reliable recognition key and persistent state; requiring supplied IDs shifts operational burden to clients; treating a file as a new snapshot alone does not identify episodes.

**Recommendation:** Do not mint a replacement ID simply because a CSV was reimported (already approved). Define duplicate/correction semantics only after identifiers and source evidence are understood.

**Consequences/dependencies:** Affects Registry and ingestion, not just contract fields. Depends on DD-002/003/004 and client correction practices. **Approval status: PROPOSED — NOT APPROVED.**

### 5.5 Migration acceptance principles

**Problem:** Existing v1.1 keys may not distinguish episodes or persist across submissions.

**Options:** (a) Migrate only rows with authoritative episode identity; (b) accept mapped subsets and explicitly exclude unresolved history if use-case policy allows; (c) reject a dataset/client migration when ambiguity exceeds an approved limit.

**Trade-offs:** Strict acceptance protects identity correctness but may reduce usable history; subset acceptance preserves attributable data but may bias coverage; thresholds/limits are unsupported without product and client evidence.

**Recommendation:** Require lineage, preserve old values, and never fabricate attribution (consistent with approved architecture/specification). Decide actual acceptance criteria jointly after profiling client history.

**Consequences/dependencies:** Affects client onboarding, Registry, migration and model eligibility. Depends on DD-002, DD-008–012. **Approval status: PROPOSED — NOT APPROVED.**

### 5.6 Episode-level churn scope

**Problem:** The episode is approved as prediction entity, but DD-EP-013 leaves event qualification and label timing unsettled.

**Options:** (a) Define one Nowa product outcome and map client events to it; (b) permit client-specific outcome definitions under a governed product taxonomy; (c) defer model labels until event semantics are verified.

**Trade-offs:** A common outcome improves comparability but may not fit contractual differences; client-specific mapping improves fidelity but limits cross-client comparability; deferral protects correctness but delays modeling.

**Recommendation:** Keep the prediction entity episode-level (approved). Product should own the canonical outcome definition, with client evidence used to validate event mapping; do not claim a final churn event rule now.

**Consequences/dependencies:** Affects labels, DQ temporal meaning, and modeling more than CSV structure. Depends on DD-001/005/006/007/013. **Approval status: PROPOSED — NOT APPROVED.**

### 5.7 Contract versioning and compatibility principles

**Problem:** v1.1 requires use of its versioning policy, while exact compatibility effects depend on the final field/key delta.

**Options:** (a) Support only a new major contract after migration; (b) temporarily support old and new versions; (c) use backward-compatible additions where possible and separately version breaking semantics.

**Trade-offs:** A single major path is simpler but may force synchronized client changes; dual support eases transition but creates code and support burden; incremental optional fields can ease adoption but strict v1.1 consumers reject unknown columns.

**Recommendation:** Apply the existing major/minor/patch policy to the actual delta. Identify client/consumer compatibility first, and do not assign a version before DD-EP-016 is resolved.

**Consequences/dependencies:** Affects headers, schemas, onboarding, migration, and release support. Depends on final contract proposal and client impact evidence. **Approval status: PROPOSED — NOT APPROVED.**

### 5.8 Customer versus episode prediction

**Problem:** Avoid confusing customer identity/aggregation with the prediction entity.

**Options:** (a) Preserve episode-level prediction and defer customer-level target/aggregation; (b) add customer-level prediction as a parallel initial target; (c) change the initial target to customer-level.

**Trade-offs:** Options (b)/(c) expand or contradict the current approved scope and reopen deferred decisions. Option (a) preserves ADR-009 and the approved episode clarification.

**Recommendation:** No new decision is needed for the initial prediction entity: retain the approved episode-level prediction unit and preserve DD-EP-014/015 as `DEFERRED`. ADR-009's existing `customer_id` feature restriction also remains unchanged; this assessment introduces no new feature policy.

**Consequences/dependencies:** Maintains current model grain and customer/account distinction. Any scope expansion requires separate product approval. **Existing episode-level boundary:** `ALREADY_APPROVED_ARCHITECTURE`. **Potential future customer-level extension:** PROPOSED — NOT APPROVED; it is not part of the initial scope and would require separately reopening deferred decisions.

### 5.9 Evaluation principles for multiple episodes per customer

**Problem:** DD-EP-017 requires a temporal evaluation strategy and consideration of customer grouping to assess leakage across episodes from one customer.

**Options:** (a) Episode-level temporal evaluation without customer grouping; (b) customer-grouped evaluation; (c) temporal and customer-group-aware evaluation; (d) report distinct estimands/metrics for future-episode prediction versus unseen-customer generalization.

**Trade-offs:** Temporal ordering reflects deployment time but can place a customer's episodes on both sides of a split; customer grouping reduces cross-episode leakage but may test generalization to unseen customers rather than future episodes for known customers; combined methods depend on data volume and objective; multiple estimands can improve transparency but require deliberate analysis.

**Recommendation:** Do not select a split strategy from current repository evidence. First state the deployment/evaluation question, inspect episode/customer history, and test for leakage. This is downstream modelling work, not a prerequisite for every CSV contract change.

**Consequences/dependencies:** Affects model evaluation protocol and interpretation, not immediate CSV structure. Depends on DD-017 and suitable episode/customer history. **Approval status: PROPOSED — NOT APPROVED.**

## 6. Client-Dependent Decisions

The following facts must be established separately for each client and source system. None can be inferred from the product architecture or synthetic repository tests.

| Discovery area | Evidence to obtain | Why Nowa cannot decide without it | Related decisions |
|---|---|---|---|
| Source identifiers and stability/reuse | Data dictionary, source key definitions, historical examples across reactivation, merge/correction, and repeated exports | Determines whether a key is subscription-level, episode-level, stable, reused, or absent. | DD-002/003 |
| Source-system namespaces and tenant boundaries | System inventory, tenant/account partitions, uniqueness guarantees, duplicate-key behavior across sources | Namespace requirements depend on real collision scope; ADR-010 does not prescribe a namespace field. | DD-004 |
| Contractual lifecycle and termination events | Client contract terms, source event definitions, effective and recorded timestamps | A product cannot infer when an episode starts/ends or termination becomes effective from column names/status alone. | DD-001/005 |
| Renewal, extension, suspension, pause, reactivation semantics | Business workflow, amendments/renewals, status/event history, service availability semantics | Determines whether current relationship continues or new episode begins and what statuses signify. | DD-005/006/007 |
| Snapshot attribution | Snapshot source keys/crosswalk, historical extract coverage, event/recording lineage | Date/status similarity is not proof that a historical row belongs to an episode. | DD-008 |
| Usage attribution and periods | Usage grain, source keys, period boundaries, partial-month availability and episode linkage | Needed to know what episode/period a row measures and whether it spans episodes. | DD-009/010 |
| Invoice attribution | Invoice-level and line/service-period linkage, credits/reissues, multi-episode coverage | Dates alone cannot establish episode allocation; finance semantics may differ. | DD-011 |
| Historical availability and lineage | Closed episode retention, backfills, event history, mapping/crosswalk availability | Determines which history can be migrated without invented identity. | DD-008–012 |
| Status/event mapping | Source status dictionary, transition meanings, event timing and reversals | Canonical labels require evidence; identical status text may not imply identical contractual events. | DD-005–007/013 |

Use privacy-approved, representative client evidence. A source-system capability remains unverified until documented for that client; one client's evidence must not be generalized to others without a product rule supporting it.

## 7. Joint Decisions

Joint decisions combine Nowa's product responsibility with client-owned facts or agreement:

| Joint area | Nowa Analytics responsibility | Client responsibility | Required joint outcome |
|---|---|---|---|
| Episode boundary and lifecycle mapping | Define canonical episode semantics and acceptable evidence; preserve approved reactivation rule. | Supply contractual/source event meanings and examples. | A boundary that is product-consistent and demonstrably represented in the client data. |
| Canonical ID mapping and Registry use | Own canonical identity, Registry controls, isolation and ambiguity policy. | Provide stable source identifiers/crosswalks and confirm source reuse/namespace behavior. | An approved mapping/input process that can support persistence and repeat recognition. |
| Snapshot, usage, invoice attribution | Define target FK meaning and evidence threshold; prohibit heuristics. | Show which source records link to which episodes and where historical links are missing. | Dataset-specific attribution coverage and explicit unresolved-record handling. |
| Churn qualification | Define the product target, prediction horizon and canonical outcome semantics. | Validate event mapping against actual contractual workflows and source timing. | A label definition that is valid for product use and grounded in client evidence. |
| Migration acceptance | Define acceptable quality, preservation and exclusion policy. | Provide history/crosswalk and quantify affected/unresolved data. | A documented decision on accepted, excluded, or unresolved records and resulting use limits. |
| Contract/version compatibility | Own contract policy, release support and version decision under v1.1 Section 12. | Identify consumers, export changes, operational transition constraints and data impact. | A compatible, supportable version transition based on the actual delta. |

## 8. Proposed Decision Sequence

This sequence is dependency-aware but not a single mandatory gate. Evidence gathering can proceed in parallel across source datasets.

1. **Preserve the baseline:** Treat ADR-010 and EP-DEC-001–005 as fixed architecture. Correctly distinguish stale v1.1 DD-004/DD-006 wording from the newer approved episode decision; do not amend source documents in this assessment.
2. **Parallel client discovery:** Investigate IDs/namespaces (DD-002/004), lifecycle and cancellation/renewal/pause events (DD-001/005–007), and dependent data linkage (DD-008–011). These evidence streams can proceed together.
3. **Nowa product policy in parallel:** Define proposed Registry acceptance criteria, ambiguity disposition options, churn outcome objective, compatibility principles, and migration acceptance principles without selecting unverified source fields or implementation technologies.
4. **Joint mapping decisions:** Combine evidence with Nowa policy for source-to-canonical ID exchange, record attribution, period semantics, and migration eligibility. DD-010 depends on usage-period and attribution findings; DD-012 depends on historical linkage evidence.
5. **Contract delta and version review:** Specify only fields and semantics supportable by the resolved decisions. Assess strict-header/consumer compatibility and schema/key impact; resolve DD-016 before assigning a contract version.
6. **Downstream modeling/evaluation:** Address DD-017 when the episode/customer history and model evaluation objective are available. It can proceed alongside contract work and is not a prerequisite for changes that do not affect modeling/evaluation.
7. **Implementation planning:** Prepare separately authorized schema, header, normalization, Registry, migration, and test work packages. Do not treat this decision inventory as implementation approval.

DD-013 depends on agreed lifecycle event meaning (especially DD-005) and client event mapping. DD-014/015 remain deferred. Snapshot conventions and other existing contract decisions remain governed by their own registers.

## 9. Contract Design Readiness

| Design area | Readiness | Evidence and remaining work |
|---|---|---|
| Target dataset structure | `PARTIALLY_READY` | Episode-level prediction entity, customer distinction, and one canonical identity per episode are approved. Exact lifecycle field semantics and how legacy source rows map to episode grain remain unresolved. A conceptual structure can be drafted; final normative rows/fields cannot. |
| Canonical and source identifier fields | `PARTIALLY_READY` | Canonical `subscription_id` ownership/UUID strategy is approved. Source ID concepts must remain separate, but field availability, requiredness, namespace, UUID details, and client-facing exchange process are undecided. Do not require `source_subscription_id` now. |
| CSV input/output responsibilities | `NOT_READY` | The contract is CSV-based, but it is undecided whether clients submit canonical IDs, source IDs plus mapping context, or an approved mapping artifact/process. Strict current headers and ingestion behavior require a compatibility design. |
| Registry integration boundary | `PARTIALLY_READY` | ADR-010 approves Registry need and functional responsibilities. Schema, persistence, APIs, operation, interface to CSV ingestion, transaction/idempotency and ambiguity workflow remain open. |
| Migration and compatibility rules | `NOT_READY` | No client source evidence, historical crosswalk, acceptance criteria or transition plan is present. DD-EP-012 and DD-EP-016 remain open. |

“Partially ready” means product architecture can constrain a design exploration; it does not authorize a final contract or implementation.

## 10. Explicit Boundaries

This document:

- Does not modify Customer Data Contract v1.1 or approve a new contract version.
- Does not authorize schema, Registry, ingestion, normalization, validator, migration, or other code implementation.
- Does not resolve client-dependent decisions without source evidence and appropriate client agreement.
- Does not reopen or reinterpret approved ADR-010 or EP-DEC architectural decisions.
- Does not change decision statuses, including `DEFERRED` DD-EP-014/015 or `PENDING_PRODUCT_DECISION` DD-EP-017.
- Does not prescribe an evaluation split strategy or source-system behavior.

## 11. Source inconsistencies and stale information

1. **Customer Data Contract v1.1 versus approved episode decisions:** Contract Sections 13 DD-004/DD-006 still describe reactivation/new-episode treatment as open and describe one row per subscription. The later approved EP-DEC-005 and ADR-010 establish that reactivation following termination creates a new episode with a new canonical identity. The contract needs later reconciliation; this assessment does not silently edit it.
2. **Canonical `subscription_id` semantics:** v1.1 says “unique subscription identifier” and uses it for dependent references. ADR-010 defines canonical episode identity, ownership, UUID strategy, stable reuse and Registry responsibilities. The contract does not yet define how submitted source identifiers resolve to that canonical field.
3. **Older assessment wording:** The earlier episode impact and identifier assessments contain recommendations/pending statements written before ADR-010 approved ownership, UUID as initial strategy, and the Registry requirement. Those older statements are not authority to reopen ADR-010; remaining detail is still pending.
4. **Data Quality documents:** The current Data Quality Specification and Implementation Architecture now reflect RI-001–RI-004 and TC-001/TC-002 implementation and state that existence validation does not prove correct episode attribution. The RI/TC code similarly provides only reference existence/date comparisons, not episode identity resolution.
5. **Snapshot requiredness:** The contract says snapshots are required for temporal modelling; current ingestion requires snapshots unconditionally. The basic-validation versus temporal-modeling requirement remains unresolved and must not be attributed to episode identity alone.
6. **Version notation:** Contract Section 12 presents a `1.1.0 → 1.1.1` patch example while the contract metadata uses `1.1`. DD-EP-016 should clarify release notation; this assessment does not normalize it.

## 12. References

- `docs/03_architecture/architecture_decisions.md` — accepted ADR-009 and client isolation ADR-003.
- `docs/03_architecture/adr_episode_identity_and_identifier_management.md` — ADR-010, accepted canonical identity/UUID/Registry architecture and implementation boundary.
- `docs/04_data/subscription_episode_lifecycle_decision_specification.md` — EP-DEC-001–005 and DD-EP-001–017, especially Sections 9–14.
- `docs/04_data/customer_data_contract.md` — v1.1, especially Sections 2, 4–7, 12–14.
- `docs/04_data/customer_data_contract_episode_alignment_proposal.md` — Phase 2.4.4.1 contract-impact/version assessment.
- `docs/04_data/subscription_episode_data_contract_impact_assessment.md`.
- `docs/04_data/subscription_episode_identity_identifier_strategy_assessment.md`.
- `docs/04_data/data_quality_specification.md` and `docs/04_data/data_quality_implementation_architecture.md`.
- Current implementation checked where relevant: five schemas, header inspection, CSV ingestion, type normalization, RI/TC validators and their unit/integration tests.

---

**Review status:** Draft product decision inventory. It does not approve new product policy or authorize implementation.
