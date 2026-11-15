# Data Sources and Governance

**Document ID:** NCI-DATA-001  
**Version:** 0.2  
**Status:** Draft for review

## 1. Development data strategy

The project will use separate datasets for separate purposes. They must not be indiscriminately merged into one training dataset.

| Dataset | Intended use | Important limitation |
|---|---|---|
| IBM Telco Customer Churn | Benchmark contractual churn classification | Not a UK SaaS dataset; schema and business context differ |
| Synthetic SaaS dataset | Build and test SaaS-oriented pipelines and application workflows | Cannot validate real-world model performance |
| UCI Online Retail II | Transactional behaviour, repeat purchasing, segmentation, and non-contractual inactivity/CLV experiments | Historical UK retailer data; not subscription churn |
| UCI Online Retail | Additional transactional experiments and comparison | Historical and not representative of current UK market |

Dataset use must comply with the relevant dataset licence and terms. The project must record source URL, download date, version, licence, and any usage restrictions.

## 2. Client data required for a SaaS pilot

Minimum viable client data will depend on the churn definition. A likely starting set includes:

- Customer or account identifier.
- Subscription identifier, where applicable.
- Subscription start date.
- Cancellation/end date or status history.
- Billing amount and billing frequency.
- Payment status/history, if available.
- Product usage/activity history, if available.
- Customer support interactions, if available.

Do not make optional fields mandatory unless the modelling approach genuinely requires them.

## 3. Data readiness assessment

Before model development, assess:

- Coverage and completeness of churn events.
- Length of historical observation.
- Consistency of customer identifiers.
- Subscription changes and reactivations.
- Timestamp quality and time zones.
- Availability of historical snapshots.
- Class balance and number of positive churn events.
- Whether features are available at the intended scoring time.

If the dataset lacks reliable event history, the team may need to reduce the scope to descriptive analysis or a proof of concept rather than claim predictive validity.

## 4. Synthetic data

Synthetic data may be used to:
- Test ingestion and schema validation.
- Exercise feature pipelines.
- Test APIs, dashboards, and exports.
- Test edge cases and failure handling.
- Demonstrate application workflows.

Synthetic data must be clearly labelled. Model performance on synthetic data must not be represented as evidence of expected performance on real customers.

## 5. UK data protection and governance

Before processing live client data, agree:
- Controller and processor roles.
- Lawful basis and purpose.
- Transparency and privacy-notice requirements.
- Data minimisation.
- Retention and deletion.
- Access controls and security measures.
- International transfer arrangements, if relevant.
- Whether a Data Protection Impact Assessment is required.
- Procedures for data-subject rights requests.
- Restrictions relevant to profiling and solely automated decisions.

Obtain appropriate legal/privacy review for the specific deployment. This document is an engineering planning document, not legal advice.

## 6. Data handling controls

- Use pseudonymous identifiers in model datasets where feasible.
- Keep direct identifiers out of model features unless justified.
- Restrict access to raw data.
- Do not place client data in public repositories.
- Do not use live client data in local development without explicit approval and appropriate safeguards.
- Keep credentials and secrets outside source control.
- Define secure transfer and deletion procedures.
- Ensure logs do not contain unnecessary personal data.

## 7. Data source references

- IBM Telco Customer Churn: IBM sample dataset / IBM documentation; verify the exact download source and terms selected for the project.
- UCI Online Retail II: https://archive.ics.uci.edu/dataset/502/online+retail+ii
- UCI Online Retail: https://archive.ics.uci.edu/dataset/352/online+retail
- UK Information Commissioner's Office: https://ico.org.uk/

The exact source, version, licence, and retrieval date must be recorded in the repository before datasets are committed or redistributed.
