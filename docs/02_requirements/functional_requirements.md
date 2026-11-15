# Functional Requirements

**Document ID:** NCI-FR-001  
**Version:** 0.2  
**Status:** Draft for review

Priority definitions: **Must** = required for MVP; **Should** = desirable for MVP if effort permits; **Could** = later release.

## 1. Data ingestion and validation

| ID | Requirement | Priority |
|---|---|---|
| FR-001 | The system shall ingest customer data from documented CSV templates. | Must |
| FR-002 | The system shall ingest subscription and contract data where available. | Must |
| FR-003 | The system shall ingest billing or transaction data where available. | Must |
| FR-004 | The system shall validate required columns and data types before processing. | Must |
| FR-005 | The system shall report missing, duplicated, invalid, and inconsistent records. | Must |
| FR-006 | The system shall produce a data-quality summary for each ingestion run. | Must |
| FR-007 | The system shall retain source-to-processed lineage metadata. | Should |
| FR-008 | The system should support API-based ingestion in a later release. | Could |

## 2. Feature engineering

| ID | Requirement | Priority |
|---|---|---|
| FR-009 | The system shall generate documented customer-level features from permitted historical data. | Must |
| FR-010 | The system shall calculate tenure and relevant subscription features where available. | Must |
| FR-011 | The system shall calculate payment and usage features where available. | Should |
| FR-012 | The system shall enforce point-in-time feature construction to prevent future-data leakage. | Must |
| FR-013 | The system shall version feature definitions used in model training and scoring. | Should |

## 3. Churn prediction

| ID | Requirement | Priority |
|---|---|---|
| FR-014 | The system shall train and evaluate a baseline churn classifier. | Must |
| FR-015 | The system shall generate a churn probability for each eligible customer. | Must |
| FR-016 | The system shall map probabilities to configurable risk bands. | Must |
| FR-017 | The system shall support batch scoring. | Must |
| FR-018 | The system shall store prediction timestamp and model version with each scoring result. | Must |
| FR-019 | The system should expose individual scoring through an authenticated API. | Should |
| FR-020 | The system should retain historical prediction snapshots for trend analysis. | Should |

## 4. Customer lifetime value

| ID | Requirement | Priority |
|---|---|---|
| FR-021 | The system shall calculate historical customer revenue where source data permits. | Must |
| FR-022 | The system shall estimate future customer value over a documented horizon. | Must |
| FR-023 | The system shall identify whether CLV represents revenue or contribution margin. | Must |
| FR-024 | The system shall document assumptions, forecast horizon, and limitations of each CLV method. | Must |
| FR-025 | The system should support customer-level and aggregate CLV views. | Should |

## 5. Customer segmentation

| ID | Requirement | Priority |
|---|---|---|
| FR-026 | The system shall generate customer segments using documented features. | Must |
| FR-027 | The system shall report segment size and descriptive profile. | Must |
| FR-028 | The system should support configurable segment labels after analytical review. | Should |

## 6. Revenue at risk

| ID | Requirement | Priority |
|---|---|---|
| FR-029 | The system shall calculate expected value at risk using documented assumptions. | Must |
| FR-030 | The system shall provide aggregate and segment-level risk summaries. | Must |
| FR-031 | The system shall distinguish expected revenue exposure from recoverable revenue. | Must |

## 7. Explainability

| ID | Requirement | Priority |
|---|---|---|
| FR-032 | The system shall provide global feature-importance information. | Must |
| FR-033 | The system shall provide local explanations for supported model types. | Must |
| FR-034 | The system shall present explanations as model associations, not causal claims. | Must |

## 8. Dashboard and reporting

| ID | Requirement | Priority |
|---|---|---|
| FR-035 | The dashboard shall display an executive overview. | Must |
| FR-036 | The dashboard shall display churn risk distribution and customer-level results. | Must |
| FR-037 | The dashboard shall display CLV and customer segments. | Must |
| FR-038 | The dashboard shall display revenue-at-risk summaries. | Must |
| FR-039 | The dashboard shall display model metadata and evaluation metrics. | Must |
| FR-040 | The dashboard should support filtering by risk and segment. | Should |
| FR-041 | The system should allow authorised users to export scored results. | Should |

## 9. Administration and audit

| ID | Requirement | Priority |
|---|---|---|
| FR-042 | The system shall record ingestion and scoring run metadata. | Must |
| FR-043 | The system shall identify the model version used for each prediction. | Must |
| FR-044 | The system should support role-based access in the deployed application. | Should |
| FR-045 | The system shall avoid displaying direct identifiers unless required for an authorised business workflow. | Must |

## 10. Requirement traceability

Each Must requirement must be linked to at least one test or acceptance criterion before the MVP release. Requirements may be refined when the first client data contract is agreed.
