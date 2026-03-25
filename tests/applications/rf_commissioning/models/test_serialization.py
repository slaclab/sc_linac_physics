"""Tests for serialization helpers used by RF commissioning models."""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional, Union

import pytest

from sc_linac_physics.applications.rf_commissioning.models.data_models import (
    CommissioningPhase,
)
from sc_linac_physics.applications.rf_commissioning.models.serialization import (
    deserialize_model,
    get_phase_display_specs,
    phase_display_field,
    serialize_model,
)


class LocalMode(Enum):
    """Local enum for helper coverage tests."""

    AUTO = "auto"
    MANUAL = "manual"


@dataclass
class DisplayModel:
    """Dataclass with display metadata for helper testing."""

    temperature: float = phase_display_field(
        default=0.0,
        label="Temperature",
        widget_name="temperature_widget",
        format_spec=".1f",
        unit="K",
    )
    mode: bool = phase_display_field(
        default=False,
        label="Mode",
        widget_name="mode_widget",
        source_attr="mode_label",
        true_text="On",
        false_text="Off",
    )


@dataclass
class RequiredFieldModel:
    """Dataclass with a required field for error-path testing."""

    required_value: int
    optional_value: str = "default"


@dataclass
class NestedModel:
    """Nested dataclass for recursive serialization tests."""

    observed_at: datetime


@dataclass
class RoundTripModel:
    """Dataclass combining enums, maps, unions, and nested dataclasses."""

    phase: CommissioningPhase
    mode: LocalMode
    created_at: datetime
    nested: NestedModel
    by_phase: dict[CommissioningPhase, int]
    values: list[int]
    union_value: Union[int, datetime]
    optional_note: Optional[str] = None


@dataclass
class ComputedModel:
    """Dataclass to verify computed field inclusion in serialize_model."""

    base: int

    @property
    def doubled(self) -> int:
        return self.base * 2


class TestPhaseDisplayHelpers:
    """Tests for phase display metadata utilities."""

    def test_get_phase_display_specs_returns_ordered_specs(self):
        specs = get_phase_display_specs(DisplayModel)

        assert [spec.field_name for spec in specs] == ["temperature", "mode"]
        assert specs[0].source_attr == "temperature"
        assert specs[0].format_spec == ".1f"
        assert specs[0].unit == "K"
        assert specs[1].source_attr == "mode_label"
        assert specs[1].true_text == "On"
        assert specs[1].false_text == "Off"

    def test_get_phase_display_specs_requires_dataclass_type(self):
        with pytest.raises(TypeError, match="requires a dataclass type"):
            get_phase_display_specs(dict)


class TestSerializeModel:
    """Tests for dataclass serialization helper."""

    def test_serialize_model_serializes_nested_enums_and_maps(self):
        model = RoundTripModel(
            phase=CommissioningPhase.COLD_LANDING,
            mode=LocalMode.AUTO,
            created_at=datetime(2026, 3, 25, 10, 0, 0),
            nested=NestedModel(observed_at=datetime(2026, 3, 25, 10, 1, 0)),
            by_phase={CommissioningPhase.COLD_LANDING: 1},
            values=[1, 2, 3],
            union_value=datetime(2026, 3, 25, 10, 2, 0),
            optional_note=None,
        )

        payload = serialize_model(model)

        assert payload["phase"] == "cold_landing"
        assert payload["mode"] == "auto"
        assert payload["created_at"] == "2026-03-25T10:00:00"
        assert payload["nested"]["observed_at"] == "2026-03-25T10:01:00"
        assert payload["by_phase"] == {"cold_landing": 1}
        assert payload["union_value"] == "2026-03-25T10:02:00"

    def test_serialize_model_includes_computed_fields(self):
        payload = serialize_model(
            ComputedModel(base=7), computed_fields=("doubled",)
        )

        assert payload["base"] == 7
        assert payload["doubled"] == 14

    def test_serialize_model_requires_dataclass_instance(self):
        with pytest.raises(TypeError, match="requires a dataclass instance"):
            serialize_model({"not": "a dataclass"})


class TestDeserializeModel:
    """Tests for dataclass deserialization helper."""

    def test_deserialize_model_round_trip_with_union_and_enum_keys(self):
        payload = {
            "phase": "ssa_char",
            "mode": "manual",
            "created_at": "2026-03-25T11:00:00",
            "nested": {"observed_at": "2026-03-25T11:01:00"},
            "by_phase": {"ssa_char": 9},
            "values": [9, 8, 7],
            "union_value": "2026-03-25T11:02:00",
            "optional_note": "ok",
        }

        model = deserialize_model(RoundTripModel, payload)

        assert model.phase == CommissioningPhase.SSA_CHAR
        assert model.mode == LocalMode.MANUAL
        assert model.created_at == datetime(2026, 3, 25, 11, 0, 0)
        assert model.nested.observed_at == datetime(2026, 3, 25, 11, 1, 0)
        assert model.by_phase == {CommissioningPhase.SSA_CHAR: 9}
        assert model.union_value == datetime(2026, 3, 25, 11, 2, 0)

    def test_deserialize_model_missing_required_field_raises(self):
        with pytest.raises(KeyError, match="Missing required field"):
            deserialize_model(RequiredFieldModel, {"optional_value": "x"})

    def test_deserialize_model_uses_defaults_for_missing_optional_fields(self):
        model = deserialize_model(RequiredFieldModel, {"required_value": 5})

        assert model.required_value == 5
        assert model.optional_value == "default"

    def test_deserialize_model_requires_dataclass_type(self):
        with pytest.raises(TypeError, match="requires a dataclass type"):
            deserialize_model(int, {"value": 1})
