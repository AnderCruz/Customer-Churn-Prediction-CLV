# Customer Data Contract Episode Alignment Proposal

> **Historical design record.** This document preserves the Phase 02 assessment and its implementation observations at the time of review. For governing requirements, see the [approved Customer Data Contract](customer_data_contract.md) and [ADR-010](../03_architecture/adr_episode_identity_and_identifier_management.md).

**Document ID:** NCI-CONTRACT-EPISODE-PROPOSAL-001
**Version:** 0.1
**Status:** Draft for technical review
**Project:** Nowa Customer Intelligence
**Scope:** Phase 2.4.4.1 — Customer Data Contract episode alignment and versioning assessment
**Assessment date:** 2026-11-15

## 1. Executive summary

**APPROVED REQUIREMENT:** The prediction entity is an individual contractual subscription episode. A customer may have multiple episodes. Each episode has an independent canonical identity; an episode terminated and later reactivated is a new episode, and earlier episodes remain historically preserved. ADR-010 assigns canonical identity ownership to Nowa Analytics, approves UUID as the initial generation strategy, requires one-time generation and persistence/reuse, and requires a persistent, client-isolated Episode Identity Registry that does not silently resolve ambiguous matches.

**CURRENT CONTRACT:** Customer Data Contract v1.1 describes one row per subscription, uses `subscription_id` as a unique string key and as the reference from snapshots, usage, and invoices, but does not define whether that ID is source-issued or canonical, episode-level identity. It does not define repeat-submission identity handling or historical episode mapping. Reactivation and episode behavior remain open in its DD-004 and DD-006.

**CURRENT IMPLEMENTATION:** The schemas enforce within-DataFrame keys. Header inspection has fixed, strict column allowlists. Ingestion retains CSV values as strings and requires customers, subscriptions, and snapshots; usage and invoices are optional. Normalization has per-dataset type maps. RI-001–RI-004 check reference existence, not whether the dependent record references the correct episode. TC-001/TC-002 compare dates within a subscription row. No identity registry, UUID issuer, cross-submission identity resolver, migration process, or episode-attribution workflow exists.

**RECOMMENDATION:** Prepare a future contract revision that defines one `subscriptions` row as one contractual episode and defines `subscription_id` as the canonical episode identifier, while preserving `customer_id` as the account key. Specify the UUID representation and submission/mapping process only after the relevant product and client decisions are recorded. Keep source subscription IDs, source episode IDs, and source namespace distinct from canonical identity; do not make source fields mandatory without evidence and approval. Dependent dataset references must resolve to the canonical episode ID only when supported by reliable source data or an explicitly approved mapping.

A major contract revision is likely if clients or consumers must change identifier semantics, required fields, key values, or dependent-dataset references. A precise version cannot be assigned until the full delta, compatibility path, and DD-EP-016 are resolved. This proposal is an assessment, not approval to revise v1.1 or implement the identity architecture.

## 2. Scope and evidence classification

This document assesses the current contract, approved episode architecture, current repository implementation, compatibility implications, and future decisions. It does not define final CSV schemas, require unverified source fields, or authorize code or contract changes.

Evidence labels used throughout:

| Label | Meaning |
|---|---|
| **APPROVED REQUIREMENT** | Explicitly approved by ADR-010 or approved EP-DEC decisions in the Episode Specification. |
| **CURRENT CONTRACT** | Requirement or definition currently stated in Customer Data Contract v1.1. |
| **CURRENT IMPLEMENTATION** | Behavior directly verified in current source code or tests. |
| **RECOMMENDATION** | Proposed contract or implementation direction for review; not an approved requirement. |
| **PENDING DECISION** | An explicit product/client decision or evidence item remains open. |
| **DEFERRED** | A topic is intentionally outside current scope or deferred by its governing decision. |

The review inspected the contract, ADR-009/ADR-010, the Subscription Episode & Lifecycle Decision Specification v0.4, both episode impact assessments, the Data Quality Specification and Implementation Architecture, all five Pandera schemas, header inspection, ingestion, normalization, RI/TC validators, and relevant tests. Existing CSV fixtures are generated in tests; no maintained CSV template or `.csv` example file was found in the repository file inventory. No live client data or source-system evidence was available.

## 3. Approved architectural requirements

### 3.1 Identity and prediction unit

- **APPROVED REQUIREMENT:** `customer_id` identifies a customer/account and is distinct from episode identity. One customer may have multiple contractual episodes.
- **APPROVED REQUIREMENT:** One contractual episode is the prediction entity and has an independent canonical identity.
- **APPROVED REQUIREMENT:** Reactivation following termination creates a new episode. Previous episodes remain historically identifiable and must not be overwritten or merged into the later episode.
- **APPROVED REQUIREMENT:** Nowa Analytics owns canonical episode identity. `subscription_id` is the canonical episode identifier for exactly one episode, stable throughout its lifecycle and never reassigned.
- **APPROVED REQUIREMENT:** UUID is the initial generation strategy. Generate once for an authoritatively established new episode, persist it, and reuse it on subsequent submissions and ingestion executions.

### 3.2 Registry and source identity

- **APPROVED REQUIREMENT:** A persistent Episode Identity Registry is required by ADR-010. It must support verified source-to-canonical associations, repeat-submission recognition, client isolation, history/lineage preservation, and explicit handling of ambiguous identity matches.
- **APPROVED REQUIREMENT:** Source subscription and episode identifiers remain separate from the canonical ID unless verified and explicitly mapped. A source subscription ID must not be assumed to identify one episode.
- **APPROVED REQUIREMENT:** Ambiguous records must not be assigned using dates, status, row order, or heuristic similarity as proof of identity.
- **PENDING DECISION:** UUID version/technical details, registry schema and storage, APIs, transaction/idempotency design, operating ownership, namespace representation, conflict resolution, retention/deletion, and how client CSV submissions participate remain open. The contract must not invent these as settled implementation details.

## 4. Current v1.1 contract baseline

| Topic | **CURRENT CONTRACT** |
|---|---|
| Prediction entity | Individual subscription; subscription-level labels/evaluation. Reactivation handling is not resolved. |
| Customer identity | `customer_id` is the associated customer account, is a customer primary key, and may be used for segmentation/reporting. The contract separately says it must not be a predictive feature; this assessment does not change that rule. |
| Subscription grain/key | One record per subscription; `subscription_id` is a required unique string primary key. The contract does not say that the row is one episode or that the ID is canonical, Nowa-issued, UUID-formatted, persistent across submissions, or never reassigned. |
| Subscription relationship | `subscriptions.customer_id` is a required FK to `customers.customer_id`. |
| Dependent keys | Snapshots use `(subscription_id, snapshot_date)`; usage uses `(subscription_id, usage_month)`; invoices use `invoice_id` as PK and `subscription_id` as FK. Their `subscription_id` fields are described as subscription identifiers. |
| Dataset presence | Customers, subscriptions, and snapshots are listed as required for their stated purpose; usage and invoices are optional. Current ingestion requires all three first datasets, including snapshots. |
| File conventions | Identifiers are strings; exact headers are prescribed; unknown columns are rejected by header inspection and strict schemas. Dates, types, nullable fields, controlled values, and existing checks are specified per dataset. |
| Versioning | Section 12 calls breaking changes to required fields, keys, or dataset structure “major”; backward-compatible additions or clarifications “minor”; corrections/documentation improvements “patch.” Examples use semantic-version-like numbers, while the current contract labels itself `1.1`. Structural changes must be documented and changes affecting schema validation, feature engineering, or model compatibility reviewed. |
| Open contract decisions | DD-004 (reactivation) and DD-006 (episodes) remain open in v1.1. Other client/product decisions appear in Section 13. |

The main conflict is semantic rather than a missing column: v1.1 permits a unique per-row `subscription_id` but does not establish that it is the stable, Nowa-owned identity of a contractual episode. ADR-010 now requires that canonical meaning and persistent lifecycle. Existing v1.1 inputs may therefore contain keys that cannot safely be adopted as canonical episode IDs.

## 5. Dataset-by-dataset impact matrix

| Dataset | **CURRENT CONTRACT** and implementation | Episode-aligned target / safe statement | Limits and decisions |
|---|---|---|---|
| `customers.csv` | One row per customer; `customer_id` PK. `CUSTOMER_SCHEMA` enforces a unique non-null string key. | **APPROVED REQUIREMENT:** Keep `customer_id` as customer/account identity and allow many episode rows to reference it. **RECOMMENDATION:** No episode identifier or other customer column is needed solely for episode identity. | Customer-level churn and risk aggregation are outside the episode identity decision (DD-EP-014/015 are deferred). The v1.1 feature-use rule is not changed here. |
| `subscriptions.csv` | One row per subscription; `subscription_id` PK and `customer_id` FK. Schema enforces within-frame uniqueness and required ID/customer/start/status checks. | **APPROVED REQUIREMENT:** Clarify row grain as one contractual episode; `subscription_id` is its canonical ID, and `customer_id` remains the account FK. Keep prior episode rows historically preserved. | **PENDING DECISION:** source-vs-Nowa supply mechanism at the CSV boundary, episode boundary/date semantics, source ID availability/reuse, and canonical scope exposed externally. UUID assignment alone cannot identify whether a row is new or existing. |
| `subscription_snapshots.csv` | Required for temporal modelling; unique `(subscription_id, snapshot_date)` and FK to subscriptions. | **RECOMMENDATION:** Preserve the composite key if `subscription_id` on each snapshot is the canonical episode ID. Define the FK as an episode reference. | **PENDING DECISION:** DD-EP-008. Historical rows without reliable episode linkage remain unresolved. Do not attribute by date, status, row order, or heuristic. Snapshot date convention DD-001 remains open. |
| `usage_monthly.csv` | Optional; unique `(subscription_id, usage_month)` and FK to subscriptions. | **RECOMMENDATION:** Preserve the composite key only if a usage row represents one defined period for one canonical episode and its `subscription_id` is that episode’s ID. | **PENDING DECISION:** DD-EP-009/010. Period bounds, partial periods, source granularity, and periods spanning episode boundaries remain undefined. Do not allocate or split usage across episodes without an approved policy. |
| `invoices.csv` | Optional; `invoice_id` PK and `subscription_id` FK. | **RECOMMENDATION:** Retain `invoice_id` as the invoice key; define `subscription_id` as canonical episode FK only where reliable episode linkage is available. | **PENDING DECISION:** DD-EP-011. Invoices covering multiple episodes/contract periods and historical ambiguous invoices cannot be allocated by invoice dates alone. |

## 6. Proposed target identity model

The following is a conceptual contract target, not a final field specification. “Canonical ID in interface” describes the desired meaning when a dataset is episode-attributed; the exact CSV exchange and registry/mapping process still require a decision.

| Identity / field | Type / nullability | Key or relationship | Classification and target meaning |
|---|---|---|---|
| `customer_id` | String; required in customers and subscriptions | Customers PK; subscriptions FK | **APPROVED REQUIREMENT:** Customer/account identity, distinct from episode identity. Existing customer table remains one row per account; many episodes may reference it. |
| `subscription_id` | String; required wherever the contract declares an episode relationship | Subscriptions PK; snapshots and episode-attributed usage/invoices reference subscriptions | **APPROVED REQUIREMENT:** Canonical episode ID owned by Nowa; UUID initial generation strategy; stable, persistent, never reassigned; one episode per ID. **PENDING DECISION:** UUID version, client/global interface uniqueness, CSV producer and transport/mapping mechanism, and transition from existing v1.1 IDs. Do not impose a UUID-version-specific regex absent a decision. |
| `source_subscription_id` | If represented, string; availability/nullability not established | No primary/foreign key or uniqueness guarantee approved | **RECOMMENDATION:** Separate source subscription-object identifier/provenance, retained and mapped when available. Never assume episode-level uniqueness; do not make mandatory without client evidence. |
| Source-system episode identifier | If present, string; availability/nullability not established | Potential registry mapping input after verification; not currently a contract key | **APPROVED REQUIREMENT:** Preserve/map when verified and available. **PENDING DECISION:** Field name, presence, scope, and source behavior. Do not assume it exists. |
| Source-system namespace/provenance | No CSV field type/nullability defined | Separate context for mapping keys as needed; not part of canonical UUID | **APPROVED REQUIREMENT:** Keep namespace/provenance distinct from canonical identity and client isolation. **PENDING DECISION:** Whether and how it is represented per client/system. |

**RECOMMENDATION:** Do not add episode identity columns to `customers.csv`. Do not use source IDs in place of canonical IDs without verified episode semantics and approved mapping. The final contract may define a boundary where inbound sources provide source identifiers while a trusted Nowa process resolves them to canonical `subscription_id`; that interface is not yet specified.

## 7. Proposed field-level changes and classification

| Proposed change | Classification | Assessment |
|---|---|---|
| State that each subscription row represents one contractual episode. | **APPROVED REQUIREMENT** as target meaning; **RECOMMENDATION** for contract wording | The episode identity is approved; row-grain clarification is needed. Whether existing client rows already conform must be discovered. Do not silently reinterpret legacy rows. |
| Define `subscription_id` as Nowa-owned canonical episode UUID, stable and never reassigned. | **APPROVED REQUIREMENT** | Add the approved semantics to a future contract. UUID version and the client-facing supply/mapping workflow remain unspecified. Applying it to current submitted values may be breaking. |
| Retain `customer_id` as customer/account PK/FK. | **APPROVED REQUIREMENT** | No new customer episode key. Existing relationship remains. |
| Add optional `source_subscription_id`. | **RECOMMENDATION**, conditional on source evidence and contract approval | ADR-010 distinguishes source IDs and says preserve/map when available; it does not mandate this CSV column. Keep nullability, uniqueness, namespace, and meaning conditional. |
| Add source episode ID field. | **PENDING DECISION** / conditional recommendation | Only if client source discovery proves such a field exists and product approves its representation. Do not make mandatory. |
| Add source-system namespace field(s). | **PENDING DECISION** | ADR-010 approves separate namespace context, not a particular CSV field or requiredness. Determine source topology and collisions first. |
| State that dependent `subscription_id` references identify canonical episodes. | **APPROVED REQUIREMENT** for correctly attributed episode records; **RECOMMENDATION** for contract/interface mechanics | RI existence alone cannot establish correct attribution. Historical or source records without reliable evidence require an approved mapping or remain unresolved. |
| Define lifecycle field meanings and episode boundary rules. | **PENDING DECISION** | Keep existing columns provisionally; do not infer new event semantics for start/end/cancellation/status. Resolve DD-EP-001 and DD-EP-005–007 first. |
| Define migration acceptance and handling of ambiguous legacy rows. | **PENDING DECISION** | Do not generate replacements or fabricate mappings. Product must approve reject/quarantine/review/exclusion criteria and dataset eligibility. |

No field addition or constraint in this table is an authorization to modify v1.1. Source identifier fields, namespace fields, input/output key exchange, and date/status lifecycle definitions require explicit contract review.

## 8. Contract-to-code/schema/test impact matrix

| Component | **CURRENT IMPLEMENTATION** | Impact if approved episode contract is adopted |
|---|---|---|
| CSV templates/examples | No maintained CSV template/example files were found. Unit/integration tests build temporary CSVs inline. | **RECOMMENDATION:** Create/update versioned templates and onboarding examples only after the final interface is approved; include multiple episodes per customer and stable repeated IDs without using live client data. |
| `DATASET_COLUMNS` / header inspection | `header_inspection.py` declares fixed exact required/optional headers and rejects unknown columns. | Register any approved source fields and decide whether versioned headers or explicit legacy compatibility are supported. Adding a field without this update causes header rejection. |
| CSV ingestion | `csv_ingestion.py` reads all values as strings; customers, subscriptions, snapshots are hard-required; usage/invoices are optional. No identity persistence or cross-submission orchestration. | No identity resolution can be achieved by the CSV reader alone. Required snapshot policy already differs from the contract’s “required for temporal modelling” language. Any required/optional dataset change affects loader behavior and compatibility. |
| `DATASET_COLUMN_TYPES` / type normalization | `type_normalization.py` maps known IDs to pandas strings and dates to UTC datetimes. | Add an approved source field to the appropriate type map. Canonical UUID validation/normalization and source-to-canonical mapping are not implemented; do not silently cast or generate IDs during ordinary normalization. |
| Pandera schemas | Five strict (`strict=True`, `coerce=False`) schemas; `add_missing_columns=True`. Keys and field-level rules are checked per DataFrame. No source-ID or namespace columns. | Add approved fields and constraints in lockstep with headers/normalization. `strict=True` means unregistered fields fail; UUID-format enforcement, if desired, is a new validation constraint. The schemas cannot prove cross-submission stability or correct historical attribution. |
| Primary/composite keys | Subscriptions unique `subscription_id`; snapshots `(subscription_id, snapshot_date)`; usage `(subscription_id, usage_month)`; invoices unique `invoice_id`. | Preserve key shapes only if each dependent row is at episode grain. Key uniqueness currently means within one DataFrame, not global identity uniqueness or persistent ID behavior. Do not add source-key uniqueness without evidence. |
| RI-001–RI-004 | Implemented; RI-001 checks customer reference; RI-002–004 check dependent `subscription_id` existence. | RI-001 remains valid per episode. RI-002–004 remain existence checks but cannot verify correct episode attribution. Add mapping/identity validation only after separately approved interface and scope; do not silently expand these rules. |
| TC-001–TC-007 | TC-001/002 are implemented for present date pairs within subscriptions. TC-003/TC-007 are pending in DQ specification; TC-004–006 also depend on cutoffs, conventions, or availability evidence. | Reconfirm TC-001/002 field meaning after episode dates are decided. TC-003 needs reliable snapshot-to-episode attribution and date semantics. TC-007 needs usage period bounds and cross-episode policy. Do not implement unresolved temporal checks. |
| Synthetic datasets and fixtures | Tests use inline/in-memory data and temporary CSVs, often with illustrative IDs such as `S001`/`subscription-1`; no maintained CSV fixtures found. | Update only after interface approval. Cover multiple episodes per customer, reactivation as distinct identity, repeat-submission stability, key reuse, unresolved links, and optional files. Use synthetic values and avoid claiming source-system behavior. |
| Unit/integration tests | Schema, normalization, ingestion, RI and TC unit tests exist. Integration test covers CSV ingestion; no DQ end-to-end identity/migration integration or registry tests exist. | Add contract/header/type/schema/key tests and registry/ingestion tests in separately authorized implementation. Test compatibility and ambiguity handling, not inferred assignment. |
| Client onboarding / migration | No client source discovery, episode registry, historical crosswalk, or migration service exists in inspected code. | **PENDING DECISION:** Require per-client source evidence, version transition plan, authoritative mapping, conflict disposition, and accepted-data criteria before onboarding episode-level history. |

## 9. Lifecycle and historical attribution constraints

**APPROVED REQUIREMENT:** Reactivation following termination creates a new episode and previous episodes remain preserved. This does not settle the exact contractual boundary or the effective event semantics used to identify termination.

For all dependent datasets, `subscription_id` can serve as a correct episode reference only when the source record carries a reliable canonical episode ID or an explicitly approved mapping resolves it. A matching ID that exists in `subscriptions.csv` proves existence only; it does not prove the record belongs to that episode.

- **PENDING DECISION — snapshots (DD-EP-008):** Records without reliable source evidence must remain unresolved. No assignment from dates, status, row order, or heuristics.
- **PENDING DECISION — usage (DD-EP-009/010):** Period boundaries, partial periods, and periods crossing episode boundaries need explicit semantics and policy. No implicit splitting or allocation.
- **PENDING DECISION — invoices (DD-EP-011):** Define whether each invoice belongs to one episode and how invoices spanning episodes or periods are represented. Dates alone are insufficient attribution evidence.
- **PENDING DECISION — migration (DD-EP-012):** Define evidence requirements and whether ambiguous historical data is rejected, quarantined, reviewed, or excluded under an approved policy. Preserve source lineage and historical records; do not fabricate attribution.

## 10. Migration and backward compatibility assessment

A v1.1 dataset may be syntactically valid but insufficient to establish episode identity. In particular, one row per source subscription and a unique ID in one file do not establish that IDs are episode-specific, stable across submissions, or not reused after reactivation. Current RI checks do not close this gap.

**RECOMMENDATION:** Before any cutover, inventory existing client exports and consumer assumptions; verify source IDs, reuse, historical coverage, and dependent dataset linkages; design and approve canonical ID provisioning and registry/mapping; then define migration acceptance criteria. Preserve prior identifiers as provenance where permitted, but do not automatically promote them to canonical IDs. Keep unresolved records explicitly unresolved until an approved disposition exists.

Compatibility considerations:

1. A new required canonical ID or changed key meaning may make old client exports invalid or semantically unsafe even when the column name remains `subscription_id`.
2. Existing strict header inspection rejects newly introduced columns until code is updated; a v1.1 consumer will not accept future fields by default.
3. Replacing IDs can require coordinated remapping of subscriptions, snapshots, usage, and invoices. Partial remapping can break references or misattribute history.
4. The current loader requires snapshots even though v1.1 says they are required for temporal modelling. Changing that behavior is a separate compatibility decision, not a consequence to infer from episode identity.
5. The identity registry and migration process are absent. CSV file changes alone do not ensure UUID reuse or idempotence across submissions.

## 11. Contract versioning analysis

Customer Data Contract v1.1 Section 12 defines breaking changes to required fields, keys, or dataset structure as major; backward-compatible additions/clarifications as minor; corrections/documentation improvements as patch. It also requires documentation and review of changes affecting schema validation, feature engineering, or model compatibility. The document labels the current contract `1.1`, while its patch example is `1.1.0 → 1.1.1`; this notation should be clarified by DD-EP-016 rather than silently normalized here.

| Scenario | Classification under current policy | Compatibility assessment |
|---|---|---|
| A. Clarify each subscription row represents one contractual episode | Minor if it is a backward-compatible clarification with no changed field/key behavior; otherwise major | The approved target meaning is clear, but whether existing client rows conform is unknown. If the clarification causes old rows/IDs to change meaning or split, it is breaking. |
| B. Define `subscription_id` as Nowa-owned canonical episode UUID | Major is likely if current clients supply source IDs or consumers rely on existing key semantics; otherwise potentially a minor clarification only after compatibility evidence | Canonical ownership/UUID strategy is approved, but supply mechanism, format/version, client-facing representation, and existing ID treatment are unresolved. A UUID format requirement and key reinterpretation would affect schema/consumer behavior. |
| C. Add optional `source_subscription_id` | Minor for a new consumer that accepts the optional field and continues to accept v1.1 files | The current strict v1.1 header/schema rejects unknown fields, so sending the new field to old code is incompatible. Source availability, field semantics, and approval remain required. |
| D. Add required `source_subscription_id` | Major | Existing sources may not provide it; v1.1 files lack it. ADR-010 explicitly does not make it mandatory. No such requirement is justified. |
| E. Add source-system namespace fields | Not classifiable until DD-EP-004 is resolved | Optional provenance could be a minor addition; required namespace structure would be major. Whether CSV fields are needed, their scope, and their requiredness are unknown. |
| F. Change dependent `subscription_id` attribution from source subscription reference to canonical episode reference | Major is likely | This changes FK semantics across snapshots, usage, and invoices and may require coordinated values/mapping. Existing IDs and historical links cannot be presumed compatible. |
| G. Change migration acceptance or required-dataset behavior | Not classifiable until DD-EP-012 and applicable product policy are resolved | Changing required files or acceptance/rejection behavior is likely major; a documentation-only clarification may be minor/patch. Exact effect depends on the approved migration and snapshot policy. |

**Version recommendation:** Do not assign a new contract version in this proposal. A documentation-only correction can follow the patch rule if it changes no normative behavior. A complete, compatible optional addition may qualify as minor. The likely adoption path that changes key meaning, required identifier semantics, or dependent references is a major change under the current policy, but DD-EP-016 and the compatibility inventory must decide the final version and transition. No `2.0` or other version is approved here.

## 12. Open decision register and dependencies

| Decision | What the contract can safely state now | What remains conditional or unspecified | Evidence / approval needed |
|---|---|---|---|
| DD-EP-001 — Contractual episode boundary (**PENDING DECISION**) | **APPROVED REQUIREMENT:** each canonical identity refers to one contractual episode; reactivation after termination creates a new one. | Exact start/end boundary and when a terminated episode is considered ended. | Product/client lifecycle definitions and source event semantics. |
| DD-EP-002 — Source subscription ID availability and reuse (**PENDING DECISION**) | Keep source subscription identity distinct; do not assume it is episode-unique. | Availability, stability, reuse, historical retention, and dependent-file coverage; no source field is mandatory now. | Per-client source documentation and historical extracts across reactivation/correction. |
| DD-EP-003 — Internal ID and Registry details (**PENDING DECISION**, partially resolved) | **APPROVED REQUIREMENT:** Nowa owns canonical identity; UUID initial strategy and persistent Registry requirement. | UUID version/format details, exact ID issuance and CSV exchange process, schema/storage/APIs, operations, conflict workflows, retention/deletion. | Product/platform design and operational ownership approval. |
| DD-EP-004 — Source-system namespace (**PENDING DECISION**) | Namespace is separate provenance/mapping context; client isolation remains required. | Whether namespace fields are required and how systems/tenants/partitions are represented. | Per-client source inventory and collision/tenant semantics. |
| DD-EP-005 — Cancellation event semantics (**PENDING DECISION**) | Preserve current cancellation fields without inferring new meanings. | Effective cancellation/termination criteria and relation of cancellation date to end date/status. | Product policy plus source event definitions. |
| DD-EP-006 — Renewals/extensions (**PENDING DECISION**) | Preserve episode history; do not silently overwrite earlier episodes. | Whether renewal/extension continues an episode or creates a new contractual relationship. | Product/client contract lifecycle rules. |
| DD-EP-007 — Suspension/pause (**PENDING DECISION**) | Existing statuses remain subject to current contract; identity remains episode-level. | Whether suspension/paused status changes episode continuity or churn treatment. | Product definitions and client status mapping. |
| DD-EP-008 — Snapshot attribution (**PENDING DECISION**) | Snapshot `subscription_id` may refer to canonical episode when reliably identified. | Historical rows lacking episode evidence cannot be assigned; date convention remains separate DD-001. | Source linkage fields or approved auditable mapping; date semantics. |
| DD-EP-009 — Usage attribution (**PENDING DECISION**) | Use canonical episode reference only when attribution is reliable. | Source linkage and episode represented by usage rows. | Source data/field lineage and client approval. |
| DD-EP-010 — Periods across episodes (**PENDING DECISION**) | Do not invent period splits or allocation. | Partial-period, boundary inclusion, cross-episode usage policy. | Approved product policy and usage period semantics. |
| DD-EP-011 — Invoice attribution (**PENDING DECISION**) | Use canonical episode reference only with reliable linkage. | Invoices spanning episodes or service periods and historical ambiguous invoices. | Financial source semantics, invoice linkage, approved mapping/allocation policy. |
| DD-EP-012 — Historical migration acceptance (**PENDING DECISION**) | Preserve records and source lineage; ambiguous identity remains unresolved. | Reject/quarantine/manual review/exclusion criteria and eligibility consequences. | Product decision based on per-client evidence and data quality/completeness impact. |
| DD-EP-013 — Episode-level churn qualification (**PENDING DECISION**) | Episode is the prediction entity. | Which contractual events qualify as churn, including termination timing and exclusions. | Product churn definition and client contract semantics. |
| DD-EP-014 — Customer-level churn (**DEFERRED**) | The initial prediction entity and contractual churn scope remain episode-level. | Customer-level churn is intentionally outside the initial episode-level contractual churn scope. | Any future scope change requires separate product review. |
| DD-EP-015 — Customer-level risk aggregation (**DEFERRED**) | Customer identity remains distinct from episode identity; aggregation is outside this proposal. | Customer-level risk aggregation is intentionally outside the initial episode-level contractual churn scope. | Any future scope change requires separate product review. |
| DD-EP-016 — Contract version/backward compatibility (**PENDING DECISION**) | Apply v1.1 Section 12 classifications; review schema/model compatibility. | Final delta, version notation, transition/dual support, and deprecation policy. | Enumerated approved delta, affected-client inventory, compatibility review, product approval. |
| DD-EP-017 — Model Evaluation Grouping and Temporal Strategy (**PENDING_PRODUCT_DECISION**) | Evaluation must account for temporal structure and multiple episodes per customer when relevant. | The temporal evaluation strategy, customer grouping approach, and controls for information leakage between episodes belonging to the same customer remain undecided. This is a downstream modelling/evaluation decision, not an immediate CSV contract structure requirement. | Product/modeling decision informed by intended evaluation objective and episode data structure; no split strategy is prescribed here. |

Other open contract decisions (including snapshot convention, cutoff/timezone, revenue/currency, and client status mapping) remain governed by the contract and Episode Specification; this proposal does not resolve or restate them as approved.

## 13. Recommended implementation sequence

All implementation steps require their own authorization after proposal review. Recommended order:

1. **RECOMMENDATION:** Review and approve the product-level contract delta and preserve the approved episode identity decisions.
2. **PENDING DECISION:** Complete relevant client source discovery and resolve DD-EP-001–007, DD-EP-008–013, and DD-EP-016 to the extent required by the chosen release scope. Identify explicitly which dependent datasets can provide reliable episode attribution.
3. **RECOMMENDATION:** Specify canonical ID exchange and mapping/Registry interfaces, ambiguity outcomes, client isolation, history retention, and migration acceptance before deciding required versus optional source fields.
4. **RECOMMENDATION:** Enumerate the exact contract delta per dataset and classify each field/key/behavior change under v1.1 Section 12. Decide whether a major compatibility path is needed; then assign a version through DD-EP-016.
5. **RECOMMENDATION:** Update the contract, headers/templates, type maps, schemas, RI/TC implementation where approved, synthetic fixtures, and tests as one coordinated implementation plan. Keep changes that do not depend on resolved episode semantics separate.
6. **RECOMMENDATION:** Validate representative, privacy-approved client samples and repeated-submission/migration cases during onboarding; unresolved identity must follow approved policy rather than heuristic assignment.

DD-EP-017 is a downstream modelling/evaluation dependency: resolve it before selecting or implementing evaluation grouping and temporal strategy, but do not treat it as a prerequisite for contract changes that do not affect modelling or evaluation design.

## 14. Explicit implementation boundaries

This proposal does not authorize or perform:

- Changes to Customer Data Contract v1.1, ADR-009, ADR-010, Episode Specification, or Data Quality documents.
- New or modified CSV fields, templates, headers, ingestion requirements, normalization rules, Pandera schemas, RI/TC behavior, fixtures, or tests.
- UUID generation, Registry creation, identity matching, mapping persistence, orchestration, client migration, or source-system integration.
- Source-system claims, historical ID splits, episode attribution, invoice allocation, or usage allocation without evidence and approval.
- Changes to feature-selection policy, churn definition, financial interpretation, or model behavior.

## 15. References inspected

- `docs/03_architecture/architecture_decisions.md` — ADR-003 and ADR-009.
- `docs/03_architecture/adr_episode_identity_and_identifier_management.md` — ADR-010.
- `docs/04_data/customer_data_contract.md` — v1.1, especially Sections 2–7, 12–14.
- `docs/04_data/subscription_episode_lifecycle_decision_specification.md` — approved EP-DEC-001–005, identity decisions, lifecycle and migration recommendations, DD-EP-001–017.
- `docs/04_data/subscription_episode_data_contract_impact_assessment.md`.
- `docs/04_data/subscription_episode_identity_identifier_strategy_assessment.md`.
- `docs/04_data/data_quality_specification.md` and `docs/04_data/data_quality_implementation_architecture.md`.
- `src/nowa_customer_intelligence/data/schemas/{customers,subscriptions,subscription_snapshots,usage_monthly,invoices}.py`.
- `src/nowa_customer_intelligence/data/ingestion/header_inspection.py`, `csv_ingestion.py`.
- `src/nowa_customer_intelligence/data/preprocessing/type_normalization.py`.
- `src/nowa_customer_intelligence/data/validation/referential_integrity.py`, `temporal_consistency.py`.
- `tests/unit/data/schemas/`, `tests/unit/data/preprocessing/test_type_normalization.py`, `tests/unit/data/test_header_inspection.py`, `tests/unit/data/test_csv_ingestion.py`, `tests/unit/data/validation/`, and `tests/integration/test_csv_ingestion.py`.

---

**Review status:** This is a proposal for review. It is not authorization to revise the contract or implement the architecture.
