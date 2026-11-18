# Data Quality Implementation Architecture

- **Document ID:** NCI-DQ-ARCH-001
- **Version:** 0.2
- **Status:** Draft for technical review
- **Scope:** Phase 2.4.2.1 — Data Quality Implementation Architecture
- **Sources:** Customer Data Contract v1.1, Data Quality Specification v0.2, ADR-003, ADR-009, ADR-010, and Subscription Episode & Lifecycle Decision Specification v0.4

## 1. Purpose and scope

This document defines the package layout, interfaces, models, runtime semantics, report
shape, blocking decision, and testing boundaries for the Data Quality Validation layer.
Implementation is partial: immutable models and the RI and TC rule-family validators exist,
while report assembly, the coordinating public interface, and pipeline integration remain
unimplemented.

The initial executable rule scope is RI-001 through RI-004 and TC-001 through TC-002
from the Data Quality Specification; these rules are implemented in separate RI and TC
modules. This design does not make RI-005, BR-006, BR-010, or any PENDING DECISION or
DEFERRED rule executable. It does not duplicate checks owned by Pandera.

The data remains client-scoped under ADR-003. The prediction entity is an individual
contractual subscription episode under the Subscription Episode & Lifecycle Decision
Specification v0.4 and ADR-010. Nowa Analytics owns canonical episode identity;
`subscription_id` is the canonical episode identifier, while `customer_id` identifies the
associated customer/account and is not a prediction identifier or predictive feature.
Reactivation following termination creates a new episode, and previous episodes remain
historically preserved. See the [episode specification](subscription_episode_lifecycle_decision_specification.md)
and [ADR-010](../03_architecture/adr_episode_identity_and_identifier_management.md).

## 2. Existing project architecture and integration points

The project is a Python 3.12 src-layout modular monolith. Its data package currently has:

| Component | Existing interface and behavior | Status |
|---|---|---|
| CSV Header Inspection | `inspect_csv_header(path, dataset)` checks a CSV header against `DATASET_COLUMNS`. | Implemented in `data/ingestion/header_inspection.py`. |
| CSV Ingestion | `ingest_csv_dataset(path, dataset)` and `ingest_client_datasets(directory)` return pandas DataFrames with source values retained as strings. | Implemented in `data/ingestion/csv_ingestion.py`. |
| Data Type Normalization | `normalize_dataset_types(dataframe, dataset)` and `normalize_client_datasets(datasets)` return normalized copies and raise `DataTypeNormalizationError` for invalid conversions. | Implemented in `data/preprocessing/type_normalization.py`. |
| Pandera schemas | Five exported schemas validate individual dataset columns, types, nullability, keys, and documented field checks with `strict=True` and `coerce=False`. | Implemented in `data/schemas/`. |
| Data Quality models | `models.py` defines immutable findings, summaries, reports, enums, and `DataQualityValidationError`. | Implemented. |
| Referential Integrity | `validate_referential_integrity(datasets)` evaluates RI-001 through RI-004. | Implemented in `data/validation/referential_integrity.py`. |
| Temporal Consistency | `validate_temporal_consistency(datasets)` evaluates TC-001 and TC-002. | Implemented in `data/validation/temporal_consistency.py`. |
| Reporting | Report assembly and aggregate calculation are specified in Section 3.1. | Not implemented; `reporting.py` is absent. |
| Coordination | Public precondition checking and RI/TC coordination are specified in Section 3.1. | Not implemented; `validator.py` and a public coordination interface are absent. |

The current loader treats `customers`, `subscriptions`, and `subscription_snapshots` as
required and `usage_monthly` and `invoices` as optional. The Data Quality entry point should
accept the mapping returned after normalization and schema validation, not file paths or
raw CSV contents. The repository does not currently have a pipeline runner that performs
normalization followed by schema validation across the dataset mapping; this design does
not add one.

Data Quality unit tests exist for models, referential integrity, and temporal consistency
in `tests/unit/data/validation/`. There are no Data Quality unit tests for reporting or
coordination. Existing integration tests cover CSV ingestion only;
`tests/integration/README.md` describes other integration workflows as future work, and no
Data Quality integration test currently exists.

### 2.1 Integration boundary

The intended call order is:

```text
ingest_client_datasets(directory)
    -> normalize_client_datasets(datasets)
    -> validate each present DataFrame with its Pandera schema
    -> validate_data_quality(schema_validated_datasets, metadata...)
    -> DataQualityReport
```

The caller is responsible for invoking Data Quality Validation only after schema
validation succeeds for each supplied DataFrame. The DQ layer must not rerun Pandera, infer
schema validity, normalize or repair values, or mutate any input DataFrame. It may inspect
frames and calculate rule outcomes. Upstream failures remain owned by their respective
stages and do not become DQ findings. This is the intended target call sequence;
`validate_data_quality` and report assembly are not currently available.

## 3. Package structure: implemented and planned components

```text
src/nowa_customer_intelligence/data/validation/
├── __init__.py
├── models.py
├── referential_integrity.py
├── temporal_consistency.py
├── reporting.py
└── validator.py
```

`models.py`, `referential_integrity.py`, and `temporal_consistency.py` currently exist.
`reporting.py` and `validator.py` are planned and not implemented. The structure preserves
separation between models, RI, TC, reporting, and coordination, while keeping one small
public coordination entry point. It avoids a generic plugin system, rule DSL, service layer,
or orchestration framework.

### 3.1 Module responsibilities and interfaces

| Module | Responsibility | Public interface / status |
|---|---|---|
| `models.py` | Define enums, immutable result records, summary/report structures, and the input/precondition exception. | Implemented: `DataQualitySeverity`, `RuleImplementationStatus`, `RuleExecutionResult`, `DataQualityFinding`, `DataQualitySummary`, `DataQualityReport`, `DataQualityValidationError`. |
| `referential_integrity.py` | Evaluate only RI-001–RI-004 across schema-valid DataFrames; compare identifiers as strings without trimming, casting, or normalization. | Implemented: `validate_referential_integrity(datasets) -> tuple[DataQualityFinding, ...]`. |
| `temporal_consistency.py` | Evaluate only TC-001 and TC-002 within the subscription DataFrame. | Implemented: `validate_temporal_consistency(datasets) -> tuple[DataQualityFinding, ...]`. |
| `reporting.py` | Create report metadata, dataset-presence flags, counts, and a client-scoped report from rule results. No serialization or persistence. | Planned, not implemented: `build_data_quality_report(...) -> DataQualityReport`. |
| `validator.py` | Check call preconditions, coordinate RI and TC validators, calculate blocking datasets, and return a report. It does not orchestrate upstream/downstream pipeline stages. | Planned, not implemented: `validate_data_quality(...) -> DataQualityReport`. |
| `__init__.py` | Re-export the supported public models, error, and main entry point. | Planned; current initializer does not expose a coordination interface. |

Validator functions should use explicit, small signatures and return immutable tuples of
findings. Internal helpers may be private to their rule-family module. Reporting and
blocking are intentionally simple functions over model values, rather than separate
frameworks.

## 4. Data models and interfaces

Use standard-library `dataclasses` and `enum.Enum`. The codebase already uses a dataclass
for `DatasetColumns`; Pandera objects and pandas DataFrames are the established data
interfaces. Pydantic is already a dependency, but the proposed report is an in-memory
Python result and this phase does not serialize it or accept an untrusted external report
payload. Dataclasses avoid an extra model convention and need no new dependency. If a future
serialization/API requirement appears, evaluate its validation needs separately.

Implementation status and execution result must be separate enum types, never a shared
generic status field:

```python
class DataQualitySeverity(Enum):
    ERROR = "ERROR"
    WARNING = "WARNING"
    INFO = "INFO"


class RuleImplementationStatus(Enum):
    ALREADY_IMPLEMENTED = "ALREADY IMPLEMENTED"
    PROPOSED = "PROPOSED"
    PENDING_DECISION = "PENDING DECISION"
    DEFERRED = "DEFERRED"
    IMPLEMENTED_IN_DQ = "IMPLEMENTED IN DATA QUALITY"


class RuleExecutionResult(Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    NOT_APPLICABLE = "NOT_APPLICABLE"
    NOT_EVALUATED = "NOT_EVALUATED"
```

The distinct enum types make implementation lifecycle and actual runtime outcome
unambiguous to callers and static type checking. Report construction should preserve those
types and must not derive an execution result from implementation status alone.
`ALREADY_IMPLEMENTED` identifies checks owned by another layer and must not be emitted as
DQ findings. `IMPLEMENTED_IN_DQ` identifies executable rules actively enforced by the DQ
layer and is defined in the Data Quality Specification. A rule may transition from
`PROPOSED` to `IMPLEMENTED_IN_DQ` only after its DQ implementation and required tests are
complete and reviewed.

Proposed minimum immutable dataclass fields:

| Model | Minimum fields |
|---|---|
| `DataQualityFinding` | `rule_id: str`, `implementation_status: RuleImplementationStatus`, `severity: DataQualitySeverity`, `result: RuleExecutionResult`, `datasets: tuple[str, ...]`, `description: str`, `records_evaluated: int | None`, `records_affected: int | None`, `blocking_datasets: tuple[str, ...]`. |
| `DataQualitySummary` | `severity_counts: Mapping[DataQualitySeverity, int]`, `result_counts: Mapping[RuleExecutionResult, int]`, `blocked: bool`, `blocked_datasets: tuple[str, ...]`. |
| `DataQualityReport` | `report_id: str`, `run_id: str`, `client_scope: str`, `created_at_utc: datetime`, `contract_version: str`, `specification_version: str`, `pipeline_stage: str`, `dataset_presence: Mapping[str, bool]`, `summary: DataQualitySummary`, `findings: tuple[DataQualityFinding, ...]`. |

`created_at_utc` should be timezone-aware and normalized to UTC. Report construction may
generate a UUID `report_id`; callers may inject `created_at_utc` for deterministic tests.
`pipeline_stage` is the constant `data_quality_validation`. The caller supplies a
pseudonymous `client_scope`; it must never be replaced with a direct customer or source
identifier.

All report models and their contents must be deeply immutable after construction. Use
`@dataclass(frozen=True)` for immutable attributes, tuples for every sequence field, and
`MappingProxyType` for mapping fields. Before wrapping each mapping, make a defensive copy
(`MappingProxyType(dict(source_mapping))`) so a caller retaining the original mapping cannot
change report contents through that reference. Mapping values must themselves be immutable
scalars or enums. Do not place mutable lists, sets, dictionaries, DataFrames, or other
mutable objects inside report fields. This applies to `DataQualitySummary.severity_counts`,
`DataQualitySummary.result_counts`, `DataQualitySummary.blocked_datasets`,
`DataQualityReport.dataset_presence`, `DataQualityReport.findings`,
`DataQualityFinding.datasets`, and `DataQualityFinding.blocking_datasets`. Callers must
not be able to change report attributes or nested contents after construction.

During report-model construction, defensively convert sequence inputs to tuples (preferred)
or reject mutable sequence inputs. In particular, convert `DataQualityFinding.datasets`,
`DataQualityFinding.blocking_datasets`, `DataQualitySummary.blocked_datasets`, and
`DataQualityReport.findings` to tuples. Retaining a caller-provided list is prohibited: a
later mutation of that list must never change an already constructed report. Every finding
inside `DataQualityReport.findings` must itself be a frozen, deeply immutable model.
These sequence rules are in addition to, and do not replace, the defensive-copy and
`MappingProxyType` requirements for mappings.

`DataQualityValidationError` should be a `ValueError` subclass for invalid invocation
preconditions only, such as a non-DataFrame dataset value or missing required input
datasets. It must not represent ordinary RI/TC violations: rule failures produce a report
and blocking decision. Its message must be safe and must not include raw row values,
identifiers, file paths, credentials, or DataFrame representations.

### 4.1 Main entry point contract

```python
def validate_data_quality(
    datasets: Mapping[str, pd.DataFrame],
    *,
    run_id: str,
    client_scope: str,
    contract_version: str = "1.1",
    specification_version: str = "0.2",
    created_at_utc: datetime | None = None,
) -> DataQualityReport: ...
```

The mapping contains schema-validated DataFrames keyed by contract dataset name. Under
current ingestion behavior, `customers`, `subscriptions`, and
`subscription_snapshots` are required inputs; `usage_monthly` and `invoices` may be absent.
An unknown key or absent required input is an invocation error, not a DQ rule finding. The
function must not modify the input mapping or frames. The report records presence for all
five known datasets, including absent optional datasets.

Input metadata must satisfy these invocation preconditions:

| Input | Validation requirement |
|---|---|
| `run_id` | Must be a string containing at least one non-whitespace character. Reject empty and whitespace-only strings. After validation, preserve the exact original string; do not trim or rewrite it. |
| `client_scope` | Must be a pseudonymous string containing at least one non-whitespace character. Reject empty and whitespace-only strings. After validation, preserve the exact original string; do not trim or rewrite it. The caller supplies the pseudonymous client-scoped value; this interface does not define an identity or pseudonym-generation mechanism. |
| `created_at_utc` when supplied | Must be a timezone-aware `datetime`. Reject a naive timestamp; do not assume UTC. Normalize an aware timestamp to UTC before building the report. |
| `created_at_utc` when omitted | Generate the current timestamp in UTC. |

Invalid metadata is an invalid invocation and raises `DataQualityValidationError`, with a
safe message. The error remains reserved for invalid invocation preconditions, including
invalid metadata and dataset mapping preconditions; ordinary RI/TC violations produce a
report and blocking decision. Do not silently trim or otherwise rewrite `run_id` or
`client_scope`.

Validate non-whitespace content without changing accepted metadata: surrounding whitespace
on an otherwise valid value remains part of the exact string preserved in the report.

No extraction cutoff, snapshot convention, or episode-boundary argument is needed for
TC-001/TC-002. Do not add temporal inputs for rules outside the approved initial scope.

## 5. Rule execution and scope

Only these rules are executable in the first implementation slice:

| Rule | Module | Inputs | Execution behavior |
|---|---|---|---|
| RI-001 | `referential_integrity.py` | `subscriptions.customer_id`, `customers.customer_id` | Find subscription references absent from the customer key set. Do not repeat key nullability or uniqueness checks. |
| RI-002 | `referential_integrity.py` | `subscription_snapshots.subscription_id`, `subscriptions.subscription_id` | Find snapshot references absent from the subscription key set. Do not repeat snapshot composite uniqueness. |
| RI-003 | `referential_integrity.py` | Optional `usage_monthly.subscription_id`, `subscriptions.subscription_id` | Evaluate only when `usage_monthly` is supplied; if absent, this implemented rule is `NOT_APPLICABLE`. |
| RI-004 | `referential_integrity.py` | Optional `invoices.subscription_id`, `subscriptions.subscription_id` | Evaluate only when `invoices` is supplied; if absent, this implemented rule is `NOT_APPLICABLE`. |
| TC-001 | `temporal_consistency.py` | `subscriptions.start_date`, `subscriptions.end_date` | Fail rows with a present `end_date` earlier than `start_date`; nullable `end_date` is not evaluated as a violation. |
| TC-002 | `temporal_consistency.py` | `subscriptions.start_date`, `subscriptions.cancellation_date` | Fail rows with a present `cancellation_date` earlier than `start_date`; nullable `cancellation_date` is not evaluated as a violation. |

Use only schema-validated types and values. Referential comparisons must preserve identifier
strings exactly. They must not trim whitespace or cast IDs. Null relationship identifiers
and duplicate primary/composite keys are already rejected by Pandera and must not be
rechecked here. Invoice date consistency is already owned by `INVOICE_SCHEMA`; it is not a
DQ rule in this scope.

For an implemented applicable rule, return `PASS` when no violations exist and `FAIL` when
violations exist. Optional-dataset RI rules return `NOT_APPLICABLE` if their dataset is
absent. The implementation status and runtime result remain independent fields. No
PENDING DECISION or DEFERRED rule is registered for execution. BR-006 remains PROPOSED and
unimplemented; optional dataset presence is represented by `dataset_presence`, does not
block, and is not a BR-006 PASS or finding. RI-005 and BR-010 are also outside this
implementation scope.

RI-001–RI-004 and TC-001–TC-002 are implemented and their implementation status is
`IMPLEMENTED_IN_DQ`. Runtime result remains separate: the validators return PASS, FAIL, or
NOT_APPLICABLE according to the defined applicability and outcomes. Reporting and
coordination are not implemented, so no complete Data Quality report or public combined
execution is available.

## 6. Rule execution lifecycle

1. The caller completes header inspection, ingestion, normalization, and Pandera validation
   for supplied datasets.
2. The caller supplies the schema-valid dataset mapping and run/client metadata to
   `validate_data_quality`.
3. The validator records dataset presence, runs the RI and TC modules for the approved
   rules, and collects their typed findings.
4. The coordinator derives blocked datasets only from applicable **ERROR** findings whose
   runtime result is `FAIL`. WARNING and INFO results do not block by default.
5. Reporting builds a client-scoped `DataQualityReport`, including result counts and the
   blocking decision, and returns it to the caller.

The function does not call the upstream stages, change datasets, persist a report, or
control downstream execution. The caller decides what to do with `summary.blocked`; a
future pipeline integration may use it to gate processing. Upstream failures must remain in
their owning stage or a future Pipeline Execution Summary, not be copied into this report.

## 7. Data Quality Report design

The in-memory report maps to the fields required by Data Quality Specification v0.2:

| Field | Proposed source and constraints |
|---|---|
| `report_id` | UUID generated during report construction. |
| `run_id` | Required caller-provided execution identifier. |
| `client_scope` | Required pseudonymous, client-scoped value; never a cross-client key or direct identity. |
| `created_at_utc` | UTC-aware timestamp; generated in UTC unless injected by the caller. |
| `contract_version` | Caller-supplied contract version, default `1.1`. |
| `specification_version` | Caller-supplied DQ specification version, default `0.2`. |
| `pipeline_stage` | Constant `data_quality_validation`. |
| `dataset_presence` | Boolean presence for the five known datasets; optional files may be absent without failure. |
| `summary` | Counts by severity and result, `blocked`, and the datasets affected by blocking findings. |
| `findings` | Immutable sequence of typed rule result records with sanitized descriptions and aggregate counts. |

For each finding, `records_evaluated` is the number of source records actually evaluated
by the rule. `records_affected` is the number of source records that violate it. Both are
non-negative integers (excluding booleans) when present, and count source records rather
than distinct identifier values. Interpret them as follows:

| Rule | `records_evaluated` | `records_affected` |
|---|---|---|
| RI-001 | Subscription records evaluated against customer identifiers. | Subscription records with invalid customer references. |
| RI-002 | Snapshot records evaluated against subscription identifiers. | Snapshot records with invalid subscription references. |
| RI-003 | Usage records evaluated against subscription identifiers. | Usage records with invalid subscription references. |
| RI-004 | Invoice records evaluated against subscription identifiers. | Invoice records with invalid subscription references. |
| TC-001 | Subscription records with both start and end dates present, evaluated for chronology. | Records with an end date earlier than the start date. |
| TC-002 | Subscription records with both start and cancellation dates present, evaluated for chronology. | Records with a cancellation date earlier than the start date. |

For `NOT_APPLICABLE` or `NOT_EVALUATED` results, both counts should be `None` unless
meaningful evaluation actually occurred; when counts are present, they retain the same
definitions. Do not expose identifiers or source values in findings.

The initial report contains results only for RI-001–RI-004 and TC-001–TC-002. Counts by
severity should count failed rule results at that severity; counts by runtime result should
count all rule result records, including `PASS` and `NOT_APPLICABLE`. `NOT_EVALUATED` is
not a pass or violation. Do not add a BR-006 runtime record as if it were executed; if a
separate execution ledger later records its unimplemented state, the result is
`NOT_EVALUATED`.

Findings must not contain raw records, direct customer/subscription/invoice identifiers,
source values, full DataFrames, absolute filesystem paths, credentials, or unsanitized
parser/validation messages. Use rule IDs, dataset/column names, aggregate affected-record
counts, safe descriptions, and client-scoped pseudonymous metadata. The model is an
in-memory interface only: serialization, storage, retention, and access control are not
implemented or selected here.

## 8. Blocking policy design

Blocking is a pure decision over rule outcomes, not orchestration:

| Severity and result | Blocking behavior |
|---|---|
| ERROR + `FAIL` | Mark only the datasets identified by that rule as blocked and indicate that their dependent downstream processing must stop. For RI failures, include the participating parent and child datasets. |
| ERROR + `PASS` | Does not block. |
| WARNING + `FAIL` | Does not block by default; retain for review. |
| INFO | Does not block. |
| `NOT_APPLICABLE` or `NOT_EVALUATED` | Does not block. |

`blocked` is true if at least one ERROR failure blocks a dataset. `blocked_datasets` is the
stable, deduplicated set of affected dataset names. Do not infer record repair, dropping,
quarantine, partial acceptance, or recovery behavior. This design does not add a global
pipeline outcome or automatically stop downstream modules.

## 9. Testing architecture

Tests for the later implementation should use synthetic in-memory DataFrames only. They
must not read live client data or depend on external services.

| Test module and status | Responsibility |
|---|---|
| Implemented: `tests/unit/data/validation/test_models.py` | Enum separation, immutable result construction, report fields, and safe input/precondition error behavior. |
| Implemented: `tests/unit/data/validation/test_referential_integrity.py` | RI-001–RI-004 parent/child matching, orphan detection, optional dataset absence, string identity preservation, and no input mutation. |
| Implemented: `tests/unit/data/validation/test_temporal_consistency.py` | TC-001/TC-002 valid chronology, equality boundary, earlier end/cancellation date, nullable end/cancellation fields, and no input mutation. |
| Planned, absent: `tests/unit/data/validation/test_reporting.py` | Report metadata, dataset-presence flags, deterministic timestamp injection, result/severity counts, sanitized descriptions, and no BR-006 pass/finding. |
| Planned, absent: `tests/unit/data/validation/test_validator.py` | Preconditions, rule coordination, output ordering, separate status/result fields, and blocking decisions for each severity/result combination. |
| Planned, absent: `tests/integration/test_data_quality_validation.py` | Schema-valid synthetic dataset mappings through the public entry point, including combined RI/TC failures and optional datasets independently absent or present. |

Unit tests should isolate each rule family and model/report behavior. Integration tests
should validate only the DQ interface over already schema-valid frames; schema validation
itself remains covered by existing schema tests. Assert that input frames and their
contents are unchanged after all DQ calls. Include privacy assertions that identifiers and
raw values do not appear in report messages. Freeze or inject report time for deterministic
tests.

## 10. Implementation sequence for Phase 2.4.2

Steps 1–3 are complete in the current repository. Steps 4–7 remain planned; the complete
Data Quality report, coordinating public entry point, DQ integration tests, and broader
pipeline integration are not implemented.

1. **Completed:** Add typed models, enums, summary/report structures, and safe precondition exception.
2. **Completed:** Implement and unit-test RI-001–RI-004 in their own module.
3. **Completed:** Implement and unit-test TC-001 and TC-002 in their own module.
4. **Planned:** Add report construction and pure blocking calculation, then test counts, result
   semantics, and privacy constraints.
5. **Planned:** Add the coordinating public entry point and unit tests for preconditions and ordering.
6. **Planned:** Add synthetic integration tests through the public DQ interface and verify no input
   mutation.
7. **Planned:** Review the implementation against the Data Quality Specification and open decisions
   before any broader pipeline integration is considered.

Do not expand this initial slice to RI-005, BR-006, BR-010, or pending/deferred rules
without a separately approved scope and decisions.

## 11. Design decisions and unresolved questions

### Decisions proposed here

- Use standard-library dataclasses and distinct enum types; do not add dependencies.
- Accept a mapping of schema-validated DataFrames, not file paths or raw CSV data.
- Keep RI and TC in separate modules and coordinate them with a small validator function.
- Return rule violations and blocking decisions in a report; reserve
  `DataQualityValidationError` for invalid invocation preconditions.
- Do not mutate input frames, duplicate Pandera checks, serialize or persist reports, or
  integrate orchestration in this architecture phase.
- Record optional dataset presence independently from BR-006; an absent optional dataset
  is not a pipeline failure.

### Unresolved questions and dependencies

| Question/dependency | Design impact |
|---|---|
| Snapshot requirement | Whether snapshots are required for every DQ run remains unresolved. The current loader requires snapshots, while the contract says they are required for temporal modelling and the Data Quality Specification records basic-validation policy as unresolved. This proposal follows the current loader for the initial entry point; product policy must confirm before a broader pipeline interface is settled. |
| Pipeline execution metadata | The repository has no run-ID or client-scope provider. The caller must supply both until an orchestration layer is designed. |
| `client_scope` governance | ADR-003 requires client isolation, but the pseudonymous identifier format, lifecycle, and source are not defined here. |
| Report serialization and retention | Format, storage, access controls, retention, deletion, and report version migration remain for a later design. |
| Foreign-key failure scope | This design blocks both participating datasets for RI failures; product owners should confirm whether later workflows may safely isolate unaffected datasets. |
| DQ rule result inventory | The specification says reports contain rule-level results, while BR-006 is unimplemented and must not be represented as executed. This design excludes BR-006 from findings and keeps optional dataset presence in `dataset_presence`. |
| Contract pipeline diagram | The Data Quality Specification notes a documented ordering discrepancy: the executable code path normalizes types before Pandera although the contract diagram differs. Reconcile through a later documentation review; this design follows the implemented dependency. |
| Separate named DQ stages | The contract lists DQ Checks, RI Validation, and Temporal Validation separately; the current DQ Specification groups these families under one DQ layer. Confirm whether production needs separate execution-stage records before orchestration is designed. |

The approved prediction entity is the individual contractual episode. ADR-010 establishes
Nowa ownership of canonical episode identity, UUID as the initial generation strategy, and
the requirement for a persistent Episode Identity Registry. Reactivation following
termination creates a new episode, and prior episodes remain historically preserved.

The current Data Quality implementation does not implement UUID generation, the Episode
Identity Registry, cross-submission identity resolution, source-system mapping, episode
attribution for snapshots, usage, or invoices, or episode-aware ingestion or orchestration.
These capabilities require separate implementation authorization and design.

DD-001, DD-004, DD-006, DD-010, and DD-011 remain relevant to rules outside TC-001/TC-002.
No snapshot first/last-day convention, usage-period boundary, invoice availability rule, or
source-record episode attribution is resolved here. The approved reactivation direction
does not itself resolve lifecycle event criteria, episode boundaries, or dependent-record
attribution.

## Revision history

| Version | Revision |
|---|---|
| 0.2 | Clarifies deep immutability, record-count semantics, input metadata validation, and alignment with Data Quality Specification v0.2. |
