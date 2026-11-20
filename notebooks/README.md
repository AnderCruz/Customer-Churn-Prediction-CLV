# Notebooks

Use numbered notebooks for exploration and experiments. Promote reusable logic into `src/`; avoid treating notebooks as production pipelines.

## Phase 04 data understanding

Use the project Python environment with the notebook extras installed, for example
`python -m pip install -e '.[notebooks]'`. Start the kernel from the repository root
or a subdirectory. Run each notebook from top to bottom in a fresh Python 3 kernel.

1. [Customer and subscription EDA](01_data_understanding/01_customer_subscription_eda.ipynb)
2. [Churn distribution and cohort analysis](01_data_understanding/02_churn_distribution_and_cohort_analysis.ipynb)
3. [Revenue, usage and temporal analysis](01_data_understanding/03_revenue_usage_and_temporal_analysis.ipynb)

Fieldwise is reconstructed through the supported development interface in a temporary
workspace. Notebooks 1 and 3 verify the approved local Misata and UCI files, respectively.
Use the separate [source acquisition commands](../docs/04_data/data_sources_and_governance.md#82-local-acquisition-and-analytical-access)
to prepare missing inputs before opening a notebook. Notebook execution is offline.

For automated end-to-end verification, execute each file with `nbclient` in its own
kernel using the notebook directory as the working directory. Store executed copies
outside Git. The repository notebooks contain source cells only. The retail notebook
streams both sheets twice, once for source validation and once for descriptive aggregation.

Use a clean Python 3.12 environment for verification. The notebooks do not use
PySpark. An unrelated PySpark installation in a shared environment can cause
Pandera to load an incompatible optional backend.

## Phase 05 feature engineering

[Fieldwise Cloud feature engineering analysis](02_feature_engineering/04_feature_engineering_analysis.ipynb)
uses the accepted bundle under `data/processed/phase05-fieldwise-final/`. Prepare
that local input using the [documented replay procedure](../docs/07_project_management/implementation_plan_and_roadmap.md#182-local-replay-and-integrity)
and the established Phase 05 Registry if the bundle is absent. A fresh Registry
creates different canonical IDs. The notebook reads and verifies the retained
bundle without opening the Registry or acquiring data.

Use a fresh Python 3.12 kernel with the notebook extras above. Executed copies
should remain local and outside Git. Outcomes are used for aggregate cohort
counts and do not enter the predictor analysis.
