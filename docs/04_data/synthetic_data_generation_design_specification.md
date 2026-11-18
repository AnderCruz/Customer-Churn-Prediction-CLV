# Synthetic Data Generation Design Specification

**Document ID:** NCI-SYNTH-DESIGN-001
**Version:** 0.1
**Status:** Approved for Design Baseline
**Project:** Nowa Customer Intelligence
**Market:** Great Britain (GB)
**Scope:** Consolidated design and implementation plan for synthetic customer, subscription, event, billing, usage, snapshot, and ground-truth data. This document authorises no implementation.

## 1. Purpose, authority, and boundaries

This document consolidates Block A (architecture), Block B (generation rules), Block C (ground truth and data quality), and Block D reproducibility/provenance into one execution-oriented design. The source Block A–C documents are v0.1 and Approved for Design Baseline. Their reviewed content governs the corresponding areas of this design. The Synthetic Business Model Specification v0.2 is Approved. Customer Data Contract v1.1 is Approved for Implementation. Neither approval authorises implementation of the synthetic generator or production churn policy.

The authoritative NEDS v1.1 project reference was reviewed; it is not stored in this repository. Phase 3.3.1 was reviewed from the supplied project attachment and is likewise not in the repository. This design assesses alignment with the available reference contents, not implementation compliance. The repository contains Python pipeline and validation code; this document distinguishes those current capabilities from proposed generator capabilities.

Governing references include [Block A](synthetic_data_generation_architecture.md), [Block B](synthetic_data_generation_rules.md), [Block C](synthetic_churn_ground_truth_and_data_quality.md), [reproducibility and provenance](synthetic_generation_reproducibility_and_provenance.md), [business model specification](synthetic_business_model_specification.md), [Customer Data Contract](customer_data_contract.md), [episode identity ADR](../03_architecture/adr_episode_identity_and_identifier_management.md), product decisions, lifecycle decision specification, and the existing data quality/pipeline implementation. Where proposals conflict with an approved decision, the approved decision governs. Open decisions remain open.

The design preserves the distinctions among contract validation, referential integrity, semantic episode attribution, temporal correctness, and model eligibility. Passing one does not imply passing another.

### 1.1 Executive technical overview

The intended system creates synthetic-only GB B2B SaaS data to exercise customer intelligence, data-quality, and future modelling workflows. The baseline population assumptions carried forward from Phase 3.3.1 are approximately 1,000 customer accounts, 1,100–1,400 subscription episodes, and a 36-month synthetic history; these are scenario inputs, not market-calibrated estimates. Outputs project only to the five unchanged Customer Data Contract datasets. Internal synthetic outcome truth, identity mappings, manifests, and negative test fixtures remain separate: negative fixtures are isolated test inputs and never part of a valid generated dataset. The existing pipeline can provide contract/schema, referential-integrity, and limited temporal validation integration; synthetic generation, semantic attribution, complete temporal/outcome validation, and publication control are future capabilities.

## 2. Design principles and preserved decisions

- Use the Block A local, sequential modular-monolith design and its component boundaries. Do not add infrastructure without an approved need.
- Generate only from explicit, validated, versioned configuration and named random streams. Synthetic assumptions are hypotheses, not estimates of GB market distributions.
- Treat a subscription episode as the prediction entity; `customer_id` is context and is not a model feature. Reactivation after termination is a new episode; preserve separate episode outcomes.
- UUID is the approved initial identity direction; ADR-010 requires a persistent, client-isolated Episode Identity Registry for durable identity reuse. UUID version/provider, allocation method, and synthetic replay details remain open.
- Preserve Block B's approved catalogue and business assumptions. Snapshot convention, period boundaries, cut-offs, target qualification, and production churn semantics remain unresolved as recorded in the decision register.
- Keep ground truth and any internal identity mapping separate from the public Customer Data Contract projection. Do not add contract columns or expose truth labels, private identifiers, or internal artefacts in public datasets.
- Do not silently repair, reclassify, impute, drop, or quarantine invalid records. A validator reports or rejects according to approved behaviour; correction policy needs separate approval.
- No generator, configuration file, manifest schema, data set, or new test is created by this design.

## 3. Logical architecture and component responsibilities

The design retains the Block A components and boundaries; the table describes intended responsibility and status, not new module names or infrastructure.

| Component | Responsibility and inputs/outputs | Current state / dependency |
|---|---|---|
| Run configuration | Parse scenario, overrides, dates, population targets, and seed; resolve a validated immutable effective configuration before draws or outputs. | Design only. Defaults, schema, snapshot and temporal policies need decisions. |
| Run context and provenance | Track run identity, effective-config fingerprint, code/environment references, stage status, and output inventory. | Design only; physical manifest and persistence not selected. See [reproducibility design](synthetic_generation_reproducibility_and_provenance.md). |
| Random stream plan | Derive isolated, versioned component streams from the master seed; component draw order is deterministic. | Design only; RNG algorithm and exact derivation remain implementation choices. |
| Customer generator | Produce synthetic customer profiles and stable within-run customer identifiers from the approved population assumptions. | Design only; population targets from Phase 3.3.1 guide scope, not external market calibration. |
| Episode identity and lifecycle | Create episode identities and lifecycle states/events, preserving customer-to-many-episodes relationships and reactivation history. | UUID direction and Registry requirement approved; identifier implementation and lifecycle semantics have open dependencies. |
| Billing and invoice generator | Generate billing periods, invoices, amounts, and payment states consistently with episode state and the approved business catalogue. | Design only; billing anchor/boundary and detailed timing choices remain open. |
| Usage generator | Generate usage within the applicable episode and usage periods, with approved business limits and reproducible component draws. | Design only; usage period boundaries remain open. |
| Snapshot builder | Represent configured observation states using approved snapshot conventions; snapshots are optional in BASIC and required in TEMPORAL mode per approved product decision. | Design only; convention and snapshot timing remain open. |
| Internal truth builder | Represent synthetic hypothesis events, effective/availability times, ascertainment, censoring, and eligibility separately from contract projection. | Design only; target qualification and production churn policy are not approved. Secure storage details remain open. |
| Contract projection | Project supported fields into the exact Customer Data Contract without internal truth or unapproved columns. | Design only. Contract and schema validation implementations exist separately. |
| Validation and reporting | Run schema/contract validation, referential checks, temporal checks, semantic attribution, outcome checks, and eligibility checks as distinct gates; report errors and warnings. | Some generic/relational/limited temporal checks exist; semantic attribution/outcome gates are not implemented. |
| Run coordinator and publisher | Execute stages in dependency order, record results against the declared scope and publish the eligible output set only with explicit authorisation. | The existing pipeline coordinator handles source ingestion and validation. Synthetic generation and publication remain at design stage. |

### 3.1 Execution flow and failure behaviour

1. **Load and validate configuration — designed, not implemented.** Resolve the scenario, seed and policy versions. Declare the execution and acceptance scope and its required gates before generation. Invalid configuration fails before random draws or data output.
2. **Establish run context and random streams — designed, not implemented.** Record provenance and initialise named streams.
3. **Generate customers — designed, not implemented; conditional on approved configuration.**
4. **Generate canonical subscription episodes — blocked in part by identity decisions.** UUID direction is approved, but UUID version/provider and replay/allocation details remain open.
5. **Generate lifecycle and commercial events — blocked by open lifecycle/event decisions.**
6. **Generate billing and invoice facts — blocked in part by billing period decisions.**
7. **Generate usage and snapshot facts — conditional on approved configuration; temporal correctness blocked by open period/snapshot policies.**
8. **Generate internal synthetic outcome truth — designed but not implemented; production target use blocked.** Keep truth separate from public outputs. The internal five-state outcome representation can be designed without approving production churn policy.
9. **Project the five approved contract datasets — designed, not implemented.**
10. **Validate contract and referential integrity — existing capabilities available, but generator integration is not implemented.** Existing RI proves key existence only.
11. **Validate semantic episode attribution — designed, not implemented.**
12. **Validate temporal correctness — existing checks are limited; complete policy and gates are blocked by open decisions.**
13. **Validate outcome and eligibility rules — designed, not implemented; target, ascertainment, censoring and eligibility decisions remain open.**
14. **Generate provenance and validation summary — designed, not implemented.**
15. **Determine publication eligibility — designed, not implemented; publication policy and storage lifecycle are unresolved.**

A failed prerequisite stops dependent stages. Record the failure reason and skipped stage outcomes. A required gate without a successful evaluation prevents acceptance and publication eligibility for its declared scope under Section 5.4. Validators report or reject according to their approved behaviour. Automatic correction, reclassification, imputation, dropping or quarantine would require separate policy approval. Retention of partial diagnostic outputs remains an open operational decision.

Logging is required for generation stage transitions, validation results, and failures, with run correlation and sanitised error context. Never log secret values, internal truth rows, or sensitive identifier mappings. Internal ground-truth and registry artifacts require least-privilege access, separation from model inputs/public outputs, controlled retention and cleanup, and auditable access; access roles, storage format and operational controls remain open. Future tests have distinct responsibilities: unit tests for component rules and deterministic stream isolation; integration tests for stage boundaries, joins, contract projection, and failure propagation; end-to-end tests for complete configured runs, provenance, reproducibility claims, and publication gates. None is claimed to exist for the generator.

## 4. Dataset mapping and validation boundaries

The contract projection is limited to the five contract datasets and their defined grains. Internal truth and provenance are not additional contract datasets.

| Dataset | Grain | Key relationship | Producer | Validation boundaries |
|---|---|---|---|---|
| `customers.csv` | One row per customer | `customer_id` primary identifier | Customer generator | Contract/schema, uniqueness and required fields; customer-to-episode attribution is not proven by row validity alone. |
| `subscriptions.csv` | One row per subscription episode | `subscription_id`; references `customer_id` | Episode/lifecycle generator | Contract/schema, key existence, lifecycle semantics, semantic attribution, temporal correctness, and later model eligibility are separate. |
| `usage_monthly.csv` | One row per usage period and episode | References `subscription_id` | Usage generator | Contract/schema, key existence, period boundaries, temporal alignment, and semantic attribution are separate. |
| `invoices.csv` | One row per invoice | `invoice_id`; references `subscription_id` | Billing/invoice generator | Contract/schema, key existence, date/amount checks, billing-period correctness, and episode attribution are separate. |
| `subscription_snapshots.csv` | One row per episode and snapshot point | References `subscription_id` | Snapshot builder | Contract/schema, key existence and configured point-in-time rules; mode-dependent requirement applies. |

Current Pandera/schema validation enforces declared field/type/nullability and selected domain constraints. Existing RI checks establish key existence only; they do not prove that an event belongs to the correct semantic episode. Current temporal checks are limited (including end date not before start date and cancellation date not before start date). They do not establish complete period, information-availability, cutoff, or label correctness. Contract validity and RI/limited temporal success are not evidence of semantic episode attribution, outcome correctness, or model eligibility.

## 5. Truth, time, scenarios, and eligibility

### 5.1 Historical truth and observable information

Maintain two conceptual timelines without adding contract columns:

- **Business state effective at `t`:** what the simulated business says was true at that effective time, including event effective timestamp.
- **Information available at `t`:** what the system could have known by `t`, based on event availability timestamp and the relevant extraction/observation cut-offs.

Event replay must order/apply business effects by effective time while respecting when information became available; late-arriving events cannot be treated as known earlier. Historical snapshots and features use only information available at their observation time. Usage aggregation assigns facts to approved business periods but cannot expose facts unavailable by the model observation cutoff. Feature generation excludes future effective events and events only available later, including later corrections. Label construction may use subsequent follow-up within the approved horizon and ascertainment cutoff, but label-only future information must never flow to predictive features. Exact conventions and completeness policy remain open.

Block C's internal outcome states remain distinct: **confirmed positive**, **confirmed negative**, **right-censored**, **pending_ascertainment**, and **ineligible**. A positive requires a qualifying event in the horizon and ascertainment by the label cutoff. A negative requires complete, ascertained follow-up through the horizon. Right-censored means follow-up is known complete only to an endpoint before the horizon. Pending ascertainment means outcome evidence/completeness is unresolved at the ascertainment cutoff; it is not a negative or a synonym for censoring. Ineligible means the observation fails a separately approved eligibility rule. Calendar coverage alone does not prove ascertainment. These are internal truth concepts, not Customer Data Contract values or production churn policy.

### 5.2 Scenario framework

Scenarios alter explicit parameters while preserving invariants and use isolated reproducible streams. The catalogue is a design framework; distributions are synthetic hypotheses and must not be described as market estimates.

| Scenario | Intended variation | Invariants / checks |
|---|---|---|
| Baseline | Approved Block B baseline profile/target parameters; affects customers, episodes and downstream facts. | Preserve baseline assumptions; test configured counts, key integrity and all applicable validation gates. |
| Higher growth | Customer/episode arrival-rate and population-target parameters; affects customers, episodes and downstream facts. | Stable independent streams; test target counts and no broken links or duplicate identities. |
| Higher reactivation | Reactivation frequency/timing parameters; affects episodes, lifecycle, billing, usage and truth. | Each confirmed reactivation gets a new episode ID; test preserved prior history and separate episode outcomes. |
| Higher synthetic churn | Synthetic hypothesis event-frequency parameters; affects lifecycle events and internal truth. | Must not define production churn; test qualification/ascertainment gates and no public truth leakage. |
| Lower usage adoption | Usage-adoption parameters; affects usage and downstream snapshots/features. | Preserve approved business limits; test period and episode alignment. |
| Higher usage adoption | Usage-adoption parameters; affects usage and downstream snapshots/features. | Preserve approved business limits; test period and episode alignment. |
| Billing stress | Invoice/payment delay, status and edge-case parameters; affects billing, invoices and possibly lifecycle context. | Contract constraints remain valid; test invoice ordering/amount constraints; unresolved boundaries prevent temporal correctness claim. |

### 5.3 Acceptance criteria: current versus future

| Gate | Acceptance condition | Current evidence/status |
|---|---|---|
| Contract/schema | Output conforms to exact contract dataset shape and schema; no truth/provenance fields leak into projection. | Generic contract/schema validation exists for inputs; generator projection not implemented. |
| Referential integrity | Every applicable foreign key resolves to its referenced entity. | RI checks exist for defined relations; semantic attribution is not implied. |
| Identity/lifecycle | Episode IDs follow approved identity and lifecycle decisions; reactivation is distinct. | ADR decisions exist; generation/Registry behaviour not implemented and several lifecycle decisions remain open. |
| Billing/usage/snapshots | Period boundaries and timing follow approved conventions and reconciliations. | Blocked in part by open temporal conventions; generation not implemented. |
| Temporal correctness | Effective/availability times and observation, horizon, follow-up, extraction, and ascertainment cutoffs are consistent. | Existing checks cover only narrow date ordering; full policy/gates not implemented. |
| Outcome/censoring | Eligibility matrix and mathematical outcome definition agree; no incomplete observation is silently negative; pending differs from censoring. | Block C design only; target/cutoff/qualification policy not approved or implemented. |
| Model eligibility/leakage | Only eligible episodes/features are selected; no future/unavailable information becomes a feature. | Policy and evaluator not implemented; several decisions open. |
| Reproducibility/provenance | Run claim matches captured config, RNG, environment, outputs and actual comparison evidence. | Design only; no generator or manifest. |
| Negative fixtures/failure | Invalid fixture triggers its specified report/reject behaviour, never automatic repair or silent exclusion. | Catalogue design; generator-specific test suite not implemented. |

### 5.4 Validation scope and publication eligibility

Before execution, declare the intended use, output inventory, applicable policy versions and required gates for each intended claim. Apply the existing acceptance criteria in Section 5.3 to that scope and record the evidence and any gates outside it. Each L1, L2 or L3 reproducibility claim also requires evidence for the level claimed.

| Intended claim | Required evidence |
|---|---|
| Contract-valid synthetic test outputs | Contract/schema and applicable referential checks succeed for the declared test inventory. The minimum BASIC slice covers these checks for customer and subscription fixtures. |
| Fully validated synthetic populations | The contract and referential checks succeed, along with the applicable population, identity, lifecycle, semantic episode attribution, complete temporal and commercial consistency checks. If the declared population includes internal outcome truth, validate it against its synthetic target, ascertainment and censoring rules. |
| Model-eligible labelled datasets | The applicable population gates succeed. The identified target and label policy, observation and outcome cutoffs, censoring, historical availability, leakage and eligibility gates all have successful evidence for the intended modelling use. Synthetic eligibility applies only under the identified synthetic policy. |
| Production-ready outputs | The gates required for the declared production use succeed, and operational, security and governance readiness is separately evidenced and accepted. Production churn use also requires approved production churn and eligibility policies. |

Any required gate recorded as `FAILED`, `BLOCKED`, `NOT_IMPLEMENTED` or `NOT_EVALUATED` prevents the corresponding acceptance and publication eligibility claim. Gates outside a narrower scope supply no evidence for broader claims. A BASIC pass provides no evidence of semantic episode attribution, complete temporal correctness, churn label validity or model eligibility. These outcome labels describe design evidence in the [logical manifest](synthetic_generation_reproducibility_and_provenance.md#7-logical-generation-manifest). The existing pipeline retains its own statuses. Publication requires separate explicit authorisation for the specific eligible output set and scope.

## 6. Consolidated decision register

Each row uses one formal status: **Approved**, **Proposed**, **Open** or **Blocked**. Pending source decisions are shown as Open in this register. The source records govern their original status and authority. Implementation evidence is recorded separately.

| ID | Decision | Status | Dependency / implementation impact |
|---|---|---|---|
| ADR-009 / EP-DEC-002 / CGQ-001 | The canonical subscription episode is the prediction entity. Customer ID identifies and groups accounts and is excluded from predictive features. | Approved | Shapes labels, grouping and the feature boundary. |
| ADR-010 / PD-002 / RPR-004 | Issue a Nowa-owned canonical UUID once for an authoritatively established episode and persist and reuse it. Confirmed reactivation after termination creates a new ID and preserves earlier history. | Approved | Depends on authoritative identity evidence. See RPR-015 for implementation and replay. |
| ADR-010 / PD-001 / RPR-005 | A persistent, client-isolated Episode Identity Registry is required for durable identity. | Approved | See DD-EP-003 and RPR-016 for open Registry design details. |
| PD-006 | Snapshot optional in BASIC and required in TEMPORAL mode. | Approved | Mode-specific contract gate; snapshot convention remains unresolved. |
| CGQ-013 | Historical features may use only information available at the observation cutoff. | Approved | Requires availability-aware feature construction and leakage checks. |
| CGQ-018 | No contract additions and no survival architecture introduced by Block C. | Approved | Internal truth remains outside contract; survival modelling remains out of scope. |
| BDR-010 / CGQ-020 | Snapshot convention and availability representation. | Open | Blocks final snapshot and historical feature semantics. |
| BDR-011 | Usage period boundaries. | Open | Blocks temporal usage aggregation acceptance. |
| Block B Section 5 (baseline cadence) | Monthly or annual advance billing is the fictional baseline cadence. | Approved | BDR-012 records the baseline as approved and tracks the remaining billing-cycle choices. |
| BDR-012 | Exact billing anchor, period boundaries and unresolved lifecycle interactions. | Open | Blocks full invoice-period correctness. |
| BDR-013 / CGQ-019 / RPR-015 | UUID version/provider and synthetic identity allocation, persistence and replay mechanism. | Open | Blocks exact identity replay. RPR-004 and RPR-005 govern the approved principles. |
| DD-EP-003 / RPR-016 | Remaining Episode Identity Registry technical and operational design. | Open | ADR-010 and PD-001 govern the approved requirements. Client and source evidence inform durable mappings. |
| BDR-014 / DD-EP-001 / DD-EP-005–007 | Episode boundary, status, lifecycle and event semantics. | Open | Blocks complete lifecycle generation. |
| DD-EP-008–012 | Dependent record attribution, boundary-spanning usage and historical migration criteria. | Open | Source and product evidence is needed for semantic attribution and historical acceptance. |
| BDR-015 | Relationship between extraction and model observation cutoffs. | Open | Blocks historical availability claims for modelling until the applicable policy is defined. |
| CGQ-009–012 | Provisional 90-day history and 30-day horizon examples, ascertainment and right-censoring rules. | Proposed | Label validation requires the approved policy, evidence-completeness rules and cutoffs. |
| CGQ-006 / RPR-013 | Synthetic effective-end target hypothesis. | Proposed | Requires qualification, ascertainment and an approved synthetic configuration. |
| CGQ-007 | Qualifying churn event set. | Open | Requires explicit episode boundary and event definitions. |
| CGQ-008 / DD-EP-013 / RPR-017 | Production churn and label semantics. | Open | Requires product policy and client/source evidence before production use. |
| CGQ-021 | `pending_ascertainment` internal outcome state. | Proposed | Must not be treated as a contract field or approved policy until accepted. |
| BDR-016 / CGQ-015–016 / DD-EP-017 / RPR-017 | Production model eligibility, grouping and evaluation strategy. | Open | Blocks final eligibility and evaluation splits. |
| CGQ-022 / RPR-010 | Persistent ground-truth and provenance storage. | Open | Format, access, retention and cleanup, identity persistence and provenance remain unresolved. |
| RPR-001 | L1 configuration, L2 statistical and L3 exact reproducibility classifications. | Proposed | Every claimed level requires its own evidence. |
| RPR-002 | Versioned named random streams. | Proposed | Depends on the selected RNG and derivation method. |
| RPR-003 | Effective configuration fingerprint. | Proposed | Depends on the chosen canonical encoding, hash and configuration schema. |
| RPR-006 | Logical generation manifest. | Proposed | Records separate stage outcomes and publication evidence. Physical format and storage depend on separate decisions. |
| RPR-007 | SHA-256 output checksum. | Proposed | Verifies file integrity using the actual output bytes. |
| RPR-008 | Exact output ordering and serialisation conventions. | Open | Affects byte equivalence within existing contract requirements. |
| RPR-009 | Runtime and dependency provenance, including a dependency fingerprint. | Proposed | Reproducible environment capture depends on a lock or resolution strategy that remains open. |
| RPR-011 | Project-wide exact reproducibility guarantee. | Open | Depends on identity replay, RNG, dependency resolution and output conventions. |
| RPR-012 | Internal run and publication states. | Proposed | Records scope-specific eligibility separately from explicit publication authorisation. |
| RPR-014 | L2 statistical metrics, assessment protocol, sample sizes and tolerances. | Open | Approve and declare the criteria before evaluation and record the comparison evidence. |

See the [Block D RPR decision register](synthetic_generation_reproducibility_and_provenance.md#11-decision-register), [Block B decision register](synthetic_data_generation_rules.md#8-structured-decision-register) and [Block C decision register](synthetic_churn_ground_truth_and_data_quality.md#10-decision-register) for source rationale and dependencies.

## 7. Critical path and implementation readiness

### 7.1 Dependency and critical-path analysis

| Work | Depends on | Can proceed independently? | Consequence / critical-path effect |
|---|---|---|---|
| Config/run context and component interfaces | Architecture and a minimal agreed config contract | Yes, as design/specification; implementation requires authorisation | Establishes reproducible orchestration without fixing open business policies. |
| Customer generation | Approved population profiles and configurable targets | Yes | Can be developed/tested independently of production churn target. |
| Episode identity allocation | ADR-009/010 plus UUID/provider/replay choices | Partly | Fixture-based contract projection can proceed; durable/reproducible allocation waits on decisions and Registry. |
| Lifecycle and event generation | Episode boundaries/status/event qualification decisions | Limited | Synthetic structural fixtures may proceed; authoritative lifecycle/outcome claims cannot. |
| Billing/invoices | Episode states plus billing anchor and boundaries | Limited | Schema-shaped examples possible; temporal acceptance blocked by unresolved periods. |
| Usage | Episode assignment and usage-period boundaries | Limited | Isolated generation logic can be explored; period reconciliation blocked. |
| Snapshots/features | Snapshot convention, availability and observation cutoff | No for historical correctness | BASIC non-snapshot path may proceed; TEMPORAL snapshot/feature correctness is blocked. |
| Ground truth/outcomes | Target, event qualification, horizon, ascertainment and censoring decisions | No for production labels | Internal model-independent structures can be designed; final target labels/eligibility blocked. |
| Persistent truth/provenance artifacts | Format, access control, retention, identity persistence, reproducibility/provenance decisions | No | No persistent storage architecture or retention operation can be implemented safely from current decisions. |
| Contract projection and existing BASIC validation | Contract v1.1 and fixture identifiers | Yes | Can validate shape and key existence but cannot prove semantic attribution, complete temporal policy or eligibility. |

### 7.2 Readiness matrix

| Component | Classification | Design maturity and existing evidence | Decisions / tests / sequence |
|---|---|---|---|
| Customer generation | Ready with approved configuration | Business model and population assumptions bound the design; no generator exists. | Fix config contract; unit tests for counts, constraints and deterministic attributes; early (WP-03). |
| Episode identity generation | Blocked by open decision | ADR-009/010 govern entity and Registry need; generator/Registry absent. | Resolve UUID method/version and replay; unit/integration tests for reuse/reactivation; after customers (WP-04). |
| Lifecycle events | Blocked by open decision | Rules document design only; lifecycle generator absent. | Resolve episode/event semantics; tests for transitions, attribution and temporal invariants; with WP-04. |
| Billing | Blocked by open decision | Contract/business catalogue exist; generator absent. | Resolve anchor and periods; test invoice/payment constraints and reconciliation; after lifecycle (WP-05). |
| Invoice generation | Ready with approved configuration | Structural catalogue/contract projection is defined; no generator. | Approve effective configuration; contract/schema plus date/amount tests; after lifecycle, with billing decisions for complete timing (WP-05). |
| Usage | Blocked by open decision | Contract shape defined; generator absent. | Resolve period boundary; tests for bounds, attribution and aggregation; after episodes (WP-06). |
| Snapshots | Blocked by open decision | Mode requirement approved; snapshot generation absent. | Resolve point convention and availability; point-in-time/no-leakage integration tests; after cutoff policy (WP-06). |
| Contract projection | Ready for implementation | Contract v1.1/schema and existing validation code are present; synthetic projection absent. | Use fixture identifiers; projection tests against schema and existing BASIC pipeline; early independent slice (WP-08). |
| Temporal validation | Blocked by open decision | Existing TC checks cover only narrow date ordering; full validator absent. | Resolve boundaries/cutoffs; unit/integration tests by distinct temporal rule; after relevant policy (WP-09). |
| Model eligibility | Blocked by open decision | No synthetic eligibility gate; Block C decisions remain open. | Resolve target, ascertainment, censoring, feature cutoff and grouping; tests for five states and leakage (WP-07/09). |
| Logical ground-truth structures | Ready for implementation | State distinctions and separation boundary can be represented without selecting storage; no generator exists. | Tests for positive/negative/censored/pending/ineligible and reactivation; after rules accepted (WP-07). |
| Persistent ground-truth storage | Blocked by open decision | No storage architecture approved. | Resolve format, access, retention/cleanup, identity persistence and provenance; security/retention tests before use (WP-10/11). |
| Provenance manifest | Ready with approved configuration | Logical contents and levels designed; no physical manifest. | Decide canonical encoding, lock strategy and lifecycle; completeness/integrity/failure tests (WP-01/10). |

Readiness means that a component has sufficient design scope to begin after implementation is separately authorised. It does not indicate that implementation, tests, or production readiness exist.

## 8. Work-package roadmap

All work packages are future, separately authorised implementation work. A package may be refined or reordered after decisions; acceptance evidence must distinguish implemented capability from design.

| WP | Objective and deliverables | Dependencies, tests, acceptance and blockers |
|---|---|---|
| WP-01 — Configuration and Run Context | Validated configuration, scenario resolution, run identity, stage lifecycle and initial provenance. | Agree defaults/policy references; unit tests reject invalid/unknown values before draws; verify run states, sanitised diagnostics and failed-stage propagation. |
| WP-02 — Deterministic Random Streams | Master seed and versioned, independent component/scenario streams. | Select RNG/derivation/version; repeatability and stream-isolation tests; exact guarantee remains open until dependencies and ordering are pinned. |
| WP-03 — Customer Population Generation | Bounded customer population from approved configuration. | WP-01/02; tests for counts, constraints and declared deterministic scope; no market calibration claim. |
| WP-04 — Canonical Episode Identity and Lifecycle | Episode records, identity issuance/reuse, lifecycle and commercial events. | UUID/replay and lifecycle decisions; test reactivation as new episode, preserved history and semantic attribution. Identity Registry details remain blocked. |
| WP-05 — Billing and Invoice Projection | Billing periods, invoices and payment facts. | Resolve billing anchor/boundaries; tests for contract constraints, reconciliation and temporal joins. |
| WP-06 — Usage and Snapshot Projection | Usage periods and mode-appropriate snapshots. | Resolve usage/snapshot/availability cutoffs; tests for period alignment and no unavailable facts in historical state/features. |
| WP-07 — Synthetic Outcome Truth and Censoring | Internal five-state truth and outcome calculations. | Approve target, qualification, horizon, ascertainment and censoring rules; test each state and ensure incomplete follow-up is not labelled negative. |
| WP-08 — Contract Projection and Existing Pipeline Integration | Project the unchanged five contract datasets and invoke existing contract/schema, RI and limited TC checks. | Contract v1.1; integration tests label each gate separately; projection does not imply semantic attribution or eligibility. |
| WP-09 — Semantic and Temporal Validation | Add episode attribution and complete temporal/availability validation gates. | Resolve lifecycle/temporal policies; rule-level and integration tests for effective/availability times, boundaries and cutoffs. |
| WP-10 — Provenance and Reproducibility Verification | Logical/physical manifest decisions, output inventory, integrity and verified reproducibility claims. | Resolve serialization, dependency lock and storage/security; tests for completeness, checksums, interruptions, failures, identity replay and code/dependency changes. |
| WP-11 — Negative Fixtures and End-to-End Acceptance | Isolated negative fixtures and full configured run/publication acceptance. | Prior packages; tests verify reject/report behaviour with no repair/drop/reclassification, isolation from valid outputs, and controlled publication/access/cleanup. |

### 8.1 Minimum vertical slice independent of production churn

The proposed minimum BASIC slice covers WP-01 through a narrow portion of WP-04 and WP-08. It validates configuration and stage reporting, generates a bounded customer population, uses fixture-supplied identifiers in the approved format, projects `customers` and `subscriptions` to contract v1.1 and runs the existing BASIC schema and applicable referential checks. Its acceptance claim is contract-valid synthetic test outputs under Section 5.4. The declared inventory contains only these two datasets and excludes churn labels. Record the actual claim and evidence for deterministic customer attributes only when the selected RNG and configuration are fixed. Semantic episode attribution, full temporal validation, synthetic churn labels and model eligibility require their own successful evidence in a broader scope.

## 9. Risks and limitations

- Synthetic distributions reflect explicit assumptions and scenarios, not calibrated GB market behaviour.
- Open identity and lifecycle decisions can invalidate stable IDs, episode history, and downstream attribution.
- Temporal ambiguity creates leakage risk and prevents defensible historical snapshots, usage periods, and labels.
- A qualifying event not ascertainable by the label cutoff cannot be silently labelled positive or negative; incomplete ascertainment is not complete follow-up.
- Current schema, RI and narrow temporal checks do not prove semantic attribution, complete temporal correctness, outcome validity or eligibility.
- Internal ground truth and identity mappings create privacy/security obligations; storage, access and retention are unresolved.
- Same seed does not ensure exact output across RNG, dependencies, identity policy, ordering or serialisation changes.
- The design baseline register records the Phase 3.3.1 traceability exception and the individual statuses of governing and supporting references.
- Design readiness, implementation completion, validation evidence and production readiness are separate claims.

## 10. Phase completion states

| State | Meaning | Evidence required |
|---|---|---|
| Design complete | Architecture, rules, provenance and acceptance expectations are documented with open decisions explicit. | Reviewed Block A–D documents and traceable decisions; does not require every policy to be settled. |
| Decision complete | Required product, temporal, target, identity and storage decisions are approved or explicitly scoped out. | Approved decision records and dependencies closed. |
| Implementation authorised/complete | Approved scope is implemented in code/configuration and reviewed. | Separate authorisation, code changes and implementation review; not achieved by this document. |
| Validation complete | Applicable unit, integration and end-to-end criteria have been run and results recorded. | Actual test/check evidence; not claimed here. |
| Production ready | Security, access, retention, operational reliability, monitoring and governance are accepted. | Separate operational/security approval; not implied by design or synthetic validation. |

## 11. NEDS v1.1 design alignment

| NEDS area | Design response | Remaining implementation consideration |
|---|---|---|
| Modularity and maintainability | Preserves bounded components and the local modular monolith. | Keep interfaces explicit and justify future architectural expansion. |
| Configuration and dependency management | Validated effective configuration, versioned inputs, environment provenance and dependency fingerprint are specified. | Select configuration schema, dependency lock/fingerprint and supported runtime. |
| Data management and quality | Dataset grains, quality layers, lineage, internal/public boundary, and failure gates are distinct. | Implement approved semantic, temporal, outcome and eligibility checks. |
| Reproducibility | L1/L2/L3 claims, named streams, manifest and verification evidence are defined in the companion design. | Select exact algorithms/conventions and demonstrate each claimed level. |
| Logging and error handling | Stage/failure logging, stop-on-failed-dependency, sanitisation and no false success are required. | Implement and verify logs, run-state propagation and publication behaviour. |
| Testing strategy | Unit, integration and end-to-end responsibilities and acceptance gates are specified. | Build and execute tests only under separately authorised implementation work. |
| Security and data protection | Least privilege, truth separation, sanitised logs, controlled access and retention are required. | Approve artefact storage, access roles, audit and cleanup controls. |
| Documentation and British English | Uses British English, stable IDs, explicit versions/statuses and cross-reference traceability. | Maintain language and links through implementation changes. |
| Technical justification and scope control | Preserves approved architecture, records unresolved decisions, and avoids unnecessary infrastructure. | Document rationale for any proposed deviation; obtain required decision approval. |

This matrix records design alignment only. It is not a claim of NEDS implementation compliance.

## 12. Traceability and status

This v0.1 consolidation for Phase 3.3.3 Block D is Approved for Design Baseline. It preserves the approved business specification and contract boundaries, Block A–C design intent, and unresolved decisions. It does not implement a generator, Registry, validation gate, manifest, storage system, dataset, or test. No production churn policy or model eligibility policy is approved by this document.
