# WP-01 Configuration and Run Context Technical Plan

| Document control | Value |
|---|---|
| Document ID | NCI-WP01-PLAN-001 |
| Version | 0.1 |
| Status | Approved — Technical Plan |
| Approval date | 18 November 2026 |
| Implementation | Subject to separate incremental authorisation. |
| Project | Nowa Customer Intelligence |
| Market | Great Britain (GB) |
| Engineering Standard | NEDS v1.1 |

## 1. Executive Technical Summary

WP-01 would give the future synthetic generator a deterministic configuration boundary and an in-memory record of each execution attempt. The proposed design uses safe YAML parsing, strict Pydantic validation, one level of named scenario overrides and immutable effective values. A small run context would record declared scope, stage outcomes and initial provenance. The existing CSV pipeline would remain the downstream validation boundary. The project owner approved the technical plan and the WP-01.1 design decisions on 18 November 2026. Section 15 records the original approvals and subsequent Batch 01 authorisation. All four WP-01 increments are implemented and tested, with technical acceptance recorded in §21.

## 2. Project Context and Approved Baseline

Inspection on 18 November 2026 found repository root `/home/anderjcruz/NowaAnalytics-Projects/NA01-Customer-Churn-Prediction-CLV`, branch `main` and HEAD `93bb09299bbbd580d2e9bb13e21a06deaf1ee6ce`. The branch was two commits ahead of and zero behind the local `origin/main` ref. The index and tracked tree were clean. Eight pre-existing architecture, contract and identity review documents were untracked. This assessment uses local refs.

The Phase 3.3.3 approval applies to design documentation. The original Phase 3.3.1 population specification and independent approval evidence remain unverified under FDB-001. The approximate 1,000 customers, 1,100–1,400 episodes and 36 months are configurable engineering anchors for fictional data. They are retained as scenario guidance, with explicit values supplied by the scenario author under this proposal.

## 3. Scope and Explicit Exclusions

The proposed implementation covers local configuration loading, validation, value resolution, immutable configuration, run metadata, declared scope, stage lifecycle, sanitised diagnostics and initial provenance. It fits the approved single-process modular architecture.

Dataset creation, schema or contract changes, RNG streams, canonical episode allocation or replay, Registry implementation, lifecycle policy, production churn, outcome labels, eligibility, publication, persistent manifests and ground-truth storage remain outside WP-01. The initial 90-day history and 30-day prediction hypotheses in the project configuration supply no WP-01 defaults. The planning deliverable is this Markdown document. Implementation, tests and configuration files require their respective implementation authorisation.

## 4. Reviewed References

| Reference | Authority or contribution |
|---|---|
| [Block A architecture](../04_data/synthetic_data_generation_architecture.md) | §§6–7 and 11–14 define component boundaries, configuration and proposed SA decisions. |
| [Block B generation rules](../04_data/synthetic_data_generation_rules.md) | §8 preserves BDR-005/006 and distinguishes approved population anchors from later behaviour choices. |
| [Block C ground truth and quality](../04_data/synthetic_churn_ground_truth_and_data_quality.md) | §§7 and 10 distinguish validation gates and internal outcome policies. |
| [Block D reproducibility and provenance](../04_data/synthetic_generation_reproducibility_and_provenance.md) | §§3, 7, 9 and 11 define effective values, evidence and deferred reproducibility decisions. |
| [Block D consolidated design](../04_data/synthetic_data_generation_design_specification.md) | §§5.4, 7 and 8 define claim boundaries, dependencies and work packages. |
| [Baseline register](../04_data/synthetic_data_generation_design_baseline.md) | FDB-001/002, original decision authority and §9 WP-01 handover. |
| [Customer Data Contract v1.1](../04_data/customer_data_contract.md) | Governs external CSV inventory, grain, fields and validation obligations. |
| [Synthetic Business Model v0.2](../04_data/synthetic_business_model_specification.md) | Governs fictional catalogue and GBP commercial assumptions. |
| [ADR-009](../03_architecture/architecture_decisions.md#adr-009-subscription-level-churn-prediction) and [ADR-010](../03_architecture/adr_episode_identity_and_identifier_management.md) | Govern subscription episode prediction, canonical identity, reactivation and the durable Registry requirement. |
| [PD-001–PD-007](../04_data/product_decision_proposals.md) and [Episode and Lifecycle Specification](../04_data/subscription_episode_lifecycle_decision_specification.md) | Individual approved decisions govern their domains. PD-006 governs snapshots. Open lifecycle decisions retain their status. |
| [Orchestration](../03_architecture/pipeline_orchestration_specification.md) and [Execution Summary](../03_architecture/pipeline_execution_summary_specification.md) | Define workflow inputs, operational errors, evidence and downstream outcomes. |
| [Data Quality Specification](../04_data/data_quality_specification.md) and [DQ Implementation Architecture](../04_data/data_quality_implementation_architecture.md) | Describe rule intent and design. Source and tests establish current capability where the supporting status narrative is stale. |
| NEDS v1.1 | Reviewed the authoritative external `../NA Enginnering_Development_Standard_NEDS.md`. SHA-256 matches the baseline fingerprint `e2b165a04a1213c2367968cc8938fafadfab27fa19bdd4570b84a918606a025c`. |

## 5. Current Repository Implementation Assessment

- `pyproject.toml` targets Python 3.12 and already declares PyYAML 6.x and Pydantic 2.x. Pytest and Ruff are development dependencies. The proposed plan requires no dependency changes.
- `configs/config.yaml` is general project configuration, with paths, `Europe/London`, an `INFO` setting and provisional modelling settings. The inspected source has no YAML loader, Pydantic configuration model, central logging setup or synthetic run context to extend.
- The `src/nowa_customer_intelligence` package separates CSV ingestion, type normalisation, schemas, validation and pipeline orchestration. `execute_pipeline` accepts explicit dataset paths and a workflow. It applies discovery, technical checks, referential integrity and DQ, and returns a Pipeline Execution Summary (PES) and an optional DQ report. Current temporal validation is limited to the implemented date-order rules.
- The code uses frozen dataclasses, tuples and read-only maps in the pipeline and DQ models. Typed `ValueError` subclasses already distinguish ingestion, DQ, discovery and operational input failures. A `PipelineOperationalInputError` can carry processing data in attached results, so its raw payload is unsuitable for logging.
- Existing tests include `tests/unit/pipeline/test_discovery.py`, `test_models.py`, `test_reporting.py`, `test_aggregation.py`, `test_quality.py` and DQ tests under `tests/unit/data/validation/`. `tests/integration/test_pipeline_execution.py` covers required and optional inputs, present-empty handling, workflow differences, errors and preservation of stage evidence. `tests/integration/test_csv_ingestion.py` covers the direct ingestion interface. Tests were inspected as source.

## 6. Functional Requirements

| ID | Future behaviour | Verification boundary |
|---|---|---|
| FR-01 | Parse one explicit versioned scenario document, reject unsafe or malformed input, unsupported versions, wrong types and unknown fields. | Parser and schema tests. |
| FR-02 | Select one named scenario, resolve defaults and approved override fields deterministically, then reject inconsistent effective values. | Precedence, isolation and cross-field tests. |
| FR-03 | Return deeply immutable effective values and allowlisted value origins after full validation. | Mutation, input-aliasing and repeat-resolution tests. |
| FR-04 | Capture one run identity, UTC timestamp, workflow, intended scope, inventory and gate requirements. | Run-context and workflow matrix tests. |
| FR-05 | Preserve started, completed, failed, dependency-blocked and unexecuted evidence with explicit stage identity. | Transition and failure propagation tests. |
| FR-06 | Return bounded sanitised diagnostics and capture initial in-memory provenance. | Log capture, diagnostic and provenance tests. |
| FR-07 | Reject invalid configuration before run execution, seed-stream use, CSV work or output creation. Preserve the pipeline interface and contract. | Spies, filesystem assertions and existing pipeline regression tests. |

## 7. Non-Functional Requirements

| Area | Measurable acceptance evidence |
|---|---|
| Modularity and maintainability | Each proposed module has a single responsibility boundary in §14. No changes to existing pipeline or contract interfaces are necessary. Public functions have type hints and targeted tests. |
| Reliability | Each invalid input case returns the documented error category. A failed stage retains its outcome, dependent stages have zero invocations and previously completed records are retained. |
| Security and logging | Tests inject secret-like values, paths, control characters and large exception strings. Captured diagnostics contain only the documented fields and stay within the configured structural limits. |
| Determinism | Repeated resolution with identical inputs, including reordered mapping keys, produces equal logical values and origins independent of clock, environment and working directory. |
| Testability | Clock, identifier and source metadata can be supplied by the caller or tests. Local tests use no network or external services. |
| Local performance | Load once per attempt and validate per supplied configuration field, using a bounded document. Avoid per-row work, network calls and output discovery during resolution. Review representative configuration timing before introducing a target. |
| Dependencies and compatibility | Use existing supported dependency ranges. Treat v1 field meanings as stable, reject unsupported versions and preserve the existing project config and pipeline behaviour. |
| Engineering evidence | Capture applicable Pytest and Ruff results, revision and review decisions against §20 before reporting implementation acceptance. |

## 8. Proposed Configuration Architecture

### WP-01.1 — Safe YAML intake

Accept one explicit UTF-8 YAML document as bytes. The caller supplies any file-reading boundary. Reject invalid UTF-8 before passing text to PyYAML. Use SafeLoader as the construction foundation, with a bounded event preflight and a duplicate-key check. The following limits are approved under WP01-D-001. They apply to the entire document, including unselected scenarios.

| Limit | Proposed bound and rationale | Boundary test |
|---|---|---|
| Encoded size | 65,536 bytes inclusive, checked before decoding. Sufficient for a compact local scenario catalogue and bounds scanning work. | Accept a valid padded document at the limit and reject one byte over. |
| Collection depth | 8 inclusive, with the root mapping at depth 1 and each nested mapping or sequence adding one. The deepest supported field is within 5 collection levels. | Depth 8 reaches schema validation; depth 9 fails preflight. |
| Scenario count | 32 entries inclusive in `scenarios`. Keeps a single catalogue reviewable. | Accept 32 valid definitions and reject 33. |
| YAML nodes | 2,048 inclusive. Count each scalar, including mapping keys, and each collection once. This bounds the width of the constructed tree independently of byte length. | A parser-level synthetic case at 2,048 reaches schema validation; 2,049 fails preflight. |
| Scalar length | 256 Unicode code points inclusive for keys and values as emitted by the parser. Identifiers and supported literals are short. | Test 256 and 257 code points, including multibyte UTF-8 and an escaped scalar. |
| Integer input | Canonical signed decimal syntax `0` or `-?[1-9][0-9]*`, within signed 64-bit range. Check digit length and compare against the limit before integer conversion. This bounds input conversion and does not select a seed representation for WP-02. | Test both signed endpoints and one outside each; separately check field constraints such as a non-negative seed. |

Preflight must finish before constructing any YAML objects. Stream events from the same immutable decoded text, counting documents, collection depth, nodes and scalar lengths. Reject zero or multiple documents, aliases, anchor declarations, every explicit tag (including standard tags), and YAML directives. Require a mapping root and scalar string keys. Track decoded keys per mapping and reject duplicates, including a quoted key that matches a plain key, and the reserved merge key `<<` even when quoted. Check the scenario count while traversing the root `scenarios` mapping. Never construct a forbidden or over-budget tree.

After preflight, use a SafeLoader subclass scoped to this loader, leaving global PyYAML behaviour intact. Restrict scalar resolution to canonical decimal integers, lowercase `true`, `false` and `null`, plus strings. Reject ambiguous plain scalars such as YAML 1.1 boolean variants, leading-zero or prefixed numbers, sexagesimal forms, floats, blank values and implicit dates. Quoted scalars remain strings. Check the scalar style for history dates during preflight. Require a single- or double-quoted value and validate its ISO syntax and calendar date in the typed schema. Retain constructor-side duplicate-key protection. Reject nested collections used as mapping keys and explicit executable tags. The loader performs no file includes or environment interpolation. Exercise each prohibited construct and invalid UTF-8 independently.

### WP-01.1 — Structural field catalogue

After parsing, dispatch on `config_schema_version`, then use strict Pydantic validation with unknown fields forbidden. A schema model represents the complete base and the shape of each patch. All scenario entries pass this boundary, including unselected entries. Null is invalid for every v1 field. An omitted optional field differs from an explicit null.

| Group | Exact proposed structure and WP-01.1 rules |
|---|---|
| Root | Exactly `config_schema_version`, `base` and `scenarios`, all required. Version is an integer, currently `1`. The other two fields are mappings. |
| `base` | Required `population`, `history`, `master_seed`, `workflow`, `execution_scope`, `requested_outputs` and `policy_refs`. Optional `diagnostics`. |
| `scenarios` | Non-empty mapping of case-sensitive IDs matching `[a-z][a-z0-9]*(?:[-_][a-z0-9]+)*` to entries. Each entry requires positive integer `scenario_version` and may include `patch`. No other entry keys. |
| `population` | Mapping of required strict positive integers `customer_count`, `episode_count_min` and `episode_count_max` in the base. |
| `history` | Mapping of required `start_date` and `cutoff_date` in the base. Each value is a quoted, valid calendar date in `YYYY-MM-DD` form. |
| `master_seed` | Strict non-negative integer within the intake representation. RNG-specific constraints remain with WP-02. |
| `workflow` and `execution_scope` | Strict string literals. Workflow is `BASIC` or `TEMPORAL`. Scope is `configuration_only` in v1. |
| `requested_outputs` | Sequence of strings, restricted to the five supported filenames in §10. Cardinality, duplicates and workflow coverage are effective checks. |
| `policy_refs` | Mapping with required string literals `contract_version` = `'1.1'`, `business_model_version` = `'0.2'` and `snapshot_decision` = `PD-006`. |
| `diagnostics` | Optional mapping. If present, requires `level` with literal `INFO` or `WARNING`. Default materialisation is WP-01.2. |
| `scenarios.<id>.patch` | Optional mapping that can be empty. Allowed fields are `population` (any subset of its three leaves), `history` (either or both dates), `master_seed` and `diagnostics.level` using its nested mapping. Every supplied leaf follows the same type and local constraints as the base. Unknown and forbidden fields are rejected. |

The loader returns `ValidatedConfiguration`, a structurally validated document with known field names and valid leaf types. The object is unresolved and cannot create a run context. Relationships between fields are checked after resolution in WP-01.2. Unsupported versions require explicit version dispatch and a documented migration or compatibility decision. The existing project YAML remains independent.

## 9. Scenario and Effective Configuration Design

Resolution order is **approved schema defaults → explicit base → selected scenario patch → explicit caller override**. The sole schema default is diagnostic level `INFO`, approved within Batch 01. Assign no implicit workflow, seed, population, policy or time window. WP-01.1 validates base and every scenario patch structurally. WP-01.2 selects the exact scenario ID, validates any caller-supplied override against the same patch allowlist, and checks the selected effective values for completeness and consistency. A separate test should prove an unused scenario's malformed fields cannot pass the document boundary.

Allow scenario patches and caller overrides on the declared population leaves, both history dates, seed and diagnostic level. Validate every supplied layer's field types and allowed paths independently. Apply per-leaf replacement with explicit origin tracking. Base workflow, scope, inventory and policy references stay fixed for the document. Scenario metadata is owned by its entry. Unknown paths, forbidden fields, implicit removals, inheritance chains and list merging are rejected. Require a different document for a different workflow or scope. Use one explicit allowlist for patch and caller override paths to avoid divergence.

Proposed interfaces are `load_configuration(document: bytes) -> ValidatedConfiguration` and `resolve_configuration(document, scenario_id, overrides=None) -> EffectiveConfiguration`. The former holds structurally validated but unresolved inputs. The latter materialises every effective value and its origin, confirms the cross-field and scope rules, and returns a frozen typed object with frozen nested records and tuples. Copy collections into immutable values to break aliases to caller-owned data. Keep origin records as immutable field-path/layer pairs with safe source identifiers alongside the effective values.

WP-01.2 checks `episode_count_min <= episode_count_max` and `start_date < cutoff_date` after all layers are applied. It also validates non-empty, duplicate-free planned inventory against the declared workflow and verifies that the scope remains configuration-only. Reject invalid merged combinations without correction. An unselected patch is structurally checked in WP-01.1 and receives effective checks only when selected. Only a fully resolved and cross-field-validated `EffectiveConfiguration` is accepted by the WP-01.3 context factory. Reject raw documents, unresolved objects and mappings passed to that factory.

Generation-relevant values include scenario ID and version, config version, population, history, seed, requested inventory, workflow and policy versions. Provide a separate allowlisted diagnostic projection with schema version, safe scenario ID, workflow, scope and inventory. Omit seed, raw YAML, overrides, host paths and external credentials from that projection. The future fingerprint must cover all output-affecting values, version its encoding, and exclude runtime timestamps, run IDs and machine-specific paths. WP-01 preserves the input boundary for future fingerprinting. Formal fingerprint and L1 evidence remain deferred.

## 10. Run Context and Execution Scope

Propose `create_run_context(effective, *, clock, run_id_factory, source_metadata) -> RunContext`. It accepts only a fully resolved configuration, reuses its immutable values and snapshots trusted runtime metadata. Generate a standard-library UUID4 for each attempt and expose it with a `gen-` prefix. This choice gives local attempts independent correlation IDs without services or seed-stream use. Tests supply fixed IDs and times. Generator run ID, later pipeline `run_id`, scenario ID, master seed and canonical `subscription_id` have distinct purposes. The future pipeline ID is an independently allocated value linked only when downstream work occurs.

The initial stage plan can contain configuration validation evidence and context preparation. Record completed configuration validation only after successful resolution, using measured times when supplied. Capture unknown timestamps explicitly. The context contains run ID, scenario ID/version, UTC start, config version, workflow, `configuration_only` execution scope, planned inventory, policy references, applicable gate requirements, outcomes, diagnostic references and initial provenance. Reuse `PipelineWorkflow` at the typed interface. Reuse the existing filename map to constrain inventory. WP-01.1 checks scope and workflow literals and the filename vocabulary. WP-01.2 checks effective inventory completeness and compatibility against PD-006 and orchestration requirements before a context can be created.

| Supported filename | BASIC | TEMPORAL |
|---|---|---|
| `customers.csv` | Required | Required |
| `subscriptions.csv` | Required | Required |
| `subscription_snapshots.csv` | Optional | Required |
| `usage_monthly.csv` | Optional | Optional |
| `invoices.csv` | Optional | Optional |

The supported contract inventory is the full list above. Planned requested outputs are the declared subset of filenames for later work. The required inputs are files that a downstream pipeline execution must receive for its declared workflow. An actual generated file is an execution artefact, and validation evidence is a result from a gate that ran. WP-01 records the declaration only. For `configuration_only`, actual generated inventory is empty and dataset validation is outside scope. Neither planned names nor successful configuration validation establish that a dataset exists or that a dataset gate passed.

The minimum BASIC inventory is customers and subscriptions. BASIC with snapshots can validate supplied snapshots under the pipeline contract. Future generator snapshot production remains subject to Block B and unresolved conventions. TEMPORAL can be declared and checked for inventory completeness during configuration work. Its runtime semantic readiness requires separate evidence. At the pipeline boundary absent optional inputs remain absent, present-empty inputs retain their existing handling, and supplied invalid inputs remain failures. The direct loader requires snapshots unconditionally.

| Claim | Evidence required in later work |
|---|---|
| Contract-valid synthetic test outputs | Actual outputs passing schema and applicable referential checks for the declared inventory. |
| Fully validated synthetic population | Applicable generation, semantic attribution, temporal and quality gates pass with evidence for the declared scope. |
| Model-eligible labelled dataset | Separately approved and evaluated outcome, ascertainment, censoring, historical feature availability and eligibility rules. |
| Production-ready output | Separate operational, security and release evidence and approvals. |

WP-01 records intended gates for future inventory and execution. Its only applicable product of execution is configuration/run-context evidence. Mark downstream gates outside this scope explicitly. An intended gate with absent capability or evaluation supplies no pass, and a pipeline summary supplies only the evidence it actually records.

## 11. Stage Management and Failure Behaviour

Use a small run-local tracker and immutable outcome snapshots. Record stage ID, scope, status, optional UTC start and finish, dependency ID where applicable, and a bounded diagnostic code/reference. The caller owns explicit sequential control. Capability states and requirements can be recorded in a separate gate list attached to the context. There is no scheduler, pipeline enum change or publication lifecycle.

| Proposed generator status | Meaning and transition |
|---|---|
| `NOT_RUN` | Declared initial state. No timestamps. Retain it for stages left unexecuted without a failing prerequisite. |
| `RUNNING` | Transition from `NOT_RUN` after dependencies succeed. Record start once. |
| `SUCCEEDED` | Transition from `RUNNING` with completion time and observed evidence. |
| `FAILED` | Transition from `RUNNING` with completion time and a diagnostic reference. Preserve prior results. |
| `BLOCKED` | Transition from `NOT_RUN` when a required prerequisite fails or is blocked. Record the prerequisite without fabricating execution timestamps. |

Reject unknown stage IDs, duplicate starts, completion without a start, transitions from terminal states and completion before start. Configuration failure emits a typed caller-visible error before context creation. On later stage error the caller records failure, marks dependent work blocked and propagates a typed error with a safe code and access to the outcome snapshot. Catch specific operational errors for classification. At the outer run boundary, preserve unexpected application failures with a generic safe diagnostic and propagate a typed wrapper to the controlled caller. The public stage wrapper retains a fixed failure code and outcome evidence. A caller requiring restricted diagnostics can capture the original exception within its operation boundary. Interrupts and process termination retain their normal semantics. Downstream pipeline outcomes remain the pipeline's own evidence and are referenced without translating partial, skipped or unimplemented outcomes into success.

## 12. Initial Provenance and Logging

Capture run ID, scenario ID/version, config schema version, the in-memory effective configuration reference, UTC execution timestamp, Python version, source revision and dirty-state indicator, policy versions, scope, inventory, value origins and stage results. Accept source metadata from the caller. Represent unavailable revision or dirty state explicitly as unknown. A supplied dirty flag covers relevant modified or untracked inputs under the caller's declared scope. No implicit Git subprocess or inference from the absence of metadata.

### WP-01.1 — Safe error contract

The proposed `ConfigurationError(ValueError)` carries a stable code and immutable issue details. Proposed subclasses distinguish parsing, intake limits, unsupported versions and schema validation. Unknown fields use the schema subclass with a distinct code. The exception's string representation contains only the stable code and its fixed message. The loader does not log or expose parser/Pydantic exceptions or their input-bearing exception context to callers.

| Code | Trigger and safe details |
|---|---|
| `CONFIG_PARSE_ERROR` | Invalid UTF-8, YAML syntax, document count, duplicate keys or unsupported constructs/scalars. Include optional 1-based line and column from safe parser metadata when available. |
| `CONFIG_SIZE_LIMIT_EXCEEDED` | Any byte, depth, scenario-count, node, scalar-length or integer-representation bound exceeded. Include only the fixed limit name. |
| `CONFIG_SCHEMA_VERSION_UNSUPPORTED` | Valid integer version outside the supported schema versions. Do not echo it. A missing or wrongly typed version is a schema validation error. |
| `CONFIG_SCHEMA_VALIDATION_ERROR` | Missing field, invalid type, range, calendar date, structural group or literal. Include only a fixed reason code and allowlisted location. |
| `CONFIG_UNKNOWN_FIELD` | Unknown key in a typed object or forbidden field in a scenario patch. Report the nearest known parent and an `<unknown>` placeholder without the actual key. |

Apply errors in intake order, then version dispatch, then structural validation. For multiple structural issues, use `CONFIG_UNKNOWN_FIELD` as the outer code if any issue is an unknown field. Otherwise use `CONFIG_SCHEMA_VALIDATION_ERROR`. Order issue details by safe schema path and fixed reason code. Return at most five issues and an omitted count. Safe paths use schema field names plus placeholders such as `scenarios.<scenario>.patch` and `base.requested_outputs.<item>`. Never include raw YAML, input values, credentials, local paths, dynamic keys, exception text or stack payloads. Rejection occurs before context creation, ID allocation, clock or RNG use, pipeline calls and output writes. WP-01.2 owns errors for unknown selected scenarios, invalid caller overrides and incompatible effective scope or inventory. WP-01.3 owns invalid run-context arguments.

### WP-01.4 — Logging integration

Use a module-level standard-library logger with caller-managed handlers. Emit fixed event names and allowlisted values such as a validated run ID, fixed stage ID, outcome and diagnostic code. Keep unrestricted error text and exception context out of ordinary logs. Use the effective diagnostic level for event verbosity and propagate failures regardless of level.

WP-10 owns the physical manifest, canonical encoding and hash selection, dependencies and lock evidence, file digests, output metrics, access and retention, replay and L1/L2/L3 verification. Storage of ground truth and publication remain separately governed. WP-01 records initial metadata in memory and supports no reproducibility certification.

## 13. Existing Component Reuse Assessment

Source paths in the first column are relative to the repository root.

| Source | Implemented responsibility and interface | Proposed reuse, adaptation and coupling |
|---|---|---|
| `pyproject.toml`, `configs/config.yaml` | Dependency declarations and general project settings. | Use declared libraries and test tooling. Keep scenario schema separate from legacy settings to avoid silent modelling defaults. No changes. |
| `src/nowa_customer_intelligence/pipeline/models.py` | `PipelineWorkflow`, `PipelineExecutionRequest`, `StageExecutionResult`, `PipelineExecutionSummary`, immutable inputs and evidence. | Reuse workflow enum. Use request/summary at the later boundary. Reuse immutable modelling conventions, with separate generator stage types to avoid coupling to PES aggregation. No changes. |
| `src/nowa_customer_intelligence/pipeline/discovery.py` | `discover_datasets` checks supplied file paths and workflow presence, with `DatasetDiscoveryError` for invalid sources. | Use workflow behaviour as a regression oracle. WP-01 validates names without inspecting files. Keep the proposed required-set check small and test parity because the source maps are private. No changes. |
| `src/nowa_customer_intelligence/pipeline/execution.py`, `src/nowa_customer_intelligence/pipeline/__init__.py` | Public `execute_pipeline` and `PipelineOperationalInputError` for present-empty required datasets. | Use public request and result with existing fixtures for compatibility. A production adapter is deferred to WP-08 when projected paths exist. Keep exception payloads outside logs. No changes. |
| `src/nowa_customer_intelligence/data/ingestion/csv_ingestion.py` | `DATASET_FILENAMES`, per-file `ingest_csv_dataset` and folder-wide `ingest_client_datasets`. | Read existing filename vocabulary and let the pipeline own per-file ingestion. The folder helper has a different snapshot rule. No changes. |
| `src/nowa_customer_intelligence/pipeline/technical.py`, `src/nowa_customer_intelligence/data/preprocessing/type_normalization.py` | `run_technical_pipeline` and `normalize_dataset_types` handle CSV and schema inputs. | Reuse downstream through `execute_pipeline`. Configuration has its own validation and must avoid CSV coercion rules. No changes. |
| `src/nowa_customer_intelligence/pipeline/quality.py`, `src/nowa_customer_intelligence/data/validation/validator.py` | `orchestrate_referential_integrity_and_data_quality` and `validate_data_quality` coordinate RI and DQ. | Reuse downstream only. Neither supplies full generator semantic, temporal or label evidence. No changes. |
| `src/nowa_customer_intelligence/data/validation/referential_integrity.py`, `src/nowa_customer_intelligence/data/validation/temporal_consistency.py`, `src/nowa_customer_intelligence/data/validation/reporting.py` | `validate_referential_integrity`, `validate_temporal_consistency` and `build_data_quality_report` supply implemented rule evidence. | Keep existing execution and reporting through the pipeline. No generator rules in WP-01. No changes. |
| `src/nowa_customer_intelligence/pipeline/finalization.py`, `src/nowa_customer_intelligence/pipeline/reporting.py`, `src/nowa_customer_intelligence/pipeline/aggregation.py` | `build_final_pipeline_result`, `build_pipeline_execution_summary` and `determine_pipeline_overall_status` construct and aggregate PES evidence. | Preserve the pipeline's summary and link its ID when available. Avoid a second pipeline status aggregator or private imports. No changes. |

## 14. Proposed Implementation File Map

All listed paths are future work. The small generator-specific package would live under the existing data package.

| Exact repository-relative path | Status and purpose | Main interfaces and dependencies | Associated tests and requirements |
|---|---|---|---|
| `src/nowa_customer_intelligence/data/synthetic/__init__.py` | New package boundary accompanying real configuration code. | Minimal package entry point. Avoid eager pipeline imports in package initialisation. | Import exercised by configuration tests. FR-01. |
| `src/nowa_customer_intelligence/data/synthetic/configuration.py` | New loader, schema, scenario resolver and effective types. Invalid input returns typed configuration errors. | `load_configuration`, `resolve_configuration`, `EffectiveConfiguration`. PyYAML, Pydantic, workflow enum and filename vocabulary. Accept explicit bytes and declaration, return validated values and origins. | `test_synthetic_configuration.py`. FR-01–04, FR-07. |
| `src/nowa_customer_intelligence/data/synthetic/run_context.py` | New run metadata, scope, stage outcomes and sanitised logging boundary. | `create_run_context`, `RunContext`, stage transition methods and immutable outcome snapshots. Resolved config, standard-library logger, UUID and datetime. Errors carry safe typed diagnostics. | `test_synthetic_run_context.py`, `test_synthetic_wp01_boundary.py`. FR-04–07. |
| `tests/unit/data/test_synthetic_configuration.py` | New parser, validation and resolution tests. | Inline document inputs and Pytest parametrisation. | FR-01–04, FR-07. |
| `tests/unit/data/test_synthetic_run_context.py` | New scope, context, stage and diagnostic tests. | Fixed clock, ID factory, source metadata and log capture. | FR-04–07. |
| `tests/integration/test_synthetic_wp01_boundary.py` | New compatibility and no-execution tests. | Prepared test fixtures, public pipeline interface and spies. | FR-04–07. |
| `tests/integration/test_pipeline_execution.py` | Existing regression evidence, run unchanged when authorised. | Current workflow and error tests. | FR-04, FR-07. |

## 15. WP-01 Technical Decision Register

The project owner approved WP01-D-001–004 on 18 November 2026 and initially limited WP01-D-005, WP01-D-008 and WP01-D-010 to their WP-01.1 portions. Batch 01 authorises WP01-D-005–011 within the configuration-only WP-01 implementation. Existing governing decisions retain their original authority.

| ID and topic | Existing authority | Options | Recommended choice and rationale | Dependencies and implementation impact | Status | Approval point |
|---|---|---|---|---|---|---|
| WP01-D-001 Input format | SA-002, Block A §11 | YAML, JSON, Python mapping | Single safe YAML document supplied explicitly as bytes. Fits project conventions and permits deterministic intake. | Existing PyYAML. Enforce all six finite limits and event preflight before SafeLoader construction (§8). | Approved | Approved 18 November 2026 |
| WP01-D-002 Typed validation | SA-002, NEDS §§4–5 | Pydantic, manual dataclass validation | Strict Pydantic for nested schemas and consistent errors. | Existing Pydantic. Validate document shape and leaf rules in WP-01.1, then enforce relationships on resolved values in WP-01.2. Translate structural errors through §12. | Approved | Approved 18 November 2026 |
| WP01-D-003 Schema version | Block A §11, RPR-003 | Integer dispatch, semantic version, unversioned input | Explicit integer v1, reject unknown versions at dispatch. | Controls compatibility and tests. | Approved | Approved 18 November 2026 |
| WP01-D-004 Required groups | BDR-006, FDB-001/002, PD-006 | Full generator schema, bounded subset | Use the exact v1 catalogue in §8, with a complete structural base, named scenario versions and partial typed patches. | Field names, numeric/date constraints and deferred modelling policy. | Approved | Approved 18 November 2026 |
| WP01-D-005 Defaults and precedence | Block A §12, Block D §3 | Full inheritance, shallow patches, base only | One base, named shallow patches and allowlisted explicit overrides, with origin tracking. | WP01-D-004. Batch 01 adopts per-leaf precedence, the INFO default and immutable value origins in WP-01.2. | Approved | Batch 01, WP-01 scope |
| WP01-D-006 Effective immutability | Block D §3, pipeline model patterns | Frozen nested models, shallow freeze, mutable mapping | Frozen typed values and immutable collections with copied inputs. | WP01-D-002/005. Defines generator input API. | Approved | Batch 01, WP-01 scope |
| WP01-D-007 Run ID | Block A §13.3, ADR-010 | UUID4, counter, deterministic config hash | Prefixed UUID4 per attempt, with injectable factory. Same scenario can have distinct attempts. | Standard library. Independent of canonical episode policy and RNG streams. | Approved | Batch 01, WP-01 scope |
| WP01-D-008 Scope and inventory | FDB-002, PD-006, ORCH-005–010 | Explicit declaration, infer from inventory, require all five | Explicit workflow and configuration-only scope, validated planned inventory and gate applicability. | Existing enum and filename vocabulary. Batch 01 adopts workflow-compatible planned inventory, required input declarations and configuration-only gate applicability. | Approved | Batch 01, WP-01 scope |
| WP01-D-009 Stage representation | PES-001–003, RPR-006 | Reuse pipeline statuses, minimal generator records, general scheduler | Generator-local transitions and immutable snapshots. Preserves scope and causal evidence. | WP01-D-008. No changes to existing enums. | Approved | Batch 01, WP-01 scope |
| WP01-D-010 Diagnostics and logging | PES-008, NEDS §14 | Standard logger, new logging framework, inline prints | Standard module logger and typed, bounded diagnostics. | Batch 01 retains the five loader codes and adopts caller-managed logging with fixed stage events and safe error propagation. | Approved | Batch 01, WP-01 scope |
| WP01-D-011 Initial provenance | RPR-006, RPR-009/012 | In-memory metadata, physical manifest, automatic Git probing | Capture structured local metadata and use caller-supplied source state. | WP01-D-006–008. Persistence remains later work. | Approved | Batch 01, WP-01 scope |
| WP01-D-012 Fingerprint boundary | RPR-003/007–011 | Hash in WP-01, defer encoding/hash with explicit inputs | Preserve fully resolved inputs and defer canonical encoding, digest and guarantees to WP-10. | WP01-D-006 plus future format, RNG and identity decisions. | Open | Record the WP-10 deferral before WP-01.2. Review and approve the mechanism separately in WP-10. |

### Scope of Batch 01 approval

WP01-D-005 covers named scenario resolution and allowed caller overrides. D-006 covers immutable effective configuration. D-007 covers generator run UUID4 only. D-008 covers planned inventory and configuration-only gates. D-009 covers generator-local stage evidence. D-010 covers sanitised configuration and stage diagnostics with caller-managed handlers. D-011 covers in-memory, caller-supplied provenance. D-012 remains Open for WP-10. Contract, product and architectural decisions retain their existing scope.

## 16. Unit and Integration Test Strategy

| Increment and proposed test location | Objective and cases | Expected evidence |
|---|---|---|
| WP-01.1, `tests/unit/data/test_synthetic_configuration.py` | Exercise valid v1 intake, malformed and unsafe YAML, UTF-8, every intake limit at and above its boundary, duplicate keys, forbidden constructs, schema dispatch, strict types, required groups, unknown keys, optional partial patches and safe typed errors. Use a constructor spy to show preflight rejection precedes construction. Test UTF-8 and YAML errors, unknown keys and library errors with sentinel values to confirm none leaks through messages, issue details or exposed exception context. | Structurally valid input returns `ValidatedConfiguration`. Fixed codes, sanitised issue details and omitted counts match the contract. Unit-level checks show no execution calls, clock or ID allocation, RNG use, pipeline calls or output writes. No resolver, context, logger integration or pipeline fixture is required to run this group. |
| WP-01.2, same configuration test file | Exercise scenario selection, override allowlist, default/base/scenario/caller precedence, effective completeness, origins, reversed dates or episode bounds, duplicate or empty planned inventories and workflow requirements. Compare repeated logical values and mutate original inputs. | Deterministic origins and values, immutable result and safe rejection of invalid effective config. |
| WP-01.3, `tests/unit/data/test_synthetic_run_context.py` | Exercise effective-only input, context creation, distinct run IDs, UTC time, policies, scope, gate applicability and unknown source metadata. | Fixed clock and ID fixtures, exact scope and provenance assertions, explicit rejection of unresolved inputs. |
| WP-01.4, same run-context test file | Exercise legal and invalid stage transitions, timestamps, failure propagation, dependent blocking, unexecuted stages and sanitised log events. | Outcome snapshots and captured log fields with no sensitive values or false success. |
| WP-01.4, `tests/integration/test_synthetic_wp01_boundary.py` and unchanged pipeline/ingestion/quality suites | Use prepared CSV fixtures and a separate pipeline ID. Test BASIC without snapshots and TEMPORAL requiring snapshots. Compare planned requirements to existing discovery behaviour. Confirm unchanged fixture headers, no generation or publication claim and no execution after invalid configuration. | Public request and PES evidence, pipeline regressions and applicable Pytest and Ruff results recorded against the future implementation revision. |

## 17. Acceptance Criteria

These criteria govern technical acceptance. Batch 01 implementation evidence appears in §21. Project-owner acceptance is recorded in §21.

1. FR-01 parses valid v1 scenarios and rejects malformed, unsafe, unknown, missing or wrongly typed fields and unsupported versions.
2. FR-02 rejects contradictions and invalid override paths and yields the documented effective values and origins for repeated identical inputs.
3. FR-03 exposes an immutable effective configuration with no aliases to mutable caller inputs.
4. FR-04 records versioned scenario and policy references, independent run ID, UTC time, scope and the workflow's required inventory.
5. FR-05 records legal transitions, retains outcomes, blocks dependants and leaves unexecuted stages explicit. Required gates without positive evidence cannot grant acceptance.
6. FR-06 diagnostics are bounded and sanitised. Initial provenance distinguishes known and unknown source state.
7. FR-07 proves invalid configuration exits before execution and WP-01 produces no generated data. Existing APIs, contract fields and pipeline behaviour pass regression checks.
8. Proposed tests and applicable existing tests pass. Targeted Ruff checks pass, and applicable NEDS review evidence and documentation describe the verified implementation and any approved limitations.

### Independent WP-01.1 acceptance

1. One valid v1 document with a complete structural base and a valid partial or omitted patch yields `ValidatedConfiguration`.
2. Exact limits and prohibited constructs in §8 are enforced, with over-budget and forbidden inputs rejected before construction.
3. Missing groups, unknown keys, unsupported versions, wrong types and invalid supplied patch leaves fail at the structural boundary. Effective order and workflow inventory combinations are evaluated in WP-01.2.
4. Every loader failure has its documented type and stable code. Invalid input and exception payloads never appear in diagnostic text, location details or exposed exception context.
5. The parser and structural suite runs independently and demonstrates zero execution side effects. Reviewed code and actual unit and Ruff results supply the evidence for WP-01.1.

## 18. Incremental Implementation Plan

Retain WP-01.1–WP-01.4. WP-01.1 covers intake, shape and local field constraints. WP-01.2 owns full merged semantics and immutable effective values. Where a configuration-only integration uses a fixture, it verifies compatibility without creating a production projection adapter.

| Increment | Objective, exact scope and files | Dependencies and decisions | Tests, acceptance and review evidence | Authorisation boundary |
|---|---|---|---|---|
| WP-01.1 Configuration Schema & Validation | Add package initialiser, `configuration.py` loader, v1 dispatch, raw base and patch schemas and safe errors, plus `test_synthetic_configuration.py`. | Previously authorised. Batch 01 verified the loader and structural schema. | Run only the independent WP-01.1 cases in §§16–17. Review field map, typed interface, diagnostic contract and actual test and lint output. | Authorised loader and schema scope. No resolver, context or real configuration artefact required. |
| WP-01.2 Scenario Resolution & Effective Configuration | Extend `configuration.py` and its tests with required effective values, leaf precedence, explicit origins, immutable types and cross-field rules. | Verified WP-01.1 and Batch 01 approval of D-005/006 and effective scope rules in D-008. Record D-012 deferral without selecting the fingerprint mechanism. | Repeat resolution, override conflict, completeness and mutation tests. Review effective values, origins and workflow matrix. | Batch 01 authorises resolver and effective configuration. |
| WP-01.3 Run Context & Execution Scope | Add `run_context.py` and `test_synthetic_run_context.py` for run metadata, UTC timestamp, identity, scope, planned gates and initial provenance. | Tested WP-01.2 and Batch 01 approval of D-007/008/011. | Fixed clock/ID, unknown metadata, invalid context and workflow/identity tests. Review snapshots and unfulfilled gate declarations. | Batch 01 authorises in-memory run context. |
| WP-01.4 Stage Management, Logging & Integration | Extend `run_context.py` and its tests with transitions, failure handling and events. Add `test_synthetic_wp01_boundary.py` and run existing relevant regressions unchanged. | Tested WP-01.3 and Batch 01 approval of D-009/010. | Stage and sanitisation tests, BASIC/TEMPORAL parity, no execution after rejection, unchanged interface regressions and scoped Pytest/Ruff output. Review safe diagnostic examples and final file inventory. | Batch 01 authorises these boundaries and tests. WP-08 adapter and dataset work remain separate. |

## 19. Dependencies and Implementation Blockers

The project owner authorised the WP-01.1 implementation and the remaining increments through Batch 01. Tests ran on Python 3.12.3 using the declared dependencies. Technical acceptance is recorded in §21. The implementation uses no new dependency or external service.

The unverified Phase 3.3.1 source remains a recorded limitation under FDB-001. It does not block configuration-only work under that disposition. UUID provider/version for canonical episodes, Registry, lifecycle/billing/usage/snapshot semantics, outcome ascertainment and model eligibility remain unresolved. They block related downstream claims or implementations according to the baseline. WP-02 owns stream choice and seed representation for the RNG, WP-08 owns CSV adapter integration for generated outputs, and WP-10 owns full provenance and fingerprint selection. None is required to implement the configuration-only subset once implementation is authorised.

## 20. NEDS v1.1 Alignment

| Applicable NEDS area | Planning evidence | Required future evidence |
|---|---|---|
| §§2–3 and 20–21, engineering principles and incremental governance | Explicit objectives, constraints, source review, decision rationale and separate increments. | Approval for each increment and timestamped actual execution evidence. |
| §§4–6, architecture, code quality and data contracts | Existing modular architecture, declared dependencies, minimal file map and traceable contract boundaries. | Reviewed implementation diff, applicable Ruff output and unchanged contract interfaces. |
| §10, testing and QA | Unit, integration and regression cases tied to verifiable requirements. | Test results from the actual implementation revision. |
| §14, security and reliability | Safe configuration intake, no secrets in configuration or operational logs, bounded errors and explicit failure. | Negative tests and review of error output and logging. |
| §§15–16, repository and documentation | Verified baseline revision, dated technical plan approval, British English and evidence-based capability descriptions. | Reviewed implementation revisions and documentation aligned to verified behaviour. |

## 21. Implementation Readiness and Approval Checklist

- [x] Identify the baseline revision and inspect existing configuration, orchestration, validation, error handling and tests.
- [x] Record proposed interfaces, scope, decision authority, exclusions and review gates.
- [x] Complete the WP-01 technical review and resolve WP01-REV-001–005.
- [x] Approve WP01-D-001 through WP01-D-004 in full.
- [x] Approve the WP-01.1 structural subsets of WP01-D-005, WP01-D-008 and WP01-D-010.
- [x] Authorise WP-01.1 and approve the bounded Batch 01 implementation of WP-01.2–WP-01.4.
- [x] Implement and test the loader, resolver, run context, stage tracker and compatibility boundary.
- [x] Record project-owner technical acceptance under Batch 02.

### Batch 01 implementation evidence

| Increment | Implementation and verification |
|---|---|
| WP-01.1 | Existing intake limits, SafeLoader isolation, schema dispatch and sanitised error handling verified. All 110 original tests passed. |
| WP-01.2 | Implemented `resolve_configuration` and immutable `EffectiveConfiguration`. The combined configuration suite passed 122 tests. |
| WP-01.3 | Implemented `create_run_context`, UUID4 identity, UTC timestamps, workflow requirements and in-memory source evidence. |
| WP-01.4 | Implemented `StageTracker`, immutable snapshots, dependency blocking and fixed diagnostic events. The combined context and stage suite passed 14 tests. Four new compatibility tests and 29 existing pipeline integration tests passed. |

The full suite passed 821 tests. Measured statement coverage was 97% for `configuration.py` and 98% for `run_context.py`. Repository-wide Ruff lint and formatting passed. Tests covered YAML intake boundaries and error-chain sanitisation, invalid effective inventory, stage failure redaction and the absence of generated files during WP-01 execution. Remaining uncovered paths include defensive parser and constructor guards, validation of mutated structural input and invalid or duplicate stage definitions.

WP-01 is implemented, tested and accepted for its configuration-only scope under Batch 02. The context records configuration-only evidence. Dataset production, the WP-08 adapter, persistent provenance and the WP-10 fingerprint mechanism remain outside this batch.

### Batch 02 closure

The project owner authorised conditional acceptance in Batch 02. Review of the seven-file working-tree implementation against baseline HEAD `93bb09299bbbd580d2e9bb13e21a06deaf1ee6ce` passed the acceptance gate. Reverification passed 169 tests (136 WP-01 unit, 4 compatibility and 29 existing pipeline integration tests). Repository-wide Ruff lint and formatting passed. WP01-D-012 remains Open for WP-10. WP-01 acceptance covers configuration and run context only. The compatibility tests use prepared fixtures for downstream pipeline checks.
