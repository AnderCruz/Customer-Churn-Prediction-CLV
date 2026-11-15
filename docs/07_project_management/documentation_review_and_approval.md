# Documentation Review and Approval Register

**Document ID:** NCI-APR-001  
**Version:** 0.3  
**Review date:** 14 November 2026  
**Review status:** Conditionally approved as the baseline for repository and development-environment setup  
**Approver:** Product owner approval required

## 1. Purpose

This register records the quality review of the Nowa Customer Intelligence documentation pack v0.2 and defines the conditions for approval.

This is a project-documentation review. It is not a legal compliance certification, security certification, production-readiness approval, or validation of model performance.

## 2. Review summary

The documentation provides a coherent initial foundation for a focused SaaS/subscription churn analytics MVP. The product scope, modular-monolith approach, local-first development strategy, client data isolation principle, and separation of contractual churn from non-contractual inactivity are appropriate for the current stage.

**Recommendation:** approve the documentation as a controlled baseline for Phase 1 (GitHub repository and development environment setup), subject to the decisions and clarifications below being tracked.

The pack is not approved as a specification for processing live client personal data or deploying a production service.

## 3. Review findings

| ID | Area | Finding | Classification | Required action |
|---|---|---|---|---|
| REV-001 | Product scope | Initial focus on UK SaaS/subscription businesses is clear. | Accepted | Validate through customer discovery; do not treat the ICP size range as a hard technical constraint. |
| REV-002 | Churn definition | Contractual churn is the initial use case, but event rules vary by client. | Open, non-blocking for repository setup | Define cancellation, non-renewal, pause, failed-payment, reactivation, and entity-level rules during data discovery. |
| REV-003 | Prediction horizon | 90-day observation and 30-day prediction are hypotheses only. | Open, non-blocking | Confirm after reviewing event frequency, data history, and business intervention lead time. |
| REV-004 | Data sources | IBM Telco is a benchmark, not representative UK SaaS data. Synthetic SaaS data is for engineering tests only. | Accepted with limitation | Record exact source, version, licence, download date, and terms before use. Do not claim real-world performance from synthetic data. |
| REV-005 | CLV | CLV method depends on contractual model, available history, and value basis. | Open, non-blocking for repository setup | Select revenue or contribution-margin basis and forecast horizon before training a CLV model. |
| REV-006 | Revenue at risk | Exposure calculation is not equivalent to recoverable revenue or campaign uplift. | Accepted | Keep these measures distinct in dashboard labels and documentation. |
| REV-007 | API scope | API is optional/Should in the MVP, while an API latency target is stated. | Clarification required | Treat API performance target as applicable only if the API is included in the release scope. |
| REV-008 | Persistence | PostgreSQL is proposed, but MVP may use files for early experiments. | Clarification required | Make database adoption a phase decision; do not add database complexity before the dashboard/persistence need is confirmed. |
| REV-009 | Client isolation | Client isolation is a design principle, but the detailed deployment boundary is not yet specified. | Open, before pilot | Define per-client storage, credentials, model registry/artifact paths, backups, and access boundaries before any client pilot. |
| REV-010 | UK GDPR | Governance topics are identified, but obligations are deployment-specific. | Open, before live data | Obtain client/legal/privacy review of roles, lawful basis, transparency, retention, DPIA need, profiling, and data-subject rights. |
| REV-011 | Model evaluation | Appropriate metrics and temporal validation are specified. | Accepted | Set client-specific performance and operating thresholds only after baseline analysis and intervention-capacity review. |
| REV-012 | Production operations | Monitoring and rollback are outlined but not yet operationally specified. | Open, before production | Create runbooks, backup/restore tests, incident process, alert thresholds, and model promotion controls. |

## 4. Required clarifications to the baseline

The following interpretations apply until the relevant phase makes a more specific decision:

1. **MVP data ingestion:** CSV-based ingestion is the required initial path. Native CRM/billing integrations are out of scope.
2. **MVP application:** Streamlit dashboard and batch scoring are core. FastAPI and PostgreSQL remain conditional components and may be deferred if they do not add value to the first demonstration.
3. **MVP modelling:** contractual churn for a SaaS/subscription context is the primary modelling target. IBM Telco is a technical benchmark only; a synthetic SaaS dataset is for pipeline and application testing.
4. **CLV:** no algorithm is pre-selected as the universal solution. Method selection follows the client business model and data-readiness assessment.
5. **Cloud:** AWS is a future deployment option, not a dependency for the initial development milestone.
6. **Privacy:** no live client personal data may be introduced until the applicable governance, security, contractual, and privacy checks have been completed.

## 5. Approval scope

### Approved for the next development phase, subject to product-owner sign-off

- Create the GitHub repository.
- Establish the Python development environment.
- Create the documented project structure.
- Add configuration, logging, and test foundations.
- Add dependency and code-quality tooling.
- Add a basic GitHub Actions CI workflow.
- Prepare Docker-based local development where useful.
- Continue using public or clearly labelled synthetic development data only.

### Not approved by this review

- Processing live client personal data.
- Production deployment.
- External customer access.
- Automated retention actions.
- Solely automated decisions with legal or similarly significant effects.
- Claims of validated churn reduction or revenue uplift.
- Treating synthetic-data metrics as evidence of production model quality.

## 6. Product-owner decisions

The product owner approved the following baseline decisions on 14 November 2026:

| Decision ID | Decision | Proposed baseline |
|---|---|---|
| PO-001 | Initial target segment | UK SaaS and subscription businesses |
| PO-002 | Initial churn use case | Contractual churn |
| PO-003 | Initial data interface | Documented CSV templates |
| PO-004 | Initial architecture | Modular monolith |
| PO-005 | Initial development environment | Local-first, Python 3.12 |
| PO-006 | Initial dashboard | Streamlit |
| PO-007 | Cloud timing | AWS after local MVP validation |
| PO-008 | Client data strategy | Client-specific data and model isolation; no shared cross-client training by default |

## 7. Approval record

| Role | Name | Decision | Date | Notes |
|---|---|---|---|---|
| Product Owner | Ander Cruz | Approved | 14 Nov 2026 | User approved PO-001 to PO-008 and authorised Phase 1 in the project conversation. |
| Technical Review | Nowa Customer Intelligence documentation review | Recommended: conditional approval | 14 Nov 2026 | Approved for repository/environment setup only |

## 8. Change control

After product-owner approval, this documentation pack becomes the baseline for Phase 1. Any material changes to product scope, prediction target, data handling, architecture, or deployment assumptions must be recorded in the relevant document and, where appropriate, an Architecture Decision Record.

## 9. Review conclusion

The documentation baseline is approved by the product owner for repository and local development-environment setup. This approval does not authorise live client-data processing or production deployment.

The open items above are deliberately scheduled for the phases where the required evidence becomes available. They do not need to be prematurely resolved before creating the repository, but they must be resolved before the affected modelling, pilot, or production activities.
