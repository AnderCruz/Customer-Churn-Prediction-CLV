# Customer Data Contract

**Product:** Nowa Customer Intelligence
**Document Version:** 1.1
**Status:** Approved for Implementation
**Last Updated:** November 2026

---

## 1. Purpose

This document defines the data contract for the initial version of Nowa Customer Intelligence.

It establishes the structure, format, granularity, validation requirements and relationships of the datasets required to support subscription-level contractual churn prediction.

The contract is designed to:

- Standardise client data ingestion through CSV files.
- Establish consistent data structures across client implementations.
- Validate data quality before processing and modelling.
- Support historical, time-aware churn prediction.
- Prevent data leakage during feature engineering and model training.
- Support subscription-level predictions and customer-level reporting.
- Provide a foundation for future Customer Lifetime Value (CLV) and revenue analytics capabilities.

This contract defines the expected data interface. It does not imply that every client will have all datasets or attributes available.

---

## 2. Scope

### 2.1 Initial Use Case

The initial analytical use case is contractual subscription churn prediction.

The model will estimate the probability that an individual subscription will experience contractual churn within a defined prediction horizon.

The initial observation window and prediction horizon are provisional and will be confirmed during data discovery.

Current working assumptions:

| Parameter | Initial assumption |
|---|---|
| Prediction entity | Individual subscription |
| Prediction target | Contractual subscription churn |
| Observation unit | Subscription |
| Historical data | Monthly subscription snapshots |
| Observation window | 90 days (provisional) |
| Prediction horizon | 30 days (provisional) |
| Initial data interface | CSV files |

### 2.2 Prediction and Reporting Granularity

The prediction entity is the individual subscription.

- `subscription_id` identifies the entity being evaluated.
- `customer_id` identifies the customer associated with the subscription.
- Churn labels are constructed at subscription level.
- Model predictions and initial model evaluation are performed at subscription level.
- Customer-level risk and revenue exposure are derived by aggregating subscription-level results.

The `customer_id` field must not be used as a predictive model feature.

### 2.3 Dataset Classification

| Dataset | File | Requirement | Primary purpose |
|---|---|---|---|
| Customers | `customers.csv` | Required | Customer account information |
| Subscriptions | `subscriptions.csv` | Required | Subscription master information |
| Subscription Snapshots | `subscription_snapshots.csv` | Required for temporal modelling | Historical subscription state |
| Monthly Usage | `usage_monthly.csv` | Optional | Subscription usage behaviour |
| Invoices | `invoices.csv` | Optional | Billing and payment behaviour |

The initial ingestion workflow must distinguish between datasets required for basic data validation and those required for historical predictive modelling.

---

## 3. General File Specifications

All CSV files must follow these conventions.

| Attribute | Requirement |
|---|---|
| File format | CSV |
| Encoding | UTF-8 |
| Delimiter | Comma (`,`) |
| Header | Required |
| Decimal separator | Period (`.`) |
| Date format | ISO 8601 (`YYYY-MM-DD`) |
| Datetime format | ISO 8601 |
| Boolean values | `true` or `false` |
| Missing values | Empty fields |
| Identifiers | String |
| Currency | ISO 4217 currency code |
| Timezone | UTC for timestamps containing time information |

Additional conventions:

1. Column names must use lowercase `snake_case`.
2. Identifiers must be treated as strings, even when they contain only numeric characters.
3. Identifiers must not contain leading or trailing whitespace.
4. Duplicate column names are not permitted.
5. CSV files must contain the expected header, including when the dataset has no records.
6. Monetary values must be numeric and must not contain currency symbols or thousands separators.
7. Dates and timestamps must use consistent formats within each file.
8. Missing values must not be represented using arbitrary strings such as `N/A`, `NULL`, `None` or `Unknown`, unless explicitly defined for a controlled categorical field.

---

## 4. Dataset Specifications

### 4.1 Customers

**File:** `customers.csv`
**Requirement:** Required
**Granularity:** One record per customer
**Primary Key:** `customer_id`

This dataset contains customer account information.

#### Fields

| Field | Data Type | Required | Description |
|---|---|---|---|
| `customer_id` | string | Yes | Unique customer identifier |
| `created_at` | date/datetime | Yes | Date the customer account was created |
| `country` | string | No | Customer country |
| `industry` | string | No | Customer industry |
| `company_size` | string | No | Customer company size category |
| `account_status` | string | No | Current customer account status |

#### Validation Rules

- `customer_id` must be unique and non-null.
- `created_at` must be a valid date or datetime.
- `created_at` must not be in the future relative to the agreed data extraction date.
- Categorical fields must use consistent values.
- Customer records must be referenced by at least one subscription in the initial dataset.

#### Important Considerations

Customer attributes may be used for segmentation and reporting.

Their suitability as predictive features must be assessed separately, considering availability at the prediction timestamp and potential data leakage.

Direct personal identifiers should not be included unless strictly necessary and explicitly approved.

---

### 4.2 Subscriptions

**File:** `subscriptions.csv`
**Requirement:** Required
**Granularity:** One record per subscription
**Primary Key:** `subscription_id`
**Foreign Key:** `customer_id`

This dataset contains the subscription master record and its contractual characteristics.

#### Fields

| Field | Data Type | Required | Description |
|---|---|---|---|
| `subscription_id` | string | Yes | Unique subscription identifier |
| `customer_id` | string | Yes | Associated customer identifier |
| `plan_id` | string | No | Subscription plan identifier |
| `start_date` | date | Yes | Subscription start date |
| `end_date` | date | No | Subscription end date, if applicable |
| `subscription_status` | string | Yes | Current subscription status |
| `billing_frequency` | string | No | Billing frequency |
| `recurring_revenue` | decimal | No | Current recurring revenue amount |
| `currency` | string | No | ISO 4217 currency code |
| `auto_renew` | boolean | No | Whether the subscription is configured for automatic renewal |
| `cancellation_date` | date | No | Date cancellation became effective, if applicable |
| `cancellation_reason` | string | No | Recorded cancellation reason |

#### Validation Rules

- `subscription_id` must be unique and non-null.
- `customer_id` must be non-null.
- Every `customer_id` must exist in `customers.csv`.
- `start_date` must be valid.
- `end_date` must not precede `start_date`.
- `cancellation_date` must not precede `start_date`.
- `recurring_revenue`, when provided, must be numeric and non-negative.
- `currency`, when provided, must use a valid ISO 4217 code.
- `auto_renew`, when provided, must contain a valid boolean value.

#### Controlled Values

The following are proposed status categories:

- `active`
- `trial`
- `cancelled`
- `expired`
- `suspended`
- `paused`

These categories are provisional. Client-specific statuses must be mapped to the standard taxonomy during data discovery.

#### Important Considerations

This dataset represents the subscription master record.

It must not be treated as a complete historical record of subscription behaviour.

Historical states must be reconstructed using `subscription_snapshots.csv`.

The current values in this file must not be used retrospectively as predictive features for historical prediction dates.

---

### 4.3 Subscription Snapshots

**File:** `subscription_snapshots.csv`
**Requirement:** Required for temporal modelling
**Granularity:** One record per subscription per monthly snapshot date
**Composite Primary Key:** `subscription_id` + `snapshot_date`
**Foreign Key:** `subscription_id`

This dataset contains historical observations of subscription states.

It is the primary dataset for constructing time-aware training examples.

Each record represents the state of a subscription at a specific observation date.

#### Fields

| Field | Data Type | Required | Description |
|---|---|---|---|
| `subscription_id` | string | Yes | Subscription identifier |
| `snapshot_date` | date | Yes | Date on which the subscription state was observed |
| `subscription_status` | string | Yes | Subscription status at the snapshot date |
| `recurring_revenue` | decimal | No | Recurring revenue at the snapshot date |
| `currency` | string | No | ISO 4217 currency code |
| `plan_id` | string | No | Plan associated with the subscription |
| `billing_frequency` | string | No | Billing frequency at the snapshot date |
| `auto_renew` | boolean | No | Automatic renewal configuration at the snapshot date |

#### Snapshot Requirements

1. Each subscription must have no more than one record per snapshot date.
2. Snapshot dates must follow a consistent monthly convention.
3. Snapshot dates must represent the state of the subscription at that date.
4. Historical records must not be overwritten with current subscription values.
5. A snapshot must not contain information that became available only after its observation date.
6. Changes in subscription status, plan, recurring revenue and billing configuration should be reflected in subsequent snapshots.

#### Validation Rules

- `subscription_id` must not be null.
- `snapshot_date` must not be null.
- The combination of `subscription_id` and `snapshot_date` must be unique.
- Every `subscription_id` must exist in `subscriptions.csv`.
- `subscription_status` must use an accepted or mapped status category.
- `recurring_revenue`, when provided, must be non-negative.
- `currency`, when provided, must use a valid ISO 4217 code.
- Snapshot dates must follow the agreed monthly convention.
- A snapshot date must not be later than the agreed data extraction cutoff.

#### Temporal Considerations

Snapshots are essential to prevent historical information from being replaced by present-day information.

For each prediction observation date:

- Features must be constructed using information available on or before that date.
- The prediction target must refer to a subsequent period.
- Information recorded after the observation date must not be used as a predictive feature.

The exact definition of the snapshot date, including whether it represents the beginning or end of a month, must be agreed during data discovery.

#### Historical Coverage

The minimum historical coverage required for model development will depend on:

- The observation window.
- The prediction horizon.
- Subscription lifecycle duration.
- Churn event frequency.
- Available historical records.
- The required temporal validation strategy.

A dataset containing only current subscription states is insufficient for reliable historical model training.

---

### 4.4 Monthly Usage

**File:** `usage_monthly.csv`
**Requirement:** Optional
**Granularity:** One record per subscription per month
**Composite Primary Key:** `subscription_id` + `usage_month`
**Foreign Key:** `subscription_id`

This dataset contains monthly subscription usage information.

It may provide behavioural indicators that improve churn prediction.

#### Fields

| Field | Data Type | Required | Description |
|---|---|---|---|
| `subscription_id` | string | Yes | Subscription identifier |
| `usage_month` | date | Yes | Month represented by the usage record |
| `active_users` | integer | No | Number of active users |
| `total_users` | integer | No | Total number of users |
| `sessions_count` | integer | No | Number of sessions |
| `events_count` | integer | No | Number of recorded events |
| `usage_volume` | decimal | No | Total usage volume |
| `usage_metric` | string | No | Description or unit of usage volume |

#### Validation Rules

- `subscription_id` must not be null.
- `usage_month` must not be null.
- The combination of `subscription_id` and `usage_month` must be unique.
- Every `subscription_id` must exist in `subscriptions.csv`.
- Count fields must be non-negative integers.
- `active_users` must not exceed `total_users`, when both are available.
- `usage_volume`, when provided, must be non-negative.
- Usage records must correspond to valid subscription periods.

#### Temporal Considerations

Usage data must be available before the prediction timestamp to be considered as a predictive feature.

For example, a prediction made on 1 June must not use usage information from June if that information was only fully observed at the end of the month.

Usage aggregation and availability timestamps must be considered during feature engineering.

---

### 4.5 Invoices

**File:** `invoices.csv`
**Requirement:** Optional
**Granularity:** One record per invoice
**Primary Key:** `invoice_id`
**Foreign Key:** `subscription_id`

This dataset contains billing and payment information.

It may support churn prediction through payment behaviour, billing failures and revenue analysis.

#### Fields

| Field | Data Type | Required | Description |
|---|---|---|---|
| `invoice_id` | string | Yes | Unique invoice identifier |
| `subscription_id` | string | Yes | Associated subscription identifier |
| `invoice_date` | date | Yes | Invoice issue date |
| `due_date` | date | No | Invoice due date |
| `paid_date` | date | No | Date the invoice was paid |
| `amount` | decimal | Yes | Invoice amount |
| `currency` | string | Yes | ISO 4217 currency code |
| `invoice_status` | string | Yes | Invoice payment status |

#### Validation Rules

- `invoice_id` must be unique and non-null.
- `subscription_id` must be non-null.
- Every `subscription_id` must exist in `subscriptions.csv`.
- `invoice_date` must be valid.
- `due_date` must not precede `invoice_date`.
- `paid_date`, when provided, must not precede `invoice_date`.
- `amount` must be numeric and non-negative.
- `currency` must use a valid ISO 4217 code.
- `invoice_status` must use an accepted or mapped status category.

#### Controlled Values

Proposed invoice status categories:

- `paid`
- `pending`
- `overdue`
- `failed`
- `void`
- `refunded`

Client-specific billing statuses must be mapped during data discovery.

#### Temporal Considerations

Payment behaviour must be calculated using only information available at the prediction timestamp.

For example, an invoice that became overdue after the prediction date cannot be used as evidence of payment delinquency at that earlier date.

---

## 5. Referential Integrity

The datasets must maintain the following relationships:

```text
customers.csv
      |
      | customer_id
      |
subscriptions.csv
      |
      | subscription_id
      |
      +-------------------------+
      |            |            |
      v            v            v
subscription_   usage_       invoices.csv
snapshots.csv   monthly.csv
```

### Referential Integrity Rules

1. Every subscription must reference an existing customer.
2. Every subscription snapshot must reference an existing subscription.
3. Every usage record must reference an existing subscription.
4. Every invoice must reference an existing subscription.
5. Foreign keys must not contain null values where they are mandatory.
6. Duplicate primary keys are not permitted.
7. Duplicate composite keys are not permitted.

The ingestion pipeline must report referential integrity violations before data proceeds to feature engineering.

---

## 6. Data Quality Requirements

Data quality validation will be performed before model preparation.

The initial validation framework will cover the following dimensions:

| Dimension | Description | Examples |
|---|---|---|
| Completeness | Required fields are populated | Missing subscription identifiers |
| Uniqueness | Primary and composite keys are unique | Duplicate subscriptions |
| Validity | Values follow expected formats and types | Invalid dates or negative revenue |
| Consistency | Related fields do not contradict each other | End date before start date |
| Referential Integrity | Relationships between datasets are valid | Unknown customer identifiers |
| Temporal Integrity | Dates follow logical chronological rules | Snapshot after extraction cutoff |
| Accuracy | Values reasonably represent the underlying business reality | Incorrect revenue or subscription status |

### Validation Severity

Data quality issues will be classified into three levels:

**Critical**

Issues that prevent safe ingestion or invalidate the dataset.

Examples:
- Missing mandatory columns.
- Duplicate primary keys.
- Invalid file format.
- Broken mandatory foreign-key relationships.

**Warning**

Issues that require investigation but may not prevent ingestion.

Examples:
- High missing-value rates in optional fields.
- Unusual revenue values.
- Unexpected category distributions.
- Incomplete historical coverage.

**Informational**

Issues that should be reported for transparency and monitoring.

Examples:
- Optional datasets not supplied.
- Low historical record counts.
- Sparse usage information.

The pipeline must produce a structured validation report.

Critical failures must prevent the affected dataset from proceeding to downstream processing.

---

## 7. Temporal Validation

Temporal validation is essential because the product performs predictive modelling using historical observations.

The following rules apply:

1. Dates must be chronologically consistent.
2. Subscription snapshots must not occur before the subscription start date.
3. Subscription snapshots must not occur after the agreed extraction cutoff.
4. Cancellation dates must not precede subscription start dates.
5. Usage records must correspond to valid subscription periods.
6. Invoice payment information must not be treated as available before its actual availability date.
7. Historical records must preserve the state known at the relevant observation date.

Temporal validation must also consider the distinction between:

- Event date: when an event occurred.
- Recording date: when the event was registered in the source system.
- Availability date: when the information became available for analytical use.

Where available, these dates should be preserved to support point-in-time correctness.

---

## 8. Churn Identification and Target Construction

The initial product focuses on contractual subscription churn.

Churn labels will be constructed at subscription level.

### 8.1 Initial Conceptual Definition

A subscription is considered churned when its contractual relationship has ended according to the client's agreed business rules.

The target variable will represent whether a subscription experiences a qualifying churn event within the prediction horizon following the observation date.

### 8.2 Target Construction

For a given observation date:

- The observation window contains information available up to that date.
- The prediction horizon covers the subsequent period.
- A qualifying contractual churn event within the prediction horizon produces a positive target.
- The absence of a qualifying event within a fully observed prediction horizon produces a negative target.
- Records without sufficient future observation must not automatically be labelled as non-churn.

The exact target construction will be implemented after data discovery and agreement on contractual definitions.

### 8.3 Events Requiring Business Rules

The following cases must be explicitly addressed:

- Customer cancellation requests.
- Cancellation effective dates.
- Contract expiration.
- Non-renewal.
- Automatic renewal failures.
- Subscription suspension.
- Temporary pauses.
- Reactivated subscriptions.
- Subscription upgrades and downgrades.
- Contract renewals.
- Multiple subscriptions belonging to the same customer.

### 8.4 Important Distinction

Contractual churn must not be confused with:

- Reduced product usage.
- Customer inactivity.
- Payment delinquency.
- Temporary suspension.
- Revenue contraction.
- Customer-level churn.

These events may be useful predictive signals, but they do not automatically represent contractual churn.

---

## 9. Data Leakage Prevention

Data leakage prevention is a mandatory requirement.

For every historical prediction observation:

1. Predictive features must use only information available at or before the observation timestamp.
2. Future cancellation information must not be included in predictive features.
3. Current subscription values must not be retrospectively applied to historical observations.
4. Future invoices, payments and usage records must not be used.
5. Target variables must be constructed separately from predictive features.
6. `customer_id` and `subscription_id` must be treated as identifiers, not predictive model features.
7. Model validation must respect the temporal structure of the data.

The initial model will not use direct customer or subscription identifiers as predictive features.

The final feature selection strategy will be documented separately.

---

## 10. Privacy and Data Governance

Client data must be handled according to the product's data governance requirements.

The initial principles are:

- Client-specific data isolation.
- No shared cross-client model training by default.
- Data minimisation.
- Use of pseudonymous identifiers where possible.
- Restricted access to raw client data.
- Controlled retention and deletion procedures.
- Secure handling of credentials and model artefacts.

Before processing live client data, the relevant privacy and governance requirements must be reviewed.

For UK clients, this includes assessing applicable UK GDPR and Data Protection Act requirements, controller and processor responsibilities, lawful basis, transparency, data retention, profiling considerations and whether a Data Protection Impact Assessment is necessary.

The data contract does not itself constitute legal approval to process client data.

Direct personal identifiers such as names, email addresses, phone numbers and postal addresses are not required by the initial churn prediction interface and should not be supplied.

---

## 11. Data Ingestion Expectations

The initial ingestion interface will use client-provided CSV files.

The ingestion pipeline is expected to follow this sequence:

```text
Client CSV Files
       |
       v
File Discovery and Loading
       |
       v
Structural Validation
       |
       v
Schema Validation
       |
       v
Data Quality Checks
       |
       v
Referential Integrity Validation
       |
       v
Temporal Validation
       |
       v
Validated Raw Data
       |
       v
Data Preprocessing
       |
       v
Processed Data
       |
       v
Feature Engineering
```

The ingestion pipeline must:

- Identify missing required files.
- Validate expected columns.
- Validate data types.
- Validate primary and foreign keys.
- Identify duplicate records.
- Validate date and monetary fields.
- Generate structured validation reports.
- Prevent critical data quality failures from reaching downstream processing.

Raw input files must remain separate from processed datasets.

The original client-provided data must not be silently overwritten during preprocessing.

---

## 12. Data Contract Versioning

This document follows semantic versioning principles for contract changes.

| Change Type | Version Example | Description |
|---|---|---|
| Major | 1.0 → 2.0 | Breaking changes to required fields, keys or dataset structure |
| Minor | 1.0 → 1.1 | Backward-compatible additions or clarifications |
| Patch | 1.1.0 → 1.1.1 | Corrections and documentation improvements |

Any structural change must be documented.

Changes that affect schema validation, feature engineering or model compatibility must be reviewed before implementation.

---

## 13. Open Decisions

The following decisions remain open and must be resolved during data discovery or subsequent architecture work.

| ID | Topic | Question / Decision Required |
|---|---|---|
| DD-001 | Snapshot convention | Will snapshots represent the first or last day of each month? |
| DD-002 | Historical coverage | What minimum historical period is required for model development? |
| DD-003 | Churn definition | Which contractual events qualify as churn for each client? |
| DD-004 | Reactivation | Is a reactivated subscription treated as a new subscription episode or a continuation? |
| DD-005 | Contract renewal | How should renewals and extensions be represented? |
| DD-006 | Subscription episodes | Can a subscription have multiple lifecycle episodes under the same identifier? |
| DD-007 | Subscription status | Which client-specific statuses map to the standard status taxonomy? |
| DD-008 | Revenue definition | Does `recurring_revenue` represent MRR, ARR, or another recurring revenue measure? |
| DD-009 | Currency handling | Will the product retain original currencies or convert revenue into a reporting currency? |
| DD-010 | Timezone | Which timezone and cutoff convention apply to event timestamps? |
| DD-011 | Historical availability | Are event recording and data availability timestamps available? |
| DD-012 | Prediction horizon | Is a 30-day prediction horizon appropriate for the client's contractual model? |
| DD-013 | Observation window | Is a 90-day observation window appropriate for the client's data and business model? |
| DD-014 | Customer aggregation | Which metrics will be used to aggregate subscription-level risk at customer level? |
| DD-015 | Missing data | What completeness thresholds will be applied to optional and predictive fields? |

These decisions must not be silently assumed during implementation.

---

## 14. Acceptance Criteria

The initial data contract will be considered ready for implementation when:

1. The subscription-level prediction entity is confirmed.
2. The customer and subscription relationship is clearly defined.
3. The required and optional datasets are documented.
4. Historical subscription snapshots are included in the contract.
5. Primary and foreign keys are defined.
6. Field names, data types and mandatory requirements are specified.
7. Referential integrity rules are documented.
8. Temporal validation requirements are documented.
9. Data leakage prevention principles are documented.
10. Churn identification principles are documented.
11. Privacy and data governance requirements are documented.
12. Remaining business decisions are explicitly recorded.

Approval of this contract authorises implementation of the corresponding data schemas and ingestion validation components.

It does not authorise the use of live client data or deployment of a predictive model in production.

---

**Document End**
