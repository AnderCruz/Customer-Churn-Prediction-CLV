# Modelling and Evaluation Strategy

**Document ID:** NCI-ML-001  
**Version:** 0.2  
**Status:** Draft for review

## 1. Modelling principles

- Define the business event before selecting an algorithm.
- Use a simple baseline before complex models.
- Prevent target leakage through point-in-time feature construction.
- Use temporal validation when timestamps and data volume permit.
- Evaluate probability calibration, not only ranking performance.
- Select thresholds based on business capacity and error costs.
- Keep contractual churn and non-contractual inactivity separate.
- Document model limitations and intended use.

## 2. Churn prediction

### Initial candidate models

1. Dummy / prevalence baseline.
2. Logistic Regression.
3. Random Forest.
4. Gradient boosting: LightGBM, XGBoost, or CatBoost.

MLP, sequence models, and other deep-learning methods may be considered only if the dataset and use case justify them.

### Evaluation metrics

- PR-AUC.
- ROC-AUC.
- Precision.
- Recall.
- F1-score.
- Confusion matrix.
- Brier score or another calibration measure.
- Precision/recall at an operational review capacity.

Accuracy must not be used as the sole performance measure, particularly where churn is relatively infrequent.

## 3. Target and temporal design

Each modelling dataset must specify:
- Entity being scored (customer, account, or subscription).
- Observation window.
- Prediction horizon.
- Churn event definition.
- Data cutoff.
- Feature availability rules.
- Treatment of reactivation, pauses, and failed payment.

Initial experiment hypotheses may use a 90-day observation window and 30-day prediction horizon, but these must be validated against the actual event cadence and data.

## 4. CLV estimation

CLV methodology depends on the business model and data availability.

Potential approaches:
- Contractual subscription: expected future recurring revenue or contribution margin using tenure, plan, renewal, and churn assumptions.
- Non-contractual repeat purchasing: BG/NBD and Gamma-Gamma where their assumptions are appropriate.
- Supervised regression: only when a defensible future-value target and temporal training design are available.

The output must state:
- Revenue or contribution-margin basis.
- Forecast horizon.
- Discounting treatment, if any.
- Cost assumptions, if any.
- Model limitations.

Historical spend must not be presented as predictive CLV.

## 5. Customer segmentation

Potential approaches:
- RFM analysis where transaction data supports it.
- K-Means after scaling and feature review.
- Hierarchical clustering for exploratory analysis.
- Other methods only where justified.

Segments must be profiled and reviewed for stability and business interpretability. Cluster labels such as “Champions” or “At Risk” are descriptive business labels, not inherent truths produced by the algorithm.

## 6. Revenue at risk

A simple expected exposure estimate may be:

`Expected Revenue Exposure = Churn Probability × Future Revenue over the defined horizon`

The calculation must:
- Use a consistent time horizon.
- State whether revenue is gross or net of relevant adjustments.
- Avoid double counting overlapping subscriptions.
- Distinguish exposure from recoverable revenue.
- Avoid implying campaign uplift without causal evidence.

## 7. Explainability

Use SHAP or another suitable method to provide:
- Global feature contribution summaries.
- Individual prediction explanations.
- Clear caveats that feature contributions are not causal effects.

Explanations should be checked for stability and should not expose sensitive attributes or inappropriate proxies without a justified and reviewed purpose.

## 8. Model selection and release

A candidate model is eligible for release when:
- It beats or provides a justified trade-off against the baseline.
- Evaluation is leakage-safe.
- Calibration is assessed.
- Thresholds are selected against operational requirements.
- Performance and limitations are documented.
- Reproducibility and artefact tracking are in place.
- Relevant fairness and privacy risks have been reviewed.

## 9. Monitoring and retraining

Monitor:
- Input schema and data-quality failures.
- Feature distribution changes.
- Prediction distribution changes.
- Label-based performance when outcomes become available.
- Calibration changes.
- Model and data version.

Retraining should be triggered by documented evidence and reviewed before promotion. Do not automatically retrain and deploy a model solely because a drift metric crossed a threshold.
