"""Contrat ``computed_base_quantities/v1`` — BaseQuantities calculées géométriquement.

Produit par le MCP géométrique (IfcOpenShell) **sans jamais écrire dans l'IFC**,
consommé par l'audit qui les fusionne *gap-only* dans le snapshot BIMData
(jointure ``uuid == global_id``).

Le tableau ``quantities`` est **plat**, chaque entrée portant son ``global_id`` :
c'est la forme déjà émise en production sous cet identifiant de schéma, et elle
n'est donc pas redéfinie ici. L'accès indexé par identifiant est offert par
:meth:`ComputedBaseQuantitiesV1.by_global_id`.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .base import (
    ContractPayload,
    ContractSource,
    read_json_document,
    remaining_keys,
    resolve_document,
)
from .errors import ContractValidationError

SCHEMA_COMPUTED_BASE_QUANTITIES_V1 = "computed_base_quantities/v1"

#: Provenance des valeurs calculées (par opposition aux valeurs natives BIMData).
SOURCE_COMPUTED = "computed_ifcopenshell"

#: Seules les entrées ``computed`` sont fusionnables ; les autres sont conservées
#: dans le payload pour la traçabilité (pourquoi une quantité manque).
STATUS_COMPUTED = "computed"


class ComputedQuantity(BaseModel):
    """Une quantité calculée pour un élément, identifiée par son ``global_id``."""

    model_config = ConfigDict(extra="allow")

    global_id: str
    quantity: str
    ifc_class: str | None = None
    qto: str | None = None
    value: float | None = None
    unit: str | None = None
    method: str | None = None
    status: str = STATUS_COMPUTED
    source: str | None = None
    reason: str | None = None

    @property
    def is_computed(self) -> bool:
        """Fusionnable : statut ``computed`` **et** valeur présente."""
        return self.status == STATUS_COMPUTED and self.value is not None


class ComputedCoverage(BaseModel):
    """Couverture du calcul — combien d'éléments scannés, calculés, en échec."""

    model_config = ConfigDict(extra="allow")

    n_elements: int | None = None
    n_computed: int | None = None
    n_failed: int | None = None


class ComputedBaseQuantitiesV1(ContractPayload):
    """Payload ``computed_base_quantities/v1``."""

    schema_: str = Field(default=SCHEMA_COMPUTED_BASE_QUANTITIES_V1, alias="schema")
    quantities: list[ComputedQuantity]
    coverage: ComputedCoverage = Field(default_factory=ComputedCoverage)
    warnings: list[str] = Field(default_factory=list)

    @field_validator("schema_")
    @classmethod
    def _check_schema(cls, value: str) -> str:
        if value != SCHEMA_COMPUTED_BASE_QUANTITIES_V1:
            raise ContractValidationError(
                f"`schema` invalide : {value!r} (attendu {SCHEMA_COMPUTED_BASE_QUANTITIES_V1!r})."
            )
        return value

    def by_global_id(self, *, computed_only: bool = True) -> dict[str, list[ComputedQuantity]]:
        """Index ``global_id`` → quantités. ``computed_only`` écarte les entrées
        non fusionnables (``skipped`` / ``failed`` / valeur absente)."""
        index: dict[str, list[ComputedQuantity]] = {}
        for q in self.quantities:
            if computed_only and not q.is_computed:
                continue
            index.setdefault(q.global_id, []).append(q)
        return index


# --------------------------------------------------------------------------- #
#  Legacy → V1
# --------------------------------------------------------------------------- #

_LEGACY_CONSUMED = {"quantities", "coverage", "warnings", "source_ifc"}


def is_legacy_computed_quantities_document(doc: dict[str, Any]) -> bool:
    """Reconnaît un export de quantités calculées legacy (sans ``schema``).

    Critère : ``quantities`` est une liste d'objets portant au minimum
    ``global_id`` et ``quantity`` — la jointure et la sémantique de la valeur.
    Une liste vide n'est pas reconnaissable et est donc refusée.
    """
    if not isinstance(doc, dict):
        return False
    rows = doc.get("quantities")
    if not isinstance(rows, list) or not rows:
        return False
    return all(
        isinstance(r, dict)
        and isinstance(r.get("global_id"), str)
        and r.get("quantity") is not None
        for r in rows
    )


def migrate_computed_base_quantities_legacy_to_v1(
    doc: dict[str, Any],
    *,
    source: ContractSource | dict[str, Any] | None = None,
    created_at: str | None = None,
) -> dict[str, Any]:
    """Migre un export legacy vers le document ``computed_base_quantities/v1``.

    Les entrées sont reprises **telles quelles**. ``coverage`` absent est
    **dérivé** des statuts présents (comptage, pas d'invention) ; ``created_at``
    reste ``None`` si l'appelant ne le fournit pas.
    """
    if not is_legacy_computed_quantities_document(doc):
        raise ContractValidationError(
            "Document non reconnu comme export de quantités calculées legacy : "
            "`quantities` doit être une liste non vide d'objets portant "
            "`global_id` et `quantity`."
        )

    if source is None and doc.get("source_ifc"):
        source = ContractSource(ifc_file=str(doc["source_ifc"]))
    if isinstance(source, dict):
        source = ContractSource(**source)

    rows = doc["quantities"]
    coverage = doc.get("coverage")
    if not isinstance(coverage, dict):
        n_computed = sum(1 for r in rows if r.get("status") == STATUS_COMPUTED)
        coverage = {
            "n_elements": None,  # non déductible : plusieurs quantités par élément
            "n_computed": n_computed,
            "n_failed": len(rows) - n_computed,
        }
    warnings_ = doc.get("warnings")
    return {
        "schema": SCHEMA_COMPUTED_BASE_QUANTITIES_V1,
        "source": source.model_dump() if source is not None else None,
        "created_at": created_at,
        "quantities": rows,
        "coverage": coverage,
        "warnings": list(warnings_) if isinstance(warnings_, list) else [],
        **remaining_keys(doc, _LEGACY_CONSUMED),
    }


# --------------------------------------------------------------------------- #
#  Entrées publiques
# --------------------------------------------------------------------------- #


def parse_computed_base_quantities(
    doc: Any, *, strict: bool | None = None, origin: str | None = None
) -> ComputedBaseQuantitiesV1:
    """Valide (et migre si besoin) un document déjà désérialisé."""
    resolved = resolve_document(
        doc,
        expected_schema=SCHEMA_COMPUTED_BASE_QUANTITIES_V1,
        is_legacy=is_legacy_computed_quantities_document,
        migrate=migrate_computed_base_quantities_legacy_to_v1,
        strict=strict,
        origin=origin,
    )
    try:
        return ComputedBaseQuantitiesV1.model_validate(resolved)
    except ContractValidationError:
        raise
    except ValueError as exc:
        raise ContractValidationError(
            f"Payload {SCHEMA_COMPUTED_BASE_QUANTITIES_V1!r} invalide"
            f"{f' ({origin})' if origin else ''} : {exc}"
        ) from exc


def load_computed_base_quantities(
    path: str, *, strict: bool | None = None
) -> ComputedBaseQuantitiesV1:
    """Lit, valide (et migre si besoin) un fichier de quantités calculées."""
    return parse_computed_base_quantities(read_json_document(path), strict=strict, origin=str(path))


__all__ = [
    "SCHEMA_COMPUTED_BASE_QUANTITIES_V1",
    "SOURCE_COMPUTED",
    "STATUS_COMPUTED",
    "ComputedBaseQuantitiesV1",
    "ComputedCoverage",
    "ComputedQuantity",
    "is_legacy_computed_quantities_document",
    "load_computed_base_quantities",
    "migrate_computed_base_quantities_legacy_to_v1",
    "parse_computed_base_quantities",
]
