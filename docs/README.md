# Nowa Customer Intelligence
## Project Documentation Pack

**Organisation:** Nowa Analytics  
**Product:** Nowa Customer Intelligence  
**Target market:** United Kingdom  
**Initial target segment:** SaaS and subscription businesses  
**Documentation status:** Draft 0.3 — conditionally approved baseline pending product-owner sign-off  
**Date:** 14 November 2026

## Purpose

This documentation pack establishes the business case, product scope, requirements, architecture, data approach, technical implementation plan, risks, and acceptance criteria for Nowa Customer Intelligence.

The product is intended to help subscription businesses identify customers at risk of churn, estimate future customer value, understand customer segments, and prioritise retention decisions.

## Document index

1. `01_business/business_case.md`
2. `01_business/business_objectives_and_scope.md`
3. `02_requirements/functional_requirements.md`
4. `02_requirements/non_functional_requirements.md`
5. `02_requirements/acceptance_criteria.md`
6. `03_architecture/system_architecture.md`
7. `03_architecture/data_architecture.md`
8. `03_architecture/architecture_decisions.md`
9. `04_data/data_sources_and_governance.md`
10. `05_ml/modelling_and_evaluation_strategy.md`
11. `06_deployment/deployment_and_mlops_strategy.md`
12. `07_project_management/implementation_plan_and_roadmap.md`
13. `07_project_management/project_risks.md`
14. `07_project_management/documentation_review_and_approval.md`

## Status and change control

All documents are drafts until reviewed and approved. Changes to scope, architecture, data assumptions, or acceptance criteria should be recorded in the relevant document and, where appropriate, in the Architecture Decision Records.

## Important product principles

- Start with a focused SaaS/subscription use case.
- Build locally first; introduce cloud infrastructure only when justified.
- Treat synthetic data as engineering/test data, not evidence of real-world model performance.
- Keep contractual churn and non-contractual inactivity as distinct problem types.
- Use temporal validation and prevent target leakage.
- Treat model outputs as decision support, not autonomous decisions with significant effects on individuals.
- Design for client data isolation from the beginning, without building a full multi-tenant SaaS platform in the MVP.
