# Pipeline Execution Summary Specification

**Project:** Nowa Customer Intelligence

**Status:** Technical specification; implementation is not authorized by this document
**Decision basis:** PES-001 through PES-016 are approved architectural decisions.

## 1. Purpose and Scope

The Pipeline Execution Summary (PES) is an execution-level record that consolidates the
outcomes reported by the components participating in one pipeline run. It provides a
traceable view of which stages ran, their reported outcomes, which stages could not run,
and whether a Data Quality (DQ) report was produced.

The PES addresses the need to retain a coherent execution history across the pipeline,
including failures that occur before DQ validation. It is a logical responsibility of the
overall orchestration layer.

The PES is not a validation engine, a DQ report, or an acceptance/eligibility engine. It
does not run or rerun validations, reinterpret or modify component results, decide whether
input data is accepted, or determine feature, training, or prediction eligibility. A
downstream acceptance/eligibility component may consume PES outcomes and other relevant
results. Persistence, APIs, and user interfaces are outside the scope of the initial PES
implementation.

Processing and prediction remain subscription-episode level: `subscription_id` identifies
the contractual episode and prediction entity; `customer_id` identifies its associated
customer/account and is not the prediction identifier. The PES records execution outcomes;
it does not change prediction granularity.

## 2. Approved Architectural Decisions

The decisions below are approved. They do not settle the remaining field-level details
explicitly listed as open in this specification.

### 2.1 PES-001 — Stage Execution Status

Each stage result uses one of the following distinct statuses:

| Status | Meaning |
|---|---|
| `SUCCEEDED` | The stage executed and completed successfully according to its own responsibility. |
| `FAILED` | The stage executed and reported a failure. |
| `PARTIAL` | The stage executed but completed only part of its intended work or returned an incomplete outcome. |
| `BLOCKED` | The stage could not execute or complete because a prerequisite or dependency prevented it. |
| `SKIPPED` | The stage was deliberately not run for this execution, although a decision or control could otherwise have run it. |
| `NOT_APPLICABLE` | The stage does not apply to the explicitly declared execution context or workflow. |
| `NOT_IMPLEMENTED` | The capability represented by the stage is not implemented in the current software. |

These statuses are not interchangeable. In particular, a non-applicable stage is not a
deliberately skipped stage; a blocked stage was prevented by a dependency; and an
unimplemented capability is not thereby a failed execution. A proposed or unavailable
workflow declaration must not be inferred solely to assign `NOT_APPLICABLE`.

### 2.2 PES-002 — Overall Pipeline Status

The PES overall status uses one of the following values:

| Status | Intended meaning |
|---|---|
| `SUCCEEDED` | The execution completed its required applicable pipeline work successfully. |
| `PARTIAL` | The execution produced some valid outcomes but did not complete all work needed for a complete execution. |
| `FAILED` | An attempted execution failed such that it cannot be represented as a successful or partial completion. |
| `BLOCKED` | The execution could not proceed through required work because a prerequisite or dependency prevented it. |

These meanings describe execution only. Overall status is not a data-acceptance decision
or a model-eligibility decision. `NOT_IMPLEMENTED` at an individual stage does not
automatically mean that the overall pipeline failed.

PES-009 defines the conditional precedence and stage-classification behavior detailed in
Section 5. Do not infer additional aggregation rules beyond those approved cases.

### 2.3 PES-003 — Data Model

The conceptual model consists of `PipelineExecutionSummary` and
`StageExecutionResult`. The fields below describe the approved conceptual shape, not a
final Python API, serialization format, or complete validation contract. “Open” means no
format, constraint, or presence rule is established here.

#### PipelineExecutionSummary

| Field | Type | Required | Purpose and established constraints |
|---|---|---:|---|
| `summary_id` | `str` | Yes | Identifier for this summary. The current implementation generates a UUIDv4 string; uniqueness scope remains open. |
| `run_id` | `str` | Yes | Associates the summary with a pipeline execution. Must be a non-empty string; source, generation, format, and uniqueness scope remain open. |
| `client_scope` | `str` | Yes | Client-scoped context. Must be a non-empty string and must not contain unnecessary client-identifying information; pseudonymous representation and source remain open. |
| `created_at_utc` | `datetime` | Yes | Summary creation timestamp; must be timezone-aware and normalized to UTC. The current implementation uses UTC now. |
| `overall_status` | `PipelineOverallStatus` | Yes | Overall execution outcome. A dedicated aggregation component calculates it under PES-009 and PES-016; the data models do not independently calculate it. |
| `stages` | `tuple[StageExecutionResult, ...]` | Yes | Consolidated stage outcomes. The tuple is immutable and contains at most one entry per `stage_id`. |
| `dq_report_id` | `str \| None` | No | Optional reference to the independent DQ report only; no findings or report contents are duplicated. |
| `dataset_presence` | `Mapping[str, bool]` | Yes | Dataset availability mapping; must be immutable. The current implementation records `customers`, `subscriptions`, `subscription_snapshots`, `usage_monthly`, and `invoices`, distinguishing presence from validation outcome. |

#### StageExecutionResult

| Field | Type | Required | Purpose and established constraints |
|---|---|---:|---|
| `stage_id` | `str` | Yes | Stage identifier; must be a non-empty string and unique within its summary. |
| `status` | `StageExecutionStatus` | Yes | Stage outcome, using the seven PES-001 values. |
| `requirement` | `StageRequirement` | Yes | Workflow-specific requirement classification using `REQUIRED`, `OPTIONAL`, or `NOT_APPLICABLE`. |
| `started_at_utc` | `datetime \| None` | No | Optional stage start timestamp; when present, must be timezone-aware and normalized to UTC. |
| `completed_at_utc` | `datetime \| None` | No | Optional stage completion timestamp; when present, must be timezone-aware and normalized to UTC, and cannot precede `started_at_utc` when both are present. |
| `records_received` | `int \| None` | No | Optional count. When known and applicable, it is a non-negative integer; `None` means unknown or not applicable, not zero. |
| `records_processed` | `int \| None` | No | Optional count. When known and applicable, it is a non-negative integer; `None` means unknown or not applicable, not zero. |
| `records_rejected` | `int \| None` | No | Optional count. When known and applicable, it is a non-negative integer; `None` means unknown or not applicable, not zero. |
| `error_code` | `str \| None` | No | Optional safe machine-readable stage error indication. Its vocabulary remains open and it must not expose sensitive values. |
| `message` | `str \| None` | No | Optional safe operational context, subject to PES-008. |

The approved model invariants are:

- Required identifiers (`summary_id`, `run_id`, `client_scope`, and `stage_id`) are
  non-empty strings.
- Every timestamp is timezone-aware and normalized to UTC. Stage timestamps may be
  `None`; `created_at_utc` is required.
- `completed_at_utc` cannot precede `started_at_utc` when both are present.
- Count values are non-negative integers when present. Python booleans are rejected as
  integers. `None` represents unknown or not applicable information and must not be
  interpreted as zero.
- `stages` is an immutable tuple. It contains at most one consolidated result per
  `stage_id`; stage IDs are non-empty and unique within a summary.
- `dataset_presence` is immutable.
- `requirement` and `status` must satisfy PES-015.

No approved invariant requires
`records_processed + records_rejected == records_received`; counter semantics do not
support that constraint. The field contract does not define identifier formats or
generation, dataset-presence keys, or serialization.

### 2.4 PES-004 — DQ Report Reference

The PES may contain `dq_report_id` when an independent DQ report exists. The DQ Report
remains its own artifact. The PES must not copy detailed DQ findings, rule results, or
other DQ report contents into the summary.

### 2.5 PES-005 — Persistence

Persistence is outside the scope of the initial PES implementation. This specification
does not select or propose a database, storage engine, persistence infrastructure, or
retention policy.

### 2.6 PES-006 — Orchestration Responsibility

The PES is a logical responsibility of the overall pipeline orchestration layer. It does
not require a separate service, microservice, or independent package. The proposed code
organization in Section 8 is only an initial organization for a future implementation.

### 2.7 PES-007 — Acceptance and Eligibility

Acceptance and eligibility are outside the PES's responsibility. The PES consolidates
execution outcomes. A separate downstream component will eventually consume those
outcomes and other relevant evidence to determine full or partial acceptance, exclusions,
and eligibility. The PES does not make those decisions or imply them through its overall
status.

### 2.8 PES-008 — Data Protection

The PES must not expose raw input records, direct personal identifiers, sensitive source
values, or unnecessary client-identifying information. Operational messages and error
information must be safe for reporting. Stage outcomes should use safe codes and concise
descriptions rather than embedding source rows or unreviewed exception contents. This
requirement applies to both the summary and its stage results; it does not authorize
including sensitive values for debugging.

### 2.9 PES-009 — Overall Status Aggregation Rules

The overall status is calculated from already-consolidated stage outcomes and their
requirement classifications. Only `REQUIRED` stages affect the outcome. `OPTIONAL` and
valid `NOT_APPLICABLE` stages are neutral for every valid execution status. For required
stages, apply this precedence:

`FAILED > BLOCKED > PARTIAL > SUCCEEDED`

For a required stage, `FAILED` maps to `FAILED`; `BLOCKED` and `NOT_IMPLEMENTED` map to
`BLOCKED`; `PARTIAL` and `SKIPPED` map to `PARTIAL`; and `SUCCEEDED` has no degrading
effect. An empty stage sequence maps to `BLOCKED`. A non-empty sequence containing no
required stages maps to `SUCCEEDED`, including sequences containing only optional,
not-applicable, or mixed neutral stages. Apply precedence only across required stages; it
is not a mechanical ranking across all reported stages. Stage status, requirement
classification, and overall pipeline status remain distinct. Overall status is an
execution result, not an acceptance or eligibility decision.

### 2.10 PES-010 — Stage Requirement Classification

Whether a stage is required, optional, or not applicable depends on the explicitly
declared execution context and workflow. The orchestration layer supplies this
classification; it is not necessarily an intrinsic property of the stage. The
classifications mean:

| Classification | Meaning |
|---|---|
| `REQUIRED` | The stage must complete for the declared workflow. |
| `OPTIONAL` | The stage may be omitted or fail without necessarily invalidating required processing. |
| `NOT_APPLICABLE` | The stage does not belong to the declared workflow or execution context. |

Do not infer workflow intent or stage classification from dataset presence. Basic and
Temporal workflow requirements follow PD-006; the workflow declaration interface and
default remain unresolved.

### 2.11 PES-011 — Stage Requirement Classification Field

`StageExecutionResult` includes a required `requirement` field represented by the
`StageRequirement` enum with values `REQUIRED`, `OPTIONAL`, and `NOT_APPLICABLE`. This is
a three-state classification, not a boolean `is_required` field. Its technical
placement in any serialized external representation remains subject to implementation
design, but the conceptual field and enum values are approved.

### 2.12 PES-012 — Stage Uniqueness

A `PipelineExecutionSummary` contains at most one consolidated entry for each `stage_id`.
Retries and repeated executions are consolidated before the summary is produced.
Retry-level execution history is outside the current model scope.

### 2.13 PES-013 — Unknown and Non-Applicable Counts

The stage count fields may be `None` when a count is unknown or not applicable. Missing
information must not be interpreted as zero. When present, count values must satisfy the
approved non-negative integer invariant; Python booleans are not valid integer counts.

### 2.14 PES-014 — Timestamp Policy

All PES timestamps must be timezone-aware and normalized to UTC. Optional stage timestamps
may be absent (`None`). A provided `completed_at_utc` cannot precede
`started_at_utc` when both are provided.

### 2.15 PES-015 — Requirement and Status Consistency

Requirement classification and stage status must agree on non-applicability:

- `requirement == NOT_APPLICABLE` requires `status == NOT_APPLICABLE`.
- `status == NOT_APPLICABLE` requires `requirement == NOT_APPLICABLE`.

This equivalence does not define further mappings between `REQUIRED` or `OPTIONAL` and
the other stage statuses.

### 2.16 PES-016 — Overall Status Calculation

The orchestration layer provides consolidated stage results and their requirement
classifications. A dedicated aggregation component calculates `overall_status` under the
approved PES-009 rules, and that result is included in `PipelineExecutionSummary`. The
data models validate structural and field-level invariants; they do not independently
calculate overall status. The aggregator does not extend the approved rules with
additional inference.

## 3. Pipeline Stages

The following stage identifiers describe PES execution responsibilities and are distinct
from acceptance, eligibility, feature generation, or prediction. Section 10 records the
current implementation state and MVP exclusions.

| Stage ID | Responsibility and component relationship | Current implementation state |
|---|---|---|
| `dataset_discovery` | Identify expected and supplied datasets and report availability using explicit workflow intent. | `pipeline.execute_pipeline()` calls `discover_datasets()` using the request's required BASIC/TEMPORAL workflow; the directory loader is not used by this entry point. |
| `header_inspection` | Inspect the CSV header and structural properties before relying on dataset columns. | The technical pipeline records header outcomes; integrated ingestion invokes inspection once per supplied file. |
| `csv_ingestion` | Read contract datasets into frames while preserving source values for subsequent normalization. | The technical pipeline ingests supplied datasets individually, preserving per-dataset stage outcomes. |
| `type_normalization` | Convert recognized input values to the contract's normalized types without silently repairing invalid identifiers. | The technical pipeline normalizes supplied frames and records per-dataset outcomes. |
| `identity_resolution` | Establish candidate canonical episode references. **Situation A:** canonical IDs supplied in input are candidates. **Situation B:** identity resolution/bootstrap and, where supported, dependent-reference resolution are required before dependent schema/RI checks. | Situation A candidate availability is possible on the current canonical-ID input path. Registry-backed identity resolution and Situation B bootstrap/reference resolution are proposed and not implemented. The input representation for Situation B remains unresolved. |
| `schema_validation` | Apply existing Pandera schemas to the applicable frames after required canonical references are available. | The technical pipeline applies the five schemas to supplied datasets and preserves schema outcomes and validated frames. |
| `referential_integrity` | Execute applicable implemented RI checks over schema-valid datasets and carry their original outcomes forward. RI establishes key-reference existence, not Registry consistency or semantic attribution. | The DQ coordinator runs RI-001 through RI-004 once after the ORCH-014 gate and passes original findings into DQ; the public entry point preserves the stage result. |
| `registry_consistency` | Verify that candidate canonical identities/mappings are consistent with the client-scoped Episode Identity Registry before identity-dependent acceptance or downstream processing. | Proposed capability; the Registry and consistency checks are not implemented. |
| `data_quality` | Coordinate applicable implemented DQ rules, including temporal checks, and produce a separate DQ report where available. It may reference earlier RI results without rerunning them. | The coordinator executes applicable TC checks after RI, preserves the DQ report, and returns its stage result; `pipeline.execute_pipeline()` integrates this flow. |
| `semantic_attribution` | Assess whether dependent records are supported as belonging to their referenced contractual episode, using available evidence after relevant technical checks. This is separate from candidate-reference resolution, RI, and Registry consistency. | Proposed capability; semantic attribution validation is not implemented. |

### 3.1 Situation A and Situation B

In **Situation A**, a canonical `subscription_id` is supplied and can be treated as a
candidate reference. Its presence alone does not establish identity authority or Registry
consistency. Applicable schema and RI checks can use available candidate references;
Registry consistency must be verified before identity-dependent acceptance or downstream
processing. Semantic attribution remains a separate later responsibility for dependent
records.

In **Situation B**, identity resolution/bootstrap is required. Authoritative evidence
must govern reuse, issuance, or unresolved identity under existing identity decisions.
Where dependent records lack canonical references, a separate evidence-supported
reference-resolution step may establish candidate references needed for schema and RI.
It does not establish final semantic attribution. The current CSV allowlists and schemas
expect canonical IDs and do not implement this bootstrap path. No source identifier or
alternate CSV field is specified here.

For both situations, canonical-ID-dependent schema and RI validation occur after the
required references are available, and applicable checks are not run twice. Registry
consistency and semantic attribution are separate outcomes; neither is implied by passing
RI.

## 4. Stage Results and Reporting Rules

The PES receives outcomes from each responsible component. It does not execute validation,
rerun validation, alter original results, or silently discard a stage outcome. It records
the stage-level outcomes available for the execution and preserves upstream failures even
when a later stage, including DQ, was never reached.

The stage status communicates whether a stage succeeded, failed, was partial, blocked,
skipped, not applicable, or not implemented. A stage that did not execute must not be
represented as having passed. The conceptual fields and optionality for stage timestamps,
counts, and diagnostics are specified in Section 2.3; their serialized representation
and error-code vocabulary remain open.

Dataset availability is distinct from validation outcome. An absent dataset must not be
misrepresented as a validation failure or as a present dataset with zero records. A
present but empty file is distinct from an absent file. Under the approved dataset policy,
empty `customers` or `subscriptions` blocks either workflow; empty snapshots are allowed
for BASIC but block TEMPORAL; empty optional `usage_monthly` and `invoices` are allowed
subject to their schemas. The current public entry point raises an operational-input
exception for a present-empty required dataset after preserving discovery and technical
results. The seven-stage PES does not represent this no-summary case as a stage outcome;
that representation remains open. The workflow is an explicit `BASIC` or `TEMPORAL`
request value and is never inferred from snapshot presence.

Basic and Temporal workflows therefore may have different applicable/required stages.
A stage may be `NOT_APPLICABLE` only when its non-applicability is established
for the current declared execution context. A stage deliberately omitted is `SKIPPED`; a
stage prevented by a dependency is `BLOCKED`; and a capability absent from the software is
`NOT_IMPLEMENTED`.

The PES may hold `dq_report_id` when a DQ report exists. DQ findings and rule-level results
remain in that independent report. The PES does not copy them, re-evaluate them, or merge
upstream ingestion, normalization, schema, Registry, or attribution errors into the DQ
report. Similarly, creation of the PES does not determine acceptance or eligibility.

## 5. Overall Status Aggregation

The overall status summarizes execution based on stage outcomes and the stage requirement
classification supplied for the explicitly declared workflow. It does not replace or
override stage outcomes. The orchestration layer supplies consolidated stage outcomes and
requirement classifications to the dedicated aggregation component, which calculates
`overall_status` according to PES-009 and PES-016. The PES builder receives that status
and constructs the summary; the data models validate it and other model invariants. Neither
the builder nor the models calculate or modify the overall status.

### 5.1 Overall Status Meanings

| Overall status | Operational meaning |
|---|---|
| `SUCCEEDED` | Required applicable processing completed successfully. Optional-stage failure or absence does not by itself prevent this result when it has no material impact on required processing. |
| `PARTIAL` | Some usable outcomes were produced, but required processing was incomplete without a condition that establishes `FAILED` or `BLOCKED`. |
| `FAILED` | A required stage executed and failed in a way that establishes execution failure. Under the conditional precedence, this takes precedence over a downstream dependency block caused by that failure. |
| `BLOCKED` | Required processing could not proceed because a prerequisite/dependency or a required unimplemented capability prevented it, absent an earlier required-stage failure establishing `FAILED`. |

### 5.2 Conditional Application to Stage Outcomes

| Stage status | Requirement classification and execution impact | Overall-status effect under approved principles |
|---|---|---|
| `FAILED` | Required stage failed and the failure establishes execution failure. | May produce overall `FAILED`; it takes precedence over a downstream `BLOCKED` outcome caused by that failure. |
| `FAILED` | Optional stage failed without materially preventing required processing. | Does not automatically invalidate the overall execution; overall `SUCCEEDED` may remain appropriate if all required work succeeded and usable outcomes are sufficient. |
| `BLOCKED` | Required stage is blocked by a dependency, with no earlier required-stage failure establishing `FAILED`. | Overall `BLOCKED`. |
| `PARTIAL` | Required stage produced incomplete results. | Overall `PARTIAL`, unless another more severe condition applies under the conditional precedence. |
| `SKIPPED` | Required stage was deliberately skipped. | Required processing is incomplete; overall `PARTIAL`, unless another more severe condition applies. |
| `NOT_IMPLEMENTED` | Capability is required for the declared workflow and its absence prevents required processing. | Overall `BLOCKED`. |
| `NOT_IMPLEMENTED` | Capability is optional for the declared workflow and its absence does not materially affect required processing. | Does not automatically degrade the overall status. |
| `NOT_APPLICABLE` | Non-applicability is validly established for the declared workflow/context. | Does not degrade the overall result. |
| `SUCCEEDED` | Stage completed successfully. | Contributes a successful stage outcome; overall result still depends on other required applicable stages. |
| `PARTIAL`, `BLOCKED`, or `SKIPPED` | Optional stage, with no material impact on required processing. | Does not automatically produce overall `PARTIAL` or `BLOCKED`; consider usable outcomes and impact. |

The precedence is conditional rather than a simple sort over all stage status values. For
example, a failed optional stage does not automatically outrank successful required work;
a required unimplemented capability blocks only when it prevents required processing; and
a stage marked `NOT_APPLICABLE` is neutral only when its non-applicability is validly
established. The orchestration layer must not infer workflow intent from dataset presence.

| Example stage combination | Overall status under the approved principles |
|---|---|
| Required schema stage `FAILED`; a dependent required DQ stage is consequently `BLOCKED`. | `FAILED`, because the earlier required-stage failure establishes failure ahead of its downstream block. |
| Required ingestion `SUCCEEDED`; another required stage is `BLOCKED` by an unavailable prerequisite; no required stage previously failed. | `BLOCKED`. |
| Required stages `SUCCEEDED`; an optional stage is `FAILED` or `NOT_IMPLEMENTED` and has no material impact on required processing. | `SUCCEEDED` may remain appropriate. |
| Required stages otherwise succeed; a required stage is `PARTIAL` or deliberately `SKIPPED`, with no more severe condition. | `PARTIAL`. |
| All required applicable stages `SUCCEEDED`; a stage is validly `NOT_APPLICABLE`. | `SUCCEEDED`; the non-applicable stage does not degrade the result. |

### 5.3 Approved Aggregation Algorithm

Apply these steps to the supplied, already-consolidated stage results:

1. If the stage sequence is empty, return `BLOCKED`.
2. Ignore `OPTIONAL` stages for overall-status calculation; every valid optional status is
   neutral.
3. Ignore valid `NOT_APPLICABLE` stages; they are neutral.
4. If there are no `REQUIRED` stages after those classifications, return `SUCCEEDED`.
5. Consider only `REQUIRED` stage statuses and apply precedence: any `FAILED` yields
   `FAILED`; otherwise any `BLOCKED` or `NOT_IMPLEMENTED` yields `BLOCKED`; otherwise
   any `PARTIAL` or `SKIPPED` yields `PARTIAL`; if all required stages are `SUCCEEDED`,
   return `SUCCEEDED`.

This algorithm applies to the statuses and combinations covered by PES-009 and the
approved PES-3 aggregation rules. It does not infer requirement classifications or
workflow intent, consolidate retries, or establish acceptance or eligibility. Overall
status remains distinct from both stage status and acceptance/eligibility outcome.

## 6. Relationship with Other Components

| Component | Responsibility | Relationship to PES |
|---|---|---|
| Header inspection and CSV ingestion | Inspect and read individual input datasets, reporting their own outcomes. | Supply their stage results; the PES does not repeat inspection or parsing. |
| Type normalization | Normalize recognized values and report normalization outcomes. | Supply its stage result; the PES does not convert data. |
| Pandera schema validation | Check per-dataset schema constraints. | Supply schema outcomes; the PES does not validate frames. |
| Referential Integrity validation | Evaluate implemented cross-dataset key-reference rules. | Supply RI outcomes once; the PES preserves them without rerunning RI. |
| Registry consistency validation | Future check of candidate identities/mappings against the Registry. | If implemented, supply a separate stage result; not equivalent to RI. |
| DQ validators | Execute implemented DQ rule families, including applicable temporal checks; coordinate rule outcomes. | Supply DQ-stage outcome and report reference; PES does not execute DQ rules. |
| DQ report builder | Build a DQ-only report from DQ results and DQ metadata. | Builds an independent artifact. PES may reference its ID but does not contain its findings. |
| Overall status aggregator | Calculate overall pipeline status from consolidated stage outcomes and their requirement classifications. | Applies PES-009/PES-016; does not build the PES or decide acceptance/eligibility. |
| Pipeline Execution Summary builder | Validate supplied consolidated stage results and construct the PES using the caller-supplied overall status. | Does not calculate or modify overall status, execute stages, or consolidate attempts. |
| Pipeline orchestration layer | Coordinate stages, provide requirement classifications, and supply consolidated outcomes. | `pipeline.execute_pipeline()` provides the implemented MVP end-to-end flow and supplies consolidated results to the aggregator and builder under PES-006. |
| Future acceptance/eligibility coordinator | Consume execution outcomes and relevant record-level evidence to determine acceptance, exclusions, and eligibility. | Downstream consumer; its decisions are outside PES under PES-007. |

The PES and DQ Report have different scopes: the report contains DQ rules/findings and
related DQ metadata; the PES contains execution-stage outcomes across the pipeline. Neither
artifact is an acceptance decision.

## 7. Open Specification Details

The following matters are not resolved by PES-001 through PES-016 and must remain open:

1. `summary_id` uniqueness scope, `run_id` source/generation/format, `dq_report_id` format,
   timestamp serialization, count semantics beyond the approved non-negative/unknown
   behavior, error-code vocabulary, message length, and any future dataset-presence keys.
2. Stage-level representation of a present-empty required dataset. The current API raises
   `PipelineOperationalInputError` after technical outcomes are available and before
   summary construction; it does not return a PES for this case.
3. How `identity_resolution` and required candidate references are represented for
   Situation B; no CSV field or source identifier is approved by this document.
4. Safe operational error vocabulary/messages and any further report-access controls.

These items require subsequent specification or product/technical approval as applicable.
This document does not resolve client-dependent, workflow, identity, or attribution
decisions.

## 8. Proposed Initial Code Organization

The following organization is the proposed initial conceptual organization. This
specification does not, by itself, authorize implementation.

```text
src/
└── nowa_customer_intelligence/
    └── pipeline/
        ├── __init__.py
        ├── models.py
        ├── aggregation.py
        └── reporting.py
```

- `models.py`: stage and overall status enums and immutable PES data models.
- `aggregation.py`: calculate `overall_status` from consolidated stage outcomes using
  PES-009/PES-016. It does not consolidate individual attempts.
- `reporting.py`: validate supplied consolidated stage outcomes and construct a Pipeline
  Execution Summary using the supplied overall status; it does not calculate that status
  or execute, rerun, or consolidate individual stage attempts.
- `__init__.py`: expose the approved public types/functions from the package.

This organization does not define a separate service or microservice. Package APIs,
serialization, and interface details remain open.

## 10. PES-4B Implementation Record

The public `execute_pipeline(request)` entry point coordinates discovery, technical
processing, RI/DQ orchestration, and final summary construction. The current seven-stage
summary order is `dataset_discovery`, `header_inspection`, `csv_ingestion`,
`type_normalization`, `schema_validation`, `referential_integrity`, and `data_quality`.
The existing aggregator calculates overall status; the existing PES builder constructs
the summary. RI findings and the DQ Report remain unchanged, separate objects.

The implementation uses UUIDv4 strings for summary IDs, matching the UUIDv4 convention
already used for DQ Report IDs. Summary creation timestamps use timezone-aware UTC now.
This records the current implementation convention without changing PES-001 through
PES-017.

The implementation does not add Registry Consistency, the Episode Identity Registry,
Situation B, Semantic Attribution, acceptance/eligibility, persistence, an external API or
UI, or live-client-data processing. `execution_intent` remains opaque. For present-empty
required inputs, discovery and technical results are preserved on
`PipelineOperationalInputError`; because the approved seven-stage model has no readiness
stage, no successful PES is returned and a stage-level representation remains future work.

## 9. Implementation Boundaries and Future Work

This specification does not implement or authorize:

- Python models, enums, construction/reporting functions, or tests.
- The end-to-end pipeline orchestrator.
- Episode Identity Registry or identity-resolution/bootstrap behavior.
- Semantic attribution validation.
- Acceptance, partial-acceptance, exclusion, or eligibility logic.
- Persistence, a database/storage technology, or retention behavior.
- An API, user interface, or monitoring infrastructure.

Implementation planning must settle the remaining open field-contract details that affect
reliable construction. Existing validation components remain responsible for their own
checks; the aggregator calculates only overall status, and the PES builder only constructs
the summary from supplied consolidated outcomes.
