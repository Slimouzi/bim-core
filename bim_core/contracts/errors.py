"""Erreurs typées des contrats JSON échangés entre MCP.

Toutes héritent de :class:`ContractError`, elle-même une ``ValueError`` : les
consommateurs historiques qui attrapaient ``ValueError`` (chargement d'un JSON
de quantités calculées, par ex.) continuent de fonctionner sans changement.
"""

from __future__ import annotations


class ContractError(ValueError):
    """Base de toutes les erreurs de contrat JSON."""


class UnknownSchemaError(ContractError):
    """Le payload porte un ``schema`` que cette version de bim-core ne connaît pas.

    **Refus dur, jamais de repli.** Un schéma inconnu signifie soit un producteur
    plus récent que le consommateur, soit un fichier étranger : dans les deux cas
    l'interpréter serait un pari silencieux.
    """


class MissingSchemaError(ContractError):
    """Le payload n'a pas de ``schema`` alors que le mode strict est actif.

    Voir ``BIM_CORE_JSON_STRICT_SCHEMA`` — la tolérance aux payloads sans
    ``schema`` est une **compat temporaire** destinée aux fichiers déjà produits.
    """


class LegacyShapeError(ContractError):
    """Payload sans ``schema`` **et** dont la forme ne correspond à aucun legacy connu.

    C'est le garde-fou central : sans lui, tout JSON non versionné passerait
    silencieusement pour un contrat valide.
    """


class ContractValidationError(ContractError):
    """Le payload est reconnu mais ne respecte pas le contrat (champ requis
    manquant, type invalide, valeur hors domaine)."""


class LegacySchemaWarning(UserWarning):
    """Catégorie des avertissements de compat (``legacy_schema_missing`` …)."""


__all__ = [
    "ContractError",
    "ContractValidationError",
    "LegacySchemaWarning",
    "LegacyShapeError",
    "MissingSchemaError",
    "UnknownSchemaError",
]
