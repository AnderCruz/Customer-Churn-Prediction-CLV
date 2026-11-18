"""Load structurally validated v1 synthetic scenario documents."""

from collections.abc import Iterator, Mapping
from contextlib import closing
from dataclasses import dataclass, field
from datetime import date
from re import compile
from typing import Annotated, Literal, Self

import yaml
from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    field_validator,
    model_validator,
)
from pydantic_core import PydanticCustomError
from yaml.constructor import ConstructorError
from yaml.error import MarkedYAMLError
from yaml.events import (
    DocumentEndEvent,
    DocumentStartEvent,
    Event,
    MappingEndEvent,
    MappingStartEvent,
    ScalarEvent,
    SequenceEndEvent,
    SequenceStartEvent,
    StreamEndEvent,
    StreamStartEvent,
)
from yaml.nodes import MappingNode

from nowa_customer_intelligence.data.ingestion import DATASET_FILENAMES
from nowa_customer_intelligence.pipeline.models import PipelineWorkflow

_MAX_DOCUMENT_BYTES = 65_536
_MAX_COLLECTION_DEPTH = 8
_MAX_SCENARIOS = 32
_MAX_NODES = 2_048
_MAX_SCALAR_LENGTH = 256
_MAX_POSITIVE_INTEGER = "9223372036854775807"
_MAX_NEGATIVE_MAGNITUDE = "9223372036854775808"
_MAX_ISSUES = 5
_DECIMAL_INTEGER = compile(r"(?:0|-?[1-9][0-9]*)\Z")
_NUMERIC_LIKE = compile(
    r"[+-]?(?:[0-9][0-9_]*(?:\.[0-9_]*)?|\.[0-9_]+)(?:[eE][+-]?[0-9_]+)?"
    r"|[+-]?0(?:[boxBOX][0-9a-fA-F_]+)"
    r"|[+-]?[0-9]+(?::[0-9]+)+(?:\.[0-9]+)?"
)
_DATE = compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}")
_YAML_TAG = "tag:yaml.org,2002:"

_PARSE_ERROR = "CONFIG_PARSE_ERROR"
_SIZE_LIMIT = "CONFIG_SIZE_LIMIT_EXCEEDED"
_UNSUPPORTED_VERSION = "CONFIG_SCHEMA_VERSION_UNSUPPORTED"
_SCHEMA_ERROR = "CONFIG_SCHEMA_VALIDATION_ERROR"
_UNKNOWN_FIELD = "CONFIG_UNKNOWN_FIELD"
_SCENARIO_ERROR = "CONFIG_SCENARIO_UNKNOWN"
_OVERRIDE_ERROR = "CONFIG_OVERRIDE_INVALID"
_EFFECTIVE_ERROR = "CONFIG_EFFECTIVE_INVALID"
_MESSAGES = {
    _SCENARIO_ERROR: "The requested scenario is unknown.",
    _OVERRIDE_ERROR: "The caller override does not match the permitted patch schema.",
    _EFFECTIVE_ERROR: "The effective configuration is invalid.",
    _PARSE_ERROR: "The document is not supported YAML.",
    _SIZE_LIMIT: "The document exceeds a configuration intake limit.",
    _UNSUPPORTED_VERSION: "The configuration schema version is unsupported.",
    _SCHEMA_ERROR: "The configuration does not match the structural schema.",
    _UNKNOWN_FIELD: "The configuration contains an unknown field.",
}


@dataclass(frozen=True)
class ConfigurationIssue:
    """An allowlisted location and fixed reason for one structural issue."""

    location: str
    reason: str


class ConfigurationError(ValueError):
    """A configuration rejection with safe, bounded diagnostics."""

    def __init__(
        self,
        code: str,
        *,
        issues: tuple[ConfigurationIssue, ...] = (),
        omitted_count: int = 0,
        limit: str | None = None,
        line: int | None = None,
        column: int | None = None,
    ) -> None:
        super().__init__(f"{code}: {_MESSAGES[code]}")
        self.code = code
        self.issues = issues
        self.omitted_count = omitted_count
        self.limit = limit
        self.line = line
        self.column = column


class ConfigurationParseError(ConfigurationError):
    """The document failed decoding or YAML intake."""


class ConfigurationSizeLimitError(ConfigurationError):
    """An approved intake limit was exceeded."""


class ConfigurationVersionError(ConfigurationError):
    """The document requests an unsupported configuration schema."""


class ConfigurationSchemaError(ConfigurationError):
    """The constructed document failed structural validation."""


class _ScenarioLoader(yaml.SafeLoader):
    """Use only WP-01.1 scalar resolution without modifying global YAML behaviour."""

    yaml_implicit_resolvers = {}

    def fetch_directive(self) -> None:
        # PyYAML discards unrecognised directives before emitting document events.
        raise MarkedYAMLError(problem_mark=self.get_mark())

    def construct_mapping(self, node: MappingNode, deep: bool = False) -> dict[str, object]:
        result = {}
        for key_node, value_node in node.value:
            key = self.construct_object(key_node, deep=deep)
            if not isinstance(key, str) or key == "<<" or key in result:
                raise ConstructorError(problem_mark=key_node.start_mark)
            result[key] = self.construct_object(value_node, deep=deep)
        return result


_ScenarioLoader.add_implicit_resolver(_YAML_TAG + "int", _DECIMAL_INTEGER, "-0123456789")
_ScenarioLoader.add_implicit_resolver(_YAML_TAG + "bool", compile(r"(?:true|false)\Z"), "tf")
_ScenarioLoader.add_implicit_resolver(_YAML_TAG + "null", compile(r"null\Z"), "n")


def _size_error(limit: str) -> ConfigurationSizeLimitError:
    return ConfigurationSizeLimitError(_SIZE_LIMIT, limit=limit)


def _parse_error(event: Event) -> ConfigurationParseError:
    mark = event.start_mark
    return ConfigurationParseError(_PARSE_ERROR, line=mark.line + 1, column=mark.column + 1)


def _scalar_kind(event: ScalarEvent) -> str:
    value = event.value
    if len(value) > _MAX_SCALAR_LENGTH:
        raise _size_error("scalar_length")
    if any(0xD800 <= ord(character) <= 0xDFFF for character in value):
        raise _parse_error(event)
    if event.style is not None:
        return "string"
    if value in ("true", "false", "null"):
        return "literal"
    if _DECIMAL_INTEGER.fullmatch(value):
        digits = value.removeprefix("-")
        bound = _MAX_NEGATIVE_MAGNITUDE if value.startswith("-") else _MAX_POSITIVE_INTEGER
        if (len(digits), digits) > (len(bound), bound):
            raise _size_error("integer_representation")
        return "integer"
    legacy = yaml.SafeLoader.yaml_implicit_resolvers
    if _NUMERIC_LIKE.fullmatch(value) or any(
        pattern.match(value) for _, pattern in legacy.get(value[:1], ())
    ):
        raise _parse_error(event)
    return "string"


@dataclass
class _Preflight:
    """Walk parser events and track keys and budgets without constructing YAML data."""

    events: Iterator[Event]
    nodes: int = field(init=False, default=0)

    def _count_node(self, event: Event) -> None:
        self.nodes += 1
        if self.nodes > _MAX_NODES:
            raise _size_error("nodes")
        if getattr(event, "anchor", None) is not None or getattr(event, "tag", None) is not None:
            raise _parse_error(event)

    def _mapping(self, path: tuple[str | None, ...], depth: int) -> None:
        keys: set[str] = set()
        for key in self.events:
            if isinstance(key, MappingEndEvent):
                return
            if not isinstance(key, ScalarEvent):
                raise _parse_error(key)
            self._count_node(key)
            if _scalar_kind(key) != "string" or key.value == "<<" or key.value in keys:
                raise _parse_error(key)
            keys.add(key.value)
            if path == ("scenarios",) and len(keys) > _MAX_SCENARIOS:
                raise _size_error("scenarios")
            self._node(next(self.events), (*path, key.value), depth)

    def _node(self, event: Event, path: tuple[str | None, ...], depth: int) -> None:
        self._count_node(event)
        if isinstance(event, ScalarEvent):
            _scalar_kind(event)
            base_history = path[:2] == ("base", "history") and len(path) == 3
            patch_history = (
                len(path) == 5 and path[0] == "scenarios" and path[2:4] == ("patch", "history")
            )
            if (
                (base_history or patch_history)
                and path[-1] in ("start_date", "cutoff_date")
                and event.style not in ("'", '"')
            ):
                raise _parse_error(event)
            return
        if not isinstance(event, (MappingStartEvent, SequenceStartEvent)):
            raise _parse_error(event)
        depth += 1
        if depth > _MAX_COLLECTION_DEPTH:
            raise _size_error("collection_depth")
        if isinstance(event, MappingStartEvent):
            self._mapping(path, depth)
            return
        for item in self.events:
            if isinstance(item, SequenceEndEvent):
                return
            self._node(item, (*path, None), depth)

    def check(self) -> None:
        if not isinstance(start := next(self.events), StreamStartEvent):
            raise _parse_error(start)
        if not isinstance(document := next(self.events), DocumentStartEvent):
            raise _parse_error(document)
        if not isinstance(root := next(self.events), MappingStartEvent):
            raise _parse_error(root)
        self._node(root, (), 0)
        if not isinstance(end := next(self.events), DocumentEndEvent):
            raise _parse_error(end)
        if not isinstance(end := next(self.events), StreamEndEvent):
            raise _parse_error(end)


def _known_filename(value: str) -> str:
    if value not in DATASET_FILENAMES.values():
        raise ValueError("Unsupported contract filename.")
    return value


def _calendar_date(value: str) -> str:
    if not _DATE.fullmatch(value):
        raise ValueError("Expected an ISO calendar date.")
    date.fromisoformat(value)
    return value


type _PositiveInteger = Annotated[int, Field(gt=0, le=2**63 - 1)]
type _Seed = Annotated[int, Field(ge=0, le=2**63 - 1)]
type _HistoryDate = Annotated[str, AfterValidator(_calendar_date)]
type _Filename = Annotated[str, AfterValidator(_known_filename)]
type _ScenarioId = Annotated[
    str, Field(max_length=_MAX_SCALAR_LENGTH, pattern=r"^[a-z][a-z0-9]*(?:[-_][a-z0-9]+)*$")
]


class _StructuralModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, hide_input_in_errors=True)

    @field_validator("*", mode="before")
    @classmethod
    def _reject_explicit_null(cls, value: object) -> object:
        if value is None:
            raise ValueError("Null is unsupported.")
        return value


class _Population(_StructuralModel):
    customer_count: _PositiveInteger
    episode_count_min: _PositiveInteger
    episode_count_max: _PositiveInteger


class _PopulationPatch(_StructuralModel):
    customer_count: _PositiveInteger | None = None
    episode_count_min: _PositiveInteger | None = None
    episode_count_max: _PositiveInteger | None = None


class _History(_StructuralModel):
    start_date: _HistoryDate
    cutoff_date: _HistoryDate


class _HistoryPatch(_StructuralModel):
    start_date: _HistoryDate | None = None
    cutoff_date: _HistoryDate | None = None


class _Diagnostics(_StructuralModel):
    level: Literal["INFO", "WARNING"]


class _PolicyReferences(_StructuralModel):
    contract_version: Literal["1.1"]
    business_model_version: Literal["0.2"]
    snapshot_decision: Literal["PD-006"]


class _Base(_StructuralModel):
    population: _Population
    history: _History
    master_seed: _Seed
    workflow: Literal["BASIC", "TEMPORAL"]
    execution_scope: Literal["configuration_only"]
    requested_outputs: list[_Filename]
    policy_refs: _PolicyReferences
    diagnostics: _Diagnostics | None = None


class _ScenarioPatch(_StructuralModel):
    population: _PopulationPatch | None = None
    history: _HistoryPatch | None = None
    master_seed: _Seed | None = None
    diagnostics: _Diagnostics | None = None


class _Scenario(_StructuralModel):
    scenario_version: _PositiveInteger
    patch: _ScenarioPatch | None = None


class ValidatedConfiguration(_StructuralModel):
    """A structurally validated v1 document awaiting scenario resolution."""

    config_schema_version: Literal[1]
    base: _Base
    scenarios: Annotated[dict[_ScenarioId, _Scenario], Field(min_length=1)]


_SCHEMA_FIELDS = frozenset(
    name
    for model in (
        ValidatedConfiguration,
        _Base,
        _Scenario,
        _ScenarioPatch,
        _Population,
        _History,
        _Diagnostics,
        _PolicyReferences,
    )
    for name in model.model_fields
)
_SAFE_REASONS = {
    "missing": "missing_field",
    "extra_forbidden": "unknown_field",
    "int_type": "invalid_type",
    "string_type": "invalid_type",
    "list_type": "invalid_type",
    "dict_type": "invalid_type",
    "model_type": "invalid_type",
    "greater_than": "out_of_range",
    "greater_than_equal": "out_of_range",
    "less_than_equal": "out_of_range",
    "too_short": "invalid_cardinality",
    "literal_error": "unsupported_literal",
    "string_pattern_mismatch": "invalid_format",
}


def _safe_location(location: tuple[str | int, ...], *, unknown: bool) -> str:
    parts = []
    for index, segment in enumerate(location):
        if unknown and index == len(location) - 1:
            parts.append("<unknown>")
        elif index == 1 and location[0] == "scenarios":
            parts.append("<scenario>")
        elif isinstance(segment, int):
            parts.append("<item>")
        elif segment in _SCHEMA_FIELDS:
            parts.append(segment)
        else:
            parts.append("<unknown>")
    return ".".join(parts) or "<document>"


def _schema_error(
    error: ValidationError, *, boundary_code: str | None = None
) -> ConfigurationSchemaError:
    issues = []
    for detail in error.errors(include_url=False, include_context=False, include_input=False):
        kind = detail["type"]
        issues.append(
            ConfigurationIssue(
                _safe_location(detail["loc"], unknown=kind == "extra_forbidden"),
                _SAFE_REASONS.get(kind, "invalid_value"),
            )
        )
    issues.sort(key=lambda issue: (issue.location, issue.reason))
    code = (
        _UNKNOWN_FIELD
        if any(issue.reason == "unknown_field" for issue in issues)
        else _SCHEMA_ERROR
    )
    return ConfigurationSchemaError(
        boundary_code or code,
        issues=tuple(issues[:_MAX_ISSUES]),
        omitted_count=max(0, len(issues) - _MAX_ISSUES),
    )


def _read_yaml(document: bytes) -> dict[str, object]:
    if len(document) > _MAX_DOCUMENT_BYTES:
        raise _size_error("document_bytes")
    try:
        text = document.decode("utf-8")
        with closing(yaml.parse(text, Loader=_ScenarioLoader)) as events:
            _Preflight(events).check()
        return yaml.load(text, Loader=_ScenarioLoader)
    except ConfigurationError:
        raise
    except yaml.YAMLError as exc:
        mark = getattr(exc, "problem_mark", None)
        error = ConfigurationParseError(
            _PARSE_ERROR,
            line=mark.line + 1 if mark is not None else None,
            column=mark.column + 1 if mark is not None else None,
        )
    except ValueError:
        # PyYAML can raise ValueError for out-of-range Unicode escapes.
        error = ConfigurationParseError(_PARSE_ERROR)
    # Raise after leaving the handler so library exceptions are not chained.
    raise error


def load_configuration(document: bytes) -> ValidatedConfiguration:
    """Validate bounded UTF-8 YAML and return its unresolved v1 configuration.

    Configuration errors expose only stable codes and sanitised issue details.
    """
    if type(document) is not bytes:
        raise ConfigurationParseError(_PARSE_ERROR)
    raw = _read_yaml(document)
    version = raw.get("config_schema_version")
    if type(version) is not int:
        reason = "invalid_type" if "config_schema_version" in raw else "missing_field"
        raise ConfigurationSchemaError(
            _SCHEMA_ERROR, issues=(ConfigurationIssue("config_schema_version", reason),)
        )
    if version != 1:
        raise ConfigurationVersionError(_UNSUPPORTED_VERSION)
    try:
        return ValidatedConfiguration.model_validate(raw)
    except ValidationError as exc:
        error = _schema_error(exc)
    raise error


class _EffectivePopulation(_Population, frozen=True):
    pass


class _EffectiveHistory(_History, frozen=True):
    pass


class _EffectivePolicies(_PolicyReferences, frozen=True):
    pass


class _EffectiveDiagnostics(_Diagnostics, frozen=True):
    pass


@dataclass(frozen=True, slots=True)
class ValueOrigin:
    """The winning configuration layer for a known effective field."""

    field_path: str
    layer: Literal["default", "base", "scenario", "override", "document"]
    source: str


def required_filenames(workflow: PipelineWorkflow) -> tuple[str, ...]:
    """Return the contract filenames required by the workflow declaration."""
    names = ("customers", "subscriptions")
    if workflow is PipelineWorkflow.TEMPORAL:
        names += ("subscription_snapshots",)
    return tuple(DATASET_FILENAMES[name] for name in names)


class EffectiveConfiguration(_StructuralModel, frozen=True):
    """Complete, immutable WP-01 settings for a selected scenario."""

    config_schema_version: Literal[1]
    scenario_id: _ScenarioId
    scenario_version: _PositiveInteger
    population: _EffectivePopulation
    history: _EffectiveHistory
    master_seed: _Seed
    workflow: PipelineWorkflow
    execution_scope: Literal["configuration_only"]
    requested_outputs: tuple[_Filename, ...]
    policy_refs: _EffectivePolicies
    diagnostics: _EffectiveDiagnostics
    origins: tuple[ValueOrigin, ...]

    @model_validator(mode="after")
    def _check_consistency(self) -> Self:
        if self.population.episode_count_min > self.population.episode_count_max:
            raise PydanticCustomError(
                "inverted_episode_bounds", "The effective configuration is inconsistent."
            )
        if self.history.start_date >= self.history.cutoff_date:
            raise PydanticCustomError(
                "invalid_date_order", "The effective configuration is inconsistent."
            )
        if len(set(self.requested_outputs)) != len(self.requested_outputs):
            raise PydanticCustomError(
                "duplicate_filename", "The effective configuration is inconsistent."
            )
        if not set(required_filenames(self.workflow)).issubset(self.requested_outputs):
            raise PydanticCustomError(
                "missing_workflow_input", "The effective configuration is inconsistent."
            )
        return self

    def diagnostic_fields(self) -> dict[str, object]:
        """Return an allowlisted projection without seed or raw input."""
        return {
            "config_schema_version": self.config_schema_version,
            "scenario_id": self.scenario_id,
            "workflow": self.workflow.value,
            "execution_scope": self.execution_scope,
            "requested_outputs": self.requested_outputs,
        }


def _effective_error(path: str, reason: str) -> ConfigurationSchemaError:
    return ConfigurationSchemaError(_EFFECTIVE_ERROR, issues=(ConfigurationIssue(path, reason),))


def resolve_configuration(
    document: ValidatedConfiguration,
    scenario_id: str,
    overrides: Mapping[str, object] | None = None,
) -> EffectiveConfiguration:
    """Resolve one exact scenario and copy supported values into a frozen configuration."""
    if type(document) is not ValidatedConfiguration:
        raise _effective_error("<document>", "invalid_type")
    # Recheck the mutable structural document before using it as a source.
    try:
        checked = ValidatedConfiguration.model_validate(
            document.model_dump(exclude_unset=True, warnings=False)
        )
    except ValidationError as exc:
        structural_error = _schema_error(exc)
    else:
        return _resolve_checked(checked, scenario_id, overrides)
    raise structural_error


def _resolve_checked(
    document: ValidatedConfiguration,
    scenario_id: str,
    overrides: Mapping[str, object] | None,
) -> EffectiveConfiguration:
    if type(scenario_id) is not str or scenario_id not in document.scenarios:
        raise ConfigurationError(_SCENARIO_ERROR)
    override = None
    if overrides is not None:
        if not isinstance(overrides, Mapping):
            raise ConfigurationSchemaError(
                _OVERRIDE_ERROR, issues=(ConfigurationIssue("<document>", "invalid_type"),)
            )
        override_error = None
        try:
            override = _ScenarioPatch.model_validate(dict(overrides))
        except ValidationError as exc:
            override_error = _schema_error(exc, boundary_code=_OVERRIDE_ERROR)
        if override_error is not None:
            raise override_error
    scenario = document.scenarios[scenario_id]
    values: dict[str, object] = {"diagnostics": {"level": "INFO"}}
    origins = {"diagnostics.level": ValueOrigin("diagnostics.level", "default", "schema-v1")}
    layers: list[tuple[Literal["base", "scenario", "override"], str, dict[str, object]]] = [
        ("base", "base", document.base.model_dump(exclude_unset=True)),
        (
            "scenario",
            scenario_id,
            scenario.patch.model_dump(exclude_unset=True) if scenario.patch else {},
        ),
        ("override", "caller", override.model_dump(exclude_unset=True) if override else {}),
    ]
    for layer, source, fields in layers:
        for name, value in fields.items():
            if isinstance(value, dict):
                previous = values.get(name)
                values[name] = {**(previous if isinstance(previous, dict) else {}), **value}
                for leaf in value:
                    path = f"{name}.{leaf}"
                    origins[path] = ValueOrigin(path, layer, source)
            else:
                values[name] = value
                origins[name] = ValueOrigin(name, layer, source)
    values["workflow"] = PipelineWorkflow(values["workflow"])
    filename_order = tuple(DATASET_FILENAMES.values())
    values["requested_outputs"] = tuple(
        sorted(document.base.requested_outputs, key=filename_order.index)
    )
    origins["config_schema_version"] = ValueOrigin("config_schema_version", "document", "schema-v1")
    for path in ("scenario_id", "scenario_version"):
        origins[path] = ValueOrigin(path, "scenario", scenario_id)
    try:
        return EffectiveConfiguration.model_validate(
            dict(
                values,
                config_schema_version=document.config_schema_version,
                scenario_id=scenario_id,
                scenario_version=scenario.scenario_version,
                origins=tuple(origins[path] for path in sorted(origins)),
            )
        )
    except ValidationError as exc:
        reason = exc.errors(include_input=False, include_context=False, include_url=False)[0][
            "type"
        ]
        location = {
            "inverted_episode_bounds": "population.episode_count_min",
            "invalid_date_order": "history.start_date",
            "duplicate_filename": "requested_outputs",
            "missing_workflow_input": "requested_outputs",
        }.get(reason)
        error = (
            _effective_error(location, reason)
            if location is not None
            else _schema_error(exc, boundary_code=_EFFECTIVE_ERROR)
        )
    raise error
