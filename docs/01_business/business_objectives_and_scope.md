# Business Objectives and Product Scope

**Document ID:** NCI-BOS-001  
**Version:** 0.2  
**Status:** Draft for review

## 1. Product vision

Enable subscription businesses to make better-informed customer retention decisions by combining churn risk, customer value, segmentation, and explainability.

## 2. Business objectives

| ID | Objective | Intended outcome |
|---|---|---|
| BO-01 | Predict churn risk | Identify customers with elevated probability of churn within a defined horizon |
| BO-02 | Estimate customer value | Estimate future customer revenue or contribution margin over a defined horizon |
| BO-03 | Segment customers | Group customers into interpretable behavioural/value segments |
| BO-04 | Quantify revenue exposure | Estimate expected revenue associated with customers at risk |
| BO-05 | Explain predictions | Provide understandable drivers associated with model outputs |
| BO-06 | Support retention prioritisation | Help users prioritise review and intervention |
| BO-07 | Enable repeatable delivery | Reuse the product workflow across client engagements while isolating client data |

## 3. Primary users

| User | Main needs |
|---|---|
| Business Owner / Managing Director | Understand overall churn exposure and business value |
| Head of Customer Success | Identify customers requiring review |
| Revenue Operations Analyst | Explore risk, value, and segment patterns |
| Data Analyst / Data Scientist | Validate inputs, models, and performance |
| System Administrator | Manage access, configuration, and operational health |

## 4. Product boundaries

The product provides analytical outputs and decision support. It does not decide whether a customer should be denied a service, charged differently, or treated adversely.

Retention actions remain the responsibility of the client. Recommendations, if introduced later, must be reviewed for fairness, appropriateness, and effectiveness.

## 5. Churn problem definitions

The product must distinguish two problem classes:

### Contractual churn

A customer has an explicit cancellation, termination, or non-renewal event. The label and prediction horizon must be defined from the client’s contract and event data.

### Non-contractual inactivity

A customer has no observed purchase or activity for a defined period. This is not automatically equivalent to a confirmed cancellation. The inactivity threshold must be selected using business context and historical behaviour.

The initial MVP focuses on contractual churn for the SaaS/subscription use case. Non-contractual churn will be treated as a separate extension.

## 6. Initial prediction design

Proposed initial design for validation:

- Observation window: configurable; initial experiment may use the preceding 90 days where the data supports it.
- Prediction horizon: configurable; initial experiment may predict churn within the following 30 days.
- Scoring frequency: batch, initially weekly or monthly depending on client data cadence.
- Unit of prediction: customer or active subscription, to be confirmed for each client.
- Label: a defined churn event occurring within the prediction horizon.

These are starting hypotheses. They must be reviewed against event timing, data availability, and the client’s business process before modelling.

## 7. MVP release goals

The MVP is complete when a user can load a documented dataset, validate it, generate customer-level predictions and value estimates, inspect segments and explanations, and export results from a dashboard with traceable model versions.
