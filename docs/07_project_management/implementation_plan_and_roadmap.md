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
