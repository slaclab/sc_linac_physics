"""Shared serialization and UI metadata helpers for RF commissioning models."""

from dataclasses import MISSING, dataclass, field, fields, is_dataclass
from datetime import datetime
from enum import Enum
from typing import (
    Any,
    Dict,
    List,
    TypeVar,
    Union,
    get_args,
    get_origin,
    get_type_hints,
)

T = TypeVar("T")
PHASE_UI_METADATA_KEY = "phase_ui"


@dataclass(frozen=True)
class PhaseDisplaySpec:
    """UI display metadata for a phase dataclass field."""

    field_name: str
    label: str
    widget_name: str
    source_attr: str
    format_spec: str | None = None
    unit: str = ""
    true_text: str = "Yes"
    false_text: str = "No"


def phase_display_field(
    *,
    label: str,
    widget_name: str,
    source_attr: str | None = None,
    format_spec: str | None = None,
    unit: str = "",
    true_text: str = "Yes",
    false_text: str = "No",
    default=MISSING,
    default_factory=MISSING,
):
    """Create a dataclass field with metadata for phase screen display."""
    metadata = {
        PHASE_UI_METADATA_KEY: {
            "label": label,
            "widget_name": widget_name,
            "source_attr": source_attr,
            "format_spec": format_spec,
            "unit": unit,
            "true_text": true_text,
            "false_text": false_text,
        }
    }
    kwargs: dict[str, Any] = {"metadata": metadata}
    if default is not MISSING:
        kwargs["default"] = default
    if default_factory is not MISSING:
        kwargs["default_factory"] = default_factory
    return field(**kwargs)


def get_phase_display_specs(model_cls: type[Any]) -> list[PhaseDisplaySpec]:
    """Return ordered display specs declared on a phase dataclass."""
    if not is_dataclass(model_cls):
        raise TypeError("get_phase_display_specs() requires a dataclass type")

    specs: list[PhaseDisplaySpec] = []
    for model_field in fields(model_cls):
        metadata = model_field.metadata.get(PHASE_UI_METADATA_KEY)
        if not metadata:
            continue
        specs.append(
            PhaseDisplaySpec(
                field_name=model_field.name,
                label=metadata["label"],
                widget_name=metadata["widget_name"],
                source_attr=metadata.get("source_attr") or model_field.name,
                format_spec=metadata.get("format_spec"),
                unit=metadata.get("unit", ""),
                true_text=metadata.get("true_text", "Yes"),
                false_text=metadata.get("false_text", "No"),
            )
        )
    return specs


def _serialize_value(value: Any) -> Any:
    """Recursively serialize model values to JSON-friendly types."""
    if isinstance(value, datetime):
        return value.isoformat()

    if isinstance(value, Enum):
        return value.value

    if is_dataclass(value) and not isinstance(value, type):
        return serialize_model(value)

    if isinstance(value, dict):
        serialized: dict[Any, Any] = {}
        for key, item in value.items():
            serialized_key = _serialize_value(key)
            if not isinstance(serialized_key, (str, int, float, bool)):
                serialized_key = str(serialized_key)
            serialized[serialized_key] = _serialize_value(item)
        return serialized

    if isinstance(value, list):
        return [_serialize_value(item) for item in value]

    if isinstance(value, tuple):
        return [_serialize_value(item) for item in value]

    return value


def _deserialize_union_value(field_type: Any, value: Any) -> Any:
    """Deserialize a value against the non-None members of a union."""
    non_none_args = [
        arg for arg in get_args(field_type) if arg is not type(None)
    ]
    for arg in non_none_args:
        try:
            deserialized = _deserialize_value(arg, value)

            # For concrete runtime types, only accept a union branch if the
            # deserialized value actually matches that type.
            if isinstance(arg, type) and not isinstance(deserialized, arg):
                continue

            return deserialized
        except (TypeError, ValueError, KeyError):
            continue
    return value


def _deserialize_list_value(field_type: Any, value: Any) -> list[Any]:
    """Deserialize a list payload using its declared item type."""
    item_type = get_args(field_type)[0] if get_args(field_type) else Any
    return [_deserialize_value(item_type, item) for item in value]


def _deserialize_dict_value(field_type: Any, value: Any) -> dict[Any, Any]:
    """Deserialize a mapping payload using declared key and value types."""
    args = get_args(field_type)
    key_type = args[0] if len(args) >= 1 else Any
    value_type = args[1] if len(args) >= 2 else Any
    return {
        _deserialize_value(key_type, key): _deserialize_value(value_type, item)
        for key, item in value.items()
    }


def _deserialize_instance_value(field_type: type[Any], value: Any) -> Any:
    """Deserialize values for concrete runtime types."""
    if issubclass(field_type, Enum):
        return field_type(value)

    if field_type is datetime:
        return datetime.fromisoformat(value)

    if is_dataclass(field_type) and isinstance(value, dict):
        return deserialize_model(field_type, value)

    return value


def _deserialize_value(field_type: Any, value: Any) -> Any:
    """Recursively deserialize JSON-friendly values back to model types."""
    if value is None or field_type is Any:
        return value

    origin = get_origin(field_type)
    if origin is Union:
        return _deserialize_union_value(field_type, value)

    if origin in (list, List):
        return _deserialize_list_value(field_type, value)

    if origin in (dict, Dict):
        return _deserialize_dict_value(field_type, value)

    if isinstance(field_type, type):
        return _deserialize_instance_value(field_type, value)

    return value


def serialize_model(
    instance: Any, computed_fields: tuple[str, ...] = ()
) -> dict[str, Any]:
    """Serialize a dataclass instance, optionally including computed properties."""
    if not is_dataclass(instance) or isinstance(instance, type):
        raise TypeError("serialize_model() requires a dataclass instance")

    serialized = {
        model_field.name: _serialize_value(getattr(instance, model_field.name))
        for model_field in fields(instance)
    }

    for property_name in computed_fields:
        serialized[property_name] = _serialize_value(
            getattr(instance, property_name)
        )

    return serialized


def deserialize_model(model_cls: type[T], data: dict[str, Any]) -> T:
    """Deserialize a dataclass instance from a dictionary payload."""
    if not is_dataclass(model_cls):
        raise TypeError("deserialize_model() requires a dataclass type")

    type_hints = get_type_hints(model_cls)
    kwargs: dict[str, Any] = {}

    for model_field in fields(model_cls):
        if model_field.name not in data:
            if (
                model_field.default is MISSING
                and model_field.default_factory is MISSING
            ):
                raise KeyError(
                    f"Missing required field '{model_field.name}' for {model_cls.__name__}"
                )
            continue

        field_type = type_hints.get(model_field.name, model_field.type)
        kwargs[model_field.name] = _deserialize_value(
            field_type, data[model_field.name]
        )

    return model_cls(**kwargs)
