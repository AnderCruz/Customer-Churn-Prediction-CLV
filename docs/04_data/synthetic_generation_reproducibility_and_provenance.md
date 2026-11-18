# Synthetic Generation Reproducibility and Provenance

**Document ID:** NCI-SYNTH-REPRO-001
**Version:** 0.1
**Status:** Approved for Design Baseline
**Project:** Nowa Customer Intelligence
**Market:** Great Britain (GB)
**Scope:** Design for reproducibility and provenance; no generator, manifest file/schema, or storage architecture is implemented here.

## 1. Purpose and governing references

This document specifies Activity 3.3.3.9 and is one of the two Block D design deliverables. It defines intended reproducibility levels, configuration and random-stream provenance, identity considerations, a logical manifest, output integrity, run lifecycle, and future verification. It preserves the Block A single-process design and the Block B and C rules. It does not authorise implementation or claim that any reproducibility level is currently achieved.

Read this document with the [Block A architecture](synthetic_data_generation_architecture.md), [Block B generation rules](synthetic_data_generation_rules.md), [Block C churn ground truth and data quality](synthetic_churn_ground_truth_and_data_quality.md), approved [Synthetic Business Model Specification v0.2](synthetic_business_model_specification.md), and [Customer Data Contract v1.1](customer_data_contract.md), plus ADR-009/010, approved product decisions, pipeline and DQ specifications.

NEDS v1.1 was reviewed from authoritative project reference material. It is not stored in this repository. The Phase 3.3.1 Synthetic Data Requirements and Population Specification was reviewed from the supplied reference attachment and is also not stored in the repository. Those access limitations are recorded here; neither absence from the repository nor this design is evidence of implementation compliance.

**Current repository observation:** `pyproject.toml` is present, but no dependency lockfile was found in the inspected repository file list. A future dependency fingerprint therefore needs an approved reproducible dependency-resolution/lock strategy before L1/L3 claims can be made. No dependency file is created here.

## 2. Reproducibility objectives

The levels below are proposed engineering classifications. A run may satisfy one level without satisfying the next; the run record must state the evidence and limitations rather than emit a generic “reproducible” claim.

| Level | Objective | Prerequisites | Verification and evidence | Limitations |
|---|---|---|---|---|
| **L1 — Configuration reproducibility** | Identify and reconstruct the validated configuration and software context used by a run. | Immutable effective configuration; versioned configuration schema; default/override resolution; generator and contract versions; runtime and dependency fingerprint; Git revision and dirty state; safe run provenance. | Revalidate the captured effective configuration against its schema and compare its canonical fingerprint; inspect provenance references and explicitly listed external inputs. | Does not promise same random draws, IDs, output rows, or bytes. A Git commit alone does not identify uncommitted files or runtime dependencies. |
| **L2 — Statistical reproducibility** | Repeated runs satisfy declared population characteristics and statistical properties within predeclared tolerances. | L1 context, named random streams and versioned scenario parameters. Decide metric definitions, sample sizes, tolerances and the assessment procedure before observing results (RPR-014). | Repeat independent seeds/runs; compute specified population/behaviour summaries and compare to declared tolerances; retain results and seeds. | Synthetic parameters are engineering assumptions, not estimates of GB market distributions. No universal tolerances or market calibration are approved. |
| **L3 — Exact reproducibility** | Regenerate logically identical output datasets under explicitly identical conditions; byte identity is a stricter, separate claim. | L1; deterministic component streams and draw order; fixed RNG/BitGenerator and versions; resolved identity replay; stable sort/serialization/null/date/decimal conventions; same code/config/dependencies/platform behaviour or verified compatibility; all relevant inputs present. | Repeat run under the same declared context; compare row-level canonical datasets and hashes; separately compare bytes when byte equality is claimed. Record any run-specific metadata excluded from dataset comparison. | UUID allocation, cross-run identity persistence, floating-point/library/platform behaviour, serialization conventions and dependency locking remain unresolved. `run_id` and execution timestamp naturally differ between executions unless excluded from data equivalence. |

No level is currently implemented by a synthetic generator. Level-specific claims require actual verification results; configuration presence or a successful pipeline contract check is not proof of L2/L3.

## 3. Configuration reproducibility

### 3.1 Raw versus effective configuration

- **Raw configuration** is the supplied scenario document and explicit override inputs, including their source/version references. It may contain omitted optional values and unresolved defaults.
- **Effective validated configuration** is the fully resolved, typed, immutable parameter set after safe parsing, default resolution, scenario override rules, cross-field validation, policy references, and rejection of unknown/invalid keys. It is the reproducibility input for generation and is captured separately from the raw source.

Raw and effective values must not be conflated. Record where each default came from and ensure all defaults that affect output are materialised in the effective representation. An override must be explicit, allowed, validated, and traceable to the selected scenario. Validate before consuming random numbers or creating output. No executable configuration expressions or secret values belong in a manifest.

### 3.2 Canonical fingerprint

**PROPOSED DESIGN:** Canonicalise the effective validated configuration with a documented, versioned representation before hashing. The fingerprint should cover:

- Configuration schema identifier/version and canonicalisation version.
- Scenario identifier/version and explicitly materialised parameter values.
- Population targets and profile/distribution parameters.
- Time window, extraction cutoff, period conventions if approved, and requested dataset/workflow selection.
- Master seed and named stream schema/version (or a separate seed fingerprint with explicit linkage).
- Synthetic target-policy identifier/version where outcome truth is generated.
- Identity-policy identifier/version and selected identity mechanism reference, without embedding secret or personal data.
- Relevant approved contract/schema version and output formatting-policy version.

Exclude execution timestamp, generated `run_id`, host-specific absolute paths, credentials, secret values, and user-specific environment values that are not generation inputs. If an external input affects output, record a safe immutable version/content fingerprint and access reference. Never fingerprint by silently omitting an output-affecting value. The hash algorithm and exact canonical encoding must be selected and versioned during implementation; no physical schema or config format is created here.

### 3.3 Environment-independent configuration

Output-affecting parameters belong in validated configuration; machine paths, credentials and deployment-specific endpoints do not. Resolve output location at run time through an approved environment interface and exclude absolute paths from portable configuration fingerprints. Do not include secrets in raw or effective configuration artifacts. If external secret/configuration references are ever required, record a non-sensitive identifier/version only, not the resolved secret.

## 4. Randomness and stream management

The design follows Block A's master seed and named independent streams. Proposed stream names include customer attributes, customer/episode allocation, lifecycle events, billing/payment, usage, and snapshots, with separate scenario namespaces where appropriate. The exact list is a versioned design input, not a final API.

| Concern | Proposed rule | Reproducibility consequence |
|---|---|---|
| Master seed | Require and record one explicit master seed (or approved seed-generation provenance); do not substitute implicit global state. | Same effective seed is necessary, but not sufficient, for exact reproduction. |
| Stream derivation | Derive named streams by a stable, documented derivation method from master seed + stream namespace + stream-schema version; never use process-randomised Python `hash()`. | Adding an unrelated component should not alter the existing component stream. The derivation algorithm/version must be pinned before L3. |
| Component independence | Each component consumes only its own stream(s); record stream names/versions and intended ownership. | A new draw in usage must not shift billing draws; component-level tests can verify this. |
| Scenario-specific streams | Include scenario identity in derivation where scenario variation is intended; retain shared baseline stream identities only where explicitly desired. | Distinct scenarios are reproducible independently and cannot silently alias all random draws. |
| Draw order | Keep deterministic iteration/sorting and fixed draw order within each stream; do not let unordered containers determine consumption order. | Code changes that reorder a component's draws may change its output and require generator/stream version change. |
| RNG implementation | Record library, RNG API, BitGenerator/algorithm, and version. Selecting a concrete generator remains an implementation decision. | Same seed under a different algorithm or library version is not assumed to produce the same sequence. |
| Repeated execution | Reset streams from the captured master seed and effective configuration for a fresh deterministic run; avoid hidden mutable process state. | Re-running must not depend on previous executions in the same process. |
| Dependency sensitivity | Record relevant dependency versions/fingerprint and runtime version; exact compatible environment is needed for L3. | Upgrades can change draw sequences, distribution functions, sorting, and serialization. |
| Parallelisation | Block A's initial design is a local sequential modular monolith. If parallelism is later justified, derive deterministic work-item substreams from stable entity/component keys rather than scheduling order. | Parallel execution must not create schedule-dependent draws. No parallel infrastructure is approved here. |

The isolation goal is that adding a component or an unrelated attribute does not unintentionally perturb previously stable populations. Achieve this through versioned named streams and component-local draw contracts; changes inside a component may intentionally change that component's output and must be reflected in generator/stream version provenance. No seed manager is implemented here.

## 5. Identity reproducibility

Population reproducibility, canonical identity, and identity persistence are separate properties. Same seed may reproduce customer/business attributes while canonical IDs remain different if identity allocation is random; repeating an import of an already established episode must reuse its persisted ID under ADR-010. Reactivation after confirmed termination always creates a separate episode and new canonical ID; prior history remains. Source identifiers are not canonical by default, and ambiguous identity is not heuristically resolved.

| Conceptual approach | Repeatability | Stability/replay and trade-offs | Status |
|---|---|---|---|
| Random UUID allocation plus persisted identity mapping | Run-level IDs differ unless the same mapping is reused. | Supports high-entropy IDs and stable replay when persisted; requires persistence, client isolation, idempotency and a defined mapping lifecycle. A seed alone does not recover an established identity. | UUID is approved; version/provider and synthetic persistence/replay details remain open. |
| Namespace-based deterministic UUID generation | Potentially repeatable for a stable namespace/name tuple. | Requires a canonical, stable name and namespace. Sensitive identifiers must not be embedded or exposed; name changes, collisions/namespace policy, and privacy implications require careful treatment. Deterministic generation does not prove that the name describes a real episode. | Conceptual alternative only; no version/provider/namespace is selected. |
| Registry-backed canonical identity allocation | Run data can reuse stable canonical IDs once an episode is authoritatively recognised. | Required architecture under ADR-010 for durable cross-submission identity, history, and client isolation; depends on persistent Registry and verified evidence. Registry schema/API/storage/operations are not approved. | Registry requirement approved; implementation details remain open and out of scope. |

No approach in this table is selected as the final synthetic UUID mechanism. The implementation must not claim stable cross-run IDs from a seed unless verified and consistent with persistence/reuse requirements. A run's generated identity manifest, if later implemented, must preserve old episode mappings and distinguish fresh synthetic population IDs from established identities.

## 6. Software and environment provenance

The logical provenance record should identify, at minimum:

| Item | Recording rule |
|---|---|
| Git revision | Record commit hash when available. A commit does not include untracked/modified content. |
| Working-tree state | Record clean/dirty state and a safe fingerprint or inventory of relevant changed/untracked source/config files. Do not store file contents containing secrets. |
| Python/runtime | Record implementation/runtime version and platform details only to the granularity needed for repeatability; do not rely on an environment label alone. |
| Dependencies | Record lockfile identifier/hash and resolved package versions; if no lockfile is available, mark the dependency fingerprint incomplete and do not claim L3. The inspected repository has `pyproject.toml` but no dependency lockfile. |
| Generator | Record generator package/version and source revision. Generator does not yet exist. |
| Contract/schema | Record Customer Data Contract version and schema implementation/version used to project/validate. |
| Scenario/configuration | Record scenario ID/version, configuration schema version, effective config fingerprint, and override provenance. |
| Policies | Record identity-policy and synthetic target-policy identifiers/versions; distinguish proposed synthetic policy from production policy. |
| Validation rules | Record rule-set/specification version and each executed stage/rule result, including not-implemented/not-evaluated states. |

Dirty or untracked relevant source makes an L1 reconstruction conditional on the captured file inventory/content fingerprints. A Git commit alone is insufficient. An output-affecting dirty state that cannot be reconstructed precludes an exact reproducibility claim. Never describe a dirty tree as clean or promote an unexecuted validation stage to `PASS`.

## 7. Logical generation manifest

This is a logical manifest specification only. It does not define JSON/YAML/CSV, a physical schema, path, storage backend, or persistent ground-truth architecture. Any format and storage/access/retention design requires later approval.

| Field group | Required fields | Conditional fields | Optional fields |
|---|---|---|---|
| Manifest/run identity | Manifest schema version; unique run identifier; execution timestamp with timezone; run completion state. | Parent/retry run reference for an approved retry/replay. | Operator-supplied non-sensitive run label. |
| Inputs/configuration | Scenario ID/version; configuration schema/version; effective configuration fingerprint; master seed or approved seed provenance. | Raw configuration reference/fingerprint; non-sensitive external-input references. | Human-readable scenario description. |
| Software environment | Generator version (or explicit `NOT_IMPLEMENTED` for design-only/pre-generator record); Git revision where available; dirty-state indicator; Python/runtime version; dependency fingerprint/lockfile status. | Platform/OS and detailed dependency inventory where needed for L3. | Build/CI reference. |
| Policy/schema lineage | Contract version; schema version; identity-policy ID/version; synthetic target-policy ID/version when outcome truth is requested; validation-rule/specification version. | Snapshot/usage/billing/temporal conventions and feature/label cutoff policies when selected. | Rule documentation reference. |
| Random streams | Master seed reference; named stream IDs and stream-schema/RNG algorithm versions. | Per-component stream metadata where component ran. | Non-sensitive RNG diagnostic summary. |
| Expected inventory and scope | Declared execution and acceptance scope, requested output inventory, applicable policies and required validation gates for each intended claim. | Negative-fixture inventory for an isolated fixture run. | Other non-contract artefacts explicitly approved. |
| Actual inventory | Actual output inventory; dataset row counts; file sizes; checksums; output ordering/serialisation version or `OPEN/NOT_SELECTED`. | Ground-truth and manifest checksums if materialised under approved storage design. | Additional non-sensitive counts. |
| Stage outcomes | Separate results for configuration validation, generation, contract/schema validation, referential integrity, semantic attribution, temporal validation, outcome/eligibility validation, provenance/manifest integrity. | Stage-specific rule/finding counts, sanitised diagnostics and warnings. | Timing/duration metrics. |
| Completion/publication | Run completion status, scope and evidence for acceptance and publication eligibility, publication authorisation state, and reason for any blocked claim. | Authorisation reference for the specific output set and scope when explicitly granted. | Non-sensitive review notes. |

Record generation, contract/schema validation, referential integrity, semantic attribution, temporal validation, outcome/eligibility validation and publication authorisation separately. Declare the intended use, output inventory, applicable policies and required gates before execution. Use the [validation scope and publication criteria](synthetic_data_generation_design_specification.md#54-validation-scope-and-publication-eligibility) to distinguish contract-valid synthetic test outputs, fully validated synthetic populations, model-eligible labelled datasets and production-ready outputs. The minimum BASIC slice supports only the contract/schema and applicable referential validation claim.

In the logical manifest, `FAILED`, `BLOCKED`, `NOT_IMPLEMENTED` or `NOT_EVALUATED` for any required gate prevents acceptance and publication eligibility for the corresponding scope. Record omitted gates and their scope rationale. Exclusion from a narrower scope supplies no evidence for a broader claim. Use evidence of a successful evaluation before recording a pass. These are logical manifest outcomes. The existing pipeline retains its own statuses. Publication requires separate explicit authorisation for the eligible output set and scope.

## 8. Output integrity and equivalence

Customer Data Contract v1.1 governs CSV fields and states UTF-8 encoding, comma delimiter, required headers, period decimal separator, ISO 8601 date/datetime form, UTC for timestamps containing time, string identifiers, and empty fields for missing values. Preserve exact contract headers and column order; no internal labels, seeds, events, policy IDs, or provenance columns may be added.

| Integrity concern | Design treatment |
|---|---|
| Checksums | **PROPOSED:** use a cryptographic digest such as SHA-256 over each final file's exact bytes; record algorithm/version. Algorithm selection is a proposal pending implementation decision. |
| Dataset ordering | **PROPOSED:** use deterministic row ordering by primary key, then date/composite key where applicable. The contract does not define row order; adopt only after documenting/versioning this output convention. |
| Column ordering | Follow exact v1.1 contract header ordering; reject unexpected columns. |
| CSV bytes | Preserve UTF-8, comma delimiter, empty missing cells, documented date/time and decimal conventions. Quoting policy, line endings, final newline, float rendering and byte canonicalisation are not fully selected by the contract and remain output-policy decisions. |
| Numeric precision | Preserve contract-compatible numeric values; approved business prices are specified to pennies. Define and version decimal computation/serialization before exact-byte claims; do not silently round arbitrary generated values. |
| File naming/inventory | Use the five established dataset filenames and explicit requested/actual inventory; missing required output is failure, not implicit empty output. |
| Integrity checks | Verify expected files, headers, row counts, byte sizes and checksums after serialization; do not imply checksum validity proves semantic correctness. |

**Logical equivalence** means rows/fields/values are equal after a documented canonical comparison that ignores irrelevant file-byte choices. **Byte-for-byte equivalence** means exact encoded file contents match, including row order, quoting, line endings, null representation, date/time formatting and numeric formatting. The latter requires all serialization conventions and runtime sensitivity to be pinned. Run IDs, timestamps and manifest execution metadata differ naturally and must be excluded or normalised when comparing dataset bytes across runs; do not alter contract outputs to force run metadata into them.

## 9. Run lifecycle, failure, and privacy

The following are **PROPOSED internal generation states**, not new pipeline statuses:

`CREATED` → `CONFIGURATION_VALIDATED` → `GENERATION_IN_PROGRESS` → `GENERATION_COMPLETED` → `VALIDATION_IN_PROGRESS` → `VALIDATION_COMPLETED` → `PUBLICATION_ELIGIBLE` → `PUBLICATION_APPROVED`

Failure branches may enter `VALIDATION_FAILED`, `PUBLICATION_BLOCKED`, or `RUN_FAILED`. The state machine must retain prior stage outcomes and failure reason; it must not rewrite a failed or unexecuted stage as successful. `PUBLICATION_APPROVED` requires a separately authorised approval and is not conferred by this design.

- Validate configuration before consuming randomness or creating final output.
- A failed required generation stage blocks dependent stages. Independent checks may proceed only when their prerequisites hold; record dependency blocks explicitly.
- Write into an isolated run-scoped temporary boundary. Promote the complete output set only after serialisation and all gates required for the declared scope succeed and explicit publication authorisation is recorded. Atomicity mechanism and filesystem/storage choice remain open.
- On failure, keep only diagnostics/provenance allowed by the eventual retention policy; cleanup of partials must be safe and must not erase required audit evidence. Retry/replay semantics and storage are open; a retry gets a linked execution identity and must not silently reuse inconsistent partial state.
- Negative fixtures use a separate output boundary/manifest and never share the valid model-development inventory.
- Logs and manifest exclude secrets, direct personal identifiers, full source rows, and raw target truth unless an explicitly access-controlled internal design later approves the minimum needed. Diagnostics are sanitised and carry safe rule IDs/counts/statuses.
- Least-privilege access, integrity protection, retention, deletion and cleanup are design requirements for any future persisted truth/provenance; their operational policy and storage mechanism remain unresolved (Block C CGQ-022).

## 10. Reproducibility verification strategy

These are future tests and evidence requirements, not executed tests. Exact expected assertions depend on the selected identity/RNG/serialization policies.

| Verification | Expected outcome | Prerequisite / limitation |
|---|---|---|
| Same seed + same effective config + same code/dependencies | Same component-level random inputs and logically equivalent generated rows; byte equality only if L3 serialisation is pinned. | RNG algorithm, draw contract, UUID behaviour and output conventions selected. |
| Different seed | At least configured stochastic fields change; deterministic invariants, schemas and approved business arithmetic remain valid. | Define which outputs are stochastic; IDs may be separately controlled. |
| Independent named streams | Adding a draw/component to usage does not change customer/lifecycle/billing streams not versioned as changed. | Stable stream derivation and component-local RNG consumption. |
| Configuration change | Effective fingerprint changes for output-affecting changes; irrelevant formatting changes to raw config do not change canonical effective fingerprint. | Canonicalisation/default-resolution version selected. |
| Dependency/RNG change | Environment fingerprint differs; exact equality is not presumed. Compatibility can be claimed only after explicit test evidence. | Dependency lock/fingerprint strategy. |
| Identity replay/reactivation | Reimport/replay of established episode retains its canonical ID; confirmed reactivation gets a new ID; prior history remains. | Identity provider/Registry persistence semantics resolved. |
| Manifest completeness | Required lineage, file inventory, stage outcomes and checksums are present; unimplemented checks are explicit, never PASS. | Logical manifest implemented and validated. |
| Checksum consistency | Recomputed checksum matches manifest bytes; mutation changes checksum. | Algorithm/byte serialization version selected. |
| Interrupted run/failed validation | No partial output is marked publication-eligible; failure and prior stage results remain inspectable. | Run-state, atomic promotion and cleanup policy implemented. |
| Negative-fixture isolation | Fixture files never appear in valid output inventory; expected defect fails at expected gate; no mutation of source valid fixture. | Separate output boundary and validator coverage. |
| Repeatability after code change | Generator/stream version changes when output-affecting draw contract changes; compare only with declared compatibility expectations. | Versioning and compatibility policy. |

## 11. Decision register

Statuses use **Approved**, **Proposed**, **Open**, or **Blocked**. Approved entries restate existing decisions; Proposed entries are design recommendations; Open entries remain undecided; Blocked identifies a dependent implementation that cannot safely proceed. This register does not change decisions in ADRs or Blocks A–C.

| Decision ID | Topic | Existing decision or proposal | Status | Rationale | Dependencies | Implementation impact |
|---|---|---|---|---|---|---|
| RPR-001 | Reproducibility levels | Use L1 configuration, L2 statistical, L3 exact as separate proposed claims. | Proposed | Prevents broad unsupported “reproducible” assertions. | Evidence protocol and project acceptance. | Manifest/report states level and evidence; none currently implemented. |
| RPR-002 | Named random streams | Use component/scenario-specific streams and stable versioned derivation; never process `hash()`. | Proposed | Limits unrelated random draw cascades. | RNG/derivation selection and stream schema. | Seed manager and tests required. |
| RPR-003 | Effective configuration fingerprint | Fingerprint canonical, fully resolved, validated config and policy refs; exclude secret/runtime path data. | Proposed | A scenario name or raw YAML alone does not reconstruct effective values. | Canonical encoding/hash and config schema. | L1 requires manifest and canonicalisation implementation. |
| RPR-004 | Canonical UUID lifecycle | Issue a Nowa-owned UUID once for an authoritatively established episode, persist and reuse it, and issue a new ID on confirmed reactivation after termination while preserving prior history. Leave ambiguous identity unresolved. | Approved | Preserves canonical identity across submissions and separates reactivated episodes. | ADR-010, PD-002, BDR-002, CGQ-002 and CGQ-003. See RPR-015 for the open mechanism. | Enforce issuance, reuse and history invariants when identity is implemented. |
| RPR-005 | Registry requirement | Require a persistent, client-isolated Episode Identity Registry for durable identity. | Approved | Recognised episodes need stable identities and traceable history across submissions. | ADR-010 and PD-001. See RPR-016 for open design details. | Preserve the Registry requirement in identity design. |
| RPR-006 | Manifest | Maintain a logical manifest with distinct stage completion and publication states. | Proposed | Provenance and honest validation status are required for replay/audit. | Manifest schema/format, access, storage and lifecycle decisions. | No manifest file/schema created here. |
| RPR-007 | Output hash | Use SHA-256 as the output checksum. | Proposed | Supports file integrity checks with a cryptographic digest. | RPR-008 for output ordering and serialisation. | Compare checksums over actual file bytes and keep the checksum separate from evidence of logical equivalence. |
| RPR-008 | Output ordering and serialisation | Select row order, line endings, quoting, numeric rendering and null representation within existing contract requirements. | Open | Contract v1.1 leaves byte representation partly unspecified. | Contract, serialiser and runtime policy. | Logical reproducibility may precede byte-level reproducibility. |
| RPR-009 | Dependency provenance | Record runtime/package versions and dependency fingerprint; no lockfile was found in inspected repo. | Proposed | Commit alone does not identify resolved environment. | Dependency resolution/lock strategy. | L1 can be limited until a verifiable dependency snapshot exists; L3 blocked. |
| RPR-010 | Persistent truth/provenance storage | Format, access, retention/cleanup, identity persistence and reproducibility policy remain open (CGQ-022). | Open | Logical manifest/truth does not approve durable storage. | Security/governance; ADR-010; data retention. | Persistent implementation blocked; no backend selected. |
| RPR-011 | Exact reproducibility guarantee | Decide the extent of any project-wide L3 guarantee. | Open | UUID, RNG, environment and byte conventions are unresolved. | RPR-002, RPR-003, RPR-008, RPR-009 and RPR-015, with RPR-006 and RPR-007 for provenance and output evidence. | Identical bytes and stable cross-run IDs each require matching evidence. |
| RPR-012 | Run and publication states | Use proposed internal run states distinct from pipeline stage statuses; publication approval remains separate. | Proposed | Prevents conflating generation, validation and approval. | Run lifecycle/approval ownership. | Do not add statuses to existing pipeline model without approval. |
| RPR-013 | Synthetic target hypothesis | Use the proposed Block C effective-end hypothesis for synthetic outcome testing under an identified and approved configuration. | Proposed | Provides a testable synthetic outcome rule. | CGQ-006 and its qualification, timing, ascertainment and censoring dependencies in CGQ-007–CGQ-012 and CGQ-021. See RPR-017 for production policy. | Record the synthetic target-policy version when the outcome stage runs. |
| RPR-014 | Statistical reproducibility metrics and tolerances | Select L2 metrics, assessment protocol, sample sizes and tolerances for the declared scenario before evaluating results. | Open | Statistical acceptance needs criteria set before observing results. | RPR-001 and RPR-002, scenario configuration and validation-rule version. | L2 claims require approved criteria and recorded comparison evidence. |
| RPR-015 | UUID implementation and synthetic identity replay | Select the UUID version/provider and the synthetic identity allocation, persistence and replay mechanism. | Open | Stable replay depends on how canonical identities are issued and reused. | RPR-004, RPR-005, RPR-016, BDR-013 and CGQ-019. | Stable identity replay and related L3 claims require implementation and verification. |
| RPR-016 | Registry implementation | Decide Registry technical and operational details, including how client/source evidence supports durable mappings. | Open | The approved Registry requirement leaves implementation details undecided. | RPR-005, ADR-010, PD-001 and DD-EP-003. RPR-010 concerns separate ground-truth and provenance storage. | Registry implementation depends on a separate design decision and authorisation. |
| RPR-017 | Production churn and eligibility policy | Resolve production churn qualification, target, observation and horizon cutoffs, censoring and model eligibility. | Open | Production labels and eligibility require separately agreed policy and evidence. | BDR-015, BDR-016, CGQ-008, CGQ-016, DD-EP-013 and DD-EP-017. See RPR-013 for the synthetic hypothesis. | Production model-ready output remains blocked. |

## 12. Implementation readiness

| Component | Readiness | Reason |
|---|---|---|
| Provenance field inventory and L1/L2/L3 definitions | Ready for implementation | Logical requirements and evidence distinctions are specified without requiring a backend. |
| Effective configuration capture | Ready with approved configuration | Block A recommends validated versioned configuration; exact schema/defaults and canonical encoding require approval. |
| Master seed and named-stream manager | Ready with approved configuration | Block A stream boundaries exist; algorithm, generator version and derivation method must be selected and pinned. |
| Environment/dependency fingerprint | Blocked by open decision | No dependency lockfile was found; reproducible dependency capture strategy is undecided. Basic runtime/version reporting can be developed independently. |
| Canonical identity replay | Blocked by open decision | UUID version/provider, Registry mechanism and persistence/replay semantics remain open. |
| Logical manifest model | Ready for implementation | Field groups and stage distinctions are specified; physical format and persistence remain separate decisions. |
| Persistent manifest/ground-truth storage | Blocked by open decision | Format/backend, access, retention, cleanup and identity persistence have not been approved. |
| CSV logical integrity checks | Ready with approved configuration | Contract encoding/header/date conventions are known; row order and byte canonicalisation remain unselected. |
| Byte-for-byte L3 verification | Blocked by open decision | RNG/identity/dependency lock and serialization policies must be pinned first. |
| Run lifecycle/failure states | Ready with approved configuration | Proposed states and failure principles are specified; they must remain internal and be mapped to existing pipeline outcomes without changing pipeline status enums. |
| Outcome/eligibility reproducibility | Blocked by open decision | Target qualification, `A`, `C`, temporal policy and model eligibility remain unresolved. |

Configuration/provenance design, current pipeline stage recording, and test scaffolding can be developed without approving production churn. Exact IDs, persisted truth, byte-level L3, and labelled model eligibility cannot.

## 13. NEDS v1.1 alignment

NEDS v1.1 was reviewed from authoritative project reference material. This matrix records design alignment, not implementation compliance.

| NEDS requirement | Design alignment | Evidence required later |
|---|---|---|
| Reproducibility | L1/L2/L3 claims, stable streams, effective config, runtime/dependency lineage, manifest, and verification plan are separated. | Execute repeatability tests in a controlled/versioned environment; report actual level and limitations. |
| Modularity and maintainability | Provenance, config, RNG, identity, serializer, validators and run lifecycle remain bounded responsibilities under the existing small modular monolith. | Keep modules/interfaces explicit; justify any architectural expansion. |
| Configuration and dependency management | Requires validated effective config and records dependency fingerprint; no new config/dependency implementation is prescribed. | Version/lock dependencies; validate configuration before generation. |
| Data quality and reliability | Stage results, output inventories, checksums and validation boundaries remain distinct; non-evaluated stages are never passes. | Implement checks and preserve errors/warnings without claiming unseen validation. |
| Error handling and logging | Defines failure propagation, no partial valid publication, safe diagnostics and run states. | Demonstrate failed-stage behaviour and sanitised logs. |
| Security and privacy | Excludes secrets/personal data, requires least privilege, integrity protection and retention decisions. | Establish operational controls and review dependencies/vulnerabilities. |
| Testability | Defines unit/integration/end-to-end repeatability and failure tests. | Execute under authorised implementation work; evidence must be actual results. |
| Technical justification and scope control | Keeps exact reproducibility and storage architecture open; rejects unnecessary infrastructure. | Record rationale and approval for every implementation choice. |
| British English and traceability | Uses British English, stable IDs, explicit statuses, versions and policy references. | Maintain language and decision links as documents/code evolve. |
| Incremental development | Verification is staged by level and component; no production implementation is authorised by this design. | Implement in reviewable increments and do not conflate design approval with production readiness. |

## 14. Risks and limitations

- A commit hash without dirty-state and dependency information cannot reconstruct a run.
- Reproducible pseudo-random attributes do not establish stable canonical identity across repeated submissions.
- Deterministic IDs can expose linkage or encode sensitive information if namespace/name inputs are poorly chosen; no mechanism is selected.
- Library/RNG upgrades and platform floating-point/CSV differences may invalidate exact comparisons.
- An execution timestamp and run ID make the manifest run-specific even when data rows are equivalent.
- Incomplete validation or unimplemented semantic/temporal/outcome gates must block the corresponding publication claim.
- No persistent truth/manifest storage, access-control implementation, retention policy, or deletion process is approved.
- No production churn definition, survival architecture, or model eligibility policy is approved.

## 15. Traceability

This v0.1 design for Activity 3.3.3.9 is Approved for Design Baseline. It preserves decisions from Blocks A–C, NEDS v1.1, the approved business model, contract and identity architecture. It does not create a seed manager, generator, physical manifest/configuration, dependency lockfile, storage system, dataset, or test. Implementation planning and approval are separate subsequent activities.
