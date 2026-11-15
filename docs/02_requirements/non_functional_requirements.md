# Non-Functional Requirements

**Document ID:** NCI-NFR-001  
**Version:** 0.2  
**Status:** Draft for review

Targets below are initial engineering objectives. They must be validated through profiling and load testing; they are not service-level guarantees.

## 1. Performance

| ID | Requirement | Initial target |
|---|---|---|
| NFR-001 | Batch scoring performance | Score 10,000 eligible customers within 5 minutes on the agreed reference environment |
| NFR-002 | API latency | p95 below 2 seconds for a single-customer scoring request, excluding upstream data retrieval |
| NFR-003 | Standard dashboard views | Load within 5 seconds for agreed test data volume |
| NFR-004 | Long-running jobs | Run asynchronously or provide visible progress/status |

## 2. Scalability

| ID | Requirement |
|---|---|
| NFR-005 | Data ingestion, training, scoring, API, and dashboard components shall be separable modules. |
| NFR-006 | Batch processing shall support increasing customer volumes without requiring a redesign of the domain logic. |
| NFR-007 | Client-specific configuration shall be separated from shared application code. |
| NFR-008 | The system shall support client data and model-artifact isolation. |

## 3. Security and privacy

| ID | Requirement |
|---|---|
| NFR-009 | Data shall be encrypted in transit in deployed environments. |
| NFR-010 | Sensitive stored data shall be encrypted at rest using platform-supported controls. |
| NFR-011 | Secrets and credentials shall not be committed to source control. |
| NFR-012 | Access shall follow least-privilege principles. |
| NFR-013 | Logs shall not expose unnecessary personal or sensitive data. |
| NFR-014 | Data retention and deletion rules shall be configurable and documented. |
| NFR-015 | The deployment shall provide an access and audit trail appropriate to the agreed use case. |

The applicable lawful basis, controller/processor roles, transparency obligations, retention periods, and any DPIA requirement must be assessed with the client and, where needed, qualified privacy/legal advisers. This document is not legal advice or a compliance certification.

## 4. Reliability and recoverability

| ID | Requirement |
|---|---|
| NFR-016 | Invalid input shall fail with actionable validation messages rather than silently producing predictions. |
| NFR-017 | Critical processing steps shall emit structured logs. |
| NFR-018 | Training and scoring runs shall record status, timestamps, configuration, and artefact references. |
| NFR-019 | The application shall handle expected errors without exposing stack traces or secrets to end users. |
| NFR-020 | Backup and recovery procedures shall be defined before production use. |

## 5. Maintainability and testability

| ID | Requirement |
|---|---|
| NFR-021 | Python code shall use modular packages, type hints where practical, and consistent formatting. |
| NFR-022 | Critical business logic shall have unit tests. |
| NFR-023 | Data pipelines and API workflows shall have integration tests. |
| NFR-024 | CI shall run automated tests and quality checks on pull requests. |
| NFR-025 | Model training shall be reproducible from versioned code and configuration, subject to documented environment constraints. |
| NFR-026 | Model artefacts shall be versioned and linked to evaluation results. |

## 6. Model quality and governance

| ID | Requirement |
|---|---|
| NFR-027 | Evaluation shall use a temporally appropriate holdout where timestamps permit. |
| NFR-028 | Performance reporting shall include metrics suitable for class imbalance, including PR-AUC, precision, and recall. |
| NFR-029 | Probability calibration shall be assessed before probabilities are interpreted as risk estimates. |
| NFR-030 | The system shall document model limitations, intended use, and known failure modes. |
| NFR-031 | Monitoring shall detect relevant data and prediction drift where sufficient reference data exists. |
| NFR-032 | Model outputs shall be used as decision support and reviewed by an authorised person before consequential customer action. |

## 7. Usability and accessibility

| ID | Requirement |
|---|---|
| NFR-033 | Dashboard labels and metric definitions shall be understandable to business users. |
| NFR-034 | Risk bands shall be accompanied by definitions and configurable thresholds. |
| NFR-035 | Charts shall include titles, units, and explanatory context. |
| NFR-036 | The interface shall not rely on colour alone to communicate risk. |
