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
| `bim_core.contracts` | contrats **JSON versionnés** échangés entre MCP (voir ci-dessous) |

Types prévus plus tard : `GeometrySnapshot`, `Evidence`, `QuantifiedValue`.

## Contrats JSON versionnés (`bim_core.contracts`)

Les types ci-dessus circulent *en mémoire*. Les **contrats JSON** circulent
*sur disque* entre serveurs MCP : un MCP calcule, écrit un fichier, un autre le
lit. Sans identifiant de version, chaque lecture est un pari sur la forme du
fichier. Ce sous-package centralise **validation, normalisation, migration des
formes historiques et erreurs typées** : ni le producteur ni le consommateur ne
réimplémentent quoi que ce soit.

| Schéma | Contenu | Producteur → consommateur |
|---|---|---|
| `computed_base_quantities/v1` | `BaseQuantities` calculées géométriquement, chaque entrée portant son `global_id` | MCP géométrique → audit (fusion *gap-only* dans le snapshot) |
| `envelope_quantities/v1` | surfaces d'enveloppe agrégées **par type de mur** (+ types hors filtre, en diagnostic) | MCP géométrique → reporting MOA (annexe « Extraction surface enveloppe ») |

Chaque payload porte `schema`, `source` (provenance), `created_at`, et une
`coverage` ou un `summary` selon le contrat.

### Politique de schéma

| Payload | Décision |
|---|---|
| `schema` connu | accepté |
| `schema` présent mais inconnu | **refus dur** (`UnknownSchemaError`) — aucune interprétation de repli |
| `schema` absent, forme legacy reconnue | accepté, **migré explicitement** vers V1, avertissement `legacy_schema_missing` |
| `schema` absent, forme inconnue | refusé (`LegacyShapeError`) |
| `schema` absent, mode strict | refusé (`MissingSchemaError`) |

```python
from bim_core.contracts import load_envelope_quantities

payload = load_envelope_quantities("250613_MN_BAT_envelope.json")
payload.summary.ratio_fac_shab      # 0.9568
payload.par_type[0].net_side_area_m2
```

Toutes les erreurs héritent de `ContractError`, elle-même une `ValueError` :
les consommateurs qui attrapaient déjà `ValueError` restent compatibles.

### Dépréciation : l'absence de `schema` est temporaire

La tolérance aux payloads sans `schema` existe **uniquement** pour ne pas
casser les fichiers déjà produits avant les contrats versionnés. Elle n'est pas
un mode de fonctionnement.

- **Les producteurs doivent réémettre des JSON versionnés** (`schema`, `source`,
  `created_at` renseignés).
- `BIM_CORE_JSON_STRICT_SCHEMA=true` refuse dès aujourd'hui tout payload sans
  `schema` — de quoi vérifier qu'un parc est entièrement migré.
- Ce mode strict deviendra le **défaut** dans une version ultérieure ; la
  tolérance sera alors retirée.

La migration reste appelable explicitement — `migrate_envelope_quantities_legacy_to_v1(...)`,
`migrate_computed_base_quantities_legacy_to_v1(...)` — pour convertir un fichier
une fois pour toutes plutôt que de le migrer à chaque lecture.

### Contrats à venir

- **Findings préliminaires géométriques** — PR 3bis, *après inventaire des 5
  JSON réels* (`*_space_inventory.json`, `*_space_clash_findings.json`,
  `*_surface_loss.json`, `*_boundaries.json`, `*_openings_check.json`). Ce n'est
  pas un contrat mais cinq, aux formes distinctes : les formaliser d'un bloc
  sans inventaire préalable produirait un contrat approximatif.
- **Manifeste de rapport** — en attente d'un **producteur réel**. Aucun code ne
  l'émet aujourd'hui ; pas de contrat spéculatif.

## Provenance

Extrait du MCP monolithique `audit-bim-i3f`. La référence fonctionnelle gelée
est le tag `legacy-i3f-mcp-v1.0` de ce dépôt. Toute évolution d'un contrat doit
préserver la parité (mêmes livrables, mêmes findings, mêmes tests).

## Installation (dev)

```bash
pip install -e /path/to/bim-core
```
