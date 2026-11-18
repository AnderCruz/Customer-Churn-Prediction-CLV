# Synthetic Data Generation Design Baseline

| Document control | Value |
|---|---|
| Document ID | NCI-SYNTH-BASELINE-001 |
| Version | 0.1 |
| Status | Approved — Documentation Baseline |
| Project | Nowa Customer Intelligence |
| Market | Great Britain (GB) |
| Scope | Documentation governance and approved design baseline for Phase 3.3.3 |
| Standard | Nowa Analytics Engineering & Development Standard (NEDS) v1.1 |

## 1. Purpose and baseline scope

The baseline identifies the five technically reviewed Phase 3.3.3 design documents and the references needed to interpret them. Blocks A–D define the architecture, generation rules, ground truth and quality gates, reproducibility and provenance, and consolidated implementation plan. This register records the approved documentation baseline and its governance evidence. The governing and supporting references retain their own authority and document control.

| Governance state | Evidence and disposition |
|---|---|
| Technical review completed and approved | The project owner confirms that technical review of Blocks A–D is complete and approved in the instruction for this activity. The confirmation applies to the design review scope and preserves the status of each underlying decision. |
| Formal document approval | The project owner approved the five reviewed specifications for this design baseline. Each document retains v0.1 and its original decision statuses. |
| Change control | The project owner authorised two local documentation commits. Section 7 records their exact scope and the execution report records the resulting revisions. |
| Implementation and validation | WP-01 is ready for planning and approval. Implementation authorisation, implementation completion, validation evidence and production readiness are separate milestones. The approved review does not confer any of them. |

## 2. Primary baseline register and integrity snapshot

All five specifications are approved for the Phase 3.3.3 design baseline. SHA-256 values cover the current file bytes, including formatting and line endings.

| Block and exact repository path | Title and document ID | Version and current metadata status | Why included and governing constraints | SHA-256 |
|---|---|---|---|---|
| A — [docs/04_data/synthetic_data_generation_architecture.md](synthetic_data_generation_architecture.md) | Synthetic Data Generation Architecture · NCI-SYNTH-ARCH-001 | 0.1 · Approved for Design Baseline | Owns logical components, configuration and the pipeline boundary. Inherits contract, ADR, population and business constraints. | `63318386c92d67d2762bb567cc56f2ed8dd2b501dc523f8df8a544cf20dc44f5` |
| B — [docs/04_data/synthetic_data_generation_rules.md](synthetic_data_generation_rules.md) | Synthetic Data Generation Rules · NCI-SYNTH-RULES-001 | 0.1 · Approved for Design Baseline | Applies Block A to entity, lifecycle, billing, usage and snapshots. The approved business model, contract and episode decisions govern their respective rules. | `143bfaf69fd47400446f868bfd0da57a23e7b4d05253318cb36277517b1f3433` |
| C — [docs/04_data/synthetic_churn_ground_truth_and_data_quality.md](synthetic_churn_ground_truth_and_data_quality.md) | Synthetic Churn Ground Truth and Data Quality · NCI-SYNTH-QUALITY-001 | 0.1 · Approved for Design Baseline | Adds synthetic outcomes, censoring, independent quality gates and isolated negative fixtures to A and B. DQ rule intent, implemented capability and production policy have separate sources. | `329ba1fd35414db0e54526736e8df84fcd20aafcd155caa2b3b8bae1e7a06d16` |
| D — [docs/04_data/synthetic_generation_reproducibility_and_provenance.md](synthetic_generation_reproducibility_and_provenance.md) | Synthetic Generation Reproducibility and Provenance · NCI-SYNTH-REPRO-001 | 0.1 · Approved for Design Baseline | Defines proposed reproducibility evidence, run scope and provenance across A–C. ADR-010 and the open identity, storage and output decisions constrain what can be claimed. | `a939f31dc91a69694836dec50d785f54051095116d22b2316b71df07dec079d6` |
| D — [docs/04_data/synthetic_data_generation_design_specification.md](synthetic_data_generation_design_specification.md) | Synthetic Data Generation Design Specification · NCI-SYNTH-DESIGN-001 | 0.1 · Approved for Design Baseline | Consolidates A–D into scope-specific acceptance, dependencies and work packages. Original decision records retain authority over the summary. | `e698935a61a22b1158d41dbd4633f6972141792e11e03a14f450a2aa0a15cbb1` |

The checksums identify the approved document bytes. The execution report records the Git revision containing this register.

## 3. Governing references, supporting material and authority

| Reference | Identification and current status | Git custody and authority |
|---|---|---|
| [Customer Data Contract](customer_data_contract.md) | v1.1, Approved for Implementation, no document ID in header | Tracked. Governs contract datasets, fields, grain and validation requirements. |
| [Synthetic Business Model Specification](synthetic_business_model_specification.md) | NCI-SYNTH-BIZ-001 v0.2, Approved | Versioned companion. Governs fictional catalogue, GBP and baseline commercial assumptions. |
| [Architecture Decision Records, ADR-009](../03_architecture/architecture_decisions.md#adr-009-subscription-level-churn-prediction) | Register NCI-ADR-001 v0.2, Proposed decisions. Individual ADR-009 Accepted. | Tracked. Governs subscription-level prediction. |
| [Subscription Episode Identity and Identifier Management](../03_architecture/adr_episode_identity_and_identifier_management.md) | ADR-010, NCI-ADR-010 v1.0, Accepted | Tracked. Governs canonical episode identity and the Registry requirement. |
| [Product Decision Proposals](product_decision_proposals.md) | NCI-PRODUCT-DECISIONS-001 v0.2. The header records approved product decisions and withholds implementation authorisation. PD-001–PD-007 are approved in the body. | Versioned companion. The individual approved product decisions govern Registry functional requirements, identity and submission treatment, migration, snapshot workflow and compatibility. |
| [Subscription Episode & Lifecycle Decision Specification](subscription_episode_lifecycle_decision_specification.md) | NCI-EPISODE-SPEC-001 v0.4, Draft for Review. The individual EP-DEC records retain their recorded statuses. | Versioned companion. Governs approved episode principles at decision level and identifies unresolved DD-EP topics. Whole-document approval is separate. |
| NEDS | v1.1, Mandatory Standard, no document ID in header | External project reference, `../NA Enginnering_Development_Standard_NEDS.md`, available and reviewed. SHA-256 `e2b165a04a1213c2367968cc8938fafadfab27fa19bdd4570b84a918606a025c`. A repository checkout alone cannot reproduce the reference review. Retain an approved reference location and this fingerprint with approval evidence. |
| Phase 3.3.1 Synthetic Data Requirements and Population Specification | The supplied attachment is the activity brief. It calls for a report in the conversation and lacks a document ID, version and approval record for that report. | The brief is external, attachment `9014bf80-a6d4-43f8-847c-d9ee827b6e92`, SHA-256 `48904aa4ef4ed7e0f4c53e4d53e7c818f2069383e87b1db4df9050c6055e00a0`. The completed specification cited by the design was not located as a repository file or verified from the accessible attachment. Preserve the adopted configurable population anchors in BDR-006 and obtain or identify the completed report and its approval evidence for independent traceability. |

SHA-256 values for local governing and supporting references

| Repository path | SHA-256 |
|---|---|
| `docs/04_data/customer_data_contract.md` | `34ba53878ea76013b7176ea2792c7dc57ec47a9a4678a0619c74e26afa601e35` |
| `docs/04_data/synthetic_business_model_specification.md` | `1f3ffb5a7b00b459e815ead0e59701dcd529777f758c2bf3d8e00b1c10e6fbe5` |
| `docs/03_architecture/architecture_decisions.md` | `1daff410139d5d6dbe9662a697a672d71085060243672945f4eeb9c755a1db19` |
| `docs/03_architecture/adr_episode_identity_and_identifier_management.md` | `f2618aad4288440c8156a5781744fbec59d85af97f8d5f64bc355669754e07ed` |
| `docs/04_data/product_decision_proposals.md` | `3eae49f9942a0650adce8fbd22d79bfa1aa946c2e3b04e5102ac418c78c9675a` |
| `docs/04_data/subscription_episode_lifecycle_decision_specification.md` | `f2990b3af725ff501403ccc3aed0bf05b97927b2a533437a580de32ab6203487` |
| `docs/04_data/product_decisions_and_contract_design_assessment.md` | `71a5ece0906f4df8ec1bc26029707392b6ae6d75a05fd45a58e3923f8b536ce9` |
| `docs/04_data/data_quality_implementation_architecture.md` | `cc6dcfff4a82740529f79f48cae3be32bf14fd0fdf1caf4a20979bb9eccd8af0` |
| `docs/04_data/subscription_episode_data_contract_impact_assessment.md` | `eb087ba22e2deb65a144f4efddccd4d10155dc853cf4570424ae8ff8d6e52d6d` |
| `docs/04_data/data_quality_specification.md` | `a2c718f027bd54cab1d19713fccf8b74dc18499d76f7625d071a782a8a82fd1d` |
| `docs/03_architecture/pipeline_orchestration_specification.md` | `4ba4889fa4827a3b8c1d76caa83c8bed3dab76b8a40987110581cf99dd344021` |
| `docs/03_architecture/pipeline_execution_summary_specification.md` | `8d625004d6a79b2d3012ad37937a0d0496f191dbe4d300a20c70bafd66c378c5` |

Supporting references have narrower roles:

| Reference | Metadata and custody | Role |
|---|---|---|
| [Data Quality Specification](data_quality_specification.md) | NCI-DQ-SPEC-001 v0.2, Draft for technical review, tracked | Rule intent, severity, applicability and validation layer boundaries. |
| [Data Quality Implementation Architecture](data_quality_implementation_architecture.md) | NCI-DQ-ARCH-001 v0.2, Draft for technical review, versioned companion | Intended DQ design. Current source and tests establish implemented capability. The descriptions of report assembly, coordination and integration in §§5–9 are stale. |
| [Pipeline Orchestration Architecture Specification](../03_architecture/pipeline_orchestration_specification.md) and [Pipeline Execution Summary Specification](../03_architecture/pipeline_execution_summary_specification.md) | Tracked. Neither header declares an ID or version. The respective status lines are “Architecture specification; this document does not authorize implementation” and “Technical specification; implementation is not authorized by this document”. | Record approved ORCH-001–ORCH-014 and PES-001–PES-016 respectively. Define orchestration and evidence boundaries. The pipeline source at the inspected HEAD is the evidence of implementation. |
| [System Architecture](../03_architecture/system_architecture.md), [Data Architecture](../03_architecture/data_architecture.md) and [Data Sources and Governance](data_sources_and_governance.md) | NCI-ARCH-001, NCI-DATA-ARCH-001 and NCI-DATA-001, respectively. All v0.2, Draft for review and tracked. | General modularity, data layers and governance context. |
| [Product Decisions and Contract Design Assessment](product_decisions_and_contract_design_assessment.md) | NCI-PRODUCT-CONTRACT-DESIGN-001 v0.1, Draft for product review, versioned companion | Supporting decision inventory and impact analysis. The approved product decision record supplies approval evidence. |
| [Subscription Episode Data Contract Impact Assessment](subscription_episode_data_contract_impact_assessment.md) | Read-only technical impact assessment. No header ID or version. Versioned companion. | Historical analysis linked from the approved business model. Contract v1.1 and accepted decisions govern current requirements. |
| [Documentation Review and Approval Register](../07_project_management/documentation_review_and_approval.md) | NCI-APR-001 v0.3, tracked. Conditionally approved baseline for repository and development-environment setup. | Earlier governance precedent for Phase 1. The current project-owner instruction supplies Phase 3.3.3 technical review evidence. |

**Precedence.** Apply NEDS to engineering governance, the contract to external dataset obligations, accepted ADRs and approved individual product/episode decisions to their policy domains, and the approved business model to synthetic assumptions. For generator design, use A for component boundaries, B for generation rules, C for truth and quality, and the provenance document for run evidence. The consolidated specification supplies the combined roadmap. Read its summary alongside the original records where wording differs. Use source code at the recorded revision to establish existing capability. Refer conflicts across authorities to their owners and retain the original decision status pending resolution.

## 4. Formal governance dispositions

### FDB-001 — Phase 3.3.1 traceability exception

The project owner approved a controlled traceability exception for the Phase 3.3.3 documentation baseline. The accessible attachment is the activity brief. The original completed population specification and its independent approval evidence remain unverified. BDR-006 retains approximately 1,000 customers, approximately 1,100–1,400 subscription episodes and a 36-month synthetic history as configurable engineering assumptions. They have no empirical validation as GB market estimates. Keep this limitation visible in future reviews. Resolve it by locating the completed specification and its approval evidence and reconciling them with BDR-006.

### FDB-002 — Workflow inventory

The five Customer Data Contract v1.1 datasets listed in Section 5 are the supported inventory. The declared workflow, contract v1.1, approved PD-006 and applicable pipeline requirements determine the required execution inventory. Initial BASIC validation requires `customers.csv` and `subscriptions.csv`. Snapshots are optional for BASIC and required for TEMPORAL. Other optional inputs follow the existing contract and workflow requirements. Use the workflow-aware `execute_pipeline` boundary for this interpretation. The direct `ingest_client_datasets` CSV loader continues to require snapshots.

### FDB-003–FDB-006 — Authority, approval and custody

Section 3 records the six companion references and their individual authority. The episode/lifecycle reference retains its Draft for Review status. A formatting-only correction replaced 23 two-space Markdown hard breaks with equivalent explicit hard breaks. The supporting DQ implementation-status discrepancy remains recorded in Section 3. Sections 1–2 record approval of the five specifications and this register for documentation governance. Section 7 records the two authorised commit inventories. Implementation requires separate authorisation.

### Other review findings

| Document and section | Finding | Severity | Disposition | Baseline impact |
|---|---|---|---|---|
| A §14 (SA-001, SA-003), B §8 (BDR-005), D consolidation §§2–3 | B treats the inherited single-process and contract boundary as established for Block B while A labels its detailed architecture choices Proposed. | Decision status clarification | Preserve BDR-005 for the inherited boundary and retain the SA records' original statuses for implementation choices. Record any later promotion in the source decision record. | No for the design scope. Explicit disposition is required before implementing an unresolved choice. |
| A §§4 and 13.2, D provenance §§2 and 11 | A uses broader repeatability language including manifests and row ordering. D records run-specific metadata and conditions exact replay and byte equivalence on evidence and open conventions. | Medium | Use the D reproducibility definitions for acceptance claims. If wording is later aligned, distinguish logical row equivalence, output bytes and run-specific manifest metadata. | No with this interpretation recorded. |
| A §10 and SA-010, D consolidation §8.1 | The direct CSV loader requires snapshots, while the workflow-aware orchestration API supports BASIC without snapshots. The difference is intentional at the two entry points and already disclosed. | Integration caveat | Name `execute_pipeline` explicitly in future integration work. Retain PD-006. | No. |
| A header and throughout, B §§7 and 10, C §6, and both D documents | Market wording in A conflates United Kingdom and GB. Spelling mixes variants such as “artifact” and “artefact”, and “serialization” and “serialisation”. | Editorial | Standardise to Great Britain (GB) where that is the intended market and use consistent British English in prose. Preserve exact code identifiers and quotations. | No for technical meaning. Record the editorial variance in the documentation approval. |

## 5. Approved principles and decision governance

- The contractual subscription episode is the prediction entity. Nowa owns canonical `subscription_id`. Issue it once on authoritative evidence and then persist and reuse it. `customer_id` identifies and groups accounts and is excluded from predictive features. ADR-009, ADR-010, EP-DEC-002, PD-002, BDR-001 and CGQ-001–002 apply.
- Confirmed reactivation after termination creates a new episode and identifier. Earlier history remains intact, and ambiguous identity stays unresolved without heuristic issuance, reuse or attribution. ADR-010, PD-002–004, BDR-002–003 and CGQ-003–004 apply.
- A persistent, client-isolated Episode Identity Registry is an approved architectural requirement. The Registry implementation remains open. ADR-010, PD-001, RPR-005 and RPR-016 apply.
- The five v1.1 datasets remain unchanged: `customers.csv`, `subscriptions.csv`, `subscription_snapshots.csv`, `usage_monthly.csv` and `invoices.csv`. Snapshot optionality follows PD-006. Ground truth and provenance stay internal and negative fixtures remain isolated.
- Historical features respect availability at the observation time (CGQ-013). Confirmed positive, confirmed negative, right-censored, `pending_ascertainment` and ineligible remain distinct internal outcome states. The effective-end hypothesis and pending ascertainment are proposals in CGQ-006 and CGQ-021. Production churn remains open.

The consolidated register is a navigation aid. RPR-004 and RPR-005 preserve approved principles and RPR-015 and RPR-016 retain the open technical mechanisms. RPR-007 is the proposed checksum for future generation outputs and RPR-014 tracks open L2 statistical criteria. The SHA-256 inventory in this document identifies documentation bytes for Activity F. It is separate from RPR-007 and does not approve a generator checksum choice. Proposed, open and blocked entries retain their source dispositions.

## 6. Unresolved decision index

The rows group existing records by dependency for handover. Work packages refer to Section 8 of the consolidated specification. “Open” describes the underlying decision and “blocked” describes the dependent capability. Where a DD-EP entry is pending, the source retains its exact recorded status.

| Source decision ID | Topic | Status | Implementation dependency | Work package | Required resolution point |
|---|---|---|---|---|---|
| SA-001–SA-005, RPR-003, RPR-006, RPR-012 | Logical architecture details, typed configuration, effective fingerprint, stream and run-context boundaries | Proposed | Agree only the subset used by the approved initial configuration and run context. | WP-01, WP-02, WP-08, WP-10 | Before authorising each affected implementation scope. |
| RPR-002 | RNG algorithm and versioned stream derivation | Proposed | Deterministic component streams require selected and pinned derivation. | WP-02 | Before stream implementation and repeatability claims. |
| BDR-013, CGQ-019, RPR-015 | UUID version/provider and allocation, persistence and replay mechanism | Open | Canonical ID generation and exact identity replay are blocked. Fixture-supplied identifiers can support the limited BASIC path. | WP-04, WP-10 | Before implementing canonical allocation or claiming stable replay. |
| DD-EP-003, RPR-016 | Registry implementation | Pending product decision in DD-EP-003. Open in RPR-016. | Technical and operational design and client/source evidence are required. | WP-04 | Before Registry implementation or durable cross-submission identity claims. |
| BDR-014, CGQ-014, DD-EP-001 and DD-EP-005–012 | Episode boundaries, lifecycle events, dependent-record attribution and historical acceptance | Open in BDR and CGQ. Pending client or product decisions in DD-EP. | Complete lifecycle and semantic attribution are blocked for affected records. | WP-04, WP-09 | Before implementing each affected transition or attribution rule. |
| BDR-012 | Billing anchor and period boundaries | Open | Full billing and invoice timing validation is blocked. Approved baseline commercial maths remains applicable. | WP-05 | Before schedule and period reconciliation. |
| BDR-010–011, BDR-015, CGQ-020 | Snapshot convention, usage boundaries, extraction/observation cutoffs and availability representation | Open | Complete temporal and historical availability validation is blocked. | WP-06, WP-09 | Before claiming temporal correctness or historical feature eligibility. |
| CGQ-006–007, CGQ-009–012, CGQ-021, RPR-013 | Synthetic qualification, illustrative windows, ascertainment and censoring | Event qualification open. Hypothesis, windows and outcome handling proposed. | Labelled synthetic outcomes need an approved policy, evidence thresholds and cutoffs. | WP-07, WP-09 | Before computing or validating synthetic labels for modelling. |
| BDR-016, CGQ-008, CGQ-015–016, DD-EP-013, DD-EP-017, RPR-017 | Production churn, eligibility and evaluation strategy | Open in design registers. Product decisions pending in DD-EP. | Production labels, evaluation and eligibility are blocked. | WP-07, WP-09, WP-11 when in scope | Before any production label or model eligibility claim. |
| BDR-017, SA-009 | Official revenue, accounting and CLV semantics | Open | Fictional commercial facts do not establish official CLV or production revenue rules. | WP-05 for commercial dependencies | Before expanding to official calculations. |
| CGQ-022, RPR-010 | Persistent ground-truth and provenance storage | Open | Format, access, retention, cleanup and identity persistence require approval. | WP-10, WP-11 | Before persistence or operational use. |
| RPR-007–009, RPR-011, RPR-014 | Output checksums, byte conventions, dependency provenance, L2 metrics and exact guarantee | RPR-007 and RPR-009 proposed. RPR-008, RPR-011 and RPR-014 open. | Reproducibility claims need declared policies and level-specific results. Exact replay also depends on identity and RNG. | WP-02, WP-10 | Before stating verified L2, L3 or byte-for-byte guarantees. |

## 7. Version-control scope and exclusions

The operation started on `main` at `8d3b1f3ed945d60cba89ebb47e8c66dfbbef8d86`, aligned with the local `origin/main` ref. The starting index and tracked working tree were clean, with 20 untracked documents.

### Commit 1 — Governing and supporting references

```text
docs/04_data/synthetic_business_model_specification.md
docs/04_data/product_decision_proposals.md
docs/04_data/subscription_episode_lifecycle_decision_specification.md
docs/04_data/product_decisions_and_contract_design_assessment.md
docs/04_data/data_quality_implementation_architecture.md
docs/04_data/subscription_episode_data_contract_impact_assessment.md
```

### Commit 2 — Formal design baseline

```text
docs/04_data/synthetic_data_generation_architecture.md
docs/04_data/synthetic_data_generation_rules.md
docs/04_data/synthetic_churn_ground_truth_and_data_quality.md
docs/04_data/synthetic_generation_reproducibility_and_provenance.md
docs/04_data/synthetic_data_generation_design_specification.md
docs/04_data/synthetic_data_generation_design_baseline.md
```

### Exclusions

The following eight documents are outside both commits.

```text
docs/03_architecture/mvp_architecture_and_technical_design.md
docs/04_data/contract_revision_readiness_and_decision_decomposition.md
docs/04_data/customer_data_contract_compatibility_assessment.md
docs/04_data/customer_data_contract_design_proposal.md
docs/04_data/customer_data_contract_episode_alignment_proposal.md
docs/04_data/customer_data_contract_impact_analysis.md
docs/04_data/customer_data_contract_semantic_revision_proposal.md
docs/04_data/subscription_episode_identity_identifier_strategy_assessment.md
```

External evidence and already-tracked governing documents are outside the staging scope. The authorisation covers local documentation commits. Pushes, tags, implementation, dataset generation and changes to code, schemas, tests, the contract, ADRs or product decisions are excluded.

## 8. Proposed change control

This versioning policy is a proposal. Use the smallest review appropriate to the effect. Reference the changed decision, version, review evidence and resulting revision in the relevant document control record.

| Change | Document version | Decision review and ADR | Contract and testing impact | Baseline revision |
|---|---|---|---|---|
| Editorial correction with no change in meaning | Record the correction. For a released controlled document, propose a patch revision if the approved version scheme supports it. | Editorial review confirms unchanged meaning. ADR review is needed only if the correction touches interpretation of an accepted decision. | Confirm no contract or test expectation changes. Check references and formatting. | Refresh the checksum and record the revision if the corrected bytes replace the formal baseline. |
| Minor design change within approved architectural boundaries | Propose a minor revision. | Review affected decision and work package. Update an ADR only if the accepted decision record needs a clarified consequence or amendment. | Screen for contract effects and identify affected tests and acceptance criteria before approval. | Review and approve the revised baseline before adoption. |
| Major change to prediction entity, identity, contract, lifecycle, churn, temporal semantics, security/privacy or approved architecture | Propose a major design revision. Apply the contract's own version rules to any contract change. | Obtain product or architecture approval as applicable. Record an ADR when an accepted architectural decision changes. | Complete contract impact and testing impact assessments, including compatibility, migration, security and revalidation where applicable. | Establish and approve a new identifiable baseline revision before implementation of the change. |

## 9. WP-01 handover assessment

**Ready for planning and approval.** Block A §§6, 7 and 11 define component boundaries, validation before execution and logical configuration groups. Block B supplies population and commercial constraints. Block D provenance §§3, 7 and 9 and consolidation §§5.4, 7 and 8 define effective configuration, run identity, scope, stage evidence and failure behaviour. The initial planning envelope can cover configuration and run context independently of production churn.

| Planning item | Handover requirement |
|---|---|
| Inputs already defined | Scenario and schema version, declared workflow and acceptance scope, output inventory, seed input and scenario references, population bounds, catalogue and policy versions, time bounds and logging/provenance boundaries. |
| Decisions needed | Agree initial YAML/typed-validation choice and schema version, defaults and override precedence, unknown-field and cross-field handling, BASIC inventory, failure and stage result representation, run identifier linkage, and safe effective-config capture. Resolve canonical encoding and fingerprint details only to the extent needed by the authorised scope. Keep unresolved temporal and identity policies explicit and out of initial defaults. |
| Relevant components | Configuration loader/validator, scenario resolution, run coordinator/context, stage diagnostics and initial logical provenance capture. The seed is a configuration input here. Deterministic stream implementation is a separate package. |
| Existing integration boundary | `execute_pipeline` accepts explicit file sources and workflow. BASIC requires customers and subscriptions. Existing schema, referential and narrow temporal checks establish only applicable validation evidence. Generator context and pipeline execution identifiers remain distinct and traceably linked. |
| Required future tests | Unit cases for missing, unknown, ill-typed and contradictory settings, override precedence, version support and deterministic effective resolution. Verify failure before random draws or outputs, sanitised diagnostics, successful/failed stage recording and dependent-stage blocking. Check input scope and policy references with a small integration boundary test once authorised. |
| Acceptance | A valid declared scenario resolves to an immutable effective configuration with identifiable inputs and sanitised trace evidence. Invalid configuration is rejected before generation. Stage results preserve failure and unexecuted outcomes and support only the declared acceptance scope. |
| Scope limits | WP-01 planning does not extend to producing datasets, implementing RNG streams, Registry, target labels, model eligibility, persistent stores or publication. Each implementation scope requires separate approval. |

## 10. NEDS v1.1 governance alignment

| NEDS area | Design and governance evidence | Remaining evidence |
|---|---|---|
| Traceability and decision governance | Document IDs, decision source references, working-tree fingerprints and scope-specific evidence. | Resolve the Phase 3.3.1 source evidence gap under FDB-001. |
| Version control and documentation quality | Exact core and companion lists, source authority, version/status controls, change classification and mixed-spelling findings. | Retain the execution report with the Git revisions and validation results. |
| Reproducibility and configuration | Effective configuration, named streams, dependency provenance and conditional L1/L2/L3 claims. | Approve the selected choices and verify the claimed levels under implementation. |
| Maintainability and incremental implementation | Single-process modular design and bounded work packages with a narrow WP-01 handover. | Authorise each change and verify interfaces and test evidence. |
| Data quality and testing | Declared scope and separate contract, RI, semantic, temporal and eligibility gates. Isolated negative fixtures. | Execute applicable tests and retain actual evidence after implementation is authorised. |
| Security | Internal truth, sanitised diagnostics and explicit publication authorisation. | Approve storage, access, retention and cleanup details and verify controls before operational use. |

This is a design and documentation governance assessment. Future generator compliance requires implementation and validation evidence.

## 11. Approval and handover

The project owner approved the documentation scope and its governance dispositions. Sections 2 and 3 supply the integrity record. WP-01 is the next planning activity. WP-01 implementation requires separate authorisation.
