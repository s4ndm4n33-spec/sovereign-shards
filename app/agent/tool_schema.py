# Copyright (c) 2024-2026 Reed Richards (s4ndm4n33). Licensed under BSL 1.1.
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

_ALLOWED_TYPES: dict[str, tuple[type, ...]] = {
    "str": (str,),
    "int": (int,),
    "float": (float, int),
    "bool": (bool,),
    "dict": (dict,),
    "list": (list,),
}


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str = ""
    args: list[dict[str, Any]] | list[str] = None
    side_effect: str = "read"
    timeout_seconds: int = 30

    def __post_init__(self) -> None:
        if self.args is None:
            object.__setattr__(self, "args", [])


def normalize_spec(spec: ToolSpec) -> dict[str, Any]:
    return {
        "name": spec.name,
        "description": spec.description,
        "args": [dict(arg) if isinstance(arg, dict) else {"name": str(arg), "type": "str", "required": True} for arg in spec.args],
        "side_effect": spec.side_effect,
        "timeout_seconds": spec.timeout_seconds,
    }


def validate_args(spec: ToolSpec, args: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(args, dict):
        raise ValueError("args must be an object")

    normalized_args: list[dict[str, Any]] = []
    for arg in spec.args:
        if isinstance(arg, dict):
            normalized_args.append(arg)
        else:
            normalized_args.append({"name": str(arg), "type": "str", "required": True})

    schema_by_name: dict[str, dict[str, Any]] = {arg["name"]: arg for arg in normalized_args}
    unknown = sorted(name for name in args if name not in schema_by_name)
    if unknown:
        raise ValueError(f"unknown arguments: {', '.join(unknown)}")

    validated: dict[str, Any] = {}
    for arg_spec in normalized_args:
        arg_name = arg_spec["name"]
        arg_type = arg_spec["type"]
        required = bool(arg_spec.get("required", False))
        has_default = "default" in arg_spec

        if arg_name in args:
            value = args[arg_name]
        elif has_default:
            value = arg_spec["default"]
        elif required:
            raise ValueError(f"missing required argument: {arg_name}")
        else:
            continue

        expected = _ALLOWED_TYPES.get(arg_type)
        if expected is None:
            raise ValueError(f"unsupported argument type: {arg_type}")
        if not isinstance(value, expected):
            raise TypeError(f"argument '{arg_name}' must be {arg_type}")
        validated[arg_name] = value

    return validated
