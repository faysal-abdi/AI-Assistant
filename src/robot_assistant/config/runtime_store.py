"""Helpers to persist and restore runtime configuration."""

from __future__ import annotations

import json
from copy import deepcopy
from dataclasses import fields, is_dataclass
from pathlib import Path
from typing import Any, Dict, Optional, Type, TypeVar

from .defaults import (
    MemoryConfig,
    ModelRoutingConfig,
    RetrievalConfig,
    RuntimeConfig,
    SafetyConfig,
    ToolingConfig,
    VoiceConfig,
)

T = TypeVar("T")

CONFIG_PATH = Path("var/runtime_config.json")

_NESTED_TYPES = {
    "models": ModelRoutingConfig,
    "retrieval": RetrievalConfig,
    "tooling": ToolingConfig,
    "memory": MemoryConfig,
    "safety": SafetyConfig,
    "voice": VoiceConfig,
}


def runtime_config_to_dict(config: RuntimeConfig) -> Dict[str, Any]:
    """Convert a RuntimeConfig to a JSON-ready dict."""
    return _dataclass_to_dict(config)


def runtime_config_from_dict(data: Dict[str, Any], base: Optional[RuntimeConfig] = None) -> RuntimeConfig:
    """Construct a RuntimeConfig from a dict, merging with base defaults."""
    base_config = base or RuntimeConfig()
    return _dict_to_dataclass(RuntimeConfig, data, base_config)


def save_runtime_config(config: RuntimeConfig, path: Optional[Path] = None) -> None:
    """Persist configuration to disk as JSON."""
    target = path or CONFIG_PATH
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = runtime_config_to_dict(config)
    target.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def load_runtime_config(path: Optional[Path] = None, base: Optional[RuntimeConfig] = None) -> RuntimeConfig:
    """Load configuration from disk; return defaults when file is absent."""
    source = path or CONFIG_PATH
    base_config = base or RuntimeConfig()
    if not source.exists():
        return base_config
    data = json.loads(source.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("runtime configuration file must contain a JSON object")
    return runtime_config_from_dict(data, base_config)


def _dataclass_to_dict(instance: Any) -> Dict[str, Any]:
    result: Dict[str, Any] = {}
    for field in fields(instance):
        value = getattr(instance, field.name)
        if is_dataclass(value):
            result[field.name] = _dataclass_to_dict(value)
        else:
            result[field.name] = value
    return result


def _dict_to_dataclass(cls: Type[T], data: Dict[str, Any], base: Optional[T] = None) -> T:
    base_instance = base if base is not None else cls()
    kwargs: Dict[str, Any] = {}
    valid_fields = {field.name for field in fields(cls)}
    unknown = set(data.keys()) - valid_fields
    if unknown:
        unknown_list = ", ".join(sorted(unknown))
        raise ValueError(f"Unknown fields for {cls.__name__}: {unknown_list}")
    for field in fields(cls):
        name = field.name
        if name in _NESTED_TYPES:
            nested_cls = _NESTED_TYPES[name]
            incoming = data.get(name) or {}
            nested_base = getattr(base_instance, name)
            kwargs[name] = _dict_to_dataclass(nested_cls, incoming, nested_base)
        else:
            if name in data:
                value = data[name]
            else:
                value = getattr(base_instance, name)
                if isinstance(value, (dict, list)):
                    value = deepcopy(value)
            kwargs[name] = value
    return cls(**kwargs)
