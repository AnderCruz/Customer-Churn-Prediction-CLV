# Synthetic Data Generation Rules

**Document ID:** NCI-SYNTH-RULES-001
**Version:** 0.1
**Status:** Approved for Design Baseline
**Project:** Nowa Customer Intelligence
**Market context:** Great Britain (GB)
**Scope:** Synthetic generation rules only; no generator, configuration, or dataset is implemented here.

## 1. Purpose and authority

This specification defines a coherent, contract-compatible baseline for generating synthetic customers, contractual subscription episodes, lifecycle events, invoices, monthly usage, and monthly snapshots. It is subordinate to explicit approved decisions and must be read with the [Block A architecture](synthetic_data_generation_architecture.md), the approved [Synthetic Business Model Specification v0.2](synthetic_business_model_specification.md), the [Customer Data Contract v1.1](customer_data_contract.md), relevant ADRs, and the [Subscription Episode & Lifecycle Decision Specification v0.4](subscription_episode_lifecycle_decision_specification.md).

The approved business-model document is `docs/04_data/synthetic_business_model_specification.md` (Version 0.2, Approved). The Phase 3.3.1 population specification was not located in the repository; only its stated starting assumptions available in project context are used here: approximately 1,000 accounts, 1,100–1,400 episodes, and 36 months of history. These are configurable engineering assumptions, not GB market estimates. No further Phase 3.3.1 requirements are inferred.

NEDS v1.1 is not in the repository, but the authoritative standard is available in project reference material and has been reviewed. This design follows its requirements for modularity, reproducibility, data quality, reliability, security, testing, technical justification, scope control, and British English. Implementation compliance requires future evidence and review.

Classification labels used below:

- **APPROVED DECISION** — explicitly approved project decision.
- **EXISTING CONTRACT CAPABILITY** — representable in the current contract, without implying semantics beyond the contract.
- **PROPOSED SYNTHETIC ASSUMPTION** — fictional baseline rule for engineering data only.
- **OPEN DECISION** — unresolved product, client, or technical question.
- **NOT SUPPORTED** — not represented by the current contract.

The rules are design-level. All fictional distributions and business relationships require explicit configuration and provenance and must not be presented as observed GB behaviour or as real-world model evidence.

## 2. Governing architecture and population

The Block A modular, single-process orchestration design remains the governing architecture. Generate authoritative internal truth first, then project the five contract datasets. The generator must not infer identity from dates, statuses, row order, or matching heuristics. Internal event history, seeds, labels, source IDs, availability times, and configuration metadata stay outside contract CSVs.

| Population anchor | Baseline rule | Classification |
|---|---|---|
| Customer accounts | Default target around 1,000; configurable positive count. | APPROVED Phase 3.3.1 starting assumption; exact count configurable |
| Episodes | Default target range around 1,100–1,400; configurable count and customer allocation. | APPROVED Phase 3.3.1 starting assumption; exact count configurable |
| History | Approximately 36 months; explicit cutoff and coverage window in run configuration. | APPROVED Phase 3.3.1 starting assumption; exact window configurable |
| Segments and behaviours | Configurable weights and scenario profiles; weights validated and recorded. | PROPOSED SYNTHETIC ASSUMPTION |

The customer and episode count constraints must be jointly satisfiable. Configuration must state how the target episode count is allocated; the implementation must not silently alter targets to satisfy a chosen allocation algorithm.

## 3. Entities, relationships, and identifiers

### 3.1 Entity grains and cardinalities

| Entity | Grain | Relationship and expected cardinality | Contract representation |
|---|---|---|---|
| Customer/account | One row per `customer_id`. | One customer has zero or more generated episode records internally; the current contract requires each included customer to be referenced by at least one subscription. | `customers.csv` |
| Subscription episode | One row per distinct contractual episode and canonical `subscription_id`. | Each episode belongs to exactly one customer; a customer may have multiple sequential episodes. Concurrent episodes are permitted only when separately established in synthetic truth and explicitly enabled. | `subscriptions.csv` |
| Lifecycle/commercial event | One internal event record per event occurrence. | Each episode event belongs to exactly one episode. An account event is not projected as an episode event unless the relationship is explicit. | Internal ground truth only; no event dataset in v1.1 |
| Invoice | One row per invoice identifier. | Each invoice is associated with exactly one episode in the baseline; an episode may have zero or more invoices. | `invoices.csv` (optional) |
| Usage | One row per episode and usage month. | Each usage row references exactly one episode; an episode may have zero or one row per month. | `usage_monthly.csv` (optional) |
| Snapshot | One row per episode and snapshot date. | Each snapshot references exactly one episode; at most one row per episode/date. | `subscription_snapshots.csv` (required for temporal modelling) |

Foreign-key existence is necessary but is not proof of correct semantic attribution. The internal truth must establish which episode owns each invoice, usage aggregate, snapshot, and event. No customer-level usage or invoice is split across episodes by date or proportion without an explicit synthetic fact that establishes allocation.

### 3.2 Customer generation

1. Generate unique, non-empty `customer_id` values as strings. The identifier implementation is an engineering choice; it must not encode segment, plan, or outcome, and IDs must not be treated as predictive features (**APPROVED DECISION**).
2. Generate one customer row per account, with contract-supported fields only: `customer_id`, `created_at`, and optionally `country`, `industry`, `company_size`, and `account_status`.
3. Do not generate direct personal identifiers. Customer attributes and any internal segment labels must be fictional, configured, and captured in run metadata where they are not contract fields.
4. Attribute relationships (for example company size to industry, plan, or adoption profile) must be parameterised conditional rules with documented rationale; avoid deterministic proxies that make one field reveal another or the target.
5. Generate `created_at` no later than the run cutoff and, in this baseline, no later than the first episode start for that account. This is a **PROPOSED SYNTHETIC ASSUMPTION**, not a universal contract rule.
6. The contract requires each included customer to have at least one subscription. Customers without an episode may exist only in internal scenario truth or a future contract revision; do not include orphan customer rows in valid v1.1 population output.
7. Validate primary-key uniqueness, non-null IDs, allowed/configured categories, and the customer-to-episode reference set. Preserve population counts and exclusions in the run manifest.

### 3.3 Episode generation and identity

1. `customer_id` identifies the account; `subscription_id` identifies one individual contractual episode and is the prediction entity (**APPROVED DECISION**).
2. Create episode truth only from an explicit synthetic episode-creation decision. Assign one unique canonical UUID `subscription_id` to it, persist and reuse it for every dependent row, and never reassign it. UUID is approved; UUID version, provider, and deterministic replay mechanism remain **OPEN DECISIONS**.
3. Source-system identifiers, if simulated internally, remain namespaced source metadata and are never used as Nowa canonical IDs. Do not create source-to-canonical resolution behaviour in this specification.
4. An episode has exactly one owning customer. Episode start must not precede the account creation date in this fictional baseline. The episode identity and its history are immutable even when later episodes are created.
5. A plan upgrade/downgrade does not automatically create a new episode in the approved fictional baseline. A confirmed reactivation after a terminated episode creates a new episode with a new UUID and leaves all prior episode truth and dependent records unchanged (**APPROVED DECISION**).
6. Renewal, extension, concurrent contracts, trial boundary, and whether a pause/suspension preserves an episode are not settled universally. Any generated example must be explicitly configured as a fictional scenario and must not be described as approved production semantics.
7. Ambiguous episode identity remains unresolved and excluded from identity-dependent valid outputs. No UUID may be issued/reused for an ambiguous case; no date/status/row-order heuristic may resolve it. Ambiguity examples belong in isolated negative/identity fixtures.
8. Enforce unique `subscription_id`, valid parent `customer_id`, valid chronology, and an explicit identity lineage in internal truth. Keep historical ended episodes in the subscriptions output; do not overwrite them with a later episode's current state.

## 4. Lifecycle and event rules

### 4.1 Status and transition boundary

The contract's proposed controlled subscription statuses are `active`, `trial`, `cancelled`, `expired`, `suspended`, and `paused`. Preserve these spellings; introduce no additional contract statuses. Their contract status is provisional, so scenario use must be documented. An invoice state such as `overdue` or `failed` is not a subscription status and does not itself imply churn.

The project has not approved a universal lifecycle state machine. The following table distinguishes safe scenario rules from unresolved transitions; “valid” means internally coherent under an explicitly selected synthetic scenario, not approved production policy.

| Previous status | Event | New status | Preconditions and timestamp requirements | Validity / identity effect |
|---|---|---|---|---|
| None | Subscription created / episode established | `trial` or `active` | Creation at or after episode start; trial use requires configured trial semantics. | Valid as a configured scenario; establishes one new episode and UUID. Trial semantics are open. |
| `trial` | Trial converted / paid activation | `active` | Conversion follows trial start and is effective at a stated timestamp. | Proposed scenario transition within same episode; no new ID. Billing start policy must be configured. |
| `active` | Plan upgraded/downgraded | `active` | Effective timestamp follows episode start; update plan in subsequent point-in-time states. | Proposed scenario transition; same episode. |
| `active` | Pause | `paused` | Effective timestamp explicitly recorded; service/access consequence configured. | Scenario only; whether pause preserves episode and billing is open. Same ID only in selected baseline scenario. |
| `paused` | Resume | `active` | Resume follows pause; record occurrence and effective times. | Scenario only; same episode if pause preserved it. |
| `active` or `trial` | Suspension | `suspended` | Suspension reason/policy internal; no new contract status. | Scenario only; suspension and billing/episode effects are open. |
| `suspended` | Resume | `active` | Resume follows suspension and follows selected scenario policy. | Scenario only; same ID unless explicit termination and later reactivation truth exists. |
| `active` or `trial` | Cancellation request | unchanged | Request time is distinct from any effective cancellation/termination time. | Event may be generated internally; it does not alone establish state change or churn. |
| `active` or `trial` | Cancellation becomes effective | `cancelled` | Effective time is explicit and follows episode start; map to contract date fields only under configured semantics. | Scenario only; termination qualification and date semantics remain open. No new ID for closure. |
| `active` | Term reaches configured end / expires | `expired` | End time follows episode start; term and non-renewal are explicit scenario truth. | Scenario only; renewal and churn meaning remain open. No new ID for closure. |
| `cancelled` or `expired` | Reactivation after confirmed termination | New episode starts `active` or configured `trial` | New start follows prior episode's established termination; distinct episode truth and UUID. | Valid only when synthetic truth explicitly establishes reactivation; **new ID required**. |
| Any final terminated episode | Later event against same episode | No further lifecycle state | Only administrative correction metadata may follow, and it must not rewrite occurrence history silently. | Invalid for baseline service events; a later service relationship is a new episode. |

Transitions involving cancellation request vs effective cancellation, annual expiry vs renewal, termination date vs final service day, payment-failure suspension, or pause billing are **OPEN DECISIONS** for product/client semantics. Do not infer these from status alone. Payment failure or overdue state may be an invoice event and may be followed by payment, but must not automatically change subscription status, label churn, or terminate an episode.

### 4.2 Internal event representation

Each internal lifecycle/commercial event should have a unique run-scoped `event_id`; `subscription_id` when it is episode-scoped; `event_type`; `occurred_at` (when the event happened); `effective_at` (when its business effect begins, if different); `recorded_at`/availability time where needed for point-in-time reconstruction; configured attributes; and the expected resulting state. These are internal design fields, not additions to the contract.

| Event | Preconditions | State / projection consequence |
|---|---|---|
| Episode created | Customer exists; episode established by synthetic truth. | Creates episode and canonical ID; establishes start. |
| Trial started / converted | Trial policy explicitly selected; conversion follows trial. | Updates internal state; optionally projects `trial` then `active`; paid billing starts only per configured scenario. |
| Activated | Episode exists and activation is supported by scenario truth. | State becomes `active`; no separate episode unless this event establishes a new episode. |
| Plan changed | Episode active under scenario policy; configured plan exists. | Updates plan and future snapshots; billing impact begins only at configured effective billing boundary. |
| Paused/resumed or suspended/resumed | Prior state allows transition; explicit scenario policy and timestamps. | Changes internal state and later snapshots. Billing and usage consequences remain scenario parameters. |
| Cancellation requested | Episode exists; request timestamp recorded. | No automatic state/end-date change; may be withdrawn in truth if that scenario is enabled. |
| Cancelled/expired/terminated | Explicit effective event follows episode start. | Closes the episode under selected synthetic interpretation; does not delete history. |
| Reactivated | Prior episode has established termination; new contractual service is explicitly created. | New episode and new `subscription_id`; old history unchanged. |
| Invoice issued/paid/failed/refunded | Invoice and episode relationship established in truth. | Changes invoice/payment facts only; no automatic episode transition. |

`occurred_at` and `effective_at` must not be conflated. Their ordering is event-specific and must be defined by the selected scenario; this design does not assume one always precedes the other. Sort/replay state changes by effective time while retaining occurrence and availability times. If equal-time events conflict, configuration must specify a stable precedence or reject the scenario; row order must not decide the result.

### 4.3 Temporal consistency and reconstruction

- No event may occur before its owning episode is created. Validate occurrence/effective-time relationships using event-specific scenario rules; do not collapse the two timestamps into one or impose a universal ordering.
- For each episode, event sequence must be replayable to one unambiguous state at any supported timestamp. Reject duplicate/conflicting transitions, impossible source states, and events after final termination, except non-state-changing administrative metadata clearly marked as such.
- Episode start/end/cancellation fields must satisfy current contract checks (end and cancellation do not precede start). This does not settle their business meaning or establish actual termination semantics.
- State intervals must not overlap inconsistently within one episode. A later reactivation after termination belongs to a new episode, not a reopened interval under the old ID.
- For any historical snapshot or feature view at cutoff `t`, include only facts whose effective time and availability time satisfy the declared point-in-time policy. Preserve late-arriving event knowledge separately; do not backdate what was known at `t`.
- Contract validation, referential integrity, semantic episode attribution, temporal correctness, and model eligibility are separate controls. A passing contract or key check does not establish the other properties.

## 5. Billing, invoices, and revenue

### 5.1 Baseline commercial terms

Use the approved fictional Fieldwise Cloud Ltd catalogue. Prices are synthetic assumptions, not market evidence.

| Plan | Monthly list price | Annual prepayment (10% discount) | Monthly-normalised annual `recurring_revenue` |
|---|---:|---:|---:|
| `launch` | GBP 79.00 | GBP 853.20 | GBP 71.10 |
| `growth` | GBP 249.00 | GBP 2,689.20 | GBP 224.10 |
| `scale` | GBP 699.00 | GBP 7,549.20 | GBP 629.10 |
| `enterprise` | GBP 1,800.00 | GBP 19,440.00 | GBP 1,620.00 |

Baseline billing is monthly in advance or annual in advance. Annual invoice amount is monthly list price × 12 × (1 − 0.10); monthly-normalised `recurring_revenue` is annual invoice amount / 12. Monthly billing `recurring_revenue` equals monthly invoice amount. Store full annual amount in `invoices.amount`, and monthly-normalised value in subscription and applicable snapshot rows. Round currency amounts to two decimal places using one documented decimal arithmetic/rounding policy; plan figures above are exact to pennies.

Additional-seat charges, overage, proration, multi-currency conversion, taxes, invoice service-period fields, payment attempt history, and refund amount/allocation are excluded or unsupported. Seats may influence usage but not baseline invoice amount or recurring revenue. A plan change is within the same episode in the baseline; it affects the next invoice from the configured next billing boundary, without proration. These are fictional rules, not production policy.

### 5.2 Invoice generation

Each contract invoice row contains only `invoice_id`, canonical `subscription_id`, `invoice_date`, optional `due_date`, optional `paid_date`, `amount`, `currency`, and `invoice_status`. Generate a unique non-empty string `invoice_id`; it is not a subscription identifier. Link to one episode only from internal ground truth. Generate monthly/annual invoices in advance according to the episode's configured cadence, beginning at its configured billing-cycle anchor. Because the contract has no service-period fields, retain billing period start/end internally and do not encode them in extra CSV columns.

| Scenario | Invoice/status rule | Episode effect |
|---|---|---|
| Monthly successful payment | One monthly invoice at monthly amount; `paid`, paid date on/after issue date. | None. |
| Annual successful payment | One annual invoice at full discounted annual amount; `paid`, paid date on/after issue date. | None. |
| Payment pending | `pending`; no paid date until settlement is represented. | None. |
| Payment failure | `failed`; no paid date unless later successful settlement is modelled as a subsequent state under supported row semantics. | No automatic cancellation, churn, suspension, or termination. |
| Overdue | `overdue` only when due date has passed without recorded settlement under the scenario's knowledge cutoff. | None by itself. |
| Subsequent success | An invoice ultimately paid may be represented as `paid` with settlement date; if interim status history is needed, it stays in internal events because the contract has one invoice row and no status history. | None. |
| Cancellation with outstanding invoice | Preserve invoice and its status; do not erase or assume it is void. | No automatic episode/payment inference. |
| Plan change | New invoice amount from next configured billing date; no proration. | Same episode. |
| Void/refund | Contract status categories allow `void`/`refunded`, but reversal timing and amount are not represented. Generate only if the chosen scenario explicitly supports a full-status case; do not calculate net cash/refund. | None. |

Contract categories `paid`, `pending`, `overdue`, `failed`, `void`, and `refunded` are proposed controlled values in v1.1. Validate uniqueness of invoice IDs, existing episode FK, non-negative amount, ISO currency (`GBP` in baseline), due date not before issue, and paid date not before issue. Do not infer invoice ownership from date overlap. If a retry and eventual settlement cannot be represented without contradicting the one-row-per-invoice shape, keep the detailed attempts internal and make the limitation explicit.

### 5.3 Revenue and CLV boundaries

Keep these concepts distinct:

- **Invoice amount:** amount billed on one invoice, stored as `invoices.amount`; annual prepayment retains the full annual amount.
- **Recurring revenue:** fictional scenario's monthly-normalised recurring amount in subscriptions/snapshots. The approved business specification defines the above synthetic calculation, not production semantics.
- **Cash collected:** actual settlement amount/time. `paid_date` and full invoice amount can approximate this only for a simple fully paid scenario; partial payment and transaction amounts are not represented.
- **Recognised revenue:** accounting allocation over service period; not supported because service periods and accounting policy are absent.
- **Refunds/credits:** status alone does not provide amount, date, partial/full treatment, or allocation; net cash/revenue is unresolved.
- **CLV:** no CLV formula, margin, horizon, discount rate, episode aggregation, or refund treatment is approved. Preserve invoice and recurring-revenue facts for future work without deriving or naming a value as official CLV.

## 6. Usage and snapshots

### 6.1 Usage generation

Usage grain is one row per canonical episode and `usage_month`, with supported fields `active_users`, `total_users`, `sessions_count`, `events_count`, `usage_volume`, and `usage_metric`. The period's date convention and exact coverage boundaries remain **OPEN DECISIONS**. Require a single configured convention consistently within a run; do not imply the current contract has settled calendar-month boundaries. Use `usage_metric` to name the unit when `usage_volume` is generated; the Fieldwise business spec proposes completed workflow items as one optional scenario metric, not a universal definition.

Profiles are configurable hypotheses, not market segments or approved churn drivers:

| Profile | Example synthetic pattern |
|---|---|
| Low adoption | Lower active/total user ratio and low sessions/events/volume within non-negative configured ranges. |
| Moderate adoption | Mixed user activity and moderate, variable workflow activity. |
| High adoption | Higher active/total user ratio and stable or growing activity within configured limits. |
| Stable | Values fluctuate within configured bounds. |
| Growing or declining | Multi-period trend with bounded variation, not a deterministic churn label. |
| Sudden reduction | Explicitly configured step change at a chosen month. |
| Irregular/seasonal | Variation tied to a declared synthetic scenario calendar. |

Plan and seat assumptions may affect allowed scale or profile parameters. The included seat counts (Launch 5, Growth 20, Scale 75, Enterprise 250) are internal fictional catalogue metadata; the contract has no seat count. Enforce non-negative integer counts, `active_users <= total_users` when both exist, non-negative usage volume, one row per episode/month, and valid episode attribution. An episode-period row may be absent when usage is not generated; absence must not be interpreted automatically as zero activity.

Lifecycle effects on usage are scenario-controlled. Trial usage may be low or ramping; active usage follows its selected profile; pause/suspension may be zero, reduced, or absent only if explicitly configured; cancellation/expiration may have no post-effective-period usage unless the scenario defines a documented lag. These are **PROPOSED SYNTHETIC ASSUMPTIONS**. No usage pattern creates a lifecycle transition or churn label.

Usage aggregates must not include events unavailable at the historical prediction timestamp. Since the contract lacks usage availability timestamps, retain period coverage and availability internally and state the cutoff policy in the run manifest. Do not claim temporal correctness solely from a valid `usage_month`.

### 6.2 Subscription snapshots

Snapshot grain is one row per `subscription_id` and `snapshot_date`, with status and optional recurring revenue, currency, plan, billing frequency, and auto-renew fields. Generate snapshots only for an explicitly selected temporal workflow; the dataset is optional for basic ingestion and required for workflows claiming temporal modelling (approved PD-006). A temporal population must follow the contract's historical observation and cutoff requirements.

The first-day versus last-day-of-month convention is unresolved in both the contract and approved specifications. Therefore:

1. Treat the date convention as a mandatory configuration/approval input before implementation. Do not choose or describe one as approved here.
2. Once selected, apply it uniformly, emit at most one row per episode/date, and record it in manifest metadata.
3. Derive state as of the snapshot date using only events effective and available under the declared point-in-time policy. Reflect plan, recurring-revenue, billing, and status changes only from their configured effective point.
4. Do not create snapshots before episode start or after the extraction cutoff. Whether to include a final snapshot on the termination date is unresolved and must be explicit.
5. Keep episode history immutable. Reactivation has its own new ID and snapshot series; never overwrite prior rows.
6. Check status against the contract's accepted categories and validate composite-key uniqueness, FK existence, non-negative revenue, and consistent currency/frequency values.

Snapshot status is the state at the observation date, not a retrospective copy of the current subscription master. The current subscriptions row represents the final/current synthetic master projection and must not be substituted for historical states. Availability/cutoff correctness requires internal event truth and is separate from schema validation and referential integrity.

## 7. Valid outputs, integrity, and exclusions

Valid population output consists only of contract-shaped datasets with exact v1.1 headers. `customers.csv` and `subscriptions.csv` are required. `subscription_snapshots.csv` is included for temporal modelling; `usage_monthly.csv` and `invoices.csv` are optional according to the selected scenario. If a selected workflow requires a dataset, a missing file is a failed run, not an implicit empty dataset. Negative fixtures are separately generated, clearly labelled, and never included in valid population or training output.

Before a run can be marked valid, the design requires the following independent gates:

1. **Contract validation:** field names, types, categories, requiredness, row constraints, and serialization conventions.
2. **Referential integrity:** child keys exist in the declared parent dataset.
3. **Semantic episode attribution:** truth establishes each invoice, usage row, snapshot, and event belongs to that specific episode.
4. **Temporal correctness:** event order, effective and availability times, episode intervals, monthly coverage, and cutoff are coherent.
5. **Model eligibility:** prediction entity, target hypothesis, observation window, horizon, feature availability, censoring, and leakage gates are explicitly configured. This is not implied by passing the first four.

Failure of a required stage or gate prevents valid publication. Preserve stage/error information in the run report without publishing partial output as valid. Keep ground truth access-controlled and separate from contract outputs; logs must not disclose raw truth or secrets.

## 8. Structured decision register

Statuses describe this design's decision state: **Approved** records a decision approved in an authoritative project artefact; **Proposed** is a baseline design proposal not yet approved; **Open** requires a product, client, or technical decision; **Blocked** means the named implementation scope cannot safely proceed until its dependency is decided. An Open decision is not converted into Approved by its inclusion here.

| Decision ID | Topic | Proposed rule or existing decision | Status | Rationale | Dependencies | Implementation impact |
|---|---|---|---|---|---|---|
| BDR-001 | Prediction entity and identifiers | `customer_id` identifies an account; canonical UUID `subscription_id` identifies one contractual episode, is persisted/reused, and is never reassigned. | Approved | Preserves episode-level prediction grain and historical identity. | ADR-010; approved identity/product decisions. | Dependent rows must carry the canonical episode ID. |
| BDR-002 | Reactivation and history | Confirmed reactivation after termination creates a new episode and UUID; earlier episode and dependent history remain. | Approved | Prevents identity reuse and preserves episode history. | Authoritative synthetic truth for termination/reactivation. | Generate a distinct episode; never reopen/overwrite prior identity. |
| BDR-003 | Ambiguous identity | Leave ambiguous identity unresolved; do not issue/reuse an ID or apply heuristics. | Approved | Follows approved identity safeguards. | Isolated negative/identity fixture path. | Exclude unresolved records from identity-dependent valid output. |
| BDR-004 | Business catalogue and revenue baseline | Use the approved Fieldwise plans/prices, GBP baseline, 10% annual discount, full annual invoice amount, monthly-normalised annual `recurring_revenue`, no baseline seat charges, overage, proration, or FX conversion. | Approved | Preserves Synthetic Business Model Specification v0.2 assumptions. | Approved v0.2; selected billing scenario. | Do not alter catalogue or treat the fictional definition as production semantics. |
| BDR-005 | Architecture and contract boundary | Use Block A's modular, single-process design; project only contract fields and keep event history/metadata separate. | Approved | Maintains the previously established architecture and contract. | Block A; Customer Data Contract v1.1. | No new service, contract field, or event dataset is introduced here. |
| BDR-006 | Customer/episode population | Use configurable starting assumptions of approximately 1,000 customers, 1,100–1,400 episodes, and 36 months; configurable segment and behaviour profiles. | Approved | These are the approved Phase 3.3.1 starting assumptions, not market estimates; its specification was not located in-repository. | Population/configuration choices; exact values remain run parameters. | Configuration must define exact counts, allocation, weights, and window before a run. |
| BDR-007 | Customer attribute relationships | Generate only contract-supported customer fields; use explicit configurable fictional relationships and no direct personal identifiers. | Proposed | Supports useful varied data without implying market truth or leakage. | Scenario parameter specification. | Validate categories and prevent identifiers/attributes from encoding target. |
| BDR-008 | Lifecycle transition catalogue | Use only contract status categories; individual transitions are scenario-specific where defined. Payment failure/overdue alone does not cause churn or termination. | Proposed | Contract statuses are provisional; no universal state machine is approved. | Episode boundary, cancellation, pause, suspension, renewal and trial decisions. | Implement only explicitly configured transitions; unresolved transitions remain disabled or isolated. |
| BDR-009 | Event time representation | Keep occurrence, effective, and availability/recorded times distinct in internal truth; apply event-specific ordering rules. | Proposed | Historical replay and point-in-time use require separate business effect and system knowledge. | Event definitions and temporal policy. | Internal metadata required; no contract columns added. |
| BDR-010 | Snapshot date convention | First-day versus last-day convention and final termination-date inclusion remain undecided. | Open | Contract and approved specifications do not select a convention. | Snapshot semantics; extraction cutoff; model observation cutoff. | Temporal snapshot generation and validation cannot be finalised until selected. |
| BDR-011 | Usage period boundaries | Calendar-month versus billing-period boundaries, partial periods, and cross-episode handling remain undecided. | Open | The contract gives a monthly grain but not period semantics. | Usage `usage_month`; billing period; episode interval; availability cutoff. | Usage generation may use provisional internal profiles, but contract output semantics are blocked pending selection. |
| BDR-012 | Billing period and cycle anchor | Monthly/annual advance cadence is approved as fictional business assumption; exact anchor, inclusive boundaries, proration, and termination handling are not approved beyond baseline exclusions. | Open | The business model does not establish all period boundary and lifecycle interactions. | Episode start, plan effective time, billing frequency, cutoff. | Invoice schedule and plan-change invoice timing need explicit scenario configuration. |
| BDR-013 | UUID version/provider and replay | UUID is approved; UUID version/provider and exact repeatability/replay mechanism remain unresolved. | Open | ADR-010 does not select the implementation mechanism. | Identity provider; seed/replay expectations; persistence model. | Episode ID implementation and exact end-to-end deterministic replay are blocked pending choice. |
| BDR-014 | Episode boundaries and status semantics | Trial-as-episode, cancellation request/effective date/last service day, renewal/extension, pause/suspension, and termination evidence remain open. | Open | Existing fields/statuses do not establish these business meanings. | Product/client policy and lifecycle decision record. | Do not infer episode boundaries or map timestamps/statuses without an explicit decision. |
| BDR-015 | Extraction and model observation cutoffs | Run extraction cutoff is configured, but the relationship to prediction-time observation cutoff and feature eligibility must be defined for a modelling scenario. | Open | Data availability and evaluation cutoffs govern historical evidence and leakage. | Snapshot, usage, event availability and target horizon decisions. | Model-ready historical examples cannot be certified until cutoffs are explicit. |
| BDR-016 | Production target and model eligibility | No production churn definition, label, horizon, observation window, or complete eligibility policy is approved. | Open | Synthetic hypotheses are not production labels. | Product decision; event/temporal semantics; censoring and feature policy. | Production model eligibility is blocked; a synthetic-only hypothesis must be separately labelled. |
| BDR-017 | Production revenue, recognition, refunds, FX and CLV | Production `recurring_revenue`, accounting recognition, refund/credit allocation, FX policy, and official CLV remain unresolved. | Open | Contract fields do not encode required accounting and payment details. | Business/accounting policy and possible contract changes. | Only approved fictional invoice/revenue facts may be generated; no official CLV. |
| BDR-018 | Missing temporal fields in contract | Event history, billing service periods, seat counts, payment attempts/refund amounts, and event/usage availability times are not contract columns. | Approved | Preserve Customer Data Contract v1.1 and limit this activity to design. | Any future contract revision requires its own approval. | Keep these facts internally; do not add columns or claim they are directly observable from CSVs. |

Implementation must surface dependencies for the selected scope and must not silently turn Proposed, Open, or Blocked items into approved policy.

## 9. Temporal dependency matrix

The temporal decisions below remain open where stated in the register. “Can proceed independently” means work can proceed without claiming a complete temporal or model-ready output.

| Temporal dependency | Affected component | Required decision | Consequence if unresolved | Can implementation proceed independently? |
|---|---|---|---|---|
| Snapshot date convention | Snapshot projection; historical state validation | Select first/last day or another explicit observation-date rule; define treatment at episode start/end. | Snapshot state meaning and point-in-time assertions are ambiguous. | Snapshot schema projection can be prototyped; valid temporal snapshot generation cannot be completed. |
| Usage period boundaries | Usage projection; feature aggregation | Define calendar/billing period, `usage_month` encoding, partial periods, and cross-episode policy. | Counts may include different intervals or activity from outside the episode; feature timestamps cannot be certified. | Profile/distribution logic can be developed over abstract periods; contract-ready usage output is blocked. |
| Billing period boundaries | Invoice schedule; recurring-revenue changes | Define cycle anchor, interval boundaries, due-date rule, and how plan changes/cancellation interact with billing periods. | Invoice dates/amounts cannot be assigned consistently to service intervals; contract cannot carry service periods. | Catalogue arithmetic and invoice serializer can proceed; complete schedule requires configured boundaries. |
| Event effective timestamps | Event generation/replay; status, plan, billing and snapshot projections | Define event-specific effective-time semantics and transition precedence, including cancellation/termination distinctions. | Reconstructed historical state and interval validation can disagree. | Event data structures can proceed; lifecycle state replay for unresolved event types is blocked. |
| Event availability timestamps | Event ingestion/truth; historical feature and snapshot generation | Define when each event becomes known to the system, including late-arriving or corrected events. | Backdated business events may leak into historically unavailable information. | Store separate internal availability metadata; point-in-time historical certification is blocked without a policy. |
| Extraction cutoff | Run context; invoices, usage, snapshots, event censoring | Configure a fixed run cutoff and whether facts after it are excluded or retained only as outcome truth. | Coverage, censored episodes, and “current” master state are not reproducible. | Generator structure can proceed; output coverage and censoring cannot be certified. |
| Model observation cutoff | Feature generation; labels and model eligibility | Define observation timestamp/window, prediction horizon, and relation to extraction cutoff and label availability. | Leakage, incomplete outcomes, and eligible examples cannot be determined. | Synthetic raw populations can be generated; model-eligible training examples are blocked. |

These decisions interact. In particular, a snapshot/usage period may extend beyond a model observation cutoff or extraction cutoff; a business event can be effective before it is available; and billing schedule boundaries can differ from calendar-month usage/snapshot boundaries. No boundary is inferred from another merely because both are monthly.

## 10. Historical state and information availability

For an event with business effective time `e` and system availability time `a`, distinguish:

- **Business state at timestamp `t`:** the state whose events have become effective by `t` (`e <= t`) under the selected lifecycle rules.
- **Information available to the system at timestamp `t`:** only facts the system had received/recorded by `t` (`a <= t`).

These are different views when an event arrives late or is recorded retrospectively. Internal ground truth should preserve occurrence, effective, and availability/recorded timestamps separately. It may support both retrospective truth and as-known-at-the-time reconstruction, but the chosen view must be explicit for each output purpose.

| Use | Required treatment |
|---|---|
| Event replay | Replay state transitions by effective time with deterministic event precedence. For an as-known-at-`t` reconstruction, first exclude facts unavailable at `t`; do not let a later-recorded backdated event change what the system could have known then. Retain later corrections as later-available knowledge. |
| Historical snapshots | State reflects the selected business state at the snapshot date, constrained by the snapshot's declared information-availability policy. A retrospective “corrected truth” snapshot and an as-known-at-that-date snapshot are not interchangeable; the snapshot convention/availability policy remains open. |
| Usage aggregation | Aggregate only events belonging to the relevant episode and period. For historical feature use, include only activity and aggregates available by the observation cutoff. A completed month that ends after the cutoff is not available in full at that earlier time. |
| Feature generation | Apply both effective-time and availability-time filters at each observation timestamp. Current subscription master fields must not be copied back into historical features. |
| Leakage prevention | Exclude facts effective after the observation date and facts that became available after it, even if their effective dates were backdated. Do not use post-cutoff payments, cancellations, usage or corrections as prior features. Label/outcome truth may use later information only in the separately defined target window. |

Availability and period metadata remain internal to the run/ground-truth artifacts and manifest. No additional Customer Data Contract columns are introduced. Because the contract does not carry these timestamps, contract validation alone cannot certify point-in-time correctness.

## 11. Implementation readiness assessment

Classification applies to the scope described here, not to production use or the whole Nowa product. “Ready with approved configuration” means the rules are sufficiently specified once a run supplies permitted values and does not resolve a policy decision.

| Component | Readiness classification | Reason / condition |
|---|---|---|
| Customer generation | Ready with approved configuration | Contract fields and population starting assumptions are known; exact counts, weights, cutoff, and fictional attribute relationships must be supplied in validated configuration. |
| Episode identity generation | Blocked by open decision | UUID strategy is approved, but UUID version/provider/replay behaviour is unresolved; Registry implementation remains outside scope. Synthetic episode ownership can be designed, but canonical ID implementation must await that decision. |
| Lifecycle events | Blocked by open decision | Event representation is defined, but episode boundaries, cancellation/termination mapping, renewal, trial, pause/suspension, and transition semantics remain open. A narrower explicitly configured scenario may be designed without asserting universal policy. |
| Billing | Ready with approved configuration | Plan catalogue, fictional monthly/annual prices and revenue arithmetic are established; billing-cycle anchor and effects of unresolved lifecycle transitions must be supplied or excluded per scenario. |
| Invoice generation | Ready with approved configuration | Contract fields, statuses, key/amount/date checks, and baseline scenarios are described; due-date/payment patterns and billing boundaries require selected configuration. Detailed retry/refund history is unsupported. |
| Usage | Blocked by open decision | Supported measures and configurable profiles are known, but usage period boundaries, partial-period handling, cross-episode policy, and availability semantics are unresolved. |
| Snapshots | Blocked by open decision | Contract grain and temporal purpose are known, but date convention, termination-date inclusion, and as-known versus retrospective availability policy are unresolved. |
| Contract projection | Ready for implementation | Contract v1.1 defines supported fields, grains, keys, and CSV boundary; this component must not invent columns or imply upstream temporal/semantic validation. |
| Temporal validation | Blocked by open decision | Validation depends on event effective/available time policies, snapshot and usage boundaries, extraction cutoff, and observation cutoff, several of which remain open. Existing schema/key checks are insufficient. |
| Model eligibility | Out of scope | This Block B design does not approve a production target, horizon, observation window, censoring policy, or feature eligibility. Model-ready examples require those separate decisions; synthetic data generation does not imply eligibility. |

## 12. NEDS v1.1 alignment

NEDS v1.1 was reviewed from authoritative project reference material. This matrix assesses design alignment only; it does not claim implementation or operational compliance.

| NEDS requirement | Design evidence in this specification | Future evidence / remaining consideration |
|---|---|---|
| Modularity and maintainability | Retains Block A's small modular, single-process architecture and separates truth, events, projections, and contract output. | Keep component interfaces and responsibilities clear; avoid unjustified infrastructure. |
| Reproducibility | Requires configured population/scenarios, explicit time cutoffs, internal event lineage, and provenance; UUID replay is identified as unresolved. | Version configuration/code/dependencies and demonstrate repeatability after UUID decision. |
| Data quality and management | Defines grain, keys, cardinalities, temporal constraints, contract checks, and separate semantic attribution/model gates. | Implement and execute the distinct checks; schema and RI results alone do not prove semantic or temporal validity. |
| Error handling and reliability | Section 7 prevents failed required gates from producing valid output; Block A defines stop-on-failure and failure reporting. | Implement stage failure behaviour and ensure partial outputs are not marked valid. |
| Logging | Block A requires run/stage outcomes, counts, durations, and failure categories without raw truth or secrets. | Select and retain operational logs without sensitive payloads. |
| Security and data protection | Separates internal ground truth from contract outputs and requires access control and no direct personal identifiers. | Apply least privilege, environment-appropriate permissions, and retention/cleanup controls. |
| Testability and testing | Rules define independently testable invariants and separate contract, RI, attribution, temporal, and eligibility gates; Block A assigns unit/integration/end-to-end responsibilities. | Implement and execute applicable tests before production readiness; no tests are created here. |
| British English and documentation accuracy | This is a versioned design with explicit classifications, limitations, and implementation boundary. | Keep future documentation/code comments in British English and update claims to match actual implementation. |
| Decision traceability and technical justification | Structured register records IDs, status, rationale, dependencies, and impact; approved vs proposed/open states remain distinct. | Link implementation choices and justified exceptions to decisions; obtain approval for open policy decisions. |

## 13. Traceability

This draft covers Block B Activities 3.3.3.3–3.3.3.6. It is based on the approved v0.2 business model, Customer Data Contract v1.1, relevant approved identity/product decisions, lifecycle decision specification, Block A design, NEDS v1.1 project reference, and the limited Phase 3.3.1 assumptions stated in project context. The supplied Block B text ends during the usage requirements; this document addresses the listed generation scope and records unresolved matters explicitly. No code, configuration, schemas, tests, datasets, ADRs, or contract changes are made.
