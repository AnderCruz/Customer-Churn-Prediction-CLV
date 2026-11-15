# Nowa Customer Intelligence

**Nowa Analytics | UK SaaS & Subscription Market**

Predictive customer intelligence for churn risk, customer lifetime value (CLV), segmentation, and revenue exposure.

## Project status

- Documentation baseline: approved (14 November 2026).
- Current phase: Phase 1 — GitHub Repository & Development Environment Setup.
- Initial use case: contractual churn for SaaS/subscription businesses.
- Initial data interface: documented CSV templates.
- Development approach: local-first, modular monolith.
- Cloud deployment: deferred until local MVP validation.

## Product scope

The planned MVP includes:
- CSV ingestion and data validation.
- Point-in-time feature engineering.
- Contractual churn prediction.
- Customer value estimation with a documented basis and forecast horizon.
- Customer segmentation.
- Revenue-at-risk estimates.
- Model explainability.
- Streamlit dashboard and batch scoring.
- Experiment tracking and reproducible model artefacts.

Synthetic data is for engineering and workflow testing only. It is not evidence of real-world model performance.

## Repository structure

```text
configs/                  # Environment and model configuration
data/                     # Local data; contents are git-ignored
docs/                     # Product, requirements, architecture and delivery docs
notebooks/                # Exploratory and experimental notebooks
src/nowa_customer_intelligence/
  data/                   # Ingestion and validation
  features/               # Feature engineering
  models/                 # Churn, CLV and segmentation
  evaluation/             # Model evaluation
  explainability/         # SHAP and explanation utilities
  monitoring/             # Data/model monitoring
tests/                    # Unit and integration tests
api/                      # Optional FastAPI application
dashboard/                # Streamlit application
deployment/               # Docker and AWS deployment assets
```

## Development setup

See `docs/06_deployment/deployment_and_mlops_strategy.md` and the Phase 1 setup instructions supplied with this repository scaffold.

## Data policy

Do not commit client data, credentials, model artefacts containing client information, or raw datasets unless the licence and project policy explicitly permit it. The `data/` directory is ignored by Git by default.

## Project documentation

Start with:
1. `docs/01_business/business_case.md`
2. `docs/02_requirements/functional_requirements.md`
3. `docs/02_requirements/non_functional_requirements.md`
4. `docs/03_architecture/system_architecture.md`
5. `docs/07_project_management/implementation_plan_and_roadmap.md`

## License

License selection is pending. Do not add an open-source licence until the intended distribution and commercial strategy have been confirmed.
