# Implementation Plan and Roadmap

**Document ID:** NCI-PM-001  
**Version:** 0.2  
**Status:** Draft for review

## 1. Delivery approach

Work will proceed in small, reviewable phases. Each phase must produce an artefact and pass its acceptance checks before the next phase begins.

The initial planning estimate is 12–16 weeks of individual development effort, subject to scope, data quality, and time availability. This is a planning range, not a delivery commitment.

## 2. Phases

| Phase | Workstream | Main activities | Deliverables |
|---|---|---|---|
| 0 | Product definition | Review business case, scope, requirements, architecture | Approved documentation baseline |
| 1 | Repository and environment | Create GitHub repository, package structure, virtual environment, quality tooling | Reproducible development environment |
| 2 | Data acquisition | Record dataset sources, download and validate development data | Raw data inventory and source register |
| 3 | Data understanding | EDA, data-quality analysis, label feasibility | EDA and data-readiness report |
| 4 | Feature engineering | Point-in-time snapshots, feature pipeline, leakage checks | Versioned feature pipeline |
| 5 | Churn modelling | Baseline, candidate models, temporal evaluation | Churn model report and artefact |
| 6 | CLV modelling | Select suitable CLV method and forecast horizon | CLV model/report |
| 7 | Segmentation | RFM/behavioural features, clustering, profiling | Segmentation report |
| 8 | Explainability and risk | SHAP, risk bands, revenue exposure calculations | Explainability and risk outputs |
| 9 | Dashboard | Executive, churn, CLV, segments, model performance | Functional dashboard |
| 10 | API and persistence | Add API and database if justified by workflow | Scoring service and persistence layer |
| 11 | MLOps and packaging | MLflow, Docker, CI, monitoring hooks | Reproducible release candidate |
| 12 | Pilot readiness | Security/privacy review, client mapping, operational runbook | Pilot deployment package |

## 3. Suggested initial schedule

| Period | Focus |
|---|---|
| Weeks 1–2 | Documentation approval, repository, environment |
| Weeks 3–4 | Data acquisition, EDA, data-readiness |
| Weeks 5–6 | Feature engineering and churn baseline |
| Weeks 7–8 | Churn candidate models and evaluation |
| Weeks 9–10 | CLV and segmentation |
| Weeks 11–12 | Explainability and dashboard |
| Weeks 13–14 | Testing, Docker, MLOps foundations |
| Weeks 15–16 | Pilot-readiness review and documentation |

The schedule may change based on data issues and the decision to build API/database components in the MVP.

## 4. Working method

For each phase:
1. Agree the objective.
2. Review inputs and dependencies.
3. Implement a small increment.
4. Run tests and inspect outputs.
5. Document decisions and limitations.
6. Review acceptance criteria.
7. Commit changes to Git.
8. Confirm whether the phase is complete.

## 5. Git workflow

Suggested branches:
- `main`: stable, reviewed code.
- `develop`: integration branch if needed.
- `feature/<short-description>`: individual changes.
- `fix/<short-description>`: corrections.

Use pull requests for changes that materially affect the product. Keep commits focused and descriptive.

## 6. First implementation milestone

The first coding milestone is not model training. It is a clean repository and reproducible environment with:
- Project structure.
- README.
- Dependency management.
- Configuration approach.
- Logging.
- Basic tests.
- CI workflow.
- Data directories excluded appropriately from Git.

## 7. Definition of done

A phase is complete when:
- Deliverables exist.
- Acceptance checks pass.
- Tests pass where applicable.
- Documentation is updated.
- Known limitations are recorded.
- Changes are committed.
- The next phase's dependencies are understood.

## 8. Synthetic generator Batch 02 implementation record

WP-01 was accepted for configuration and run context after 169 targeted tests passed. Its seven-file local checkpoint is `79d38498e51e51d4e7c2e04e22feef5fb4635fc2`. WP-02 and WP-03 are implemented and tested. The project owner accepted those two work packages under Batch 03 after all 22 targeted tests passed and repository-wide Ruff checks passed.

- **WP-02.** `create_random_stream(master_seed, name, namespace="default")` uses `numpy.PCG64+sha256/nci-stream-v1`. SHA-256 covers the ASCII bytes `nowa.synthetic.stream.v1`, one NUL byte, eight unsigned big-endian seed bytes, the ASCII namespace, one NUL byte and the ASCII stream name. The digest interpreted as an unsigned big-endian integer seeds NumPy's explicit `PCG64` bit generator. Each call creates a fresh generator at its initial state. The seed range is 0 through 2⁶³ − 1. Names and namespaces are bounded lowercase ASCII labels. Replay, a fixed derivation vector, creation-order independence and global state isolation were verified locally on NumPy 2.5.4. Cross-version or cross-platform output equivalence and L1/L2/L3 verification remain with WP-10.
- **WP-03.** `generate_customers(effective)` uses the `customer.created-at` stream in the selected scenario ID namespace. It returns an ordered tuple of immutable accounts with population-local `synthetic-customer-NNNNNN` ordinal IDs, a date sampled uniformly from the inclusive configured history and fictional baseline country `GB`. The date distribution is an engineering assumption. Industry, company size and account status are omitted pending configured assumptions. The supported date window must fit the existing UTC nanosecond representation. The population is held in memory and uniqueness applies within that population. Subscription references and production CSV projection require later work.
- **Evidence.** The consolidated suite passed 843 tests (797 unit and 46 integration), with no failures or skips. WP-02 and WP-03 both reached 100% statement coverage in their modules. Customer populations of 1, 12 and 1,000 records passed the existing customer type normalisation and schema checks. No customer CSV, linked subscription population or multi-dataset validation claim was produced.

## 9. Synthetic generator Batch 03 implementation record

WP-02 and WP-03 were accepted after 22 targeted tests and repository-wide Ruff checks passed. The six-file local checkpoint is `a32c9995cfece871474b51a46070c5dc79a82866`. WP-04 and WP-05 are partially completed and await review of their bounded foundations.

| Requirement | Decision status and implemented boundary |
|---|---|
| Canonical episode ownership and customer relationship | Approved — implementable. ADR-009/010, PD-002 and BDR-001 govern one caller-established episode per supplied UUID and exactly one explicit owning customer. Duplicate UUIDs and missing customer references are rejected. |
| Supplied UUIDs for development | Synthetic-only assumption — explicitly authorised by Batch 03. Validate the supplied standard UUID spelling and value, retain its spelling and check duplicate UUID values irrespective of casing. Generation, persistence and matching are outside this interface. |
| UUID issuance and durable registry | Open — implementation blocked by BDR-013, RPR-015, DD-EP-003 and RPR-016. Select and validate issuance, replay, persistence and lineage mechanisms before generating canonical IDs. |
| Establishment evidence and historical preservation | Approved — implementable at the supplied-fact boundary. Establishment timestamps are explicit, timezone-aware and separately represented. Supplied historical episodes retain their records. Confirmed reactivation requires a separate episode per BDR-002, with automated allocation blocked by BDR-013. |
| Lifecycle transitions, termination evidence and concurrency | Open — implementation blocked by BDR-014 and DD-EP-001/005–007. Status is a supplied category. This interface performs no state replay, termination inference or policy adjudication for concurrent episodes. |
| Snapshot convention and production projection | Not applicable to this batch. BDR-010 and BDR-015 continue to govern unresolved temporal conventions. Existing schemas were exercised on in-memory fixture fields. |
| Fictional commercial arithmetic | Synthetic-only assumption — explicitly authorised. Apply the Fieldwise GBP list prices and 10% annual discount using exact penny amounts. Validate explicit invoice identifiers, dates, non-negative finite Decimal amounts and supplied ownership. |
| Billing schedules, semantic attribution and accounting | Open — implementation blocked by BDR-012, DD-EP-011 and BDR-017. No date, payment status, refund or recognition policy is inferred from an invoice or episode. |

The consolidated suite passed 891 tests (844 unit and 47 integration), with zero failures or skips. The 210 targeted synthetic tests included 47 new unit tests and one new cross-component integration test. Both new modules reached 100% statement coverage. Repository-wide Ruff lint and format, dependency consistency and whitespace checks passed. The integration fixture preserved customer records, passed the existing subscription and invoice schema checks and wrote no files. This evidence covers explicit facts and arithmetic. Full lifecycle, billing histories, policy-based semantic attribution and production projection remain outside the implemented foundation.

### Batch 04 foundation verification

- **WP-04 — Foundation Implemented and Verified; Full WP Pending**
- **WP-05 — Foundation Implemented and Verified; Full WP Pending**

All 48 targeted episode, billing and integration tests passed. Repository-wide Ruff lint and formatting passed. Verification covers supplied UUIDs and ownership, preservation of explicit episode facts, exact GBP catalogue arithmetic and validation of supplied invoice facts. Identity issuance, lifecycle replay, billing schedules and formal full-package acceptance remain pending.

## 10. Synthetic generator Batch 04 vertical slice

The verified WP-04/05 foundations are checkpointed in `20c4cee83553fc07b05f1522934635b2195ec9da`. Full work-package acceptance remains pending.

- **WP-06.** `UsageRecord` and `validate_usage` check explicit inclusive coverage dates, subscription ownership, uniqueness by labelled month, non-negative quantities, user counts, and optional availability against the extraction cutoff. `SnapshotRecord` and `validate_snapshots` check explicit historical status and separate occurrence, effective, availability and observation timestamps. Supported commercial facts use the existing fictional GBP catalogue and monthly-normalised revenue. No monthly convention, lifecycle replay or behavioural distribution is inferred.
- **WP-08.** `project_development_population` checks the declared inventory, customer coverage and supported record relationships, then returns immutable contract-ordered rows. `export_development_csvs` uses exclusive writes in a caller-supplied empty temporary directory. Internal timestamps and periods stay out of contract columns. Missing optional columns are represented by empty values, and unsupported fields fail projection. This interface is for development fixtures only.
- **Evidence.** BASIC succeeded with 2 customers, 2 subscriptions, 1 usage record and 1 invoice across four CSVs. TEMPORAL succeeded with the same records plus 1 historical snapshot across five CSVs. Both passed existing schema, applicable referential-integrity and data-quality gates, including TC-001/002 date ordering. RI-002 was inapplicable to BASIC without snapshots and passed for TEMPORAL. These checks do not establish broader historical correctness, semantic attribution for client sources or model eligibility.
- **Quality.** The targeted synthetic and pipeline suites passed 276 tests. The full suite passed 928 tests (879 unit, 49 integration), with no failures or skips. Statement coverage was 100% for `observations.py` and 97% for `projection.py`. Its uncovered statements are defensive unsupported-type, unsupported-field and missing-required-value guards. Ruff lint and formatting, dependency consistency and whitespace checks passed.
- **Remaining decisions.** BDR-010 requires an explicit monthly snapshot convention and termination-date treatment. BDR-011 requires agreed usage coverage boundaries. BDR-015 governs model observation and availability cutoffs. BDR-013, DD-EP-003, BDR-014 and BDR-012 still block source-generated identity, lifecycle and billing histories. The development slice is ready for technical review. Full WP-06 and WP-08 acceptance remains pending.

### Batch 05 foundation reverification

- **WP-06: Foundation Verified — Full Work Package Pending.**
- **WP-08: Development Projection Verified — Production Integration Pending.**

All 66 observation, projection and pipeline tests passed. Repository-wide Ruff lint and format checks passed. BASIC without snapshots and TEMPORAL with snapshots passed the implemented pipeline gates using temporary fixture exports. Semantic attribution, full historical correctness, model eligibility and production publication remain outside this checkpoint.

## 11. Synthetic generator Batch 05 evidence foundations

WP-06 and WP-08 foundation reverification is checkpointed in `bb855d81131c65dd3a3731d2939a6553b218e98c`. All 66 checkpoint tests passed.

- **WP-07.** Immutable `OutcomeRecord` and `OutcomeEvidence` retain the five supplied internal states, source references, temporal evidence and observation and ascertainment cutoffs. `validate_outcomes` checks unique episode observations and explicit ownership. Structural checks do not establish event qualification, completeness or model eligibility. No binary label, outcome persistence or contract projection is implemented.
- **WP-09.** `validate_synthetic_evidence` reuses the domain validators and checks explicit source bindings, episode lineage, cutoff chronology and feature availability. Its fixed diagnostic categories distinguish passed, failed, not evaluated and blocked by unresolved policy. Canonical allocation, lifecycle replay, billing schedules, monthly conventions, target and eligibility remain policy-blocked. The existing pipeline is unchanged.
- **WP-11.** Isolated one-defect fixtures cover duplicate episode or observation grains, missing ownership, unknown references, contradictory facts, future evidence, incorrect invoice attribution, invalid outcome evidence and unsupported transitions. Tests check rejection and preservation of the valid fixture. The suite covers implemented checks only.
- **Evidence.** The 45 new tests passed. The full suite passed 973 tests (923 unit and 50 integration), with no failures or skips. Both new modules reached 100% statement coverage. Ruff lint and formatting, dependency consistency and whitespace checks passed. An integration fixture passed the existing BASIC pipeline with customer and subscription CSVs while outcome truth remained internal.
- **Remaining work.** BDR-013 and DD-EP-003 govern identity issuance and persistence, BDR-014 governs lifecycle, BDR-012 governs billing timing, and BDR-010/011/015 govern temporal generation. CGQ-006/007/010–012/021 and CGQ-016 govern later outcome certification and eligibility. Full WP-07, WP-09 and WP-11 acceptance remains pending. WP-10 has not started.

### Batch 06 foundation acceptance

WP-07, WP-09 and WP-11 foundations are accepted within their Batch 05 scope after 45 targeted tests and repository-wide Ruff lint and formatting passed. Full work packages remain pending. Supplied internal outcome truth and isolated negative fixtures confer no production outcome or eligibility certification.
