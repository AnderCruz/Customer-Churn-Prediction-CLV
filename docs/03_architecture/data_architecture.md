# Data Architecture

**Document ID:** NCI-DATA-ARCH-001  
**Version:** 0.2  
**Status:** Draft for review

## 1. Design principles

- Use stable, pseudonymous customer identifiers in analytical datasets wherever possible.
- Keep source data separate from processed and feature datasets.
- Record ingestion time and source provenance.
- Build features using only information available at the scoring cutoff.
- Preserve client-level data isolation.
- Document definitions, units, time zones, and null handling.
- Do not assume fields exist in every client system.

## 2. Core logical entities

### Customers

| Field | Type | Description |
|---|---|---|
| customer_id | string | Client-scoped customer identifier |
| signup_date | date/datetime | Registration date |
| customer_status | string | Current status, if supplied |
| acquisition_channel | string | Acquisition source, if supplied |
| country_code | string | Country code, if required |

### Subscriptions

| Field | Type | Description |
|---|---|---|
| subscription_id | string | Subscription identifier |
| customer_id | string | Customer relationship key |
| start_date | datetime | Subscription start |
| end_date | datetime/null | End date, if applicable |
| subscription_status | string | Status at the relevant timestamp |
| recurring_amount | decimal | Recurring charge |
| billing_frequency | string | Monthly, annual, etc. |
| currency | string | ISO currency code |

### Billing / Transactions

| Field | Type | Description |
|---|---|---|
| transaction_id | string | Transaction identifier |
| customer_id | string | Customer relationship key |
| transaction_date | datetime | Transaction timestamp |
| amount | decimal | Transaction amount |
| currency | string | ISO currency code |
| transaction_status | string | Paid, failed, refunded, etc. |

### Product activity

| Field | Type | Description |
|---|---|---|
| customer_id | string | Customer relationship key |
| activity_timestamp | datetime | Activity timestamp |
| event_type | string | Activity/event name |
| event_count | integer | Event count, where aggregated |
| feature_name | string/null | Product feature used, if available |

### Prediction output

| Field | Type | Description |
|---|---|---|
| prediction_id | string | Unique prediction record |
| client_id | string | Client/deployment scope identifier |
| customer_id | string | Pseudonymous customer key |
| prediction_timestamp | datetime | Scoring time |
| churn_probability | float | Estimated probability |
| risk_band | string | Configured risk category |
| predicted_clv | decimal/null | Estimated value |
| clv_basis | string/null | Revenue or contribution margin |
| forecast_horizon | string | CLV horizon |
| model_version | string | Model identifier/version |

## 3. Data zones

| Zone | Purpose | Example |
|---|---|---|
| Raw | Immutable or controlled source copy | Original CSV files |
| Validated | Schema-checked records | Validated tables |
| Processed | Cleaned and standardised records | Normalised customer/subscription data |
| Features | Point-in-time model features | Customer feature snapshots |
| Predictions | Model outputs | Churn and CLV scores |
| Reporting | Aggregated business metrics | Segment and risk summaries |

For the local MVP, these zones may be represented by clearly separated folders and/or database schemas. A cloud data lake is not required at the outset.

## 4. Temporal modelling and leakage prevention

Each training example must have:
- An observation cutoff timestamp.
- A feature observation window.
- A target definition.
- A target outcome window.
- A customer/entity identifier.

Features must not include events occurring after the observation cutoff. Labels must be derived from the subsequent target window. Training and test periods must respect time ordering where possible.

## 5. Churn label design

For contractual churn, define churn using a confirmed cancellation, termination, or non-renewal event and document treatment of pauses, failed payments, reactivations, and administrative closures.

For non-contractual inactivity, define an inactivity threshold using business context and historical purchasing cadence. This must remain a separate modelling problem from contractual churn.

## 6. Revenue-at-risk definition

A simple expected exposure measure may be calculated as:

`Expected Revenue Exposure = Churn Probability × Future Revenue at Risk`

The revenue horizon and revenue basis must be explicit. If CLV is used, avoid mixing revenue and contribution margin. This measure is not the same as recoverable revenue or expected campaign uplift.

## 7. Data dictionary and client mapping

Each client onboarding must include a mapping document from source fields to canonical fields, including:
- Source system and field.
- Canonical field.
- Data type and unit.
- Time zone.
- Null and default handling.
- Transformation rule.
- Data owner.
- Personal-data classification, where applicable.

## 8. Retention and deletion

Retention periods must be agreed per client and implemented in the deployment and operating procedures. The product should support deletion or removal workflows for client data and derived artefacts when contractually and legally required.
