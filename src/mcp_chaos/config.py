"""Load a FaultPlan from YAML."""

from __future__ import annotations

import yaml

from .faults import (
    DropToolFault,
    ErrorInjectionFault,
    FaultPlan,
    LatencyFault,
    PartialResultFault,
    RegistryInconsistencyFault,
    SchemaDriftFault,
)

_REGISTRY = {
    "latency": LatencyFault,
    "drop_tool": DropToolFault,
    "schema_drift": SchemaDriftFault,
    "partial_result": PartialResultFault,
    "registry_inconsistency": RegistryInconsistencyFault,
    "error_injection": ErrorInjectionFault,
}


def load_fault_plan(path: str) -> FaultPlan:
    with open(path) as fh:
        doc = yaml.safe_load(fh) or {}
    seed = int(doc.get("seed", 0))
    faults = []
    for entry in doc.get("faults", []):
        entry = dict(entry)
        kind = entry.pop("type")
        cls = _REGISTRY.get(kind)
        if cls is None:
            raise ValueError(f"unknown fault type: {kind}")
        try:
            faults.append(cls(**entry))
        except TypeError as exc:
            raise ValueError(f"invalid fields for fault type '{kind}': {exc}") from exc
    return FaultPlan(faults=faults, seed=seed)
