# bim-core

Contrats communs (types de domaine Pydantic/dataclass) partagés par les MCP
d'audit, de requête, de publication et de reporting BIM.

Ce package est volontairement **sans dépendance métier** : uniquement stdlib +
pydantic. Il fige les interfaces stables que tous les autres MCP produisent ou
consomment, afin qu'un découpage ne change ni les livrables ni les findings.

## Contenu

| Module | Types |
|---|---|
| `bim_core.findings` | `Severity`, `Theme`, `ErrorType`, `Finding` |
| `bim_core.bim_object` | `BimObject`, `ClassificationRef` |
| `bim_core.filters` | `ObjectFilter`, `FindingFilter`, `SuggestionFilter`, `ConfidenceBand`, `SuggestionStatus` |
| `bim_core.write_plan` | `WritePlan`, `ActionResult`, `WritePlanKind` (pattern prepare/apply) |
| `bim_core.model_snapshot` | `ModelSnapshot` |

Types prévus plus tard : `GeometrySnapshot`, `Evidence`, `QuantifiedValue`.

## Provenance

Extrait du MCP monolithique `audit-bim-i3f`. La référence fonctionnelle gelée
est le tag `legacy-i3f-mcp-v1.0` de ce dépôt. Toute évolution d'un contrat doit
préserver la parité (mêmes livrables, mêmes findings, mêmes tests).

## Installation (dev)

```bash
pip install -e /path/to/bim-core
```
