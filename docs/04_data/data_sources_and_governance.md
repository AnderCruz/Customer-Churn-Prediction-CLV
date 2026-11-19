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
| Misata B2B SaaS Subscription Analytics | Complementary SaaS account, subscription, billing and support analysis | Fictional source identifiers and lifecycle states remain native to Misata |
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

## 8. Approved complementary Phase 03 sources

The Project Owner authorised local acquisition and independent analytical integration of Misata B2B SaaS Subscription Analytics and UCI Online Retail II before Phase 03 closure. Fieldwise Cloud remains the primary development source. IBM Telco and UCI Online Retail (dataset 352) remain assessment candidates.

| Source | Publisher evidence | Local acquisition |
|---|---|---|
| Misata B2B SaaS Subscription Analytics | [Misata Studio dataset page](https://www.misata.studio/datasets/saas-subscription-analytics), CC0 1.0, seed 20260722, third-party synthetic data with ten fictional country markets including the UK | `data/external/misata_saas/`, acquired 19 November 2026 22:06 UTC from the publisher ZIP. Archive 635,172 bytes, SHA-256 `243a7a4006b4d24b6ffab562b67205da4d2dcec9d9f5f4525c147222de5231fe`. |
| UCI Online Retail II | [UCI catalogue, dataset 502](https://archive.ics.uci.edu/dataset/502/online%2Bretail%2Bii), CC BY 4.0. Credit Daqing Chen (2012), *Online Retail II*, UCI Machine Learning Repository, [DOI 10.24432/C5CG6D](https://doi.org/10.24432/C5CG6D). Retain the licence link and identify adaptations when sharing. | `data/external/uci_online_retail_ii/`, acquired 19 November 2026 22:06 UTC from the UCI ZIP. Archive 45,622,418 bytes, SHA-256 `572e36277c2390fbfde10664750731e0a86f55e33470d91919085f0408e67bfb`. Workbook 45,622,278 bytes, SHA-256 `bcbe73b35f5b7babf197fb0cb983a11f5d9ff929078d4aa53d171b1f2df2e980`. |

The ignored source directories retain the original archives and extracted source files. Each `provenance.json` records the exact UTC acquisition timestamp, official HTTPS URL, classification, licence and release evidence, filenames, sizes and per-file SHA-256. These are local integrity checksums. Neither publisher supplied a pinned hash for comparison. Keep raw inputs local and separate. The current authorisation covers local development and excludes publication and commercial redistribution.

### 8.1 Native schemas and compatibility

| Misata file and grain | Ordered native fields |
|---|---|
| `accounts.csv`, one row per account | `account_id, company_name, industry, country, employee_count, signup_date, plan` |
| `subscriptions.csv`, one row per source subscription | `subscription_id, account_id, seats, status, mrr, started_on, ended_on` |
| `invoices.csv`, one row per source invoice | `invoice_id, account_id, invoice_date, amount, status` |
| `support_tickets.csv`, one row per ticket | `ticket_id, account_id, opened_at, priority, category, satisfaction_score, resolution_hours, resolved_at` |
| `users.csv`, one row per user | `user_id, account_id, full_name, role, email` |

Misata amounts retain the source USD meaning and exact decimals. Timestamps are UTC. Account IDs join the five tables within Misata. Invoices link to accounts, with consistency checked against the unique native subscription for each account. The native source does not establish Nowa canonical episodes, reactivation history, point-in-time feature availability, monthly usage or subscription snapshots. The adapter preserves native identifiers, amounts and status values without issuing canonical IDs or outcomes.

UCI's `online_retail_II.xlsx` contains `Year 2009-2010` and `Year 2010-2011`, both at invoice-line grain. The ordered native headers are `Invoice, StockCode, Description, Quantity, InvoiceDate, Price, Customer ID, Country`. The Python iterator preserves sheet and row positions, source wall-time dates, nullable customer and description fields, signed integer quantities and exact decimal GBP values. A publisher-defined `C` invoice prefix denotes cancellation. Negative non-cancellation quantities, adjustment invoice identifiers, negative and zero prices and repeated lines remain in the data. The adapter records product-code whitespace trimming and numeric descriptions represented as text. Retail data supports transactional analysis and lacks canonical subscription identity, lifecycle and subscription outcome evidence.

### 8.2 Local acquisition and analytical access

Run the commands from the project root with the project environment active. Acquisition requires network access to the two official HTTPS endpoints. Verification is offline.

```bash
python -m nowa_customer_intelligence.data.public_sources.acquisition acquire misata_saas
python -m nowa_customer_intelligence.data.public_sources.acquisition acquire uci_online_retail_ii
python -m nowa_customer_intelligence.data.public_sources.acquisition verify misata_saas
python -m nowa_customer_intelligence.data.public_sources.acquisition verify uci_online_retail_ii
```

Use `misata.load_misata(Path("data/external/misata_saas"))` for typed account, subscription, invoice, support and user tables and their quality report. Use `retail.iter_retail_lines(Path("data/external/uci_online_retail_ii/online_retail_II.xlsx"))` to stream typed retail lines. Both modules are under `nowa_customer_intelligence.data.public_sources`. The retail iterator exposes invoice, customer, date and cancellation fields for downstream customer, recency, frequency and cohort analysis and a signed exact-decimal transaction value. The full retail audit retains bounded fingerprints for duplicate detection while the iterator streams one line at a time. These interfaces preserve the separate native source schemas and apply no Customer Data Contract projection.

### 8.3 Live verification results

Misata passed native validation across 42,240 records. The five tables contained 1,200 accounts, 1,200 subscriptions, 7,892 invoices, 6,946 tickets and 25,002 users. All primary keys were unique and all 41,040 account references resolved. Account and subscription starts span January 2023 to December 2025 UTC. Invoices and ticket openings span January to December 2025. Missing fields were limited to 907 subscription end dates, 2,292 satisfaction scores and 123 each for ticket resolution timestamp and hours. All five tables are available for independent local analysis.

UCI passed native structural and type checks across 1,067,371 lines, comprising 525,461 and 541,910 lines in workbook order, 53,628 distinct invoice IDs and 5,942 distinct known customer IDs. Dates span 1 December 2009 through 9 December 2011. The quality report counted 243,007 missing customer IDs, 4,382 missing descriptions, 34,335 repeated normalised lines, 19,494 cancellation lines across 8,292 invoice IDs, and 22,950 negative quantities, including 3,457 on non-cancellation invoices. One cancellation line had non-negative quantity. Five unit prices were negative and 6,202 were zero. Four numeric descriptions and one whitespace-padded product code were normalised with explicit notes. No source lines were dropped. The workbook is available for independent local retail analysis with these limitations.
