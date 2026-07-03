"""bim-core — contrats communs partagés par les MCP BIM.

Point d'entrée unique pour les types de domaine stables. Les autres MCP
importent depuis ``bim_core`` (ou ses sous-modules) plutôt que de redéfinir
ces types.
"""

from __future__ import annotations

from .bim_object import BimObject, ClassificationRef
from .filters import (
    DEFAULT_LIMIT,
    MAX_LIMIT,
    ConfidenceBand,
    FindingFilter,
    ObjectFilter,
    SuggestionFilter,
    SuggestionStatus,
)
from .findings import ErrorType, Finding, Severity, Theme
from .model_snapshot import ModelSnapshot
from .write_plan import ActionResult, WritePlan, WritePlanKind

__all__ = [
    # findings
    "Severity",
    "Theme",
    "ErrorType",
    "Finding",
    # bim_object
    "BimObject",
    "ClassificationRef",
    # filters
    "ObjectFilter",
    "FindingFilter",
    "SuggestionFilter",
    "ConfidenceBand",
    "SuggestionStatus",
    "DEFAULT_LIMIT",
    "MAX_LIMIT",
    # write_plan
    "WritePlan",
    "ActionResult",
    "WritePlanKind",
    # model_snapshot
    "ModelSnapshot",
]

__version__ = "0.1.0"
