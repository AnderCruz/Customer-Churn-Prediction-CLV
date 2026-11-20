"""Check offline analytical notebook sources and their reproducible reference inputs."""

import ast
import json
import socket
from pathlib import Path

import pytest

from nowa_customer_intelligence.data.eda_inputs import fieldwise_reference, reference_outcomes
from nowa_customer_intelligence.data.synthetic.feature_matrix import FEATURE_SPECS

_NOTEBOOKS = Path(__file__).resolve().parents[2] / "notebooks"
_PHASE05 = "02_feature_engineering/04_feature_engineering_analysis.ipynb"
_PATHS = (
    "01_data_understanding/01_customer_subscription_eda.ipynb",
    "01_data_understanding/02_churn_distribution_and_cohort_analysis.ipynb",
    "01_data_understanding/03_revenue_usage_and_temporal_analysis.ipynb",
    _PHASE05,
)
_OUT_OF_SCOPE_IMPORTS = {
    "requests",
    "socket",
    "urllib",
    "sklearn",
    "tensorflow",
    "torch",
    "xgboost",
    "lightgbm",
}
_OUT_OF_SCOPE_CALLS = {"acquire", "download", "fit", "fit_transform", "savefig", "write_text"}


@pytest.mark.parametrize("relative_path", _PATHS)
def test_notebook_source_is_valid_clean_and_descriptive(relative_path: str) -> None:
    path = _NOTEBOOKS / relative_path
    document = json.loads(path.read_text(encoding="utf-8"))
    assert document["nbformat"] == 4
    assert document["metadata"]["kernelspec"]["language"] == "python"
    cells = document["cells"]
    assert len(cells) == len({cell["id"] for cell in cells})
    assert cells[0]["cell_type"] == "markdown"
    assert cells[-1]["cell_type"] == "markdown"
    assert any(cell["cell_type"] == "code" for cell in cells)
    for cell in cells:
        source = "".join(cell["source"])
        assert source.strip()
        if cell["cell_type"] == "markdown":
            continue
        assert cell["cell_type"] == "code"
        assert cell["execution_count"] is None
        assert not cell["outputs"]
        for node in ast.walk(ast.parse(source, filename=str(path))):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert alias.name.split(".")[0] not in _OUT_OF_SCOPE_IMPORTS
            elif isinstance(node, ast.ImportFrom):
                assert (node.module or "").split(".")[0] not in _OUT_OF_SCOPE_IMPORTS
            elif isinstance(node, ast.Call):
                if isinstance(node.func, ast.Attribute):
                    assert node.func.attr not in _OUT_OF_SCOPE_CALLS
                elif isinstance(node.func, ast.Name):
                    assert node.func.id not in _OUT_OF_SCOPE_CALLS


def test_phase05_dictionary_covers_exact_registry_in_order() -> None:
    document = json.loads((_NOTEBOOKS / _PHASE05).read_text(encoding="utf-8"))
    code = "\n\n".join(
        "".join(cell["source"]) for cell in document["cells"] if cell["cell_type"] == "code"
    )
    module = ast.parse(code)
    dictionaries = [
        ast.literal_eval(node.value)
        for node in module.body
        if isinstance(node, ast.Assign)
        and any(
            isinstance(target, ast.Name) and target.id == "field_context" for target in node.targets
        )
    ]
    assert len(dictionaries) == 1
    assert tuple(dictionaries[0]) == tuple(spec.name for spec in FEATURE_SPECS)
    assert all(len(fields) == 3 and all(fields) for fields in dictionaries[0].values())


def test_reference_inputs_run_offline_and_clean_up(monkeypatch: pytest.MonkeyPatch) -> None:
    def deny_socket(*args, **kwargs):
        pytest.fail("EDA data reconstruction must not use the network.")

    monkeypatch.setattr(socket, "socket", deny_socket)
    with fieldwise_reference() as (run, export):
        assert {row.dataset: row.records for row in run.provenance.inventory} == {
            "customers": 1000,
            "subscriptions": 1200,
            "invoices": 14787,
            "usage_monthly": 16547,
            "subscription_snapshots": 18661,
        }
        assert reference_outcomes(run, export).counts == {
            "confirmed_positive": 151,
            "confirmed_negative": 14212,
            "right_censored": 895,
            "pending_ascertainment": 0,
            "ineligible": 3403,
        }
    assert not export.parent.exists()
