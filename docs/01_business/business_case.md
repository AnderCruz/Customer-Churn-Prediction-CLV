# Business Case

**Document ID:** NCI-BC-001  
**Version:** 0.2  
**Status:** Draft for review

## 1. Executive summary

Nowa Customer Intelligence is a predictive analytics product by Nowa Analytics for UK-based SaaS and subscription businesses. It combines customer churn prediction, customer lifetime value (CLV) estimation, customer segmentation, revenue-at-risk analysis, and model explainability.

The initial product will be delivered as a client-specific analytics solution. The architecture and codebase will be reusable across clients, while each client’s data, model artefacts, and predictions will remain isolated.

## 2. Business problem

Subscription businesses need to retain customers and recurring revenue, but often rely on retrospective reports and broad retention campaigns. These approaches can make it difficult to identify customers who may churn early, distinguish high-value customers from low-value customers, and prioritise limited retention resources.

The product will support earlier, more targeted decisions by combining churn risk with customer economic value.

## 3. Proposed solution

The MVP will provide:

1. Customer-level churn probability for a defined prediction horizon.
2. Configurable risk bands.
3. Customer-level and aggregate CLV estimates.
4. Customer segmentation based on available behavioural and commercial features.
5. Revenue-at-risk estimates with clearly documented assumptions.
6. Global and individual model explanations.
7. A dashboard and batch scoring workflow.
8. Reproducible model experiments and versioned artefacts.

The MVP is an analytical decision-support product. It will not automatically cancel, restrict, price, or otherwise make significant decisions about individuals.

## 4. Target market and initial customer profile

**Geography:** United Kingdom.  
**Initial segment:** SaaS and subscription businesses.

Initial ideal-customer-profile hypotheses:

- Recurring-revenue business model.
- Sufficient historical customer and subscription data.
- A meaningful customer base and observable churn events.
- Ability to provide customer, subscription, billing, and product-usage data.
- A business owner for retention, customer success, or revenue operations.

The initial customer-volume range of 1,000–50,000 customers is a commercial targeting hypothesis, not a technical limit or mandatory product requirement.

## 5. Value proposition

“Turn customer data into predictive intelligence to anticipate churn, understand customer value, and prioritise retention decisions.”

Expected value areas:

- Earlier identification of customers with elevated churn risk.
- Better prioritisation of customer-success activity.
- Improved visibility of customer value and revenue exposure.
- More focused retention campaigns.
- Transparent explanations of model outputs.

No financial uplift is guaranteed. Commercial impact must be evaluated with client data and, where feasible, controlled experiments.

## 6. Product scope

### In scope for the MVP

- File-based data ingestion using documented CSV templates.
- Data schema and quality validation.
- Customer-level churn scoring.
- Initial CLV estimation.
- Customer segmentation.
- Revenue-at-risk calculations.
- Explainability outputs.
- Streamlit dashboard.
- Batch prediction export.
- MLflow experiment tracking and model version metadata.
- Automated tests and Docker-based local deployment.

### Out of scope for the MVP

- Fully self-service SaaS onboarding.
- Full multi-tenant application with shared runtime.
- Real-time streaming ingestion.
- Pre-built integrations with every CRM, billing, or product analytics provider.
- Automated retention campaign execution.
- Autonomous decisions affecting customer access or contractual rights.
- Guaranteed churn reduction or revenue uplift.
- A universal model trained across unrelated client datasets.

## 7. Business model hypothesis

Potential commercial offers:

| Offer | Scope | Commercial model |
|---|---|---|
| Churn Analytics Assessment | Data assessment, churn baseline, initial findings | Fixed-fee project |
| Customer Intelligence Implementation | Churn, CLV, segmentation, dashboard | Implementation fee |
| Predictive Analytics Service | Monitoring, periodic scoring, model review and support | Recurring monthly fee |

Indicative prices previously discussed are hypotheses for market testing only. They should not be treated as validated market rates until tested through customer discovery and competitor research.

## 8. Success measures

### Product and technical measures

- Data ingestion and validation complete without critical errors.
- Churn model evaluated on a temporally separated holdout set.
- PR-AUC, ROC-AUC, precision, recall, calibration, and confusion matrix reported.
- CLV methodology and forecast horizon documented.
- Reproducible model training and version tracking.
- Dashboard displays model outputs with timestamps and model version.
- Critical application paths covered by automated tests.

### Business measures

- Number of qualified discovery conversations.
- Number of pilot customers secured.
- Time required to onboard a client dataset.
- Customer adoption of risk and value insights.
- Retention campaign outcomes measured by the client.
- Incremental retention impact measured using an appropriate experimental design where possible.

## 9. Key assumptions

- Initial buyers have access to usable historical customer data.
- Customer identifiers can be consistently joined across source files.
- Churn can be defined operationally for each client.
- The client can provide sufficient observation history and churn events.
- The client has a lawful basis and appropriate notices/permissions for the proposed processing.
- The product can initially be delivered as a client-specific deployment or controlled analytics engagement.

## 10. Recommendation

Proceed with a focused MVP for SaaS/subscription use cases. Validate the problem and data availability through customer discovery before investing in extensive integrations or a full SaaS platform.
