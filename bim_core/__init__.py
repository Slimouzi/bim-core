"""bim-core — contrats communs partagés par les MCP BIM.

Point d'entrée unique pour les types de domaine stables. Les autres MCP
importent depuis ``bim_core`` (ou ses sous-modules) plutôt que de redéfinir
ces types.

Deux familles :

- **types de domaine** (ce module) — ``Finding``, ``BimObject``, ``WritePlan``,
  ``ModelSnapshot``… échangés en mémoire entre couches.
- **contrats JSON versionnés** (:mod:`bim_core.contracts`) — payloads échangés
  *sur disque* entre MCP, avec validation, normalisation, migration legacy et
  erreurs typées centralisées.
"""

from __future__ import annotations

from . import contracts
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
    # contrats JSON versionnés (sous-package)
    "contracts",
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

__version__ = "0.2.0"
