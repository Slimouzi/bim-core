"""Contrats JSON versionnés échangés entre les MCP BIM.

Un contrat = un identifiant ``schema`` (``<nom>/v<N>``), un modèle Pydantic, un
détecteur de forme legacy et une migration explicite. Validation, normalisation,
migration et erreurs typées vivent **ici** : les producteurs (MCP géométrique)
et les consommateurs (audit / reporting) ne réimplémentent rien.

Contrats disponibles :

- ``computed_base_quantities/v1`` — BaseQuantities calculées, keyées ``global_id``.
- ``envelope_quantities/v1`` — surfaces d'enveloppe agrégées par type de mur.
- ``spatial_evidence/v1`` — boîtes englobantes, contenances, encombrements.
  Contrat **né versionné** : aucune forme legacy, un payload sans ``schema`` est
  refusé dans tous les modes.

Politique de schéma (détail dans :mod:`bim_core.contracts.base`) : schéma connu
accepté, schéma inconnu **refusé durement**, schéma absent accepté uniquement
sur forme legacy reconnue — avec migration explicite et avertissement
``legacy_schema_missing``. Cette tolérance est **temporaire** : les producteurs
doivent réémettre des JSON versionnés ; ``BIM_CORE_JSON_STRICT_SCHEMA=true``
refuse dès aujourd'hui tout payload sans ``schema``.
"""

from __future__ import annotations

from .base import (
    STRICT_SCHEMA_ENV,
    WARN_LEGACY_SCHEMA_MISSING,
    ContractPayload,
    ContractSource,
    read_json_document,
    resolve_document,
    strict_schema_enabled,
    utc_now_iso,
)
from .computed_base_quantities import (
    SCHEMA_COMPUTED_BASE_QUANTITIES_V1,
    SOURCE_COMPUTED,
    STATUS_COMPUTED,
    ComputedBaseQuantitiesV1,
    ComputedCoverage,
    ComputedQuantity,
    is_legacy_computed_quantities_document,
    load_computed_base_quantities,
    migrate_computed_base_quantities_legacy_to_v1,
    parse_computed_base_quantities,
)
from .envelope_quantities import (
    SCHEMA_ENVELOPE_QUANTITIES_V1,
    EnvelopeQuantitiesV1,
    EnvelopeSummary,
    EnvelopeTypeRow,
    is_legacy_envelope_document,
    load_envelope_quantities,
    migrate_envelope_quantities_legacy_to_v1,
    parse_envelope_quantities,
)
from .errors import (
    ContractError,
    ContractValidationError,
    LegacySchemaWarning,
    LegacyShapeError,
    MissingSchemaError,
    UnknownSchemaError,
)
from .spatial_evidence import (
    CONTAINMENT_METHODS,
    GEOMETRY_STATUS,
    SCHEMA_SPATIAL_EVIDENCE_V1,
    BoundingBox,
    Containment,
    EvidenceCoverage,
    EvidenceSelection,
    ObjectEvidence,
    SpaceEvidence,
    SpatialEvidenceV1,
    load_spatial_evidence,
    parse_spatial_evidence,
)

#: Identifiants de schéma reconnus par cette version de bim-core.
KNOWN_SCHEMAS = frozenset(
    {
        SCHEMA_COMPUTED_BASE_QUANTITIES_V1,
        SCHEMA_ENVELOPE_QUANTITIES_V1,
        SCHEMA_SPATIAL_EVIDENCE_V1,
    }
)

__all__ = [
    "BoundingBox",
    "CONTAINMENT_METHODS",
    "ComputedBaseQuantitiesV1",
    "ComputedCoverage",
    "ComputedQuantity",
    "Containment",
    "ContractError",
    "ContractPayload",
    "ContractSource",
    "ContractValidationError",
    "EnvelopeQuantitiesV1",
    "EnvelopeSummary",
    "EnvelopeTypeRow",
    "EvidenceCoverage",
    "EvidenceSelection",
    "GEOMETRY_STATUS",
    "KNOWN_SCHEMAS",
    "LegacySchemaWarning",
    "LegacyShapeError",
    "MissingSchemaError",
    "ObjectEvidence",
    "SCHEMA_COMPUTED_BASE_QUANTITIES_V1",
    "SCHEMA_ENVELOPE_QUANTITIES_V1",
    "SCHEMA_SPATIAL_EVIDENCE_V1",
    "SOURCE_COMPUTED",
    "STATUS_COMPUTED",
    "STRICT_SCHEMA_ENV",
    "SpaceEvidence",
    "SpatialEvidenceV1",
    "UnknownSchemaError",
    "WARN_LEGACY_SCHEMA_MISSING",
    "is_legacy_computed_quantities_document",
    "is_legacy_envelope_document",
    "load_computed_base_quantities",
    "load_envelope_quantities",
    "load_spatial_evidence",
    "migrate_computed_base_quantities_legacy_to_v1",
    "migrate_envelope_quantities_legacy_to_v1",
    "parse_computed_base_quantities",
    "parse_envelope_quantities",
    "parse_spatial_evidence",
    "read_json_document",
    "resolve_document",
    "strict_schema_enabled",
    "utc_now_iso",
]
