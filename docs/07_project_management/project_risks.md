# Project Risks and Mitigations

**Document ID:** NCI-RISK-001  
**Version:** 0.2  
**Status:** Draft for review

| ID | Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|---|
| R-01 | Insufficient real SaaS churn data | High | High | Validate data readiness early; use synthetic data only for engineering tests; secure a pilot dataset |
| R-02 | Unclear churn definition | Medium | High | Agree event definition and prediction horizon before modelling |
| R-03 | Target leakage | Medium | High | Point-in-time features, temporal splits, leakage review |
| R-04 | Low number of churn events | Medium | High | Assess event counts early; simplify model or extend observation period |
| R-05 | CLV assumptions unsuitable for business model | Medium | High | Select method by contractual/non-contractual model; document horizon and assumptions |
| R-06 | Synthetic results mistaken for real-world validation | Medium | High | Label synthetic outputs and reports clearly; prohibit performance claims based on synthetic data |
| R-07 | Data quality and identity joins are poor | High | High | Data-readiness assessment and canonical mapping |
| R-08 | Model drift | Medium | Medium | Monitor inputs and outcomes; review before retraining |
| R-09 | Privacy or security incident | Low/Medium | High | Minimise data, isolate clients, restrict access, encrypt, review deployment |
| R-10 | Cloud costs exceed expectations | Medium | Medium | Local-first build, budgets, alerts, cost reviews |
| R-11 | Product lacks differentiation | Medium | High | Focus on customer value, financial prioritisation, explainability, and implementation simplicity |
| R-12 | Dashboard/API scope expands too early | Medium | Medium | Keep MVP focused; add integrations only after pilot evidence |
| R-13 | Predictions do not improve retention outcomes | Medium | High | Treat as decision support; evaluate campaigns with control groups where feasible |
| R-14 | Model explanations are interpreted causally | Medium | Medium | Explain limitations in UI and documentation; use causal methods only in a separate validated workstream |

## Risk review cadence

Review risks at the end of each major phase and whenever scope, data source, deployment model, or client use case changes.

## Escalation

Any suspected privacy/security incident, exposure of client data, or use of predictions for an unapproved consequential decision must be escalated immediately and handled under the applicable incident and client procedures.
