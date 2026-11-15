# MVP Acceptance Criteria

**Document ID:** NCI-AC-001  
**Version:** 0.2  
**Status:** Draft for review

The MVP is accepted only when the criteria below are demonstrated on the agreed development dataset and reference environment.

| ID | Area | Acceptance criterion | Evidence |
|---|---|---|---|
| AC-001 | Ingestion | A valid documented CSV dataset can be loaded successfully. | Automated integration test and run log |
| AC-002 | Validation | Missing required columns or invalid types produce clear validation errors. | Tests and sample error report |
| AC-003 | Data quality | A report summarises missing values, duplicates, and key consistency checks. | Generated data-quality report |
| AC-004 | Leakage control | Features are constructed using information available at the prediction cutoff only. | Feature logic review and temporal test |
| AC-005 | Churn model | At least one baseline and one candidate model are evaluated against a holdout set. | Model comparison report |
| AC-006 | Evaluation | Report includes PR-AUC, ROC-AUC, precision, recall, confusion matrix, and calibration assessment. | Evaluation report |
| AC-007 | Scoring | Batch scoring produces one result per eligible customer. | Output file and automated test |
| AC-008 | Traceability | Each prediction includes prediction timestamp and model version. | Prediction output and database record |
| AC-009 | CLV | CLV output specifies whether it is revenue or contribution margin and states the forecast horizon. | CLV methodology and output |
| AC-010 | Segmentation | Segments have size statistics and interpretable descriptive profiles. | Segmentation report |
| AC-011 | Revenue at risk | Calculation assumptions are visible and exposure is not described as guaranteed recoverable revenue. | Metric definition and dashboard |
| AC-012 | Explainability | Global and supported local explanations can be generated. | Explanation report and tests |
| AC-013 | Dashboard | Executive, churn, CLV/segment, and model-performance views render on reference data. | Demonstration checklist |
| AC-014 | Export | An authorised user can export scored customer results. | Demonstration and test |
| AC-015 | Testing | Critical unit and integration tests pass in CI. | CI run |
| AC-016 | Packaging | Application components can be started using documented Docker instructions. | Clean-environment deployment test |
| AC-017 | Documentation | Setup, data schema, model limitations, and run instructions are documented. | Documentation review |
| AC-018 | Privacy | Test data and logs do not expose unnecessary direct identifiers. | Privacy review checklist |

## Model performance acceptance

No arbitrary ROC-AUC or recall threshold is set before inspecting the dataset and label definition. A model must be compared with a meaningful baseline, evaluated on a leakage-safe holdout, and judged against the business cost of false positives and false negatives.

For a client pilot, acceptance thresholds must be agreed before final evaluation and must reflect the client’s operational capacity and intervention economics.

## Release decision

A release is blocked by:
- Critical data leakage.
- Untraceable predictions.
- Failed critical tests.
- Unexplained data-processing failures.
- Unresolved high-severity security or privacy issues.
- Material mismatch between the documented churn label and the client’s actual business definition.
