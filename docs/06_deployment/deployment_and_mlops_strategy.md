# Deployment and MLOps Strategy

**Document ID:** NCI-DEP-001  
**Version:** 0.2  
**Status:** Draft for review

## 1. Deployment principles

- Develop locally first.
- Package repeatable components with Docker.
- Separate training from inference.
- Track experiments and model versions.
- Keep client data and artefacts isolated.
- Deploy only after security, privacy, and operational review.
- Select cloud services based on the pilot's actual requirements.

## 2. Environments

| Environment | Purpose |
|---|---|
| Local development | Coding, notebooks, unit tests |
| Docker test environment | Reproducible integration testing |
| Pilot | Controlled client validation |
| Production | Operational client service |

Environment configuration and secrets must be separate. Production credentials must never be committed to Git.

## 3. Initial technology choices

- Python 3.12.
- Pandas and NumPy.
- Scikit-learn and selected gradient-boosting libraries.
- SHAP.
- MLflow.
- Pandera.
- PostgreSQL.
- Streamlit.
- FastAPI where an API integration is required.
- Docker and Docker Compose.
- GitHub Actions.

Exact package versions should be pinned after the environment is created and tested.

## 4. CI/CD

Initial CI workflow:
1. Install dependencies.
2. Run formatting/lint checks.
3. Run unit tests.
4. Run integration tests that do not require live client data.
5. Build Docker image.
6. Publish artefacts only through an approved release workflow.

Production deployment should require a controlled approval step.

## 5. Model lifecycle

1. Experiment created and tracked in MLflow.
2. Evaluation report generated.
3. Candidate model reviewed.
4. Model artefact and metadata versioned.
5. Approved model promoted to the scoring environment.
6. Predictions record model version and timestamp.
7. Monitoring results reviewed.
8. Retraining or rollback initiated when justified.

## 6. AWS deployment options

Potential services, subject to design and cost review:

| Service | Potential use |
|---|---|
| Amazon S3 | Approved data and model artefact storage |
| Amazon ECR | Container image registry |
| Amazon ECS | Run containerised API/dashboard or batch jobs |
| Amazon RDS for PostgreSQL | Managed relational database |
| Amazon CloudWatch | Logs, metrics, alarms |
| AWS IAM | Identity and access management |
| AWS Secrets Manager | Secret storage |
| Amazon SageMaker | Managed training and/or inference where justified |

Do not assume every service is required. For a small pilot, a simpler deployment may be more cost-effective and easier to operate.

## 7. Operational controls

Before production:
- Define service owner and support process.
- Define backup and restore approach.
- Define data retention and deletion process.
- Configure monitoring and alerting.
- Test access controls.
- Test recovery from failed ingestion/scoring.
- Document model rollback.
- Agree client support and incident responsibilities.

## 8. Cost management

Track cloud costs by environment and client. Shut down idle development resources. Set budgets and alerts. Review whether managed services provide sufficient operational value for the expected workload.
