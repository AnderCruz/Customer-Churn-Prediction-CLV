"""Check Phase 04 notebook sources and their reproducible offline reference input."""

import ast
import json
import socket
from pathlib import Path

import pytest

from nowa_customer_intelligence.data.eda_inputs import fieldwise_reference, reference_outcomes

_NOTEBOOKS = Path(__file__).resolve().parents[2] / "notebooks" / "01_data_understanding"
_NAMES = (
    "01_customer_subscription_eda",
    "02_churn_distribution_and_cohort_analysis",
    "03_revenue_usage_and_temporal_analysis",
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


@pytest.mark.parametrize("name", _NAMES)
def test_notebook_source_is_valid_clean_and_descriptive(name: str) -> None:
    path = _NOTEBOOKS / f"{name}.ipynb"
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
