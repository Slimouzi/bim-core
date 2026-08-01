"""Contrat ``envelope_quantities/v1`` — surfaces d'enveloppe calculées.

Produit par le MCP géométrique (IfcOpenShell) à partir d'une maquette IFC,
consommé par le reporting MOA (annexe « Extraction surface enveloppe »).

La donnée métier est **une ligne par type de mur** (``par_type``) — jamais une
ligne par mur élémentaire. ``hors_filtre_type`` porte les types écartés du
total métier : diagnostic, jamais additionné.

Formes legacy tolérées (payloads sans ``schema``, cf. :mod:`.base`) : les JSON
d'enveloppe émis avant la version des contrats. Deux variantes existent dans le
parc et sont migrées à l'identique — celle des premiers exports (clés
``layer_pattern`` / ``n_murs_calque`` / ``seuil_i3f``) et celle du MCP
ifc-geometry (clés ``file`` / ``counts`` / ``methode_facade`` + ventilation
fenêtres/portes).
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .base import (
    ContractPayload,
    ContractSource,
    as_str_list,
    first_present,
    read_json_document,
    remaining_keys,
    resolve_document,
)
from .errors import ContractValidationError

SCHEMA_ENVELOPE_QUANTITIES_V1 = "envelope_quantities/v1"


class EnvelopeTypeRow(BaseModel):
    """Une ligne métier : un type de mur d'enveloppe, agrégé."""

    model_config = ConfigDict(extra="allow")

    type: str | None = None
    n: int | None = Field(default=None, description="Nombre de murs de ce type.")
    etages: list[str] = Field(default_factory=list)
    net_side_area_m2: float | None = Field(
        default=None, description="Aire nette de parement (Archicad BQ NetSideArea)."
    )
    surface_ifc_openshell_m2: float | None = Field(
        default=None, description="Aire recalculée géométriquement, si disponible."
    )
    menuiseries_m2: float | None = None
    fenetres_m2: float | None = None
    portes_m2: float | None = None
    superficie_ouvertures_exterieures_m2: float | None = None


class EnvelopeSummary(BaseModel):
    """Totaux métier. ``superficie_facades_m2`` et ``shab_m2`` sont **requis** :
    sans eux le livrable MOA n'a pas de sens."""

    model_config = ConfigDict(extra="allow")

    superficie_facades_m2: float
    shab_m2: float
    superficie_facades_nette_m2: float | None = None
    superficie_calque_total_m2: float | None = None
    superficie_menuiseries_m2: float | None = None
    superficie_menuiseries_fenetres_m2: float | None = None
    superficie_menuiseries_portes_m2: float | None = None
    ratio_fac_shab: float | None = None
    seuil_i3f: float | None = None
    conforme_seuil: bool | None = None
    methode_facade: str | None = None


class EnvelopeQuantitiesV1(ContractPayload):
    """Payload ``envelope_quantities/v1``."""

    schema_: str = Field(default=SCHEMA_ENVELOPE_QUANTITIES_V1, alias="schema")
    summary: EnvelopeSummary
    par_type: list[EnvelopeTypeRow] = Field(default_factory=list)
    hors_filtre_type: list[EnvelopeTypeRow] = Field(default_factory=list)
    diagnostics: dict[str, Any] = Field(
        default_factory=dict,
        description="Champs producteur hors contrat, conservés tels quels.",
    )

    @field_validator("schema_")
    @classmethod
    def _check_schema(cls, value: str) -> str:
        if value != SCHEMA_ENVELOPE_QUANTITIES_V1:
            raise ContractValidationError(
                f"`schema` invalide : {value!r} (attendu {SCHEMA_ENVELOPE_QUANTITIES_V1!r})."
            )
        return value


# --------------------------------------------------------------------------- #
#  Legacy → V1
# --------------------------------------------------------------------------- #

# Clés legacy consommées par la migration ; le reste part dans ``diagnostics``.
_LEGACY_CONSUMED = {
    "superficie_facades_m2",
    "superficie_facades_nette_m2",
    "superficie_calque_total_m2",
    "superficie_menuiseries_m2",
    "superficie_menuiseries_fenetres_m2",
    "superficie_menuiseries_portes_m2",
    "shab_m2",
    "ratio_fac_shab",
    "seuil_i3f",
    "seuil_3f",
    "conforme_seuil",
    "methode_facade",
    "par_type",
    "hors_filtre_type",
    "file",
}


def is_legacy_envelope_document(doc: dict[str, Any]) -> bool:
    """Reconnaît un JSON d'enveloppe legacy (sans ``schema``).

    Critère : la décomposition métier ``par_type`` **et** les deux totaux qui
    fondent le ratio FAC/SHAB. Volontairement strict — un document qui ne les
    porte pas n'est pas une enveloppe et doit être refusé.
    """
    if not isinstance(doc, dict) or not isinstance(doc.get("par_type"), list):
        return False
    return _is_number(doc.get("superficie_facades_m2")) and _is_number(doc.get("shab_m2"))


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _row_to_v1(row: Any) -> dict[str, Any]:
    if not isinstance(row, dict):
        raise ContractValidationError(
            f"Ligne `par_type` invalide : objet attendu, reçu {type(row).__name__}."
        )
    known = {
        "type",
        "n",
        "nombre",
        "etages",
        "net_side_area_m2",
        "netsidearea_m2",
        "surface_ifc_openshell_m2",
        "ifc_openshell_surface_m2",
        "menuiseries_m2",
        "fenetres_m2",
        "windows_m2",
        "portes_m2",
        "doors_m2",
        "superficie_ouvertures_exterieures_m2",
        "archicad_openings_m2",
    }
    out: dict[str, Any] = {
        "type": row.get("type"),
        "n": first_present(row, "n", "nombre"),
        "etages": as_str_list(row.get("etages")),
        "net_side_area_m2": first_present(row, "net_side_area_m2", "netsidearea_m2"),
        "surface_ifc_openshell_m2": first_present(
            row, "surface_ifc_openshell_m2", "ifc_openshell_surface_m2"
        ),
        "menuiseries_m2": row.get("menuiseries_m2"),
        "fenetres_m2": first_present(row, "fenetres_m2", "windows_m2"),
        "portes_m2": first_present(row, "portes_m2", "doors_m2"),
        "superficie_ouvertures_exterieures_m2": first_present(
            row, "superficie_ouvertures_exterieures_m2", "archicad_openings_m2"
        ),
    }
    out.update({k: v for k, v in row.items() if k not in known})
    return out


def migrate_envelope_quantities_legacy_to_v1(
    doc: dict[str, Any],
    *,
    source: ContractSource | dict[str, Any] | None = None,
    created_at: str | None = None,
) -> dict[str, Any]:
    """Migre un JSON d'enveloppe legacy vers le document ``envelope_quantities/v1``.

    Conversion **explicite et sans invention** : les totaux et lignes sont
    repris tels quels (alias de clés normalisés), les champs producteur hors
    contrat sont conservés dans ``diagnostics``. ``created_at`` reste ``None``
    si l'appelant ne le fournit pas — un fichier legacy ne porte pas sa date de
    production, et la déduire serait une invention.
    """
    if not is_legacy_envelope_document(doc):
        raise ContractValidationError(
            "Document non reconnu comme enveloppe legacy : `par_type` (liste) + "
            "`superficie_facades_m2` + `shab_m2` (nombres) sont requis."
        )

    if source is None and doc.get("file"):
        source = ContractSource(ifc_file=str(doc["file"]))
    if isinstance(source, dict):
        source = ContractSource(**source)

    summary = {
        "superficie_facades_m2": doc["superficie_facades_m2"],
        "shab_m2": doc["shab_m2"],
        "superficie_facades_nette_m2": doc.get("superficie_facades_nette_m2"),
        "superficie_calque_total_m2": doc.get("superficie_calque_total_m2"),
        "superficie_menuiseries_m2": doc.get("superficie_menuiseries_m2"),
        "superficie_menuiseries_fenetres_m2": doc.get("superficie_menuiseries_fenetres_m2"),
        "superficie_menuiseries_portes_m2": doc.get("superficie_menuiseries_portes_m2"),
        "ratio_fac_shab": doc.get("ratio_fac_shab"),
        "seuil_i3f": first_present(doc, "seuil_i3f", "seuil_3f"),
        "conforme_seuil": doc.get("conforme_seuil"),
        "methode_facade": doc.get("methode_facade"),
    }
    return {
        "schema": SCHEMA_ENVELOPE_QUANTITIES_V1,
        "source": source.model_dump() if source is not None else None,
        "created_at": created_at,
        "summary": summary,
        "par_type": [_row_to_v1(r) for r in doc.get("par_type") or []],
        "hors_filtre_type": [_row_to_v1(r) for r in doc.get("hors_filtre_type") or []],
        "diagnostics": remaining_keys(doc, _LEGACY_CONSUMED),
    }


# --------------------------------------------------------------------------- #
#  Entrées publiques
# --------------------------------------------------------------------------- #


def parse_envelope_quantities(
    doc: Any, *, strict: bool | None = None, origin: str | None = None
) -> EnvelopeQuantitiesV1:
    """Valide (et migre si besoin) un document déjà désérialisé."""
    resolved = resolve_document(
        doc,
        expected_schema=SCHEMA_ENVELOPE_QUANTITIES_V1,
        is_legacy=is_legacy_envelope_document,
        migrate=migrate_envelope_quantities_legacy_to_v1,
        strict=strict,
        origin=origin,
    )
    try:
        return EnvelopeQuantitiesV1.model_validate(resolved)
    except ContractValidationError:
        raise
    except ValueError as exc:
        raise ContractValidationError(
            f"Payload {SCHEMA_ENVELOPE_QUANTITIES_V1!r} invalide"
            f"{f' ({origin})' if origin else ''} : {exc}"
        ) from exc


def load_envelope_quantities(path: str, *, strict: bool | None = None) -> EnvelopeQuantitiesV1:
    """Lit, valide (et migre si besoin) un fichier d'enveloppe."""
    return parse_envelope_quantities(read_json_document(path), strict=strict, origin=str(path))


__all__ = [
    "SCHEMA_ENVELOPE_QUANTITIES_V1",
    "EnvelopeQuantitiesV1",
    "EnvelopeSummary",
    "EnvelopeTypeRow",
    "is_legacy_envelope_document",
    "load_envelope_quantities",
    "migrate_envelope_quantities_legacy_to_v1",
    "parse_envelope_quantities",
]
