# Architecture Decision Records

**Document ID:** NCI-ADR-001  
**Version:** 0.2  
**Status:** Proposed decisions

## ADR-001: Modular monolith for the MVP

**Status:** Accepted for MVP, subject to review.

**Context:** The product is being developed by a small team and needs a manageable deployment model.

**Decision:** Use a modular monolith with clear package boundaries for ingestion, features, modelling, API, and dashboard.

**Consequences:** Lower operational complexity. Components can be separated later if scale or deployment boundaries justify it.

## ADR-002: Local-first development

**Status:** Accepted.

**Context:** Cloud costs and operational complexity should be controlled during experimentation.

**Decision:** Develop and test locally, using Docker for reproducibility. Introduce AWS after the core workflows are validated.

**Consequences:** Lower early costs; production-specific controls must be added before handling live client data.

## ADR-003: Client-specific data and model isolation

**Status:** Accepted as a design principle.

**Context:** Client datasets may contain confidential and personal data and should not be mixed.

**Decision:** Keep data, artefacts, configuration, and predictions scoped to a client. The initial deployment can be single-client.

**Consequences:** Reusable code without requiring shared multi-tenant infrastructure in the MVP.

## ADR-004: CSV templates before native integrations

**Status:** Accepted for MVP.

**Context:** Native integrations increase scope and depend on client systems and credentials.

**Decision:** Start with documented CSV templates and secure transfer procedures. Add APIs/connectors after pilot requirements are known.

**Consequences:** Faster onboarding prototype; manual mapping remains necessary initially.

## ADR-005: Tabular ML before deep learning

**Status:** Accepted for initial modelling.

**Context:** Initial datasets are expected to be structured and relatively modest in size.

**Decision:** Establish baselines with Logistic Regression and tree-based models such as Random Forest, LightGBM, XGBoost, or CatBoost. Evaluate deep learning only when justified by data scale or sequential structure.

**Consequences:** Faster experimentation and more interpretable baselines.

## ADR-006: Separate churn problem types

**Status:** Accepted.

**Context:** Contractual cancellation and non-contractual inactivity have different labels and event processes.

**Decision:** Model them as separate use cases, with contractual churn as the initial SaaS/subscription focus.

**Consequences:** Avoids misleading label definitions and inappropriate transfer of models between sectors.

## ADR-007: Streamlit for MVP dashboard

**Status:** Proposed.

**Context:** The first objective is a functional demonstration and analyst/business-user workflow.

**Decision:** Use Streamlit for the MVP. Reassess frontend technology if external customer-facing product requirements become more demanding.

**Consequences:** Fast delivery; UI customisation and complex user management may be limited.

## ADR-008: MLflow for experiment tracking

**Status:** Proposed.

**Context:** Experiments, parameters, metrics, and artefacts need reproducibility.

**Decision:** Use MLflow for local experiment tracking and model metadata, with an appropriate managed or secured backend for production.

**Consequences:** Consistent experiment history; production access and storage security must be configured.
