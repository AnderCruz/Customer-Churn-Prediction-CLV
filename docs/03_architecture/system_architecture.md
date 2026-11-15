# System Architecture

**Document ID:** NCI-ARCH-001  
**Version:** 0.2  
**Status:** Draft for review

## 1. Architectural approach

The MVP will use a modular monolith rather than microservices. This keeps deployment and operations manageable for a small development team while preserving clear boundaries between data, modelling, API, and presentation components.

The design will be client-configurable and client-isolated. The first deployment may serve one client at a time; shared multi-tenant SaaS infrastructure is not an MVP requirement.

## 2. Logical architecture

```text
Client data files / later integrations
                |
          Ingestion layer
                |
       Schema and quality checks
                |
       Processing and feature layer
                |
       Versioned feature datasets
                |
      Model training and evaluation
                |
      Model registry / artefact store
                |
           Batch scoring
                |
       Prediction and explanation data
                |
        FastAPI service (optional MVP)
                |
       PostgreSQL / structured storage
                |
        Streamlit business dashboard
```

## 3. Component responsibilities

| Component | Proposed technology | Responsibility |
|---|---|---|
| Ingestion | Python | Load client-approved source files |
| Validation | Pandera | Validate schemas and data constraints |
| Transformation | Pandas / NumPy | Clean and transform data |
| Feature engineering | Python package | Build point-in-time customer features |
| Modelling | Scikit-learn, LightGBM, XGBoost | Train and score tabular models |
| Probabilistic CLV | Lifetimes or validated alternative | Estimate repeat-purchase behaviour where suitable |
| Explainability | SHAP | Explain supported model outputs |
| Experiment tracking | MLflow | Track runs, metrics, parameters, and artefacts |
| API | FastAPI | Expose scoring and metadata endpoints if required |
| Database | PostgreSQL | Store application metadata and prediction outputs |
| Dashboard | Streamlit | Present business insights |
| Packaging | Docker Compose | Reproducible local execution |
| CI | GitHub Actions | Automated tests and checks |

## 4. Main workflows

### 4.1 Data onboarding

1. Client provides files through an agreed secure channel.
2. Ingestion checks file format and schema.
3. Data quality checks generate a report.
4. Invalid records are rejected or quarantined according to documented rules.
5. Approved data is transformed into analysis-ready tables.

### 4.2 Model development

1. Create a point-in-time training dataset.
2. Define target and prediction horizon.
3. Split data using a temporal strategy where feasible.
4. Train baseline and candidate models.
5. Evaluate discrimination, calibration, and operational trade-offs.
6. Register selected model and artefacts in MLflow.

### 4.3 Scoring and reporting

1. Load the approved model version.
2. Validate scoring data.
3. Generate churn and CLV outputs.
4. Calculate segment and revenue-at-risk summaries.
5. Generate explanations.
6. Persist outputs with timestamps and model versions.
7. Display results in the dashboard and allow controlled export.

## 5. Deployment stages

- Stage A: local development.
- Stage B: Docker-based reproducible environment.
- Stage C: controlled pilot deployment.
- Stage D: AWS production deployment, selected according to client security, scale, and operating requirements.

## 6. Architecture quality attributes

The architecture prioritises:
- Reproducibility.
- Data isolation.
- Traceability.
- Maintainability.
- Low initial operating cost.
- Clear separation of model training and inference.
- Incremental cloud adoption.

## 7. Constraints and limitations

- Streamlit is suitable for an MVP and internal/business-facing demonstration; a more customised frontend may be justified later.
- FastAPI is optional until an external system needs programmatic scoring.
- SageMaker is not mandatory for the first production pilot; deployment choice should follow operational requirements and cost analysis.
- A single generic model is not assumed to work across unrelated clients or industries.
