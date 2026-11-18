# Synthetic Business Model Specification

**Document ID:** NCI-SYNTH-BIZ-001
**Version:** 0.2
**Status:** Approved
**Project:** Nowa Customer Intelligence
**Market context:** United Kingdom (GB)
**Scope:** Fictional business and synthetic data requirements; no generator or dataset is implemented here.

## 1. Executive Summary

This specification defines a fictional B2B SaaS company and a coherent commercial context for a future synthetic population. The proposed company, **Fieldwise Cloud Ltd**, sells workflow and compliance software to UK organisations that coordinate recurring operational work across teams and sites. The business model gives the synthetic population recurring subscriptions, customer accounts, plans, seats, usage, invoices, payment events, upgrades, contraction, cancellation, and possible reactivation.

All company, product, price, customer mix, behavioural, and commercial characteristics in this document are **PROPOSED SYNTHETIC ASSUMPTIONS**. They are not descriptions of an actual company or estimates of UK SaaS market behaviour.

The architecture already approves the distinction between `customer_id` and a canonical episode `subscription_id`, UUID as the initial canonical identifier strategy, a persistent client-isolated Episode Identity Registry requirement, preservation of historical episodes, and a new episode after confirmed reactivation following termination. These architectural decisions do not define episode boundary evidence, cancellation semantics, renewals, pauses, churn qualification, or registry implementation. Source identifiers and dates/statuses must not be used to infer episode identity on their own.

The proposed baseline is intentionally modest: four subscription plans, configurable pricing and customer segments, a GBP-first billing scenario, monthly and annual billing, monthly usage and snapshots, and one active episode per customer by default. Annual invoices use the discounted full annual amount while `recurring_revenue` in the subscription master and snapshots uses a consistently monthly-normalised amount. Additional seats are included without extra baseline charges. Plan upgrades and downgrades update the existing episode’s commercial state and do not automatically create a new episode. A separate optional scenario may represent multiple concurrent episodes only where the fictional business explicitly creates separate contractual subscriptions and each episode is authoritatively assigned in synthetic ground truth.

The contract can represent many core business attributes, but not product catalogue detail, seat counts, event history, event availability timestamps, payment attempt histories, refund amounts, invoice service periods, plan-price components, or identity ambiguity. Those gaps are called out rather than added to the existing contract.

## 2. Specification Authority and Classification

Each important rule is classified as one of:

- **APPROVED DECISION** — explicitly approved architecture or product decision; not reopened here.
- **EXISTING CONTRACT CAPABILITY** — a field, grain, or relationship available in Customer Data Contract v1.1; semantics may still be open.
- **PROPOSED SYNTHETIC ASSUMPTION** — a fictional rule for a future synthetic business scenario only.
- **OPEN DECISION** — product, client, or technical issue that remains unresolved.
- **NOT SUPPORTED** — cannot currently be represented in the five contract datasets or inspected implementation.

### 2.1 Repository inspection notes

Reviewed the current [Customer Data Contract v1.1](customer_data_contract.md), [ADR-009](../03_architecture/architecture_decisions.md), [ADR-010](../03_architecture/adr_episode_identity_and_identifier_management.md), [Subscription Episode & Lifecycle Decision Specification v0.4](subscription_episode_lifecycle_decision_specification.md), [Data Sources and Governance](data_sources_and_governance.md), [Business Objectives and Scope](../01_business/business_objectives_and_scope.md), [Business Case](../01_business/business_case.md), [product decision inventory](product_decisions_and_contract_design_assessment.md), [approved product decision record](product_decision_proposals.md), [contract/episode impact assessment](subscription_episode_data_contract_impact_assessment.md), and the customer, subscription, snapshot, usage, and invoice schema and temporal-validation modules under `src/nowa_customer_intelligence/data/`.

The repository search did not find a document explicitly named or identified as the **NA Engineering Development Standard (NEDS)**. The Phase 3.3.1 population specification is present in the preceding conversation but not as a repository file. This specification follows the task’s stated NEDS principles of scope control, explicit decision classification, traceability, reproducibility, incremental specification, and separation of requirements from implementation; it does not claim conformance to additional NEDS requirements that were not available for inspection.

### 2.2 Approved decisions relevant here

- **APPROVED DECISION:** `customer_id` identifies the customer/account; the contractual episode is the prediction entity.
- **APPROVED DECISION:** Nowa owns canonical `subscription_id`; it identifies one episode, remains stable, and is never reassigned.
- **APPROVED DECISION:** UUID is the initial canonical identifier generation strategy. Issue once for an authoritatively established episode, persist, and reuse.
- **APPROVED DECISION:** A persistent, client-isolated Episode Identity Registry is required. Its implementation is not present in the repository.
- **APPROVED DECISION:** Conflicting or ambiguous identity evidence must be visible and unresolved rather than silently resolved. Approved PD-002/PD-003 requirements exclude unresolved identity records from identity-dependent processing and prevent automatic issuance/reuse when identity evidence is insufficient.
- **APPROVED DECISION:** Confirmed reactivation following termination creates a new episode, and previous episode identity/history is preserved.
- **APPROVED DECISION:** Contractual and non-contractual churn are separate use cases; contractual churn is the initial focus (ADR-006).
- **APPROVED DECISION:** Initial prediction/evaluation unit is subscription-level (ADR-009), clarified by the episode decision specification as an individual contractual episode.
- **APPROVED DECISION:** Customer ID must not be used as a predictive model feature (contract v1.1).
- **APPROVED DECISION:** Snapshots are optional for basic ingestion and required for workflows that claim temporal modelling (PD-006); this does not resolve the currently implemented loader’s unconditional snapshot requirement or any snapshot date convention.

## 3. Fictional Business Profile

### 3.1 Company and product

| Attribute | Proposed fictional definition | Classification |
|---|---|---|
| Company | Fieldwise Cloud Ltd | PROPOSED SYNTHETIC ASSUMPTION |
| Domain | B2B workflow coordination and operational compliance software | PROPOSED SYNTHETIC ASSUMPTION |
| Main product | Fieldwise Operations Cloud, a hosted workspace for assigning, tracking, and evidencing recurring operational work | PROPOSED SYNTHETIC ASSUMPTION |
| Core problem | Organisations coordinate recurring work, evidence, and approvals across people and sites using disconnected spreadsheets and tools | PROPOSED SYNTHETIC ASSUMPTION |
| Target customers | UK businesses with teams performing repeatable operational workflows across one or more locations | PROPOSED SYNTHETIC ASSUMPTION |
| Value proposition | Centralise work queues, automate routine steps, and provide a traceable record of completion and exceptions | PROPOSED SYNTHETIC ASSUMPTION |
| Geographic scope | UK-first. The baseline uses GBP and UK customer records; an optional international scenario may include other ISO currencies without conversion | PROPOSED SYNTHETIC ASSUMPTION |
| Product delivery | Hosted, account-based software accessed by licensed users | PROPOSED SYNTHETIC ASSUMPTION |

This is an engineering narrative only. It is not a claim about Nowa Analytics’ own business or a real Fieldwise Cloud entity.

### 3.2 Acquisition and onboarding assumptions

- **PROPOSED SYNTHETIC ASSUMPTION:** Customers arrive through direct sales, partner referral, or self-service enquiry. Acquisition channel is generator metadata only; the contract has no acquisition-channel field.
- **PROPOSED SYNTHETIC ASSUMPTION:** An account is created during sales/onboarding before or at its first trial or paid episode. Account creation and paid subscription start may differ.
- **PROPOSED SYNTHETIC ASSUMPTION:** Larger accounts may require assisted onboarding and configuration; smaller accounts may onboard through a standard guided setup.
- **OPEN DECISION:** The baseline does not represent personal contact details, sales pipeline events, support interactions, or onboarding milestones because these are not in the five contract datasets and are not needed to demonstrate the current interface.

## 4. Product and Plan Catalogue

The plans below are deliberately simple and allow variation in seats, usage, and recurring revenue. Prices, limits, included features, and annual discounts are **PROPOSED SYNTHETIC ASSUMPTIONS**, not actual UK market prices. Plan and limit details are internal fictional product-catalogue metadata; the contract can carry `plan_id`, but not the catalogue or seat/limit details themselves.

**PROPOSED SYNTHETIC ASSUMPTION:** Monthly subscriptions are billed monthly in advance. Annual subscriptions are billed annually in advance and receive a fictional 10% discount against twelve monthly list-price payments. For the baseline revenue calculation, monthly billing uses `recurring_revenue = monthly_invoice_amount`. Annual billing uses `annual_invoice_amount = monthly_list_price × 12 × (1 - annual_discount_rate)` and `recurring_revenue = annual_invoice_amount / 12`. The annual invoice record contains the full annual amount; the monthly-normalised value is stored in both `subscriptions.recurring_revenue` and `subscription_snapshots.recurring_revenue`. No inference about real-world discounting is intended.

| Plan (`plan_id`) | Intended segment (not identical to plan eligibility) | Fictional included capability and allowance | Monthly list price (GBP) | Annual prepay (GBP, 10% synthetic discount) | Commercial notes |
|---|---|---|---:|---:|---|
| `launch` | Micro and small organisations | Core work queues, templates, evidence log; 5 included seats; one workspace; basic reporting | £79 | £853.20 | Additional seats do not add baseline charges; standard support assumption |
| `growth` | Small and medium organisations | Launch features plus workflow automation, team dashboards, and 20 included seats | £249 | £2,689.20 | Supports moderate team and workflow growth |
| `scale` | Medium and large organisations | Growth features plus multi-site views, advanced reporting, API access, and 75 included seats | £699 | £7,549.20 | Higher usage and administration allowance |
| `enterprise` | Large or operationally complex organisations | Configurable controls, SSO, advanced permissions, and 250 included seats | £1,800 | £19,440 | Fictional base amount; negotiated additions are not represented as separate contract fields |

### 4.1 Limits and commercial restrictions

- **PROPOSED SYNTHETIC ASSUMPTION:** Each plan has an included seat allowance and configurable usage limits. Additional seats are uncharged in the baseline; seat changes may alter usage but do not alter recurring revenue. No per-seat recurring charges, additional-seat invoice lines, overage billing, or seat-change proration are generated. These may be considered in a separately labelled optional scenario.
- **PROPOSED SYNTHETIC ASSUMPTION:** A customer may select a suitable plan regardless of its employee segment. Segment is descriptive, not a deterministic plan assignment.
- **PROPOSED SYNTHETIC ASSUMPTION:** In the first baseline, plan changes take effect from the configured next billing date. **OPEN DECISION:** Production timing may be immediate, next billing date, or renewal and is not approved.
- **NOT SUPPORTED:** The current contract has no seat count, feature entitlement, usage limit, discount, tax, or plan-price field. `plan_id` can identify a plan in synthetic generator metadata but does not carry its full terms.

## 5. Customer Segmentation

These employee bands and segment descriptions are **PROPOSED SYNTHETIC ASSUMPTIONS** for illustrative coverage. They do not describe the UK market distribution. Customer segment is an account characteristic and must not be made equivalent to plan.

| Segment | Fictional employee range | Likely plan fit | Usage/commercial profile for scenario design | Possible expansion or retention challenge |
|---|---:|---|---|---|
| Micro | 1–10 | Launch; occasionally Growth | Few licensed users; low absolute event volume; owner-led administration | Limited staff capacity, variable engagement, or growth beyond included seats |
| Small | 11–50 | Launch or Growth | Several teams or workflows; moderate usage with uneven adoption | Adoption may depend on a small champion group; seat or workflow expansion possible |
| Medium | 51–250 | Growth or Scale | Multiple departments or locations; broader user and workflow footprint | Expansion potential with adoption; configuration and integration needs may increase |
| Large | 251+ | Scale or Enterprise | Multiple sites, administrators, and business units; higher absolute usage | Longer onboarding and procurement assumptions; broader deployment may phase over time |

Illustrative industries may include professional services, financial services, technology, retail/e-commerce, manufacturing, healthcare, and other services. They exist to exercise categoricals and segmentation; no proportions or industry-specific churn behaviour are asserted.

Customer-level aggregation may group episode and invoice history using `customer_id`, while retaining each canonical `subscription_id` episode as an independent prediction entity. **OPEN DECISION:** The product has not approved a customer-level risk aggregation rule or CLV formula.

## 6. Customer and Episode Business Model

### 6.1 Entity relationships

```text
Customer account (customer_id)
  ├── Contractual episode A (subscription_id = canonical UUID)
  │     ├── monthly snapshots (subscription_id, snapshot_date)
  │     ├── monthly usage (subscription_id, usage_month)
  │     └── invoices (invoice_id, subscription_id)
  └── Contractual episode B (new canonical UUID if a new episode is established)
        ├── monthly snapshots
        ├── monthly usage
        └── invoices
```

**APPROVED DECISION:** One customer may have multiple episodes; each episode has its own independently managed lifecycle and identity. A new episode after confirmed termination receives a new canonical UUID. Prior episodes and their attributed history remain preserved.

**EXISTING CONTRACT CAPABILITY:** Customers have one row per `customer_id`; subscriptions have one row per `subscription_id` and a `customer_id` reference; snapshots, usage, and invoices reference `subscription_id`. This structure permits multiple subscription rows per customer and dependent rows per episode, subject to correct authoritative episode attribution.

### 6.2 Required scenarios

1. **One customer, one episode:** default baseline case.
2. **One customer, multiple sequential episodes:** include in baseline at a modest configurable frequency; second episode is created only for a synthetic ground-truth reactivation scenario after confirmed termination.
3. **One customer, multiple concurrent episodes:** possible as an optional scenario for distinct contractual products/workspaces. `plan_id` could distinguish product/plan in scenario metadata, but the contract has no dedicated product or contract ID. Keep this scenario out of baseline until the intended episode meaning is explicit.
4. **Termination then reactivation:** preserve the first episode and all historical dependent records; assign a new canonical UUID to the new episode. Do not reuse the old episode ID.
5. **Plan/seat changes during an episode:** treat as a commercial change within the same episode in the baseline; reflect plan and recurring-revenue changes in later snapshots and invoice amounts from the configured next billing date. Seat changes can affect usage but do not change baseline recurring revenue or invoice amounts. Neither plan nor seat changes automatically create a new episode. This is a proposed synthetic rule, not an approved renewal or contract policy.
6. **Historical episode plus current episode:** account has one ended episode and a later currently active episode; customer reporting can aggregate at account level without collapsing the two episode identities.

### 6.3 Distinguishing commercial events

| Concept | Business meaning | Classification / unresolved point |
|---|---|---|
| Plan change | Product tier changes for an existing service relationship | PROPOSED SYNTHETIC ASSUMPTION: within-episode change in baseline; production episode-boundary semantics remain OPEN DECISION |
| Renewal | A new contract term or continuation after a term boundary | OPEN DECISION: a renewal does not automatically create a new episode; whether it continues the existing episode or establishes a distinct episode depends on source/contract evidence |
| Extension | Contract end is moved or term extended | OPEN DECISION: an extension does not automatically create a new episode; exact semantics and identity effect are not defined |
| Cancellation request | Customer asks to stop service | OPEN DECISION: request date is not necessarily effective date or termination |
| Effective cancellation / termination | Contractual service relationship ends under defined terms | OPEN DECISION: the event and date semantics must be established; not equivalent automatically to status text |
| Reactivation | Service begins again after confirmed termination | APPROVED DECISION: creates a new episode; exact evidence of termination and reactivation event remains open |

The Episode Identity Registry is not implemented and is outside this specification. No source-ID mapping or identity-resolution algorithm is proposed.

## 7. Contract and Billing Model

### 7.1 Contract types and episode dates

- **PROPOSED SYNTHETIC ASSUMPTION:** Offer monthly rolling contracts and annual fixed-term contracts with automatic renewal enabled by default for the scenario, but permit `auto_renew` false as a configurable case.
- **PROPOSED SYNTHETIC ASSUMPTION:** A fictional subscription starts on its synthetic contractual commencement date; trial start may precede paid start only if the trial is modelled as part of the same episode in that scenario.
- **OPEN DECISION:** The contract fields `start_date`, `end_date`, and `cancellation_date` exist, but their exact relationship to activation, cancellation request, effective cancellation, final service day, expiration, and termination is unresolved. Do not generate contradictory meanings or imply that request date equals end date.
- **OPEN DECISION:** Auto-renewal intent does not establish that a renewal occurred, whether it extends the same episode, or whether a renewal begins a new episode.
- **NOT SUPPORTED:** Contract term length, cancellation request timestamp, renewal event, and service-access interval have no dedicated fields in v1.1.

### 7.2 Invoicing and payment behaviour

**PROPOSED SYNTHETIC ASSUMPTION:** Generate invoices in advance at the billing cadence: one invoice per month for monthly billing and one invoice per year for annual prepayment. Monthly invoice amount equals the monthly list price in the baseline; an annual invoice contains the full discounted annual amount defined in Section 7.3. Due dates and payment dates vary in configured scenarios. An invoice is linked to an episode only because the generator has authoritative synthetic ground truth, not because its date happens to overlap an episode.

| Event/status | Fictional business interpretation | Contract support and limitation |
|---|---|---|
| Invoice issue | Bill is issued for an episode’s plan and billing period | `invoice_date`, `invoice_id`, `subscription_id`, amount and currency supported; covered service period not supported |
| Due date | Payment is contractually due | Optional `due_date` supported |
| Paid | Payment is settled | `paid_date` and `invoice_status` supported; payment transaction identity/cash amount is not |
| Pending | Issued but not yet resolved | Status supported; no payment-attempt history |
| Late / overdue | Due date passed without recorded payment, or payment after due date | `overdue` status and dates supported; exact status transition timing not defined |
| Failed payment | Attempt failed | `failed` invoice status supported; attempt count, reason, and retry timeline are not |
| Void | Invoice cancelled before collection | `void` status supported; void event date/reason is not |
| Refund | Money returned after payment | `refunded` status supported; refund amount/date, partial refund, credit note, and allocation are not |

**PROPOSED SYNTHETIC ASSUMPTION:** A failed or overdue invoice triggers reminders and may temporarily restrict some service after a configurable grace period. It does not automatically cancel, terminate, or churn the episode. The operational response and grace period are fictional scenario rules, not approved product logic.

### 7.3 Revenue semantics

Keep the following concepts distinct:

- **Recurring revenue:** contractual recurring amount at a point in time; stored in `subscriptions.recurring_revenue` and snapshots, but its measure is unresolved.
- **Invoice amount:** amount billed on an invoice, potentially monthly or annual; stored as `invoices.amount`.
- **Cash received:** amount actually collected and timing of settlement. `paid_date` plus invoice amount can approximate settled invoice cash in a simple full-payment scenario, but partial payments and payment transactions are not represented.
- **Contract value:** value over a contractual term; term, discounts, tax, and cancellation treatment are not represented completely.
- **Historical customer revenue:** sum of appropriately attributed invoice or payment amounts across that customer’s episodes over a stated window; invoice-to-episode attribution and refund treatment must be explicit.
- **Customer-level CLV:** future economic value attributed to a customer account across episodes, requiring a separately chosen method and horizon.

**PROPOSED SYNTHETIC ASSUMPTION for the first scenario:** Treat `recurring_revenue` as a monthly-normalised recurring amount (MRR-like) in scenario configuration. For monthly billing, it equals the monthly invoice amount. For annual billing, calculate `annual_invoice_amount = monthly_list_price × 12 × (1 - annual_discount_rate)`, then set `recurring_revenue = annual_invoice_amount / 12`. For Launch at GBP 79.00 per month and a 10% annual discount, the annual invoice is GBP 853.20 and monthly-normalised recurring revenue is GBP 71.10. Store GBP 71.10 in both `subscriptions.recurring_revenue` and each applicable `subscription_snapshots.recurring_revenue`; the annual invoice row contains GBP 853.20, not GBP 71.10. Apply the same calculation consistently to other plans. This makes monthly and annual contracts comparable for scenario analysis.

For reference, the derived annual-billing baseline values are: Launch GBP 853.20 invoice / GBP 71.10 monthly-normalised recurring revenue; Growth GBP 2,689.20 / GBP 224.10; Scale GBP 7,549.20 / GBP 629.10; Enterprise GBP 19,440.00 / GBP 1,620.00. These values follow directly from each listed monthly price and the synthetic 10% discount.

This calculation is a **PROPOSED SYNTHETIC ASSUMPTION** for the fictional baseline only. Customer Data Contract v1.1 does not identify the measure basis; this assumption does not approve the production semantic definition of `recurring_revenue`. The production semantic decision remains **OPEN DECISION**. Label the scenario basis in metadata and do not present it as the approved meaning for real-client data. Do not add contract fields here.

GBP (`GBP`) is the baseline synthetic currency. An optional multi-currency scenario may retain each invoice’s original ISO 4217 currency. **OPEN DECISION:** FX conversion date, source, reporting currency, and historical conversion policy are undefined; no conversion should be implied.

## 8. Product Usage Model

### 8.1 Usage dimensions

The product is used by licensed employees who create, assign, update, and complete operational workflows. Usage can be represented with the existing fields: `active_users`, `total_users`, `sessions_count`, `events_count`, `usage_volume`, and `usage_metric` at one row per episode per usage month.

**PROPOSED SYNTHETIC ASSUMPTION:** `usage_volume` may represent completed workflow items in a scenario, and `usage_metric` can identify that unit. This is only a chosen scenario definition; it is not a universal contract definition.

### 8.2 Behaviour profiles

Include configurable profiles, not hard-coded market segments:

- **High adoption:** a large share of licensed users are active, usage broadly stable or growing.
- **Moderate adoption:** mixed active/inactive users and periodic workflow activity.
- **Low adoption:** few users active relative to licensed users; low event volume.
- **Stable:** usage fluctuates within a configured band.
- **Growing:** active users, sessions, or workflow volume rise over multiple months.
- **Declining:** usage falls over multiple periods.
- **Sudden reduction:** an abrupt drop in a selected metric.
- **Irregular / seasonal:** variable or periodically elevated usage under an explicit scenario calendar.

Potential generated relationships (e.g. larger accounts having greater absolute event volume, higher plans allowing more seats, or low-adoption accounts sometimes declining) are **business hypotheses for engineering experiments**. No relationship is an approved churn driver or an empirical predictor.

### 8.3 Constraints and attribution

- **EXISTING CONTRACT CAPABILITY:** One usage row per `subscription_id` and `usage_month`, non-negative counts and volume, and `active_users <= total_users` when both are present.
- **APPROVED DECISION:** Usage must be assigned to a canonical episode only when authoritative synthetic ground truth establishes that relationship; do not use dates/status to infer it.
- **OPEN DECISION:** Calendar-month versus billing-period boundaries, partial periods, and behavior crossing an episode boundary are unresolved.
- **NOT SUPPORTED:** Seat entitlement, licensed seat count, individual-user events, event timestamps, and event availability timestamps are not contract fields.

## 9. Customer Lifecycle

The following are business lifecycle concepts, not approved values for `account_status` or `subscription_status`:

1. Prospect (outside the five datasets).
2. Account onboarding (account exists; setup activity not represented).
3. Trial (possible contract status, with trial semantics still open).
4. Active customer (one or more active contractual episodes, but no approved customer status derivation).
5. Growing / stable customer (analytical descriptors, not statuses).
6. At-risk customer (model/report concept, not a source lifecycle status).
7. Cancellation requested (request event semantics not represented or approved).
8. Terminated customer relationship or episode (exact event and account-level implications open).
9. Reactivated customer (new episode after confirmed termination is approved; customer-level lifecycle label is not).

`customers.account_status` is a free-text optional field in the contract and schema, not a controlled lifecycle state machine. Subscription status values in the contract/schema are currently `active`, `trial`, `cancelled`, `expired`, `suspended`, and `paused`. Do not introduce `past_due` or `terminated` as subscription statuses. An invoice payment state such as `overdue` is not a contractual subscription state.

## 10. Commercial Event Catalogue

Impacts below are business hypotheses for synthetic scenarios. They do not define production transitions or churn rules.

| Event | Meaning / trigger | Affected entity | Possible revenue / invoice impact | Possible usage impact | New episode? | Classification |
|---|---|---|---|---|---|---|
| Account created | Customer account provisioned | Customer | None by itself | None by itself | No | PROPOSED SYNTHETIC ASSUMPTION; `created_at` supported |
| Trial begins | Evaluation access starts | Episode candidate | No paid invoice in a free-trial scenario | Onboarding usage may begin | OPEN: whether trial is an episode and when it starts |
| Paid subscription starts | Paid contractual service begins | Episode | Recurring revenue begins; invoice generated by cadence | Usage begins | Establishes episode only with authoritative evidence | Dates/status supported; boundary OPEN |
| Invoice issued | Charge billed for contract period | Invoice + episode | Invoice amount recorded | No direct necessary effect | No | Invoice fields support basic event, period not supported |
| Payment late/failed | Due date passes or attempt fails | Invoice; possibly account operations | Cash delayed or absent | Service may be restricted only in a scenario | No | Invoice status/dates supported; operational policy proposed |
| Upgrade/downgrade | Plan changes for same service relationship | Episode state | Baseline recurring amount may change to the new plan amount; invoice reflects the changed plan from the configured next billing date, with no proration | Limits/features may change | No automatic new episode in baseline | Within-episode treatment and next-billing-date timing are proposed synthetic assumptions; production timing OPEN |
| Add/reduce seats | Customer changes licensed capacity | Episode/commercial state | No baseline recurring-revenue or invoice change | May affect usage behaviour | No by baseline | Seat count not supported by contract; additional-seat pricing excluded from baseline |
| Usage rise/fall | User behaviour changes | Episode usage | No automatic billing effect in baseline | Usage measures change | No | Usage rows support aggregate measurements; causal interpretation is hypothesis |
| Cancellation request | Customer requests termination | Episode / source event | May affect future renewal, not necessarily current invoice | Service may continue | No, not by itself | Request semantics not supported; OPEN |
| Effective termination | Contractual service relationship ends | Episode | Recurring revenue ends at scenario-defined point | Usage ceases or tails off by scenario | No; closes current episode | Event definition OPEN; do not infer from status alone |
| Renewal / extension | Contract continues or term extends | Episode or contract | Future recurring revenue/invoice schedule continues | Usage continues | OPEN: same episode or new episode | Client/product decision required |
| Reactivation after termination | New service contract begins after prior episode ended | Customer + new episode | Revenue resumes under new terms | New episode usage begins | Yes, approved | Identity rule approved; evidence/event boundary OPEN |
| Refund / void | Invoice is reversed or money returned | Invoice | Net cash/revenue treatment changes | None necessarily | No | Status supported; amount/timing/allocation not supported |

## 11. Upgrade, Downgrade, Expansion and Contraction

### Baseline proposed behavior

- A plan upgrade or downgrade changes `plan_id` and may change `recurring_revenue` within the existing episode. Subsequent monthly snapshots reflect the new plan and recurring-revenue state. The change does not automatically create a new `subscription_id`.
- Each plan has an included seat allowance. Additional seats do not generate baseline charges; seat counts remain internal generator metadata. Seat changes may affect usage behaviour but do not automatically affect recurring revenue.
- No seat-based pricing, overage billing, additional-seat invoice lines, or proration caused by seat or plan changes are generated in the baseline. These may be considered in future optional scenarios.
- Invoice amounts may reflect a plan change from the configured next billing date. For annual contracts, the invoice amount remains the full annual amount under the scenario calculation; `recurring_revenue` remains monthly-normalised.
- Usage limits/available features may change with a plan. Actual usage remains measured in `usage_monthly` when episode attribution is known.
- Price changes unrelated to customer action are excluded from baseline and may be an optional scenario.

All bullets above are **PROPOSED SYNTHETIC ASSUMPTIONS**. They describe one tractable business scenario and do not approve how plan changes work in a client contract.

### Open interpretations

- **OPEN DECISION:** A renewal could extend the current episode or, if authoritative evidence establishes a distinct contractual episode, be represented by another episode. A renewal does not automatically create a new episode; ADR-010 approves a new episode after confirmed reactivation following termination, and does not decide renewal semantics.
- **OPEN DECISION:** A contract extension could modify the existing end date or, if authoritative evidence establishes a distinct contractual episode, be represented by another episode. An extension does not automatically create a new episode.
- **PROPOSED SYNTHETIC ASSUMPTION:** Baseline plan changes occur within the current episode and do not automatically create a new `subscription_id`. A distinct new episode is created only when synthetic ground truth establishes a distinct new contractual episode consistently with approved identity architecture.
- **NOT SUPPORTED:** Effective-dated plan history beyond monthly snapshots, seat counts, proration lines, discount detail, and reason for commercial changes.

## 12. Churn Business Context

### 12.1 Distinct concepts

- **Episode churn:** qualifying termination of one contractual episode. The episode prediction target is approved at the architectural level, but its qualifying event remains open.
- **Customer/account churn:** loss of the overall customer relationship, potentially after all episodes end. Customer-level churn is deferred and must not be inferred from one episode ending.
- **Cancellation request:** an intent/event that may precede, be reversed before, or fail to result in effective termination.
- **Effective cancellation / termination:** contractual endpoint under business rules that are not yet defined.
- **Expiration / non-renewal:** a term ends without renewal; exact churn interpretation requires an approved rule.
- **Payment-related interruption:** delinquency, failed payment, or temporary access restriction; not automatically churn or episode termination.
- **Reactivation:** new episode after confirmed termination; prior episode remains historically preserved.

### 12.2 Synthetic event alternatives

For test scenarios only, use one of these explicit synthetic label hypotheses:

| Synthetic label hypothesis | Rule | Advantage | Limitation |
|---|---|---|---|
| Effective-end event | Label an episode positive when a synthetic authoritative termination event occurs within the configured future horizon | Clear event timing and aligned with an episode-level target | Production meaning of effective termination and exclusions remain unapproved |
| Non-renewal event | Label positive when an annual term reaches its synthetic end and no renewal is generated by a declared cutoff | Exercises annual renewal cases | Renewal evidence, grace periods, and episode-boundary treatment are unresolved |
| Cancellation-request event | Label on a request timestamp | Easy to generate and can model intent | Not equivalent to actual contractual churn; reversals/withdrawals may invalidate it |

**Recommendation:** Use the effective-end event in the first synthetic scenario because it is simplest to define as a synthetic ground-truth outcome while preserving request/end distinctions. Mark it as a **PROPOSED SYNTHETIC ASSUMPTION**, not a production label. Keep other alternatives as separate scenarios rather than blending them.

### 12.3 Censoring and leakage

- Episodes still active at extraction cutoff, or whose future outcome window is incomplete, are censored / outcome not yet observed; do not label them automatically as non-churn.
- Use only values available by the prediction timestamp. A later invoice payment, cancellation, plan change, or usage aggregate must not appear in historical features.
- Keep synthetic event occurrence time and event availability time separate in generator metadata; v1.1 has no availability-timestamp columns.
- A later reactivation is a separate new episode and does not erase a prior episode’s outcome.
- **OPEN DECISION:** Production churn qualification, prediction horizon, observation window, cancellation reversal handling, grace periods, and reason exclusions remain unapproved. The contract’s 90-day observation and 30-day horizon are provisional assumptions.

## 13. CLV Business Context

CLV is customer-level; the initial churn prediction entity is an episode. For a customer with sequential episodes, customer-level historical revenue may aggregate attributable revenue across each preserved episode. This must not merge episode IDs or turn a customer aggregation into an episode churn target.

Potential future-value methods are alternatives, not approved formulas:

1. **Revenue-based cohort value:** sum invoice revenue over a fixed future horizon, with explicit invoice/credit/refund rules.
2. **Recurring-revenue projection:** project a recurring-revenue measure over a horizon using retention and expansion assumptions.
3. **Contribution-margin value:** forecast revenue less service/acquisition/support cost, if cost inputs become available.
4. **Discounted future cash flow:** discount future cash flows using an approved rate and timing convention.

The first synthetic business scenario should support revenue-based historical summaries and simple recurring-revenue trajectories, while leaving the official CLV estimator unspecified. Monthly/annual billing, failed payments, refund statuses, expansion, and reactivation may affect value, but payment allocation, partial payments, taxes, FX, margin, discounts, discount rate, and future horizon need policy decisions. The contract lacks cost, tax, FX rate, refund amount, service period, and payment transaction fields.

**OPEN DECISION:** No CLV formula, margin definition, customer-level episode aggregation method, future horizon, discounting, or treatment of refunds and non-cash invoices is approved.

## 14. Temporal Consistency Rules

| Temporal relationship | Baseline specification | Classification |
|---|---|---|
| Customer creation | `created_at` precedes or equals associated first episode start in the baseline | PROPOSED SYNTHETIC ASSUMPTION; contract has `created_at`, but equality/order business semantics are not a fully specified validation rule |
| Episode start/end | End must not precede start; cancellation date must not precede start under existing checks | EXISTING CONTRACT CAPABILITY and implemented TC-001/TC-002 checks; event meanings still OPEN |
| Snapshot timing | Monthly snapshots within each episode’s generated valid interval; state must not include future knowledge | Contract-supported point-in-time requirement; first/last day convention OPEN |
| Usage period | One usage record per episode/month only with authoritative episode attribution | Contract-supported grain; period boundaries and cross-episode policy OPEN |
| Invoice issue/due/payment | Due date not before invoice date; paid date not before invoice date | Contract-supported and enforced by invoice schema; service period and status availability semantics OPEN |
| Plan changes | Occurrence at configured effective date; reflected in a later snapshot and billing scenario | PROPOSED SYNTHETIC ASSUMPTION; effective-date field absent |
| Cancellation | Keep request, effective event, service end, and status distinct in generator truth | OPEN semantics; contract has limited dates/status but no request timestamp or event log |
| Cutoff / timezone | Fixed configured extraction cutoff; internal timestamps use UTC for contract-compatible output | Contract uses UTC datetimes; precise cutoff convention and timezone for business-date interpretation OPEN |
| Feature availability | Value may enter a prediction row only after it is available to the scoring process | Contract requirement; separate availability timestamp NOT SUPPORTED in CSV schemas |

The first-of-month versus last-of-month snapshot convention remains explicitly open (DD-001); do not select either as an approved rule. A generator may expose the convention as configuration and use one value per named scenario only after the scenario specification names it. Usage-period boundaries, cutoff timezone, and recurring-revenue basis also remain configurable/open until resolved.

## 15. Customer Data Contract Mapping

The contract supports five CSV datasets and strict schemas. The following mapping describes business fit, not a contract change.

| Dataset | Business purpose / grain | Main supported attributes and relationships | Classification and scenario limits |
|---|---|---|---|
| `customers` | One row per account | `customer_id`, `created_at`, optional country, industry, company size, account status | **SUPPORTED** for account identity and basic segmentation. **PARTIALLY SUPPORTED** for lifecycle: account status is not a controlled lifecycle, and no account-status history, acquisition channel, employee count, or contact data is represented. |
| `subscriptions` | One row per contractual episode in target interpretation | `subscription_id`, `customer_id`, plan ID, start/end, status, billing frequency, recurring revenue, currency, auto-renew, cancellation date/reason | **SUPPORTED** for a subscription master row and basic commercial attributes. **OPEN SEMANTICS** for exact episode boundary, date meaning, revenue basis, renewal/extension, status transitions, and canonical UUID supply workflow. No seat/term/discount/product catalogue fields. |
| `subscription_snapshots` | One row per episode and monthly snapshot date | Episode key, snapshot date, status, recurring revenue, currency, plan, frequency, auto-renew | **SUPPORTED** for monthly historical state. **OPEN SEMANTICS** for snapshot convention, cutoff, availability time, and reliable historical episode attribution. Optional for basic ingestion and mandatory for temporal modelling by approved PD-006; repository loader has not yet been updated from unconditional requirement. |
| `usage_monthly` | One row per episode per usage month | Episode key, month, active/total users, sessions, events, volume, metric | **SUPPORTED** for aggregate monthly usage measures. **PARTIALLY SUPPORTED** for product use because no licensed-seat count, individual events, timestamps, feature usage, or availability time exists. Usage-period semantics and episode attribution remain open. |
| `invoices` | One row per invoice | Invoice ID, episode FK, issue/due/paid dates, amount, currency, status | **SUPPORTED** for basic invoice and payment-state history. **PARTIALLY SUPPORTED** for cash and revenue analytics: no service period, line items, payment attempt, partial payment, refund amount/date, tax, discount, credit note, or allocation policy. Episode attribution must be authoritative. |

### 15.1 Generator metadata versus contract gaps

The following may remain internal generator configuration/ground truth for the first scenario without becoming contract fields: synthetic plan catalogue and prices, licensed-seat allowance, customer segment, acquisition source, lifecycle event log, event availability timestamps, source-system identifier scenarios, event reasons, synthetic label truth, scenario name/seed, and synthetic renewal/term metadata.

If a requirement needs to be consumed by Nowa as client data rather than only used to generate fixtures, it requires a separately reviewed product/contract decision. Do not add fields to v1.1 in this activity.

## 16. Recommended Baseline Scenario

The following coherent baseline is recommended for Phase 3.3.3 design. Every fictional business property below is a synthetic assumption. Population size proportions remain configurable as specified in Phase 3.3.1.

| Element | Recommended baseline | Classification |
|---|---|---|
| Business | Fieldwise Cloud Ltd, fictional UK workflow/compliance SaaS | PROPOSED SYNTHETIC ASSUMPTION |
| Plans | Launch, Growth, Scale, Enterprise with catalogue/prices in Section 4 | PROPOSED SYNTHETIC ASSUMPTION |
| Account segments | Micro, Small, Medium, Large; industry labels optional and illustrative | PROPOSED SYNTHETIC ASSUMPTION |
| Currency | GBP-only in baseline | PROPOSED SYNTHETIC ASSUMPTION |
| Contracts | Monthly rolling or annual prepay; renewal behavior stated in scenario metadata | PROPOSED SYNTHETIC ASSUMPTION; renewal semantics remain open |
| Revenue basis | Monthly-normalised recurring amount stored in `recurring_revenue` for this synthetic scenario | PROPOSED SYNTHETIC ASSUMPTION; not approved contract meaning |
| Episode count pattern | One active episode per customer at a time; some accounts have prior terminated episode and later new episode | PROPOSED SYNTHETIC ASSUMPTION; reactivation-new-episode principle is approved |
| Concurrent subscriptions | Excluded from baseline; optional scenario after explicit episode/product definition | PROPOSED SYNTHETIC ASSUMPTION / OPEN DECISION |
| Plan/seat movement | Plan upgrades/downgrades stay within the existing episode and may change `plan_id` and recurring revenue from the configured next billing date; seat changes affect usage only and add no baseline charge. No proration or new ID is generated automatically. | PROPOSED SYNTHETIC ASSUMPTION |
| Usage | Monthly episode-grain aggregate with stable/growing/declining/irregular profiles and explicit metric unit | Contract grain supported; behavioural relationships are hypotheses |
| Billing | Monthly invoices equal the monthly invoice amount basis; annual advance invoice contains the full discounted annual amount. Recurring revenue remains monthly-normalised in subscription and snapshot rows. Include configurable on-time, late, failed, pending, overdue, void/refund statuses. | PROPOSED SYNTHETIC ASSUMPTION; contract fields support basic representation, refund detail incomplete |
| Churn | Synthetic effective-end event within a declared horizon; active episodes at cutoff are censored | PROPOSED SYNTHETIC ASSUMPTION; production qualification open |
| CLV | Generate invoice and recurring-revenue history usable for alternative future analysis; do not assign official CLV formula | OPEN DECISION |
| Time | Configurable 36-month default history and extraction cutoff; monthly snapshots; convention parameter remains unset until approved | Proposed population assumption; snapshot convention open |

### Explicit first-baseline exclusions

- Actual UK market prices, market shares, churn rates, plan mix, or industry behaviour.
- Multi-currency conversion, tax, margin, costs, discounted cash flow, and proration.
- Detailed renewal/extension event policy or automatic inference from status/date.
- Multiple concurrent episodes unless ground truth explicitly establishes separate contracts.
- Personal data, named users, contact details, support tickets, CRM pipeline, or native billing-provider event data.
- Episode Identity Registry, source ID mapping implementation, and any identity-resolution algorithm.
- Production churn label or approved CLV formula.
- Any claim that synthetic model performance predicts real-world performance.

## 17. Open Decisions and Risk Register

Recommendations below guide later decision work; none changes the source decision status.

| ID | Topic | Description / impact | Alternatives and recommendation | Approval required before generation? | Related contract area / source |
|---|---|---|---|---|---|
| SB-001 | Revenue basis | Meaning of `recurring_revenue` changes interpretation of plan, invoice comparison, ARR/MRR, and CLV | Alternatives: MRR-like normalized amount, ARR, billing-period amount. Recommendation: use monthly invoice amount for monthly billing; for annual billing use discounted annual invoice amount divided by 12, only in the labelled baseline; product definition remains open. | No for isolated synthetic scenario; yes before product/client interpretation | subscriptions, snapshots; DD-008 |
| SB-002 | Episode lifecycle boundaries | Start/end/termination evidence and cancellation semantics affect episode identity and target eligibility | Alternatives depend on authoritative contract events. Recommendation: define synthetic events explicitly and retain unresolved product semantics. | Yes before claiming episode-level production relevance | subscriptions, all dependent FKs; DD-EP-001/005 |
| SB-003 | Renewal and extension | Whether term renewal/extension continues an episode or starts another affects IDs, snapshots, and labels | Alternatives: continue same episode; represent another only if authoritative evidence establishes a distinct episode. Recommendation: neither renewal nor extension automatically creates a new episode; keep production semantics open. | Yes before representing as approved lifecycle | subscriptions/snapshots; DD-EP-006, DD-005 |
| SB-004 | Cancellation and termination | Request/effective/end dates can differ and reversal may occur | Alternatives: request-based, effective-end, expiration/non-renewal. Recommendation: use effective-end only as synthetic label hypothesis. | Yes before production churn labels; no for clearly labelled synthetic truth | subscriptions; DD-EP-005 |
| SB-005 | Snapshot convention | First or last day of month unresolved | Alternatives: first-day state or last-day state. Recommendation: defer selection; expose as scenario configuration. | Yes before using a scenario as contract-conformance evidence | snapshots; DD-001 |
| SB-006 | Usage-period boundaries | Calendar month vs billing period and partial-month handling affect attribution and leakage | Recommendation: identify the period convention explicitly; no cross-episode allocation absent policy. | Yes for temporal/episode usage claims | usage_monthly; DD-EP-009/010 |
| SB-007 | Churn qualification | Qualifying termination, horizon, exclusions, grace period, reversal handling unresolved | Alternatives in Section 12.2. Recommendation: synthetic effective-end event only, clearly not production target. | Yes before production model label | subscriptions/snapshots; DD-EP-013, DD-003/012/013 |
| SB-008 | CLV formula | Revenue vs margin, horizon, discounting, episode aggregation unresolved | Alternatives in Section 13. Recommendation: retain multiple candidate metrics; do not designate one as product CLV. | Yes before official CLV output | invoices, subscriptions; business objective BO-02 |
| SB-009 | Refund/payment allocation | Refund status has no amount/date; partial payments and credits not represented | Alternatives: exclude; treat whole invoice as reversed; add future allocation model after decision. Recommendation: keep baseline refund cases only as status tests. | Yes before net revenue or cash claims | invoices |
| SB-010 | Currency and FX | Currency field exists but reporting currency and conversion policy do not | Alternatives: GBP-only; preserve original currencies; convert with approved FX policy. Recommendation: GBP-only baseline. | No for GBP-only synthetic baseline; yes for multi-currency aggregation | subscriptions/snapshots/invoices; DD-009 |
| SB-011 | Multiple and concurrent subscriptions | Product ID/contract ID is not separate; concurrent episodes could be ambiguous | Alternatives: one active episode per customer baseline; separate products/concurrent contracts in optional scenario with authoritative identity assignment. Recommendation: baseline sequential/simple. | Yes before generalizing beyond baseline | subscriptions, all dependent datasets; ADR-009 / DD-EP-001/002 |
| SB-012 | Pause/suspension | Statuses exist but effect on contract, usage, and churn not defined | Alternatives: preserve episode, end episode, or operational suspension without contractual effect. Recommendation: keep out of baseline lifecycle transitions. | Yes before lifecycle claims | subscriptions/snapshots; DD-EP-007 |
| SB-013 | Invoice service period and attribution | Invoice may span terms or episodes; no service-period field | Alternatives: one invoice per episode/period in synthetic ground truth; future allocation policy for multi-episode invoices. Recommendation: baseline one invoice per episode. | Yes before representing real-source invoice semantics | invoices; DD-EP-011 |
| SB-014 | Contract compatibility and implementation state | Strict schema and ingestion behavior may differ from approved workflow decisions | Recommendation: use only current schemas for generated files; separately authorize any implementation/contract alignment. | Yes before claiming the generated interface is accepted by the live pipeline | all five; PD-006, PD-007 |
| SB-015 | Population proportions | Business assumptions could be mistaken for UK benchmarks | Alternatives: vary scenario mixes; no “representative UK” claim. Recommendation: publish parameters and seeds, not market claims. | No, provided labelled and configurable | generator metadata; Phase 3.3.1 |
| SB-016 | Additional seat pricing | Seat counts and price components are not contract fields; charging for seats would change baseline invoice and revenue behaviour | Alternatives: no added baseline charge; optional future per-seat/overage scenario. Recommendation: no additional-seat charges, invoice lines, or proration in baseline; seat changes may affect usage only. | No for baseline; yes before any optional price scenario | plan catalogue metadata, subscriptions, snapshots, invoices |

## 18. Recommendations for Phase 3.3.3 — Synthetic Data Generation Rules

1. Convert the baseline and optional scenarios into explicit generator inputs, with a fixed seed and documented parameter file or equivalent internal configuration. Apply the baseline billing equations exactly: monthly recurring revenue equals the monthly invoice amount; annual invoice amount is monthly list price times 12 times one minus the annual discount rate; annual monthly-normalised recurring revenue is that invoice amount divided by 12.
2. Define generated ground truth separately from the five contract outputs: canonical episode UUIDs, declared source-ID behavior, lifecycle event occurrence, event availability, plan catalogue, seat entitlements, scenario assumptions, and synthetic target outcomes.
3. Generate only valid episode-to-customer, snapshot-to-episode, usage-to-episode, and invoice-to-episode links in the valid population when ground truth establishes the relationship. Keep unresolved identity test cases outside accepted episode-level datasets and without automatic IDs.
4. Define event ordering and point-in-time rules before writing records: occurrence time, availability time, snapshot convention, usage window, invoice dates, and extraction cutoff. Preserve the baseline rule that extra seats do not add charges, and that plan changes update the existing episode without automatically creating a new `subscription_id`.
5. Keep contract-compatible output columns exact; do not insert internal metadata into CSV files or alter schemas without a separate approved contract activity.
6. Separate valid model-development data from deliberately corrupted fixtures. Specify expected validation outcomes for each negative case.
7. Preserve censoring and future outcomes so feature windows and target windows can be tested without leakage.
8. Include scenario-level documentation that all companies, prices, proportions, behaviours, and synthetic labels are fictional; performance on these data is engineering evidence only, not expected real-customer performance.
9. Before implementing generator logic, resolve or explicitly isolate the open decisions necessary for the selected scenarios. Phase 3.3.3 should not implement the Episode Identity Registry, revise the contract, or finalize production churn/CLV policy unless separately authorized.

## 19. Scope and Change Record

This document is a specification only. It does not change Customer Data Contract v1.1, schemas, ADRs, approved product decisions, source code, tests, pipeline behaviour, or identity architecture. It does not generate records or implement a generator. Open decisions remain open even where one proposed synthetic scenario needs a configurable assumption.
