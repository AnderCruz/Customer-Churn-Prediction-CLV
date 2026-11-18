"""Verify the bounded synthetic configuration intake independently of execution."""

import io
import random
import traceback
from pathlib import Path

import pytest
import yaml

from nowa_customer_intelligence.data.synthetic import configuration
from nowa_customer_intelligence.data.synthetic.configuration import (
    ConfigurationError,
    ConfigurationParseError,
    ConfigurationSchemaError,
    ConfigurationSizeLimitError,
    ConfigurationVersionError,
    ValidatedConfiguration,
    load_configuration,
    resolve_configuration,
)
from nowa_customer_intelligence.pipeline import execution

_VALID = b"""config_schema_version: 1
base:
  population:
    customer_count: 1000
    episode_count_min: 1100
    episode_count_max: 1400
  history:
    start_date: '2023-01-01'
    cutoff_date: "2026-01-01"
  master_seed: 0
  workflow: BASIC
  execution_scope: configuration_only
  requested_outputs: [customers.csv, subscriptions.csv]
  policy_refs:
    contract_version: '1.1'
    business_model_version: '0.2'
    snapshot_decision: PD-006
scenarios:
  baseline:
    scenario_version: 1
"""


def test_loads_complete_structural_base_without_materialising_defaults() -> None:
    result = load_configuration(_VALID)
    assert isinstance(result, ValidatedConfiguration)
    assert result.config_schema_version == 1
    assert result.base.population.customer_count == 1000
    assert result.base.history.start_date == "2023-01-01"
    assert result.base.master_seed == 0
    assert result.base.workflow == "BASIC"
    assert result.base.execution_scope == "configuration_only"
    assert result.base.requested_outputs == ["customers.csv", "subscriptions.csv"]
    assert result.base.policy_refs.contract_version == "1.1"
    assert result.base.diagnostics is None
    assert "diagnostics" not in result.base.model_fields_set
    assert result.scenarios["baseline"].patch is None


def test_supports_empty_and_partial_patches_and_resolver_safe_string_prefixes() -> None:
    raw = (
        _VALID
        + b"""    patch: {}
  truefuture:
    scenario_version: 2
    patch:
      history: {cutoff_date: '2024-02-29'}
      population: {episode_count_max: 1900}
      master_seed: 12
      diagnostics: {level: WARNING}
"""
    )
    result = load_configuration(raw)
    empty = result.scenarios["baseline"].patch
    patch = result.scenarios["truefuture"].patch
    assert empty is not None and empty.model_fields_set == set()
    assert patch is not None and patch.history is not None and patch.population is not None
    assert patch.history.cutoff_date == "2024-02-29"
    assert patch.history.start_date is None
    assert patch.population.episode_count_max == 1900
    assert patch.population.episode_count_min is None
    assert patch.master_seed == 12
    assert patch.diagnostics is not None and patch.diagnostics.level == "WARNING"
    assert result.base.population.episode_count_max == 1400


@pytest.mark.parametrize(
    "raw",
    [
        b"",
        b"---",
        b"[]",
        b"base: [unclosed",
        b"base: \xff",
        b"base: \x00",
        rb'base: "\U00110000"',
        rb'base: "\uD800"',
        b"base: {}\n---\nscenarios: {}",
        b"base: &anchor {}",
        b"base: *anchor",
        b"base: {'<<': {}}",
        b"base: {<<: {}}",
        b"base: {same: 1, 'same': 2}",
        b'base: {same: 1, "\\x73ame": 2}',
        b"base: {same: 1, same: 2}",
        b"base: !!map {}",
        b"base: !custom {}",
        b"base: !!python/name:os.getcwd ''",
        b"%YAML 1.1\n---\nbase: {}",
        b"%TAG !e! tag:example.com,2026:\n---\nbase: {}",
        b"%UNKNOWN arg\n---\nbase: {}",
        b"base: {[key]: value}",
        b"base: {true: value}",
        b"base: {42: value}",
        b"base: {null: value}",
        b"base: {empty: }",
    ],
)
def test_rejects_prohibited_input_before_construction(
    raw: bytes, monkeypatch: pytest.MonkeyPatch
) -> None:
    def unexpected_construction(*args: object, **kwargs: object) -> None:
        pytest.fail("YAML construction ran before intake rejection.")

    monkeypatch.setattr(configuration.yaml, "load", unexpected_construction)
    with pytest.raises(ConfigurationParseError, match="CONFIG_PARSE_ERROR"):
        load_configuration(raw)


@pytest.mark.parametrize(
    "value",
    [
        b"yes",
        b"OFF",
        b"False",
        b"NULL",
        b"~",
        b"00",
        b"01",
        b"089",
        b"+1",
        b"-0",
        b"0o12",
        b"0x12",
        b"0b10",
        b"1_000",
        b"1:99",
        b"1.0",
        b"1e4",
        b".inf",
        b".NaN",
        b"2024-02-29",
        b"2024-02-29T12:00:00Z",
    ],
)
def test_rejects_ambiguous_plain_scalars(value: bytes) -> None:
    with pytest.raises(ConfigurationParseError, match="CONFIG_PARSE_ERROR"):
        load_configuration(_VALID.replace(b"master_seed: 0", b"master_seed: " + value))


@pytest.mark.parametrize(
    "raw",
    [
        _VALID.replace(b"'2023-01-01'", b"2023-01-01"),
        _VALID.replace(b"'2023-01-01'", b">-\n      2023-01-01"),
        _VALID + b"    patch: {history: {start_date: 20240101}}\n",
    ],
)
def test_history_dates_require_single_or_double_quotes(raw: bytes) -> None:
    with pytest.raises(ConfigurationParseError, match="CONFIG_PARSE_ERROR"):
        load_configuration(raw)


def _resource_inputs() -> list[tuple[str, bytes, bytes, bool]]:
    size = _VALID + b"#" + b" " * (65_536 - len(_VALID) - 1)
    scenarios = _VALID + b"".join(
        f"  case-{i}: {{scenario_version: 1}}\n".encode() for i in range(1, 32)
    )
    nodes = b"{items: [" + b"x," * 2_045 + b"]}"
    depth = b"items: " + b"[" * 7 + b"x" + b"]" * 7
    scalar = ('items: "' + "é" * 255 + r"\u00e9" + '"').encode()
    return [
        ("document_bytes", size, size + b" ", True),
        ("scenarios", scenarios, scenarios + b"  excess: {scenario_version: 1}\n", True),
        ("nodes", nodes, nodes.replace(b"x,]", b"x,x,]"), False),
        ("collection_depth", depth, depth.replace(b"x", b"[x]"), False),
        ("scalar_length", scalar, scalar[:-1] + b'x"', False),
        (
            "integer_representation",
            b"item: 9223372036854775807",
            b"item: 9223372036854775808",
            False,
        ),
        (
            "integer_representation",
            b"item: -9223372036854775808",
            b"item: -9223372036854775809",
            False,
        ),
        ("integer_representation", b"item: 0", b"item: " + b"9" * 256, False),
    ]


@pytest.mark.parametrize(("limit", "within", "beyond", "valid"), _resource_inputs())
def test_exact_intake_boundaries(
    limit: str, within: bytes, beyond: bytes, valid: bool, monkeypatch: pytest.MonkeyPatch
) -> None:
    if valid:
        assert isinstance(load_configuration(within), ValidatedConfiguration)
    else:
        with pytest.raises(ConfigurationSchemaError):
            load_configuration(within)

    def unexpected_construction(*args: object, **kwargs: object) -> None:
        pytest.fail("An over-budget document reached YAML construction.")

    monkeypatch.setattr(configuration.yaml, "load", unexpected_construction)
    with pytest.raises(ConfigurationSizeLimitError, match="CONFIG_SIZE_LIMIT_EXCEEDED") as caught:
        load_configuration(beyond)
    assert caught.value.limit == limit
    assert caught.value.issues == ()
    assert caught.value.line is None
    assert caught.value.column is None


def test_scalar_length_limit_also_covers_keys() -> None:
    with pytest.raises(ConfigurationSizeLimitError) as caught:
        load_configuration(b"k" * 257 + b": value")
    assert caught.value.limit == "scalar_length"


def test_size_limit_precedes_utf8_decoding() -> None:
    with pytest.raises(ConfigurationSizeLimitError) as caught:
        load_configuration(b"\xff" * 65_537)
    assert caught.value.limit == "document_bytes"


def test_dispatches_unsupported_integer_versions_before_other_schema_checks() -> None:
    with pytest.raises(ConfigurationVersionError, match="CONFIG_SCHEMA_VERSION_UNSUPPORTED"):
        load_configuration(b"config_schema_version: 73\nunknown: value")


@pytest.mark.parametrize("version", [b'"1"', b"true", b"null"])
def test_schema_version_must_be_a_strict_integer(version: bytes) -> None:
    with pytest.raises(ConfigurationSchemaError) as caught:
        load_configuration(b"config_schema_version: " + version)
    assert caught.value.code == "CONFIG_SCHEMA_VALIDATION_ERROR"
    assert caught.value.issues[0].location == "config_schema_version"


@pytest.mark.parametrize(
    ("old", "new", "path"),
    [
        (b"config_schema_version: 1\n", b"", "config_schema_version"),
        (b"base:\n", b"base: []\nother:\n", "base"),
        (
            b"  population:\n    customer_count: 1000\n    episode_count_min: 1100\n"
            b"    episode_count_max: 1400\n",
            b"",
            "base.population",
        ),
        (b"    customer_count: 1000\n", b"", "base.population.customer_count"),
        (b"customer_count: 1000", b"customer_count: '1000'", "base.population.customer_count"),
        (b"customer_count: 1000", b"customer_count: true", "base.population.customer_count"),
        (b"customer_count: 1000", b"customer_count: 0", "base.population.customer_count"),
        (b"episode_count_min: 1100", b"episode_count_min: -1", "base.population.episode_count_min"),
        (b"master_seed: 0", b"master_seed: -9223372036854775808", "base.master_seed"),
        (b"workflow: BASIC", b"workflow: basic", "base.workflow"),
        (b"execution_scope: configuration_only", b"execution_scope: full", "base.execution_scope"),
        (
            b"requested_outputs: [customers.csv, subscriptions.csv]",
            b"requested_outputs: customers.csv",
            "base.requested_outputs",
        ),
        (b"subscriptions.csv]", b"other.csv]", "base.requested_outputs.<item>"),
        (b"'1.1'", b"'1.0'", "base.policy_refs.contract_version"),
        (b"'0.2'", b"'0.1'", "base.policy_refs.business_model_version"),
        (b"PD-006", b"PD-007", "base.policy_refs.snapshot_decision"),
        (b"'2023-01-01'", b"'2023-02-29'", "base.history.start_date"),
        (b"'2023-01-01'", b"'20230101'", "base.history.start_date"),
        (b"  baseline:", b"  INVALID:", "scenarios.<scenario>.<unknown>"),
        (b"scenarios:\n  baseline:\n    scenario_version: 1", b"scenarios: {}", "scenarios"),
        (b"scenario_version: 1", b"scenario_version: 0", "scenarios.<scenario>.scenario_version"),
        (
            b"scenario_version: 1",
            b"scenario_version: 1\n    patch: null",
            "scenarios.<scenario>.patch",
        ),
        (
            b"scenario_version: 1",
            b"scenario_version: 1\n    patch: {master_seed: null}",
            "scenarios.<scenario>.patch.master_seed",
        ),
        (
            b"scenario_version: 1",
            b"scenario_version: 1\n    patch: {history: {cutoff_date: 'bogus'}}",
            "scenarios.<scenario>.patch.history.cutoff_date",
        ),
        (b"workflow: BASIC", b"diagnostics: {}\n  workflow: BASIC", "base.diagnostics.level"),
        (
            b"workflow: BASIC",
            b"diagnostics: {level: DEBUG}\n  workflow: BASIC",
            "base.diagnostics.level",
        ),
    ],
)
def test_structural_errors_report_safe_locations(old: bytes, new: bytes, path: str) -> None:
    with pytest.raises(ConfigurationSchemaError) as caught:
        load_configuration(_VALID.replace(old, new))
    assert path in {issue.location for issue in caught.value.issues}


@pytest.mark.parametrize(
    "patch",
    [
        b"{workflow: TEMPORAL}",
        b"{execution_scope: configuration_only}",
        b"{requested_outputs: []}",
        b"{policy_refs: {}}",
        b"{population: {other: 1}}",
        b"{diagnostics: {raw_input: true}}",
    ],
)
def test_rejects_unknown_and_forbidden_patch_fields_in_any_scenario(patch: bytes) -> None:
    extra = b"  unused:\n    scenario_version: 1\n    patch: " + patch + b"\n"
    with pytest.raises(ConfigurationSchemaError, match="CONFIG_UNKNOWN_FIELD") as caught:
        load_configuration(_VALID + extra)
    assert caught.value.issues[0].location.startswith("scenarios.<scenario>.patch.")
    assert caught.value.issues[0].location.endswith("<unknown>")


def test_preserves_effective_checks_for_the_later_increment() -> None:
    raw = (
        _VALID.replace(b"workflow: BASIC", b"workflow: TEMPORAL")
        .replace(b"[customers.csv, subscriptions.csv]", b"[invoices.csv, invoices.csv]")
        .replace(b"episode_count_min: 1100", b"episode_count_min: 2000")
        .replace(b'"2026-01-01"', b'"2022-01-01"')
    )
    assert load_configuration(raw).base.requested_outputs == ["invoices.csv", "invoices.csv"]
    assert (
        load_configuration(
            raw.replace(b"[invoices.csv, invoices.csv]", b"[]")
        ).base.requested_outputs
        == []
    )


def test_bounds_sorts_and_sanitises_multiple_schema_issues() -> None:
    raw = _VALID.replace(b"customer_count: 1000", b"customer_count: 'sentinel-value'") + b"".join(
        f"secret-key-{index}: 'sentinel-value'\n".encode() for index in range(7)
    )
    raw += b"scenarios-extra: '/home/sentinel-value'\n"
    with pytest.raises(ConfigurationSchemaError, match="CONFIG_UNKNOWN_FIELD") as caught:
        load_configuration(raw)
    error = caught.value
    assert len(error.issues) == 5
    assert error.omitted_count == 4
    assert [issue.location for issue in error.issues] == ["<unknown>"] * 5
    assert all(issue.reason == "unknown_field" for issue in error.issues)
    assert error.__cause__ is None
    assert error.__context__ is None
    assert "sentinel-value" not in repr(vars(error))
    assert "secret-key" not in repr(vars(error))


@pytest.mark.parametrize(
    "raw",
    [
        b"raw-sentinel: [",
        rb'raw-sentinel: "\U00110000"',
        b"\xffraw-sentinel",
        _VALID.replace(b"master_seed: 0", b"master_seed: 'raw-sentinel'"),
        _VALID.replace(b"  baseline:", b"  raw-sentinel pending:"),
        _VALID + b"raw-sentinel: /home/raw-sentinel\n",
    ],
)
def test_public_error_does_not_expose_payload_or_library_exception(raw: bytes) -> None:
    with pytest.raises(ConfigurationError) as caught:
        load_configuration(raw)
    error = caught.value
    assert error.__cause__ is None
    assert error.__context__ is None
    diagnostics = str(error) + repr(error) + repr(vars(error))
    diagnostics += "".join(traceback.format_exception(error))
    assert "raw-sentinel" not in diagnostics
    assert "pydantic_core" not in diagnostics
    assert "ParserError" not in diagnostics


def test_parser_position_is_safe_and_one_based() -> None:
    with pytest.raises(ConfigurationParseError) as caught:
        load_configuration(b"base: [\n")
    assert caught.value.line == 2
    assert caught.value.column == 1


def test_yaml_customisation_does_not_change_safe_loader() -> None:
    assert yaml.safe_load("legacy: on") == {"legacy": True}
    with pytest.raises(ConfigurationParseError):
        load_configuration(b"legacy: on")
    assert yaml.safe_load("legacy: on") == {"legacy": True}


def test_loading_and_rejection_have_no_execution_side_effects(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.chdir(tmp_path)

    def forbidden(*args: object, **kwargs: object) -> None:
        pytest.fail("Configuration loading attempted an execution side effect.")

    with monkeypatch.context() as guard:
        guard.setattr("builtins.open", forbidden)
        guard.setattr(io, "open", forbidden)
        guard.setattr(random.Random, "random", forbidden)
        guard.setattr(execution, "execute_pipeline", forbidden)
        load_configuration(_VALID)
        with pytest.raises(ConfigurationSchemaError):
            load_configuration(_VALID.replace(b"workflow: BASIC", b"workflow: unsupported"))
    assert list(tmp_path.iterdir()) == []


def test_resolution_precedence_origins_and_isolation() -> None:
    raw = (
        _VALID
        + b"""    patch:
      population: {customer_count: 900, episode_count_max: 1800}
      master_seed: 2
      diagnostics: {level: WARNING}
"""
    )
    document = load_configuration(raw)
    overrides = {"population": {"customer_count": 800}, "master_seed": 3}
    effective = resolve_configuration(document, "baseline", overrides)
    assert effective == resolve_configuration(
        document, "baseline", dict(reversed(list(overrides.items())))
    )
    assert effective.population.customer_count == 800
    assert effective.population.episode_count_max == 1800
    assert effective.master_seed == 3
    assert effective.diagnostics.level == "WARNING"
    origins = {origin.field_path: origin.layer for origin in effective.origins}
    assert origins["population.customer_count"] == "override"
    assert origins["population.episode_count_max"] == "scenario"
    assert origins["population.episode_count_min"] == "base"
    assert origins["config_schema_version"] == "document"
    overrides["population"] = {"customer_count": 1}
    document.base.requested_outputs.clear()
    assert effective.population.customer_count == 800
    assert effective.requested_outputs == ("customers.csv", "subscriptions.csv")
    assert "master_seed" not in effective.diagnostic_fields()
    with pytest.raises(ValueError, match="frozen"):
        effective.population.customer_count = 1


def test_resolution_materialises_only_the_diagnostic_default() -> None:
    effective = resolve_configuration(load_configuration(_VALID), "baseline")
    assert effective.diagnostics.level == "INFO"
    assert any(
        o.field_path == "diagnostics.level" and o.layer == "default" for o in effective.origins
    )
    assert effective.master_seed == 0


@pytest.mark.parametrize(
    "override",
    [
        {"population": {"customer_count": None}},
        {"master_seed": 2**63},
        {"workflow": "TEMPORAL"},
        {"secret-sentinel": "secret-sentinel"},
    ],
)
def test_resolution_rejects_invalid_overrides_safely(override: dict[str, object]) -> None:
    with pytest.raises(ConfigurationError, match="CONFIG_OVERRIDE_INVALID") as caught:
        resolve_configuration(load_configuration(_VALID), "baseline", override)
    assert caught.value.__context__ is None
    assert "secret-sentinel" not in repr(vars(caught.value))


def test_resolution_requires_an_exact_scenario_without_disclosing_it() -> None:
    with pytest.raises(ConfigurationError, match="CONFIG_SCENARIO_UNKNOWN") as caught:
        resolve_configuration(load_configuration(_VALID), "BASELINE-secret-sentinel")
    assert "secret-sentinel" not in str(caught.value)


@pytest.mark.parametrize(
    ("old", "new", "reason"),
    [
        (b"episode_count_min: 1100", b"episode_count_min: 2000", "inverted_episode_bounds"),
        (b'"2026-01-01"', b'"2022-01-01"', "invalid_date_order"),
        (b"subscriptions.csv]", b"customers.csv]", "duplicate_filename"),
        (b"[customers.csv, subscriptions.csv]", b"[]", "missing_workflow_input"),
        (b"workflow: BASIC", b"workflow: TEMPORAL", "missing_workflow_input"),
    ],
)
def test_resolution_checks_effective_relationships(old: bytes, new: bytes, reason: str) -> None:
    document = load_configuration(_VALID.replace(old, new))
    with pytest.raises(ConfigurationError, match="CONFIG_EFFECTIVE_INVALID") as caught:
        resolve_configuration(document, "baseline")
    assert caught.value.issues[0].reason == reason
