"""Socle commun des contrats JSON : provenance, politique de schéma, chargement.

La **politique de schéma** est centralisée ici (une seule implémentation, tous
les contrats la partagent) :

===========================  ==========================================
Payload                      Décision
===========================  ==========================================
``schema`` connu             accepté
``schema`` présent, inconnu  **refus dur** (:class:`UnknownSchemaError`)
``schema`` absent            accepté **seulement** si le payload correspond
                             à une forme legacy connue → migration explicite
                             vers V1 + avertissement ``legacy_schema_missing``
``schema`` absent, strict    **refus** (:class:`MissingSchemaError`)
===========================  ==========================================

La tolérance aux payloads sans ``schema`` est une **compat temporaire** : elle
existe pour ne pas casser les fichiers déjà produits (JSON d'enveloppe et de
quantités calculées émis avant la version des contrats). Les producteurs
doivent réémettre des JSON versionnés ; le mode strict
(``BIM_CORE_JSON_STRICT_SCHEMA=true``) permet dès aujourd'hui de vérifier
qu'un parc est entièrement migré, et deviendra le défaut.
"""

from __future__ import annotations

import json
import os
import warnings
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .errors import (
    ContractValidationError,
    LegacySchemaWarning,
    LegacyShapeError,
    MissingSchemaError,
    UnknownSchemaError,
)

#: Variable d'environnement activant le refus des payloads sans ``schema``.
STRICT_SCHEMA_ENV = "BIM_CORE_JSON_STRICT_SCHEMA"

#: Code de l'avertissement émis quand un payload sans ``schema`` est migré.
WARN_LEGACY_SCHEMA_MISSING = "legacy_schema_missing"

_TRUE = {"1", "true", "yes", "on"}


def strict_schema_enabled(override: bool | None = None) -> bool:
    """Mode strict actif ? ``override`` (paramètre d'appel) prime sur l'environnement.

    L'environnement est lu **à chaque appel** (jamais mémorisé à l'import) pour
    que l'activation soit testable et modifiable en cours de process.
    """
    if override is not None:
        return override
    return os.environ.get(STRICT_SCHEMA_ENV, "").strip().lower() in _TRUE


def utc_now_iso() -> str:
    """Horodatage ISO-8601 UTC — valeur de ``created_at`` côté producteur."""
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class ContractSource(BaseModel):
    """Provenance d'un payload. Tous les champs sont optionnels : on ne renseigne
    que ce que l'on **sait** (un JSON legacy ne porte pas sa provenance)."""

    model_config = ConfigDict(extra="allow")

    producer: str | None = Field(default=None, description="MCP émetteur, ex. « ifc-geometry ».")
    tool: str | None = Field(default=None, description="Outil MCP appelé.")
    version: str | None = Field(default=None, description="Version du producteur.")
    ifc_file: str | None = Field(default=None, description="Maquette source.")


class ContractPayload(BaseModel):
    """Base des payloads versionnés : ``schema`` + provenance.

    ``source`` et ``created_at`` sont **optionnels** : les fichiers V1 déjà
    produits ne les portent pas. Les producteurs à jour les renseignent
    systématiquement (cf. note de dépréciation du module).
    """

    model_config = ConfigDict(extra="allow", populate_by_name=True)

    schema_: str = Field(alias="schema")
    source: ContractSource | None = None
    created_at: str | None = None

    @field_validator("created_at")
    @classmethod
    def _check_created_at(cls, value: str | None) -> str | None:
        if value is None:
            return None
        try:
            datetime.fromisoformat(str(value))
        except (TypeError, ValueError) as exc:
            raise ContractValidationError(
                f"`created_at` n'est pas un horodatage ISO-8601 : {value!r}"
            ) from exc
        return str(value)

    def to_document(self) -> dict[str, Any]:
        """Payload JSON-sérialisable (clé ``schema``, ``None`` conservés)."""
        return self.model_dump(by_alias=True)


def read_json_document(path: str | Path) -> dict[str, Any]:
    """Lit un document JSON en objet. Erreurs typées, jamais d'``OSError`` nue."""
    p = Path(path)
    if not p.is_file():
        raise ContractValidationError(f"Fichier JSON introuvable : {path}")
    try:
        doc = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ContractValidationError(f"JSON illisible ({path}) : {exc}") from exc
    if not isinstance(doc, dict):
        raise ContractValidationError(
            f"Le document JSON doit être un objet, reçu {type(doc).__name__} ({path})."
        )
    return doc


def resolve_document(
    doc: Any,
    *,
    expected_schema: str,
    is_legacy: Callable[[dict[str, Any]], bool],
    migrate: Callable[[dict[str, Any]], dict[str, Any]],
    strict: bool | None = None,
    origin: str | None = None,
) -> dict[str, Any]:
    """Applique la politique de schéma et renvoie un document **au format V1**.

    Args:
        doc: document JSON déjà désérialisé.
        expected_schema: identifiant attendu, ex. ``"envelope_quantities/v1"``.
        is_legacy: reconnaît une forme legacy (payload sans ``schema``).
        migrate: convertit cette forme legacy en document V1.
        strict: force le mode strict (défaut : ``BIM_CORE_JSON_STRICT_SCHEMA``).
        origin: chemin/fichier, cité dans les messages d'erreur.

    Raises:
        ContractValidationError: document non-objet.
        UnknownSchemaError: ``schema`` présent mais différent de l'attendu.
        MissingSchemaError: ``schema`` absent en mode strict.
        LegacyShapeError: ``schema`` absent et forme non reconnue.
    """
    where = f" ({origin})" if origin else ""
    if not isinstance(doc, dict):
        raise ContractValidationError(
            f"Le document doit être un objet JSON, reçu {type(doc).__name__}{where}."
        )

    # Présence de la CLÉ, pas véracité de la valeur : un payload qui déclare
    # explicitement ``"schema": null`` a bien un schéma — il est simplement
    # invalide. Le traiter comme « absent » l'enverrait en migration legacy,
    # c'est-à-dire accepterait sous warning ce qui doit être refusé durement.
    if "schema" in doc:
        declared = doc["schema"]
        if declared == expected_schema:
            return doc
        raise UnknownSchemaError(
            f"Schéma non reconnu : {declared!r}{where} — attendu {expected_schema!r}. "
            "Aucune interprétation de repli n'est tentée : régénérez le fichier "
            "avec un producteur compatible."
        )

    if strict_schema_enabled(strict):
        raise MissingSchemaError(
            f"Payload sans `schema`{where} refusé : mode strict actif "
            f"({STRICT_SCHEMA_ENV}). Régénérez le fichier au format "
            f"{expected_schema!r}."
        )

    if not is_legacy(doc):
        raise LegacyShapeError(
            f"Payload sans `schema`{where} et forme legacy non reconnue — refusé. "
            f"Attendu {expected_schema!r} (ou une forme legacy connue de ce contrat)."
        )

    warnings.warn(
        f"{WARN_LEGACY_SCHEMA_MISSING}: payload sans `schema`{where} reconnu comme "
        f"forme legacy et migré vers {expected_schema!r}. Compat TEMPORAIRE — le "
        f"producteur doit réémettre un JSON versionné (cf. {STRICT_SCHEMA_ENV}).",
        LegacySchemaWarning,
        stacklevel=3,
    )
    return migrate(doc)


def first_present(mapping: dict[str, Any], *keys: str) -> Any:
    """Première clé présente et non ``None`` — normalisation des alias legacy."""
    for key in keys:
        value = mapping.get(key)
        if value is not None:
            return value
    return None


def as_str_list(value: Any) -> list[str]:
    """Normalise un champ « liste de libellés » (scalaire toléré, vides ignorés)."""
    if value is None:
        return []
    if isinstance(value, (list, tuple, set)):
        return [str(v) for v in value if v not in (None, "")]
    return [str(value)] if value != "" else []


def remaining_keys(doc: dict[str, Any], consumed: set[str]) -> dict[str, Any]:
    """Clés du document non consommées par la migration.

    Elles sont conservées telles quelles dans ``diagnostics`` : on ne perd
    aucune donnée du producteur, et on n'en invente aucune.
    """
    return {k: v for k, v in doc.items() if k not in consumed}


__all__ = [
    "STRICT_SCHEMA_ENV",
    "WARN_LEGACY_SCHEMA_MISSING",
    "ContractPayload",
    "ContractSource",
    "as_str_list",
    "first_present",
    "read_json_document",
    "remaining_keys",
    "resolve_document",
    "strict_schema_enabled",
    "utc_now_iso",
]
