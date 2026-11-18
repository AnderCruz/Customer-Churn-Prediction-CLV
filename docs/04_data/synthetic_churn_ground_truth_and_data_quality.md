# Synthetic Churn Ground Truth and Data Quality

**Document ID:** NCI-SYNTH-QUALITY-001
**Version:** 0.1
**Status:** Approved for Design Baseline
**Project:** Nowa Customer Intelligence
**Market:** Great Britain (GB)
**Scope:** Design for synthetic outcome truth, censoring, data quality, and negative test scenarios. No implementation is authorised here.

## 1. Purpose, scope, and authority

This document specifies Activities 3.3.3.7 and 3.3.3.8. It defines synthetic episode-level outcome hypotheses, point-in-time observations, censoring, eligibility, data quality controls, negative fixtures, failure behaviour, and future test responsibilities. It does not approve a production churn definition, survival-analysis architecture, model feature set, label policy, or Customer Data Contract change.

The reviewed Block B technical content in [Synthetic Data Generation Rules v0.1](synthetic_data_generation_rules.md) is treated as the governing Block B design as instructed. Its document-control status is Approved for Design Baseline. Block A's modular single-process architecture and contract boundary remain in force.

### 1.1 References reviewed

| Reference | Location / status | Use in this design |
|---|---|---|
| Block A — Synthetic Data Generation Architecture v0.1 | `docs/04_data/synthetic_data_generation_architecture.md`; Approved for Design Baseline | Single-process orchestration, separate ground truth, named stages, valid/negative isolation, pipeline boundary, failure/reporting design. |
| Block B — Synthetic Data Generation Rules v0.1 | `docs/04_data/synthetic_data_generation_rules.md`; Approved for Design Baseline | Episode, lifecycle, billing, usage, snapshot, temporal dependencies, readiness and decision register. |
| Synthetic Business Model Specification v0.2 | `docs/04_data/synthetic_business_model_specification.md`; Approved | Fictional catalogue and commercial assumptions only; no production market claims. |
| Customer Data Contract v1.1 | `docs/04_data/customer_data_contract.md`; Approved for Implementation | Supported fields, dataset grain, statuses, validation requirements and provisional churn context. |
| Subscription Episode & Lifecycle Decision Specification v0.4 | `docs/04_data/subscription_episode_lifecycle_decision_specification.md` | Approved identity principles and unresolved episode/lifecycle semantics. |
| ADR-009 and ADR-010 | `docs/03_architecture/architecture_decisions.md`; `docs/03_architecture/adr_episode_identity_and_identifier_management.md`; Accepted | Episode-level prediction, identity, reactivation, preservation, and identifier boundaries. |
| Approved product decisions | `docs/04_data/product_decision_proposals.md`; approved, implementation not authorised | PD-001–PD-007 constraints, including ambiguity handling and snapshot workflow policy. |
| Phase 3.3.1 Synthetic Data Requirements and Population Specification | Supplied project reference attachment; not stored in the repository | Population and analytical requirements were reviewed; they do not settle production label or temporal policy. |
| NEDS v1.1 | Authoritative project reference material; not stored in the repository | Engineering and documentation alignment; this is a design assessment, not implementation compliance. |
| Data Quality Specification v0.2 | `docs/04_data/data_quality_specification.md` | Rule intent, severity, runtime status, and decision limitations. |
| Data Quality Implementation Architecture v0.2 | `docs/04_data/data_quality_implementation_architecture.md` | Intended DQ boundaries; some implementation-status statements conflict with current source. |
| Pipeline orchestration and execution specifications | `docs/03_architecture/pipeline_orchestration_specification.md`; `docs/03_architecture/pipeline_execution_summary_specification.md` | Workflow dependencies, stage outcomes, and validation boundaries. |

**Phase 3.3.1 source limitation:** The specification was found and read from the supplied reference attachment, but no repository copy was located. Its population assumptions already carried into Block A/B are approximately 1,000 accounts, 1,100–1,400 episodes, and 36 months; they remain configurable engineering assumptions rather than GB estimates. No further population distribution or churn rate is inferred from unavailable repository artefacts.

**As-built documentation discrepancy:** The DQ implementation architecture says report assembly, coordination and pipeline integration are unimplemented, while the inspected current source includes `pipeline/quality.py`, `data/validation/reporting.py`, `data/validation/validator.py`, and `pipeline/execution.py`. This specification reports capabilities from source and integration tests, and does not modify the separate stale document.

## 2. Ground-truth architecture

The four layers are related but must not be collapsed. Ground truth is not automatically a model feature, and a valid contract CSV is not sufficient evidence for a correct target.

| Layer | Meaning | Contents / boundary |
|---|---|---|
| 1 — Synthetic Business Reality | Complete generated business history, as represented by the simulation. | Customer and episode identity; lifecycle/commercial events; occurrence, effective and availability timestamps; billing/payment and usage history; confirmed synthetic episode termination facts. Internal, run-scoped, access-controlled; not a contract dataset. |
| 2 — Observable Historical Information | Facts that could have been known at a particular observation timestamp `t`. | Point-in-time view of business events and attributes using both effective time and availability time. Used to construct features; excludes later-arriving information even if backdated. |
| 3 — Synthetic Outcome Truth | Outcome under one explicitly identified synthetic target policy. | Qualifying event, effective event time, evidence, outcome ascertainment time, policy identifier/version, and follow-up endpoint. Internal states include positive, negative, right-censored, `pending_ascertainment`, and ineligible; pending is not a binary label. Separate from features and production churn semantics. |
| 4 — Model-Eligible Labelled Observations | Observation rows satisfying target, identity, follow-up, censoring, ascertainment, and feature-availability gates. | Observation-level eligibility and label state; only eligible positive/negative feature views and targets may be passed to a future binary modelling process. Requires separate approval/configuration; not currently implemented. |

Layer 1 describes what the simulation generated; Layer 2 describes what an actor could know then; Layer 3 applies a declared target hypothesis; Layer 4 determines whether the observation is usable for a particular modelling/evaluation purpose. For example, a termination may be true in Layer 1, unavailable at `t` in Layer 2, positive under a later-ascertained Layer 3 policy, and still ineligible for a feature snapshot at `t`. Do not expose internal target, censoring, eligibility, or generator flags as contract features.

## 3. Synthetic churn hypothesis

### 3.1 Proposed hypothesis and event qualification

The following is a **PROPOSED SYNTHETIC ASSUMPTION**, not an approved production churn definition:

> For a known canonical episode, a synthetic qualifying churn outcome may be assigned when internal business truth contains a confirmed episode-termination event whose effective time falls within the configured prediction horizon and the declared target policy accepts that event type.

For this hypothesis, a qualifying event must have, at minimum:

1. An unambiguous canonical `subscription_id` attached to one known episode and customer.
2. A unique internal event identity and explicit event type denoting confirmed termination (not merely request, status text, or payment state).
3. A recorded effective timestamp, distinct from occurrence/recorded/availability time.
4. Synthetic authoritative evidence in the generated episode truth that the episode ended, with policy identifier/version and provenance.
5. No unresolved contradiction about identity, event timing, reversal, or episode ownership.
6. An outcome ascertainment cutoff by which the evidence is available to the label-construction process.

Invoice status, absent usage, subscription status alone, or date proximity does not meet this evidence threshold. The contract fields `end_date`, `cancellation_date`, and `subscription_status` are not interchangeable proof of contractual termination. A synthetic scenario may generate an effective termination event, but the rule and its limitations must be explicit in run metadata.

| Event/concept | Synthetic target treatment | Decision status / limitation |
|---|---|---|
| Cancellation requested | Does not qualify on request alone. A request may be withdrawn or have a later effective date. | Open event semantics; not a positive label by itself. |
| Cancellation effective | May qualify only when synthetic truth establishes confirmed episode termination and the selected policy accepts it. | Proposed event candidate; production date/meaning remains open. |
| Subscription expiration | Does not automatically qualify. Expiration and non-renewal may have different meanings and renewal evidence is absent from the contract. | Policy-dependent. |
| Confirmed episode termination | Candidate qualifying event for the proposed synthetic effective-end hypothesis, with evidence and effective time. | Proposed synthetic assumption only. |
| Trial conversion failure | Does not automatically qualify; trial-as-episode and failure semantics are unsettled. | Open/policy-dependent. |
| Pause or suspension | Not churn by itself; may interrupt service without ending the contractual episode. | Open lifecycle semantics; not a positive label by default. |
| Payment failure or overdue invoice | Not churn by itself; payment status is not contractual termination. | Explicitly excluded as an automatic churn event. |
| Reactivation | A confirmed post-termination service relationship is a new episode with a new canonical ID. It does not erase the earlier episode's outcome. | New episode identity is approved; event evidence and timing remain open. |

### 3.2 Observation windows and prediction horizon

For one episode and observation:

- `t` — observation timestamp, inclusive endpoint for feature availability.
- `W` — configured historical feature-window length; the feature interval is `[t-W, t]`, subject to each feature's own period coverage and availability.
- `H` — prediction-horizon length; the outcome interval is `(t, t+H]`. An event effective at `t` is not a future event for this observation.
- `E` — run extraction cutoff, the latest time included in the extracted/generated data package.
- `A` — outcome ascertainment cutoff: the label process's cutoff for deciding which event evidence has been received and adjudicated. `A` is not the event effective time, observation timestamp, or follow-up endpoint.
- `C` — endpoint on the business/follow-up time axis through which outcome history is known to be complete for this episode/observation. `C` is not automatically equal to extraction cutoff `E` or ascertainment cutoff `A`; completeness through `C` must be evidenced, not inferred from calendar coverage.
- `T` — effective time of a confirmed qualifying event, if one exists.
- `V` — event availability timestamp: when the event evidence became available to the label/feature system. For a confirmed positive at cutoff `A`, `V <= A` and the evidence must have been adjudicated as qualifying.

The contract's initial `90 days` observation-window and `30 days` horizon are provisional engineering examples only. They are not approved production parameters. A scenario must configure `W`, `H`, time zone/date precision, `E`, `A`, the rule for establishing `C`, and outcome ascertainment policy before labelled observations are built. Validate `W > 0`, `H > 0`, cutoffs are ordered under the selected convention, and no observation is beyond available feature history. Calendar/file coverage alone does not prove that event outcomes are complete or ascertained. Keep these values and policy version in the internal manifest, not contract CSV columns.

The horizon rule is:

Let `Q_A(t,t+H)` be the set of qualifying events effective in `(t,t+H]` whose identity/evidence is confirmed and whose availability timestamp is no later than `A`. Let `Complete_A(C)` mean outcome evidence is adjudicated complete through follow-up endpoint `C` by `A`. Calendar coverage by itself does not establish `Complete_A(C)`.

Operational states are distinct:

- **Confirmed positive:** a qualifying event is confirmed, effective in the horizon, and ascertainable by `A`.
- **Confirmed negative:** no qualifying event is found and evidence is complete and ascertained through the entire horizon by `A`.
- **Right-censored:** no qualifying event is established through a follow-up endpoint `C<t+H`, and outcome evidence is complete and ascertained through `C` by `A`.
- **Pending outcome ascertainment (`pending_ascertainment`):** evidence relevant to deciding the horizon outcome remains unavailable or unadjudicated at `A`. This includes an in-horizon event whose effective time is known but whose evidence is not yet available/confirmed by `A`, or apparent calendar coverage without adjudicated outcome completeness. It is neither positive, negative, nor right-censored at this cutoff.
- **Ineligible:** identity, required timestamps, target evidence, or feature-history requirements fail in a way that prevents a valid observation; this is not a censoring state.

\[
S(t) =
\begin{cases}
\text{ineligible}, & \text{identity, required timestamps, target evidence, feature history, or at-risk status at }t\text{ is invalid/ambiguous};\\
\text{positive}, & Q_A(t,t+H)\ne\varnothing;\\
\text{negative}, & C\ge t+H,\ Complete_A(t+H),\ Q_A(t,t+H)=\varnothing;\\
\text{pending\_ascertainment}, & \text{relevant in-horizon event evidence or outcome completeness is unresolved by }A;\\
\text{right-censored}, & C<t+H,\ Complete_A(C),\ \text{no event in }(t,C]\text{ and no unresolved in-horizon candidate};\\
\text{pending\_ascertainment}, & \text{otherwise, where relevant outcome evidence/coverage is unresolved by }A.
\end{cases}
\]

These are internal outcome states. Positive and negative may carry binary values `1` and `0` respectively; right-censored, `pending_ascertainment`, and ineligible do not receive a binary value. A qualifying event effective within the horizon but unavailable or unadjudicated by `A` is `pending_ascertainment`, never a confirmed positive or negative. If there is incomplete follow-up and no event, it is right-censored only when outcome evidence is complete through `C`; otherwise it is pending. An event after `t+H` is not positive for this horizon; the observation is negative only when complete outcome evidence through the full horizon is ascertained by `A`. Missing evidence is not evidence of no event.

#### Timeline examples

| Case | Example (`H=30d`) | Treatment under proposed hypothesis |
|---|---|---|
| Confirmed event in horizon | `t=1 Mar`, `T=20 Mar`, event available/adjudicated by `A=15 Apr`, `C>=20 Mar`. | Positive, if all identity and policy checks pass. Event availability after `t` is appropriate for target ascertainment, not as a feature at `t`. |
| No event, full follow-up and ascertainment | `t=1 Mar`, no event through `31 Mar`, `C>=31 Mar`, `Complete_A(31 Mar)`. | Negative. |
| Event after horizon | `t=1 Mar`, `T=15 Apr`, `C>=31 Mar`, complete and ascertained evidence through `31 Mar`. | Negative for the 30-day target; later episode outcome remains in truth. |
| No event, incomplete follow-up but complete through `C` | `t=1 Mar`, `C=20 Mar`, outcome evidence complete through `C`, no event by `C` and no unresolved event candidate in the horizon. | Right-censored, not negative. |
| No event, calendar records exist but ascertainment incomplete | `t=1 Mar`, calendar coverage appears through `31 Mar`, but outcome completeness through that date is not adjudicated by `A`. | `pending_ascertainment`, not negative and not yet right-censored. |
| Event effective before observation, recorded later | `T=25 Feb`, availability `30 Mar`, `t=1 Mar`. | Not a future positive. The event was not observable at `t`; historical target/eligibility treatment requires the configured retrospective vs as-known policy, and features must not use it at `t`. |
| Event in horizon but evidence arrives after label cutoff | `T=20 Mar`, `A=15 Mar`, event availability `30 Mar`, `C>=20 Mar`. | `pending_ascertainment`; not a confirmed positive or negative at `A`, even if calendar coverage spans the horizon. |

### 3.3 Censoring and incomplete follow-up

Right censoring means follow-up is known complete through `C`, but `C<t+H`; the episode may continue or observation may stop. Administrative right censoring occurs when the configured follow-up/extraction boundary limits `C` before the horizon endpoint. `pending_ascertainment` is different: at cutoff `A`, event evidence or its completeness has not yet been adjudicated, even if dates/files appear to cover the interval. Neither state is a negative label. Censoring is an outcome-knowledge state, not a data-quality failure.

Apply these distinctions:

- An episode still active at `E` is not automatically a negative; each observation needs follow-up through its horizon.
- An episode that enters the dataset late may lack the full historical feature window; its feature eligibility may fail even if future follow-up is complete.
- Incomplete follow-up with outcome evidence complete through `C` and no qualifying event/candidate in the horizon is right-censored. If evidence through `C` is not complete/adjudicated by `A`, or an in-horizon event is awaiting ascertainment, use `pending_ascertainment`. A qualifying event already confirmed inside the horizon by `A` may be positive despite later incomplete follow-up.
- An ambiguous episode identity is ineligible for identity-dependent labelling, not “censored” as a substitute for identity resolution.
- Missing or contradictory identity/timestamps can make an observation ineligible. Unresolved outcome evidence/completeness at `A` is `pending_ascertainment`; do not force a binary target.
- A fully followed-up and fully ascertained horizon with no qualifying event is negative under the declared synthetic policy only. It is not a claim that the episode never churns or that a production label is known.

Binary classification datasets should retain only eligible confirmed positive/negative observations for that specified policy. Right-censored, `pending_ascertainment`, and ineligible observations remain distinct internal states and are not coerced to binary labels. Survival-analysis methods might use right-censored durations in a future activity, but this document does not approve such architecture, estimators, or data contract changes.

### 3.4 Observation eligibility matrix

| Case | Business interpretation | Synthetic target treatment | Censoring treatment | Model eligibility | Policy decision required? |
|---|---|---|---|---|---|
| Active episode, full follow-up, no qualifying event | No termination through full horizon. | Negative only if outcome evidence is complete and ascertained through `t+H` by `A`. | Not censored. | Eligible if identity, feature and target gates pass. | Target policy and completeness rule must be selected. |
| Qualifying termination within horizon | Confirmed synthetic episode end. | Positive only if event evidence is confirmed and available by `A`. | Not right-censored for the event; later follow-up may remain incomplete. | Eligible if event is correctly attributed and features are point-in-time valid. | Yes: policy must accept this event type. |
| Termination after horizon | Event occurs outside target interval. | Negative only if follow-up and outcome ascertainment through `t+H` are complete. | Not censored for this horizon. | Eligible subject to other gates. | Event must be qualified; horizon configured. |
| Active episode, insufficient follow-up | No event yet observed; horizon incomplete. | No binary label. | Right-censored only if evidence is complete through `C`; otherwise `pending_ascertainment`. | Not eligible for binary training label in either state. | Yes: `C`/`A` completeness policy must be configured. |
| Incomplete follow-up, but evidence completeness through `C` is not adjudicated | Calendar/file interval may appear covered, but outcome completeness at `A` is unknown. | `pending_ascertainment`; no binary label. | Not yet classifiable as right-censored. | Pending, not model-eligible. | Ascertainment completeness policy required. |
| Cancellation request without effective termination | Intent/request only. | Not positive; unchanged target depends on later qualifying event and complete follow-up. | Censor only if follow-up incomplete. | Potentially eligible; request may be a feature only if available by `t` and approved. | Yes: request/reversal semantics and feature policy. |
| Payment failure without termination | Invoice/payment event only. | Not positive by itself. | Follow-up handled independently. | Potentially eligible; payment feature only if available by `t`. | No churn decision; feature use still needs approval. |
| Suspended episode | Service restriction may or may not end episode. | Policy-dependent; do not automatically label. | Depends on outcome follow-up. | Ineligible until suspension/termination policy resolves the target status. | Yes. |
| Paused episode | Temporary pause may preserve episode. | Policy-dependent; pause is not automatic churn. | Depends on follow-up. | Ineligible for target if pause semantics affect endpoint; otherwise conditional. | Yes. |
| Trial episode | Trial status; episode boundary and conversion failure are unresolved. | Policy-dependent; failed conversion not automatically churn. | Depends on follow-up after target start. | Ineligible for universal target; synthetic scenario can isolate it. | Yes. |
| Expired episode | Contract term reached an end; renewal/non-renewal semantics unknown. | Policy-dependent unless selected target explicitly accepts confirmed termination. | Follow-up depends on target evidence. | Ineligible under unresolved expiry mapping. | Yes. |
| Customer reactivated with a new episode | Later contractual episode after earlier termination. | Earlier episode retains its own outcome; new episode starts with a new target timeline. | Independently assessed per observation/episode. | Eligible per episode if identity and other gates pass. | Identity rule approved; target policy still applies. |
| Ambiguous episode identity | Episode ownership cannot be established. | No binary target. | Not censoring. | Ineligible; isolate unresolved identity record. | No heuristic resolution permitted; authoritative resolution remains external. |
| Missing/contradictory timestamps | Timeline cannot be reliably ordered. | No binary target. | Not automatically censoring. | Ineligible pending correction/evidence. | Yes if semantics/correction policy needed; never infer. |
| Event known only after observation time | Outcome event was not available to features at `t`. | May be positive only if effective in horizon and confirmed/ascertained by `A`; otherwise `pending_ascertainment`. | Right-censored only with complete evidence through `C` and no unresolved candidate; otherwise pending. | Feature view must exclude it; target eligibility depends on ascertainment. | Availability policy required. |
| Qualifying event in horizon, but not ascertainable by `A` | Candidate outcome may have occurred, but its evidence/confirmation arrives after the label cutoff. | `pending_ascertainment`; neither positive nor negative. | Not right-censored solely because ascertainment is late. | Pending; no binary label at this cutoff. | Yes: outcome evidence/ascertainment policy. |
| Observation created after episode termination | No at-risk observation period remains under this target. | No future-horizon label. | Not censoring. | Ineligible. | Only event/date semantics if termination itself uncertain. |

## 4. Reactivation, repeated observations, and grouping

The approved identity model remains unchanged: each contractual episode has its own canonical `subscription_id`; confirmed reactivation following termination creates a new episode/UUID; prior episode history remains preserved. Generate outcome facts independently per episode. Never transfer the earlier episode's positive label, censoring, termination time, or follow-up endpoint to the reactivated episode.

Multiple observations within one episode have separate `t`, history window, horizon, `C`, and eligibility. Their outcome intervals can overlap, so they are correlated observations and must not be split across training and evaluation partitions as if independent. Future evaluation design must select temporal separation and grouping rules. At minimum, keep observations from the same episode together; if evaluating generalisation to unseen accounts, group all episodes of a `customer_id` together across partitions. The grouping objective and final split strategy remain open (DD-EP-017). `customer_id` may be used as a split/grouping key but must not be a predictive feature. No split is implemented here.

## 5. Leakage prevention

At observation `t`, feature eligibility requires both business-effective and information-available constraints. For an event feature, require effective time at or before `t` and availability time at or before `t`, unless a separately approved feature definition explicitly concerns a different time concept. A future effective event is excluded even if scheduled/announced early unless a validated, point-in-time-available plan feature is deliberately approved. A backdated event learned later is also excluded from an as-known-at-`t` feature view.

| Leakage risk | Required safeguard |
|---|---|
| Future lifecycle event included as historical feature | Filter by effective time and availability time relative to `t`; retain later outcome truth separately. |
| Termination date not known at `t` | Do not expose the future termination date or a proxy derived from outcome truth in features. |
| Post-observation invoice payment | Exclude payment/overdue resolution unavailable by `t`, even if invoice was issued earlier. |
| Future usage aggregate | Use only usage whose covered interval has ended and whose aggregate was available by `t`; partial periods need an explicit policy. |
| Current subscription master copied into historical observation | Build historical features from event/snapshot truth as-of `t`, not final `subscriptions.csv` fields. |
| Outcome-derived IDs or synthetic-generation flags | Keep IDs out of predictive features per approved contract/ADR constraints; keep `target_policy_id`, event identity, censoring, and generator flags internal. |
| Label/censoring metadata used as predictors | Store separately from feature matrices and enforce explicit target/feature column allowlists in future model-data assembly. |
| Overlapping episode observations contaminating evaluation | Keep all observations from one episode in one partition; decide customer grouping and time split before evaluation. |

Maintain distinct timestamps: event occurrence, effective, availability/recorded, observation `t`, extraction cutoff `E`, outcome ascertainment cutoff `A`, and label construction time. No single timestamp substitutes for another. No internal target or censoring fields are added to contract CSVs.

## 6. Ground-truth storage boundary

The internal ground-truth representation is a logical design, not a file/schema. It must remain separate from the five contract CSVs and contain no real personal data. Any future persisted ground truth must be run-scoped and access-controlled; the operational access-control model and persistence controls remain open under CGQ-022. A suitable logical observation record contains:

| Internal field | Purpose |
|---|---|
| `run_id`, `scenario_id`, `target_policy_id`, policy version/hash | Provenance and unambiguous interpretation of synthetic outcomes. |
| `customer_id`, canonical `subscription_id`, `observation_id` | Entity lineage; identifiers remain excluded from predictive features. |
| `observation_timestamp`, history start, `prediction_horizon`, horizon end | Define feature interval and target interval. |
| `qualifying_event_id`, event type, effective time, availability time | Record candidate outcome and evidence/temporal lineage. |
| `follow_up_endpoint` (`C`), extraction cutoff (`E`), outcome ascertainment cutoff (`A`) | Establish completeness of the observation horizon. |
| `outcome_state`, optional binary outcome, censoring indicator/reason, ascertainment-pending reason | Distinguish the five defined states: confirmed positive, confirmed negative, right-censored, `pending_ascertainment`, and ineligible. Policy-dependent cases remain unresolved until a target policy is selected. Only positive/negative have binary values. |
| `eligibility_status`, exclusion reason(s), feature availability summary | Explain inclusion/exclusion without exposing outcome-derived fields as predictors. |
| configuration hash, generator/version, seed/provenance references | Support reproducibility and audit of synthetic assumptions. |

Contract projections must continue to contain only approved headers and fields. Ground-truth artifacts and diagnostic logs must not include raw real source records, secrets, or unnecessary identifiers. Apply least-privilege access and an implementation-defined retention/cleanup policy before persistence.

## 7. Data quality framework

### 7.1 Independent gates and scope

| Gate | Responsibility | Limitation |
|---|---|---|
| Contract validation | Header, requiredness, types/formats, categories, row-level and within-dataset schema constraints. | Does not prove cross-dataset key existence, semantic ownership, temporal availability, or valid labels. |
| Referential integrity | RI-001–RI-004 check subscription-to-customer and snapshot/usage/invoice-to-subscription key existence. | A child row can reference an existing but wrong episode and pass. |
| Semantic episode attribution | Future comparison of generated truth/approved lineage with dependent-row owner. | Not currently checked by contract schemas or RI; cannot use date overlap as proof. |
| Temporal correctness | Event sequence, effective/available timestamps, period coverage, cutoffs, historical state and follow-up. | Current TC rules cover only subscription end/cancellation date not preceding start. Other rules need decisions and implementation. |
| Model eligibility | Target qualification, observation/horizon/follow-up, censoring, identity and feature availability. | No such label/eligibility implementation exists. Pipeline success does not confer model eligibility. |

Current validation sources reviewed include exact CSV header inspection, CSV row-width/encoding checks, type normalisation, strict Pandera schemas, RI and TC validators, and `execute_pipeline` integration tests. As currently implemented, the schema layer checks primary/composite-key uniqueness, required/null fields, status membership, numeric non-negativity, `active_users <= total_users`, three-letter uppercase currency shape, and invoice due/paid date ordering. RI-001–RI-004 and TC-001–TC-002 are implemented. These are not all complete contract semantics: three-letter currency shape is not full ISO 4217 membership, and current TC rules do not enforce snapshot/usage periods, cutoff, event chronology, or historical availability.

The current pipeline blocks RI/DQ when a supplied applicable dataset fails schema validation; missing required workflow input blocks dependent stages; present-empty required inputs fail operational checks; optional datasets may be absent. A failure must remain recorded in stage outcomes, and invalid/partial data must never be represented as a successful valid synthetic population. A future synthetic generator must separately gate semantic truth, temporal correctness, and eligibility before declaring model-ready output.

### 7.2 Data quality dimensions and expected behaviour

Severity for confirmed future rules is proposed as **ERROR** where validity/attribution/label safety is broken, **WARNING** for reviewable quality concerns that do not invalidate the entire affected scope, and **INFO** for non-failing counts/coverage. No numeric warning thresholds are invented. Pending or unimplemented rules are `NOT_EVALUATED`, not `PASS`; absent optional datasets are not failures.

| Dimension | Objective / invariant | Data and stage | Current enforcement | Failure severity / behaviour |
|---|---|---|---|---|
| Completeness | Required headers/values present; optional missingness reported only under an approved threshold. | CSV header, normalisation, schemas; future reporting for coverage. | Required header/value checks exist; no general missingness threshold. | ERROR for required schema failure, stage blocks dependent checks; warning threshold is open. |
| Uniqueness | Customer and subscription IDs unique; invoice ID unique; snapshot and usage composite keys unique. | Each dataset; schema validation. | Enforced by Pandera. | ERROR; failed dataset does not proceed as valid. |
| Referential integrity | Each subscription customer key and dependent episode key exists. | Cross-dataset; RI stage. | RI-001–RI-004 implemented. | ERROR; related scope blocked/failed per current pipeline outcome. |
| Type and format validity | Dates, timestamps, numerics, booleans and identifiers parse without lossy inference; CSV format is consistent. | Header/ingestion/normalisation/schema. | Header and normalisation plus strict schemas implemented. | ERROR; stop affected validation chain and preserve diagnostic. |
| Allowed categorical values | Subscription/snapshot/invoice statuses are members of current schema lists. | Schema. | Enforced by Pandera. | ERROR. Client-specific pre-schema mapping remains unresolved/not implemented. |
| Numerical validity | Amounts/counts/volume non-negative; usage active users do not exceed total users. | Schema. | Enforced by Pandera. | ERROR. No distribution/outlier thresholds are approved. |
| Currency validity | Shape matches three uppercase letters; membership in ISO 4217 requires authoritative list and policy. | Schema now; future configured reference validation. | Shape only. | Shape violation: ERROR now. Full membership: NOT_EVALUATED until decision and implementation. |
| Temporal consistency | End/cancellation do not precede start; future extensions cover snapshots, usage, events, cutoffs and periods. | TC stage and future truth validator. | TC-001/002 implemented; invoice due/paid >= issue is schema-level. | Current violations: ERROR. Other cases: NOT_EVALUATED pending decisions/implementation. |
| Episode identity consistency | Canonical ID is stable, unique per episode, new after confirmed reactivation; no heuristic ambiguity resolution. | Ground truth/identity lineage, optional registry future. | Within-file uniqueness only; no registry/cross-submission identity control. | ERROR/ineligible for affected identity-dependent observations; current pipeline cannot fully detect it. |
| Cross-dataset consistency | Child references the correct episode/customer, not merely an existing key. | Truth + CSV projections; future semantic attribution stage. | Key existence only. | ERROR; block affected dependent records/run; NOT_EVALUATED in current pipeline. |
| Business-rule consistency | Billing amounts follow configured plan/cadence; invoice and recurring revenue use approved synthetic equations; payment failure not churn. | Ground truth/projections; future business validator. | No financial reconciliation or churn-business validator. | ERROR for generated inconsistency; NOT_EVALUATED currently. Do not impose production accounting rules. |
| Historical availability | Features use facts effective and available by `t`; period aggregates are complete/available. | Internal event/usage truth, feature assembly. | Not enforced by CSV pipeline. | ERROR/ineligible for affected observation; proposed future check. |
| Outcome consistency | Positive label has qualifying event; negative has complete follow-up and no qualifying event in horizon. | Internal outcome truth and target assembler. | Not implemented. | ERROR; reject label/observation from model-eligible set. |
| Censoring consistency | Follow-up shorter than horizon without event is censored, not negative; reason agrees with `C`, `t`, `H`. | Internal outcome truth. | Not implemented. | ERROR; no binary label; future target validation. |
| Reproducibility and provenance | Same approved config/code/dependencies/seed and identity policy can be traced to one run and outputs. | Config, manifest, internal truth. | No synthetic generator/manifest implementation. | ERROR for missing/mismatched provenance on a claimed reproducible run; future check. |

Failure handling is scoped: contract/schema failure blocks downstream validation for that dataset; RI failure blocks trust in the affected relationships; semantic/temporal/outcome failures exclude or block affected data from a valid population/model-eligible set. Do not silently repair, impute, drop, or quarantine rows. Any future correction/reject policy needs separate approval and traceability. Diagnostics must be sanitised and identify rule, datasets, affected counts, and expected gate without full row payloads or secrets.

## 8. Negative fixture catalogue

Fixtures are design cases only. A future fixture runner must clone or construct data under an isolated fixture ID and expected gate. “Current” below describes inspected code; “future” means additional validation is required. A schema-valid foreign key can still be semantically false. Expected states in this catalogue describe diagnostics, not automatic correction: validators report/reject the invalid case according to approved behaviour and do not mutate it, reclassify its label, impute, drop, or quarantine it. Any correction or disposition workflow needs separate approval.

| Fixture ID | Category / intended defect | Affected data | Expected gate and failure classification | Expected diagnostic | Current pipeline detection? / additional validation |
|---|---|---|---|---|---|
| NQ-C-001 | Missing required column | Any contract CSV | Header inspection; ERROR, stage blocked. | Dataset and missing header name. | Yes; existing exact header checks. |
| NQ-C-002 | Unexpected column | Any contract CSV | Header inspection; ERROR, stage blocked. | Dataset and unexpected header name. | Yes; extra columns rejected. |
| NQ-C-003 | Invalid date/numeric/boolean token or malformed row width | Relevant CSV | Ingestion/normalisation; ERROR. | Sanitised dataset, column or row-width reason. | Yes; type parsing/row-width checks implemented. |
| NQ-C-004 | Missing/null/blank required identifier | Customer, subscription, invoice, snapshot, usage | Schema after normalisation; ERROR. | Dataset/field and failed constraint. | Yes; required/null and blank identifier constraints. |
| NQ-C-005 | Duplicate primary/composite key | Customer, subscription, invoice, snapshot, usage | Schema; ERROR. | Dataset/key constraint. | Yes; uniqueness schemas implemented. |
| NQ-C-006 | Invalid status category | Subscription, snapshot, invoice | Schema; ERROR. | Dataset/status field and accepted-category constraint. | Yes; exact category schemas implemented. |
| NQ-C-007 | Negative invoice amount | Invoice | Schema; ERROR. | `invoices.amount` non-negative violation. | Yes; Pandera check. |
| NQ-C-008 | Negative usage count or volume | Usage | Schema; ERROR. | Field and non-negative constraint. | Yes; Pandera checks. |
| NQ-C-009 | `active_users > total_users` | Usage | Schema; ERROR. | Usage row violates user-count relationship. | Yes; Pandera check. |
| NQ-C-010 | Invalid currency shape (e.g. lower-case or wrong length) | Subscription/snapshot/invoice | Schema; ERROR. | Currency does not match uppercase three-letter format. | Yes. A shape-valid non-ISO code requires future full-membership validation. |
| NQ-C-011 | Valid-format but absent ISO currency code | Subscription/snapshot/invoice | Future reference-list check; proposed ERROR. | Currency not in configured ISO 4217 version. | No; current schema checks shape only. |
| NQ-R-001 | Subscription references missing customer | Subscriptions + customers | RI-001; ERROR, relationship fails. | Count/IDs safely summarised; no raw row payload. | Yes; implemented. |
| NQ-R-002 | Invoice references missing subscription | Invoices + subscriptions | RI-004; ERROR. | Orphan invoice relationship/count. | Yes; implemented. |
| NQ-R-003 | Usage references missing subscription | Usage + subscriptions | RI-003; ERROR. | Orphan usage relationship/count. | Yes; implemented. |
| NQ-R-004 | Snapshot references missing subscription | Snapshots + subscriptions | RI-002; ERROR. | Orphan snapshot relationship/count. | Yes; implemented. |
| NQ-R-005 | Duplicate episode identifier | Subscriptions | Schema; ERROR. | Duplicate `subscription_id`. | Yes within supplied dataset; cross-run identity stability is not checked. |
| NQ-R-006 | Cross-dataset ownership contradiction while keys exist | Truth + child row + valid parent rows | Semantic attribution; ERROR/ineligible. | Child's truth owner differs from referenced episode. | No; requires generated truth/attribution validator. |
| NQ-I-001 | Source identifier copied as canonical ID without authority | Truth + subscriptions | Identity/semantic gate; ERROR/ineligible. | Canonical ID lacks approved identity lineage. | No; may pass schema/RI; requires identity provenance checks. |
| NQ-I-002 | Reused `subscription_id` after confirmed reactivation | Subscriptions + truth/history | Identity gate; ERROR. | Two confirmed episodes share canonical ID. | Only duplicate rows in one file are caught; Registry/cross-history check needed otherwise. |
| NQ-I-003 | Earlier episode history overwritten by later episode | Snapshots/invoices/usage + truth | Semantic history gate; ERROR. | Missing or reassigned prior-episode lineage. | No; requires truth/history comparison. |
| NQ-I-004 | Invoice assigned to wrong existing episode | Invoices + truth | Semantic attribution; ERROR. | `invoice_id` points to an episode other than truth owner. | No; RI passes if key exists. |
| NQ-I-005 | Usage assigned to wrong existing episode | Usage + truth | Semantic attribution; ERROR. | Episode-month record differs from truth owner. | No; RI passes if key exists. |
| NQ-I-006 | Snapshot assigned to wrong existing episode | Snapshots + truth | Semantic attribution; ERROR. | Snapshot episode differs from truth owner. | No; RI passes if key exists. |
| NQ-I-007 | Ambiguity resolved by date proximity or row order | Truth/identity case | Identity gate; ineligible, no canonical ID. | Ambiguity remains unresolved; heuristic assignment prohibited. | No; isolated identity fixture and future identity checks. |
| NQ-I-008 | Conflicting episode ownership | Truth + dependent row | Semantic attribution; ERROR/ineligible. | More than one authoritative owner or contradictory lineage. | No; requires truth validation. |
| NQ-T-001 | Event before episode creation | Event truth | Temporal validator; ERROR. | `occurred_at` predates episode creation. | No; internal event chronology check required. |
| NQ-T-002 | Episode end before start | Subscriptions | TC-001; ERROR. | End date precedes start date. | Yes; implemented. |
| NQ-T-003 | Cancellation date before start | Subscriptions | TC-002; ERROR. | Cancellation date precedes start date. | Yes; implemented. |
| NQ-T-004 | Snapshot before episode start | Snapshot + subscriptions | Future temporal gate; ERROR. | Snapshot falls outside episode interval. | No; current TC rules do not check snapshots. |
| NQ-T-005 | Snapshot after extraction cutoff | Snapshot + run context | Future cutoff gate; ERROR. | Snapshot exceeds configured `E`. | No; cutoff unavailable to current validator. |
| NQ-T-006 | Usage outside permitted episode interval | Usage + truth | Future temporal/semantic gate; ERROR or policy-dependent exclusion. | Usage coverage overlaps no permitted active episode interval. | No; requires period boundaries and attribution decision. |
| NQ-T-007 | Contradictory lifecycle transitions | Event truth | Transition replay; ERROR. | No deterministic state sequence. | No; lifecycle validator absent and semantics open. |
| NQ-T-008 | Conflicting simultaneous events | Event truth | Event precedence gate; ERROR/NOT_EVALUATED until precedence selected. | Conflicting state changes at same effective time. | No; explicit policy and validator needed. |
| NQ-T-009 | Service event after confirmed final termination on same ID | Events + truth | Episode interval gate; ERROR. | Post-termination event attached to closed episode. | No; requires event truth. |
| NQ-T-010 | Backdated event treated as available before actual availability | Event availability + feature view | Point-in-time gate; ERROR/leakage failure. | Feature consumes event with availability `> t`. | No; availability is not in contract. |
| NQ-T-011 | Invoice outside configured billing cycle | Invoice + internal billing period | Billing schedule validator; ERROR or NOT_EVALUATED while boundaries open. | Issue date/amount inconsistent with configured cycle. | No; service period and cycle rules absent. |
| NQ-T-012 | Usage aggregate extends beyond observation cutoff | Usage coverage + observation | Feature eligibility; ERROR/ineligible observation. | Aggregate includes activity after `t` or unavailable by `t`. | No; coverage/availability internal and period policy open. |
| NQ-T-013 | Snapshot uses final master status for past date | Snapshot + event truth | Historical-state gate; ERROR. | Snapshot differs from replayed as-of state or uses later-known fact. | No; current contract pipeline does not replay events. |
| NQ-Y-001 | Payment failure labelled as churn | Invoice + target truth | Outcome consistency; ERROR/reject label. | Payment state has no qualifying termination evidence. | No; outcome validator not implemented. |
| NQ-Y-002 | Cancellation request labelled as effective churn | Event + target truth | Outcome consistency; ERROR/reject label. | Request event is not confirmed effective termination. | No; policy and validator needed. |
| NQ-Y-003 | Incomplete follow-up labelled negative | Outcome truth | ERROR — reject invalid negative label; report expected censored state without automatically modifying the record. | `C < t+H`, ascertainment complete through `C`, no event/candidate, but negative supplied. If ascertainment is incomplete, report `pending_ascertainment` instead. | No; censoring/ascertainment logic not implemented. |
| NQ-Y-004 | Event after horizon labelled positive | Event + target truth | Horizon check; ERROR/reject label. | `T > t+H`. | No; outcome/horizon validator needed. |
| NQ-Y-005 | Event before observation labelled future positive | Event + target truth | Outcome/temporal check; ERROR/ineligible for future target. | `T <= t` but target marked positive for `(t,t+H]`. | No; validator needed. |
| NQ-Y-006 | Reactivated episode inherits earlier episode label | Customer episodes + target truth | Episode outcome lineage; ERROR. | Target references event from another `subscription_id`. | No; requires truth linkage check. |
| NQ-Y-007 | Ambiguous identity assigned binary label | Identity + target truth | Eligibility gate; ineligible, no binary target. | Identity unresolved but label emitted. | No; identity/eligibility validator needed. |
| NQ-Y-008 | Future event included as a feature | Feature view + event truth | Leakage gate; ERROR/reject observation. | Feature uses effective or availability time after `t`. | No; model-data assembler not implemented. |
| NQ-Y-009 | Missing outcome evidence treated as confirmed negative | Outcome truth | ERROR — reject unsupported negative label; report expected `pending_ascertainment`, right-censored, or ineligible state as evidenced, without modifying the record. | Negative lacks the complete outcome evidence required through `t+H`. | No; target/ascertainment validator needed. |
| NQ-Y-010 | Censoring flag contradicts follow-up | Observation outcome record | Censoring consistency; ERROR. | Censor flag disagrees with `C`, `t`, `H`, or event evidence. | No; censoring validator needed. |

Fixture diagnostics should use rule/fixture IDs, dataset/field names, counts, and safe descriptions. Do not persist raw rows, personal data, unrestricted identifiers, full DataFrames, credentials, or source paths in broadly accessible logs.

## 9. Isolation, validation failure, and future tests

### 9.1 Isolation and failure behaviour

- Valid synthetic population outputs and negative fixtures have separate run/output roots and manifests. A fixture run must never be referenced as a training population.
- Negative fixture construction is explicit and deterministic where a seed/policy can control it. Each fixture manifest records fixture ID, intended defect, seed/config provenance, expected gate, and expected result.
- Invalid fixture outcomes are expected test failures at their declared gate; they are not operational generation successes. A fixture cannot be marked valid merely because upstream schema checks passed when its intended defect belongs to attribution, temporal, or label validation.
- Failure in a required generation/validation stage prevents the run from being marked a valid population. Preserve prior stage outcomes and identify dependent blocked checks. Do not publish partial output as complete or silently repair/drop/quarantine rows.
- Ground truth remains separate from contract CSVs. Diagnostic logging must be sanitised and must not expose raw truth, direct personal data, secrets, or unnecessary identifiers.
- Current `execute_pipeline` validates file-based contract data; it does not validate synthetic truth, churn labels, censoring, leakage, or fixture isolation. Pipeline success alone is not model-readiness evidence.

### 9.2 Future test strategy

| Test level | Future responsibilities |
|---|---|
| Unit | Target qualification and interval boundaries; positive/negative/censored/ineligible classification; censoring consistency; event replay and time availability; identity invariants; individual DQ rules; fixture expected findings. |
| Integration | Cross-dataset keys and truth attribution; contract projection; event-to-snapshot/usage/invoice derivation; temporal reconstruction; pipeline validation and stage dependencies; failure diagnostics and output isolation. |
| End-to-end | Reproducible valid generation; manifest/ground-truth/output consistency; a catalogue of negative fixtures failing at expected gates; no valid publication after failure; repeat episode/customer split grouping invariants once evaluation policy is approved. |

These are future design responsibilities only. No tests are added or run in this documentation activity.

## 10. Decision register

Statuses record current project authority: **Approved** is an existing approved decision; **Proposed** is a synthetic/design recommendation awaiting approval; **Open** requires a product/client/technical decision; **Blocked** means the dependent implementation scope cannot proceed safely until a decision is made. Previously open decisions remain open.

| Decision ID | Topic | Proposal or existing decision | Status | Rationale | Dependencies | Implementation impact |
|---|---|---|---|---|---|---|
| CGQ-001 | Episode prediction entity | `subscription_id` represents one canonical contractual episode; `customer_id` represents the account and is not a predictive feature. | Approved | ADR-009/010 and contract grain. | ADR-009, ADR-010. | Labels are per episode; customer grouping is metadata only. |
| CGQ-002 | Canonical UUID lifecycle | UUID issued once for authoritatively established episode, persisted/reused; version/provider remains undecided. | Approved | Preserves stable identity without selecting technical mechanics. | PD-002; Registry requirement; UUID technical design. | Identity persistence principle applies; deterministic generator implementation awaits mechanism. |
| CGQ-003 | Reactivation and episode history | Confirmed reactivation after termination creates a new canonical ID; earlier history remains. | Approved | ADR-010 and approved identity decisions. | Authoritative episode termination/reactivation evidence remains context-dependent. | Outcome truth must be episode-scoped; no label transfer. |
| CGQ-004 | Ambiguous identity treatment | Do not resolve by dates/status/row order/heuristics; isolate unresolved records and exclude from identity-dependent processing. | Approved | PD-003 and ADR-010. | Identity evidence and attribution. | No binary label for unresolved episode identity. |
| CGQ-005 | Snapshot workflow | Snapshots optional for BASIC and required for TEMPORAL workflows. | Approved | PD-006. | Declared workflow; snapshot convention remains open. | Does not make any particular snapshot date convention approved. |
| CGQ-006 | Synthetic effective-end target | A confirmed synthetic termination effective in `(t,t+H]` and ascertainable by `A` may be positive under an identified target policy; no event is negative only with complete and ascertained follow-up through `t+H`. | Proposed | Gives a testable synthetic hypothesis without approving production churn. | CGQ-007–CGQ-012, CGQ-021; evidence and ascertainment cutoffs. | Implement only after policy/configuration approval; retain internal policy ID. |
| CGQ-007 | Churn event qualification | Cancellation request, expiration, trial failure, pause, suspension, failed payment or overdue invoice do not automatically qualify without an explicit target policy. | Open | Avoids conflating intent, operational state, billing, and contractual termination; the accepted positive event set remains undecided. | Episode boundary and event definitions. | Event mapping and positive labels blocked until relevant policy is approved. |
| CGQ-008 | Production churn definition | Production qualifying event and label semantics remain undefined. | Open | Contract/business references require later agreement and evidence. | DD-EP-005, DD-EP-013; source/client evidence and product policy. | No production labels or claims. |
| CGQ-009 | Observation/history window | 90-day history may be used as a provisional engineering example only. | Proposed | Contract calls observation assumptions provisional. | Intended modelling use and data coverage. | Configure; do not represent as approved production value. |
| CGQ-010 | Prediction horizon | 30-day horizon may be used as a provisional engineering example only. | Proposed | Permits illustrative boundary tests without deciding production horizon. | Target policy, use case, evaluation design. | Configure; no model eligibility until approved. |
| CGQ-011 | Outcome ascertainment and completeness | Track `A` separately from `E`, `C`, `t`, `T`, and event availability; calendar coverage does not prove event ascertainment or completeness. | Proposed | Label evidence can arrive after event effective time and feature observation, or remain unadjudicated despite apparent coverage. | Data coverage and event availability policy. | Store internal temporal metadata; define evidence-completeness rules before labels are built. |
| CGQ-012 | Right censoring | Right-censor only when `C<t+H`, follow-up is fully ascertained through `C`, and no in-horizon qualifying event/candidate is unresolved. Otherwise use pending where ascertainment is unresolved; never assign negative from incomplete follow-up. | Proposed | Distinguishes incomplete follow-up from incomplete outcome adjudication and prevents false negatives. | Definition of `C`, `A`, and evidence completeness. | Binary eligibility depends on approved cutoff and ascertainment policy. |
| CGQ-013 | Historical availability principle | Predictive features use only information available at or before observation time; later information is not retrospectively applied. | Approved | Contract and leakage guidance require prediction-time availability; this does not prescribe the implementation. | Event/usage availability metadata and snapshot semantics. | No additional contract columns; the principle applies to feature construction. |
| CGQ-014 | Trial, pause, suspension, expiry | Their episode and target treatment remains policy-dependent; none is automatically churn. | Open | Block B and episode decisions leave lifecycle meanings unresolved. | DD-EP-001, DD-EP-005–007 and target policy. | Affected observations remain policy-dependent/ineligible for a universal target. |
| CGQ-015 | Episode grouping/evaluation split | Keep one episode's observations in one partition; customer-level grouping may be needed to test unseen-account generalisation. | Open | Prevents direct repeated-observation leakage while preserving evaluation intent; final strategy depends on objective. | DD-EP-017 and modelling objective. | No split implemented; final grouping/time strategy requires approval. |
| CGQ-016 | Model eligibility | Production observation, horizon, target, censoring, feature policy and eligibility criteria are not approved. | Open | Synthetic rules do not settle production model policy. | CGQ-008–CGQ-015; product and client evidence as applicable. | Production labelled dataset remains blocked. |
| CGQ-017 | Data quality rules beyond current checks | Semantic attribution, detailed temporal, outcome, censoring and leakage rules are proposed future checks, not implemented. | Proposed | Necessary to distinguish passing schema/key checks from correct model data. | Explicit rule definitions and implementation authorisation. | Report as not evaluated until implemented; do not claim pass. |
| CGQ-018 | Contract additions and survival architecture | No new contract columns and no production survival-analysis design are authorised by Block C. | Approved | Preserves v1.1 and prevents premature architecture decisions. | Separate approval if future requirements demand changes. | Keep metadata internal; survival use remains future work. |
| CGQ-019 | UUID version/provider and replay mechanism | Select a concrete UUID version/provider and exact persistence/replay method. | Open | ADR-010 approves UUID but not implementation details or deterministic replay. | Identity-provider design, Registry and reproducibility requirements. | Canonical episode-ID generation implementation is blocked pending decision. |
| CGQ-020 | Availability-time representation and policy | Define how late-arriving/corrected events and usage availability are represented and reconstructed internally. | Open | Contract CSVs have no availability-time columns and the as-of process is not implemented. | Event types, ingestion/recording behaviour, observation and outcome cutoffs. | Historical as-known feature certification is blocked until defined; no contract columns are added here. |
| CGQ-021 | `pending_ascertainment` state | Use `pending_ascertainment` as an internal non-binary state when relevant event evidence/completeness is unresolved at `A`. | Proposed | Prevents an unascertained in-horizon event or incomplete adjudication from being called positive, negative, or right-censored. | CGQ-011–CGQ-012; target/ascertainment policy. | Internal-only outcome state; must not be added to Customer Data Contract v1.1. |
| CGQ-022 | Persistent ground-truth storage | Decide storage format, access controls, retention/cleanup, identity persistence, and reproducibility/provenance before persisting ground truth. | Open | Logical fields do not establish a safe or durable storage design. | ADR-010 identity persistence; security, data governance, and reproducibility requirements. | Persistent storage is blocked; no storage architecture is selected by this document. |

## 11. Implementation readiness

Readiness is limited to the specified design scope. “Ready with approved configuration” allows parameterised synthetic-only work after the relevant values and policy ID are selected; it does not approve production semantics.

| Component | Classification | Reason / dependency |
|---|---|---|
| Logical ground-truth structures | Ready for implementation | Four layers and logical fields are specified; they can be represented in memory without selecting persistent storage architecture or adding contract columns. |
| Persistent ground-truth storage | Blocked by open decision | Storage format, access-control model, retention/cleanup, identity persistence, and reproducibility/provenance requirements must be decided before persistence. This does not select a new storage architecture. |
| Synthetic outcome hypothesis | Ready with approved configuration | Effective-end hypothesis is testable as a synthetic assumption once a target-policy ID and event evidence configuration are approved; not a production label. |
| Event qualification | Blocked by open decision | Exact qualifying contractual event and mapping from cancellation/expiration/termination require policy and evidence. A synthetic-only explicit event type can be isolated but must not imply universal semantics. |
| Observation generation | Ready with approved configuration | `t`, history window, extraction cutoff and provenance are defined conceptually; exact `W`/cutoff values and timestamp precision need configuration. |
| Horizon evaluation | Ready with approved configuration | `(t,t+H]` and outcome categories are specified; requires a selected `H`, qualification policy, and complete event evidence. |
| Censoring and ascertainment states | Ready with approved configuration | Positive, negative, right-censored and `pending_ascertainment` are distinguished; operational computation requires approved `C`, `A`, and evidence-completeness rules. |
| Label eligibility | Blocked by open decision | Production target, horizon/window, lifecycle treatment, identity and feature eligibility are unresolved. Synthetic-only eligibility can be implemented only after policy configuration. |
| Contract-level data quality | Ready for implementation | Header, normalisation, schemas, RI, and two TC rules exist; listed negative fixtures can target current rules. New fields/rules are not authorised. |
| Referential integrity | Ready for implementation | RI-001–004 are implemented; they only prove reference existence. Semantic correctness is separate. |
| Semantic episode attribution | Blocked by open decision | Requires authoritative truth/lineage and attribution evidence; current pipeline has no such validator and Registry is not implemented. |
| Temporal validation | Blocked by open decision | Beyond TC-001/002 it requires event, snapshot, usage, billing, availability, and cutoff policies, several of which remain open. |
| Negative fixture generation | Ready with approved configuration | Fixture catalogue and expected gates are specified; isolation, deterministic seeds, and test-only output boundary must be implemented. |
| Pipeline validation integration | Ready for implementation | Existing file-based `execute_pipeline` supports BASIC/TEMPORAL workflows and stage outcomes; it validates contract data only and must not be presented as ground-truth/label validation. |

Components that can be developed independently of production churn semantics include internal ground-truth containers, contract-level fixtures for already-enforced rules, key-existence RI cases, output isolation, and pipeline invocation. Production label generation, policy-dependent event qualification, temporal correctness, semantic identity attribution, and model eligibility remain blocked or require explicit synthetic-only configuration.

## 12. NEDS v1.1 alignment

The authoritative NEDS v1.1 was reviewed in project reference material. The table assesses this design only; it does not claim that implementation or operational compliance has been achieved.

| NEDS area | Design alignment | Future evidence / remaining work |
|---|---|---|
| Modular architecture | Four distinct truth/observation/outcome/eligibility layers and independent quality gates map to Block A's modular responsibilities. | Keep future components small, explicit, and within existing architecture. |
| Reproducibility | Target policy, configuration, run ID, horizon, cutoffs, provenance, and deterministic fixture expectations are specified. | Version code/config/dependencies and verify repeatable outcomes after identity-provider decisions. |
| Data quality | Testable dimensions and fixture-specific expected gates distinguish schema, RI, semantic, temporal, and label quality. | Implement only approved rules and report actual execution status; pending rules are not passes. |
| Error handling | Failed gates reject/block affected observations and prohibit valid publication; partial results retain stage outcomes. | Implement and evidence blocking, propagation, and safe diagnostics. |
| Logging | Diagnostics include rule/fixture and safe counts, not raw data. | Configure run/stage logs and retention for deployment context. |
| Security and privacy | Synthetic-only truth, access control, separation from contract data, least privilege, minimisation, and sanitised output are required. | Define environment permissions, retention/deletion, and operational controls before persistence. |
| Testability | Unit, integration, and end-to-end responsibilities are mapped to rule boundaries and fixture expectations. | Add and run tests only in an authorised implementation phase; report actual results. |
| Maintainability | Decision register, explicit unresolved statuses, and stable fixture IDs support review and change tracking. | Version changes to rule meaning and preserve decision traceability. |
| Technical justification | Proposed synthetic effective-end target is justified as a tractable test hypothesis and bounded from production policy. | Record rationale for each future policy/implementation decision and exception. |
| British English | Document language and terminology use British English. | Keep future code comments and repository documentation consistent with NEDS. |
| Decision traceability | Register links status, rationale, dependencies, and impact; approved/open decisions remain distinguished. | Link implementation artefacts/tests to the relevant decision and update statuses only after approval. |
| Incremental delivery | Block C extends Block A/B without changing contracts, code, or previous design decisions. | Implement in separately authorised increments with reviewable evidence at each stage. |

## 13. Risks, limitations, and next steps

| Risk / limitation | Treatment in this design |
|---|---|
| Synthetic hypothesis mistaken for production churn | Label it explicitly as Proposed Synthetic Assumption, retain a policy ID, and exclude production claims. |
| Incomplete follow-up silently labelled negative | Use `C` and ascertainment completeness; right-censor only when evidence is complete through `C`, and use `pending_ascertainment` while evidence completeness is unresolved. |
| Status/request/payment signal mistaken for termination | Require explicit synthetic termination evidence; separate invoice and lifecycle state. |
| Late-arriving/backdated event leaks into features | Track availability separately and filter as-known features at `t`. |
| Schema/RI pass mistaken for attribution or temporal proof | Keep validation gates independent and show current coverage limitations. |
| Episode identity ambiguity contaminates labels | Keep identity unresolved and exclude from identity-dependent eligibility; preserve prior episodes on reactivation. |
| Temporal policy gaps make labels non-reproducible | Keep snapshot, usage, billing, effective/availability, extraction, and observation cutoff decisions open in the register. |
| DQ documentation disagrees with source | This document records inspected source capability and flags the separate discrepancy; no unrelated doc is changed. |

Next steps after review are to obtain approval for the synthetic target hypothesis and its configuration, resolve event qualification and temporal dependencies needed for a selected scope, and then separately authorise implementation of generators/validators/tests. No Block D work should begin until Block C review and approval. This document creates no code, configuration, dataset, test, schema, pipeline, ADR, or contract change.
